# Independent planning council

Audience: INTERNAL_RESTRICTED

Status: `PASSED`

Force classification: `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_COUNCIL_PASSED`

Overall verdict: `PASS_WITH_NONBLOCKING_NOTES`

This file replaces the producer stub. The planning producer did not sit this council and did not self-certify a pass.

## Council identity

| Item | Value |
| --- | --- |
| Council agent | `bc-cef881e2-7866-5523-9e29-1116de3490ab` |
| Model | Grok 4.7 |
| Role | `INDEPENDENT_PLANNING_COUNCIL` |
| Seats | All 12 filled by this agent |
| Council URL | https://cursor.com/agents/bc-cef881e2-7866-5523-9e29-1116de3490ab |
| Reviewed tip | `f89f5143ffd70d22d6d9a15b22d191cc9d62e0bd` |
| Branch | `planning/optics-foundation-a8-decomposition` |
| Draft PR | https://github.com/vantioai/vantio-open-core/pull/56 |
| Planning producer | `bc-cdec4aa3-94f6-5b72-b604-d2b7ba3bfbac` |
| Producer classification | `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_READY_FOR_COUNCIL` |
| Reviewed at (UTC) | `2026-09-26T17:40:00Z` |
| Reviewed at (America/New_York) | `2026-09-26T13:40:00-0400` |
| Architecture main | `8a6ef881169c2bf379e04a7d1e8381532ec236b2` |

The producer classification is the handoff this council received. It is not this council’s verdict.

No package and no requirement is `IMPLEMENTED`, `SHIPPED`, or `PROVED`. Evidence tiers, independent-verifier fields, stranger-host fields, and customer-validation fields stay `UNSET` on all 52 requirements. This council assigns no achieved tier.

## Seat verdicts

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Observability product architecture | `PASS_WITH_NONBLOCKING_NOTES` |
| 2 | Privacy engineering | `PASS_WITH_NONBLOCKING_NOTES` |
| 3 | Node instrumentation | `PASS_WITH_NONBLOCKING_NOTES` |
| 4 | Python instrumentation | `PASS_WITH_NONBLOCKING_NOTES` |
| 5 | Storage and migration | `PASS` |
| 6 | Release engineering | `PASS_WITH_NONBLOCKING_NOTES` |
| 7 | Reliability and fail-open | `PASS_WITH_NONBLOCKING_NOTES` |
| 8 | Cross-platform engineering | `PASS_WITH_NONBLOCKING_NOTES` |
| 9 | Developer experience | `PASS` |
| 10 | Scope control | `PASS_WITH_NONBLOCKING_NOTES` |
| 11 | Evidence and verification | `PASS` |
| 12 | Customer supportability | `PASS` |

Worst material seat outcome: `PASS_WITH_NONBLOCKING_NOTES`. No seat returned `NEEDS_REVISION` or `BLOCKED`.

### Seat 1 — Observability product architecture

`PASS_WITH_NONBLOCKING_NOTES`

The 17-package map keeps binding selection, schema persistence, portable proof, legacy copy, query, UI, alerting, and network export on separate release boundaries. Slice 1 is the evidence contract and write-path privacy boundary (`PKG-01`) and sits before any SQLite package. Run-level display `PARTIAL`, lifecycle `PARTIAL`, and query completeness `PARTIAL` stay three fields. `UNSUPPORTED` and `UNAVAILABLE` stay status tokens. OF-01 closes at `PKG-07`. `PKG-03`, `PKG-05`, `PKG-06`, and `PKG-17` own prerequisites or Founder gates and close none of the 52 requirements on their own. All 52 requirements still have one package, one planning status, one rollback unit, and `evidence_tier_now` `UNSET`.

Note N1. Package predecessor arrays name waits that the canonical edge list does not draw: `PKG-03` and `PKG-12` on `PKG-10`, and `PKG-10` and `PKG-12` on `PKG-16`. `PKG-01` on `PKG-07`, `PKG-08`, and `PKG-13` is already enforced by a path through other edges. The edge list remains acyclic, has 25 edges, and hashes to `37bb03cba8107813bba35c812c740b341be7dcbd04bd75e19febc2cdfe774833`. File-backed query is a mode gate on `PKG-07`, which itself waits for `PKG-12`. This note does not reopen package boundaries.

### Seat 2 — Privacy engineering

`PASS_WITH_NONBLOCKING_NOTES`

Slice 1 states the privacy failure behavior in `07-FIRST-SLICE-SPECIFICATION.md` sections 5, 6, and 8. Prohibited values are omitted or the event is dropped. Query and userinfo strip keeps host, explicit port, scheme, and path when the strip succeeds, and omits destination fields when the strip fails. Paths over 512 characters and session ids over 80 UTF-8 bytes are rejected whole. The corpus disposition is removal. A stored mask or a stored digest of a secret is outside the corpus. The application result stays unchanged when validation omits a secret, drops an event, throws, sees malformed UTF-8, or sees an enormous input. That fail-open rule matches A5: the privacy exception and the evidence-root exception still leave the application response alone. Decisions 2, 6, 7, and 11 stay exclusions on `PKG-01`. `optics-demo.invalid` reads as `SIMULATED_DEMO`. A claimed `LOCAL_OBSERVATION` without recognized producer, version, and provenance reads as `LEGACY_UNMARKED`.

Note N2. The corpus table does not give its own rows to SSN, phone, environment blocks, command lines, or the product-telemetry `anonymousId`. A1 section 5 still names those categories. Slice 1 scope item 2 adopts that denylist. The table is the minimum fixture list the future force must implement. It does not waive the rest of the denylist. Section 6’s session-id row is a summary. A1 section 11 still binds: backslash, controls, noncharacters, no trim, and no rewrite of a non-NFC value. An implementation force pins one disposition token per fixture so Node and Python cannot each choose a different legal branch of “omit or drop.”

### Seat 3 — Node instrumentation

`PASS_WITH_NONBLOCKING_NOTES`

`@vantio/cli` is `0.3.24` in `packages/vantio-cli/package.json`. Slice 1 recommendation is option B: a private contract package that `vantio run` 0.3.24 does not load. The future force forbids edits under `packages/vantio-cli/**`. Inventory finding 1.2’s envelope fields are the legacy fixtures, including `est_spend_usd` omitted from contract output while decision 2 is open. The frozen writer that stores unknown `bytes` as `0` stays frozen. The contract normalizer’s target for an unknown length is null `response_bytes`, which matches the A1 catalog. Node SDK `0.2.4` stays out of the contract.

Note N3. Option D uses hand-written `validate.cjs` and `validate.py` against one catalog and one fixture corpus. A shared generator is absent, which avoids generated-file drift and also leaves room for the two validators to disagree on a case the corpus does not pin. S1-G5 is the gate that fails when dispositions differ. That gate is unsatisfied. This planning tip runs no Node tests.

### Seat 4 — Python instrumentation

`PASS_WITH_NONBLOCKING_NOTES`

`vantio-agent-sdk` is `3.1.0` in `packages/vantio-agent-sdk-py/pyproject.toml`. Python 3.0.15 is not the compatibility target. Slice 1 does not import the contract from `vantio._http_observe` and does not change 3.1.0 source behavior. The zero-call envelope (lifecycle `COMPLETE`, application status `NOT_OBSERVED`) is the A3 target and is sequenced on `PKG-02`, because Python 3.1.0 skips the write when the call list is empty. `workflow`, human outcome lines, and the missing pid stay legacy-fixture behavior.

Note N4. The same fixture gate in note N3 applies to `validate.py`. Python can adopt the private package in a later version without a CLI release. A claim that Node and Python match still requires both fixture results together. This planning tip runs no Python tests.

### Seat 5 — Storage and migration

`PASS`

Slice 1 scope excludes SQLite, a binding, a schema, WAL, migrations, legacy import execution, and record conversion. `PKG-05` is an application-owned interface and an in-memory adapter with no `sqlite` dependency. `PKG-06` is `NEEDS_FOUNDER_DECISION` and names no candidate library. `PKG-07` waits for `PKG-05`, `PKG-06`, and `PKG-12`. `PKG-08` waits for `PKG-07` and for `PKG-04` before any preservation claim. Rollback keeps legacy JSON, refuses a newer `user_version`, performs no down-migration, leaves corrupt files in place, and does not replace a corrupt store with an empty file. `privacy_generation` starts at 1 only on a future first allowlist write. Slice 1 does not perform that write. `schema_status` stays `unstable-pre-1.0`. Decision 1 stays `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY` and is not an implementation order. Decision 9 stays unresolved.

### Seat 6 — Release engineering

`PASS_WITH_NONBLOCKING_NOTES`

Release units that can move alone are the unpublished Slice 1 package, a future Python writer, a future CLI version, the proof library after `PKG-01`, a coverage command after self-health, and UI, alerting, and network export after their own Founder decisions. Units that ship together are the selected Node binding with `PKG-07`, `PKG-12` with the release that makes SQLite the default writer, both languages’ fixture results for any parity claim, and `PKG-04` with any `PKG-08` build that claims preservation. `@vantio/cli@0.3.24` is outside every release unit. This PR publishes nothing, tags nothing, and seals nothing. S1-G9 and S1-G10 stay listed and are outside the option B library exit. Gate 8 stays closed on this tip. A8 is not started.

Note N5. `08-FIRST-SLICE-FUTURE-FORCE.md` tells a future implementation agent to report Gate 8 unchanged and also describes A8 as limited to the contract library once that force runs. The reading that matches the architecture is: this planning tip does not open Gate 8; an implementation agent does not edit `docs/architecture/optics-foundation/`; a later Founder issuance of that force is the act that opens Gate 8. The template on this tip is not that issuance.

### Seat 7 — Reliability and fail-open

`PASS_WITH_NONBLOCKING_NOTES`

The contract API returns a result and leaves a supplied application result unchanged. Enforcement block, redact, and cap stay outside the invariant. Numeric `NFR-*` targets stay `NOT_SET`. The future force forbids an unbounded lock and forbids inventing a timeout. `OF-14` stays on `PKG-12` as `BLOCKED_BY_DEPENDENCY`. Slice 1 covers the contract-API subset and records completeness impact for a later envelope. It does not write a `product_health` row and does not implement the query. Default sampling remains `UNSAMPLED` on the later runtime package. Queue-full behavior on `PKG-12` refuses inserts and does not delete history. `SIGKILL` stays absence or `ABANDONED`, and a missing flush is not relabeled `COMPLETE`.

Note N6. The canonical graph draws `PKG-12` → `PKG-07` and does not draw `PKG-12` → `PKG-10` or `PKG-12` → `PKG-16`. Package predecessor arrays do list those waits. File-backed query still waits on `PKG-07`, so it still waits on fail-open. `PKG-16` stays behind Founder decision 3, whose safe default is no alerter and no daemon. A later force for customer query or for alerting keeps `PKG-12` in front of that customer path.

### Seat 8 — Cross-platform engineering

`PASS_WITH_NONBLOCKING_NOTES`

`PKG-01` tests are pure functions over bytes and strings and precede OS-specific store tests. The plan requires Windows, Linux, macOS, and WSL before an external claim and does not execute that matrix here. Offline use is a constraint on every package. Decision 8 leaves Windows ACL details unset. Unix owner-only mode `0600` is the specified intent. A Windows release that claims an ACL waits on that decision. `PKG-06` is not a ship decision until the load matrix exists. Child-process propagation on `PKG-09` waits on OS process semantics and does not wait on SQLite.

Note N7. This council inspected documents and hashes. It ran no Windows, Linux, macOS, WSL, or container product test. That matches a planning review.

### Seat 9 — Developer experience

`PASS`

Option B leaves current readers, current writers, and `optics-cx.cjs` tokens in place. Customers of CLI 0.3.24 see no new public schema. The catalog stays internal while `schema_status` is `unstable-pre-1.0`. Account-free local use stays the default. Prompts and completions stay out of stored records. Deferred command chrome (`OF-07`, `OF-08`, `OF-09`, `OF-10`, `OF-11`, `OF-17`, `OF-18`) stays `DEFERRED` inside `PKG-13`. `vantio doctor` stays uncreated. A missing `evidence_origin` stays `LEGACY_UNMARKED` for the reader.

### Seat 10 — Scope control

`PASS_WITH_NONBLOCKING_NOTES`

The diff from `8a6ef881169c2bf379e04a7d1e8381532ec236b2` to the reviewed tip adds only the 12 files under `docs/planning/optics-foundation-a8/`. Architecture files and the roadmap file are unchanged. Their SHA-256 values match `PLANNING-MANIFEST.json` and the architecture manifest. Slice 1 is `PKG-01` only. The future force allowlist is the private `packages/optics-evidence-contract/` tree named in `08-FIRST-SLICE-FUTURE-FORCE.md`, and that file is marked `NOT AUTHORIZED`, `DRAFT FOR FOUNDER REVIEW`, and `DO NOT EXECUTE`. Founder decisions 2–13 stay unresolved. This council does not authorize Slice 1 and does not open an implementation PR.

Note N8. `IMPLEMENTATION-PACKAGES.json` lists Founder decision 13 on `PKG-15`. The package-map prose lists decisions 6 and 10 for that package and still says the UI charter comes before exemplar drill-down. Trends and indicators are not Slice 1. The exemplar wait is the constraint that matters, and it is already written in the `PKG-15` gates.

### Seat 11 — Evidence and verification

`PASS`

This council recomputed the 13 architecture input hashes against the bytes at the reviewed tip’s parent `8a6ef881169c2bf379e04a7d1e8381532ec236b2`. All matched. Requirement counts are 52, with `ARCHITECTURE_DEFINED` 29, `TARGET_DESIGN` 20, `NEEDS_FOUNDER_DECISION` 3, and `ARCHITECTURE_BLOCKED` 0. All 52 `evidence_tier`, `customer_validation`, `independent_verifier`, `stranger_host`, and `required_closing_tier` values in the architecture matrix are `UNSET`. Planning `evidence_tier_now` and `customer_validation_now` are `UNSET` on all 52. Planning statuses are only `PLANNED` (7), `BLOCKED_BY_DEPENDENCY` (26), `NEEDS_FOUNDER_DECISION` (6), and `DEFERRED` (13). Package statuses are `PLANNED` 1, `BLOCKED_BY_DEPENDENCY` 12, `NEEDS_FOUNDER_DECISION` 4. The producer stub had every seat `PENDING` and did not self-pass. Producer tests do not close a package. S1-G1 through S1-G10 are unsatisfied. S1-G8 is a later council on an implementation tip. The architecture council’s golden-vector recomputation is a document check. It is not `PROVED_EXTERNAL` for an implementation. `OF-52` names `CUSTOMER_VALIDATED` as a future required tier and keeps the achieved tier `UNSET`.

### Seat 12 — Customer supportability

`PASS`

A source rollback leaves recorded JSON readable. Unknown keys are skipped or omitted and do not become `application_status` `SUCCESS` or issue location `NONE`. A missing row does not invent `optics_status` `SUCCESS` for the provider outcome. `LEGACY_UNMARKED` is not reread as `LOCAL_OBSERVATION`. Import, when it later exists, writes `IMPORTED` and does not promote quarantine on rollback. Proof bytes stay stored bytes. Verification hashes those bytes. Store rollback, prune, and compaction do not rewrite an existing proof. A completed prune does not guess deleted rows back into existence. Missing health becomes unknown drop state, which is not query `COMPLETE`. Slice 1’s own rollback is removal of an unwired private package. CLI 0.3.24 and Python 3.1.0 behavior remain, because Slice 1 does not switch them.

## Challenge checklist

| # | Challenge | Result |
| --- | --- | --- |
| 1 | Package boundaries independently releasable? | Pass. The private contract package, a future Python writer, a future CLI version, and the proof library can move on their own. Binding plus schema, fail-open plus the default SQLite writer, both languages’ fixture results for a parity claim, and proof evidence plus a preservation claim ship together. |
| 2 | Dependencies ordered, with evidence and privacy before persistence? | Pass. `PKG-01` precedes conformance, the store interface, binding selection, SQLite persistence, proof, and trends. `PKG-12` precedes default-path `PKG-07`. `PKG-04` precedes preservation claims. `PKG-09` precedes session-aware query. `PKG-10` precedes UI. See note N1 for predecessor-array versus edge-list detail. |
| 3 | Slice 1 is the minimum safe first slice? | Pass. The first slice is the shared persistence-boundary contract: allowlist, denylist, origin, issue location, destination sanitization, session id, trace context, structural redaction, the privacy corpus, and the contract-API fail-open behavior. Health and annotation shapes are validation objects so a secret has no side door. They are not stores. |
| 4 | Slice 1 includes SQLite, a binding, a schema, or a migration? | Pass. Those are excluded in the Slice 1 spec, in `PKG-01` non-scope, and in the future force. `PKG-06` and `PKG-07` are not Slice 1. |
| 5 | CLI `@vantio/cli@0.3.24` freeze and option B? | Pass. Option B is the Slice 1 recommendation. Option A is a later CLI version. Option C is the `PKG-02` cutover. The version in tree is `0.3.24`. |
| 6 | Can Node and Python drift under option D? | Pass with notes N3 and N4. One catalog, one denylist, one corpus, and S1-G5 are the controls. Hand-written validators can still diverge on an unpinned case until that gate exists. The plan does not add a schema generator and does not declare schema v1. |
| 7 | Privacy failure behavior explicit? | Pass with note N2. Reject whole, strip, omit, drop, and fail-open of the application result are separate outcomes. Removal is the secret disposition. |
| 8 | Rollback stays safe? | Pass. Recorded evidence stays readable. Unknown fields and missing origins are not success. Proof bytes are not rewritten into a pass. Corrupt stores are not replaced with an empty file. |
| 9 | Test and evidence strategy sufficient? | Pass. Required tiers are named per package and are `UNSET` now. Producer tests do not close packages. Independent verifier and stranger-host sit in front of external claims. Customer validation is additional and unset. |
| 10 | Implementation gates prevent premature release? | Pass with note N5. S1-G9 and S1-G10 block a customer install claim. Option B does not seal or publish. Gate 8 stays closed on this tip. |
| 11 | Founder decisions 2–13 unresolved? | Pass. The twelve decisions match `08-ARCHITECTURE-DECISION-PACK.md` section 35. Safe defaults are exclusion, no daemon, `NOT_SET` numbers, no encryption, no promote, `annotation_role`, no invented ACL, no binding, `CURRENT` unemitted, hostname prohibited, no exporter, and no UI. Decision 1 is architecture-only. |
| 12 | `08-FIRST-SLICE-FUTURE-FORCE.md` executable, bounded, and not authorized? | Pass. The file carries `NOT AUTHORIZED`, `DRAFT FOR FOUNDER REVIEW`, and `DO NOT EXECUTE`. Its file allowlist is the private contract package. Its non-scope repeats the SQLite, UI, alert, and export exclusions. Placeholders for the starting SHA must be filled by a Founder before any agent runs it. This council does not execute it. |

## Producer claims checked

| Claim | Result |
| --- | --- |
| Planning diff is only `docs/planning/optics-foundation-a8/` | Confirmed. 12 files added. Parent of the reviewed tip is `8a6ef881169c2bf379e04a7d1e8381532ec236b2`. |
| 17 packages; Slice 1 is `PKG-01` `PLANNED` | Confirmed. |
| Status vocabulary is only `PLANNED`, `BLOCKED_BY_DEPENDENCY`, `NEEDS_FOUNDER_DECISION`, `DEFERRED` | Confirmed on packages and requirements. Forbidden achieved-status words are not used as status. |
| P0 architecture hashes and requirement counts match main | Confirmed against the bytes at `8a6ef881`. Roadmap SHA-256 `909f9eb69fac697dff98d42f29de7bf00a9ee808c2c307af220b4a931f4e952a` matches. |
| Gate 8 closed; A8 not started | Confirmed. Architecture gate table still says Gate 8 is closed. This tip adds no product code and opens no implementation PR. |
| Producer did not self-pass in the 09 stub | Confirmed on the reviewed tip. Every seat was `PENDING`. `council_identities` was null. `self_certified_council_pass` was false. |
| `schema_status` stays `unstable-pre-1.0` | Confirmed. `CURRENT` is not emitted. `LEGACY_UNMARKED` is not promoted. |
| Historical “PR #55 stays draft” sentences | Left in the architecture files. This council does not edit those files and does not treat those sentences as a second architecture. |
| No credentials, registries, tags, seals, website edits, or announcements | Confirmed for this diff. |

## Blocking findings

None.

## Nonblocking notes

| ID | Seats | Note |
| --- | --- | --- |
| N1 | 1, 7 | Predecessor arrays are stricter than the 25 canonical edges for `PKG-10` and `PKG-16`. The SQLite default path still waits for `PKG-01` and `PKG-12`. |
| N2 | 2, 4 | Corpus table is a minimum. A1 section 5 categories without their own rows, and the full A1 section 11 session rules, stay in force through the denylist and scope item 2. Fixtures pin one disposition. |
| N3 | 3, 4 | Option D controls Node/Python drift with shared fixtures, not with a generator. S1-G5 is unsatisfied. |
| N4 | 3, 4 | Same control as N3, called out for the Python validator and for the rule that a parity claim needs both languages. |
| N5 | 6, 10 | A future Founder force opens Gate 8 by being issued. The template on this tip does not. The implementation agent does not edit the architecture gate file. |
| N6 | 7 | Customer query and alerting, when a later force exists, keep fail-open in front of the customer path. |
| N7 | 8 | No OS matrix was executed in this review. |
| N8 | 10 | `PKG-15` decision 13 is in the JSON list and in the exemplar gate. The markdown unresolved-decision sentence names 6 and 10. |

This council does not edit the package map, the edge list, or the Slice 1 spec to absorb these notes.

## Attestations

| Stop | Result |
| --- | --- |
| Reviewed tip | `f89f5143ffd70d22d6d9a15b22d191cc9d62e0bd` |
| Packages `IMPLEMENTED`, `SHIPPED`, or `PROVED` | None |
| Requirements achieved | None. All evidence tiers `UNSET` |
| Slice 1 SQLite, binding, schema, migration | Excluded |
| Founder decisions 2–13 | Unresolved |
| Decision 1 | Architecture only |
| Gate 8 | Closed |
| A8 | Not started |
| Product code in this council commit | None. Council files under `docs/planning/optics-foundation-a8/` only |
| `08-FIRST-SLICE-FUTURE-FORCE.md` | `NOT AUTHORIZED` / `DRAFT FOR FOUNDER REVIEW` / `DO NOT EXECUTE` |
| PR #56 | Remains draft. Not merged. Not marked ready |
| Slice 1 implementation | Not started |

## Founder choice after this council

The plan is accepted for Founder review. The next choice is one of these:

- Authorize a Slice 1 implementation force for `PKG-01` only, using `08-FIRST-SLICE-FUTURE-FORCE.md` after filling the starting SHA, with option B, with SQLite excluded.
- Revise Slice 1 scope before that authorization.

That choice is not an authorization of SQLite, a binding, a schema, a migration, UI, alerting, OTLP, or the rest of A8.
