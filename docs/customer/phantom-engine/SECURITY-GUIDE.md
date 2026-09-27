# Security guide

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

This is an operator security guide. It is not a penetration-test report, not a certification, and not an attestation. Vantio holds no SOC 2, ISO 27001, or similar certificate as of this manual. Framework mapping, if your account team discusses it, is mapping only.

## Assets

| Asset | Why it is in scope |
|---|---|
| Prompts, tool payloads, and files the agent can read | They can contain personal data or secrets. Host TLS observe records sizes and endpoints, not prompt bodies, unless you explicitly enable the keyword mark. |
| Agent credentials | A governed and an ungoverned path differ. Rogue Reconciliation exists to name a host transmission with no application record. |
| The ledger | Examiners will ask what was **observed** and what was **enforced**. Labels must stay honest. |
| Loader privileges | The DaemonSet holds `CAP_BPF`, `CAP_NET_ADMIN`, and `CAP_SYS_ADMIN` in the host PID and host network namespaces. Treat the pod as a high-value workload. |

## Adversaries the design considers

1. A prompt-compromised agent using a legitimate process.
2. Agent code that exfiltrates or loops.
3. An operator who ships a process without the application-path wrap.
4. A process that forks or uses a library the wrap does not see.

Hardware implants, kernel exploits against eBPF, and physical theft of disks are outside this guide. A privileged person on the node can stop the loader. That residual is part of the product boundary. Hardening of the node, admission control, and heartbeat monitoring are your controls for it. Phantom Engine does not claim to be agent-proof against a root user who unloads it.

## Controls

| Layer | Control | Residual |
|---|---|---|
| Optics | **observed** metadata on the wrapped path | A process that is not wrapped has no Optics row. |
| Bundled Enforce | In-process block, redact, spend or size cap when the process is wired | The same skip produces no Enforce row. |
| Host Control | TLS observe, fork inheritance of trace id, scoped egress drop for enrolled cgroups, optional path-prefix refusal | Requires the capabilities above to run, and a privileged operator can stop it. Forwarded pod traffic may be unattributed. Path canonicalization is **unavailable**. |
| Rogue Reconciliation | Names `BYPASS_INDICATOR` when a comparison sees a host transmission and no application record | The lab demo has produced the label. A standing service is **unavailable**. |

Trust assumptions you must actually meet:

- Kernel 5.8+, BTF, cgroup v2, bpffs, and the capabilities above.
- Workloads you intend to drop are **enrolled**.
- Application and host records share a trace id when you need correlation.
- Consumers of the ledger treat `OBSERVED` on the wire as pass-through, and `BLOCKED` / `NETWORK_BLOCK` as the drop.

## Pod hardening in the chart

The container sets `privileged: false`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `seccompProfile: RuntimeDefault`, and drops all capabilities except `BPF`, `NET_ADMIN`, and `SYS_ADMIN`. It mounts bpffs, read-only cgroupfs, read-only debugfs, and a writable `emptyDir` at `/run/vantio`.

Those settings are **configured** in chart 0.1.1. A lab `kind` cluster ran the DaemonSet. Acceptance by a managed cluster's Pod Security standards is **not tested**. A dedicated test that the three capabilities are sufficient on every supported kernel is **not tested** as its own row; the lab node did load programs as root.

RBAC is read-only on nodes and read/watch on pods. Do not widen it to delete or exec in application namespaces.

## Data handling

| Data | Handling |
|---|---|
| Prompt and completion bodies | Not stored by the host TLS observe path. The keyword mark inspects a short plaintext prefix only when you set `--tls-sever-keyword`, and it does not stop that write. |
| Trace ids, pids, byte counts, destinations | Present in logs and NDJSON. Treat the log as security telemetry. |
| `VANTIO_API_KEY`, Spanner JSON | Your secrets. This manual contains none. |
| Signal Share | Shipped default is off. The loader does not send it. |
| Optional ingest to `https://vantio.ai` | Off unless you set `VANTIO_CLOUD_INGEST_URL`. Leave it unset when data must remain in your VPC. |

Inbound accept records are **observed**. They are not blocks. Do not describe Phantom Engine as stopping inbound attackers.

## This manual

Classification is CUSTOMER_CONFIDENTIAL. Distribution is authorized customers and the Vantio review of this draft. Do not attach it to a public ticket, a public repository wiki, a website, or an `llms.txt` file. A customer assistant that reads it must follow [CUSTOMER-AI-GUIDE.md](./CUSTOMER-AI-GUIDE.md).

The manual omits kernel offsets, map layouts, probe internals, and any procedure whose purpose is to defeat a control. Asking a vendor or a model to fill those omissions is outside support.

Report a suspected vulnerability to `security@vantio.ai`. Include the image tag and the mode the node was in. Do not include exploit payloads.
