# Independent council — vantio-open-core PR #131

Audience: INTERNAL_RESTRICTED

| Item | Value |
| --- | --- |
| Subject | https://github.com/vantioai/vantio-open-core/pull/131 |
| Branch | `cursor/class-b-installer-docs-459a` |
| Tip | `e3eefd226102ba9e8e349179c89c5b37e7f06e4b` |
| Base | `main` @ `c4a543e269a0b6a710ac43925e8badff5a663aa4` |
| Gaps | GAP-CB-DEP-004, GAP-CB-DEP-008, GAP-CB-DEP-011 |
| Reviewed at (UTC) | 2026-09-29 |
| Reviewer | Independent cloud agent (Grok 4.7) |
| Scope | Read the diff and the installer the docs describe. No installer code was added. No merge. No package publish. |

## Verdict

VERDICT: NEEDS_REVISION

MERGE: BLOCKED

Source-only squash-merge stays blocked until the two QUICKSTART corrections below are on the PR tip. The other five checks passed on `e3eefd2`.

## Blocking fixes

1. **Sealed sdist command in `packages/vantio-install/docs/QUICKSTART.md`.** The page says a sealed sdist installs with the same `pip install --no-index --disable-pip-version-check --no-deps` command once a build backend is already on the machine. That command failed here with hatchling already installed in the target virtualenv. Pip still builds in an isolated environment, `--no-index` leaves that environment with no hatchling, and the error is `No matching distribution found for hatchling`. The command that installed the sdist is the same command plus `--no-build-isolation`. Change the opening sentence that says the sdist is installed "the same way", and change the later sdist paragraph, to that flag. Assert the corrected command from `tests/test_seal_recipe.py` so the false sentence cannot return.

2. **`--prefix` fallback in the same file.** After `python3 -m pip install --prefix /var/lib/vantio/installer-prefix --no-index --disable-pip-version-check --no-deps <sealed-wheel>`, the page sets `PATH` to `.../local/bin` and runs `vantio-install --help`. On this Ubuntu host that sequence raised `ModuleNotFoundError: No module named 'vantio_install'`. The console script shebang is `/usr/bin/python3`, and `local/lib/python3.12/dist-packages` is not on that interpreter's `sys.path`. The fallback has to put `local/lib/python3.X/dist-packages` on `sys.path` before those commands. Assert that instruction from `tests/test_seal_recipe.py`.

The virtualenv wheel command is the one that worked. Leave it as written:

`python3 -m venv /var/lib/vantio/installer-venv`

`/var/lib/vantio/installer-venv/bin/python -m pip install --no-index --disable-pip-version-check --no-deps <sealed-wheel>`

## Checks

### 1. GAP-CB-DEP-004 — sealed wheel, sdist, SHA256SUMS, no private clone

Partial. The wheel path and the checksum file are real. The sdist sentence and the prefix fallback are not.

`python3 packaging/seal_customer_artifact.py --outdir /tmp/sealed-vantio` from the tip wrote:

- `vantio_install-0.1.0+stage.a-py3-none-any.whl`
- `vantio_install-0.1.0+stage.a.tar.gz`
- `SHA256SUMS` in `sha256sum` form (two spaces). `sha256sum -c SHA256SUMS` matched both files.

The source tree after the build still had `version = "0.1.0-stage-a"`. The wheel metadata version is `0.1.0+stage.a`. Installed `vantio_install.__version__` and `INSTALLER_VERSION` stayed `0.1.0-stage-a`.

A fresh virtualenv, `pip install --no-index --no-deps` of that wheel, and `PATH` pointing at the venv `bin` resolved `vantio-install` and `vantio-verify`. `vantio-install --help` printed usage and exited 0. That path does not clone `vantio-open-core`. QUICKSTART forbids a floating `main` checkout and a private clone.

The sdist archive omits `bin/` and includes the package, docs, config, and `packaging/seal_customer_artifact.py`. The documented sdist install failed as described above. Adding `--no-build-isolation` installed it, and the installed pins stayed `0.1.0-stage-a`, `0.3.24`, `0.2.4`, and `3.1.0`.

### 2. GAP-CB-DEP-008 — `privilege_mode`, raw docker forbidden

Pass. `PREFLIGHT.md`, `INSTALL.md`, and `LIMITATIONS.md` match the live probe and the live grant.

`probe_live` sets `privilege_mode` to `docker_group` when `/var/run/docker.sock` is writable, `sudo` when it is not and `sudo` is on `PATH`, and `UNKNOWN` otherwise. It does not store the string `root`. `authorize_live` accepts effective uid 0, `sudo` with `sudo_available`, or `docker_group` with `principal_can_talk_to_docker`. Otherwise it returns `FAILED_SAFE` and `Live mutations need root or the documented sudo or docker privilege.`

`PF-DOCKER-PERM` is the preflight check id. A live `UNKNOWN` that cannot write the socket is `BLOCKED`, the plan stays off `PLANNED`, and the exit is 2.

The allowlisted executables in `live_executor.py` are `mkdir`, `npm`, `python3`, `docker`, `tc`, and `apparmor_parser`. `sudo` and `su` are refused as the executable. Dispatch refuses an argv list that differs from the catalog entry. The operator pages forbid raw `docker` and raw `sudo docker`, and they say the installer does not put `sudo` in front of `docker`.

### 3. GAP-CB-DEP-011 — `--fixture-host` and ungated apply forbidden on the customer path

Pass for the operator contract this PR writes.

`INSTALL.md` no longer tells the operator to run `apply --yes` "for a fixture or rehearsal". Customer `apply`, `rollback`, and `uninstall` are the dual-gated commands: `VANTIO_INSTALL_ALLOW_LIVE=1` and `--i-accept-live-mutations`, plus `--plan` and `--plan-sha256`. README, ROLLBACK, UNINSTALL, and LIMITATIONS say `--fixture-host` is forbidden for customer operators. An apply that omits either live gate is refused by `authorize_live` before a host change when `--fixture-host` is absent.

The installed console script still accepts `--fixture-host`. That path sets the live grant to none and uses the fixture mutator. The operator pages forbid the flag. This source-only PR does not need a CLI change to close the written customer path. See the note below.

### 4. Frozen Optics versions

Pass. `vantio_install/constants.py` is not in the diff. The sealed wheel still has Optics CLI `0.3.24`, Agent SDK npm `0.2.4`, and Agent SDK Python `3.1.0`. The seal script rewrites `project.version` only on a temporary copy, then checks the source pin and those three strings again.

### 5. Claim ceiling

Pass. The new pages keep `proof_state` at `NOT_PROVED` and the ceiling at `INTERNAL_CLEAN_HOST_PROOF`. They do not claim Class B, a registry publish, or a product READY state. The seal script does not upload and does not contact a package registry.

### 6. IAM and credentials

Pass. The diff adds no `Resource:*` IAM statement and no AWS credential material. A scan of the sealed wheel and sdist found no `Resource:*`, `AKIA…`, or `aws_secret_access_key` text.

### 7. Tests and the seal recipe

Pass, with the doc-test gap called out in the blocking fixes. `python3 -m unittest discover -s tests` at the tip ran 124 tests and passed, including `tests.test_seal_recipe`. The recipe builds the documented filenames and leaves the source pin in place. The unit test checks the version rewrite and greps the docs. It does not run `python -m build` or the pip commands, which is why the two false procedures stayed green.

## Notes that do not block

- SHA256SUMS is an operator comparison. `pip install` does not read that file. QUICKSTART already tells the operator to compare first and leave a mismatch unused.
- `PF-DOCKER-PERM` also passes when the socket is writable and `privilege_mode` is `UNKNOWN`. `probe_live` does not emit that pair. The customer description of the live probe is the one that matches the code.
- `seal()` checksums every file already in `--outdir` except `SHA256SUMS`. A fresh directory matches the documented names.
- `--fixture-host` remains on `vantio-install apply --help` after the wheel install. Customer pages forbid it. A later change that rejects the flag in the customer entrypoint is outside this docs diff.
