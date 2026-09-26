# Optics Foundation — implementation planning boundary

Audience: INTERNAL_RESTRICTED

Producer role: planning producer only. This agent does not sit the independent planning council, does not self-assign a council pass, and does not open Gate 8.

Producer identity: Cursor cloud agent `bc-cdec4aa3-94f6-5b72-b604-d2b7ba3bfbac`, model Grok 4.7.

Producer classification: `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_READY_FOR_COUNCIL`

That classification means the planning packet is ready for a separate council. It is not a council verdict, not an implementation authorization, and not evidence that any package is proved.

## 1. Locked input

| Item | Value verified at planning time |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `8a6ef881169c2bf379e04a7d1e8381532ec236b2` |
| Commit subject | Merge pull request #55 from `vantioai/architecture/optics-foundation-a0-a7` |
| Planning branch | `planning/optics-foundation-a8-decomposition` |
| Writable path | `docs/planning/optics-foundation-a8/` only |
| Founder input label | `OPTICS_FOUNDATION_ARCHITECTURE_MERGED_NO_IMPLEMENTATION` |
| In-file council classification | `OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED` |
| Store direction | `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY` |
| Gate 8 | Closed |
| A8 | Not started |

The Founder input label and the in-file council classification describe the same tree. Council reviewed tip `7db944d17c7f74706f08970b4908e92d0bf2d589`. The next commit on that branch, `df55066aa1ab797bcade4a7867590274e2325c09`, records the re-council pass. Merge commit `8a6ef881169c2bf379e04a7d1e8381532ec236b2` brings that tree onto main. Requirement counts, evidence tiers, customer-validation fields, Gate 8, and Option C were checked on this merge commit.

Sentences inside the architecture pack that say draft PR #55 stays draft are historical attestations written before the merge. This planning force leaves those sentences in place. They are not a second architecture and they are not a reason to replan.

## 2. P0 verification

Verified on `8a6ef881169c2bf379e04a7d1e8381532ec236b2`:

- All 13 architecture files exist under `docs/architecture/optics-foundation/`.
- `ARCHITECTURE-MANIFEST.json` and `TRACEABILITY-MATRIX.json` parse.
- `files_sha256` in the architecture manifest matches the bytes of the 12 listed files. The manifest’s own SHA-256 is recorded in `PLANNING-MANIFEST.json` because the architecture manifest does not store its own hash.
- Requirement count is 52.
- Status counts are `ARCHITECTURE_DEFINED` 29, `TARGET_DESIGN` 20, `NEEDS_FOUNDER_DECISION` 3, `ARCHITECTURE_BLOCKED` 0.
- All 52 `evidence_tier` values are `UNSET`.
- All 52 `customer_validation` values are `UNSET`.
- All 52 `independent_verifier`, `stranger_host`, and `required_closing_tier` values are `UNSET`.
- Gate 8 is closed. Gates 1–7 are architecture documents. Passing a document gate assigns no evidence tier.
- Option C is embedded SQLite, WAL mode, application-owned schema, no raw SQL customer API, architecture only.
- No requirement is represented as implemented, shipped, proved, or customer-validated.
- Roadmap file `docs/internal/optics-best-in-class-roadmap.md` is unchanged. Its SHA-256 matches the architecture manifest: `909f9eb69fac697dff98d42f29de7bf00a9ee808c2c307af220b4a931f4e952a`.

P0 result: input matches the merged classification. Planning continues.

## 3. Product facts read from this tree

These facts were read from source metadata and internal notes. This force does not publish, seal, or contact a registry.

| Surface | Fact in this tree | Planning consequence |
| --- | --- | --- |
| `@vantio/cli` | `packages/vantio-cli/package.json` version `0.3.24` | Frozen. Slice 1 does not patch, republish, or retag it. |
| Node writer | `packages/vantio-cli/bin/interceptor.cjs` writes the run file | A future Node writer change is a future CLI version. It is outside Slice 1. |
| Node display vocabulary | `packages/vantio-cli/bin/optics-cx.cjs` tokens `OBSERVED`, `NOT_OBSERVED`, `UNSUPPORTED`, `UNAVAILABLE`, `APPLICATION_ERROR`, `OPTICS_ERROR`, `PARTIAL`, `SUCCESS` | Slice 1 preserves these tokens. |
| Python package | `packages/vantio-agent-sdk-py/pyproject.toml` name `vantio-agent-sdk`, version `3.1.0` | Merged source. Unpublished from this planning force. No RC. No seal. |
| Python 3.0.15 | Changelog entry. `docs/internal/python-3.1.0-stage2-backlog.md` says it is not the ship target and is not published from that pass | Compatibility target for Slice 1 is 3.1.0 source behavior. 3.0.15 is not the target. |
| Node SDK | `packages/vantio-agent-sdk/package.json` version `0.2.4` | A different package from the Python distribution. Slice 1 does not modify it. |

`PARTIAL` is a current display token for mixed machine outcomes in one run. The architecture also uses `PARTIAL` for run lifecycle and for query completeness. Those three uses stay distinct fields. Slice 1 must not collapse them into one success bit.

## 4. What this force does

- Decomposes the merged architecture into 17 implementation packages.
- Records dependencies, rollback, release units, evidence gates, and the locked first slice.
- Writes a future Founder Force template for Slice 1 and marks that template not authorized.
- Leaves `09-INDEPENDENT-PLANNING-COUNCIL.md` as `PENDING_INDEPENDENT_COUNCIL`.

## 5. What this force keeps closed

- Product code, package versions, workflows, tags, GitHub releases, npm, PyPI, TestPyPI, and Twine.
- SQLite files, bindings, schemas, migrations, record conversion, and WAL.
- UI, daemon, OTLP, SIEM export, alerting, retention execution, pruning, and `vantio doctor`.
- Stable schema declaration, numeric performance targets, and customer-validation claims.
- Gate 8 and A8.
- Founder decisions 2–13.
- Credentials, website copy, and announcements.

`schema_status` stays `unstable-pre-1.0` on every object this plan describes.

## 6. Slice 1 lock

Founder lock: **SLICE 1 — EVIDENCE CONTRACT AND WRITE-PATH PRIVACY BOUNDARY**, before any SQLite work.

Package: `PKG-01`.

This document does not authorize that slice. Specification: `07-FIRST-SLICE-SPECIFICATION.md`. Future force text: `08-FIRST-SLICE-FUTURE-FORCE.md`, marked `NOT AUTHORIZED`.

## 7. Unresolved Founder decisions 2–13

Decision 1 stays resolved as architecture only: `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. This plan does not reopen it and does not treat it as permission to create a database.

Decisions 2–13 stay unresolved. Safe defaults below are the behavior an implementation uses while the decision is open. They are not silent resolutions.

| # | Decision | Packages affected | Earliest decision point | Consequence of deferral | Safe default while unresolved | Architecture conflict if decided the other way | Founder options already named | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | Usage and cost metadata (OF-05) | PKG-01, later writers in PKG-02 | Before any writer persists a usage or cost field | Cost stays absent from records and proofs | Field stays off the allowlist. No body inspection | Adding the field requires a new allowlist generation and a privacy review of provider bodies | Allowlist a bounded numeric field, or keep it excluded | Keep excluded until a Founder names the exact fields and confirms they are not body text |
| 3 | Alerting delivery mode (OF-45) | PKG-16, and any daemon temptation in PKG-12 | Before PKG-16 implementation | No alerter ships. Failures stay on product-health and the query envelope | No daemon. No alert transport | A daemon default conflicts with fail-open and with the rejected store option E | Run-time, post-run, external scheduler, or explicit service | Defer. Do not pick a mode in this plan |
| 4 | Numeric NFR targets (OF-32) | PKG-12, PKG-07, PKG-10, PKG-11, PKG-04 | Before any release claims a latency, size, or overhead number | Packages ship structural caps only: row limit 500, reject unbounded work, unbounded retention when unset | Every `NFR-*` target stays `NOT_SET`. No roadmap example number is adopted | A number chosen here would be an invented budget | Founder sets each `NFR-*` target, measurement, and workload | Leave `NOT_SET` |
| 5 | At-rest encryption | PKG-07, PKG-11, PKG-08 | Before a release claims encryption | Store file relies on filesystem owner-only mode | Encryption is not selected and is not implemented | A later encryption choice must not rewrite historical proof bytes | Select a mechanism later, or keep filesystem permissions as the control | Leave unselected |
| 6 | Customer promote of `LEGACY_UNMARKED` to `LOCAL_OBSERVATION` | PKG-08, PKG-15, PKG-01 | Before any promote command | Legacy files stay readable and stay out of default trends | No promote. Preservation of an allowlisted origin requires recognized producer provenance. Demo host `optics-demo.invalid` reads as `SIMULATED_DEMO` | A promote path that is the default would inflate operational totals | Explicit customer promote, or no promote | Keep the default as no promote |
| 7 | Seventh evidence-origin for annotations | PKG-01, PKG-02, later annotation storage | Before an annotation record is written | Annotations stay out of the observation origin enum | `annotation_role` `CUSTOMER_ANNOTATION`. No seventh writer origin | Adding an origin later is a vocabulary change for PKG-02 fixtures | Add a seventh origin, or keep `annotation_role` | Keep `annotation_role` until a Founder asks for the seventh value |
| 8 | Windows ACL specifics beyond owner-only intent | PKG-07, PKG-11, PKG-04 proof file modes, OF-47 | Before a Windows release claims an ACL | Unix mode `0600` / owner-only is the specified intent. Windows ACL details stay unset | Owner-only intent. Do not invent an ACL | A Windows-specific ACL chosen in code without a decision would over-claim OF-35 | Founder names the ACL, or limits the Windows claim to owner-only intent | Leave the ACL unset. Block a Windows ACL claim until then |
| 9 | Node SQLite binding | PKG-06, then PKG-07 | After PKG-05 interface is accepted, before PKG-07 | No SQLite dependency is added. Python stdlib `sqlite3` stays the documented Python expectation and is still not implemented | Binding stays unselected | Selecting a binding inside Slice 1 or inside this plan would skip PKG-06 | Founder selects a binding in a later force | No recommendation. This plan does not compare bindings |
| 10 | Freshness window for token `CURRENT` | PKG-10, PKG-15, OF-27 | Before any surface emits `CURRENT` | Freshness stays `UNKNOWN` | `CURRENT` is not emitted. `STALE` stays reserved | Emitting `CURRENT` without a window would make a page look live | Founder sets the window, or retires the token | Do not emit `CURRENT` |
| 11 | Optional persisted machine hostname | PKG-01, PKG-02 | Before any writer adds `machine` | Docs that mention `machine` stay in conflict with writers | Hostname stays off the allowlist | Allowlisting it conflicts with A1 resource identity and with threat minimization | Allowlist a hostname, or keep it prohibited | Keep prohibited |
| 12 | OTLP or SIEM export | PKG-17 | Before any exporter | Portable proof remains the specified export. OTLP stays unauthorized | No OTLP. No SIEM exporter | An exporter that sends evidence off-box conflicts with the local, account-free boundary and with decision 12 | Authorize a specific exporter later, or keep proof JSON as the only export | Keep unauthorized |
| 13 | Local UI charter and accessibility (OF-06, OF-37) | PKG-14, OF-36 prerequisites | Before any UI file | No UI. Query and security prerequisites stay documents | UI is not designed as a build | Building the UI from OF-36 security notes alone would skip the charter | Open a charter, or keep the UI closed | Keep closed |

## 8. Nonblocking architecture notes this plan leaves open

The fresh architecture council left notes that are not planning blockers and are not Founder decisions. This plan does not close them:

- Inventory finding 1.3 still understates missing response size. The target catalog forbids inventing a zero. `01-CURRENT-STATE-INVENTORY.md` stays unread by this force as an edit.
- The A2 scorecard still gives Option C a pass on some application-policy rows. Ratification is not an engine proof.
- `producer_id` entropy is unspecified. Conflicts stay visible as `PRODUCER_SEQUENCE`.
- Canonical timestamp rule 13 does not name `time_start` or `time_end`. NFC rejection does not name a Unicode version.
- WAL and SHM sidecars are neighbors of the store file and are not separate recovery-envelope fields.
- `dropState` `UNKNOWN` cannot be query `COMPLETE`.
- A1’s non-executable `event_id` example `evt_example` is not the A4 encoding.
- Every `NFR-*` target stays `NOT_SET`, including shutdown flush.

## 9. Hard-stop attestation for this planning commit

| Stop | Attestation |
| --- | --- |
| Architecture files | Unchanged |
| Roadmap file | Unchanged |
| CLI 0.3.24 | Unchanged |
| Python 3.1.0 source | Unchanged |
| Node SDK 0.2.4 | Unchanged |
| Product code | None added |
| SQLite, database, migration | None |
| UI, daemon, OTLP, alerting | None |
| Seal, tag, registry | None |
| Gate 8 | Closed |
| A8 | Not started |
| Council | Pending. This producer does not pass it |
