# WS3 P34 — stranger-host execution packet boundary

Audience: INTERNAL_RESTRICTED

Classification: `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`

Mode: `PREP_ONLY`

Force: WS3 P34

Producer: Cursor cloud agent `bc-22d4d08f-d82d-5241-82ee-1a238b4c3e3f`, model Grok 4.7

Repository: `vantioai/vantio-open-core`

Prepared against main: `5064f32f1cdfcb840dfd100e2ce5c712d046550d`

Writable path: `docs/planning/stranger-host-gate/`

## Revision

Council `bc-9f46789b-e2a8-5d01-a1fe-d43ca6b2830f` returned `STRANGER_HOST_PACKET_NEEDS_REVISION` on tip `3b00ea90ce90a85f63c92c28591233aee62830d1`. Revision agent `bc-5f157656-f625-5e20-8cd6-5dafbb0d9368` corrected the `shield()` wording, the CI `run:` citation, and the pip uninstall citation. Prep classification stays `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`. Execution stays `NOT_AUTHORIZED`. The Founder template stays unfilled.

## What this classification means

The prep packet is complete, and stranger-host execution remains unauthorized. The local verifier prints `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH` when the packet files, hashes, refusal entrypoints, and unfilled authorization template agree.

That line is a prep result. It assigns none of `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`.

## Purpose

This directory holds the checklist, evidence requirements, stop conditions, Founder authorization template, runbook, rollback, and local verifier for a later stranger-host run of the checks already defined in `.github/workflows/ci.yml`.

Stranger-host, in `docs/planning/optics-foundation-a8/05-TEST-AND-EVIDENCE-STRATEGY.md`, means a host that is not the producer’s. The same checks on that host are the evidence a later force would need before anyone could discuss `STRANGER_HOST_PROVED`. This prep force records the procedure and stops before the host run.

## Hard stop

- No stranger-host execution.
- No customer host.
- No credential creation.

`scripts/refuse-stranger-host-execution.mjs` exits 2 with `STRANGER_HOST_EXECUTION_BLOCKED_AWAITING_AUTH` on every invocation. `scripts/refuse-rollback.mjs` exits 2 with `STRANGER_HOST_ROLLBACK_BLOCKED_AWAITING_AUTH`. Filling `authorization/FOUNDER-AUTHORIZATION.template.json` in this packet is the wrong act: the verifier requires `status` `NOT_AUTHORIZED` and unfilled placeholders. A later Founder force copies the template and replaces the refuse script.

## Scope of the later matrix

The later matrix, still unauthorized, is CI parity with `.github/workflows/ci.yml` at the prepared SHA:

| CI job | Role in the later matrix |
| --- | --- |
| `lint-and-test-js` | CLI lint, CLI tests, Node SDK typecheck, Node SDK tests, Node SDK build |
| `test-python` | Python 3.10, 3.11, and 3.12 unittest of `packages/vantio-agent-sdk-py` |
| `release-governance` | Local governance tests. They use stand-ins and do not upload. Production upload modules under `scripts/release/` are outside the matrix. |
| `candidate-artifacts` | `npm pack` and `python3 -m build` into a disposable directory |

Workflows outside that file stay outside the matrix: `.github/workflows/npm-publish.yml`, `.github/workflows/pypi-publish.yml`, `.github/workflows/mcp-registry-publish.yml`, `.github/workflows/enterprise-slsa-provenance.yml`, and `.github/workflows/vantio-prove-example.yml`.

Packages present in the tree and absent from `ci.yml` stay outside the default matrix. That includes `@vantio/optics-mcp`, `@vantio/gate-mcp`, `packages/optics-evidence-contract`, and `packages/optics-record-vocabulary`. `docs/scripts/check-docs-release.mjs` is also outside `ci.yml` at this SHA.

Phantom Engine enrollment, kernel modules, and eBPF are a different repository. They are outside this matrix.

## Product facts this packet uses

Versions recorded in `docs/governance/VERSION-METADATA.json` on the prepared SHA:

| Package | Version in this tree |
| --- | --- |
| `@vantio/cli` | 0.3.24 |
| `@vantio/agent-sdk` | 0.2.4 |
| `vantio-agent-sdk` (Python source) | 3.1.0 |
| `@vantio/optics-mcp` | 0.1.2 |
| `@vantio/gate-mcp` | 0.1.0 |

`docs/products/optics/INSTALLATION.md` records a registry observation on 2026-09-27: npm `@vantio/cli` 0.3.24 and PyPI `vantio-agent-sdk` 3.0.14. This prep did not query npm or PyPI. A later published-install smoke, default off, re-checks those pins before it installs anything.

Python 3.1.0 in this tree and Python 3.0.14 on PyPI are different packages of behavior. Source-tree unittest exercises 3.1.0. A green source run is silent about the published 3.0.14 wheel.

`docs/products/optics/TELEMETRY.md` distinguishes the gates: CLI 0.3.24 and unpublished Python 3.1.0 stay quiet unless `VANTIO_TELEMETRY=1`. Published Python 3.0.14 `shield()` sends unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. The later session sets both overrides and leaves `VANTIO_TELEMETRY` unset.

Phase 4 runs `python -m unittest discover -s tests -t . -v` in `packages/vantio-agent-sdk-py`. That suite calls `shield()`. The call sites include `tests/test_sdk.py`, `tests/test_http_observe.py`, `tests/test_optics_status.py`, `tests/test_socket_timing.py`, and `tests/test_outcome_clarity.py`. `shield()` calls `send_run_telemetry_once` (`vantio/sdk.py`). In this tree `send_run_telemetry_once` returns immediately when `is_telemetry_disabled()` is true (`vantio/_telemetry.py`): `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` forces that return, and an unset `VANTIO_TELEMETRY` does too, because a send requires `VANTIO_TELEMETRY=1`. `tests/test_telemetry.py` clears `VANTIO_TELEMETRY`, `VANTIO_TELEMETRY_DISABLED`, and `DO_NOT_TRACK` in `setUp`. Cases that opt in set `VANTIO_TELEMETRY=1` and point `VANTIO_INGEST_URL` at a local `MockServer` on `127.0.0.1` (`tests/mock_server.py`). Live telemetry stays unauthorized.

CLI tests in `packages/vantio-cli/test/optics-cx.test.js` invoke `strace`. The default later host class is Linux with `strace` already installed. Job `lint-and-test-js` in `.github/workflows/ci.yml` at the prepared SHA also runs `sudo apt-get update && sudo apt-get install -y strace`. `05-RUNBOOK.md` cites that line. `later_commands` omits it. SH-STOP-14 keeps `strace` as a preinstalled host tool. The later matrix installs no operating-system packages.

CLI interceptor tests bind a local mock on `127.0.0.1`. They are part of `pnpm --filter @vantio/cli run test`. They are not live calls to a model provider.

Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` stays closed. This packet does not open it, does not start an implementation force, and does not edit the architecture pack.

## What prep runs

One local command:

```bash
node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs
```

The verifier reads this directory, checks hashes in `PACKET-MANIFEST.json`, checks git paths stay inside this directory, runs the two refuse scripts, and prints the classification. It does not install packages, open a network connection, or create a credential.

## Readiness update

Wave 2 Track 16 keeps this prep packet and records currency main `89f95099d0dce463307eb75d78e7fcf2ef99feb2`. Producer of the update: Cursor cloud agent `bc-ad6e7ae1-4de4-5416-bc9d-a6971c7717f4`, model Grok 4.7. Mode: `READINESS_UPDATE_ONLY`. Classification of the update: `STRANGER_HOST_READINESS_UPDATED_READY_FOR_COUNCIL`. Council status: `PENDING_INDEPENDENT_COUNCIL`.

The update adds placeholder sections for ingress, egress, host-authority, sequential-authority, health, and progressive-enforcement. Each placeholder is `NOT_EXECUTED`. It adds an unfilled named host and operator checklist. Future execution authorization requires that checklist copied and named, plus Founder execution authorization, and replacement of the refuse script by that later force. This update leaves execution `NOT_AUTHORIZED`. `07-READINESS-UPDATE.md` is the record.
