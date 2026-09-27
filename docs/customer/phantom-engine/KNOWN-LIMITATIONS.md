# Known limitations

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Limits below are properties of product version 0.1.0 as documented at commit `631e435315cd780d83d3259e111893c1d0569bc3`. They are not a backlog with dates.

## Coverage

| Limit | Status |
|---|---|
| Only enrolled workloads are in scoped Control. Everyone else is passed. | By design. **independently tested** as the fail-safe. |
| The node-interface classifier attributes traffic it can tie to a local socket. Forwarded egress from a non-`hostNetwork` pod can pass that classifier even when the pod is annotated. | Residual. Kubernetes `--enroll-watch` does not attach the optional per-cgroup egress program. That automatic attach is **unavailable**. |
| Optional per-cgroup egress attach for Docker and startup enrollment exists and defaults off. | Shipped flag. **customer validated**: none. |
| TLS observe follows the OpenSSL and GnuTLS probes the loader attached. Another TLS stack, or another copy of the library file in a different image, can be invisible to those probes. | Cross-image case **not tested**. |
| The TLS probe records a write. It does not stop that write. | By design. Stopping egress is the classifier, after the write, when enforcement is on and the packet is attributable. |
| Keyword mark does not stop the write that matched. | By design of that flag. Off unless set. |
| Inbound accepts can be **observed**. They are not dropped. | Inbound deny is **unavailable**. |
| UDP, QUIC datagram peers, `io_uring` accepts, and listeners outside enrolled cgroups are outside the inbound observe guarantee. | **unsupported** as covered cases. The inventory says `cannot_see` when it cannot read the namespace. |
| Path-prefix refusal is host-wide, not per enrolled cgroup. Full canonicalization of every alternate path is **unavailable**. | Operator hazard. Review prefixes before enabling. |
| Process termination after a path refusal is off unless both `--kill-on-enforce` and `VANTIO_PHANTOM_DENY=1` are set. | Default off. |
| A privileged operator can stop the loader. Heartbeat monitoring is how you notice. | Residual. Node hardening is yours. |
| One interface per loader. | Multi-interface attach is **unavailable**. |
| Raw manifest `--iface $(NODE_IFACE)` is not shell-expanded. | Use Helm `nodeIface`, or replace the argument. |
| Chart NDJSON on `/run/vantio` is ephemeral. The chart does not mount a durable log volume. | [BACKUP-AND-RECOVERY.md](./BACKUP-AND-RECOVERY.md) |
| Local NDJSON is append-oriented. It is not WORM. | Live Spanner insert is **not tested**. |
| Quarantine execution, action reversal, and generic EDR behavior | **unavailable** / **unsupported** as a description of this version. A planner exists; the executor is unwired. |
| Standing Rogue Reconciliation service | **unavailable**. A lab demo has produced `BYPASS_INDICATOR`. |
| Admission webhook that enrolls pods for you | **unavailable**. |
| Signal Share transmission | **unavailable**. Default off. |
| Multi-tenant hosted Phantom Engine | **unavailable**. |
| Air-gapped mirror runbook | **unavailable**. |
| Certifications | None held. |

## Environments

| Limit | Status |
|---|---|
| Kernel older than 5.8, no BTF, cgroup v1, or no bpffs | **unsupported**. |
| Non-Linux host as the enforcement node | **unsupported**. |
| GKE, EKS, AKS | **not tested**. |
| Any customer environment | **customer validated**: none. |
| A Linux host that is not Vantio's lab | Stranger-host pass **not tested**. |
| IPv6 CIDR allow on a live dual-stack network | **not tested**. Exact IPv6 allow entries are implemented. |
| VLAN or QinQ frames on real trunk hardware | Live frames **not tested**. |
| Pod Security Admission on a managed cluster | **not tested**. |
| Control-plane enforcement | Prohibited by this manual. The chart does not schedule control planes unless you opt in. |

## Identity

Startup calibration of process identity runs once per loader start. `curl` must be installed. The DaemonSet must use the host PID namespace. If the measured relationship goes stale during one long process lifetime, restart the loader. Periodic recalibration is **unavailable**.

Do not edit the calibration file. Support may ask for diagnostic command output in a private ticket. This manual does not document how to adjust identity by hand.

## Application path

Skipping the in-process wrap produces no Enforce record. Host observe can still see a probed TLS write. Those two facts are the reason the gap has a name. They are not a promise that every unwrapped flow is labeled automatically. The labeling service is **unavailable**.

The public `@vantio/gate-mcp` package is a dry-run. It is not host Control and it is not a second product.

## Performance and availability

The chart requests 50m CPU and 64Mi memory and limits the container to 200m and 256Mi. Those numbers are scheduling hints. This manual states no host CPU percentage and no latency budget. No such measurement is recorded here.

During a rolling restart, one node at a time has no attached programs until the new pod is Ready. That window is a coverage gap.

## Manual status

This document set is a **draft**. It matches the product commit named above. It is not itself **customer validated**. Publishing it to a website, package registry, or `llms.txt` is out of scope. See [CUSTOMER-OVERVIEW.md](./CUSTOMER-OVERVIEW.md).
