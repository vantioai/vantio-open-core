# Quickstart

This note is for a qualified Linux operator on Ubuntu 24.04 LTS x86_64. It installs the `vantio-install` and `vantio-verify` commands from a sealed wheel. A sealed sdist of the same package can be installed the same way when a build backend is already present offline. Installing these commands does not install Optics and does not start Phantom Engine.

`proof_state` stays `NOT_PROVED`. The proof ceiling stays `INTERNAL_CLEAN_HOST_PROOF`. The second-lab gate in `STAGE-B-ARTIFACT-PATH.md` stays closed until a separate authorization. These pages do not raise that ceiling.

The sealer delivers three files: the wheel, `SHA256SUMS`, and these operator notes. The sdist is optional and uses the same checksum file. The source pin of this package stays `0.1.0-stage-a`. The wheel's distribution version is the PEP 440 local version `0.1.0+stage.a`, which is the seal form of that same pin. After install, `vantio_install.__version__` and the JSON field `installer_version` still report `0.1.0-stage-a`.

Check the delivered SHA-256 before you install:

`sha256sum <sealed-wheel>`

Compare the hex digest to the matching line in `SHA256SUMS`. A mismatch stops the install. Leave the file unused.

Create a tool environment and install the wheel with the package index disabled:

`python3 -m venv /var/lib/vantio/installer-venv`

`/var/lib/vantio/installer-venv/bin/python -m pip install --no-index --disable-pip-version-check --no-deps <sealed-wheel>`

That directory is only the tool environment. It is not the node prefix, the stage directory, or the evidence directory.

The wheel installs two console scripts, `vantio-install` and `vantio-verify`, into `/var/lib/vantio/installer-venv/bin`. Put that directory on `PATH` and confirm both commands resolve inside it:

`export PATH="/var/lib/vantio/installer-venv/bin:${PATH}"`

`command -v vantio-install`

`command -v vantio-verify`

`vantio-install --help` and `vantio-verify --help` print usage and do not change the host.

A sealed sdist installs the same two scripts when you pass that file to the same `pip install --no-index --no-deps` command and the build backend is already on the machine. When the backend is absent, install the wheel.

The product bundle is a separate sealed directory that is already on the host. `INSTALL.md` is the next step. The bundle pins stay Optics CLI 0.3.24, Agent SDK npm 0.2.4, and Agent SDK Python 3.1.0. This package does not change those versions. The installer reads the bundle. It does not fetch it.

The following are forbidden on this path:

- Cloning `vantio-open-core`, including a floating `main` checkout, and any private clone of that repository
- A Phantom Box path, or any other company-host path, as the install location or the working directory
- Pulling Phantom Engine from GHCR, including tag 0.1.0
- The source launcher `bin/vantio-install`, which expects this package tree on disk

`artifact_source` stays `sealed_archive`. Preflight check `PF-GHCR-DEFAULT` blocks a GHCR 0.1.0 selection.
