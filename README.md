# zram-advisor: Check/Setup/Test zRAM Tool
> **Quick-start**:
> * If running python 5.11+, install `pipx`, and install with `pipx install zram-advisor`
> * else install `pip`, and install with `pip install zram-advisor --user`
> * `zram-advisor` - reports on currently running zRAM 
> * `zram-advisor --setup` - configure/starts zRAM w defaults on system w/o rRAM configured.

`zram-advisor` can:
* Check on your running zRAM and report ill advised settings and zRAM effectiveness.
* Install `fix-zram` which can setup your zRAM and/or reload it with different parameters (e.g., for testing).
* Provide a browser bookmark file to be imported to help testing your settings.

## Checking Your Running zRAM
Here is the sample output of `zram-advisor` w/o arguments on a system with zRAM running:
```
$ zram-advisor 
          Distro : Linux Mint 21.3
             180 : vm.swappiness.................. in [150, 200]
               0 : vm.watermark_boost_factor...... in [0, 0]
             125 : vm.watermark_scale_factor...... in [125, 125]
               0 : vm.page-cluster................ in [0, 0]
            1.6G : zRAM.disksize.................. >= 1.4G
================ 410s ================
          952.4M : Total Memory     eTotal=2.2G/239%
      830.2M/87% : Used              eUsed=1.4G/155%
      122.3M/13% : Available        eAvail=800.7M/84%
zram0:
   uncmpr: 814.5M limit=1.6G
     cmpr: 158.5M/17% factor=5.14
     RAM: 165.5M/17% most=240M/25% limit=0

```
* The top section show key parameters for zRAM and suggested ranges (if it did not like those it would preface the range with "NOT in")
* The midsection shows traditional key memory stats on the left, and on the right, the "effective values":
  * **eUsed**: is the amount of memory used if the compressed part in zRAM were expanded; than number is "true".
  * **eTotal** and **eAvail** are projected numbers based on the current compression ratio; these number are more accurate as the zRAM memory footprint grows increases.
* The lower section are stats for each zram device .. typically, there is just one.
    * **uncmpr**: is the amount of "original" memory stored by zRAM; its limit is officially called 'disksize' which is the name/value you see from `zramctl`.
    * **RAM**: is the amount of physical RAM consumed by zRAM including overhead; **most** it the largest RAM used since boot.
    
Another app (installable with `pipx` or `pip`) is pmemstat. The top of it sample output (on the same system as above) was:
```
14:41:39 Tot=952.4M Used=741.5M Avail=210.9M Oth=0 Sh+Tmp=8.7M PIDs=122
     0.6/ker  zRAM=210.2M eTot:2.2G/240% eUsed:1.5G/166% eAvail:705.7M/74%
 cpu_pct   pswap   other    data  ptotal   key/info (exe by mem)
     9.8     945     100     195   1,239 T 122x --TOTALS in MB --
───────────────────────────────────────────────────────────────────────────
     3.3     396      65     106     567   23x chromium
```
* You can see those same "effective" key memory stats, plus you can see kernel cpu% (i.e., the `0.6/ker`). Kernal CPU (most the swap process) can be significant, and that CPU cost is the primary "cost" of using zRAM).

## Setting up zRAM with fix-zram
`fix-zram` is bash script bundled with `zram-advisor`. `fix-zram` usage is:
```
fix-zram [--(load|reload|unload|setup|unsetup)] [-n|--dry-run] [-cN] [N.Nx] [Nm|Ng]
where:
  --{command} defaults to 'load' but can be one of:
          load      - load/start zRAM  with given params or their defaults
          reload    - remove any existing zRAM and load zram
          unload    - unloads any existing zRAM
          setup     - copy fix-zram to '/usr/local/bin' and setup service [dflt=no]
          unsetup   - remove '/usr/local/bin/fix-zram' and remove service [dflt=no]
  -n,--dry-run  - only print commands that would be executed
  -c{integer}   - set number of zram devices
  {float}x      - set zram-size to {float} * ram at most [dflt=1.75]
  {integer}m    - set gross zram-size to {integer} megabytes at most [dflt=12288m]
  {integer}g    - set gross zram-size to {integer} gigabytes at most
```
### zRAM Setup Methods
* `zram-advisor --setup` - installs `fix-zram` and creates the `zram-init-fix` service which will load zRAM per the defaults on each load
* `zram-advisor --setup` - installs `fix-zram` and creates the `zram-init-fix` service which will load zRAM per the defaults on each load