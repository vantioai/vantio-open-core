# Enrollment guide

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

**Enrolled** means the workload's cgroup id is in `/sys/fs/bpf/vantio_enrolled_cgroups`. It does not mean traffic is dropped. Drops require enforcement to be on. See [POLICY-GUIDE.md](./POLICY-GUIDE.md).

Unenrolled workloads are outside scoped Control. Their egress is passed. That is the fail-safe, and it is **independently tested** on the lab host.

## Kubernetes annotation

The chart sets `enrollWatch` true by default. The loader lists pods on its own node (`NODE_NAME` from the downward API) and enrolls pods whose annotation or label is:

```yaml
metadata:
  annotations:
    vantio.ai/enroll: "true"
```

Put that on the pod template of the pilot Deployment or DaemonSet, not only on the parent object if the pod spec would drop it.

The watch reconciles about every 30 seconds. It adds pods that opted in and removes ids it previously added when those pods leave. Ids you enrolled with `--enroll-cgroup` are left in place.

Resolution covers the pod cgroup and descendant container scopes for both the cgroupfs and systemd layouts. That resolution was **independently tested** against the local `kind` API server. Your CNI and cgroup driver need a **customer validated** check: after the annotation is on a Running pod, the loader log should show the enroll, and scoped enforcement (when you later enable it) should affect that pod only.

`--enroll-watch` does not attach the optional per-cgroup egress program. For pod networks that forward through a veth, node-interface attribution may not see the pod. Read [KNOWN-LIMITATIONS.md](./KNOWN-LIMITATIONS.md) before you treat an annotation as full egress coverage.

There is no mutating admission webhook in this version. You apply the annotation, or you apply it with your own policy engine. That convenience webhook is **unavailable**.

## One-shot commands

The loader must already be running. On a bare host, from the repository checkout:

```bash
sudo ./target/release/vantio-loader --enroll-cgroup /sys/fs/cgroup/system.slice/my-agent.service
sudo ./target/release/vantio-loader --enroll-cgroup 12345
sudo ./target/release/vantio-loader --enroll-pod-uid <pod-uid>
sudo ./target/release/vantio-loader --unenroll-cgroup 12345
```

`--enroll-pod-uid` enrolls the pod cgroup subtree on the node where you run it. A numeric id and a cgroup path are both accepted. The cgroup v2 id used by enforcement is the cgroup directory inode.

Inside the container image the binary is `/vantio-loader`. `kubectl exec` into the loader pod is an operator action on a privileged-capability pod. Prefer the annotation watch for day-2 enrollment so shell access to that pod stays rare.

## Docker

```bash
sudo ./target/release/vantio-loader --enroll-docker-watch
```

That flag reconciles containers labeled `vantio.pe/watch=true`. The CLI default is off. The Helm values file does not set it. Turning it on is a command change outside the chart defaults and is **not tested** as a Helm value.

`--cgroup-skb-enforce` attaches an additional egress program on Docker and startup-enrolled cgroups so bridge traffic that the node interface does not attribute can still be in scope. The CLI default is off. Kubernetes enroll-watch does not turn it on. Lab notes record the flag as shipped and default-off. A customer cluster has not validated it (**customer validated**: none).

`--startup-enroll-cgroup` enrolls a cgroup chosen when the loader starts. It is a loader flag, not a chart value.

## Process trace identity is not enrollment

`--inject <trace-id> <pid>` puts a process in the trace map so its TLS and syscall events carry your trace id. Child processes inherit that id when the fork hook is working (**independently tested** as strong lab evidence, not as a standalone fork-only fixture).

Injection does not add a cgroup to the enrolled set. A process can be traced and still be unenrolled. An enrolled cgroup can still show no TLS rows if the process never called the probed libraries or the pid identity did not resolve. See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

```bash
sudo ./target/release/vantio-loader --inject "$VANTIO_TRACE_ID" <pid>
```

Use a pid from the host pid namespace. The DaemonSet sets `hostPID: true` for that reason. If children do not appear, inject them explicitly and then inspect calibration (troubleshooting). Do not hand-edit the calibration file.

## Pilot checklist

| Step | Word when it is true |
|---|---|
| Annotation or `--enroll-cgroup` accepted | **configured** |
| Id present in the enrolled map / loader enroll log | **enrolled** |
| Audit events for that workload | **observed** |
| Scoped drop of a non-allowlisted destination, with unenrolled traffic still passing | **enforced**, and only after you turn enforcement on |
| The same result on your cluster | **customer validated** after you record it |

Enroll a pilot namespace first. Do not annotate every workload in the cluster before the pilot drop behaves as this table describes.
