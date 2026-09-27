# Changelog guide

This manual is version 1. It is a docs set. It does not bump `@vantio/cli`, `vantio-agent-sdk`, or any other package.

## Which history to read

| You installed | Read |
| --- | --- |
| `@vantio/cli@0.3.24` | The CLI is frozen at 0.3.24. Behavior in this manual's Node pages matches that package. Later customer-wording ideas are backlog only and are not in 0.3.24. |
| `vantio-agent-sdk==3.0.14` | [PYTHON-GUIDE.md](PYTHON-GUIDE.md) sections marked published. The package changelog inside the git tree also has 3.0.15 and 3.1.0 headings. Those headings describe commits that were not the PyPI release on 2026-09-27. |
| A checkout of this repository | `pyproject.toml` says 3.1.0. That string is source. It is not a release you can pip install from PyPI until it is published. |

Package changelogs live next to the packages (`packages/vantio-agent-sdk-py/CHANGELOG.md` and the CLI README). When a changelog line and the source of the published tag disagree, the published tag wins for "what did 3.0.14 do?" The 3.0.14 tag in this repository is commit `6f76dd84f52a1c3d02c6cef6c23be41aa3c4d35c`.

## How to read the Python changelog without over-claiming

`3.0.14` is a packaging-metadata release. SDK behavior relative to 3.0.13 is unchanged. The telemetry gate in that tag sends from `shield()` unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`.

`3.0.15` in git is a documentation and gate correction that makes Python telemetry opt-in. Its changelog text says the payload schema is unchanged and also says telemetry stays off unless `VANTIO_TELEMETRY=1`. The gate change is real in that commit. The release was not what PyPI served. Do not tell operators that 3.0.15 is installed.

`3.1.0` in git records HTTP outcome fields, `ok` aligned to status, socket timing, and the opt-in telemetry gate. It is unpublished. CLI 0.3.24 was not reopened to match its customer sentences.

## CLI history that still affects support

`0.3.24` is the current public CLI. It is free, local, and account-free. `vantio login` is not part of the help surface. `vantio logout` only deletes a leftover `config.json`.

Command `--json` output includes `schema_status` `unstable-pre-1.0`. That line means the JSON may change. It does not mean the Node run file contains `schema_status`. The Node run file does not.

## Manual changes

| Manual version | Meaning |
| --- | --- |
| 1 | First public manual set under `docs/products/optics/`, matched to CLI 0.3.24 and PyPI Python 3.0.14, with unpublished 3.1.0 called out. |

When a later manual version is cut, it should name the registry versions it was checked against and the source commit. Until PyPI serves 3.1.0, manuals must keep the split.

## Words that changed

The product name in this manual is Vantio Optics. Older package summaries contain the phrase Sight Loop. Published Python run files still store `workflow` `sight_loop`. Support should recognize the string and should not use it as the name of the product.

Gate is an internal name for enforcement functions inside Phantom Engine. It is not a current standalone public SKU. This manual does not document it as something to install.
