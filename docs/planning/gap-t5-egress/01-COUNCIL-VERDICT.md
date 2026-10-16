# T5 design council verdict

Audience: INTERNAL_RESTRICTED

Track: T5

Reviewed at: 2026-10-16T16:03:22Z

Reviewer family: Claude Opus (model slug `claude-opus-5-5-high`)

Reviewer agent: `bc-548bf82b-3c57-5c89-b685-8f3e7842604f`

Producer family: Grok. The producer did not sit this verdict.

This verdict covers the design packet only. It is not a review of implementation commits. Those do not exist yet. A later review from a different model family has to read the final head after the code lands. A review of this design does not satisfy that later requirement.

## Scope of review

| File | Role |
| --- | --- |
| `docs/planning/gap-t5-egress/00-DESIGN.md` | Design |
| `docs/planning/gap-t5-egress/02-RISK-REGISTER.md` | Risks |

Passes:

1. First read. Verdict `NEEDS_REVISION`. Seven blocking items: loopback aliases, symlink root race and errno map, observe-mode transmit, policy schema bounds, GET normalization, split-label tunnels, and a PID-namespace check the `unshare` line did not create.
2. Second read, after the design revision. Verdict `ACCEPT_WITH_NOTES`. All ten checks passed. One required text fix: risk row R-T5-4 still said observe mode sends a hidden method or name.
3. Third read, after that row and the notes were folded into the packet. Verdict `ACCEPT_WITH_NOTES`. Blocking: none. Citation from the current R-T5-4 row: "Section 6 drops them in observe and in enforce."

## Verdict

`ACCEPT_WITH_NOTES`

Code may start. The notes below are binding on the implementation. They do not require another design edit.

## Checks on the accepted text

| Check | Result |
| --- | --- |
| Nine cases are in the threat model and each has a drill id | PASS |
| Fail-closed versus fail-open is a transmit table, and no row fails open | PASS |
| eBPF verifier limits are concrete, including no floating point for Shannon | PASS |
| Observe, then Enforce, then Control. Control is not implemented | PASS |
| Evidence excludes conversation content | PASS |
| Lab integration is a later step. Workflows are not authorized | PASS |
| Labels are Lab-only or Roadmap. Cluster is not claimed | PASS |
| Dependencies are real. Rollback before merge is deleting the branch | PASS |
| Hostname suffix rule matches `hostListed`, and the deltas are named | PASS |
| Empty lists, malformed policy, missing enrollment, hidden method, missing `openat2`, volume bound, root-open race | PASS |

## Notes the implementation follows

1. `address_not_canonical` is listed under "Allow and scope" in section 5 and also placed with `policy_malformed` in section 6. Section 3 says it is an evaluation failure. The code returns `DENY`, `transmit` false in both modes, and `evaluation_failure` true. A unit test pins that result. The design file is not edited again for this filing.
2. `link_local_not_allowed` is a classified violation, so observe mode transmits. The drill namespace has no route to `169.254.169.254`. R-T5-19 is the hook for any later wiring that would.
3. The symlink root test asserts the token `symlink_root`, not a particular errno. Every errno from the root open maps to that token.
4. Section 6 is a table-driven unit test for both modes, including `transmit`, `enforce_outcome`, and `evaluation_failure`. The two `dns_query_volume` paths (over the cap, and a gate-update failure) differ in `evaluation_failure`.
5. The design header still says "council pass 2". This file is the pass record. Pass 3 is the accepting read.

## What this verdict does not do

- It does not apply a founder-approved label.
- It does not authorize a merge, a cloud lab, an eBPF load, a pin change, or a workflow edit.
- It does not mark any drill Verified. The local proof, once it exits 0, is Lab-only.
