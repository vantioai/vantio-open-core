# Supported environments

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Read the status words in [CUSTOMER-OVERVIEW.md](./CUSTOMER-OVERVIEW.md) before treating any row as production proof.

## Host requirements

All of the following are required for the loader to attach.

| Check | Required result | Status |
|---|---|---|
| Linux kernel | 5.8 or later (`uname -r`) | Required. Older kernels are **unsupported**. |
| cgroup hierarchy | `stat -fc %T /sys/fs/cgroup` prints `cgroup2fs` | cgroup v2 is required for cgroup-id enrollment. cgroup v1 is **unsupported** for that enrollment. |
| BTF | `/sys/kernel/btf/vmlinux` exists | Required. Hosts without BTF are **unsupported**. |
| BPF filesystem | `/sys/fs/bpf` is mounted | Required. Mount with `sudo mount -t bpf bpf /sys/fs/bpf` when the directory is absent. |
| Privilege | root, or `CAP_BPF` + `CAP_NET_ADMIN` + `CAP_SYS_ADMIN` | Required to load and attach. The chart drops all other capabilities and sets `privileged: false`. A dedicated proof that this capability set is sufficient on GKE, EKS, or AKS is **not tested**. |
| TLS library | `libssl.so.3` or `libgnutls.so.30` (or both) | Best effort. A missing library logs a warning and the loader continues. Tracepoints and the egress classifier still attach. Hosts with neither library have no TLS observe from these probes. |

Non-Linux enforcement hosts are **unsupported**. Windows and macOS are not Phantom Engine nodes. Optics can still observe wrapped processes on those developer machines; that is a different product.

## Node operating systems named for Kubernetes

The Kubernetes notes name Amazon Linux 2 / 2023, Ubuntu 22.04+, and RHEL 8+ as node OS families the manifests are written for. That list is a compatibility target. It is not a per-image certification. Record the actual image and kernel during your architecture review.

Container-optimized images vary. Confirm BTF, cgroup v2, and a mounted bpffs on the node image you will run. Local `kind` required a bpffs mount before the lab DaemonSet became ready. Managed clouds often mount bpffs by default. That vendor default is **not tested** by Vantio on GKE, EKS, or AKS.

## Where lab evidence exists

| Environment | What the lab record covers | Status |
|---|---|---|
| Privileged Linux host in Vantio's lab | Program load, verifier acceptance of the suite then under test, TLS observe with byte counts, scoped drop of an enrolled cgroup, node-wide drop mode, IPv4 CIDR prefix boundary, fork inheritance evidence | **independently tested** |
| Local `kind` cluster on that same lab kernel | Image build, DaemonSet reached Running, RBAC list on pods and nodes, `--enroll-watch` against that API server, maps pinned, TLS probes attached inside the loader pod, TC attached in audit, startup process-identity calibration | **independently tested** |
| GKE, EKS, AKS | No Vantio bake-off is recorded | **not tested** |
| A second organization's Linux host | No stranger-host pass is recorded | **not tested** |
| Any customer environment | No acceptance record is in this manual | **customer validated**: none |

`kind` is local Kubernetes on the lab kernel. It is not a managed-cloud validation. Do not describe the `kind` record as GKE, EKS, or AKS.

The lab verifier record matches the program suite that was loaded in that session. Later path-protection probes and the optional per-cgroup egress program were added after the original "suite accepted" note. Treat a fresh customer kernel as **not tested** until that kernel accepts the build you actually ship.

## Network interfaces

The classifier attaches to one interface named at start.

| Place | Interface the manifests suggest | Status |
|---|---|---|
| Helm `nodeIface` | You set it. Examples used in the chart comments: `eth0`, `ens5` (EKS Nitro), `enp0s3` | **configured** by you. Correctness on your CNI is **customer validated** only after you check it. |
| GKE / AKS comments | `eth0` | Comment only. **not tested** on those clouds. |
| EKS Nitro comments | `ens5` | Comment only. **not tested**. |
| Bare metal comments | `eth0`, `enp0s3`, `ens3` | Comment only. |

One interface per loader process is the current attachment. Multiple interfaces on one node are **unavailable** as a single-process feature.

## Kubernetes scheduling

The chart does not tolerate control-plane taints unless `scheduleOnControlPlane` is true. Leave that false. Enforcement on control-plane nodes is an operational prohibition in this manual, not a kernel interlock you should test in production.

`hostPID: true` and `hostNetwork: true` are set because the loader must see host processes and the node interface. Those settings are **configured** in the manifest. Pod Security Admission acceptance of that shape on a managed cluster is **not tested**.

## Application-path component

The bundled on-prem enforcement component is part of the node purchase. Its listener, when the authorized pack starts it, is `http://127.0.0.1:5001/health` unless `GATE_ONPREM_URL` or `VANTIO_PRO_PORT` overrides it. Health of that process is **configured** by the customer pack. This manual's authoring did not start it.

A multi-tenant Vantio-hosted control plane for Phantom Engine is **unavailable**. Optional dashboard ingest, if you set it, is a separate choice and is not required for the kernel path. See [ARCHITECTURE-BOUNDARIES.md](./ARCHITECTURE-BOUNDARIES.md).

## Versions this manual matches

| Artifact | Version |
|---|---|
| `vantio-loader` | 0.1.0 |
| Container image tag pinned by the chart and the raw manifest | `ghcr.io/vantioai/vantio-phantom-engine:0.1.0` |
| Helm chart | 0.1.1 (`appVersion` 0.1.0) |

Do not deploy a floating `:latest` tag. Pull access to the image is part of authorized distribution. This manual does not publish an image.
