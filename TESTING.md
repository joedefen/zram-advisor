# Manual Test Plan: fresh install + sanity tests

Purpose: wipe every artifact of the previously installed release (and any zRAM it
left loaded), reinstall from this working tree, and sanity-check the audit fixes.

Commands are run from the project root. Steps that touch the system use `sudo`.
The teardown of the *old* release is done by hand (see Step 3) because the old
`fix-zram --unsetup` is itself buggy.

Each code block holds one command per line; run them top to bottom. A blank line
separates each command so a wrapped line is easy to spot. No shell prompts are
included, so any line can be copied verbatim.

---

## Step 1 — Snapshot the current state (so you can prove it changed)

Record which of these exist. This is your "before" baseline.

```bash
free -h

zramctl

swapon --show

ls -l /usr/local/bin/fix-zram

systemctl status fix-zram.service --no-pager

ls -l /etc/systemd/system/fix-zram.service /etc/init.d/fix-zram-init /var/log/fix-zram-init.log 2>/dev/null

ls -l /tmp/fix-zram.sh 2>/dev/null

pipx list | grep -A1 zram-advisor
```

---

## Step 2 — Unload any zRAM left by the old release

Expect `zramctl` empty, no `/dev/zram*` in `swapon`, no `zram` module, and no
recreated `/tmp/fix-zram.sh` (the new `run_script()` uses a private temp file).

```bash
zram-advisor --unload 2>/dev/null || sudo /usr/local/bin/fix-zram --unload

zramctl                # EXPECT empty output

swapon --show          # EXPECT no /dev/zram* entries

lsmod | grep zram      # EXPECT nothing (module unloaded)

ls -l /tmp/fix-zram.sh 2>/dev/null   # EXPECT no such file
```

---

## Step 3 — Remove the old service/daemon and installed script (by hand)

Do **not** use the old release's `--unsetup`. As shipped, its `unsetup()` ran `rm`
unconditionally, so even `--unsetup --dry-run` deleted `/usr/local/bin/fix-zram`;
because it deleted the script it was running, the shell then choked. Observed
symptom (for reference — do not run):

```
WOULD ++ rm '/etc/systemd/system/fix-zram.service'
+ rm /usr/local/bin/fix-zram      <-- executed for real, no "WOULD ++"
bash: : command not found         <-- script deleted itself mid-run
```

That is the bug fixed at [`fix-zram.sh`](zram_advisor/fix-zram.sh:267), where the
self-removal is now wrapped in `run` (so dry-run only prints). Tear the old
install down explicitly:

```bash
sudo systemctl disable --now fix-zram.service 2>/dev/null

sudo rm -f /etc/systemd/system/fix-zram.service

sudo rm -f /etc/init.d/fix-zram-init /var/log/fix-zram-init.log

sudo rm -f /usr/local/bin/fix-zram

sudo systemctl daemon-reload
```

Verify — expect the unit not-found/disabled and each `ls` target gone:

```bash
systemctl status fix-zram.service --no-pager   # EXPECT not found / disabled

ls -l /etc/systemd/system/fix-zram.service     # EXPECT gone

ls -l /usr/local/bin/fix-zram                  # EXPECT gone

ls -l /etc/init.d/fix-zram-init                # EXPECT gone (if sysVinit was used)
```

---

## Step 4 — Uninstall the old package and purge stale artifacts

`pipx uninstall` also removes the `zram-advisor` launcher **symlink** in
`~/.local/bin/`. Expect the final `pipx list` grep to print nothing.

```bash
pipx uninstall zram-advisor

hash -r                         # clear this shell's cached command lookups

rm -rf build dist *.egg-info

find . -name '__pycache__' -type d -prune -exec rm -rf {} +

rm -f /tmp/fix-zram.sh

pipx list | grep zram-advisor   # EXPECT no output
```

---

## Step 5 — Verify a clean slate before reinstalling

Run `hash -r` first. Shells (and custom prompt setups) cache command locations,
so `command -v` can report a path that was already removed — if you see one,
`hash -r` and re-check; do not delete via `command -v`. Expect every command
below to produce no output.

```bash
hash -r

command -v zram-advisor         # EXPECT nothing

ls -l ~/.local/bin/zram-advisor # EXPECT no such file (pipx launcher symlink)

pipx list | grep -i zram        # EXPECT nothing

zramctl                         # EXPECT empty

swapon --show                   # EXPECT no zram

systemctl list-unit-files | grep fix-zram   # EXPECT nothing
```

---

## Step 6 — Fresh install from this working tree

Expect `zram-advisor` to appear in `pipx list`.

```bash
pipx install .          # OR pipx install --force .

pipx list | grep -A1 zram-advisor
```

---

## Step 7 — Verify packaging metadata (the audit changes)

Expect `Requires-Python: >=3.10`, `Requires: ['console-window==1.4.3']`, and
`console-window: 1.4.3`.

```bash
VENV="$HOME/.local/share/pipx/venvs/zram-advisor"

"$VENV/bin/python" -c "import importlib.metadata as m; print('Requires-Python:', m.metadata('zram-advisor')['Requires-Python']); print('Requires:', m.requires('zram-advisor')); print('console-window:', m.version('console-window'))"
```

---

## Step 8 — CLI surface sanity (the `--load` alias + help text)

The usage line must list `-L, --reload, --load` (the old README spelling `--load`
now works instead of erroring).

```bash
zram-advisor --help

zram-advisor --load --help >/dev/null && echo "ALIAS OK"
```

Dev-wrapper alternative (no install needed): `./runner --help`. The wrapper runs
from the project's local `.venv`; create it once with
`python3 -m venv .venv && .venv/bin/python -m pip install -e .` (it auto
re-execs with `.venv/bin/python` when started from another interpreter).

---

## Step 9 — Non-destructive feature sanity

Expect `SCRIPT SYNTAX OK` (the parser is now extglob-free, so plain `bash -n`
validates it); the new `--unsetup --dry-run` emits only `WOULD ++` lines and
deletes nothing; the bookmark count is one per site (~53); and the no-zRAM run
prints `NO zRAM...` then `exit=1`.

```bash
zram-advisor -d > /tmp/fix-zram-dump.sh

bash -n /tmp/fix-zram-dump.sh && echo "SCRIPT SYNTAX OK"

sudo bash /tmp/fix-zram-dump.sh --unsetup --dry-run

ls -l /usr/local/bin/fix-zram      # EXPECT unchanged by the dry-run

zram-advisor -t > /tmp/sites.html

grep -c '<DT><A HREF="https://' /tmp/sites.html     # EXPECT one per site (~53)

zram-advisor; echo "exit=$?"    # EXPECT "NO zRAM..." then exit=1
```

---

## Step 10 — Live load / monitor / unload round-trip

Expect `zram0` at ~12G using `zstd`, swap priority 100, vm params `180 / 0 / 125 /
0`, no `/tmp/fix-zram.sh`, the monitor rendering then printing `Final snapshot:`
on keypress (or Ctrl-C), and the clean state returning after `--unload`.

```bash
zram-advisor --load 2x 12g

zramctl                          # EXPECT zram0, DISKSIZE ~12G, algorithm zstd

swapon --show                    # EXPECT /dev/zram0, priority 100

sysctl vm.swappiness vm.watermark_boost_factor vm.watermark_scale_factor vm.page-cluster

ls -l /tmp/fix-zram.sh 2>/dev/null   # EXPECT no such file

zram-advisor                     # live monitor; keypress prints final snapshot

zram-advisor --unload

zramctl                          # EXPECT empty

swapon --show                    # EXPECT no zram
```

---

## Pass criteria

- Steps 2–5 leave zero zRAM devices, zero fix-zram service/script, and no pipx
  entry for the old release.
- Step 7 reports `>=3.10` and a pinned `console-window==1.4.3`.
- Step 8 shows the `--load` alias.
- Step 9's `-d`/`-t` outputs are well-formed, the no-zRAM run exits 1, and
  `--unsetup --dry-run` prints only `WOULD ++` lines and deletes nothing.
- Step 10 round-trips load → monitor → unload with no `/tmp/fix-zram.sh` residue.
