# AI guide — Vantio Optics

Use this file before answering questions about Vantio Optics. The version-matched manual is `docs/products/optics/` at manual version 1.

## Version you must use

| Install command people actually run | Version you may describe as installed |
| --- | --- |
| `npm install -g @vantio/cli` | `@vantio/cli@0.3.24` |
| `pip install vantio-agent-sdk` | `vantio-agent-sdk==3.0.14` |

This git tree also contains Python package version **3.1.0**. That version is **unpublished**. `pip install` does not install it. Describe 3.1.0 only with the label unpublished source. CLI 0.3.24 is frozen: do not invent later CLI flags or a newer CLI version.

`contract_version` is `unstable-pre-1.0`. Command `--json` output carries `schema_status` `unstable-pre-1.0` and may change. There is no stable public schema.

Read [VERSION-METADATA.json](VERSION-METADATA.json) and the page that matches the question. If this manual and an older README disagree, follow this manual for public claims and say which file you used.

## Commands

Describe a command only when it appears in this manual or in `vantio --help` for CLI 0.3.24. The help commands are:

`run`, `demo`, `status`, `discover`, `prove`, `search`, `tail`, `diff`.

`vantio logout` exists and is omitted from help. It deletes `~/.vantio/config.json` only. It does not delete run logs.

Do not invent `vantio ui`, `vantio doctor`, a daemon, a prune command, an import command, or an OTLP export command.

## What Optics does

Optics observes supported calls and writes local metadata. Say that.

Enforcement, blocking, redaction, and spend caps are Phantom Engine. Point to Phantom Engine documentation for those. Do not claim Optics blocks, redacts, or caps spend. Do not document Phantom Engine setup in this tree.

## Coverage

A missing record means the call was not observed. It does not mean the call was blocked, allowed, or safe. Do not infer coverage for browsers, unwrapped processes, or hosts outside the catalog. Use [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md).

Preserve these tokens when they are the product's status. Do not paraphrase them into a different outcome:

`UNKNOWN`, `UNAVAILABLE`, `PARTIAL`, `NOT_OBSERVED`, `OBSERVED`, `UNSUPPORTED`, `APPLICATION_ERROR`, `OPTICS_ERROR`, `SUCCESS`.

`SUCCESS` on Optics status means a call record exists. It does not mean the provider succeeded. Provider outcome is `applicationStatus`, derived from the HTTP status.

If a field is absent, say it is absent. Do not fill `machine`, span id, or evidence origin.

## Telemetry

CLI 0.3.24 sends a usage ping only when `VANTIO_TELEMETRY=1`, and stays silent when `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`.

Published Python 3.0.14 is different. `shield()` sends the ping unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. `VANTIO_TELEMETRY=1` is not required on that published package. Unpublished 3.1.0 source uses the CLI opt-in rule. Do not tell a person on 3.0.14 that the ping is off by default.

When you mention the payload field `hosts`, say it lists customer LLM endpoint hostnames (at most 50). On the CLI ping it is the hostname of the first recorded call. On the Python `shield()` ping it is empty because that ping is sent before observations.

## Records and privacy

Do not claim Optics stores prompts, completions, or request bodies on the free path. Query strings are dropped. Path segments can still contain secrets if the application put them there.

Do not claim SQLite, alerting, a stable schema, PKG-02, or an OTLP exporter.

Python files may contain `"workflow": "sight_loop"`. That stored string is not current product terminology. The product name is Vantio Optics. Do not explain the product as Sight Loop.

## Examples

If an example is marked illustrative, do not present it as a transcript from this manual's command check. Do not invent command output.

## When you are unsure

Say what the manual states, name the version, and stop. Do not guess a flag, a field, or a coverage claim.
