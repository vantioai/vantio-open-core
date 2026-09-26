# Independent planning council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

This file is a producer stub. The planning producer must not self-certify PASS. No seat below has a verdict. Council identities are unset until a separate Founder-authorized council agent reviews the exact planning tip and replaces this stub.

Planning producer: Cursor cloud agent `bc-cdec4aa3-94f6-5b72-b604-d2b7ba3bfbac`, model Grok 4.7. That identity is not a council identity.

Producer classification handed to council: `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_READY_FOR_COUNCIL`

That classification is not a council verdict. Overall force classifications `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_COUNCIL_PASSED`, `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_NEEDS_REVISION`, and `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_BLOCKED` are assigned only by the independent council.

Reviewed tip: unset. The council fills the tip it actually read.

## Seats required

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Observability product architecture | PENDING |
| 2 | Privacy engineering | PENDING |
| 3 | Node instrumentation | PENDING |
| 4 | Python instrumentation | PENDING |
| 5 | Storage and migration | PENDING |
| 6 | Release engineering | PENDING |
| 7 | Reliability and fail-open | PENDING |
| 8 | Cross-platform engineering | PENDING |
| 9 | Developer experience | PENDING |
| 10 | Scope control | PENDING |
| 11 | Evidence and verification | PENDING |
| 12 | Customer supportability | PENDING |

## Challenge checklist

The council challenges the planning tip against each item. The producer does not check these boxes.

1. Starting commit is `8a6ef881169c2bf379e04a7d1e8381532ec236b2`, and the planning branch contains only `docs/planning/optics-foundation-a8/`.
2. All 13 architecture files are unchanged. Their hashes match `PLANNING-MANIFEST.json` and the architecture manifest’s `files_sha256`.
3. Requirement counts remain 52, with `ARCHITECTURE_DEFINED` 29, `TARGET_DESIGN` 20, `NEEDS_FOUNDER_DECISION` 3, `ARCHITECTURE_BLOCKED` 0.
4. Every architecture evidence tier and every customer-validation field remains `UNSET`.
5. Gate 8 remains closed. A8 is not started. No implementation PR is opened.
6. `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY` remains architecture only. No binding is selected. No database, schema, or migration is created.
7. No package or requirement uses `IMPLEMENTED`, `IN_PROGRESS`, `SHIPPED`, `PROVED`, or `CUSTOMER_VALIDATED`.
8. Founder decisions 2–13 stay unresolved. Decision 1 is not treated as an implementation order.
9. Slice 1 is the evidence contract and write-path privacy boundary, and it is sequenced before any SQLite package.
10. Slice 1 exclusions hold: no WAL, no stable schema, no UI, no daemon, no OTLP, no alerting, no numeric targets, no secret hashing as a default, no live CLI or Python 3.1.0 wire-up.
11. The dependency graph enforces evidence and privacy before shared conformance and before operational persistence; portable proof before evidence-preserving migration claims; store interface before binding selection; binding before SQLite persistence; SQLite before legacy migration; correlation before session-aware querying; query before UI; self-health before diagnostic commands; fail-open before storage as the default path; evidence origin and completeness before trends and alerts; query and security before UI; UI charter before UI; indicators before customer-configured objectives; alerting decision before alerts; export privacy before OTLP or SIEM.
12. The graph assigns no dates and no durations.
13. Cross-package recommendation is option D. It does not add a schema generator and does not declare schema v1.
14. Slice 1 compatibility recommendation is option B. Option A and option C are sequenced later and do not reopen CLI 0.3.24 inside Slice 1.
15. Rollback states that a source rollback keeps evidence readable and does not reinterpret unknown fields as success.
16. The privacy corpus covers every canary named in the Slice 1 spec and states a disposition. Removal is used where removal is safer than hashing.
17. All 52 requirements map to a package, a planning status, a rollback unit, and an evidence tier that is still `UNSET` as achieved.
18. Python 3.0.15 is not the compatibility target. Python 3.1.0 source behavior is unchanged by this PR. Node SDK 0.2.4 is unchanged.
19. `08-FIRST-SLICE-FUTURE-FORCE.md` is marked `NOT AUTHORIZED`, `DRAFT FOR FOUNDER REVIEW`, and `DO NOT EXECUTE`.
20. This council file was `PENDING_INDEPENDENT_COUNCIL` when the producer opened the draft PR. The producer did not fill seat verdicts.
21. `schema_status` remains `unstable-pre-1.0`. Freshness `CURRENT` is not emitted. `LEGACY_UNMARKED` is not promoted.
22. Historical sentences in the architecture pack that say PR #55 stays draft are left intact and are not used as a reason to ignore the merge commit.
23. No product code, credentials, registries, tags, seals, website edits, or announcements are in the planning diff.

## Council result

Verdict: unset.

Force classification: unset.

Blocked items: unset.

The council replaces this stub in a later commit on the planning branch, or the Founder directs a different record location. This producer will not perform that replacement.
