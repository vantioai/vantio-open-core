# Troubleshooting

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Fix the prerequisite that failed. Do not hand-edit the loader binary or the calibration file.

## Startup

| What you see | What it means | What to do |
|---|---|---|
| Embedded object format error | The binary was not produced by the supported build | `cargo build -p vantio-loader --release` or use image tag `0.1.0`. Do not patch bytes. |
| `failed to pin map: No such file or directory` | bpffs is not mounted | `sudo mount -t bpf bpf /sys/fs/bpf` and confirm the chart's hostPath `/sys/fs/bpf` exists on the node. Local `kind` needed this mount. |
| `failed to pin map: File exists` | A pin was left behind | Current loader builds clear a stale pin on startup. If the error remains, confirm no other loader is running, then remove only that pin during a maintenance window. See [REMOVAL-AND-UNINSTALL.md](./REMOVAL-AND-UNINSTALL.md). |
| `BPF_PROG_LOAD failed` | The kernel verifier rejected a program | Confirm kernel ≥ 5.8 and BTF. Rebuild against this kernel. A rejection on your kernel is **not tested** until you capture the verifier log in the change ticket. Do not treat a lab kernel's acceptance as your kernel's acceptance. |
| `failed to add clsact qdisc: File exists` | A previous attach left the qdisc | The loader treats this as idempotent and continues. |
| `sudo: preserving environment is not supported` | `sudo -E` is blocked | Pass variables as `VAR=val sudo ./vantio-loader`. |
| Read-only file system on the calibration path | Default path `/var/run/vantio_pid_offset` is not writable | The chart sets `VANTIO_PID_OFFSET_PATH=/run/vantio/pid_offset`. The loader still calibrates in memory and repeats that work on each start when it cannot save the file. Point the variable at a writable path. Do not chmod the container root; the root filesystem is read-only on purpose. |
| Pod `CrashLoopBackOff` and liveness failures | Heartbeat older than 60 seconds or the trace map pin is missing | Read logs. A deadlock in the event loop fails this probe on purpose. Confirm bpffs and capabilities. The probe uses `test` and `stat` only. |

## No events

| What you see | What it means | What to do |
|---|---|---|
| No rows for an annotated pod | Not enrolled, wrong node, or cgroup v1 | Confirm the annotation is on the pod, `cgroup2fs` is in use, and the loader log shows enroll-watch for that node name. |
| Enforcement drops nothing | Scoped mode with an empty enrolled set drops nothing | Enroll the workload. This is the fail-safe, not a broken classifier. |
| `--inject` printed success and TLS rows are still absent | Process identity on this host did not match, or the process did not call a probed library | Confirm `curl` is installed and the loader is in the host PID namespace (`hostPID: true` on the DaemonSet). Restart the loader so startup calibration runs again. If the log says calibration saw no TLS traffic, install `libssl.so.3` or `libgnutls.so.30`, and install `curl`. |
| `warning: could not translate PID` | Namespace translation failed and calibration was not available | Same as the row above. |
| No rows for `curl` on a recent Ubuntu | `curl` may be linked to GnuTLS | The loader attaches both probes when both libraries exist. Confirm the GnuTLS probe line in the startup log. |
| Events on the loader node and none from another pod's TLS | The probe attaches to the library file it resolved. A pod with a different copy of `libssl` or `libgnutls` is **not tested**. | Record the library path inside the workload image. Cross-image interception is **not tested**. |
| Enrolled pod, still no drop, scoped mode on | The node interface may not attribute forwarded pod traffic | See [KNOWN-LIMITATIONS.md](./KNOWN-LIMITATIONS.md). `hostNetwork` workloads are the case the lab drop covered. Kubernetes enroll-watch does not attach the extra per-cgroup program. |

Startup calibration runs once per process. If process identity drifts during a long-lived process, rows can go quiet or attach to the wrong pid until you restart the loader. Periodic recalibration is **unavailable**.

Diagnostic flags `--dump-trace-map` and `--dump-debug-counters` exist for a support session. They print trace-map entries and pipeline counters. Use them with Vantio support. This manual does not interpret counter indexes. Do not publish the output in a public ticket; it contains process ids and trace ids from your host.

## Interface mistakes

If the log names an interface you do not have, or attach fails immediately after `--iface`, you passed the wrong name.

Helm: set `nodeIface` and upgrade.

Raw manifest: replace the `--iface` argument. The token `$(NODE_IFACE)` in `deploy/kubernetes/daemonset.yaml` is not expanded by Kubernetes exec form. A pod that was applied with that token is **configured** with a bad interface name.

Common names from the chart comments, not from a cloud test: `eth0`, `ens5`, `enp0s3`. Measure on the node.

## Enforcement surprises

| What you see | What it means | What to do |
|---|---|---|
| Whole node lost egress | Node-wide mode is on, or a broad allowlist is missing for a destination the node itself needs | Return to audit. [INCIDENT-RESPONSE.md](./INCIDENT-RESPONSE.md). Leave `nodeWideEnforcement` false. |
| Pilot dropped, neighbor still works | Scoped mode | Expected when the neighbor is not **enrolled**. |
| Private addresses never drop | Built-in permit for RFC1918, loopback, link-local, IPv6 ULA and link-local | Expected. Use application-path policy if that flow must be constrained in process. |
| A destination inside an allow CIDR is dropped | Prefix or address family does not match, or `--sever-cidr` hard-blocks it | Check the configured prefix. Hard-block wins over allow. IPv6 CIDR live behavior is **not tested**. |
| Path refusal hit a process you did not enroll | Path prefixes are host-wide | Remove or narrow the prefix. Enrollment does not scope path protection. |

## On-prem component

The chart can be Ready while `http://127.0.0.1:5001/health` is down. That is an incomplete node: Control may be up and Enforce is not. Start the authorized pack and re-check health. Do not satisfy that check by pointing at a public Gate checkout URL. Phantom Engine does not include a second Gate subscription.

## Getting help

Send `security@vantio.ai` the image tag, the product commit you built, kernel version, whether the node is bare metal or Kubernetes, the mode (audit, scoped, node-wide), and whether the workload is enrolled. Omit API keys, Spanner credentials, and prompt contents. The host observe path is not a prompt store. Do not send a procedure you wrote to defeat a control.
