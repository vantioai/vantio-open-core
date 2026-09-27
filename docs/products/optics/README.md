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

Command blocks in the other pages are marked **illustrative** when they are the documented shape of a command, including `npm install -g` and calls to customer LLM providers. This pass did not send a prompt to a customer LLM endpoint.

The following were executed locally on 2026-09-27 against `node packages/vantio-cli/bin/vantio.js` (package version 0.3.24) and, where noted, the PyPI wheel `vantio-agent-sdk==3.0.14` installed with `pip install --target` (not a global install):

| Check | Result |
| --- | --- |
| `vantio --version` | `0.3.24` |
| `vantio --help` | No `login` command |
| `vantio demo`, `vantio demo --json` | Stub HTTP 200, `schema_status` `unstable-pre-1.0`, `content` null, duration 0 |
| `vantio status` with telemetry vars unset | Posture `off` |
| `vantio status` with `VANTIO_TELEMETRY_DISABLED=1` | Posture `disabled`. Provider SDK rows `Unsupported` in an empty directory |
| `vantio prove --list`, `search`, `tail -n 5`, `tail -n 0`, `diff` | Read the demo files |
| `vantio tail --json --follow` | Exit 1 |
| `vantio run --json node -e 'process.exit(0)'` | Stdout `opticsStatus` `SUCCESS`, `applicationStatus` `NOT_OBSERVED`, `schema_status` `unstable-pre-1.0` |
| `vantio run node` with no in-scope call | Wrote a run file with `calls` `[]`, `schema_version` 2, no `schema_status` |
| `vantio run node` POST to `127.0.0.1` with `VANTIO_EXTRA_LLM_HOSTS` | Recorded `action` `OBSERVED`, path `/v1/chat/completions`, HTTP 201, provider `local`. The prompt, the query token, and the response body were absent from the file |
| `vantio run python3` without the SDK | Stderr warning. The process still printed and exited |
| `vantio discover --local` | Listed hosts from `~/.vantio/runs` only |
| PyPI `vantio-agent-sdk==3.0.14` | `vantio.__version__` is `3.0.14`. With telemetry variables unset, `is_telemetry_disabled()` is false (the ping is allowed). `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` each make it true. The check did not POST |
| Unpublished source import | `vantio.__version__` is `3.1.0`. With telemetry variables unset, `is_telemetry_disabled()` is true |
| `vantio run python3` with 3.0.14 and `VANTIO_HOME` set, urllib POST that returns HTTP 500 | Writer directory received the file. CLI `discover` did not. File has `workflow` `sight_loop`, no `schema_status`, no `pid`, `provider` `other`, `status` 500, `ok` false, `error` `network_error`. Prompt, query, and response body were absent |

`vantio prove --format=md` was also run on the local Node file. It did not contain the prompt canary.

## PDF

No PDF is produced with this manual. This repository has no reviewed, deterministic documentation renderer for Optics, and this change does not add one. A later export can concatenate the Markdown files in the order listed under [Files](#files) and render that text with a tool the docs council has already accepted. The renderer must not add claims.

## Public-safety notes for review

- Optics records supported calls. A path with no record was not observed. It was not blocked by Optics.
- The published Python 3.0.14 `shield()` usage ping is sent unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. CLI 0.3.24 and unpublished Python 3.1.0 source stay off unless `VANTIO_TELEMETRY=1`. See [TELEMETRY.md](TELEMETRY.md).
- Any sentence about the telemetry field `hosts` means customer LLM endpoint hostnames. See [TELEMETRY.md](TELEMETRY.md).
- Published Python run files still contain the string `sight_loop` in `workflow`. That string is leftover storage. It is not the product name. The product name is Vantio Optics.
- SQLite, a `vantio ui` interface, alerting, an OTLP exporter, a stable schema, and PKG-02 are absent. See [KNOWN-LIMITATIONS.md](KNOWN-LIMITATIONS.md).
- This tree is ready for a separate docs council. Classification token: `OPTICS_PUBLIC_DOCS_READY_FOR_COUNCIL`.
