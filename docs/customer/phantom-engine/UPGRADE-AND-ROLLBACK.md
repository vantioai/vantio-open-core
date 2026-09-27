# Upgrade and rollback

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Manual version 1 matches loader `0.1.0`, image tag `0.1.0`, and Helm chart `0.1.1` at product commit `631e435315cd780d83d3259e111893c1d0569bc3`. There is no newer customer image tag in this manual. An upgrade procedure for a later tag will ship with that tag. Until then, "upgrade" means reinstalling this pin on purpose, or moving from a local build to this image.

This document does not merge, publish, or restart any live system.

## Pin

| Item | Pin |
|---|---|
| Image | `ghcr.io/vantioai/vantio-phantom-engine:0.1.0` |
| Chart `version` | `0.1.1` |
| Chart `appVersion` | `0.1.0` |
| Loader crate | `0.1.0` |

Refuse `:latest`. If you build from source, check out the product commit above or a commit Vantio has named for your subscription. Record the commit in your change ticket.

## Before you change a running node

1. Note the Helm revision: `helm history vantio-phantom-engine -n vantio`.
2. Confirm you are in audit mode unless this change is the approved enforcement window.
3. Copy any NDJSON you need. The chart's `/run/vantio` emptyDir is deleted when the pod is recreated. See [BACKUP-AND-RECOVERY.md](./BACKUP-AND-RECOVERY.md).
4. Keep the previous image digest. `imagePullPolicy: Always` will re-pull tag `0.1.0` if the registry moves that tag. Prefer a digest pin in your overlay if the registry allows it.

A customer rollback of this manual's git branch is a documentation rollback. It does not roll back a DaemonSet.

## Re-apply the same pin

```bash
helm upgrade --install vantio-phantom-engine ./deploy/helm \
  --namespace vantio \
  --set image.tag=0.1.0 \
  --set nodeIface=<measured-iface> \
  --set enforce=false \
  --set nodeWideEnforcement=false \
  --set enrollWatch=true \
  --set scheduleOnControlPlane=false \
  --set sovereignMode=local \
  --set outputFile=/run/vantio/events.ndjson \
  --set telemetry.signalShare.enabled=false
```

Use your real interface and your approved `enforce` value. Copying `enforce=false` over a node that was approved for scoped enforce is a policy change. Put the approved value in the command you actually run.

The chart strategy is `RollingUpdate` with `maxUnavailable: 1`. One node can be down at a time. During that restart, that node's probes are not attached until the new pod is Ready. Plan for a gap in **observed** and **enforced** coverage on that node for the restart window.

## Helm rollback

```bash
helm history vantio-phantom-engine -n vantio
helm rollback vantio-phantom-engine <revision> -n vantio
kubectl rollout status daemonset/vantio-phantom-engine -n vantio
```

Rollback restores the chart values of that revision. It does not restore an ephemeral NDJSON file. It does not un-drop packets that were already dropped. It does not rewrite Spanner. Confirm the pod log shows audit or the mode you expect before you close the ticket.

If the previous revision used a different `nodeIface` or turned on node-wide enforcement, read the history before you roll back.

## Bare-metal rollback

Stop the current process (clean interrupt). Start the previous binary you kept on disk, with the same flags you recorded. A clean stop detaches probes. The pinned maps can remain. The new process replaces them on startup; the current loader clears a stale pin when it can. If startup says the pin exists and it does not clear, stop and follow [TROUBLESHOOTING.md](./TROUBLESHOOTING.md). Do not delete pins while you are unsure whether another loader is live.

Keep the previous `target/release/vantio-loader` binary until the new process has printed the event header.

## What rollback does not cover

| Item | Status |
|---|---|
| Managed-cloud upgrade rehearsal | **not tested** |
| Stranger-host rollback of the customer pack | **not tested** |
| Automatic rollback if a drop is too broad | **unavailable**. An operator returns the node to audit. |
| Database migration of the Spanner schema | Live Spanner is **not tested**. Do not invent a migration. |

## Manual revisions

| Manual | Product pin | Notes |
|---|---|---|
| 1 (this draft) | loader 0.1.0, chart 0.1.1, commit `631e435315cd780d83d3259e111893c1d0569bc3` | Draft for review. Not a customer-validated release. |

See [CUSTOMER-RELEASE-NOTES.md](./CUSTOMER-RELEASE-NOTES.md).
