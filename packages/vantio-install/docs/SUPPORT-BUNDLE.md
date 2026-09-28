# Support bundle

After apply, the evidence directory can contain `vantio-support-<transaction_id>.tar.gz` and a `.sha256` sidecar.

The archive holds the transaction record, the plan, preflight, health, artifact verification, the redacted event log, the residual report, and a short host summary (architecture, OS, BTF, cgroup, Vantio container names, BPF pin names, and the traffic-control interface).

Private keys, cloud credentials, registry tokens, and raw packet captures are left out. Text that matches those shapes is replaced before it is packed. The archive uses relative names inside the tar.
