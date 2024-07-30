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
command=start

usage() {
    echo "$@"
    cat <<END
USE: fix-zram [--(load|reload|unload|setup|unsetup)] [-n|--dry-run] [-cN] [N.Nx] [Nm|Ng]
where:
  --{command} defaults to 'load' but can be one of:
          load      - remove any existing zRAM and load zRAM with optional params
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
shopt -s extglob # permit patterns like *(-)
for arg in "$@"; do
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
        *(-)c[0-9]*)
            count="${arg##*c}"
            ;;
        *(-)load)       command=reload ;;
        *(-)reload)     command=reload ;;
        *(-)unload)     command=unload ;;
        *(-)setup)      command=setup ;;
        *(-)unsetup)    command=unsetup ;;
        -n|--dry-run)   dry_run=yes ;;
        -h|--help|-\?) usage ;;
        *) usage "Unknown option: $arg"  ;;
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
# run a command (or don't)
run() {
    if [[ $dry_run == "yes" ]]; then
        echo 'WOULD ++' "$@"
    else
        echo '++' "$@"
        eval "$@"
    fi
}

########################################################
# unload zram
unload_zram() {
    found=no
    shopt -s nullglob
    devs=(/dev/zram*)
    for dev in "${devs[@]}"; do
        run "swapoff ${dev}"
        found=yes
    done
    shopt -u nullglob
    run 'modprobe -r zram'
    if [[ $found == "no" ]]; then
        echo 'NOTE: zram already unloaded'
    fi
    run "zramctl"
}

########################################################
# initialize zram
load_zram() {
    shopt -s nullglob
    devs=(/dev/zram*)
    for dev in "${devs[@]}"; do
        if [[ $command == 'reload' ]]; then
            unload_zram
        else
            echo "ERROR: ${dev} exists; use --reload to first unload then load"
            exit -1
        fi
        break
    done
    shopt -u nullglob

    # unload zswap just in case
    run "echo 0 > /sys/module/zswap/parameters/enabled"

    run "modprobe zram num_devices=${count}"
    sizeM=$(python3 -c "print(int(round(${zram_sizeM} / ${count} )))")
    for (( ii=0; ii<count; ii++ )); do
        run "echo zstd > /sys/block/zram${ii}/comp_algorithm"
        run "echo ${sizeM}M > /sys/block/zram${ii}/disksize"
        run "echo 0 > /sys/block/zram${ii}/mem_limit"
    done

    run "sysctl -w vm.swappiness=${swappiness} >/dev/null"
    run "sysctl -w vm.watermark_boost_factor=${watermark_boost_factor} > /dev/null"
    run "sysctl -w vm.watermark_scale_factor=${watermark_scale_factor} >/dev/null"
    run "sysctl -w vm.page-cluster=${page_cluster} >/dev/null"

    for (( ii=0; ii<count; ii++ )); do
        run mkswap /dev/zram${ii}
        run swapon --priority ${priority} /dev/zram${ii}
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
ExecStart=/bin/bash ${script_bin_path} -c${count} ${factor}x ${capM}M

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
    run "rm /var/log/${service}.log"
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
    ( set -x; rm $script_bin_path)
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
