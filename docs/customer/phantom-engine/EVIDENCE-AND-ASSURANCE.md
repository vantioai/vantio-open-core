# Evidence and assurance

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Assurance in this manual means: which records exist, what each label guarantees, and which proofs have been run. It does not mean a certification, a WORM attestation, or a customer sign-off.

## How to read a row

| Field | Meaning |
|---|---|
| `TraceId` | Correlation id for this session or process. Empty or missing means you cannot join the row to an application record. |
| `Pid` | Process id the loader resolved. A failed resolution does not invent a pid. |
| `EventType` | `TLS_EGRESS` for a seen TLS write. `NETWORK_BLOCK` for a drop. `INGRESS_ACCEPT` for a seen inbound accept. Syscall events use the loader's syscall event type. |
| `ActionTaken` | Wire value. Pass-through TLS is `OBSERVED`. A drop is `BLOCKED`. Ingress accept is `OBSERVED` with decision observed. |
| Product label | Phantom Engine may present a pass-through as `ALLOWED`. That product word and the wire word `OBSERVED` refer to the same non-drop. Do not quote one and hide the other in an exam response. |
| `BytesObserved` | Length recorded for a seen write. Set on pass-through. |
| `BytesSevered` | Length of a packet that was actually dropped. Only a real `NETWORK_BLOCK` sets this to a measured drop length. Pass-through uses 0. |
| `RawSyscallId` | Syscall id when the event is a syscall record. |

Optics rows from the free client are `OBSERVED` and are not host enforcement. A report that mixes them must say which file they came from.

A drop that cannot be tied to a traced pid is not written as a fabricated ledger row. Absence of a `NETWORK_BLOCK` row can mean "no drop" or "drop occurred and attribution missed." Scoped mode's lab record included attributed `NETWORK_BLOCK` rows with non-zero `BytesSevered` (**independently tested**). Unattributed forwarded traffic is the residual in [KNOWN-LIMITATIONS.md](./KNOWN-LIMITATIONS.md).

## Reconciliation labels

| Label | When it applies | Status |
|---|---|---|
| Reconciled | Application record and host record share the trace id for that transmission | Lab comparison has been shown. A standing service that emits this continuously is **unavailable**. |
| `BYPASS_INDICATOR` | Host saw a transmission and the application layer has no matching record | Lab demo **independently tested**. Standing service **unavailable**. |

This manual does not tell you how to produce a gap. If you need a controlled demonstration, ask Vantio to run it under the architecture review. Do not turn that demonstration into a production control.

## Stores

| Store | What it is | What it is not | Status |
|---|---|---|---|
| Loader stdout | Operational event table | Not durable unless you retain logs | **independently tested** in lab sessions |
| Local NDJSON | Append-oriented file from `--output-file` | Not WORM. Not tamper-proof against a user who can write the file. | Content path **independently tested** on a lab host |
| Chart `/run/vantio/events.ndjson` | Ephemeral scratch | Not a backup | **configured** |
| Spanner `TrueTimeLedger` | Intended durable store with a commit timestamp | Not live-proven | Schema and writer alignment **independently tested** as code. Live insert **not tested**. |
| Customer SIEM | Your shipper | Not provided by the chart | **unavailable** as a Vantio integration guide |

Until a live Spanner row is queried in the target project, the honest evidence plane is retained logs plus any NDJSON you copied off the host.

## Lab evidence this manual relies on

The private product repository records the following on a Vantio lab host and, where noted, a local `kind` cluster. Manual version 1 did not re-run them. The September 20, 2026 remediation ran fixture checks of protection-state and verifier profiles. That remediation did not load eBPF. Those fixture passes are **independently tested** as unit fixtures, not as a kernel load.

| Item | Status |
|---|---|
| Verifier accepted the suite loaded in the lab session | **independently tested** (lab kernel and `kind`) |
| TLS observe with byte counts on OpenSSL and GnuTLS probes | **independently tested** |
| Fork trace-id inheritance | **independently tested** (strong evidence inside a broader run, not a standalone fork-only fixture) |
| Scoped `TC` drop, enrolled only; unenrolled passed | **independently tested** |
| Node-wide drop mode | **independently tested** in the lab; dangerous; default off |
| IPv4 CIDR prefix boundary | **independently tested** |
| `--enroll-watch` against the `kind` API, maps pinned, probes attached in the loader pod | **independently tested** |
| Startup process-identity calibration on the lab host and inside `kind` | **independently tested** |
| Helm lint and render | **independently tested** as a chart check in prior lab notes |
| Protection-state fixture (28 checks) and independent-verify profiles (8 checks) on 2026-09-20 | **independently tested** as fixtures |
| GKE, EKS, AKS functional rows | **not tested** |
| Live Spanner insert | **not tested** |
| IPv6 CIDR on a live dual-stack network | **not tested** |
| VLAN-tagged frames on real trunk hardware | Parser is in the program. Live tagged frames **not tested** |
| Cross-pod TLS using a different library file than the loader | **not tested** |
| Stranger host or any customer environment | **not tested** / **customer validated**: none |
| Inbound deny, quarantine execution, action reversal | **unavailable** |
| Certifications | None held |

`kind` is not managed Kubernetes. Say "local kind" when you cite that row.

## What you can tell an examiner today

You can say:

- The node can record host TLS writes and, when scoped enforcement is on and the workload is enrolled and attributable, can drop non-allowlisted egress.
- Lab evidence for that statement is Vantio's, on Vantio's hardware and a local kind cluster.
- Your own acceptance test is still open until you complete it and file it.
- The durable WORM path is not yet shown end to end.
- No certificate is held.

You cannot say, from this manual alone, that your cluster, your base image, or your Spanner project has been validated.
