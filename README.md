## zram-advisor: Check/Test/Setup zRAM Tool

`zram-advisor` helps you evaluate, tune, and configure zRAM (compressed swap in RAM) for Linux systems. zRAM can effectively expand your usable memory by compressing swap data, often achieving 3-4x compression ratios. Thus, a 8GB system might behave similar as if it had 16GB with favorable loads.

**What zram-advisor does:**
- **Evaluate**: Monitor your current zRAM effectiveness with real-time stats and projections
- **Tune**: Test different zRAM configurations without making permanent changes
- **Make Permanent**: Install and configure zRAM to load automatically on boot

#### ⯈ How to Install zRAM-advisor

Install using `pipx` (Python 3.11+) or `pip`:
- `pipx install zram-advisor         # Preferred method`
- `pip install zram-advisor --user   # Alternative`

#### ⯈  Your First Run

Simply run `zram-advisor` to see your current zRAM status. If you see "NO zRAM", you'll need to either:
- Load zRAM temporarily for testing: `zram-advisor --load 2x 12g`
- Set up zRAM permanently: `zram-advisor --setup-fix-zram 2x 12g`

**Note:** Before setting up zRAM, remove any existing zRAM solution (e.g., `zram-config`, `zramswap`) to avoid conflicts.

#### ⯈ What zram-advisor Can Do For You

- **Evaluate:** Run `zram-advisor` (no arguments) to see live updating stats showing:
  - Current compression ratios (algorithm efficiency vs real-world including overhead)
  - Projected effectiveness when zRAM fills up
  - Effective memory (how much uncompressed memory you're actually using)
  - Kernel parameters and whether they're optimal

- **Tune:** Test different configurations without permanent changes:
  - `zram-advisor --load 3x 12g # Load zRAM with 3x RAM capacity, max 12GB`
  - `zram-advisor # Run your workload, then check effectiveness`
  - `zram-advisor --load 2x 15g # Not happy? Try different settings`
  - `zram-advisor --unload  # or just reboot # Remove test configuration`

- **Make Permanent:** Once you've found settings that work well:
  - `zram-advisor --setup-fix-zram 2x 12g # Install fix-zram and create systemd service`
  - `fix-zram --setup 3x 15g # Later, adjust if needed`

---
## How to Evaluate zRAM Effectiveness

#### ⯈ Interpreting the Output

When you run `zram-advisor`, you'll see output like this:

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

**Top section** - Kernel parameters and their recommended ranges:
- Lines show actual values and whether they're in acceptable ranges
- "NOT in" prefix means a parameter is outside recommended values
- `disksize` is the maximum uncompressed data zRAM will accept

**Middle section** - Memory statistics with "effective" projections:
- **Total Memory**: Physical RAM installed
- **eTotal**: Projected total effective memory at full zRAM capacity (214% of physical in this example)
- **Used**: Currently used physical RAM
- **eUsed**: Effective memory used if compressed data were expanded (107% of physical - you're using more than your physical RAM thanks to compression!)
- **Available**: Remaining available physical RAM
- **eAvail**: Projected effective memory available

**Bottom section** - Per-device zRAM statistics (usually just zram0):
- **uncmpr**: Uncompressed data stored in zRAM (2.6G out of 12G limit)
- **cmpr**: Compressed data details:
  - `607.3M/8%`: Actual compressed size and percentage of disksize used
  - `4.34:1`: Pure compression ratio (algorithm efficiency: 2.6G→607.3M)
  - `eff=4.23:1`: Effective ratio including zRAM metadata overhead (623.1M actual RAM for 2.6G data)
  - `→ 3.60:1 (confident)`: Projected ratio when zRAM fills, with confidence level
    - `uncertain`: <10% of disksize used - projection unreliable
    - `confident`: 10-50% used - good confidence
    - `certain`: >50% used - high confidence
- **RAM**: Physical RAM consumed by zRAM
  - `623.1M/8%`: Current usage and percentage of physical RAM
  - `most=941M/12%`: Peak usage since boot
  - `limit=0`: No configured limit (0 means unlimited)

#### ⯈ Judging zRAM Effectiveness

**✅ zRAM is working well when:**
- Compression ratio (eff) is **≥3:1** - good compression efficiency
- eTotal is **≥150%** of physical RAM - significant memory expansion
- eUsed is **>100%** of physical RAM - you're using more memory than you physically have
- Confidence is **"confident"** or **"certain"** - projections are reliable
- Kernel parameters show **"in"** ranges (not "NOT in")
- Kernel CPU overhead is low (check with `pmemstat` if available, look for <5% kernel CPU)

**❌ zRAM may not be worthwhile when:**
- Compression ratio is **<2:1** - poor compression, not worth the CPU overhead
- eTotal is **<120%** of physical RAM - minimal memory gain
- You see **"NOT in"** warnings for kernel parameters - suboptimal configuration
- Kernel CPU is consistently **>10%** - swap overhead is too high
- `uncmpr` frequently hits the `limit` (disksize) - need larger disksize
- RAM usage hits `limit` - need to increase mem_limit or reduce disksize multiplier

**🔧 What to change when zRAM isn't performing well:**

| Problem | Solution |
|---------|----------|
| Compression ratio <2:1 | Your workload may not compress well - consider not using zRAM |
| Hitting disksize limit | Increase the size limit: `--load 3x 15g` (was 2x 12g) |
| High kernel CPU (>10%) | Reduce zRAM usage or reconsider if benefit outweighs cost |
| Kernel params "NOT in" | zram-advisor sets these automatically with `--load` or `--setup-fix-zram` |
| Confidence is "uncertain" | Load more data into zRAM to get reliable projections |
| RAM limit being hit | Increase the multiplier (e.g., 3x instead of 2x) |

---

## How to Tune zRAM with zram-advisor

Follow this workflow to find optimal zRAM settings:

1. **Load zRAM with Test Configuration**
    - Start with a conservative configuration: `zram-advisor --load 2x 12g`
    - This configures zRAM to use at most 2x your physical RAM or 12GB, whichever is smaller.

2. **Generate System Load.** Load your system either:
    - **Normally:** Run your typical heavy workload (multiple browsers, IDEs, virtual machines, etc.)
    - **Artificially:**
      - Use the bookmark generator:
        - `zram-advisor --gen-test-sites > test-sites.html`

      - Import into your browser, then open multiple bookmark folders
      -  Disable any memory-saving browser extensions for accurate testing

3. **Evaluate Performance.**
    - While the system is loaded, run: `zram-advisor`
    - Watch the live updating stats.
    - Let it run for several minutes to collect data.

4. **Adjust and Repeat.** Based on the results:
    - **If compression is good (≥3:1) but hitting disksize limit:**
      - Increase size `zram-advisor --load 3x 15g`
    - **If RAM usage is high but disksize isn't filling:**
      - Reduce multiplier: `zram-advisor --load 1.5x 10g`
    - **If compression is poor (<2:1):**
      - zRAM may not help your workload - consider not using it

5. **Verify Stability**
    - Once you find good settings, run with them for a day or two before making permanent.

6. **Remove Test Configuration**
    - When done testing: `zram-advisor --unload  # or just reboot`

---

## How to Make zRAM Permanent

Once you've found good settings, make them permanent; e.g.,:
 - `zram-advisor --setup-fix-zram 2x 12g`

This will:
1. Install `fix-zram` to `/usr/local/bin/`
2. Create `fix-zram-init.service` to load zRAM on boot
3. Load zRAM immediately with your specified settings

#### ⯈ Adjusting Permanent Settings

To change settings after installation, repeat with new args; e.g.:
  - `fix-zram --setup-fix-ram 3x 15g`

#### ⯈ Advanced: Customizing Fixed Parameters

The following parameters are set automatically but cannot be changed via command line:
- `vm.swappiness=180` - Aggressiveness of swap usage
- `vm.watermark_boost_factor=0` - Memory reclaim behavior
- `vm.watermark_scale_factor=125` - When to start reclaiming memory
- `vm.page-cluster=0` - Pages to swap at once (0=single pages for compressed swap)

To modify these, edit the script: `sudo nano /usr/local/bin/fix-zram`
  - **Warning:** Re-running `zram-advisor --setup-fix-zram` overwrites your customizations.

#### ⯈ Removing zRAM Permanently

To completely remove zRAM:

1. Remove the fix-zram service and script: `fix-zram --unsetup`
2. Uninstall zram-advisor: `pipx uninstall zram-advisor`

---

## Reference

#### ⯈ Command Reference

```
usage: zram-advisor [-h] [-s] [-d] [-t] [-L] [-U] [--DB] [args ...]

options:
  -h, --help            show this help message
  -s, --setup-fix-zram  install fix-zram and create systemd service
  -d, --dump-fix-zram   print fix-zram.sh script for manual installation
  -t, --gen-test-sites  generate bookmarks.html for browser load testing
  -L, --load [args]     load zRAM temporarily for testing (e.g., 2x 12g)
  -U, --unload          unload temporary zRAM configuration
  --DB                  debug mode

args format:
  {float}x              multiply physical RAM by this factor (default: 1.75)
  {integer}g|m          maximum size in gigabytes or megabytes (default: 12g)

examples:
  zram-advisor                    # monitor current zRAM
  zram-advisor --load 3x 15g      # test with 3xRAM, max 15GB
  zram-advisor --setup-fix-zram 2x 12g  # make permanent
```

#### ⯈ fix-zram Command Reference

The `fix-zram` script is installed by `--setup-fix-zram`:

```
fix-zram [--(load|unload|setup|unsetup)] [-n|--dry-run] [args ...]

commands:
  --load       load zRAM with specified parameters (temporary, until reboot)
  --unload     unload current zRAM (fails if memory can't be swapped out)
  --setup      install to /usr/local/bin and create systemd service
  --unsetup    remove installed script and systemd service

options:
  -n, --dry-run  show commands without executing

examples:
  fix-zram --load 3x 12g     # test configuration
  fix-zram --setup 2x 15g    # make permanent
  fix-zram --unsetup         # remove everything
```

#### ⯈ Everyday Monitoring with pmemstat

For day-to-day memory monitoring, consider installing `pmemstat`, which shows zRAM stats alongside process memory usage:
- install: `pipx install pmemstat`
- usage: `pmemstat`

Output includes effective memory stats and kernel CPU overhead, helping you monitor the ongoing cost/benefit of zRAM.

---

**Project:** [https://github.com/joedefen/zram-advisor](https://github.com/joedefen/zram-advisor)
**Issues:** [https://github.com/joedefen/zram-advisor/issues](https://github.com/joedefen/zram-advisor/issues)
