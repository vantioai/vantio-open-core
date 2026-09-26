# PKG-01 independent council report

Audience: INTERNAL_RESTRICTED

## Classification

`OPTICS_PKG01_NEEDS_REVISION`

This council does not assign `OPTICS_PKG01_COUNCIL_PASSED`. It does not authorize merge, seal, publication, live CLI or Python integration, SQLite, UI, alerting, or exporters.

## Identity

| Item | Value |
| --- | --- |
| Council agent | `bc-795c2ba1-73bc-5a15-beba-f1505acc58cf` |
| Council run | https://cursor.com/agents/bc-795c2ba1-73bc-5a15-beba-f1505acc58cf |
| Producer agent (judgments not reused) | https://cursor.com/agents/bc-9d2eaaed-8a23-520b-8476-c64f679ba455 |
| Repository | `vantioai/vantio-open-core` |
| Draft PR | https://github.com/vantioai/vantio-open-core/pull/58 |
| Branch | `implementation/optics-pkg01-evidence-privacy` |
| Tip reviewed | `aac796416d3e6f64223445086f4a649b779c29fe` |
| Authorized base | `311f260a5f1bee1d3dc9b3734fd6910fb1116094` |
| Implementation commit | `a25cdd00e6b0e4a531bf71538899b52b1efdb151` |
| Producer classification | `OPTICS_PKG01_READY_FOR_COUNCIL` |

The council reviewed that tip and re-ran the isolated tests. It did not edit `packages/optics-evidence-contract/` or `tests/optics-evidence-contract/`.

## Seats

Overall is the worst material seat. `NEEDS_REVISION` is the worst result below. No seat is `BLOCKED`.

| # | Seat | Result |
| --- | --- | --- |
| 1 | Privacy engineering | `NEEDS_REVISION` |
| 2 | Observability semantics | `NEEDS_REVISION` |
| 3 | Node security | `NEEDS_REVISION` |
| 4 | Python security | `NEEDS_REVISION` |
| 5 | Cross-package conformance | `NEEDS_REVISION` |
| 6 | Application fail-open behavior | `PASS` |
| 7 | Compatibility | `PASS` |
| 8 | Cross-platform engineering | `PASS_WITH_NONBLOCKING_NOTES` |
| 9 | Release and scope control | `PASS` |
| 10 | Customer diagnostics | `NEEDS_REVISION` |
| 11 | Evidence verification | `NEEDS_REVISION` |
| 12 | Product positioning | `PASS` |

## Blocking findings

1. **Allowlisted strings are stored without the prohibited-value scan.** `contract/normalization.json` requires a scan of allowlisted strings. These writers store a charset match and skip `containsProhibited` / `contains_prohibited`. The detector returns true for each sample below. Both Node and Python emitted the sample with `privacy_event` null and reason `NORMALIZED`.

   | Field | Sample stored in the record | Confidence / record |
   | --- | --- | --- |
   | `schema_status_seen` | `sk-CANARYSEEN00001` | `import_quarantine` |
   | `schema_status_seen` | `eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig` | `import_quarantine` |
   | `detail_code` | `AKIAIOSFODNN7EXAMPLE` | `product_health` |
   | `detail_code` | `AIzaCANARY0001` | `product_health` |
   | `reason_code` | `ghp_CANARYTOKEN0001` | `import_quarantine` |
   | `provider_id` | `sk-canary0001` | `CATALOG`, `REGIONAL_PATTERN`, and `LOCAL_OLLAMA` on `localhost:11434` |

   Source: `validate.cjs` schema-status-seen store, detail-code store, quarantine reason store, and provider-id store (`confidence === "NONE"` is the only branch that forces `provider_id` to `unknown`). The Python module has the same stores.

2. **A prohibited value in a field name is copied into diagnostics and classified as an unknown field.** Input key `sk-CANARYKEYNAME0001` with value `x` produced disposition `STRIP`, reason `UNKNOWN_FIELD_OMITTED`, `privacy_event` null, and `fields.stripped` / `completeness_inputs.stripped_fields` equal to that key. `PRIVACY-DISPOSITIONS.md` says the prohibited value is not copied into the result, the reason, or a diagnostic string. The key is the prohibited value. Node and Python matched.

3. **Node stores a Unicode email in `path`. Python rejects that path.** With `destination_host` `api.example.com` and path `/user@exämple.com`, Node emitted the path, disposition `NORMALIZE`, reason `NORMALIZED`, privacy null. `privacy.cjs` `containsProhibited` was false. Python disposition was `REJECT_FIELD`, reason `REDACTION_DROP`, path absent. Python `contains_prohibited` was true. The email scanners differ: Node accepts only ASCII local and domain characters; Python uses Unicode `isalnum`. ASCII `canary.person@example.com` is rejected by both.

4. **Prohibited-name folding differs, so a payload name does not drop the record on Python.** Key `prompt` plus a following newline, value `sk-CANARYPROMPTNL01`: Node disposition `REJECT_RECORD`, reason `PROMPT_COMPLETION_EXCLUDED`, record omitted. Python disposition `STRIP`, reason `REDACTION_DROP`, record emitted. The secret value was absent from both canonical results. Node `normalizeName` removes `\s`. Python `normalize_name` removes only `-`, `_`, space, and tab, so the name stays out of the payload set. `isPayloadName("prompt\n")` was true on Node and false on Python.

5. **Inherited trace context keeps a caller basis of `OPTICS_GENERATED`.** `normalization.json` sets `inherited_trace_basis` to `ASSERTED_CONTEXT`. `PRIVACY-DISPOSITIONS.md` says `VANTIO_TRACE_ID` maps to basis `ASSERTED_CONTEXT`. For `vantio_trace_id` `0123456789abcdef0123456789abcdef` plus `trace_id_basis` `OPTICS_GENERATED`, plus a sufficient `node_interceptor` / `0.3.24` / `LOCAL_OBSERVATION` tuple, both languages stored `trace_id_basis` `OPTICS_GENERATED` and `evidence_origin` `LOCAL_OBSERVATION`. `diagnostics.trace_basis_meaning` was `ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF`. The same basis override on `traceparent` `00-0123456789abcdef0123456789abcdef-0123456789abcdef-01` stored `OPTICS_GENERATED` and left `trace_basis_meaning` null. `applyTrace` / `_apply_trace` uses a present enum basis before the inherited-source default.

## Nonblocking notes

- The shared 75-fixture corpus matches across languages, including canary absence. The blocking cases are outside that corpus.
- Missing `optics_status` is stored as `SUCCESS` when an observation is emitted, including beside `http_status` 500 and `application_status` `APPLICATION_ERROR`. The field catalog says SUCCESS means the observation object was produced. Missing `application_status` with no HTTP status is omitted. Missing `action` is stored as the const `OBSERVED`. A present action other than `OBSERVED` drops the record.
- Legacy `bytes` `0` becomes `response_bytes` null. Explicit `response_bytes` `0` stays `0`.
- A secret `path` with no destination host is omitted and is not marked privacy, because destination collection returns before the explicit-path scan when no host is chosen. The value was absent from the result. The same path with a host is `REJECT_FIELD` / `REDACTION_DROP` on both languages for an ASCII `sk-` query.
- `error_class` and a non-token `detail_code` call the privacy marker for every rejected value, including values the detector would not call a secret.
- A getter that never returns can still hang. Throwing getters, cycles, depth 20, and a 2,000,000 character string return terminal results.
- Python string length is code points. Some Node checks use UTF-16 code units. The corpus is BMP. Documented in `KNOWN-LIMITATIONS.md`.
- One detection decode is documented. This council did not treat a second encoding layer as a new defect.
- Duplicate JSON object keys remain last-key-wins, as documented.
- Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` still says closed. That file is not in the diff.

## Required questions

1. **Can prohibited content cross the validator boundary?** Yes. Finding 1 stores detector-positive tokens in `schema_status_seen`, `detail_code`, `reason_code`, and `provider_id`. Finding 3 stores a Unicode email in Node `path`. Corpus canaries in scanned fields (`path` with an ASCII `sk-` value, prompts, headers, sessions) are omitted. Top-level arrays are dropped.

2. **Can prohibited values leak through diagnostics?** Yes. Finding 2 copies the key `sk-CANARYKEYNAME0001` into `fields.stripped` and `completeness_inputs.stripped_fields` with reason `UNKNOWN_FIELD_OMITTED`. Closed reason codes and remediation codes do not interpolate values. `issue_location_label` is not `Provider fault` on the corpus.

3. **Can Node and Python produce different dispositions?** Yes, outside the corpus. Finding 3: Node `NORMALIZE` versus Python `REJECT_FIELD`. Finding 4: Node `REJECT_RECORD` versus Python `STRIP`, and Python still emits the record. The 75 corpus canonical strings matched byte for byte in both runners.

4. **Can hostile input hang or crash validation?** The tested hostile cases do not. Throwing getter → `HOSTILE_INPUT` and the getter message is absent. Cycle → `CYCLE_REJECTED`. Depth 20 → `EXCESSIVE_NESTING`. Malformed UTF-8 bytes → `MALFORMED_UTF8`. A 2,000,000 character string → `INPUT_BOUND` in under the test's 2 second bound, and the result does not contain `xxxx`. `validateEvidence` / `validate_evidence` catch failures and return `VALIDATOR_FAULT` without the injected exception text. A getter that never returns is not time-bounded.

5. **Can validation mutate caller data?** Not on the inputs exercised. Probe objects compared equal before and after `validateEvidence` / `validate_evidence`. The Node freeze test keeps `{ record_type: "nope" }`. `plainCopy` / `plain_copy` builds a new tree. `application_result` is the same reference the caller passed.

6. **Can a validator failure escape into host code?** Not on the paths exercised. Entry points catch and return a result. `http_status` `1.5` returned a result and the same `applicationResult` reference. Canonical JSON is a separate helper and is not called inside the validator.

7. **Can imported or simulated data masquerade as local observation?** Not on the shapes exercised. `import_quarantine` with requested `LOCAL_OBSERVATION` stored `evidence_origin` `IMPORTED`, reader `IMPORTED`, reason `ORIGIN_NOT_PROMOTED`. `original_evidence_origin` may still say `LOCAL_OBSERVATION`, which is the claimed prior label. Host `optics-demo.invalid` with `demo_command` and requested `LOCAL_OBSERVATION` stored `SIMULATED_DEMO`. An annotation with `evidence_origin` `LOCAL_OBSERVATION` refused that origin, reader `LEGACY_UNMARKED`, and did not store `LOCAL_OBSERVATION`.

8. **Can inherited trace context masquerade as observed evidence?** Yes. Finding 5 stores `trace_id_basis` `OPTICS_GENERATED` for `vantio_trace_id` and for `traceparent`, with `evidence_origin` `LOCAL_OBSERVATION` when the producer tuple is sufficient. The `vantio_trace_id` diagnostic says `ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF`. The traceparent case does not set that diagnostic. A legacy envelope `trace_id` of `0xabc123` was stored as `run_id` and was not stored as contract `trace_id`.

9. **Can missing fields become fabricated success or zero?** Missing `optics_status` becomes `SUCCESS` on an emitted observation, including when application status is `APPLICATION_ERROR`. Missing `action` becomes `OBSERVED`. Missing `application_status` without an HTTP status is omitted. Legacy byte count `0` becomes null. Explicit `response_bytes` `0` stays `0`. Missing import `accepted` becomes false. `sampling` becomes `UNSAMPLED`. `scope_complete` stays false. `integrity_state` stays `UNKNOWN`.

10. **Did live CLI or Python imports change?** No. The diff against `311f260a5f1bee1d3dc9b3734fd6910fb1116094` is 27 added files under `packages/optics-evidence-contract/`, `tests/optics-evidence-contract/`, and `docs/internal/optics-pkg01/`. `git grep` of `optics-evidence-contract` under `packages/vantio-cli`, `packages/vantio-agent-sdk-py`, and `packages/vantio-agent-sdk` found no matches. CLI version is `0.3.24`. Python package version is `3.1.0`. The scope test walks those trees and passed.

11. **Did any SQLite, UI, daemon, exporter, or alerting work enter the PR?** No. The 27-file diff has no sqlite, migration, UI, daemon, OTLP, SIEM, alerting, or workflow path. The private `package.json` has no `dependencies`. `store.sqlite` is absent. The scope test asserts that.

12. **Are all privacy fixtures deterministic?** Yes. `corpus.json` is static. The validators do not call `Math.random`, `Date.now`, or a UUID generator. The Node timing check around the long string does not enter the result.

13. **Are all canaries absent from outputs and test artifacts?** Yes for validator outputs. Both runners assert each case's `forbidden` list against canonical JSON, and those tests passed. Independent scans of `/tmp/pkg01-python-dump.json` (75 cases, 178558 bytes) and `/tmp/pkg01-node-dump.json` (75 cases, 178409 bytes) found zero occurrences of `CANARY`, `sk-`, `AKIA`, `BEGIN PRIVATE`, `canary.person`, `4111-1111`, and `123-45-6789`. The byte gap is the outer dump encoding (`json.dumps` spaces versus `JSON.stringify`). The inner canonical strings matched in the tests. Canary tokens remain in `corpus.json` and the test files as inputs.

14. **Does any documentation imply shipment or a stable schema?** No. Package README, `contract-metadata.json`, and `docs/internal/optics-pkg01/` say `unstable-pre-1.0`, `schema_version` 0, private, and not loaded by the live CLI or Python runtime. `stable_schema` is false. The field catalog says it is not a JSON Schema and not a stable public schema.

## Producer claims

| Claim | Council check |
| --- | --- |
| Paths only under the contract package, its tests, and `docs/internal/optics-pkg01/` | Confirmed. 27 added files. No other paths in the diff. |
| Option B: live CLI and Python do not import the package | Confirmed by grep and by the passing scope tests. |
| 75 fixtures and the stated disposition counts | Confirmed. `ACCEPT` 11, `NORMALIZE` 9, `STRIP` 16, `REJECT_FIELD` 27, `REPLACE_WITH_SAFE_CATEGORY` 8, `REJECT_RECORD` 4. Reason counts in `IMPLEMENTATION-REPORT.md` match a fresh count of `corpus.json`. |
| Linux Node and Python tests; other environments `NOT_TESTED` | Re-ran on this host. See below. Python 3.10 and 3.11 are not installed. Windows, macOS, and WSL were not run. |
| `schema_status` `unstable-pre-1.0`; no store writes | Confirmed on every corpus result by the tests. No database file. |
| Gate 8 opened for PKG-01 source only; other packages not advanced | The architecture gate file is unchanged and still says Gate 8 is closed. The diff does not add another implementation package. This council does not treat that prose as a pass of S1-G8. |
| Founder decisions 2–13 unresolved | `contract-metadata.json` lists 2 through 13 unresolved, with the safe defaults. No alerting, SQLite, UI, OTLP, SIEM, cost field, or `CURRENT` freshness writer was added. |
| PR still draft | Confirmed at review time: PR 58 `isDraft` true, `state` OPEN, `headRefOid` `aac796416d3e6f64223445086f4a649b779c29fe`, `baseRefOid` `311f260a5f1bee1d3dc9b3734fd6910fb1116094`. |
| 120 field rows | Confirmed. `field-catalog.json` `fields` length is 120. |

## Test re-run

Host: Linux `6.12.94+` x86_64. Node `v22.14.0`. Python `3.12.3`. Offline. No npm install and no pip install. Tip `aac796416d3e6f64223445086f4a649b779c29fe`.

```bash
node --test tests/optics-evidence-contract/node.test.cjs
python3 tests/optics-evidence-contract/python_test.py -v
```

Node: 7 tests, 7 pass, 0 fail. Python: 6 tests, OK. The cross-language subtest passed inside both commands.

`NOT_TESTED`: Python 3.10, Python 3.11, Windows, macOS, WSL, Node versions other than v22.14.0.

## Confirmations

- No live CLI or Python integration was added or authorized.
- No SQLite, UI, daemon, OTLP, SIEM, or alerting work is in the diff.
- Founder decisions 2–13 remain unresolved.
- The architecture gate file still describes Gate 8 as closed. This review does not advance any other package.
- PR 58 stays draft. This council does not merge it and does not mark it ready.

## Next Founder choice

Revise PKG-01. The revision stays inside the private contract, its tests, and these internal notes. Merging PKG-01 source, and any live runtime integration, stay unauthorized until a later council pass.
