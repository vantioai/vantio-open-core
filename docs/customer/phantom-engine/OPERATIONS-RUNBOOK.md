# Operations runbook

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Audience: the platform team that owns the enrolled nodes. This runbook does not change product behavior by being read.

## Daily checks

| Check | Healthy signal | If it fails |
|---|---|---|
| Loader process or DaemonSet | Pod `Running` / `Ready`, or the host process still in the foreground or under your service manager | [TROUBLESHOOTING.md](./TROUBLESHOOTING.md), then [INCIDENT-RESPONSE.md](./INCIDENT-RESPONSE.md) if enforcement was on |
| Heartbeat | `/run/vantio/heartbeat` (Kubernetes) touched within 60 seconds. The loader refreshes it about every 15 seconds. | Liveness restarts the pod after the probe fails. A restart is **observed** in pod events. It is not evidence that policy is correct. |
| Mode | Log line shows audit, unless change control has approved scoped enforce | If you see node-wide and that was not approved, return to audit. [INCIDENT-RESPONSE.md](./INCIDENT-RESPONSE.md) |
| Enrollment | Pilot pods with `vantio.ai/enroll: "true"` show up in the loader log after the reconcile interval (about 30 seconds) | [ENROLLMENT-GUIDE.md](./ENROLLMENT-GUIDE.md) |
| On-prem Enforce health | `http://127.0.0.1:5001/health` when the customer pack is in use | The chart does not run this process. A failed health check means the node is not a complete install. |
| Disk for NDJSON | Bare metal: the directory you passed to `--output-file` is writable and rotated by you | [BACKUP-AND-RECOVERY.md](./BACKUP-AND-RECOVERY.md) |

Kubernetes liveness uses `test` and `stat` on the pinned map `/sys/fs/bpf/vantio_trace_map` and the heartbeat. The map pin can outlive the process, which is why the heartbeat is required. Probe timing in the chart: `initialDelaySeconds` 20, `periodSeconds` 30.

## Change control

| Change | Required posture |
|---|---|
| First install | Audit, one pilot node, `nodeWideEnforcement=false`, control plane excluded |
| Annotate a new workload | Still audit until that workload is **enrolled** and you have seen **observed** events or an explicit enroll log |
| Turn on scoped enforce | Maintenance window, allowlist reviewed, unenrolled neighbor tested so you know it still passes |
| Turn on node-wide | Separate written acceptance that the node may lose non-allowlisted egress. Not a routine change. |
| Enable path-prefix refusal or process termination | Architecture review. Process termination stays off by default. |
| Change `nodeIface`, image tag, or chart values | [UPGRADE-AND-ROLLBACK.md](./UPGRADE-AND-ROLLBACK.md) |
| Point Spanner at a database | Keep a local or log copy until a row is queried in your project. Live insert is **not tested** by Vantio. |

Record who approved enforcement. The product does not store that approval for you.

## What operators see

The event table header is:

```text
PID       Trace ID            Type     Action     Detail      Timestamp(ns)
```

A TLS row in audit is **observed**. The product label for that pass-through on Phantom Engine is `ALLOWED`. The wire action may read `OBSERVED`. A real drop is `NETWORK_BLOCK` / `BLOCKED` and carries `BytesSevered`. Rows without a resolved trace id for the dropping process are not invented. See [EVIDENCE-AND-ASSURANCE.md](./EVIDENCE-AND-ASSURANCE.md).

Exec and open activity that the attached tracepoints emit is **observed**. It is not, by itself, a path refusal.

## Service management on bare metal

Run the loader under a supervisor you control (systemd or equivalent), as root or with `CAP_BPF`, `CAP_NET_ADMIN`, and `CAP_SYS_ADMIN`. Pass environment on the command line (`VAR=val sudo ./vantio-loader`). `sudo -E` is not available on every sudo build.

A clean stop is Ctrl-C or a supervisor stop that delivers the same interrupt. The loader detaches probes and leaves the pinned trace map on disk until reboot or until you remove it. See [REMOVAL-AND-UNINSTALL.md](./REMOVAL-AND-UNINSTALL.md).

Do not enable enforcement in the same unit that starts on a control-plane host.

## Kubernetes operations

```bash
kubectl get daemonset -n vantio
kubectl get pods -n vantio -o wide
kubectl logs -n vantio daemonset/vantio-phantom-engine --tail=100
kubectl describe pod -n vantio -l app=vantio-phantom-engine
```

The Helm release name in the examples is `vantio-phantom-engine`. Labels use that release name. Rolling update `maxUnavailable` is 1.

Image pull policy in the chart is `Always` with tag `0.1.0`. Pin the digest in your own overlay when your registry process requires immutability. Do not float the tag to `latest`.

Resource requests in the chart: 50m CPU, 64Mi memory. Limits: 200m CPU, 256Mi memory. Those are **configured** defaults, not a capacity test of your node (**not tested** as a performance claim).

## Permissions and secrets

| Secret | Purpose |
|---|---|
| `vantio-secrets` key `VANTIO_TRACE_ID` | Session trace id. Optional in the chart. Generate with `openssl rand -hex 8` and prefix `0x`. |
| `google-cloud-key` | Service account JSON, only if you are testing Spanner. |

RBAC is nodes `get`/`list` and pods `get`/`list`/`watch`. Review that binding in your cluster's permission model. The loader does not need permission to delete workloads.

## On-call handoff

State, in the ticket:

- image tag and Helm revision
- audit versus scoped versus node-wide
- whether control-plane scheduling is off
- which namespaces are annotated
- whether the on-prem health check is passing
- where the current evidence copy lives (logs, ephemeral `/run/vantio`, or a host file)

A handoff that says only "Phantom Engine is on" is not enough to tell **enrolled** from **enforced**.
