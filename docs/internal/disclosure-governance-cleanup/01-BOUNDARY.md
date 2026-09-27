# Disclosure and governance cleanup — boundary

Audience: INTERNAL_RESTRICTED

Producer: Cursor cloud agent `bc-07ad7beb-878c-5c79-bc02-25cfbc56e015`, model Grok 4.7.

Producer classification: `DISCLOSURE_GOVERNANCE_CLEANUP_READY_FOR_COUNCIL`

That classification means this branch is ready for a separate council. It is not a council verdict, not a merge, and not a statement that GitHub has purged anything.

## What this force does

- Adds `tests/shared-health-vocabulary/collision.test.cjs` to the frozen stale-name inventory at the live count, with a reviewed reason.
- Keeps that path inside the legacy scan.
- Records the public draft tip, the eight commit SHAs, and the reviewed manual hashes.
- Records the private-channel copy check.
- Writes a GitHub Support purge packet and marks it unsent.

## What this force keeps closed

- Merge of this pull request. Council is a separate reader.
- Merge of pull request #66, reopening it, or copying `docs/customer/phantom-engine/` onto public `main`.
- Contacting GitHub Support, filing the packet, or any other external send.
- `git filter-repo`, a force push, or a rewrite of `main`.
- Customer deploy, announcements, credential changes, and registry publish.
- CLI `0.3.24` and Python `3.1.0` bytes.
- Editing the collision test to delete the prohibition needles.
- Treating an intentional leftover, or an exclude prefix, as the fix for this file.

`docs/customer/phantom-engine/` stays absent from this worktree.
