# Packaging recipe

This recipe seals a customer wheel and sdist on a workstation that already has this package tree. It is the sealer's procedure. A customer operator follows `QUICKSTART.md` and does not run this recipe. Cloning `vantio-open-core` to obtain the installer is forbidden for that operator, including a floating `main` checkout and a private clone.

The source pin in `pyproject.toml`, `vantio_install/__init__.py`, and `INSTALLER_VERSION` stays `0.1.0-stage-a`. Hatchling rejects that string as a project version because it is not PEP 440. `python -m build` on this tree fails for that reason. The seal script copies the package to a temporary directory and sets `project.version` on the copy only, to `0.1.0+stage.a`. The copy is discarded. The source pin is read again after the build and the script stops if it changed.

Optics CLI 0.3.24, Agent SDK npm 0.2.4, and Agent SDK Python 3.1.0 are pins in `vantio_install/constants.py`. This recipe does not rewrite them.

`[project.scripts]` is the customer bin contract:

- `vantio-install` calls `vantio_install.cli:main`
- `vantio-verify` calls `vantio_install.verifier:main`

`bin/vantio-install` is a source launcher. The sdist include list omits `bin/`. The sealed wheel's console scripts are the customer commands.

From `packages/vantio-install`, with the `build` module available for the sealer:

`python3 packaging/seal_customer_artifact.py --outdir <sealed-dir>`

The script runs `python -m build --wheel --sdist` in the temporary copy and writes the wheel, the sdist, and `SHA256SUMS` into `<sealed-dir>`. The wheel name is `vantio_install-0.1.0+stage.a-py3-none-any.whl`. The sdist name is `vantio_install-0.1.0+stage.a.tar.gz`. The checksum file is `sha256sum` format. The script does not upload those files, does not contact a package registry, and does not pull Phantom Engine.

Deliver the wheel, `SHA256SUMS`, and the operator notes. Deliver the sdist when you want the sealed source archive beside the wheel. The customer compares the hash and installs the wheel with `--no-index`, as `QUICKSTART.md` describes.

`proof_state` stays `NOT_PROVED`. The proof ceiling stays `INTERNAL_CLEAN_HOST_PROOF`.
