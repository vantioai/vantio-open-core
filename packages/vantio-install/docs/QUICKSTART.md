# Quickstart

This note is for a qualified Linux operator on Ubuntu 24.04 LTS x86_64. It installs the `vantio-install` and `vantio-verify` commands from a sealed wheel. That wheel install is the one to use. A sealed sdist is a fallback: it needs `--no-build-isolation` and hatchling already installed in the same environment. Installing these commands does not install Optics and does not start Phantom Engine.

`proof_state` stays `NOT_PROVED`. The proof ceiling stays `INTERNAL_CLEAN_HOST_PROOF`. The second-lab gate in `STAGE-B-ARTIFACT-PATH.md` stays closed until a separate authorization. These pages do not raise that ceiling.

The sealer delivers the wheel, `SHA256SUMS`, and these operator notes. The sdist is optional and uses the same checksum file. The wheel file name is `vantio_install-0.1.0+stage.a-py3-none-any.whl`. The sdist file name is `vantio_install-0.1.0+stage.a.tar.gz`. Quote those paths. The source pin of this package stays `0.1.0-stage-a`. The wheel's distribution version is the PEP 440 local version `0.1.0+stage.a`, which is the seal form of that same pin. After install, `vantio_install.__version__` and the JSON field `installer_version` still report `0.1.0-stage-a`.

Check the delivered SHA-256 before you install:

`sha256sum <sealed-wheel>`

Compare the hex digest to the matching line in `SHA256SUMS`. A mismatch stops the install. Leave the file unused.

Create a tool environment and install the wheel with the package index disabled:

`python3 -m venv /var/lib/vantio/installer-venv`

`/var/lib/vantio/installer-venv/bin/python -m pip install --no-index --disable-pip-version-check --no-deps <sealed-wheel>`

When `venv` is unavailable, install with a prefix instead:

`python3 -m pip install --prefix /var/lib/vantio/installer-prefix --no-index --disable-pip-version-check --no-deps <sealed-wheel>`

Either directory is only the tool environment. It is not the node prefix, the stage directory, or the evidence directory.

The wheel installs two console scripts, `vantio-install` and `vantio-verify`, into `/var/lib/vantio/installer-venv/bin`. The virtualenv interpreter already sees that environment's site-packages. Put the script directory on `PATH` and confirm both commands resolve there:

`export PATH="/var/lib/vantio/installer-venv/bin:${PATH}"`

A `--prefix /var/lib/vantio/installer-prefix` install on Debian or Ubuntu writes those scripts to `/var/lib/vantio/installer-prefix/local/bin` and the package to `local/lib/python3.X/dist-packages`. The script shebang is `/usr/bin/python3`. `PATH` alone leaves that interpreter without the prefix packages, and `vantio-install` raises `ModuleNotFoundError: No module named 'vantio_install'`. Put the prefix `dist-packages` directory on `PYTHONPATH` so it is on `sys.path`. Replace `X` with the minor version reported by `python3 --version`.

`export PATH="/var/lib/vantio/installer-prefix/local/bin:${PATH}"`

`export PYTHONPATH="/var/lib/vantio/installer-prefix/local/lib/python3.X/dist-packages"`

`command -v vantio-install`

`command -v vantio-verify`

`vantio-install --help` and `vantio-verify --help` print usage and do not change the host.

Use the wheel commands above. A sealed sdist installs the same two scripts only when hatchling is already installed in that virtualenv and pip does not isolate the build:

`/var/lib/vantio/installer-venv/bin/python -m pip install --no-index --disable-pip-version-check --no-deps --no-build-isolation <sealed-sdist>`

`--no-index` without `--no-build-isolation` still builds in an isolated environment, looks up hatchling there, and fails with `No matching distribution found for hatchling`. When hatchling is absent, install the wheel.

The product bundle is a separate sealed directory. `INSTALL.md` is the observe path when that directory is already in place. The bundle pins stay Optics CLI 0.3.24, Agent SDK npm 0.2.4, and Agent SDK Python 3.1.0. This package does not change those versions. The self-serve section below is the license-gated fetch. Before plan or apply, place the sealed bytes per `ARTIFACT-PATH.md` and verify `SHA256SUMS`, or fetch them with that command.

The following are forbidden on this path:

- Cloning `vantio-open-core`, including a floating `main` checkout, and any private clone of that repository
- A company-host path as the install location or the working directory
- Pulling Phantom Engine from GHCR, including tag 0.1.0
- The source launcher `bin/vantio-install`, which expects this package tree on disk

`artifact_source` stays `sealed_archive`. Preflight check `PF-GHCR-DEFAULT` blocks a GHCR 0.1.0 selection.

## Self-serve on Ubuntu 24.04 LTS

This path is for one Linux server running Ubuntu 24.04 LTS on x86_64. AWS and GCP are the launch targets. `proof_state` stays `NOT_PROVED`. This page does not claim the `self-service-enforce` lab has passed on the canonical seal.

Set `VANTIO_INSTALL_ALLOW_LIVE=1` for every command that changes the Linux server, and pass `--i-accept-live-mutations` on that same command. One of the two is not enough.

1. Fetch the sealed bundle. The default endpoint is `https://vantio.ai/api/pe/download`. The command follows one redirect, and only to `objects.githubusercontent.com` or `release-assets.githubusercontent.com` over https. It stores the license at `/etc/vantio/license` with mode 0600 and does not print the token.

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install fetch --license @license.txt --bundle-dir /var/lib/vantio/bundle --i-accept-live-mutations --json`

2. Plan, then apply. Apply without `--enforce-enrolled` stays observe-only. Observe-only remains the default and remains healthy when the checks pass.

3. If plan reports `PF-LSM`, the running LSM list does not include `bpf` as its own token. Run host-prep, then reboot the Linux server yourself. The installer does not reboot. When `bpf` is already listed, host-prep records `NO_CHANGE_NEEDED` and does not edit the boot entry. That is the usual case on GCP.

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install host-prep --write-lsm --i-accept-reboot --i-accept-live-mutations --transaction-id <id> --json`

4. After the reboot, start enforcement. The command refuses without a valid license, a signed policy that allows enforcement, and `bpf` in the post-boot LSM list. `protection_state` is `PROTECTED` only when the loader output contains `SCOPED (drop enrolled)` and the program list contains `cgroup_skb_egress_enforce`. Otherwise the state is `DEGRADED` and the JSON names the reason.

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install apply --enforce-enrolled --yes --i-accept-live-mutations --transaction-id <id> --policy-file <signed-policy> --json`

5. Enroll the workload unit. The drop-in sets `Slice=vantio-enrolled.slice`. Names `vantio-*`, `docker`, `containerd`, `sshd`, `ssh`, and `systemd-*` are refused.

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install enroll --unit lab-workload --i-accept-live-mutations --transaction-id <id> --json`

6. Read `vantio-install status`. Then uninstall and run `verify-removal`. `VERIFIED_REMOVED` requires the grub drop-in, the license file, and the enroll drop-ins to be gone. Uninstall and rollback remove those files. Rollback runs `update-grub` and does not reboot.

`--exec-preset web-server` is accepted only with `--enforce-enrolled`, and only when `PHANTOM-ARTIFACT-MANIFEST.json` advertises `exec_deny`. Otherwise the reason is `EXEC_DENY_NOT_IN_SEAL`.

Limits:

- Ubuntu 24.04 LTS x86_64 only.
- uid 0 and processes that are not in `vantio-enrolled.slice` stay observe-only.
- Tamper resistance is not claimed.

Fetch exit codes: `0` when the bundle is verified, `2` when the download is blocked, `41` when the license was not accepted, `43` when the license is canceled or expired, `44` when the bundle is no longer available, and `45` when there have been too many download attempts.
