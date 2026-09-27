# Revoke, restart, rollback

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL`

Session state is an object in this process. It is not a loader map and it is not a file.

## 1. Grant

A `HELD` evaluation stores a grant id derived from the session boot id, the workload key, and the policy sha and version. The key is enroll id, pid, start time, port, and protocol. A later non-hold for that key moves the id to the dead set.

`child_process_escape` and `post_accept_denied` also add the key to the revoked set. A later clean bundle stays `revoked` until restart or rollback clears that set. The event log keeps `authority_stopped`.

## 2. Revoke

`revokeActive` moves a live grant to the dead set and revokes its key. Containment stays not required. `cgroup_freeze_applied` stays false. Connection isolation stays `NOT_PRESENT`. Identity-provider revoke stays `NOT_EXECUTED`.

An unknown grant id returns `grant_not_carried` and creates no grant.

## 3. Restart

Restart moves every live grant to the dead set, clears the revoked set, and advances the boot id and epoch.

When `last_known_sha` is present, the session applied sha becomes that digest and the result is `policy_reloaded_not_granted`. The restart itself does not hold. A replay of the old grant id is `grant_not_carried`. A new evaluation holds only when the supplied policy sha equals the reloaded digest and the rest of the hold rule passes. The new grant id differs because the boot id differs.

When `last_known_sha` is absent, the result is `recovery_required`. Later evaluations stay withheld. The session does not treat an empty policy as an open grant.

## 4. Rollback

Rollback uses the same grant drop. With a last-known digest it sets the applied sha to that digest and the version to `rollback:<sha>:<n>`. The result is `rolled_back_not_granted`. The previous version string is not reused.

Until a later bundle presents that new version id and the same sha, evaluation is `stale_policy`. A bundle that does present them may hold as a new grant. `ingress_protected_claim` stays false.

Without a last-known digest, rollback returns `recovery_required`.

## 5. What these operations do not do

They do not thaw a cgroup, reload a kernel map, call a recover script, or mark the workload `protected`. Customer-host recover verbs in the private tree stay unread by this force and uninvoked.
