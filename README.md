# zram-advisor: Check/Setup/Test zRAM Tool
`zram-advisor` can:
* Check on your running zRAM and report ill advised settings and zRAM effectiveness.
* Install `fix-zram` which can setup your zRAM and/or reload it with different parameters (e.g., for testing).
* Provide a browser bookmark file to be imported to help testing your settings.

> **Quick-start**:
* If running python 5.11+, install `pipx`, and install with `pipx install zram-advisor`
* else install `pip`, and install with `pip install zram-advisor --user`
* `zram-advisor` - reports on currently running zRAM 
  * **Unless it reports "NO zRAM"**, then remove your current zRAM solution
    before calling with `--setup-fix-zram`.
* `zram-advisor --setup-fix-zram 2x 15g` - configures/starts zRAM w zRAM limit of the lesser
   of 2x RAM or 15GiB (vary to please or omit to take default of 1.75x 12g).
  **If unsure of zRAM effectiveness or best parameters, delay setup until zRAM is tested (read further).**

> **But, to first test whether zRAM works for well and, if so, make it permanent:**
* Load tested amount: `zram-advisor --load 3x 12g` -- configures zRAM as the minimum of 3xPhysicalRAM
  or (vary as you wish).
* Test with your heaviest system work load (or possibly use the `--gen-test-sites` option below
  to assist creating an artificial load).
* To remove if disappointed with zRAM:
  * run `zram-advisor --unload` or simply reboot.
  * remove `zram-advisor` with `pipx uninstall zram-advisor`.
* If your tested zRAM params work well, make it permanent with:
  * `zram-advisor --setup-fix-zram 2x 12g` - installs `fix-zram`, loads zRAM per
    your given parameters, and installs a systemd service to load on each start.
  * `fix-zram --setup 3x 20g` - to set non-default values (vary to please).

> **Removal Steps -- More than 'pipx uninstall' may be needed.**
  1. if `--setup-fix-zram` was done, run `fix-zram --unsetup`
     to remove itself from `/user/local/bin` and to remove its systemd service
  2. run `pipx uninstall zram-advisor`
    

## Checking Your Running zRAM
#### Checking with zram-advisor
Here is the sample output of `zram-advisor` w/o arguments on a system with zRAM running:
```
13:24:48  Distro : Ubuntu 24.04.2 LTS
             180 : vm.swappiness.................. in [150, 200]
               0 : vm.watermark_boost_factor...... in [0, 0]
             125 : vm.watermark_scale_factor...... in [125, 125]
               0 : vm.page-cluster................ in [0, 0]
             12G : zRAM.disksize.................. >= 11.4G
───────────────────────────────────────────────────────────────────────────────────────────────
            7.6G : Total Memory     eTotal=16.3G/214%
        6.2G/81% : Used              eUsed=8.1G/107%
        1.5G/19% : Available        eAvail=8.2G/107%
   zram0: uncmpr : 2.6G limit=12G
            cmpr : 607.3M/8% 4.34:1 eff=4.23:1 → 3.60:1 (confident)
             RAM : 623.1M/8% most=941M/12% limit=0
```
* The top section shows key parameters for zRAM and suggested ranges (if it did not like those it would preface the range with "NOT in")
* The midsection shows traditional key memory stats on the left, and on the right, the "effective values":
  * **eUsed**: amount of memory used if the compressed part in zRAM were expanded.
    *In this example, we have more memory in use than we have physical RAM (thanks to compression).*
  * **eTotal** and **eAvail**: projected "effective" numbers based on the current compression ratio; these become more accurate as the zRAM memory footprint increases. *In this example, in effect, we have 2.2G memory (not 952.4M) and the "available" RAM is nearly as much as physical RAM (although also using more RAM than physical RAM)*.
* The lower section are stats for each zram device .. typically, there is just one.
    * **uncmpr**: amount of "original" memory stored by zRAM; its "limit" value is officially called 'disksize' which is the name/value you see from `zramctl`.
    * **cmpr**: compressed data size and compression metrics:
      * **factor**: pure compression ratio (how well the algorithm compressed: 2.6G→607.3M = 4.34:1)
      * **effective**: real-world ratio including zRAM's metadata overhead (623.1M actual RAM used for 2.6G data = 4.23:1)
      * **projected**: expected ratio when zRAM fills up, accounting for compression degradation as memory diversifies (3.60:1)
      * **confidence**: reliability of projection based on current usage (uncertain <10%, confident 10-50%, certain >50% of disksize)
    * **RAM**: amount of physical RAM consumed by zRAM including overhead; **most**: largest RAM used since boot.
    
#### Checking with pmemstat
Another app (installable with `pipx` or `pip`) is `pmemstat`. The top of its sample output (on the same system as above) was:
```
10:54:02 Tot=7.6G Used=5.6G Avail=2.1G Oth=0 Sh+Tmp=630.3M PIDs=166
     2.8%/ker MajF/s=21  zRAM=553.6M CR=4.4 eTot:16.4G eUsed:7.4G eAvail:9.0G
 cpu_pct   pswap   other    data  ptotal   key/info (exe by mem)
    52.9   1,960     644   3,419   6,023 T 165x --TOTALS in MB --
───────────────────────────────────────────────────────────────────────────────
     2.5     781      77     932   1,789   19x browser
```
* You can see those same "effective" key memory stats, plus you can see:
  *  kernel cpu% (i.e., the `0.6/ker`). Kernal CPU (most the swap process) can be significant, and that CPU cost is the primary "cost" of using zRAM.

## zram-advisor Options
```
usage: zram-advisor [-h] [-s] [-d] [-t] [--DB] [args ...]
options:
  -s, --setup-fix-zram  install "fix-zram" program and start zRAM
  -d, --dump-fix-zram   print "fix-zram.sh" for manual install
  -t, --gen-test-sites  print "bookmarks.html" to import to a web-browser for load test
  -L, --load            run "fix-zram --load [args ...]>" to test zRAM w/o any footprint
  -U, --unload          run "fix-zram --unload" to remove zRAM test
<
```
* **--setup-fix-zram** installs a programs `fix-ram` and creates a service called `fix-zram-init` to run it on boot.
* **--dump-fix-zram** prints the stock `fix-zram.sh` (e.g., so you can modify it) and install your modified script by running it (e.g., `bash my-fix-zram.sh`).
* **--gen-test-sites** prints a .html to imported into (most) browsers; then open folders of sites to manufacture memory demand (of browsers at least); disable memory saving options and extensions to be most effective.

**Notes:**
* do not install `fix-zram` if w/o uninstalling any competing tool to configure zRAM.
* `systemd` is required for loading zRAM per your specs on boot.

## Controlling zRAM with fix-zram
`fix-zram` is bash script bundled with `zram-advisor`. Its usage is:
```
fix-zram [--(load|unload|setup|unsetup)] [-n|--dry-run] [-cN] [N.Nx] [Nm|Ng]
where:
  --{command} defaults to 'load' but can be one of:
          load      - remove any existing zRAM and load zRAM with optional params
          unload    - unloads any existing zRAM
          setup     - copy fix-zram to '/usr/local/bin' and setup service [dflt=no]
          unsetup   - remove '/usr/local/bin/fix-zram' and remove service [dflt=no]
  -n,--dry-run  - only print commands that would be executed
  -c{integer}   - set number of zram devices
  {float}x      - set zram-size to {float} * ram at most [dflt=1.75]
  {integer}m    - set gross zram-size to {integer} megabytes at most [dflt=12288m]
  {integer}g    - set gross zram-size to {integer} gigabytes at most
Currently fixed values are:
    vm.swappiness=180
    vm.watermark_boost_factor=0
    vm.watermark_scale_factor=125
    vm.page-cluster=0
    zRam-swap-priority=100
```
### fix-zram Run-Time Commands
`load`  and `unload` affect the running system but the effects do not survive reboot. So, these can be used for trialing zRAM.
* `load` sets the `vm.*` parameters shown by `zram-advisor`.
* `unload` and `load` remove preexisting zRAM if running. Removal only works if all memory stored in zRAM can be placed in RAM or another swap device.

Typical use:
* `fix-zram --load 3x 12g` - will unload the current zRAM (if exists and possible), and then install zRAM with sized at the minimum of 3x RAM and 12GB.

### fix-zram Setup Methods
* `fix-zram --setup` - installs `fix-zram` and creates a `zram-init-fix` service which will load zRAM per the defaults on each load with default values.
* `fix-zram --unsetup` - removes the  installed `fix-zram` and removes the `zram-init-fix` service.

Typical use:
* `fix-zram setup 3x 12g` - installs a zRAM init service that start zRAM sized at the minimum of 3xRAM and 12GB on boot.

> The "fixed values" (shown in the usage section above) cannot be varied on the command line,
> but they are reasonable values w/o fretting much.
> If unacceptable, run `sudo nano /usr/local/bin/fix-zram` and adjust the values at the top of the script;
> be aware that another `zram-advisor --setup-fix-zram` will overwrite your changes.