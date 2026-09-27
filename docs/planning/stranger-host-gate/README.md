# Stranger-host gate (WS3 P34 prep)

Audience: INTERNAL_RESTRICTED

Classification: `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`

This directory is the prep packet for a later stranger-host run. Execution is unauthorized. The entrypoint that a host run would call refuses:

```bash
node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs
node docs/planning/stranger-host-gate/scripts/verify-readiness-update.mjs
node docs/planning/stranger-host-gate/scripts/refuse-stranger-host-execution.mjs
node docs/planning/stranger-host-gate/scripts/refuse-rollback.mjs
```

The prep verifier exits 0 and prints `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH` when the packet is intact. The readiness verifier exits 0 and prints `STRANGER_HOST_READINESS_UPDATED_READY_FOR_COUNCIL`. Each refuse script exits 2. `--execute` on either verifier exits 2.

| File | Role |
| --- | --- |
| `00-PACKET-BOUNDARY.md` | Scope, hard stop, prepared SHA |
| `01-PACKET-CHECKLIST.md` | Prep rows and LATER rows |
| `02-EVIDENCE-REQUIREMENTS.md` | Prep record and the later bundle, tiers `UNSET` |
| `03-STOP-CONDITIONS.md` | SH-STOP-01 through SH-STOP-21 |
| `04-FOUNDER-AUTHORIZATION-TEMPLATE.md` | Copy-ready form for a later force |
| `authorization/FOUNDER-AUTHORIZATION.template.json` | Machine-checked `NOT_AUTHORIZED` template |
| `05-RUNBOOK.md` | Phase 0 and Phase 0b now; Phases 1–6 unauthorized |
| `06-ROLLBACK.md` | Disposable-path rollback, unauthorized |
| `PACKET-MANIFEST.json` | Hashes and classification fields |
| `07-READINESS-UPDATE.md` | Currency inventory and readiness classification |
| `08-PLACEHOLDER-MATRIX.md` | Ingress, egress, host-authority, sequential-authority, health, progressive-enforcement placeholders |
| `PLACEHOLDER-MATRIX.json` | Machine-checked placeholder rows, all `NOT_EXECUTED` |
| `09-EXECUTION-AUTH-CHECKLIST.md` | Named host and operator checklist, `UNFILLED` |
| `authorization/EXECUTION-AUTH-CHECKLIST.template.json` | Machine-checked unfilled checklist |
| `10-INDEPENDENT-COUNCIL.md` | Producer stub, `PENDING_INDEPENDENT_COUNCIL` |
| `scripts/verify-packet-prep.mjs` | Local prep verifier |
| `scripts/verify-readiness-update.mjs` | Readiness verifier. Prints `STRANGER_HOST_READINESS_UPDATED_READY_FOR_COUNCIL` |
| `scripts/readiness-lib.mjs` | Checklist gap rule and readiness checks |
| `scripts/readiness.test.mjs` | Direct and adversarial packet tests |
| `scripts/refuse-stranger-host-execution.mjs` | Host-execution refusal |
| `scripts/refuse-rollback.mjs` | Rollback refusal |
