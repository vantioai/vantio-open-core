# Removal and uninstall

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Removal stops Control on that node. It does not uninstall Vantio Optics from developer machines. It does not delete evidence unless you delete those files yourself.

## Kubernetes

Return to audit before uninstall if you want one last quiet window. Then:

```bash
helm uninstall vantio-phantom-engine -n vantio
```

If you applied the raw manifest instead:

```bash
kubectl delete -n vantio -f deploy/kubernetes/daemonset.yaml
```

Confirm no loader pod remains:

```bash
kubectl get pods -n vantio -o wide
```

Helm uninstall removes the chart's DaemonSet, ServiceAccount, and RBAC objects that the chart created. It does not remove namespace `vantio` if other objects remain. It does not remove secrets `vantio-secrets` or `google-cloud-key` unless they were created by the chart, which they were not. Delete secrets when your key-rotation process says to:

```bash
kubectl delete secret vantio-secrets google-cloud-key -n vantio
```

Pinned maps live on the node hostPath `/sys/fs/bpf`. Uninstalling the pod detaches programs on a clean process exit. The pins can remain until node reboot. During a maintenance window, on each node that ran the loader, after you have confirmed no loader process remains:

```bash
sudo rm -f /sys/fs/bpf/vantio_trace_map /sys/fs/bpf/vantio_enrolled_cgroups
```

Do this only when no loader is running. Removing pins under a live loader breaks that process.

`/run/vantio` is an emptyDir and disappears with the pod. If you added your own hostPath for logs, that path is yours to delete.

Remove `vantio.ai/enroll: "true"` from workload templates so a future reinstall does not enroll them by surprise.

## Bare metal

1. Stop the supervisor, or press Ctrl-C in the foreground. The loader logs that it is detaching probes.
2. Confirm the process is gone.
3. Remove pins if you are not restarting immediately:

```bash
sudo rm -f /sys/fs/bpf/vantio_trace_map /sys/fs/bpf/vantio_enrolled_cgroups
```

4. Keep or delete `/var/log/vantio/events.ndjson` under your retention schedule. Uninstall does not delete it.
5. Remove the systemd unit or other supervisor entry so it does not start on boot.
6. Remove the checkout and the binary when you no longer need that version for rollback. Keep the binary until rollback is no longer required ([UPGRADE-AND-ROLLBACK.md](./UPGRADE-AND-ROLLBACK.md)).

Unenroll is unnecessary after the process and the pins are gone. To unenroll while the loader stays up:

```bash
sudo ./target/release/vantio-loader --unenroll-cgroup <id-or-path>
```

## Bundled on-prem component

Stop that process with the customer pack's own stop procedure. The Helm uninstall does not stop it, because the chart did not start it. After it is stopped, `http://127.0.0.1:5001/health` should fail to connect. Application-path enforcement stops with that process. Host Control stops with the loader. Either one can be down while the other is up. An incomplete removal is still a partial control plane.

## Optics and developer machines

`npm uninstall -g @vantio/cli` and removal of a Python virtualenv are Optics actions. They do not remove a Phantom Engine DaemonSet. A developer laptop that only ran Optics never loaded these kernel programs.

## After removal

| Check | Expected |
|---|---|
| Loader process | Absent |
| DaemonSet | Absent |
| New TLS rows | None |
| Existing NDJSON you kept | Still present until you delete it |
| Workload egress | No longer subject to this node's classifier |

A clean detach stops new enforcement. It does not rewrite history already in a file or in Spanner. Spanner rows, if you ever wrote any, follow your GCP retention and are not deleted by `helm uninstall`.
