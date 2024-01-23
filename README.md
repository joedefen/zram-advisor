# zram-advisor: Check/Setup/Test zRAM Tool
> **Quick-start**:
> * If running python 5.11+, install `pipx`, and install with `pipx install zram-advisor`
> * else install `pip`, and install with `pip install zram-advisor --user`
> * `zram-advisor` - reports on currently running zRAM 
> * `zram-advisor --setup` - configure/starts zRAM w defaults on system w/o rRAM configured.

`zram-advisor` can:
* Check on your running zRAM and report ill advised settings and zRAM effectiveness.
* Install `zram-fix` which can setup your zRAM and/or reload it with different parameters (e.g., for testing).
* Provide a browser bookmark file to be imported to help testing your settings.

## Checking Your Running zRAM
Here is the sample output of `zram-advisor` w/o arguments on a system with zRAM running: