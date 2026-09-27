# Incident response

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

This is the customer operator procedure when Phantom Engine is involved in an incident. It is not Vantio's internal on-call runbook. It does not authorize taking down a cluster, and it does not include exploit steps.

Two incident classes are covered: the product is harming production traffic, and you need to preserve evidence of agent activity.

## If enforcement is harming production

1. Say so in the incident channel: scoped or node-wide, which node, which time.
2. Return that node to audit. On Helm, upgrade with `enforce=false` and `nodeWideEnforcement=false`, keeping the same `nodeIface` and image tag. On bare metal, restart the loader without `--enforce` and without `--node-wide-enforcement`.
3. Confirm the startup log says audit (log only) before you declare the node quiet.
4. Do not "fix" a broad drop by switching to node-wide mode. Node-wide is broader.
5. Do not enable `--kill-on-enforce` during an incident. Process termination is off by default and is not an incident tool in this manual.
6. If the loader itself is unhealthy and you cannot reach a quiet audit mode, stop the DaemonSet or the host process. A clean stop detaches probes. Workloads then run without this node's Control until you start again in audit.

Unenroll a single pilot if only that workload should leave enforcement and the rest of the node should stay as approved:

```bash
sudo ./target/release/vantio-loader --unenroll-cgroup <id-or-path>
```

Removing the annotation stops enroll-watch from putting that pod back on the next reconcile. Do both when the watch is on.

Packets already dropped stay dropped. Rollback does not replay them.

## If you need evidence

1. Leave the loader running in audit if it is safe to do so. Stopping it ends new rows.
2. Copy loader logs immediately (`kubectl logs` or the journal) to a ticket attachment stored under your incident retention.
3. If bare-metal NDJSON exists, copy the file and record a checksum. Do not truncate it as part of collection.
4. Record image tag, Helm revision, mode, node name, kernel (`uname -r`), and which workloads were enrolled.
5. Do not email API keys, Spanner JSON, or prompt bodies. The host observe path is not your prompt archive.
6. Optional cloud ingest, if it was on, is a second copy only for the events that ingest accepted. It is not a substitute for the node log if you disabled ingest.

Ephemeral `/run/vantio/events.ndjson` vanishes on restart. Copy it before any upgrade or uninstall.

## If the loader stopped unexpectedly

1. Read the last logs and pod events.
2. Do not assume enforcement remained in force. A clean exit detaches probes. A crash is an unknown until you see a new startup line. Check whether the process is running.
3. Start in audit, confirm the event header, then re-apply only the enforcement change control had already approved.
4. Re-check enroll-watch. A reboot clears pins. Annotations on pods are still **configured**; the watch must run again before they are **enrolled**.

## If you suspect a skipped application path

A host row with no matching application row is the Rogue Reconciliation case. Preserve both the host log and the application log for that trace id and time window. Label the gap `BYPASS_INDICATOR` only when your comparison actually shows host evidence and no application record. Do not invent the label. A standing reconciler is **unavailable**, so the comparison may be a human review of the two files.

This manual does not include a way to force that gap. If the incident requires a vendor demonstration, contact `security@vantio.ai` and keep the request inside the incident channel.

## Communications

| Audience | Tell them |
|---|---|
| Your operations channel | Mode, node, whether you returned to audit, where the log copy is |
| Your security channel | Trace ids, enrolled workloads, whether rows are **observed** or **enforced** |
| Vantio `security@vantio.ai` | Image tag, commit if you built from source, kernel, mode, and the symptom. No credentials. |

Customer environment results you record during the incident can become **customer validated** for that specific check. Write down what you saw. A lab row in this manual does not become customer validation because an incident occurred.

## After the incident

File a short record: start time, audit restored time, evidence location, and whether any pin or annotation was left in a state you do not want on the next boot. Then follow [OPERATIONS-RUNBOOK.md](./OPERATIONS-RUNBOOK.md) before you enable scoped enforce again.
