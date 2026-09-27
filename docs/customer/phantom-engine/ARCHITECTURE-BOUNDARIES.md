# Architecture boundaries

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

## Planes

Phantom Engine is one purchase with three functions. They are not three invoices.

| Function | Where it runs | What "on" means |
|---|---|---|
| Observe | Optics on the wired process, and host probes on the enrolled Linux node | Events are **observed**. Optics alone does not block. |
| Enforce | Bundled on-prem application path, in process, for workloads that load it | Hostname block, redaction, and spend or size caps are **enforced** only on that wired path. |
| Control | `vantio-loader` on the Linux host | Enrolled egress drops and host path-prefix refusal, when those controls are turned on. |

Gate is the internal name of the Enforce function set. Customer language is Phantom Engine. Do not buy Gate as a second product on a Phantom Engine node.

Optics remains the free observe client in `vantio-open-core`. Phantom Engine source and the loader image come from the private product repository. This manual is stored beside the open-core tree for review. The running engine is not the Optics CLI.

## What stays in your environment

The host path is built to run inside your VPC or on your machines.

| Path | Boundary |
|---|---|
| Kernel programs and the enrolled-cgroup map | On the node. They do not require a Vantio SaaS hop to attach. |
| Loader stdout | On the node, in the service manager or `kubectl logs`. |
| NDJSON output file | On a path you pass to `--output-file`, if you set one. See [BACKUP-AND-RECOVERY.md](./BACKUP-AND-RECOVERY.md). |
| Spanner | Your GCP project, if you later configure `GOOGLE_SPANNER_DATABASE`. Live insert is **not tested**. |
| Bundled on-prem policy component | In your network. The Helm chart does not start it. |
| Optional cloud ingest | Only if you set `VANTIO_CLOUD_INGEST_URL` and an API key. Leave it unset when regulator data must stay on the host. |

Design intent (data plane for the kernel path remains in the customer environment) is **independently tested** as a design review of the loader, not as a managed-cloud proof. A cloud proof of a full sovereign pattern is **not tested**.

## Deployment shapes

| Shape | What runs | Status |
|---|---|---|
| Bare Linux daemon | `vantio-loader` on the host | Lab host **independently tested** |
| Kubernetes DaemonSet | Helm chart `deploy/helm` in the private product repository, namespace `vantio` | Local `kind` **independently tested**. Managed clouds **not tested**. |
| On-prem Enforce beside the DaemonSet | Authorized customer pack, separate from the chart | Pack exists as a companion procedure. This manual does not embed that pack. |
| Air-gapped mirror plus a customer SIEM shipper | No Spanner; you copy NDJSON | Architecture can run without Spanner. A written mirror procedure is **unavailable**. |
| Vantio-hosted multi-tenant Phantom Engine | — | **unavailable** |

The DaemonSet is `hostNetwork` and `hostPID`. It is scheduled on workers. Control-plane scheduling is off unless you set `scheduleOnControlPlane`. Do not combine that opt-in with enforcement.

## Correlation

A trace id ties application records to host records when both sides were given the same id.

1. You export `VANTIO_TRACE_ID` (16 hex digits with an `0x` prefix) for the loader session.
2. A governed process is started with that identity, or you inject the id onto a running pid (`vantio-loader --inject`).
3. Child processes inherit the id when the fork hook is attached and process identity resolves.
4. Ledger rows that share the id can be compared later.

Inject and inheritance have lab evidence (**independently tested**). An admission webhook that inserts the annotation or the trace id for you is **unavailable** (intentionally not shipped). You set the annotation yourself. See [ENROLLMENT-GUIDE.md](./ENROLLMENT-GUIDE.md).

Rogue Reconciliation is the comparison: host transmission with no application-layer record is `BYPASS_INDICATOR`. Both sides present is the reconciled case. The lab demo has shown the indicator. A productized reconciliation service is **unavailable**.

## Enforcement scope

Scoped mode drops egress only when both are true: the packet is attributed to an **enrolled** cgroup, and the destination is outside the built-in private ranges and your allow rules. An empty enrolled set drops nothing. That fail-safe has lab evidence (**independently tested**).

Traffic the node interface cannot attribute to a local socket is treated as not enrolled and is passed by the node-interface classifier. Forwarded traffic from a non-`hostNetwork` pod is the usual case. An optional per-cgroup egress attachment exists for Docker and startup enrollment. Kubernetes `--enroll-watch` does not attach it. That Kubernetes gap is **unavailable** as an automatic behavior in this version. Details and operator choices are in [KNOWN-LIMITATIONS.md](./KNOWN-LIMITATIONS.md) and [POLICY-GUIDE.md](./POLICY-GUIDE.md).

Node-wide mode drops non-allowlisted egress on the attached interface regardless of cgroup. It is **configured** only when you pass `--node-wide-enforcement` or set `nodeWideEnforcement=true`. It can cut the node off. Leave it false.

Control path protection matches configured path prefixes on the host. The match is host-wide. It is not limited to enrolled cgroups. Process termination after a path refusal is off unless you explicitly enable it.

## Ingress

Inbound accept activity on enrolled workloads can be **observed** (`INGRESS_ACCEPT`, decision observed). That record does not drop the connection. Inbound deny is **unavailable**. Phantom Engine is not a firewall, WAF, or DDoS product.

Coverage words for that observe path, when the inventory tool is run, are `seeing`, `honest_idle`, `cannot_see`, and `degraded`. Idle means no established inbound and no unexpected listener in the snapshot. `cannot_see` means the inventory could not read enrollment or the network namespace. Those states were exercised in Vantio's lab (**independently tested** on that lab). They are not a stranger-host pass (**not tested** elsewhere).

## What this product is not

| Ask | Status |
|---|---|
| Generic EDR, action reversal, or automatic quarantine | **unsupported** as a description of this version. A quarantine planner exists and its executor is **unavailable** (unwired). |
| Certifications (SOC 2, ISO, or otherwise) held by Vantio | None held. This manual is not an attestation. |
| A network proxy that all agent traffic must traverse | The application path enforces in process. The host path is on the node. There is no mandatory proxy hop. |
| Coverage of workloads that are not enrolled, or of hosts that are not running the loader | Outside the purchase's effective scope. Unenrolled traffic is passed in scoped mode by design. |
