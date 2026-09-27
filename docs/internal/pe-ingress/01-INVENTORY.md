# Ingress inventory

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL`

Read date: 2026-09-27. Product tip: `631e435315cd780d83d3259e111893c1d0569bc3`. Class for every row: `OBSERVED_FROM_REPOSITORY_EVIDENCE`. This force did not run `pe_ingress_truth.py`, `vantio_assure.py`, or the loader.

## 1. Blobs read

| Path | Blob | Use |
| --- | --- | --- |
| `docs/enterprise/INGRESS_P0B.md` | `92fe8a5692bb55ec710206120a78e537642a7d3b` | Observe-only ingress truth that landed on Phantom-Box |
| `docs/enterprise/INGRESS_SECURITY_FEASIBILITY.md` | `3da24295df42105f1d060ecdb3f1c551034d95bd` | 25-capability scoreboard. Present 3, Partial 13, Roadmap 9 |
| `python/pe_ingress_truth.py` | `a83dc64e63000f34c28f5d590f9e1508e205e9f6` | Listener classes, coverage names, envelope match |
| `architecture_state.md` | `84d53654894180cbf351d62231f90e564504162c` | Cited by the feasibility file as inspected. Not re-executed |
| `python/pe_protection_state.py` | `a1b49fe6e431cdb574f0d285f7976236945519c7` | Nine protection-state names, via the open-core health binding |

P0b decision on that tip is `observed`. `ActionTaken` on those rows is `OBSERVED`. The file says the slice does not drop packets, isolate processes, or expand `enforce_paths`.

Confirmed absent as inbound enforce on that tip: `cgroup_skb/ingress`, TC ingress, `sock_ops`, `bpf_sk_lookup`, sockmap, and an inbound drop. P0b added observe-only `accept` / `accept4` tracepoints and a `/proc` listener inventory.

## 2. What P0b can name

| Item | Repository status | Residual named in the same files |
| --- | --- | --- |
| Enrolled listener inventory | Present, `/proc` netns snapshot | Unix-domain and vsock are cannot-see. Host daemons outside enrolled cgroups are out of scope |
| Expected, unexpected, undeclared, missing | Present, envelope versus observed | Empty envelope or another workload's rows stay undeclared. Unexpected is named, not refused at bind |
| Inbound TCP accept to process | Present for `accept` / `accept4` | UDP peer, `io_uring`, and short-lived fds stay cannot-see |
| Interface | Partial | Loopback may be named `lo` by the scanner. Other ifaces stay unnamed. No ingress classifier |
| Parent and TraceId | Partial | Full inbound tree walk and containment stay later phases |
| Coverage | `seeing`, `honest_idle`, `cannot_see`, `degraded` | A gap is not a safe empty list |
| Quarantine executor | Unwired | `pe_scoped_quarantine.py` plans `cgroup.freeze`. Live `quarantine_action` is unwired. Company-host apply stays refused |
| Identity revoke | Roadmap signal only | The engine is not an identity provider. Automatic credential revoke is rejected there |

## 3. Authority gaps this program fills in-process

The private scoreboard leaves workload-specific ingress policy, source policy, connection isolation, and live containment on later phases. This open-core program does not start those kernel phases.

It does decide, for an evidence bundle, whether post-accept authority is held, refused, withheld, or observation-only. That decision does not attach a program and does not change the loader.

## 4. Classifier difference the council should see

`pe_ingress_truth.py` marks a declared listener missing only when that workload already has at least one observed socket in the same snapshot. A named workload with zero sockets does not produce missing rows.

`evaluateIngress` is already scoped to one workload bundle. A declared row and no listener object yields `listener_state` `missing`. The pure `classifyListeners` export keeps the snapshot rule from the Python file, and the direct test checks that rule.

## 5. Health tokens reused, not extended

Protection-state echo is limited to the nine names in `docs/planning/phantom-engine-production/HEALTH-VOCABULARY.json`: `protected`, `observing`, `not_enrolled`, `protection_stale`, `policy_stale`, `degraded`, `quarantined`, `recovery_required`, `coverage_unknown`.

This program does not add a protection state. Shared freshness stays `UNKNOWN` under `FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN`. Caller-window attestation uses `identity_attestation`, not the reserved freshness tokens `CURRENT`, `HISTORICAL`, or `STALE`.
