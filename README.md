## zram-advisor: Check/Test/Setup zRAM Tool

zRAM is compressed swap held in RAM. On a favorable workload it stores 3-4x more than it occupies, so an 8GB machine can behave like a 16GB one. `zram-advisor` tells you whether that is happening on *your* machine, lets you try different sizes safely, and can install the settings permanently.

**What it can help you do:**
- **Evaluate** - live stats and projections for the zRAM already running
- **Tune** - load a test configuration, run your workload, watch the result
- **Make permanent** - install a small service that loads zRAM at boot

**About `zram-advisor --load`** (as used in the steps below):
- **`--load` can replace existing zRAM, whoever installed it** (e.g., distro default, `zram-config`, `zramswap`, `zram-generator`, an earlier `zram-advisor --load`). It does not change that provider's configuration; see Step 5.
- **`--load` first empties zRAM**, so memory in use at that moment must fit in physical RAM; otherwise it aborts and leaves zRAM as it was. If too much used memory cripples `--load`, reduce memory demand or reboot.

---

## Step 1. Install zram-advisor

Python 3.11 or newer: `pipx install zram-advisor`

## Step 2. Run zram-advisor

Run: `zram-advisor` (shows a live screen of what zRAM is doing and updates frequently).

**If another zRAM provider is installed,** the screen reports on that zRAM unchanged, so you can evaluate it as is (skip to Step 3). To use zram-advisor's settings instead, continue below.

**To load zRAM, or replace existing zRAM,** run `zram-advisor --load` (works with or without zRAM loaded):
* After unloading any existing zRAM, it creates zRAM sized at 1.75x RAM, capped at 12GB, with recommended kernel parameters.
* No zRAM changes survive a reboot, so it is safe to experiment; reboot to return to the previous state.

## Step 3. Evaluate effectiveness

Use the machine normally or under heavy load; for artificial load, try:

* `zram-advisor --gen-test-sites > test-sites.html`, and
* import those bookmarks into your browser and open several folders.

To evaluate, watch the numbers from `zram-advisor`; e.g.:

```
zram-advisor  [q]uit
13:24:48  Distro : Ubuntu 24.04.2 LTS
             180 : vm.swappiness.................. in [150, 200]
               0 : vm.watermark_boost_factor...... in [0, 0]
             125 : vm.watermark_scale_factor...... in [125, 125]
               0 : vm.page-cluster................ in [0, 0]
             12G : zRAM.disksize (1.6x)........... >= 11.4G
───────────────────────────────────────────────────────────────────────────────
            7.6G : Total Memory     eTotal=16.3G/214%
        6.2G/81% : Used              eUsed=8.1G/107%
        1.5G/19% : Available        eAvail=8.2G/107%
   zram0: uncmpr : 2.6G limit=12G
            cmpr : 607.3M/8% 4.34:1 eff=4.23:1 ➡ 3.60:1 (confident)
             RAM : 623.1M/8% most=941M/12% limit=0
```

Read it in three parts:
* The top block is the kernel parameters and zRAM size, each marked `in` its recommended range or `NOT in`. The `(N.Nx)` after `zRAM.disksize` is the multiplier in effect (disksize / RAM).
* The middle block compares physical memory with the *effective* memory compression is buying you (i.e., with the `e...` numbers).
* The bottom block is the per-device detail, where
  * `cmpr:` includes `eff=`, the current net compression ratio, and after (`➡`), the projected value if zRAM were to max out.
  * `RAM:` shows (1) physical RAM taken by zRAM now, (2) peak since boot, and (3) configured limit (0 means no explicit limit).

You want `eff` at least 2:1 or better, `eTotal` well above 100% of physical RAM, and the separator line quiet. If the separator carries an "outside recommendation" warning, or the projection says `(uncertain)`, the numbers are not ready to judge yet - keep using/loading the machine. Address concerns:

| Concern | Solution |
|---------|----------|
| Compression ratio <2:1 | Your workload may not compress well - consider not using zRAM |
| Hitting the disksize limit | Increase the size: `--load 3x 15g` (e.g., from the 1.75x/12g default) |
| `RAM:` peak at limit | `limit=` (i.e., mem_limit) raise or set no limit |
| Kernel parameters "NOT in" | Loading with `--load` or `--setup-fix-zram` sets these for you |
| Projection is "uncertain" | Increase memory demand to get a reliable projection |
| High kernel CPU (>10%) | Reduce zRAM usage, or reconsider whether the benefit is worth the cost |

## Step 4. Tune, then repeat

Change one thing at a time and re-measure. Re-loading replaces the temporary zRAM.

1. Alter zRAM; e.g., `zram-advisor --load 3x 15g` (for more zRAM), or `--load 1.5x 10g` (for less).
2. Run your workload again and watch the `zram-advisor` screen.
3. Repeat until your zRAM settings seem best for you.


**If another provider owns zRAM,** either apply the numbers in its configuration (zram-advisor cannot edit another service's setup) or replace it with `--load` (Step 2).

## Step 5. Make it permanent (using zram-advisor)

Once the settings hold up, run: `zram-advisor --setup-fix-zram 3x 15g` (for example).

This installs `fix-zram` to `/usr/local/bin/`, creates a boot service with those numbers, and starts it now, replacing loaded zRAM (free-memory rule applies). Repeat the setup command with new values to adjust them.

**If another provider owns zRAM,** disable it first (e.g. `systemctl disable --now <its service>`) so the two boot services do not compete for the device.

Or, to undo everything related to `zram-advisor`:

- `fix-zram --unsetup` - remove the service and the installed script
- `pipx uninstall zram-advisor` - remove the monitor itself

---

For ongoing day-to-day memory watching, `pmemstat` (`pipx install pmemstat`) shows zRAM stats beside process memory usage, including the kernel CPU cost. As of Nov 2026, no other memory tools (e.g., `top` and `htop`) project zRAM effectiveness.  Or run `zram-advisor` for the focused view.
