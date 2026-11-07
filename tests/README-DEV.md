# zram-advisor: working on the source tree

This is the developer companion to [`README.md`](../README.md), which documents
the tool for its users.  Here we document the two things a maintainer needs and
a user does not: the **test gate** and the **release gate** (`./bless`).

This file lives in `tests/`, so its links point one directory up.  The commands
assume the repository root, which is where the gate has to be run.

The manual, root-using checks are separate and stay in
[`TESTING.md`](../TESTING.md) (and its rungs spec [`TESTING.ini`](../TESTING.ini));
this file covers what runs as an ordinary user in `.venv`.

## Layout and single sources of truth

| Path | Owns |
| --- | --- |
| [`zram_advisor/__init__.py`](../zram_advisor/__init__.py) | `__version__`, and nothing else.  The build backend reads it, `zram-advisor --version` prints it, `bless` reads the line without importing the package. |
| [`pyproject.toml`](../pyproject.toml) | Name, description, keywords, `requires-python`, runtime dependencies, the SPDX `license` and `license-files`, the `test`/`dev` extras, and the pytest, coverage and ruff configuration. |
| [`bless`](../bless) | The release gate, emitted verbatim from [`../../blessd/bless`](../../blessd/bless) by that repo's `build.py`.  It holds no copy of this project's identity, and it is never edited here. |
| [`blessd/docs/release-strategy.md`](../../blessd/docs/release-strategy.md) | The release strategy every project shares: the branch model, the stages, the rehearsal, the credentials.  This file documents only what is particular to `zram-advisor`. |
| [`tests/inspect_dist.py`](inspect_dist.py) | The distribution inspector.  `bless` refuses to upload a wheel and sdist it has not inspected with this file. |
| [`runner`](../runner) | Runs the tree from source (`zram_advisor.main`) for debugging, under `.venv/bin/python`.  It installs nothing and never writes to `~/.local/bin`, so it cannot displace a released `zram-advisor`. |
| [`.gitignore`](../.gitignore) | Keeps gate artifacts (`build/`, `dist/`, `.coverage*`, caches, `*.whl`, `*.tar.gz`) out of `git status`, because the gate refuses a dirty tree. |

The version lives in exactly one place.  `pyproject.toml` declares
`dynamic = ["version"]`, so flit reads `zram_advisor/__init__.py`; a
`X.Y.Z.99.N` rehearsal rewrites that line only inside a throwaway copy.

Almost nothing needs a `[tool.bless]` table: `NAME = zram-advisor`,
`MODULE = zram_advisor`, the console script and the inspector are all derived
from what is already there.  The one setting written out is `branches`, which
names the branches `publish` releases from -- see
[the branch model](#the-branch-model-is-a-setting-not-a-convention) below.

## Where the package lives

This tree follows the per-project environment model: the package lives in the
checkout, not in a shared site directory.  Nothing here installs with
`pip --user` any more, so no project can shadow another's dependency.

| Thing | Where | Made by |
| --- | --- | --- |
| Editable package + this project's `dev` extra | `.venv/` in this tree | `bt penv` |
| The runnable console script | `~/.local/bin/zram-advisor` | `bt edit` (a symlink into `.venv/bin`) or `bt test` / `bt prod` / `pipx install` (pipx's own venv) |
| A released artifact, isolated per app | `~/.local/share/pipx/venvs/zram-advisor` | `bt test` / `bt prod` |

Two invariants:

1. `.venv` is the **editable/debug** environment: the interpreter VS Code
   selects and the one `./bless`, pytest and a debugger run under, so
   breakpoints land in the tree.  It holds an editable install
   (`-e '.[dev]'`), never a built copy.
2. Exactly **one owner** of `~/.local/bin/zram-advisor` at a time -- `bt edit`
   links it into `.venv/bin`, `bt test`/`bt prod` let pipx own it -- and no
   command claims it with `pip --user`.

Run the source without owning the entry point:

    ./runner                      # re-execs into .venv/bin/python
    .venv/bin/python ./runner     # the same, spelled out

`runner` installs nothing and never writes to `~/.local/bin`, so a source run
and a released install cannot collide.  When the command on `PATH` should
follow the tree instead, hand the entry point to it:

    bt edit        # ~/.local/bin/zram-advisor -> .venv/bin/zram-advisor

`bt edit` and `bt test`/`bt prod` are a switch, not two installs: the last one
run owns the link.  Do not `pipx install --editable` for this project; that
would create a second editable install `bt edit` does not manage.  `bt status`
prints the owner, pipx's own record, the editable `.venv` and the VS Code
interpreter, plus any leftover copy from the old model that `bt clean` removes.

VS Code selects `.venv` (that is the `Editable .venv` path `bt status` prints);
to debug a released artifact instead, select
`~/.local/share/pipx/venvs/zram-advisor/bin/python`.  This project ships no
systemd unit of its own -- `fix-zram --setup` creates one for the installed
script -- but if you add one, name the stable path so a restart re-resolves the
link:

    ExecStart=%h/.local/bin/zram-advisor

## The test gate

Build what the gate needs with `bt`, which puts the editable package plus the
`dev` extra into this tree's `.venv` (and the gate's tool floors with it):

    bt penv        # from the project root; `bt penv zram-advisor` from elsewhere

`bless` runs every stage with `sys.executable`, so it has to be *that*
interpreter -- the one holding `console-window` and the dev extra.  Activate the
virtualenv first, or start the gate by hand:

    .venv/bin/python ./bless

Then the commands `bless` runs, in the same order, on the same interpreter:

    python -m ruff check .
    python -m compileall -q zram_advisor tests
    python -m pytest -q --cov=zram_advisor --cov-report=term-missing

The coverage floor (38%) is enforced through
`[tool.coverage.report] fail_under`.  It was set just below the measured number
when the gate was adopted; raise it when the number rises, never lower it.

The ruff selection is committed rather than inherited
(`[tool.ruff.lint] select = ["E4", "E7", "E9", "F", "I", "UP", "B"]`,
`target-version = "py310"`) so that no user or global configuration can change
what the gate enforces.

`zram-advisor --version` is answered by argparse before `/etc/os-release` is
read or the curses screen is touched, because the smoke stage of the release
gate runs it as an ordinary user on a machine with no saved state.

## The release gate: `./bless`

`./bless` takes no arguments and has no flag that skips a stage.  It always runs
everything, then prints what it has in hand and asks one question:

    ====> Enter test or publish or quit:

Only `test` and `publish` are accepted, spelled in full; anything else is asked
again.  Enter, `quit` or Ctrl-C stops with nothing tagged, uploaded or pushed.

**Stages, in order**

1. **preflight** -- clean tree, the `vX.Y.Z` tag absent, `twine>=7` and
   `packaging>=26` present.
2. **index check** -- refuses if `__version__` is already on PyPI, printing
   every published version, before anything is built or uploaded.
3. **gates** -- the three commands above.
4. **build** -- into `build/bless-<version>/`, wiped first, so no older
   artifact can be sent by mistake.
5. **inspect** -- `tests/inspect_dist.py` against the wheel and the sdist.
6. **check** -- `twine check --strict` on both files.
7. **smoke** -- installs the built wheel into a throwaway venv and runs
   `zram-advisor --version`, which must print the version being released.
8. **branch plan** -- refuses a detached HEAD, a branch that is not one of the
   release branches, a release branch missing locally or on origin, two
   branches that have diverged, or a push that would not fast-forward.

**`test`** is the rehearsal and never spends the working version.  It copies the
tree to `build/bless-test-<version>/src`, rewrites `__version__` to
`X.Y.Z.99.N` (`N` is one past the highest suffix TestPyPI already holds for
that base), builds, inspects and smoke-tests the copy, and uploads only to
`test.pypi.org`.  No tag, no branch, no push.

**`publish`** fast-forwards the release branches to one commit, tags `vX.Y.Z`,
uploads the two inspected files to PyPI, verifies the index, and pushes those
branches and the tag.

**Credentials** are resolved per index -- `TWINE_PASSWORD` for PyPI,
`TWINE_TESTPYPI_PASSWORD` for TestPyPI, each overruling the `~/.pypirc` section
whose `repository` matches that index's upload URL -- so a PyPI token is never
spent on a rehearsal.  A missing credential is a refusal before `twine` starts.

There is no CI publish job, on purpose: the upload is irreversible and is run by
the owner from the development tree, so the safety lives in one inspectable
command.  CI stays a gate.

## The branch model is a setting, not a convention

`bless` publishes only from a branch it was told about, and pushes every branch
it was told about.  Which ones those are is `[tool.bless] branches` in
[`pyproject.toml`](../pyproject.toml), and there are two shapes:

* `branches = ["main"]` -- one release branch.  Nothing is aligned, and `publish`
  pushes `main` and the tag.  This is what this project uses, so a small change
  can be published straight from the trunk.
* `branches = ["main", "dev"]` -- the default when the setting is absent.  While
  you are on `main`, `dev` does not have to exist yet: the trunk alone satisfies
  the model, so `publish` releases from `main` and pushes only what exists.  Once
  `dev` has been created it also has to exist as `origin/dev`, and whichever of
  the two lags is fast-forwarded onto the other before the tag, so a release
  always leaves them at one commit.

Either way the gate refuses a branch it was not told about, a branch it has to
push that is missing on origin, two branches that have diverged, and a push that
would not fast-forward.  What a single branch cannot do is notice that a
development branch was left behind: merging `dev` into `main` stays your job.

Switching to the pair is one line in `pyproject.toml` plus the branch itself:

    git branch dev
    git push -u origin dev

## What the inspector asserts

[`tests/inspect_dist.py`](inspect_dist.py) is the one implementation, used by
`bless` and, once CI is wired up, by CI; expectations are read from
`pyproject.toml` and the package, never from the artifact under test.

* **wheel** -- `Name`, `Version`, `Summary`, `Requires-Python`, `Keywords`,
  `License-Expression` and the *runtime* `Requires-Dist` names match
  `pyproject.toml`; every declared `license-files` entry is listed in
  `License-File`; every `zram_advisor/*.py` is present; the two runtime data
  files `fix-zram.sh` and `random-sites.txt` are present; a `LICENSE` is
  carried; no `tests/`, no `.venv`, no `__pycache__`, no `.pyc`.
* **sdist** -- carries `pyproject.toml`, `README.md`, `LICENSE`,
  `zram_advisor/__init__.py`, `zram_advisor/main.py`, `zram_advisor/fix-zram.sh`
  and `zram_advisor/random-sites.txt`; the `__version__` inside the sdist
  equals the artifact version; no venv or bytecode.

Run it by hand on any built pair:

    python tests/inspect_dist.py build/check/zram_advisor-1.1.7-py3-none-any.whl \
                                build/check/zram_advisor-1.1.7.tar.gz

## Releasing, in three steps

1. Bump `__version__` in [`zram_advisor/__init__.py`](../zram_advisor/__init__.py)
   and commit.
2. Run `./bless`.  The gate runs in full.
3. Answer `test` to rehearse on TestPyPI, then run `./bless` again and answer
   `publish` -- or go straight to `publish`.

`[tool.bless] branches` names what `publish` pushes.  The trunk in that list must
exist and track origin.  Everything else about the release is one of the stages
above, and the shared half lives in
[`blessd/docs/release-strategy.md`](../../blessd/docs/release-strategy.md).

## Notes on this adoption

* This section is one run of
  [`../../blessd/docs/adopting.md`](../../blessd/docs/adopting.md), which is the
  procedure written for whoever converts the next project.  If the two ever
  disagree, that document is the procedure and this is the record of one run.
* [`bless`](../bless) is emitted, byte for byte, from
  [`../../blessd/bless`](../../blessd/bless) -- SHA-256
  `3ef60e9e806ca58a3d900dd6622bb8be0052210da1ef26f9918bf0a1deb1e3b2` when this
  was written.  It is not edited here: a change is made in `blessd` and
  re-emitted with `python3 ../../blessd/build.py --into .`, which replaces the
  file and prints the new hash.
* The gate replaced nothing here: this project had no `bless` and no tests, so
  no gate policy tests were carried over, and the trimmed-suite rule of the
  procedure did not apply.  The suite is [`tests/test_bless.py`](test_bless.py)
  (the identity this tree derives and the inspector it uploads behind) and
  [`tests/test_main.py`](test_main.py) (the pure calculations and the packaged
  data files).  What the gate itself does -- branch plan, refusals, prompt,
  index check, emitter -- is tested once, in
  [`../../blessd/tests/test_bless.py`](../../blessd/tests/test_bless.py).
* The project had to add five things: one version location
  (`dynamic = ["version"]` plus `__version__` in the package), a
  `-V`/`--version` option that prints `zram-advisor X.Y.Z`, an inspector, the
  `test`/`dev` extras (with `tomli` on Python 3.10, where `tomllib` is not in
  the stdlib), and a branch model for the branch plan -- here
  `branches = ["main"]`.  The metadata moved to the PEP 639 `license`
  expression and `license-files` at the same time, which is why the build
  backend floor is `flit_core>=3.12,<5`.
* The ruff rule set was added with the gate, so the tree was brought to a clean
  `ruff check .` once.  The measured coverage at adoption was 40.35% over 23
  tests; the floor is 38%, a ratchet rather than a target.
* The environment follows the per-project model of the same procedure's
  postscript: `bt penv` built `.venv` around the tree (editable `zram-advisor`
  plus the `dev` extra), and [`runner`](../runner) re-execs into
  `.venv/bin/python`.  `bt status` reports no owner for
  `~/.local/bin/zram-advisor`, so the entry point is free for `bt edit`,
  `bt test` or `bt prod`.
* CI is not wired up yet.  When it is, it must run the same three gate commands
  and the same inspector, never an equivalent.
