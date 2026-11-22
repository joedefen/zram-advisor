#!/bin/bash
#
    #   default kernel settings
swappiness=180
watermark_boost_factor=0
watermark_scale_factor=125
page_cluster=0
priority=100
    #   default options to this script
factor=1.75
capM=$((12*1024))  # the default cap on zRAM
count=1
dry_run=no
command=load

usage() {
    echo "$@"
    cat <<END
USE: fix-zram [--(load|unload|setup|unsetup)] [-n|--dry-run] [-cN] [N.Nx] [Nm|Ng]
where:
  --{command} defaults to 'load' but can be one of:
          load      - swap off/remove any existing zRAM, then load zRAM
          unload    - unloads any existing zRAM
          setup     - copy fix-zram to '/usr/local/bin' and setup service
          unsetup   - remove '/usr/local/bin/fix-zram' and remove service
  -n,--dry-run  - only print commands that would be executed
  -c{integer}   - set number of zram devices
  {float}x      - set zram-size to {float} * ram at most [dflt=$factor]
  {integer}m    - set gross zram-size to {integer} megabytes at most [dflt=${capM}m]
  {integer}g    - set gross zram-size to {integer} gigabytes at most
Currently fixed values are:
    vm.swappiness=$swappiness
    vm.watermark_boost_factor=$watermark_boost_factor
    vm.watermark_scale_factor=$watermark_scale_factor
    vm.page-cluster=$page_cluster
    zRam-swap-priority=100
END
    exit 1
}

########################################################
# restart this program if not root
if [[ $(id --user) != 0 ]]; then
    script_tmp_dir=$(realpath "$0")
    exec sudo bash "${script_tmp_dir}" "$@"
fi

########################################################
# Iterate over command-line arguments
# (no extglob needed: normalize leading dashes, then match the bare token)
for arg in "$@"; do
    token="${arg#-}"   # allow -, --, or no dash
    token="${token#-}"
    case "$arg" in
        [0-9]*[xX]|[0-9]*.[0-9]*[xX])
            factor="${arg%?}"
            ;;
        [0-9]*[mM])
            capM="${arg%?}"
            ;;
        [0-9]*[gG])
            capG="${arg%?}"
            capM=$((capG*1024))
            ;;
        -n|--dry-run)   dry_run=yes ;;
        -h|--help|-\?) usage ;;
        *)
            case "$token" in
                c[0-9]*)     count="${token##*c}" ;;
                load|reload) command=load ;;  # reload: deprecated alias
                unload)      command=unload ;;
                setup)       command=setup ;;
                unsetup)     command=unsetup ;;
                *)           usage "Unknown option: $arg" ;;
            esac
            ;;
    esac
done

########################################################
# Calculations verification
ramM=$(free -m | awk '/^Mem:/ {print $2}')
zram_sizeM=$(python3 -c "print(int(round(${factor} * ${ramM})))")
echo factor=$factor cap=$capM ramM=$ramM zram_size=$zram_sizeM
if (( capM < zram_sizeM )); then
    zram_sizeM="${capM}"
fi
echo OPTS: $command dry-run=$dry_run count=$count factor=$factor capM=$capM
echo INFO: ramM=$ramM zram_sizeM=$zram_sizeM

########################################################
# run a command (or don't); returns the command's status
run() {
    if [[ $dry_run == "yes" ]]; then
        echo 'WOULD ++' "$@"
    else
        echo '++' "$@"
        eval "$@"
    fi
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

# MiB that must come back into RAM to empty one device
zram_need_M() {
    stat=/sys/block/$(basename "$1")/mm_stat
    [[ -r $stat ]] || { echo 0; return; }
    awk '{ d = $1 - $2; print int(d > 0 ? d/1048576 : 0) }' "$stat"
}

mem_avail_M() {
    awk '/^MemAvailable:/ { a=$2 } /^MemFree:/ { f=$2 }
         END { print int((a != "" ? a : f)/1024) }' /proc/meminfo
}

########################################################
# unload zram; abort if it cannot be emptied
unload_zram() {
    shopt -s nullglob
    devs=(/dev/zram*)
    shopt -u nullglob
    if (( ${#devs[@]} == 0 )); then
        echo 'NOTE: zram already unloaded'
        run 'modprobe -r zram'
        run "zramctl"
        return 0
    fi

    if [[ $dry_run != yes ]]; then
        needM=0
        for dev in "${devs[@]}"; do
            (( needM += $(zram_need_M "${dev}") ))
        done
        availM=$(mem_avail_M)
        headM=$(( needM / 10 + 32 ))
        if (( needM + headM > availM )); then
            die "swapoff needs ~${needM}M free, only ${availM}M available; zRAM left as it was"
        fi
    fi

    for dev in "${devs[@]}"; do
        run "swapoff ${dev}" \
            || die "swapoff ${dev} failed; zRAM left as it was - free memory and retry"
    done

    if ! run 'modprobe -r zram'; then
        echo 'WARNING: cannot remove the zram module; resetting devices' >&2
        shopt -s nullglob
        for dev in /dev/zram*; do
            run "echo 0 > /sys/block/$(basename "${dev}")/disksize" \
                || die "cannot reset ${dev}; it is still in use"
        done
        shopt -u nullglob
    fi
    run "zramctl"
}

########################################################
# initialize zram
load_zram() {
    unload_zram

    # unload zswap just in case
    run "echo 0 > /sys/module/zswap/parameters/enabled"

    run "modprobe zram num_devices=${count}" \
        || die "cannot load the zram module"
    sizeM=$(python3 -c "print(int(round(${zram_sizeM} / ${count} )))")
    for (( ii=0; ii<count; ii++ )); do
        run "echo zstd > /sys/block/zram${ii}/comp_algorithm" \
            || die "zram${ii} is not available; unload it first"
        run "echo ${sizeM}M > /sys/block/zram${ii}/disksize" \
            || die "cannot size zram${ii}; it is still in use"
        run "echo 0 > /sys/block/zram${ii}/mem_limit"
    done

    run "sysctl -w vm.swappiness=${swappiness} >/dev/null"
    run "sysctl -w vm.watermark_boost_factor=${watermark_boost_factor} > /dev/null"
    run "sysctl -w vm.watermark_scale_factor=${watermark_scale_factor} >/dev/null"
    run "sysctl -w vm.page-cluster=${page_cluster} >/dev/null"

    for (( ii=0; ii<count; ii++ )); do
        run mkswap /dev/zram${ii} || die "mkswap failed on zram${ii}; run 'fix-zram --unload' to clean up"
        run swapon --priority ${priority} /dev/zram${ii} \
            || die "swapon failed on zram${ii}; run 'fix-zram --unload' to clean up"
    done
    run "zramctl"
}


########################################################
# systemd service setup
setup_systemd() {
    dest="/etc/systemd/system/fix-zram.service"
    service=$(basename "$dest")
    cat <<END > "${dest}"
#!/bin/sh
[Unit]
Description=Init zRAM on boot

[Service]
Type=simple
ExecStart=/bin/bash ${script_bin_path} load -c${count} ${factor}x ${capM}M

[Install]
WantedBy=multi-user.target
END

    run "chmod 644 '$dest'"
    run "systemctl enable --now ${service}"

}
unsetup_systemd() {
    dest="/etc/systemd/system/fix-zram.service"
    service=$(basename "$dest")
    if [ -f "$dest" ]; then
        run "systemctl disable --now ${service}"
        run "rm '$dest'"
    fi
}

########################################################
# sysVinit service setup
setup_sysVinit() {
    wrapper="/etc/init.d/fix-zram-init"
    service=$(basename "${wrapper}")

    cat <<END > "${wrapper}"
#!/bin/bash
### BEGIN INIT INFO
# Default-Start:     2 3 4 5
# Default-Stop:
### END INIT INFO

case "$1" in
  start) sudo bash ${script_bin_path} load -c${count} ${factor}x ${capM}M;;
  stop) sudo bash ${script_bin_path} --unload ;;
  *)     ;;
esac
exit 0
END
    run "chmod 755 '$wrapper'"

    if which chkconfig >/dev/null 2>&1; then
        run "chkconfig --add ${service}"
    elif which update-rc.d >/dev/null 2>&1; then
        run "update-rc.d ${wrapper} defaults"
    fi
    if which service >/dev/null 2>&1; then
        run "service $service enable"
        run "service $service start"
    elif which update-rc.d >/dev/null 2>&1; then
        run "update-rd.d $service enable"
        run "$wrapper start"
    fi

}
unsetup_sysVinit() {
    wrapper="/etc/init.d/fix-zram-init"
    service=$(basename "${wrapper}")
    if which service >/dev/null 2>&1; then
        run "service ${service} stop"
        run "service ${service} disable"
    elif which update-rc.d >/dev/null 2>&1; then
        run "${wrapper} stop"
        run "update-rd.d ${service} disable"
    fi
    run "rm ${wrapper}"
    if which update-rc.d >/dev/null 2>&1; then
        run "update-rc.d -f ${service} remove"
    fi
    run "rm -f /var/log/${service}.log"
}

########################################################
# setup
setup() {
    script_tmp_dir=$(realpath "$0")
    script_bin_path="/usr/local/bin/fix-zram"
    if [[ $script_tmp_dir != $script_bin_path ]]; then
        ( run "cp '$script_tmp_dir' '$script_bin_path'" )
    fi

    init_cmd=$(ps -p 1 -o comm=)
    case "$init_cmd" in
      init)    ( setup_sysVinit ) ;;
      systemd) ( setup_systemd ) ;;
      *) echo unhandled init type "$init_cmd" ;;
    esac
}
########################################################
# unsetup
unsetup() {
    script_bin_path="/usr/local/bin/fix-zram"
    init_cmd=$(ps -p 1 -o comm=)
    case "$init_cmd" in
      init)    ( unsetup_sysVinit ) ;;
      systemd) ( unsetup_systemd ) ;;
      *) echo unhandled init type "$init_cmd" ;;
    esac
    run "rm -f '$script_bin_path'"
}

if [[ $command == 'setup' ]]; then
    setup
elif [[ $command == 'unsetup' ]]; then
    unsetup
elif [[ $command == 'unload' ]]; then
    unload_zram
else
    load_zram
fi
