# Backup and recovery

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

You own retention. Phantom Engine does not ship a backup scheduler. Nothing in this version is a WORM guarantee.

## What exists to keep

| Artifact | Where | Durable? | Status |
|---|---|---|---|
| Loader log | stdout, `kubectl logs`, or your service journal | Only if your platform retains logs | **configured** by your cluster or journald. Retention is yours. |
| NDJSON from `--output-file` on bare metal | Path you choose, for example `/var/log/vantio/events.ndjson` | Yes, if the disk is backed up | Local NDJSON content has lab evidence (**independently tested**). Your backup job is **customer validated** only after you restore it. |
| NDJSON at Helm `outputFile=/run/vantio/events.ndjson` | Container `emptyDir` | No. Pod recreate deletes it. | **configured** as a scratch file. Not a backup. |
| Heartbeat `/run/vantio/heartbeat` | Same emptyDir | No | Liveness only. Not evidence of agent traffic. |
| Process-identity calibration file | `/run/vantio/pid_offset` in the chart, or `/var/run/vantio_pid_offset` on a host that can write there | No | Runtime aid. Do not back it up and do not edit it. Deleting it causes the next start to calibrate again. |
| Pinned BPF maps | `/sys/fs/bpf/vantio_trace_map`, `/sys/fs/bpf/vantio_enrolled_cgroups` | Until reboot or `rm` of the pin | Operational state, not a ledger. |
| Spanner `TrueTimeLedger` | Your GCP database, if you configure it | Designed to be the durable store | Writer and schema alignment are **independently tested** as code. Live insert is **not tested**. |
| On-prem policy store | Whatever the customer pack uses | Your backup of that component | Outside this chart. |

Append-oriented NDJSON can be copied while the loader is running. Copy a stable snapshot (copy then checksum). The file is not locked as an immutable ledger. A later process with write access to that path can append or truncate it. Protect the directory with normal file permissions.

## What to back up before maintenance

1. Helm values you actually applied, including `nodeIface`, `enforce`, and `image.tag`.
2. The trace-id secret material stored in your secret manager (not in this manual).
3. A copy of bare-metal NDJSON, if that file is your evidence.
4. The list of annotated workloads (`kubectl get pods -A -o json` filtered for `vantio.ai/enroll`, or your Git source of the annotation).
5. The product commit or image digest.

`kubectl logs` retention follows your cluster logging product. If you have no log shipper, the shipped chart does not give you a durable ledger. Add a volume only through a change you have reviewed. The shipped chart does not mount a host path for NDJSON. A hostPath you add yourself is **not tested** as part of chart 0.1.1.

## Recovery

| Loss | Recovery |
|---|---|
| Loader pod crash | The DaemonSet restarts it. Liveness also restarts a hung process whose heartbeat is older than 60 seconds. Enrollment watch repopulates ids it manages. Manual `--enroll-cgroup` ids live in the pinned map until reboot or unenroll; a node reboot clears pinned maps. Re-apply manual enrollments after a reboot. |
| Node reboot | bpffs pins are gone. Start the loader again. Re-enroll anything that was manual. Annotations are still on the pods; enroll-watch will reconcile. |
| Accidental `helm uninstall` | Re-run the install in [DEPLOYMENT-GUIDE.md](./DEPLOYMENT-GUIDE.md). Evidence that lived only on `/run/vantio` is gone. |
| Bad enforcement window | Return to audit with [INCIDENT-RESPONSE.md](./INCIDENT-RESPONSE.md). Rollback of the chart does not undo drops that already happened. |
| Spanner project unavailable | Keep using logs or NDJSON. Do not claim a WORM copy you cannot query. |
| Lost calibration file | Ignore it. The next loader start measures process identity again. Install `curl` so that measurement can run. |

## Restore test

A backup you have not restored is **configured**, not **customer validated**. Once per retention period, restore one NDJSON file to a non-production path and confirm the rows include the trace ids you expect. Vantio has no record of performing that restore in a customer account.

## Air gap

The loader can run with no Spanner and no cloud ingest. An image-mirror procedure for an air-gapped registry is **unavailable** in this manual. Your registry team mirrors `ghcr.io/vantioai/vantio-phantom-engine:0.1.0` under your own process, then you set `image.repository` and `image.tag` to that mirror. That mirror step is yours to validate.
