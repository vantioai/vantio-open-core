# PKG-01 privacy dispositions

Audience: INTERNAL_RESTRICTED

One disposition is chosen per result, by the highest rank that occurred:

`ACCEPT` < `NORMALIZE` < `STRIP` < `REPLACE_WITH_SAFE_CATEGORY` < `REJECT_FIELD` < `REJECT_RECORD`

Detector character classes live in `contract/detector-classes.json`. Node and Python expand that file. Governed detection does not call `str.isalpha`, `str.isalnum`, locale case conversion, or Unicode casefold. ASCII case fold maps A–Z to a–z and leaves every other code point unchanged. `MRN:` stays case-sensitive. Other listed credential prefixes, including `AKIA`, `ASIA`, `AIza`, `ghp_`, `github_pat_`, `Bearer`, `Basic`, `eyJ`, and the OpenAI prefixes, fold ASCII case. A non-ASCII code point inside a credential tail is an insertion, not a terminator and not an ASCII letter. PAN scans use ASCII digits, optional ASCII space or hyphen separators, and an ASCII-letter boundary only. Non-ASCII does not hide a 13–19 digit run.

One reason code is chosen by `reason_priority` in `contract/enums.json`. That order is the reported reason. `MAX_SIZE_EXCEEDED` outranks `DETECTOR_MATCH` and `REDACTION_DROP`. The value is still omitted. A size-only failure does not set `diagnostics.privacy_event` to `DETECTOR_MATCH`. When a detector also matches, the privacy category can be `DETECTOR_MATCH` while the reason remains `MAX_SIZE_EXCEEDED`. Session overflow keeps `SESSION_ID_REJECTED` and is measured in UTF-8 bytes. A privacy failure uses reason `REDACTION_DROP` when that rank is the highest one present. A detector match on an allowlisted free-form value, or on a field name, uses `DETECTOR_MATCH` and `diagnostics.privacy_event` `DETECTOR_MATCH`. The prohibited value is not copied into the result, the reason, or a diagnostic string. Raw unsafe field names are not copied either. A safe grammar name may be echoed. A disguised prohibited name uses locator `PROHIBITED_FIELD_CATEGORY`. A detector-positive, control, or otherwise unsafe name uses `UNKNOWN_FIELD_REDACTED_n`.

When a destination component is omitted because it is sensitive, `diagnostics.privacy_event` is `DESTINATION_COMPONENT_REDACTED`. The category does not contain the path, host, query, userinfo, or canary. A destination that is only too long stays privacy-null unless a detector also matched.

Removal is the disposition. This slice does not store a hash or a mask of a secret.

| Situation | Disposition | Reason | What remains |
| --- | --- | --- | --- |
| Clean allowlisted observation with provenance | `ACCEPT` | `OK` | The observation |
| DNS case, timestamp padding, content-type parameters, trace hex case | `NORMALIZE` | `NORMALIZED` | Canonical value |
| Header map, clean unknown key, baggage without a secret, non-secret query | `STRIP` | `REDACTION_DROP`, `UNKNOWN_FIELD_OMITTED`, `BAGGAGE_OMITTED`, or `QUERY_STRIPPED` | Observation without that key |
| Secret inside an allowlisted string, username path, Unicode email-like path, database URL, PAN adjacent to non-ASCII | `REJECT_FIELD` | `REDACTION_DROP` | Observation without the destination or string field. Destination omissions use privacy category `DESTINATION_COMPONENT_REDACTED` |
| Detector-positive `schema_status_seen`, `detail_code`, quarantine `reason_code`, `provider_id`, `source_label`, `duplicate_of`, or `error_class`, including ASCII case fold and mixed-script tails | `REJECT_FIELD` | `DETECTOR_MATCH` | Value absent. Exact confidence enum may remain. Privacy category `DETECTOR_MATCH` |
| Secret-shaped unknown field name | `REJECT_FIELD` | `DETECTOR_MATCH` | Locator `UNKNOWN_FIELD_REDACTED_1`. Raw name absent |
| Control-character unknown field name that is not a detector | `STRIP` | `UNKNOWN_FIELD_REDACTED` | Locator `UNKNOWN_FIELD_REDACTED_n`. Privacy result stays null |
| Disguised payload name (newline, CR, tab, space, case, safe percent-encoding) | `REJECT_RECORD` | `PROHIBITED_FIELD_NAME` | Locator `PROHIBITED_FIELD_CATEGORY`. Exact catalog name `prompt` stays `PROMPT_COMPLETION_EXCLUDED` |
| Duplicate canonical field name after normalization | `REJECT_RECORD` | `DUPLICATE_CANONICAL_FIELD` | No record. Raw names absent |
| Oversized field name | `REJECT_RECORD` | `MAX_SIZE_EXCEEDED` | No record. Name absent |
| Caller `OPTICS_GENERATED` without the private trace witness | `NORMALIZE` or `STRIP` when the inherited key is removed | `CONFLICTING_PROVENANCE` | Basis replaced with `ASSERTED_CONTEXT`, or `IMPORTED_UNVERIFIED` for `traceparent` on import quarantine. Meaning is set. `provenance_conflict` is `TRACE_BASIS_REPLACED` |
| Inherited trace without local event evidence, claimed as `LOCAL_OBSERVATION` | `REPLACE_WITH_SAFE_CATEGORY` | `CONFLICTING_PROVENANCE` | Reader label `LEGACY_UNMARKED`. Origin not stored |
| Missing `optics_status` or missing `action` | `NORMALIZE` | `MISSING_REQUIRED_STATUS` | `optics_status` `UNAVAILABLE` when missing. Action omitted. HTTP evidence kept |
| Unknown non-enum `optics_status` token | `NORMALIZE` | `OPTIMISTIC_DEFAULT_FORBIDDEN` | Stored `UNAVAILABLE`. Token absent. Not a privacy incident |
| Accessor, proxy, or dict subclass with container hooks | `REJECT_RECORD` | `ACCESSOR_PROPERTY_FORBIDDEN` | No record. Getter not called |
| Plain class instance | `REJECT_RECORD` | `UNSUPPORTED_COMPLEX_VALUE` | No record |
| Function or other callable | `REJECT_FIELD` | `UNSUPPORTED_COMPLEX_VALUE` | No record. No function name, repr, or return value |
| Oversized path, label, annotation, diagnostic, provider id, version, or trace, measured in UTF-8 bytes | `REJECT_FIELD` | `MAX_SIZE_EXCEEDED` | Value omitted, not truncated. `PATH_OVERSIZE` remains in the enum and is not the byte-limit outcome |
| Invalid, overlong, or non-NFC session | `REJECT_FIELD` | `SESSION_ID_REJECTED` | Both session fields omitted |
| Session value that is also a secret | `REJECT_FIELD` | `REDACTION_DROP` | Both session fields omitted; both health counters increment |
| Malformed trace, or two contexts that disagree | `REJECT_FIELD` | `CONTEXT_REJECTED` | Trace stored as null; disagreeing case is `CONFIGURATION` when no earlier issue rule matches |
| Missing origin on a legacy shape | `REPLACE_WITH_SAFE_CATEGORY` | `LEGACY_UNMARKED` | Reader label `LEGACY_UNMARKED`; origin not stored |
| Claimed `LOCAL_OBSERVATION` without producer and version | `REPLACE_WITH_SAFE_CATEGORY` | `PROVENANCE_INSUFFICIENT` | Reader label `LEGACY_UNMARKED`; inherited trace kept as `ASSERTED_CONTEXT` |
| Host `optics-demo.invalid` | `REPLACE_WITH_SAFE_CATEGORY` | `SIMULATED_DEMO` | Origin `SIMULATED_DEMO` |
| Prompt, completion, message, or body | `REJECT_RECORD` | `PROMPT_COMPLETION_EXCLUDED` | No record; issue location `OPTICS` |
| Enforcement action other than `OBSERVED` | `REJECT_RECORD` | `ENFORCEMENT_ACTION_EXCLUDED` | No record |
| Validator fault, cycle, hostile getter, excessive nesting, malformed UTF-8, input bound | `REJECT_RECORD` | The matching terminal reason | No record; no exception text |

Issue location is chosen in this order: `OPTICS` when the record is not stored or the failure is internal, then `NETWORK` when a network failure has no HTTP status, then `PROVIDER_INTERACTION` for HTTP 400–599, then `CUSTOMER_APPLICATION` for a wrapped or classed error with no HTTP status, then `COVERAGE`, then unevidenced coverage as `UNKNOWN`, then `CONFIGURATION`, then `ENVIRONMENT`, then HTTP 2xx/3xx as `NONE`. The customer label is `Provider interaction`. The string `Provider fault` is not a label.

`VANTIO_TRACE_ID` maps to basis `ASSERTED_CONTEXT` and sets `diagnostics.trace_basis_meaning` to `ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF`. `traceparent` on an observation uses the same basis. `traceparent` on `import_quarantine` uses `IMPORTED_UNVERIFIED`. Inherited context does not prove `LOCAL_OBSERVATION` unless the record also has stored destination or HTTP evidence. A caller label `OPTICS_GENERATED` is kept only when `optics_trace_witness` is the private fixture value and the producer plus `cli_or_sdk_version` are present. The witness is not persisted. Field names are compared after NFC, one safe percent-decode, separator and control removal, and ASCII A–Z folding. Paths are classified after NFC.

Remediation codes are the closed set in `enums.json`. None of them ask for a raw evidence upload.

Structural exclusions (`workflow`, `plane`, `free_mode`, `est_spend_usd`, usage, token counts, cost, `residual`, `data_note`, `status_labels`) are omitted without a privacy failure when the value itself is not a secret. A prohibited name that is not in that structural set, including `hostname_machine`, is a privacy failure and the value is omitted.
