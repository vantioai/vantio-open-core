# Vantio Optics public manual

Manual version 1. Audience: public. Contract: `unstable-pre-1.0`.

This folder is the public manual for **Vantio Optics**: free, local-first observability for supported AI-agent traffic. Optics records destination, process, size, and timing metadata. Prompts and completions are absent from Optics records.

Enforcement is Phantom Engine. This manual does not document Phantom Engine installation, policy, or host protection.

## Version this manual is matched to

Checked against the public registries on 2026-09-27, and against source commit `14249ba84ff1f3d5aa8ad7a7366172f29235c76e`.

| Package | What a fresh install returns | What this source tree contains |
| --- | --- | --- |
| `@vantio/cli` (npm) | **0.3.24** | **0.3.24**, frozen. The CLI in this commit is that published package. |
| `vantio-agent-sdk` (PyPI) | **3.0.14** | **3.1.0**, unpublished. `pip install vantio-agent-sdk` does not install 3.1.0. |
| `@vantio/agent-sdk` (npm) | **0.2.4** | **0.2.4**. This package does not write `~/.vantio/runs`. |
| `@vantio/optics-mcp` (npm) | **0.1.2** | **0.1.2**. Read-only local log reader. |

Status of this manual: **draft-honest**. CLI behavior below is the frozen 0.3.24 CLI. Python behavior below is the published 3.0.14 package unless a sentence is explicitly labeled **unpublished 3.1.0 source**.

Machine-readable copy: [VERSION-METADATA.json](VERSION-METADATA.json).

## How to read this set

| Reader | Start here |
| --- | --- |
| First-time developer | [QUICKSTART.md](QUICKSTART.md), then [NODE-GUIDE.md](NODE-GUIDE.md) or [PYTHON-GUIDE.md](PYTHON-GUIDE.md) |
| Install and uninstall | [INSTALLATION.md](INSTALLATION.md), [UPGRADE-ROLLBACK-UNINSTALL.md](UPGRADE-ROLLBACK-UNINSTALL.md) |
| Security reviewer | [PRIVACY-AND-SECURITY.md](PRIVACY-AND-SECURITY.md), [TELEMETRY.md](TELEMETRY.md), [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md) |
| Support | [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [STATUS-AND-OUTCOMES.md](STATUS-AND-OUTCOMES.md) |
| Evaluator | [USER-MANUAL.md](USER-MANUAL.md), [KNOWN-LIMITATIONS.md](KNOWN-LIMITATIONS.md) |
| Upgrade from Python v2 or from 3.0.x | [UPGRADE-ROLLBACK-UNINSTALL.md](UPGRADE-ROLLBACK-UNINSTALL.md), [PYTHON-GUIDE.md](PYTHON-GUIDE.md) |
| AI assistant | [AI-GUIDE.md](AI-GUIDE.md) and [llms.txt](llms.txt) |

Full narrative: [USER-MANUAL.md](USER-MANUAL.md).

## Files

| File | Role |
| --- | --- |
| [USER-MANUAL.md](USER-MANUAL.md) | Product manual for every audience |
| [QUICKSTART.md](QUICKSTART.md) | Shortest path to a local record |
| [INSTALLATION.md](INSTALLATION.md) | Packages, versions, runtimes |
| [NODE-GUIDE.md](NODE-GUIDE.md) | `vantio run` for Node |
| [PYTHON-GUIDE.md](PYTHON-GUIDE.md) | Published 3.0.14 and unpublished 3.1.0 |
| [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md) | What can produce a record |
| [RECORD-REFERENCE.md](RECORD-REFERENCE.md) | On-disk files, fields, read and write |
| [STATUS-AND-OUTCOMES.md](STATUS-AND-OUTCOMES.md) | Status tokens and what they mean |
| [PRIVACY-AND-SECURITY.md](PRIVACY-AND-SECURITY.md) | Metadata boundary, files, permissions |
| [TELEMETRY.md](TELEMETRY.md) | Optional usage ping, including `hosts` |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Empty logs, corrupt files, missed calls |
| [UPGRADE-ROLLBACK-UNINSTALL.md](UPGRADE-ROLLBACK-UNINSTALL.md) | v2, mixed versions, removal |
| [KNOWN-LIMITATIONS.md](KNOWN-LIMITATIONS.md) | Absent features and current gaps |
| [AI-GUIDE.md](AI-GUIDE.md) | Rules for assistants |
| [CHANGELOG-GUIDE.md](CHANGELOG-GUIDE.md) | How to read package history |
| [VERSION-METADATA.json](VERSION-METADATA.json) | Machine-readable versions |
| [llms.txt](llms.txt) | Short index for assistants |
| [llms-full.txt](llms-full.txt) | Full manual text for assistants |

## Founder topics covered

| Topic | Where |
| --- | --- |
| 1 Node record path and shape | NODE-GUIDE, RECORD-REFERENCE |
| 2 Python record path and shape | PYTHON-GUIDE, RECORD-REFERENCE |
| 3 Run-log locations | RECORD-REFERENCE, TROUBLESHOOTING |
| 4 Naming | RECORD-REFERENCE |
| 5 Write | RECORD-REFERENCE |
| 6 Read | RECORD-REFERENCE, USER-MANUAL |
| 7 Tail | USER-MANUAL, NODE-GUIDE |
| 8 Search | USER-MANUAL, NODE-GUIDE |
| 9 Diff | USER-MANUAL, NODE-GUIDE |
| 10 Proof | USER-MANUAL, RECORD-REFERENCE |
| 11 Locking | RECORD-REFERENCE, KNOWN-LIMITATIONS |
| 12 Retention | UPGRADE-ROLLBACK-UNINSTALL, KNOWN-LIMITATIONS |
| 13 Cleanup | UPGRADE-ROLLBACK-UNINSTALL |
| 14 Permissions | PRIVACY-AND-SECURITY |
| 15 JSON schema markers | RECORD-REFERENCE, STATUS-AND-OUTCOMES |
| 16 Run, trace, process, provider, and status fields | RECORD-REFERENCE, STATUS-AND-OUTCOMES |
| 17 Privacy filters | PRIVACY-AND-SECURITY |
| 18 Provider detection | SUPPORTED-PATHS, NODE-GUIDE, PYTHON-GUIDE |
| 19 URL and destination normalization | RECORD-REFERENCE, PRIVACY-AND-SECURITY |
| 20 Demo and fixture | QUICKSTART, KNOWN-LIMITATIONS |
| 21 Import and export | USER-MANUAL, KNOWN-LIMITATIONS |
| 22 Version skew | UPGRADE-ROLLBACK-UNINSTALL, PYTHON-GUIDE |
| 23 Corrupt records, disk full, and write failure | TROUBLESHOOTING |
| 24 Process exit, interruption, clock, and duration | TROUBLESHOOTING, KNOWN-LIMITATIONS |
| 25 Product telemetry and test coverage | TELEMETRY, README example status |

## Examples

Command blocks are either **tested** in this documentation pass or **illustrative**.

The first draft marks command blocks **illustrative** when they are taken from CLI help text and source and have not yet been executed for this manual. A later revision of this same manual records which commands were executed locally. Live calls to customer LLM providers stay illustrative: this pass does not send prompts to those providers.

## PDF

No PDF is produced with this manual. This repository has no reviewed, deterministic documentation renderer for Optics, and this change does not add one. A later export can concatenate the Markdown files in the order listed under [Files](#files) and render that text with a tool the docs council has already accepted. The renderer must not add claims.

## Public-safety notes for review

- Optics records supported calls. A path with no record was not observed. It was not blocked by Optics.
- The published Python 3.0.14 `shield()` usage ping is sent unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. CLI 0.3.24 and unpublished Python 3.1.0 source stay off unless `VANTIO_TELEMETRY=1`. See [TELEMETRY.md](TELEMETRY.md).
- Any sentence about the telemetry field `hosts` means customer LLM endpoint hostnames. See [TELEMETRY.md](TELEMETRY.md).
- Published Python run files still contain the string `sight_loop` in `workflow`. That string is leftover storage. It is not the product name. The product name is Vantio Optics.
- SQLite, a `vantio ui` interface, alerting, an OTLP exporter, a stable schema, and PKG-02 are absent. See [KNOWN-LIMITATIONS.md](KNOWN-LIMITATIONS.md).
- This tree is ready for a separate docs council. Classification token: `OPTICS_PUBLIC_DOCS_READY_FOR_COUNCIL`.
