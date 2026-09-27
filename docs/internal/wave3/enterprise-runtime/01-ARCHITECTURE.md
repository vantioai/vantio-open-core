# Architecture

Audience: INTERNAL_RESTRICTED

The composition is a dispatcher plus a plane joiner. It owns one Enterprise customer-held store and one PE integrated runtime. It does not merge their stores.

`integrate` accepts one operation:

- An Enterprise record operation calls the existing evaluator and projects the result. The decision plane carries the record outcome (`APPROVED`, `REFUSED`, `REJECTED`, `RECORDED`, `QUOTED`). Application enforcement is `NOT_APPLIED` with execution `EVALUATE_ONLY`. Host enforcement is `NOT_APPLIED` with execution `HOST_ATTACHMENT_FALSE`.
- `pe` forwards a request to `pe-integrated-runtime` `integrate`. The PE planes are kept. A PE quote that claims a wire was applied, a kernel map changed, or a host was executed becomes `HONESTY_FAULT`.
- `cite_policy` writes one in-memory PE policy version. The version id is `eg-policy-` plus the enterprise policy version. The digest is SHA-256 of the JSON envelope. `applied_to_host` stays false. The digest is a citation handle. It is not a certification and not a proof system.

`compose` runs the enterprise operation first. The PE operation runs only after that record call returns `ok`. The joined decision is `SEPARATED` when both layers produced a decision. Enforcement rows collapse to `NOT_APPLIED` or `GAP`. They do not collapse to `APPLIED`, and they do not inherit `APPROVED`.

A supplied PE host observation may include the contract fixture field `enrolled`. That field sits inside the PE attempt. This composition does not read it as an enroll command. The joined host plane stays `NOT_APPLIED`, with `kernel_executed` false and `host_attachment` false. An Enterprise enroll intent is a separate record and stores `enrolled` false.

Promotion keys on the request, on `input`, or on the nested PE request return `PROMOTION_REFUSED` before a child runs. Those keys include live customer authority, host attachment, enroll, publish, announce, credential issuance, and frozen-version reopen. An enroll intent is the record field `intent: "enroll"`. A request field `enrolled: true` is a promotion attempt and is refused.

`snapshot` aggregates composition contributions and quotes both child snapshots. Enterprise `host_enrolled`, `host_protected`, and `host_enforced` stay false. The PE snapshot keeps `host_attachment` false. Policy versions copied from the PE runtime keep `applied_to_host` false.

The Enterprise evaluator continues to read its own clock for approval windows. This composition passes `now` through on clock and spawn inputs. It does not replace that evaluator.
