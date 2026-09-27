# Demo script

Audience: INTERNAL_RESTRICTED

Follow `04-OPERATOR-RUNBOOK.md` for the home directory and environment. Say the lines. Run only the commands in each beat. Leave the simulation banner visible from B07 through B10 and again during B15.

Banner text, kept on screen:

`SIMULATION — SIMULATED_DEMO — vantio demo — no network — not a customer call`

Binary:

`node packages/vantio-cli/bin/vantio.js`

Working directory: repository root. Version required before B04: `0.3.24`.

## B01 — Room contract

Say: This is a deterministic Optics walkthrough on CLI 0.3.24. One command writes an in-process stub. That stub is simulated. Spoken sections describe the product boundary and do not create events. Nothing in this room is a customer deployment.

## B02 — Lineup

Say: Vantio Optics is free, local-first observability for AI agent egress. It is the free Observe tier. Phantom Engine is Enforce plus Control on enrolled Linux hosts at $799/node/mo. Enterprise is governance on top of that protection and is talk to sales. Free Optics needs no account and no API key. Gate is not a current standalone public SKU.

Source to have open: `docs/PRODUCT_LINEUP.md` and `docs/governance/canonical/product-boundary.md`.

## B03 — Version

Run `--version`.

Say: The binary is 0.3.24. That package is the frozen CLI this script uses.

## B04 — Empty status

Run `status`.

Say: Registry latest says not checked. This command did not contact a registry. Telemetry says disabled. Run logs say Not observed because this home has no run file yet. Provider SDK lines say Unsupported when those packages do not resolve from this directory. Unsupported here means the package did not resolve. It does not mean traffic is blocked.

## B05 — Mechanism

Say: `vantio run node agent.js` injects the Node interceptor with `NODE_OPTIONS --require` for `node`, `npx`, `tsx`, and `ts-node`. That is the observe path in this repository. This beat does not start an agent and does not contact a model.

## B06 — Coverage

Say: A call that never hits the interceptor is not recorded. Browser paths stay outside this wrap. Without vantio-agent-sdk, prefixing `vantio run python` does not intercept. An unobserved path is not a blocked path. This script does not install the Python package and does not present source version 3.1.0 as the PyPI package. The public manual in this tree records PyPI 3.0.14 and source 3.1.0 as unpublished at its 2026-09-27 check. This force did not query PyPI.

## B07 — Simulated demo

Put the banner up. Then run `demo` once.

Say: The line "Demo — in-process stub. No network." is the product telling you this is a stub. HTTP status 200, Optics status Successful, application outcome Successful, duration 0. There is no prompt and no completion. The trace id changes every run. Copy the trace id from this output for the next beats.

## B08 — Run file

Open `~/.vantio/runs/<trace>.json` inside the demo home.

Say: The file marker is `vantio_run_log` 1, plane `optics`, schema version 2, one call, hostname `optics-demo.invalid`, action `OBSERVED`, bytes 0, HTTP status 200. The file has no `evidence_origin`, no `producer`, and no `pid`. Action `OBSERVED` means the stub stored a call record. It does not mean a customer agent called a provider. The hostname is the simulation marker the file actually carries. The missing origin field is a current limitation. We do not relabel this file as local customer observation.

## B09 — Proof

Keep the banner up. Run `prove --list`, then `prove --run=<trace> --format=md`.

Say: The Markdown names host `optics-demo.invalid`, duration 0 ms, process id as an em dash, total bytes as an em dash, Optics status Successful, application outcome Successful. The proof text does not contain the word simulation. The banner is the label. This Markdown is not a customer report.

## B10 — Recorded fields

Say: The record shows destination host, method, path, HTTP status, byte count, and time. Byte count is 0 because the stub sent nothing. Prompts and completions are absent from the file. `content` on `demo --json` is null. That JSON mode is documented in the expected outputs. The spoken script does not run a second demo.

## B11 — Two statuses

Say: Optics status Successful means a record exists. Application outcome Successful means the stored HTTP status is in 200–399. Neither token is an allow decision. Application error is not an Optics block. Not observed is not proof that a call was prevented.

## B12 — Free Optics boundary

Say: This demo did not block, redact, or apply a spend cap. There is no OTLP exporter. JSON command output uses schema_status `unstable-pre-1.0`. The store in this CLI is one JSON file per trace id. A database, a local UI, a daemon, and alerting are absent from the command that just ran.

## B13 — Phantom Engine boundary

Say: Phantom Engine is a separate product and a separate repository. This laptop did not enroll a host and did not load a kernel program. Enforce and Control are not shown as events. Rogue Reconciliation is not shown as an event. If a file in this home contained a block or redact action, we would stop, because that file would be outside this script.

## B14 — Claims

Read the `DO_NOT_SAY` rows in `08-CLAIM-LEDGER.json` by id and statement.

Say: Rows marked shown-as-simulation were the stub you just saw. Rows marked narrated were speech from a doc. Rows marked not demonstrated were not executed. No row is customer validation.

## B15 — Unlabeled injection

Follow `07-FAILURE-INJECTION-OUTLINE.md` injection F1 only.

Say: This planted file has no simulation label and its host is not `optics-demo.invalid`. The demo stops on it. We do not prove it and we do not add it to a total. Discover on the real demo file already lists `optics-demo.invalid` as observed locally. That sentence in the CLI is why the banner has to stay up. The CLI does not remove demo files from that count.

## B16 — No narrated block

Say: I will not describe a block that this room did not produce. Free Optics records `OBSERVED` on this stub. The SDK type list includes enforcement action tokens for a Phantom Engine or Enterprise policy path. Those tokens are not the outcome of the command we ran.

## B17 — Reset

Follow `05-RESET-OUTLINE.md` while the room can see the demo home path.

Say: The demo home is a temporary directory. Deleting it removes the stub and the planted defect. The operator's own home directory is not the demo home.

## B18 — Close

Read limitation ids `L-DEMO-FILE-UNLABELED`, `L-PROVE-OMITS-LABEL`, `L-DISCOVER-COUNTS-DEMO`, `L-NOT-DETERMINISTIC-IDS`, `L-PE-NOT-RUN`, and `L-FOUNDER-BEATS-ABSENT` from `09-LIMITATION-LEDGER.json`.

Say: This session is a design script checked against CLI 0.3.24 on a design host. It is not a customer validation and it is not a production-cluster proof.
