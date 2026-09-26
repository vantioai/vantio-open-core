# Independent council report

Status: `NEEDS_REVISION`

Audience: INTERNAL_RESTRICTED

Council: Cursor cloud agent `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2`, model Grok 4.7. This agent filled all 12 seats. It is not the architecture producer. Producer tip reviewed: `8aef23cd6886139d3b8f7de52cfb28c0972628cd`. Draft PR: https://github.com/vantioai/vantio-open-core/pull/55. That tip matched the PR head at review. Starting main `d6b74d41808a43f251d6de46e1313625a025d16d` matches the pack.

Reviewed at: `2026-09-26T15:27:56Z`.

Force classification: `OPTICS_FOUNDATION_ARCHITECTURE_NEEDS_REVISION`

The producer classification `OPTICS_FOUNDATION_A6_READY_FOR_COUNCIL` stands as the producer’s handoff. It is not a council pass. Gate 8 stays closed. A8 is not started.

The producer stub listed twelve different seat scopes and left them `UNFILLED`. This report replaces that stub with the twelve seats required by the council Force.

## Overall verdict

`NEEDS_REVISION`

The pack is reviewable. It keeps enforcement, a daemon, OTLP, a stable schema, external proof, and customer validation out of the foundation. Option C is a coherent store recommendation and stays unratified. The contracts that would be implemented next contradict each other on failing-layer assignment, on when evidence may look complete, and on what a corrupt store is allowed to do. Those are specification defects. They are not new founder product choices.

## Seats

| Seat | Scope | Identity | Verdict |
| --- | --- | --- | --- |
| 1 | Observability architecture | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `NEEDS_REVISION` |
| 2 | Data storage and migration | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `NEEDS_REVISION` |
| 3 | Privacy and data minimization | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `NEEDS_REVISION` |
| 4 | Application reliability and fail-open behavior | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `PASS_WITH_NONBLOCKING_NOTES` |
| 5 | Distributed tracing and correlation | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `NEEDS_REVISION` |
| 6 | Query and cardinality | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `NEEDS_REVISION` |
| 7 | Local security | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `NEEDS_REVISION` |
| 8 | Cross-platform engineering | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `PASS_WITH_NONBLOCKING_NOTES` |
| 9 | Customer support and diagnostics | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `NEEDS_REVISION` |
| 10 | Evidence and independent verification | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `NEEDS_REVISION` |
| 11 | Developer experience | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `PASS_WITH_NONBLOCKING_NOTES` |
| 12 | Scope control and product positioning | `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2` | `PASS_WITH_NONBLOCKING_NOTES` |

## Seat rationale

### 1. Observability architecture — `NEEDS_REVISION`

The class split (observed, derived, annotation, demo, import, health, telemetry, proof, fixture) is the right model, and missing origin stays `LEGACY_UNMARKED`. The failing-layer model is not implementable as written.

`02-EVIDENCE-AND-PRIVACY-CONTRACT.md` section 3 maps HTTP 400–599 on a catalog-confident call to `PROVIDER_INTERACTION`, then says `CUSTOMER_APPLICATION` is wrong for a provider 4xx, then says to use `UNKNOWN` when catalog confidence is absent. A 400, 401, 403, 404, or 422 on a catalog host is often the caller’s request or credential, and the mapping still names the provider. The same section maps every `failure_kind` `wrapped` with no HTTP status to `CUSTOMER_APPLICATION`, and it maps disk pressure to “`OPTICS` or `ENVIRONMENT`” without a rule for which one. The enum has no value for a call that has no failing layer. Section 10’s illustration sets `http_status` 200, `application_status` `SUCCESS`, and `issue_location` `PROVIDER_INTERACTION` on the same event.

`06-SELF-OBSERVABILITY-AND-RELIABILITY.md` section 2 drops the catalog-confidence clause and says provider HTTP 4xx/5xx is `PROVIDER_INTERACTION` or `UNKNOWN`. An implementer cannot satisfy both pages.

`optics_status` is incorporated by reference to `packages/vantio-cli/bin/optics-cx.cjs`, where `opticsStatusForRecordedCall` returns `SUCCESS` for any stored call. The revision has to say that beside the field. Otherwise a support reading treats Optics `SUCCESS` as provider health.

### 2. Data storage and migration — `NEEDS_REVISION`

This seat does not reject option C. Embedded SQLite as a mutable index, with JSON proof kept separate, matches the scaling gap in the inventory and avoids a daemon. Founder ratification stays open. A and B remain legacy input and export shapes. D and E stay rejected for a second native engine and for a daemon.

The integrity rule is two rules. `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` section 3 step 3 says a corrupt file stops, the bytes stay, and nothing is renamed over it. `07-THREAT-MODEL.md` case T10 says newer or corrupt schemas “stay refused or bounded read-only.” Bounded read-only on a torn file is the outcome T10 says it is preventing: opening damaged bytes as a database the caller can use.

Disclosure is circular. A2 tells a failed open to record product-health in a side diagnostic. A5 defines product-health as rows, then says a failed diagnostic write becomes one in-memory counter and stops. That counter dies with the process. No command contract requires the next reader to print integrity failure, migration state, or rollback refusal from a channel outside the failed database file.

A3’s `user_version` and `BEGIN IMMEDIATE` mechanics are written as the schema contract while option C is still unratified. The revision labels those mechanics conditional on ratification. It does not need a new store option.

### 3. Privacy and data minimization — `NEEDS_REVISION`

The deny-by-default catalog, the prohibited list (bodies, headers, query strings, exception text, baggage, telemetry ids), reject-not-truncate for overlong paths, and “demo and import are not customer activity” are the right privacy posture. Current source is still `PARTIAL`. This seat does not convert that into a pass.

Three target holes remain:

- `session_id` is an allowlisted string, max 80, with no alphabet. A4 calls an incoming value “validated” and does not define the check. Trace ids and span ids have size and hex rules and are dropped when they fail. Session id does not. The general secret-pattern sentence does not define acceptance.
- The legacy adapter in A3 says to map known allowlisted keys, and `evidence_origin` is an allowlisted key. The next sentence says a non-demo legacy file is `LEGACY_UNMARKED`. A file that supplies `evidence_origin: LOCAL_OBSERVATION` can be implemented either way. Masquerade depends on which sentence wins.
- The annotation allowlist row names `evidence_origin`, says the constant `DERIVED_DIAGNOSTIC` is wrong, and says not to set an observation origin. That row is not a field spec. The seventh-origin question stays a founder decision. The row still has to be rewritten so a writer can see the allowed keys.

### 4. Application reliability and fail-open behavior — `PASS_WITH_NONBLOCKING_NOTES`

A5’s observation-path rule is explicit: an Optics failure must not fail the call, hang it, or change response bytes or status, and it must not invent a successful observation or a successful application outcome. Privacy drop and evidence-root refusal are named, and both still leave the application response alone. The request-path timeout is `NOT_SET`, and the pack forbids an unbounded lock on that path until a number exists. That is the correct way to leave the number open.

The same source files can block, redact, or cap when they are not in free mode. The pack places those branches outside Optics. Fail-open is a property of the observation contract, and the inventory already shows it is not a property of every branch in `interceptor.cjs`.

### 5. Distributed tracing and correlation — `NEEDS_REVISION`

Retries, async work, redirects, and proxies are specified in a way that stays honest. A retry is a new `event_id`. `duplicate_of` is allowed only when the writer knows the attempt is the same one, and no millisecond window is invented while that window is `NOT_SET`. Async work shares `run_id` and must keep `sequence` monotonic. A redirect is a new event and does not rewrite the first destination. A proxy is the peer the client connected to, and origin-behind-proxy is not inferred. Timestamp order is not causality.

Child processes are not specified to the same standard. A4 says they inherit correlation only when they inherit instrumentation and `VANTIO_TRACE_ID`. Today `packages/vantio-cli/bin/vantio.js` lines 339–342 put that variable on the child, and the value is the process-run id the new model renames to `run_id`. The contract never says whether the child mints its own `run_id`, copies the parent `run_id`, or stores the inherited value in `trace_id`. `event_id` is (`producer`, `run_id`, `sequence`). Two processes that share a `run_id` collide. A child that stores the parent run id in `trace_id` merges the two namespaces the model just split.

### 6. Query and cardinality — `NEEDS_REVISION`

Cardinality and the structural query bounds are in good shape. Predicates are an indexed allowlist. Metric labels are low-cardinality enums plus `provider_id`. Paths, run ids, trace ids, session ids, event ids, and raw hosts are excluded from metric labels. Limit is 1–500 with default 100. Caller regular expressions and arbitrary SQL are rejected. A predicate that cannot use an allowlisted index is refused. Sampling stays `UNSAMPLED`. Overflow increments one drop count and does not delete history to free space. Numeric cost stays `NOT_SET`.

The read model can still hide incompleteness. A4 section 5.2 defines answer completeness as `COMPLETE`, `PARTIAL`, `TRUNCATED_BY_LIMIT`, or `UNAVAILABLE`, and it never defines `PARTIAL`. `COMPLETE` is the natural reading when the page is not truncated. `dropped_count`, run `lifecycle`, and `integrity_state` are not response fields. Default queries return `LOCAL_OBSERVATION` only, so the product-health row that holds the drop count is outside the default answer. A caller can observe a complete page of a partial capture.

### 7. Local security — `NEEDS_REVISION`

T1–T15 have the required fields. Residual risk is `UNSET`. Controls are `NOT_STARTED` except where the inventory already records a narrower current behavior. No case is closed. Symlink confinement, owner-only modes, quarantine default `accepted: false`, and “no arbitrary SQL” are the right objectives. Windows ACL detail stays unresolved rather than invented.

T10’s failure behavior contradicts A3, and the detection signal (`integrity_state`) is a row in the store being diagnosed. A local reader cannot trust a health bit that the corrupt file is supposed to hold. That is a local-security defect, not only a migration wording defect. The rest of the case list can stand once T10 matches A3 and the disclosure channel is outside the failed file.

### 8. Cross-platform engineering — `PASS_WITH_NONBLOCKING_NOTES`

The store is a local file. Telemetry is default-off and is not on the evidence path. An offline machine can be a future test host for read, write, migration refusal, and proof export. Windows is not covered by Unix `0600`. The pack says that, and it leaves ACL specifics unresolved. OF-47 stays `TARGET_DESIGN`. The Node SQLite binding is unresolved, so a same-file Node and Python test is a Gate 8 prerequisite, not a result. This council ran no Windows, Linux, or offline product test.

### 9. Customer support and diagnostics — `NEEDS_REVISION`

Support text would be generated from issue location and from query completeness. Both are wrong in the ways seats 1 and 6 describe. A catalog-host 401 labeled `PROVIDER_INTERACTION`, a successful call labeled with a failing layer, and a `COMPLETE` page that omitted drops would send a customer to the wrong layer. `LEGACY_UNMARKED` excluded from default trends is an intentional support surprise and is already an open founder decision; it is not itself the defect. The defect is that the diagnostic fields support would read are not yet trustworthy.

### 10. Evidence and independent verification — `NEEDS_REVISION`

No requirement is `IMPLEMENTED`, `SHIPPED`, `PROVED_EXTERNAL`, `CUSTOMER_VALIDATED`, or `INTERNAL_PROOF`. Evidence tiers are `UNSET`. The producer did not re-run suites, and this council did not re-run them either. Load-bearing inventory citations were checked against the tree at this tip and held, with one understatement recorded in the nonblocking notes.

The proof is a separate artifact, and the hash is specified as a change detector. It is not yet an independently checkable manifest. A2 section 5 allows the JSON to be pretty-printed or compact and also says the hash covers the canonical body. Node and Python serializers do not share one byte profile unless the pack names one. Two producers can hash different bytes for one logical proof. OF-43 is `ARCHITECTURE_BLOCKED` until the byte rules exist.

### 11. Developer experience — `PASS_WITH_NONBLOCKING_NOTES`

Unstable pre-1.0 is consistent. Legacy `schema_version` 2 is not reused as the store version. Commands for prune, config, UI, and doctor are named as absent. Default trends that hide legacy files until an explicit promote will confuse the first migrated workspace; that choice is visible in the founder list. The revision should keep the CLI reader’s `VANTIO_HOME` bug as a future correction and should not patch `vantio.js` inside the revision of this pack.

### 12. Scope control and product positioning — `PASS_WITH_NONBLOCKING_NOTES`

Optics stays structural observation. `action` for foundation evidence is `OBSERVED`. Phantom Engine remains the enforcement plane. Option E is rejected. Alerting is unselected. OTLP and the local UI are unauthorized. No public claim and no customer-validation claim appear in the pack. The roadmap input already names SQLite in section 10; A2 still compares five options and leaves ratification open. That is a recommendation, and it stays one.

## Answers to the required challenges

1. **Does the evidence model identify every failing layer without assigning false blame?** No. There is no “no failing layer” value. The section 10 example assigns `PROVIDER_INTERACTION` to HTTP 200. Catalog-confident HTTP 4xx, including client errors, maps to the provider. A1 and A5 disagree. Disk pressure is “`OPTICS` or `ENVIRONMENT`.”

2. **Can Optics itself fail without breaking the application?** Yes, on the observation path, as a contract. The call must continue with unchanged output, and a missed write must not become a successful observation. Co-located enforcement branches are outside that grant. The contract is not implemented.

3. **Can evidence become incomplete without appearing complete?** Yes, under the current text. Query `COMPLETE` describes an untruncated page. Drops live on product-health, which the default query excludes. Proof completeness is a second, undefined use of the same word.

4. **Can simulated, imported, or fixture evidence masquerade as customer evidence?** The default origin filter and the import rule aim to prevent that. The legacy adapter contradicts itself on whether a file may assert `LOCAL_OBSERVATION`. Until that sentence is closed, a forged legacy file can be read as customer evidence. Today’s `vantio demo` already writes an ordinary run file; that is current source, and the target origin rule is what has to become unambiguous.

5. **Can the store be corrupted, rolled back, or migrated without disclosure?** Yes. Stop-and-keep-bytes and bounded read-only are both written down. The health record that would disclose the event is inside the store, and a failed health write is specified as an in-memory counter.

6. **Can sensitive content reach persistence through metadata, exceptions, URLs, baggage, annotations, or imports?** The prohibited list blocks the obvious channels and is the right rule. `session_id` is still an unspecified string on the allowlist. Annotation’s allowlist row cannot be implemented as written. Import’s stored row has a hash and a label, not a raw body, and acceptance must not change origin. The corpus is specified and not built.

7. **Is portable proof clearly separated from the operational store?** Yes. Compaction must not rewrite an exported proof. Attestation words are prohibited. The hash does not name an author. The bytes that enter the hash are not defined. Separation passes. Reproducibility does not.

8. **Can Node and Python versions coexist safely?** The writer rule is safe: the newer build may migrate forward, the older build refuses or stays read-only, and legacy JSON stays on disk. The Node binding is unselected, so a shared-file implementation is not yet specified. Child-process id inheritance can still merge or collide the two runtimes’ ids. Mixed-version legacy files remain `LEGACY_UNMARKED`, which avoids a false promotion and hides them from default trends.

9. **Can retries, async calls, child processes, redirects, and proxies be correlated honestly?** Retries, async calls, redirects, and proxies can. Child processes cannot, until `run_id` allocation and `sequence` scope are defined for a process that inherited `VANTIO_TRACE_ID`.

10. **Is the query contract bounded against information leakage and denial of service?** Denial of service is bounded by the structural caps: row limit, no SQL, no caller regex, time bounds except a single-run lookup, and refusal of a non-indexed predicate. Numeric latency remains `NOT_SET`. Leakage is bounded for bodies, annotations-by-default, and telemetry ids. It is open for an unspecified `session_id` and for a completeness field that omits drops.

11. **Are cardinality and overload behavior explicit?** Yes. Label allowlists, `UNSAMPLED`, queue-full drops, and “do not delete to make room” are explicit. Threshold numbers are `NOT_SET` on purpose.

12. **Are freshness, completeness, and integrity independent dimensions?** They are named in different places and are not fields of one answer. `CURRENT` is withheld until a window exists, so the honest freshness value is `UNKNOWN`. Integrity is a product-health enum. Completeness on a query is page truncation. OF-27 is `ARCHITECTURE_BLOCKED`.

13. **Does any specification assume SQLite before the alternatives analysis?** A1 does not. A2 scores A–E and recommends C with ratification still open. A3 then uses SQLite `user_version` and `BEGIN IMMEDIATE` without a conditional label. The roadmap input states SQLite before this pack. Inside the architecture set, C is a recommendation. The scorecard also gives C a pass on “do not delete a corrupt file” and “allowlist before insert,” which are application rules available to the file options too. That scoring bias does not by itself reopen A–E.

14. **Does any requirement quietly create a daemon?** No. Option E is rejected. OF-45 is `NEEDS_FOUNDER_DECISION`. Background update is refused. The UI prerequisite forbids a persistent daemon.

15. **Does any design imply enforcement by Optics?** No. Foundation rows use `action: OBSERVED`. Block, redact, and cap stay inventoried as co-located Phantom Engine behavior and are not extended.

16. **Does any architecture claim external proof or customer validation?** No. Tiers are unset. The manifest hash is a local change detector. Producer readiness is labeled as producer readiness.

17. **Is the future UI downstream of governed evidence semantics?** The dependency direction is right: the UI is `TARGET_DESIGN`, and it would have to use the bounded query. Those semantics are not ready. A UI built on today’s query and issue-location text would render false layers and complete-looking gaps. OF-06 stays unauthorized.

18. **Are all implementation prerequisites explicit?** Gates, `NOT_SET` budgets, and the founder list are explicit. Canonical JSON, the out-of-band integrity channel, `session_id` validation, child `run_id` allocation, and the success value for issue location were written as if they were decided or were left as conflicting sentences. Those are revision items, not additional founder decisions.

19. **Can the architecture be tested on Windows, Linux, and offline environments?** Linux and offline tests are compatible with the local-file design and have not been run. Windows tests require an ACL rule this pack correctly refuses to invent. OF-47 is still `TARGET_DESIGN`.

20. **Are unresolved decisions clearly marked rather than silently selected?** The thirteen founder decisions are marked, and this council leaves every one of them open. The silent or conflicting selections are issue location, query completeness, corrupt-store read behavior, `session_id` acceptance, proof canonical bytes, and child-process identity. Option C is marked unratified.

## Blocking issues

The producer revises the documents. This council does not rewrite those specs in place.

1. **Failing layer.** Give issue location a defined value for “no failing layer,” or omit the field on success. Stop mapping every catalog-confident HTTP 4xx to `PROVIDER_INTERACTION`. Make A1 section 3, A5 section 2, and the section 10 example say the same thing. State that Optics `SUCCESS` means a record was stored. Replace “`OPTICS` or `ENVIRONMENT`” with one rule, using `UNKNOWN` when the layer is not determined.

2. **Complete-looking gaps.** The shared read contract for a future CLI, UI, and structured output has to carry capture state separately from page truncation. A page that returns every stored row is still incomplete when `dropped_count` is non-zero, any included run is not `COMPLETE`, sampling is anything other than `UNSAMPLED`, or integrity is not `OK`. Define `PARTIAL`. Default answers have to show that envelope even though product-health rows stay out of the customer timeline. OF-27 and OF-33 move to `ARCHITECTURE_BLOCKED`.

3. **Store damage disclosure.** One behavior for a corrupt file: stop, keep the bytes, do not serve them as a readable store. Align T10 with A3. Specify a disclosure channel that works when the database cannot be opened, and that the next command must surface. A migration and a weaker-writer refusal use that same channel. OF-34 moves to `ARCHITECTURE_BLOCKED`.

4. **Origin and open strings.** State that a legacy file’s own `evidence_origin` is discarded. Demo host `optics-demo.invalid` remains `SIMULATED_DEMO`; every other legacy file remains `LEGACY_UNMARKED`. Define `session_id` acceptance with a charset and a reject path, or drop the field until that rule exists. Rewrite the annotation allowlist row so it does not cite `DERIVED_DIAGNOSTIC`. Do not add a seventh origin while that founder decision is open.

5. **Proof bytes.** Name the canonical JSON rules the SHA-256 covers. “Pretty-printed or compact” cannot both be canonical. HTML and Markdown stay renderings and stay outside the hash. OF-43 moves to `ARCHITECTURE_BLOCKED`.

6. **Child process identity.** Define `run_id` as one attached process. Define what a child that inherited `VANTIO_TRACE_ID` writes into `run_id` and into `trace_id`, and define `sequence` scope so two processes cannot mint the same `event_id`.

Gates reopened: 2, 3, 4, 5, 6, and 7. Gate 1 stays accepted with the factual note below. Gate 8 stays closed. `09-IMPLEMENTATION-GATES.md` is unchanged. Its producer sentence that a revision request had not happened inside that file remains producer text. This report is the request.

## Nonblocking notes

- Inventory finding 1.3 says response size is absent when `Content-Length` is absent. The exit mapper stores `call.bytes || 0` (`packages/vantio-cli/bin/interceptor.cjs` line 3736), so a missing size becomes zero. The target catalog already says null when unknown and forbids inventing the number. The inventory classification `PARTIAL` still fits. The zero-invention detail belongs in the inventory sentence when A0 is next touched. This council does not edit `01-CURRENT-STATE-INVENTORY.md`.
- Checked and consistent with the inventory: Node exit envelope and swallowed write error (`interceptor.cjs` lines 3679–3768); Python skip on zero calls, `schema_status`, `workflow`, and chmod `OSError` (`_http_observe.py` lines 2485–2538); CLI `runsDir` ignoring `VANTIO_HOME` (`vantio.js` `configDir` / `runsDir`); `vantio demo` writing `optics-demo.invalid` with no origin; `prove --from` rendering any JSON object (lines 785–818); `guessProvider` substring matches (`llm-hosts.cjs` lines 84–112). Suites were not re-run.
- The A2 scorecard credits SQLite for policies a JSON store can also enforce. Keep the recommendation. Fix the conditional label on A3. Do not treat the bias as a rejection of option C.
- Annotation’s seventh origin stays unresolved. Repair the allowlist cell in the same revision; do not close the founder question by picking a value.
- After a future migration, default trends omit `LEGACY_UNMARKED` history until a promote decision. That is already founder decision 6. Support copy has to say so. It is not a silent promotion.
- POSIX modes are not a Windows control. Leave the ACL decision open.
- A future SQLite call on process exit can delay exit even when per-call observation fails open. The `NOT_SET` shutdown budget already blocks an invented timeout. Gate 8 has to keep exit delay visible.
- OF-36 `ARCHITECTURE_DEFINED` means UI security prerequisites are written. It does not mean a UI exists. OF-06 stays `TARGET_DESIGN`.

## Requirement status changes

| ID | Previous | Council status | Why |
| --- | --- | --- | --- |
| OF-27 | `ARCHITECTURE_DEFINED` | `ARCHITECTURE_BLOCKED` | Freshness, completeness, and integrity are not one read model. |
| OF-33 | `ARCHITECTURE_DEFINED` | `ARCHITECTURE_BLOCKED` | The application continues. Drops are not required on the default read. |
| OF-34 | `ARCHITECTURE_DEFINED` | `ARCHITECTURE_BLOCKED` | Corrupt-store behavior and its disclosure channel contradict each other. |
| OF-43 | `ARCHITECTURE_DEFINED` | `ARCHITECTURE_BLOCKED` | The proof hash has no canonical byte rules. |

Counts after this council: `ARCHITECTURE_DEFINED` 25, `TARGET_DESIGN` 20, `NEEDS_FOUNDER_DECISION` 3, `ARCHITECTURE_BLOCKED` 4. Total 52. No row moved to `IMPLEMENTED`, `SHIPPED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`.

## Unresolved founder decisions

Unchanged. The council ratifies none of them and adds none.

1. Ratify or replace operational-store option C.
2. Usage and cost metadata (OF-05).
3. Alerting delivery mode (OF-45). No daemon is selected.
4. Numeric targets for every `NFR-*` budget (OF-32). All remain `NOT_SET`.
5. At-rest encryption.
6. Whether an explicit customer promote may stamp `LEGACY_UNMARKED` as `LOCAL_OBSERVATION`.
7. Whether annotations need a seventh origin value.
8. Windows ACL specifics beyond owner-only intent.
9. Node SQLite binding.
10. Freshness window that would allow the token `CURRENT`.
11. Optional persisted machine hostname.
12. OTLP or SIEM export.
13. Local UI charter (OF-06) and accessibility (OF-37).

## What this council deliberately leaves standing

- Evidence classes and the six writer origins, with `LEGACY_UNMARKED` as a reader state.
- Option C as the recommendation to ratify, with A, B, D, and E rejected for the long-term index on the reasons that are actually engine limits: transactional migration, no daemon, and no second analytical stack.
- Proof as a separate JSON artifact. Prohibited words: tamper-proof, WORM, notarized, certified, regulator-approved, externally attested.
- Unstable pre-1.0. No deprecation schedule.
- Fail-open for the observation path.
- Cardinality limits, `UNSAMPLED`, and explicit overflow.
- Threat cases T1–T15 with unset residual risk, after T10 is aligned with A3.
- Hard boundary against Phantom Engine enforcement, a daemon, OTLP, alerting, a UI build, and a stable schema.

## Hard-stop attestations

This council wrote only under `docs/architecture/optics-foundation/`: this report, the council sections of `08-ARCHITECTURE-DECISION-PACK.md`, council fields in `ARCHITECTURE-MANIFEST.json`, and the four requirement statuses above in `TRACEABILITY-MATRIX.json`.

| Stop | Attestation |
| --- | --- |
| No product code | No file under `packages/` was modified. |
| No package, seal, publish, tag, or release | No version, workflow, tag, npm, or PyPI action. |
| No credentials | No secret was read or written. |
| No store implementation | No SQLite file, migration, or record conversion was executed. |
| No UI, daemon, OTLP, or alerting | Not started. |
| No stable schema | `schema_status` remains `unstable-pre-1.0`. |
| No customer-validation or external-proof claim | None added. |
| A8 not started | Gate 8 remains closed. |
| PR left draft | https://github.com/vantioai/vantio-open-core/pull/55 stays draft. It was not marked ready and was not merged. |

## Council exit

Verdict: `NEEDS_REVISION`

Force classification: `OPTICS_FOUNDATION_ARCHITECTURE_NEEDS_REVISION`
