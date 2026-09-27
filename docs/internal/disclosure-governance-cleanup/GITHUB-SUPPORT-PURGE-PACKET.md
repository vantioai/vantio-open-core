# GitHub Support purge packet

Audience: INTERNAL_RESTRICTED

PACKET_STATUS: PREPARED_NOT_SENT

GITHUB_SUPPORT_CONTACTED: false

PUBLIC_PR_66_STATE: CLOSED_UNMERGED

TIP: 60726bef7a7d7da35525a4d832ec63b5f8ca5bad

PULL_REF: refs/pull/66/head

HISTORY_REWRITE_OF_MAIN: NOT_PERFORMED

FILTER_REPO_RUN: false

MERGE_TO_PUBLIC_MAIN: NOT_AUTHORIZED

This force did not submit this packet.

## Why this is a packet and not a ticket

External communication is not authorized. Nobody in this force opened https://support.github.com/ or wrote to GitHub Support. A later Founder action would submit the request below. Until that action, the status stays `PREPARED_NOT_SENT`.

## Request a later sender may file

Repository: `vantioai/vantio-open-core`

Sensitive residue: customer-confidential manual files that were committed on a public draft and were not merged. The file names and content hashes are in `DISCLOSURE-RECORD.json`. Do not attach or paste the file bodies into the ticket.

Scope the sender should ask for:

- Cached views of pull request 66, including the files diff and earlier description revisions.
- The read-only ref `refs/pull/66/head`.
- These eight commits, only if they are not reachable from `main`: `8baead08d12192799ad51bae6f411cd394c444e4`, `dada18b428ec4caadc0f799a7a4c38e2e599032b`, `9bd056f66ed4ea2fe6aff93f62aacbd3b0e06821`, `aca55ef3fc2b01b6e1643ecb752185f492e4be77`, `2f0cb57ebd2a7558d99f5cf73f352d0b497c6f3e`, `bb70c56f5755d0d9cdbd3c165e01f7076704faec`, `949063873365e804a6d2ebddc39d97ea584b3f22`, `60726bef7a7d7da35525a4d832ec63b5f8ca5bad`.
- Server garbage collection of those objects after the pull ref is gone.

Facts the sender can cite, observed `2026-09-27T11:19:38Z`:

- Pull request 66 is closed, draft, and `merged_at` is null. Closed at `2026-09-27T07:33:14Z`.
- Branch `docs/phantom-engine-customer-manual-v1` is not on origin.
- The only advertised ref at the tip is `refs/pull/66/head`.
- Fork count was 0.
- Compare against `89f95099d0dce463307eb75d78e7fcf2ef99feb2` was `diverged`. Merge base `14249ba84ff1f3d5aa8ad7a7366172f29235c76e`. The tip is not an ancestor of `main`.
- A private copy already exists in `vantioai/vantio-pe-customer-docs`. Anonymous access to that repository returned 404. Do not ask GitHub to copy the manual, and do not ask GitHub to make that repository public.

## What the sender must not do

- Do not rewrite `main`. `HISTORY_REWRITE_OF_MAIN` stays `NOT_PERFORMED` unless a separate decision says otherwise.
- Do not run `git filter-repo` against this repository as part of filing the ticket. `FILTER_REPO_RUN` stays false. GitHub's published removal guide assumes a history rewrite and then a Support request for pull refs, because clients cannot push `refs/pull/`. That rewrite is the wrong tool here: the manual is not on `main`, and a mirror push would risk every other ref.
- Do not reopen or merge pull request 66. `MERGE_TO_PUBLIC_MAIN` stays `NOT_AUTHORIZED`.
- Do not include manual text in the ticket.

## Limit, stated before any send

GitHub's published guide says Support will not remove non-sensitive data, and will assist only when Support decides the risk cannot be mitigated by rotating credentials. This residue is document text, not a credential. Rotation does not remove the cached draft. Support may decline. This packet does not record a purge, a ticket number, or a success.
