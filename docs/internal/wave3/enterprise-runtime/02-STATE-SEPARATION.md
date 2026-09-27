# State separation

Audience: INTERNAL_RESTRICTED

The planes are `OBSERVATION`, `DECISION`, `APPLICATION_ENFORCEMENT`, `HOST_ENFORCEMENT`, `CONTAINMENT`, `REVOCATION`, `EVIDENCE`, and `INDEPENDENT_VERIFICATION`.

| Layer | What a reader is looking at | Where it lands | What stays closed |
| --- | --- | --- | --- |
| Enterprise title | Root founding, recognition, owner set | `DECISION` | `live_customer_authority` false. Vantio stays out of the root set |
| Enterprise delegation | Policy narrow or widen, grant, clock, spawn | `DECISION` | `applied_to_host` false. Spawn does not mint a grant. `ENDED` does not reopen. `host_expanded_authority_cleared` stays `UNSATISFIED` |
| Enterprise approval | Class checks, freeze, revoke, recover, billing | `DECISION`, and `CONTAINMENT` or `REVOCATION` when those records exist | `host_freeze_performed` false. Billing does not move title |
| Host intent | `intent: "enroll"` or `intent: "retire"` | `OBSERVATION` `HOST_INTENT_RECORDED`, execution `NOT_PERFORMED` | `enrolled`, `protected`, and `enforced` stay false. No host attach call |
| Record store | Export, hash, rollback intent, uninstall intent, store availability | `EVIDENCE` | No customer deploy. Uninstall is not performed |
| PE runtime | One `integrate` operation already defined by the integrated runtime | That runtime's own planes | `HOST_ENFORCEMENT` and `APPLICATION_ENFORCEMENT` stay `NOT_APPLIED` or `GAP` |
| Policy citation | Enterprise envelope digest stored as a PE policy version | `DECISION` `RECORDED`, execution `NOT_PERFORMED` | `kernel_maps_changed` false. The digest is not a proof |
| Joint call | Record outcome and PE decision together | `DECISION` `SEPARATED` | The two outcomes remain on `enterprise.quote` and `pe.quote` |

`APPROVED` on an enterprise child means the record rule passed. It does not set `planes.APPLICATION_ENFORCEMENT.applied` or `planes.HOST_ENFORCEMENT.applied`.

Independent verification stays `NOT_INDEPENDENTLY_VERIFIED`.
