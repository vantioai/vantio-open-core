# Stranger-host gate (WS3 P34 prep)

Audience: INTERNAL_RESTRICTED

Classification: `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`

This directory is the prep packet for a later stranger-host run. Execution is unauthorized. The entrypoint that a host run would call refuses:

```bash
node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs
node docs/planning/stranger-host-gate/scripts/refuse-stranger-host-execution.mjs
node docs/planning/stranger-host-gate/scripts/refuse-rollback.mjs
```

The verifier exits 0 and prints the classification when the packet is intact. Each refuse script exits 2.

| File | Role |
| --- | --- |
| `00-PACKET-BOUNDARY.md` | Scope, hard stop, prepared SHA |
| `01-PACKET-CHECKLIST.md` | Prep rows and LATER rows |
| `02-EVIDENCE-REQUIREMENTS.md` | Prep record and the later bundle, tiers `UNSET` |
| `03-STOP-CONDITIONS.md` | SH-STOP-01 through SH-STOP-20 |
| `04-FOUNDER-AUTHORIZATION-TEMPLATE.md` | Copy-ready form for a later force |
| `authorization/FOUNDER-AUTHORIZATION.template.json` | Machine-checked `NOT_AUTHORIZED` template |
| `05-RUNBOOK.md` | Phase 0 now; Phases 1–6 unauthorized |
| `06-ROLLBACK.md` | Disposable-path rollback, unauthorized |
| `PACKET-MANIFEST.json` | Hashes and classification fields |
| `scripts/verify-packet-prep.mjs` | Local prep verifier |
| `scripts/refuse-stranger-host-execution.mjs` | Host-execution refusal |
| `scripts/refuse-rollback.mjs` | Rollback refusal |
