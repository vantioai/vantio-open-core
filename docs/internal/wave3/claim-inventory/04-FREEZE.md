# Freeze

Audience: INTERNAL_RESTRICTED

`status` and `freeze.status` are `FROZEN_INVENTORY`. `freeze.kind` is `INVENTORY_ONLY`.

Frozen on 2026-09-27, America/New_York. The inventory source commit is `03995835c88a4ebcca2ee3b8c1ae7fa490d21653`.

`freeze.content_commit_sha` is the commit that introduced the claim rows, recorded by the following seal commit. The seal commit does not change claim rows, dispositions, or authorization flags. A commit cannot store its own SHA. `FROZEN_INVENTORY` is not that SHA, and it is not a publish.

These flags are false:

- `authorizes_public_rewrite`
- `authorizes_publish`
- `authorizes_announce`
- `authorizes_registry_mutation`
- `authorizes_external_account_edit`
- `authorizes_track_16`
- `authorizes_track_17`
- `authorizes_tracks_18_through_21`
- `public_ship_authorization`
- `clean_host_internal_proof`
- `proved_external`

`publicShipAuthorized` in `internal/wave3-claim-inventory/freeze.cjs` returns false for this ledger, including when those flags are flipped in a copy. `dispositionExecutesNow` returns false for every disposition. The check fails if a flag is anything other than false.

`KEEP` does not publish. `REWRITE` does not edit. `HOLD` does not yank. `EXTERNAL_ACCOUNT_ACTION_REQUIRED` does not log in. `DEFER_TO_T16` does not write Track 16.
