# Version procedure

Audience: INTERNAL_RESTRICTED

Current package version: `0.2.0-internal`

It supersedes `0.1.0-internal`. Catalog rows whose capability version was the package version now use `0.2.0-internal` and set `supersedes` to `0.1.0-internal`. `review_date` is `2026-09-28` on every row. Product pins stay on their own capability versions with `supersedes` null: CLI `0.3.24`, npm SDK `0.2.4`, Python `3.1.0`.

Soft-dependency currency for this rebind is `b0bcbdeb01ccb84a58a3aa6aacd0c05f94b22450`. The prior currency `a80fd4288df4983bf294aa219511ef60d86fa87c` remains the 0.1.0-internal citation point. Refreshing currency does not raise a proof class.

The 0.2.0-internal packet cites the Stage B accepted close and the C5 integration record. It rereads the merged ingress, egress, and Unit E tracks. Those tracks still do not count toward satisfaction. Enforcement efficacy stays `NOT_PROVED`. O7 is cited as `INTERNAL_CLEAN_HOST_INITIALIZATION_PROOF` for an observe record with enforcement not enabled. That citation does not authorize the O7 store. Enterprise stays `NO_LIVE_CUSTOMER_AUTHORITY`.

Council acceptance of this packet is a separate force. `council_status` stays `PENDING_INDEPENDENT_COUNCIL`. This package does not sit that council.

| Version | When it is allowed |
| --- | --- |
| `0.2.0-internal` | This rebind. Wave 2 merges are cited, and the Stage B close is cited. Citing those facts does not grant satisfaction and does not authorize the next rung. |
| `0.3.0` | After a clean-host qualification that this partial Stage B proof does not supply. `BLOCKED_INFRA` and an unset evidence tier do not qualify. `PARTIAL_INTERNAL_CLEAN_HOST_PROOF` does not qualify. |
| `0.4.0` | After stranger-host execution is authorized and completed. Readiness does not qualify. |
| `1.0.0-customer-candidate` | Only after an external assessment, a disclosure review, and a separate release council. |

A version bump does not raise a proof class. A prior pass does not survive a stale row. Mapping commit stays `NOT_SELF_HASHED` until a release process records the tip outside the hashed body.

Open gates from the C5 record stay visible: Council F billing and C8, Council I recordings, the live RBK-004 re-proof, and Class B.
