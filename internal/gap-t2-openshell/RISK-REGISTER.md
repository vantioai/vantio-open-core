# T2 risk register — OpenShell and Rogue Reconciliation

Audience: INTERNAL_RESTRICTED

Recorded: 2026-10-16T15:48:53Z

Update this file again when the fixture proof has run. Do not delete a risk because a later commit hopes it is gone.

| ID | Risk | Status | Residual |
| --- | --- | --- | --- |
| R1 | Live OpenShell and Phantom Engine were not run together. | Open. Label Roadmap. | The council comparison is a source reading. The join, once tested, is Lab-only against fixtures. |
| R2 | This runner is not an enrolled Vantio host. Docker and Podman are absent. Effective `cap_bpf` is absent. `unprivileged_bpf_disabled` is 2. | Open. Accepted for this track. | No install is attempted. A later drill needs a host the company owns. |
| R3 | Kernel `EventTimestamp` in the architecture case study is a monotonic nanosecond clock. OpenShell `time` is Unix time. | Open. Designed. | Rows without a Unix millisecond stamp are `UNATTRIBUTED` unless a Gate trace id matches. They are not cleared and they are not bypasses. |
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

## Approval gates still closed

Contact NVIDIA. Merge. Founder-approved label. Public claim change. Production enrollment. Cloud spend. Image publish. Moving the public pin.
