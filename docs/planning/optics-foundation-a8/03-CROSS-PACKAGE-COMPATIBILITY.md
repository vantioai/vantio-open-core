# Cross-package compatibility

Audience: INTERNAL_RESTRICTED

`schema_status` stays `unstable-pre-1.0`. This plan does not declare schema v1 and does not add a schema generator.

## 1. Options

| Option | Mechanism |
| --- | --- |
| A | Each language implements the contract from one machine-readable catalog, without a shared fixture gate |
| B | A canonical JSON Schema file plus validators generated or interpreted from that schema |
| C | A shared fixture corpus and hand-written validators, without a field catalog as data |
| D | A field catalog, a denylist, and a shared fixture corpus, with hand-written Node and Python validators |

## 2. Recommendation

**Option D.**

Slice 1 and PKG-02 use one field catalog and one denylist checked into the future contract package, plus one fixture corpus that both languages load. Node and Python validators are written in that language and tested against the same fixtures. No generator emits the validators. No JSON Schema file is the customer contract.

Option D is the recommendation for these reasons:

| Criterion | How option D behaves |
| --- | --- |
| Package independence | The catalog and fixtures live in one private package. CLI 0.3.24 and Python 3.1.0 do not import it until a later force. Node SDK 0.2.4 stays out of the contract. |
| Zero-install posture | Validators use the language runtime. They do not add a JSON Schema library, a native module, or a SQLite binding. |
| Build complexity | No codegen step and no generated file to drift. The catalog is hand-edited data. |
| Runtime overhead | Validation is a single pass over one record at the persistence boundary. No schema compiler runs on the request path. |
| Schema instability | The catalog is allowed to change while `schema_status` is `unstable-pre-1.0`. A JSON Schema published as the contract would be read as a stable surface. Option D keeps the catalog internal. |
| Customer inspectability | The catalog is JSON a reviewer can read. Fixtures show accepted and rejected bytes. Customers of CLI 0.3.24 see no new public schema. |
| Test determinism | Both languages assert the same fixture outputs, including canonical field order where a proof is involved later. |
| Future SQLite integration | PKG-05’s interface accepts the validator’s output object. PKG-07 stores that object. SQLite does not become the place that defines fields. |
| Backward compatibility | Current JSON files stay valid inputs to current readers. The validator’s target object is a separate result until writers are cut over. |
| Generated-file drift | Avoided. Option A drifts when one language interprets the catalog differently and no fixture catches it. Option B drifts when generated validators are edited by hand. |
| Node and Python release independence | Python can adopt the private package in a later version without a CLI release. The CLI adopts it only in a future CLI version. Conformance evidence for a paired claim still runs both fixture suites. |

## 3. Why the other options stay unused

Option A leaves Node and Python free to interpret an enum differently. The inventory already shows that split on `schema_status`, `workflow`, `pid`, provider detection, and zero-call files. A catalog without fixtures would repeat it.

Option B cannot express reject-not-truncate, query stripping, “omit the field and continue the application,” or completeness impact. A schema file also reads as a stability promise this architecture withholds. This plan does not add a generator.

Option C can lock the cases that have fixtures and still let an untested field diverge. The allowlist is larger than any one corpus. The catalog is the list the corpus is checked against.

## 4. Conformance rules that both languages share

- One allowlist. Unknown keys are omitted on the contract output.
- `schema_status` is `unstable-pre-1.0` on contract-shaped objects.
- `provider_id` comes from catalog, regional pattern, or local Ollama. Otherwise `unknown` with `provider_confidence` `NONE`. Substring `guessProvider` is not the target rule.
- `process_id` and `parent_process_id` are stored when the runtime provides them, otherwise null.
- An attached process has a `run_envelope` when `call_count` is 0. Lifecycle `COMPLETE` and application status `NOT_OBSERVED` on that envelope are the target. Wiring that into Python is PKG-02, because Python 3.1.0 currently skips the write when the call list is empty.
- Human sentences are `derived_diagnostic` records. They are not required to trust the observation.
- `action` on Optics evidence is `OBSERVED`. Enforcement actions stay out of Optics rows.
- `est_spend_usd` and other cost fields are omitted while decision 2 is open.
- `workflow` is not an observation field.
- `machine` and username are omitted while decision 11 is open.
- Display tokens in `optics-cx.cjs` stay the reader vocabulary. `UNSUPPORTED` and `UNAVAILABLE` stay status tokens, not evidence origins.
- Run-level display `PARTIAL`, lifecycle `PARTIAL`, and query completeness `PARTIAL` stay three fields.

## 5. Slice 1 compatibility choice

CLI 0.3.24 is frozen. The Node writer is `packages/vantio-cli/bin/interceptor.cjs`. The Python writer is `packages/vantio-agent-sdk-py/vantio/_http_observe.py` at source version 3.1.0. Python 3.0.15 is not the compatibility target.

| Option | Meaning for Slice 1 |
| --- | --- |
| A | A future CLI version carries the shared contract on the live Node writer |
| B | A shared contract package is introduced and is not loaded by live CLI 0.3.24 or by the Python 3.1.0 import path |
| C | Node and Python behavior change in staged product releases |

**Slice 1 recommendation: option B.**

The contract, catalog, validators, and fixtures land in a private package that `vantio run` 0.3.24 does not load and that `vantio._http_observe` does not import. Current readers and current writers keep their behavior. Tests may import existing readers without editing them.

Option A is the later step that puts the contract on the Node customer path. It requires a CLI version other than 0.3.24. It is not Slice 1.

Option C is the release shape after the contract exists: Python can ship in a later version, and Node waits for that future CLI. Staging the behavior change inside Slice 1 would change 3.1.0 source behavior or reopen 0.3.24 before the corpus is a gate.

PKG-02 is where option C’s writer cutover is planned. PKG-02 stays `BLOCKED_BY_DEPENDENCY` on PKG-01.

## 6. Reader compatibility

Current run readers, proof renderers, and status tokens keep their behavior through Slice 1 because Slice 1 does not change their files.

When PKG-02 later writes contract-shaped fields:

- A legacy reader that skips unknown keys must still show the fields it already understands.
- A missing `evidence_origin` stays the reader disposition `LEGACY_UNMARKED`. It is not filled in as `LOCAL_OBSERVATION`.
- `optics_status` `SUCCESS` means the observation record was stored. It does not mean the provider call succeeded.
- `schema_status` on new objects is `unstable-pre-1.0`. CLI stdout JSON keeps that marker as it does today.
- Prompts and completions stay out of the store and out of the proof.
- Product telemetry stays on its existing opt-in channel. `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` override `VANTIO_TELEMETRY=1`. The anonymous id file stays out of the evidence store.
- Account-free local use stays the default. The contract does not add a login or an API key.

## 7. Release independence

| Release | Can move alone? |
| --- | --- |
| Private contract package (Slice 1, option B) | Yes. No CLI publish and no Python seal |
| Future Python writer | Yes, after PKG-02, without a CLI publish |
| Future CLI writer | Yes, as a new CLI version, without republishing 0.3.24 |
| Claim that Node and Python match | No. The fixture suite for both languages is one evidence unit |
| SQLite default writer | No. Binding, schema, and fail-open ship together |
| Proof verifier | Yes, as a library, after PKG-01 and before migration claims |
| UI, alerts, OTLP | Each waits for its own Founder decision |
