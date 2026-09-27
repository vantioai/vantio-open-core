# Packet checklist

Audience: INTERNAL_RESTRICTED

Classification: `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`

The local verifier is the check for this table. A row in the prep section is satisfied when `node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs` exits 0. Rows marked LATER stay open. This document does not close them.

## Prep (this force)

| ID | Item | Where | State |
| --- | --- | --- | --- |
| P1 | Packet boundary, hard stop, prepared SHA | `00-PACKET-BOUNDARY.md` | Required for the classification |
| P2 | Checklist | This file | Required for the classification |
| P3 | Evidence requirements, tiers left `UNSET` | `02-EVIDENCE-REQUIREMENTS.md` | Required for the classification |
| P4 | Stop conditions SH-STOP-01 through SH-STOP-20 | `03-STOP-CONDITIONS.md` | Required for the classification |
| P5 | Founder authorization template still `NOT_AUTHORIZED` | `04-FOUNDER-AUTHORIZATION-TEMPLATE.md` and `authorization/FOUNDER-AUTHORIZATION.template.json` | Required for the classification |
| P6 | Runbook written | `05-RUNBOOK.md` | Written. Execution is LATER |
| P7 | Rollback written | `06-ROLLBACK.md` | Written. Execution is LATER |
| P8 | Execution entrypoint refuses | `scripts/refuse-stranger-host-execution.mjs` | Exit 2 |
| P9 | Rollback entrypoint refuses | `scripts/refuse-rollback.mjs` | Exit 2 |
| P10 | Local verifier | `scripts/verify-packet-prep.mjs` | The prep command |
| P11 | Manifest hashes for every packet file except the manifest | `PACKET-MANIFEST.json` | Required for the classification |
| P12 | Packet bytes contain no credential material | Verifier secret scan | Required for the classification |

## Later execution (unauthorized)

| ID | Item | State |
| --- | --- | --- |
| L1 | A later Founder force copies the template, names the host, locks the SHA, and replaces the refuse script | LATER |
| L2 | Host attestation: owner, class, and why the machine is outside the producer environment | LATER |
| L3 | Clean checkout of the locked SHA | LATER |
| L4 | CI parity commands from `05-RUNBOOK.md` | LATER |
| L5 | Evidence bundle with `tier.txt` containing `UNSET` | LATER |
| L6 | Published install smoke | LATER, and only after a future authorization changes `published_install_smoke` from `NO` |
| L7 | Independent reviewer on the evidence bundle | LATER. `PROVED_EXTERNAL` stays unset here |
| L8 | Confirmation that customer validation stays unset | LATER record. A customer host is forbidden |
| L9 | Rollback of the disposable directories recorded for that run | LATER, and only if that run created them |

## Closed by this prep

P1 through P12 are the prep contract. The verifier fails the packet when a required file, marker, hash, authorization field, or refuse behavior drifts.

## Left open on purpose

L1 through L9 require a host, a Founder authorization, or both. This force stops before those rows.
