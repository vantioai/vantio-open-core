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

The product bundle is a separate sealed directory that is already on the host. `INSTALL.md` is the next step. The bundle pins stay Optics CLI 0.3.24, Agent SDK npm 0.2.4, and Agent SDK Python 3.1.0. This package does not change those versions. The installer reads the bundle. It does not fetch it. Before plan or apply, place the sealed bytes per `ARTIFACT-PATH.md` and verify `SHA256SUMS`.

The following are forbidden on this path:

- Cloning `vantio-open-core`, including a floating `main` checkout, and any private clone of that repository
- A company-host path as the install location or the working directory
- Pulling Phantom Engine from GHCR, including tag 0.1.0
- The source launcher `bin/vantio-install`, which expects this package tree on disk

`artifact_source` stays `sealed_archive`. Preflight check `PF-GHCR-DEFAULT` blocks a GHCR 0.1.0 selection.
