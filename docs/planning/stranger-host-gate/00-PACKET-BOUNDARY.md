# WS3 P34 — stranger-host execution packet boundary

Audience: INTERNAL_RESTRICTED

Classification: `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`

Mode: `PREP_ONLY`

Force: WS3 P34

Producer: Cursor cloud agent `bc-22d4d08f-d82d-5241-82ee-1a238b4c3e3f`, model Grok 4.7

Repository: `vantioai/vantio-open-core`

Prepared against main: `5064f32f1cdfcb840dfd100e2ce5c712d046550d`

Writable path: `docs/planning/stranger-host-gate/`

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

`docs/products/optics/TELEMETRY.md` distinguishes the gates: CLI 0.3.24 and unpublished Python 3.1.0 stay quiet unless `VANTIO_TELEMETRY=1`. Published Python 3.0.14 `shield()` sends unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. The later session sets both overrides. The default matrix does not call `shield()`.

CLI tests in `packages/vantio-cli/test/optics-cx.test.js` invoke `strace`. The default later host class is Linux with `strace` already installed. The matrix contains no operating-system package install.

CLI interceptor tests bind a local mock on `127.0.0.1`. They are part of `pnpm --filter @vantio/cli run test`. They are not live calls to a model provider.

Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` stays closed. This packet does not open it, does not start an implementation force, and does not edit the architecture pack.

## What prep runs

One local command:

```bash
node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs
```

The verifier reads this directory, checks hashes in `PACKET-MANIFEST.json`, checks git paths stay inside this directory, runs the two refuse scripts, and prints the classification. It does not install packages, open a network connection, or create a credential.
