# PKG-01 privacy dispositions

Audience: INTERNAL_RESTRICTED

One disposition is chosen per result, by the highest rank that occurred:

`ACCEPT` < `NORMALIZE` < `STRIP` < `REPLACE_WITH_SAFE_CATEGORY` < `REJECT_FIELD` < `REJECT_RECORD`

One reason code is chosen by `reason_priority` in `contract/enums.json`. A privacy failure uses reason `REDACTION_DROP` when that rank is the highest one present. The prohibited value is not copied into the result, the reason, or a diagnostic string.

Removal is the disposition. This slice does not store a hash or a mask of a secret.

| Situation | Disposition | Reason | What remains |
| --- | --- | --- | --- |
| Clean allowlisted observation with provenance | `ACCEPT` | `OK` | The observation |
| DNS case, timestamp padding, content-type parameters, trace hex case | `NORMALIZE` | `NORMALIZED` | Canonical value |
| Header map, clean unknown key, baggage without a secret, non-secret query | `STRIP` | `REDACTION_DROP`, `UNKNOWN_FIELD_OMITTED`, `BAGGAGE_OMITTED`, or `QUERY_STRIPPED` | Observation without that key |
| Secret inside an allowlisted string, username path, database URL | `REJECT_FIELD` | `REDACTION_DROP` | Observation without the destination or string field |
| Oversized path that is not itself a detected secret | `REJECT_FIELD` | `PATH_OVERSIZE` | Path omitted, not truncated |
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

`VANTIO_TRACE_ID` maps to basis `ASSERTED_CONTEXT` and sets `diagnostics.trace_basis_meaning` to `ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF`. It does not mint `run_id` and it does not prove `LOCAL_OBSERVATION`.

Remediation codes are the closed set in `enums.json`. None of them ask for a raw evidence upload.

Structural exclusions (`workflow`, `plane`, `free_mode`, `est_spend_usd`, usage, token counts, cost, `residual`, `data_note`, `status_labels`) are omitted without a privacy failure when the value itself is not a secret. A prohibited name that is not in that structural set, including `hostname_machine`, is a privacy failure and the value is omitted.
