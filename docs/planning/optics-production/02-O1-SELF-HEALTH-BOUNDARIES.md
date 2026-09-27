# O1 — self-health design boundaries

Audience: INTERNAL_RESTRICTED

Producer classification: `OPTICS_STORE_OPTION_C_VERIFIED_PLAN_READY_FOR_COUNCIL`

Package status: `DESIGN_SKETCH_ONLY`

Satisfaction owner: `PKG-03` in `docs/planning/optics-foundation-a8/01-IMPLEMENTATION-PACKAGE-MAP.md`. This sketch does not implement `PKG-03`.

Source: `docs/architecture/optics-foundation/06-SELF-OBSERVABILITY-AND-RELIABILITY.md` sections 1 and 2, decision-pack section 27, and the `PKG-03` entry in the A8 map. This sketch adds no diagnostic name.

## 1. Boundary

`O1` defines how Optics records its own health so that an Optics failure stays distinct from a customer call and from a provider call.

The record type is `product_health`. Those records are not customer AI calls, not provider calls, and not rows returned by the default observation query.

A future local UI, if a later force is authorized, still shows the query envelope, including `dropState`, `completeness`, and `integrityState`. It does not render product-health rows on the customer timeline. No UI is authorized here.

## 2. Diagnostic names

The `name` enum is the A5 list:

- `hooks_installed`
- `events_received`
- `events_persisted`
- `events_rejected`
- `events_dropped`
- `write_latency_ms` (measurement method `NOT_SET`)
- `query_latency_ms` (measurement method `NOT_SET`)
- `database_size_bytes`
- `last_successful_write_at`
- `integrity_state` with values `OK`, `FAILED`, `UNKNOWN`
- `session_id_rejected`
- `producer_sequence_conflict`
- `parent_conflict`
- `formatter_failures`
- `migration_state` with values `IDLE`, `IN_PROGRESS`, `FAILED`, `NOT_APPLICABLE`
- `redaction_failures`
- `schema_version`
- `privacy_generation`
- `rejected_context`
- `telemetry_last_result` with values `DISABLED`, `SENT`, `FAILED`, `SKIPPED`

`write_latency_ms` and `query_latency_ms` are names in the enum. They are not numeric targets. Founder decision 4 stays open. Every `NFR-*` current target stays `NOT_SET`.

## 3. Recursion stop

- The writer that persists product-health does not pass through the customer observation hook.
- If a diagnostic write fails, one in-memory counter increments and the writer stops.
- That counter does not emit a customer event, and it does not emit a new diagnostic per failure in a loop.
- The store write, when a store exists later, is not an observed destination. The same separation already used for the telemetry ping applies to that future client.
- A health payload does not copy prompts, completions, raw bodies, credentials, exception text, or customer payloads. A future fixture puts a canary in the health input and asserts the canary is absent from the stored health record. This sketch does not run that fixture.

## 4. Store failure is not a health row inside the failed file

When the store cannot be opened, `integrity_state` comes from the A3 external recovery envelope. A row inside the failed store is not that source. The envelope file itself belongs to the future persistence package `O7` / `PKG-07`. `O1` states the separation. `O1` does not create the envelope and does not create `store.sqlite`.

The in-memory recursion stop is not the corrupt-store disclosure. The next command surfaces the envelope. A missing envelope does not mean the store is healthy.

`dropState` `UNKNOWN` cannot be reported as query `COMPLETE`.

## 5. Issue location

Hook, persistence, read, migration, formatter, privacy, and other internal Optics failures use issue location `OPTICS`. The process continues. Optics does not fabricate a stored success.

A stored HTTP 500 can have `optics_status` `SUCCESS` and issue location `PROVIDER_INTERACTION`. `SUCCESS` here means the observation record was stored. It does not mean the provider call succeeded, and it does not mean Optics enforced anything.

`OPTICS_ERROR` remains the display token when Optics could not complete a local operation. It is not the application outcome for a provider 500.

## 6. Fail-open interaction

`O1` supplies the health record and the recursion stop that `O12` (`PKG-12`) consumes.

Observation failure does not fail the application call, does not hang it, and does not change response bytes or status. The two named exceptions are a privacy drop and an evidence-root refusal. Both still leave the application response unchanged.

Enforcement that blocks, redacts, or caps a call is outside `O1`. It is not an Optics health event and it is not an exception granted to Optics.

## 7. Predecessors and dependents

Predecessor: `PKG-01`, so a health record uses the same denylist. The private contract is on this commit. Live writers do not import it. That predecessor is satisfied for a design sketch and unsatisfied for a live writer.

Dependents:

- `O12` fail-open, overload, and crash behavior
- `O13` coverage and diagnostic commands
- `O10` query envelope fields for drops and integrity

`O13` waits until this model exists. This sketch is the model on paper. It does not authorize the command.

## 8. Held closed by this sketch

- `vantio doctor` and any support bundle
- A numeric latency, size, or overhead claim
- Alerting, a daemon, and a network export
- A health row that stands in for the recovery envelope
- A database file, a binding, and a migration
- CLI `0.3.24`
- Rendering product-health as customer activity
- Host enforcement

Evidence tier for `O1`: `UNSET`.
