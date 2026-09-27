# Rollback

Audience: INTERNAL_RESTRICTED

```
NOT AUTHORIZED
```

Prep deletes nothing. `scripts/refuse-rollback.mjs` prints `STRANGER_HOST_ROLLBACK_BLOCKED_AWAITING_AUTH` and exits 2. SH-STOP-20 is the scope rule for a later run that already created disposable directories.

## What a later run is allowed to remove

Only paths recorded in that run’s evidence bundle:

| Path | How it was created | Removal |
| --- | --- | --- |
| Disposable `HOME` | Phase 2, empty directory exported as `HOME` | Delete the directory |
| Disposable `RUNNER_TEMP` | Phase 2, empty directory exported as `RUNNER_TEMP`, including `candidates` and `candidates-py` | Delete the directory |
| Disposable git worktree or clone | Phase 2 checkout of the locked SHA | Delete that worktree or clone |
| Disposable virtualenv | Published smoke, only if a later force set `published_install_smoke` to `YES` | Delete the virtualenv |

The account’s original home stays in place. A pre-existing `~/.vantio` on that original home was never the `HOME` of the run. Leave it.

## Package removal when the published smoke ran

The smoke installs into the disposable `HOME` (global npm prefix under that `HOME`) and the disposable virtualenv. Deleting those directories removes the installs. When a command used a prefix outside those directories, stop under SH-STOP-20 and record the path. The manual commands, for a prefix that really was created by the run, are the ones in `docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md`:

```bash
npm uninstall -g @vantio/cli
pip uninstall -y vantio-agent-sdk
```

Run them only against the disposable prefix. Then delete the disposable directories. There is no downgrade migration. Run files under the disposable `HOME` disappear with that directory. Optics does not prune `~/.vantio/runs` by age; this rollback does not invent a prune of someone else’s files.

## What rollback leaves alone

- The locked git SHA’s source
- Package versions
- Gate 8
- Evidence tiers (`tier.txt` stays `UNSET` in any bundle that is kept)
- Phantom Engine enrollment state (the run must not have enrolled a host)
- Registry packages (the run must not have published)
- Any path not written into the bundle before deletion

## Failed run

When a stop fires after disposable directories exist, write the stop id into the bundle, keep `tier.txt` as `UNSET`, then delete only the disposable paths. When a secret marker is found in the bundle, delete the bundle with the disposable `HOME` after the stop id is recorded outside the bundle in the force’s return packet.

## Prep

This force has no disposable host directory to remove. The rollback artifact is this document plus the refuse script.
