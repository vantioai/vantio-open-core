# T2 risk register — OpenShell and Rogue Reconciliation

Audience: INTERNAL_RESTRICTED

Recorded: 2026-10-16T15:48:53Z

Update this file again when the fixture proof has run. Do not delete a risk because a later commit hopes it is gone.

| ID | Risk | Status | Residual |
| --- | --- | --- | --- |
| R1 | Live OpenShell and Phantom Engine were not run together. | Open. Label Roadmap. | The council comparison is a source reading. The join, once tested, is Lab-only against fixtures. |
| R2 | This runner is not an enrolled Vantio host. Docker and Podman are absent. Effective `cap_bpf` is absent. `unprivileged_bpf_disabled` is 2. | Open. Accepted for this track. | No install is attempted. A later drill needs a host the company owns. |
| R3 | Kernel `EventTimestamp` in the architecture case study is a monotonic nanosecond clock. OpenShell `time` is Unix time. A monotonic reading can numerically overlap the Unix millisecond window. | Open. Designed. | `EventTimestamp` is ignored. Only `observed_at_ms` is a clock. Rows without that stamp are `UNATTRIBUTED` unless a Gate trace id matches. |
| R4 | OpenShell OCSF export is best-effort and drops lines when its 1,024-line queue is full. | Open. Accepted. | A dropped sandbox row can become `BYPASS_INDICATOR`. The reason is absence from the snapshot. |
| R5 | Scoped TC passes packets whose cgroup id is 0. | Open. Outside this track's code. | Those packets are `OUT_OF_SCOPE` for the indicator. The pass remains a Phantom Engine property. |
| R6 | Kubernetes `--enroll-watch` does not auto-attach `cgroup_skb` to pod cgroups, per the architecture roadmap. | Open. Inherited. | A pod forwarded path can miss both the TC attribution and this join. |
| R7 | Fork-inheritance evidence in the 1 Jul 2026 matrix is strong and not an isolated fork-only test. | Open. Inherited. | The join does not treat a parent process record as cover for a child network or file event. |
| R8 | Local `kind` and WSL2 rows can be retold as managed-cloud verification. | Open. Wording rule. | Product spec keeps GKE, EKS, AKS, and live Spanner at target design. This track uses that wording. |
| R9 | An OpenShell `metadata.uid` could be mistaken for a Vantio trace id. | Designed. | Event id is not a join key. A fixture must prove a collision does not reconcile. |
| R10 | PID namespaces and the measured PID offset can false-join on pid. | Designed. | PID is not a join key. |
| R11 | Conversation text or a credential could land in a fixture or a result. | Designed. | The loader rejects those keys and values. Output is an allowlist. The proof must not print a rejected value. |
| R12 | A corrupt or partial snapshot could be skipped and look like a clean run. | Designed. | The run status becomes `rejected` and the finding list is empty. |
| R13 | `decision_mismatch` could be read as a second enforcement product. | Designed. | It is a flag on `RECONCILED_OK`. It does not block traffic. |
| R14 | Integrating as OpenShell middleware would sit on the supervisor hop and miss the bypass class. | Closed by the verdict. | Verdict is differentiate. Integration stays an approval-gate item, and NVIDIA contact stays closed. |
| R15 | Sentry on BlueField-4 could be described as something Phantom Engine already does. | Open. Wording rule. | No BlueField port. No hardware claim. |
| R16 | Public pricing figures from older briefs could be copied. | Open. Wording rule. | Artifacts say Contact Vantio and contain no prices. |
| R17 | The internal positioning line could be pasted onto the website or README. | Open. | `POSITIONING.md` is marked draft and not for public use. This track does not edit those surfaces. |
| R18 | One OpenShell network row can match every kernel write to that destination inside the window. Counts are not compared. | Open. Accepted for the lab join. | A second TLS write is not, by itself, `BYPASS_INDICATOR` while the first row still matches. Cardinality is part of the Roadmap live drill. |
| R19 | An OCSF object with more than 64 keys, or a line over 65,536 bytes, rejects the snapshot. | Open. Accepted. | Rejection emits no finding. A richer live export needs a recorded adapter, not a silent skip. |
| R20 | `decision_mismatch` recognizes OpenShell disposition `Allowed` and Gate action `ALLOWED` only. | Open. Accepted. | Other spellings stay reconciled without the flag. The flag does not block traffic. |
| R21 | A caller-supplied clock offset can join unrelated events inside the window. | Open. Lab-only harness. | The offset is an input, not a measurement. See `LIVE-JOIN.md`. |
| R22 | The file harness can be described as a live OpenShell run. | Open. The live stack stays Roadmap. | `openshell_runtime` stays `not-executed`. |
| R23 | An OCSF drop still becomes `BYPASS_INDICATOR` when the file tail is missing that row. | Open. Accepted. | Absence is not a captured bypass on a live host. |
| R24 | A concurrent append during the file read is not locked. | Open. Lab-only. | Two readers can observe different prefixes. |

## Fixture proof

Command: `node --test internal/gap-t2-openshell/test/*.test.cjs`, which also runs `proof/prove-bypass.cjs`.

| Check | Result |
| --- | --- |
| Tests | 32 passed. The evidence file still records the 2026-10-16T16:01:29.765Z fixture proof. Fixtures did not change, so its hashes still match. |
| Evidence time | 2026-10-16T16:01:29.765Z |
| Drill indicator | `BYPASS_INDICATOR` |
| OpenShell control | `matched_openshell` |
| Gate control | `matched_gate` |
| Label | Lab-only |
| Live OpenShell process | not executed |
| Live Phantom Engine loader | not executed |
| Evidence | `internal/gap-t2-openshell/evidence/bypass-drill.json` |

R1 stays open. The fixture proof does not move the live stack off Roadmap. R3, R9, R10, R11, and R12 have fixture coverage and stay open as properties of a live capture.

## Approval gates still closed

Contact NVIDIA. Merge. Founder-approved label. Public claim change. Production enrollment. Cloud spend. Image publish. Moving the public pin.
