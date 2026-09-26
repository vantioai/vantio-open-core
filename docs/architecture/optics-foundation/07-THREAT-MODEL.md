# A6 — Threat model

Revision: `OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL`. Gate 7 stays reopened until a fresh council passes. This line is not a council pass. This file is the threat model. Gates are in `09-IMPLEMENTATION-GATES.md`.

Audience: INTERNAL_RESTRICTED

No threat below is closed. Residual risk is `UNSET` for every case. No control is claimed to exist in the product today unless the inventory says the current code already does something narrower. Implementation status of every control is `NOT_STARTED`. Model status is `ARCHITECTURE_DEFINED`: the case, the control objective, and the failure behavior are specified for council review.

Optics observes. It does not enforce. A threat that is solved only by blocking customer traffic is a Phantom Engine concern and is out of scope for the control listed here.

Evidence tier for every case: unset. Required tests are specifications, not results.

## Shared assets

- Operational store and legacy JSON run files
- Portable proof files
- Product-telemetry id and ping
- Annotation records
- Application availability and response bytes

## Cases

### T1 — Compromised observed application

- Threat actor: code inside the observed application, including a dependency
- Asset: local evidence store and proof export
- Trust boundary: application process versus Optics persistence
- Abuse path: the application submits customer content, credentials, or forged records for persistence
- Prevention: A1 allowlist before persistence. Observation is structural metadata. Annotations and imports cannot rewrite a `LOCAL_OBSERVATION` row
- Detection: `redaction_failures` and `events_rejected` on product-health, excluded from customer activity
- Failure behavior: the application continues. The bad field or event is absent. No fabricated success row
- Recovery: refuse the bad record. Do not recreate an empty database
- Residual risk: `UNSET`
- Required test: fixtures with disallowed content assert the persisted record excludes it
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`

### T2 — Malicious local user

- Threat actor: another user on the same workstation
- Asset: evidence files, database, exports, configuration, telemetry id
- Trust boundary: OS user account versus other local accounts
- Abuse path: a local user reads or replaces another user’s evidence
- Prevention: directory `0700`, files `0600`, created by the owner. Windows ACL is not specified beyond “owner-only.” That gap is a Founder and implementation item, not a claim that Unix modes cover Windows
- Detection: permission errors surface as `integrity_state`
- Failure behavior: access outside the owner boundary fails closed for the store and does not widen modes to recover
- Recovery: restore from the pre-migration backup or a proof the owner still has. Do not create a replacement database over the damaged file
- Residual risk: `UNSET`
- Required test: two-user permission fixtures on the documented filesystem cases
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`. Current Unix create modes are `PARTIAL` in the inventory

### T3 — Poisoned imported evidence

- Threat actor: the author of an imported bundle
- Asset: trends, views, and proof exports
- Trust boundary: imported bytes versus `LOCAL_OBSERVATION`
- Abuse path: imported records are presented as locally observed activity
- Prevention: origin `IMPORTED`, `original_evidence_origin` preserved separately, quarantine default `accepted: false`, no silent overwrite, no promotion to `LOCAL_OBSERVATION`, demo, fixture, and `LEGACY_UNMARKED` excluded from default trends
- Detection: every material view shows evidence origin. This pack does not build the view
- Failure behavior: failed provenance or schema checks stay in quarantine
- Recovery: prior local observations are unchanged
- Residual risk: `UNSET`
- Required test: import fixtures that must not count as local observation or as operational trends
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`. Today `vantio prove --from` can render a JSON object without an origin label (`PARTIAL` / gap)

### T4 — Malformed trace context

- Threat actor: a caller or upstream process supplying trace context
- Asset: correlation fields
- Trust boundary: incoming context versus local `run_id`
- Abuse path: malformed, replayed, colliding, or sensitive baggage is stored or propagated
- Prevention: size limits, hex or legacy-hex allowlist, no baggage field, conflict drops both parents. `VANTIO_TRACE_ID` is `ASSERTED_CONTEXT`, not observation proof. Child `run_id` is new when the child is wrapped. `event_id` is scoped to `producer_id` plus `producer_sequence`
- Detection: `rejected_context` product-health. Parent and producer-sequence conflicts set `identity_conflict` and are visible on the query envelope
- Failure behavior: the event is kept with null trace fields. The bad context is not stored. Conflicting parenthood keeps both claims. A duplicate producer sequence with a different identity keeps both rows
- Recovery: local `run_id` still identifies the attached process
- Residual risk: `UNSET`
- Required test: malformed, replay, collision, oversize-context, parent-plus-child, detached child, conflicting parent, duplicate producer sequence, and cross-process timestamp-tie fixtures. Specified in A4. Not executed here
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`

### T5 — Oversized telemetry

- Threat actor: a noisy or hostile observed workload
- Asset: queue, store, application latency
- Trust boundary: observation path versus application progress
- Abuse path: volume exhausts queue, disk, or query budget
- Prevention: indexed-field allowlist, row limit 500 on queries, no regex, queue-full drops, no silent delete to free space. Numeric queue and latency budgets remain `NOT_SET`
- Detection: `events_dropped`, `database_size_bytes`, query refusal
- Failure behavior: explicit overflow. Application continues. One drop counter, not a per-event storm
- Recovery: customer retention only after the customer has configured a limit and confirmed a dry-run manifest
- Residual risk: `UNSET`
- Required test: burst and queue-full fixtures that assert explicit drop evidence and unchanged application responses
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`

### T6 — Path traversal and symlink

- Threat actor: a local user or a crafted import path
- Asset: files outside the evidence root
- Trust boundary: evidence root versus the rest of the filesystem
- Abuse path: a path or symlink redirects reads or writes
- Prevention: refuse symlinks that resolve outside the evidence root. `prove` output paths are customer-named and must not be followed if they are symlinks to unexpected locations. Legacy adapter reads only `*.json` directory entries inside the runs directory, not a caller-built relative path
- Detection: refused path attempts in `integrity_state`
- Failure behavior: the operation stops. No partial write outside the root
- Recovery: nothing outside the root was written
- Residual risk: `UNSET`
- Required test: symlink and parent-directory fixtures that fail closed
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`. `directoryBytes` skips symlinks when measuring size. Writers do not perform this confinement check today

### T7 — Local UI injection

- Threat actor: evidence or annotation text rendered by a future local UI
- Asset: the local browser session
- Trust boundary: stored text versus the UI document
- Abuse path: stored text is interpreted as active content
- Prevention: output escaping, a content security policy, no third-party assets. Specified as a prerequisite. The UI is not in this Force
- Detection: the first UI release has no mutation endpoint
- Failure behavior: untrusted text renders as text
- Recovery: restart the UI process. The store is unchanged because that release is read-only
- Residual risk: `UNSET`
- Required test: render fixtures for evidence and annotation text
- Status: `ARCHITECTURE_DEFINED` as a prerequisite. The UI requirement OF-06 remains `TARGET_DESIGN`
- Implementation: `NOT_STARTED`

### T8 — Unauthorized local UI access

- Threat actor: a different local user or a non-loopback client
- Asset: a future read-only evidence view
- Trust boundary: loopback interface versus other interfaces and users
- Abuse path: a client off-machine, or another local user, opens the UI
- Prevention: loopback-only binding, origin checks, explicit shutdown, no persistent daemon
- Detection: bind and origin failures are visible. No analytics channel
- Failure behavior: non-loopback and cross-origin requests are refused
- Recovery: shut the UI down
- Residual risk: `UNSET`
- Required test: bind-address and origin fixtures
- Status: `ARCHITECTURE_DEFINED` as a prerequisite
- Implementation: `NOT_STARTED`

### T9 — Query denial of service

- Threat actor: a local query client
- Asset: responsiveness of local tools and the store
- Trust boundary: bounded query contract versus arbitrary query power
- Abuse path: an expensive query stalls the store or the application
- Prevention: no arbitrary SQL, no caller regex, limit 500, time bounds, refuse unbounded scans
- Detection: query latency diagnostic and rejected-query count
- Failure behavior: the query is refused. The observed application keeps running
- Recovery: a narrower query still works. Saved views store queries, not copied events
- Residual risk: `UNSET`
- Required test: over-broad query fixtures that hit the structural cap
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`. Current search parses every JSON file

### T10 — Database corruption

- Threat actor: crash, disk fault, or a partial write
- Asset: operational store integrity
- Trust boundary: durable store versus in-flight buffer, and versus the external recovery envelope
- Abuse path: a torn write or interrupted migration is opened as a healthy database, or the only disclosure is a row inside the file that failed
- Prevention: transactional migrations, integrity check, stop normal writes, preserve original bytes, no silent empty replacement, no automatic overwrite or delete
- Detection: external recovery envelope under `optics/recovery/`, which the next command surfaces without trusting a health row inside the failed file. `integrity_result` on that envelope. Query `integrityState` uses the envelope when the store is not healthy
- Failure behavior: first state is `STOPPED_PRESERVED`. The corrupt file is not served as the operational store. `READ_ONLY_SALVAGE` is a later classified mode only. Salvage answers are `PARTIAL` or `UNAVAILABLE`, never `COMPLETE`. Newer-schema and weaker-writer refusals use the same envelope with `RECOVERY_REQUIRED` and do not rewrite the file
- Recovery: explicit workflow only. Success is `RECOVERED_TO_NEW_STORE` with a new store id. Failure is `RECOVERY_FAILED`. Original bytes and any pre-migration backup stay. Legacy JSON files were not deleted. The envelope may contain only the A3 allowlist
- Residual risk: `UNSET`
- Required test: interrupted migration and torn-write fixtures that assert the original bytes still exist, the envelope exists outside the failed file, salvage is not `COMPLETE`, and a replacement does not overwrite the corrupt bytes. Specified in A3. Not executed here
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`. Current writers are non-atomic full-file replaces, and errors are swallowed

### T11 — Instrumentation recursion

- Threat actor: Optics observing its own diagnostic writes or telemetry
- Asset: customer activity views and counts
- Trust boundary: customer AI calls versus Optics-internal diagnostics
- Abuse path: hooks or formatter failures are stored as customer calls
- Prevention: product-health and telemetry use a channel that does not pass through the customer hook. Default queries exclude `PRODUCT_HEALTH`
- Detection: a recursion counter that stops after one failure. That counter is not the corrupt-store record
- Failure behavior: diagnostic failure does not create a customer event. Store corruption is disclosed by the external envelope, not by a row in the failed file
- Recovery: drop the recursive diagnostic, record one internal failure, stop
- Residual risk: `UNSET`
- Required test: a self-observation fixture that asserts zero customer events from internal diagnostics
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED` for the store. Telemetry’s captured `fetch` is `CURRENTLY_IMPLEMENTED` for that ping only

### T12 — Metadata secret placement

- Threat actor: an application or provider that puts tokens in headers, query strings, paths, or nested fields
- Asset: persisted records, exports, and views
- Trust boundary: allowlisted structural metadata versus secrets and content
- Abuse path: a secret in a header, query, URL, path, or encoded field is stored
- Prevention: allowlist, query stripped, path length cap with reject-not-truncate, PII-pattern and encoded-token checks on persisted strings
- Detection: `redaction_failures`. Release-blocking when implemented
- Failure behavior: the persisted record does not contain the secret. The application still returns its own output
- Recovery: the bad field is omitted. It is not masked with a reversible copy
- Residual risk: `UNSET`
- Required test: metadata redaction suite and privacy corpus, including Unicode and nested encodings
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED` as a corpus. Path-and-query stripping on the free-tier URL parser is `PARTIAL`

### T13 — Duplicate instrumentation

- Threat actor: stacked Optics copies, or co-installed OpenTelemetry, APM, or provider SDK hooks
- Asset: event identity and counts
- Trust boundary: one observation pipeline versus other hooks in the same process
- Abuse path: one call is stored more than once and inflates counts
- Prevention: `event_id` from (`producer_id`, `producer_sequence`). Two processes do not share a producer stream. An identical replay does not add a second logical event. A conflicting replay stays visible. A time-window heuristic is not adopted while the window is `NOT_SET`
- Detection: duplicate insert counted in product-health
- Failure behavior: duplicates are marked and excluded from inflated totals
- Recovery: repeat-safe import does not create a second logical event and does not change origin
- Residual risk: `UNSET`
- Required test: wrapper-order and multiple-copy fixtures
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`. In-process double-gate suppression exists and is not durable identity

### T14 — Tampered annotation

- Threat actor: the local customer, or another local user editing annotation storage
- Asset: original observation evidence
- Trust boundary: annotation store versus observation store
- Abuse path: an annotation edit changes the observation or is shown as an observation
- Prevention: separate record type. Observation bytes are not updated by annotation writes. Default proof excludes annotation text
- Detection: views must label `annotation_role` as customer-entered context. The view is not built here
- Failure behavior: a corrupt annotation is dropped from the view. The observation remains
- Recovery: delete the annotation without rewriting a proof
- Residual risk: `UNSET`
- Required test: an annotation edit that leaves the observation bytes unchanged
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`

### T15 — Rollback to a privacy-weaker schema

- Threat actor: an operator rolling software or schema backward
- Asset: privacy invariants already applied to stored records
- Trust boundary: newer privacy generation versus an older reader
- Abuse path: rollback reinterprets records under a weaker allowlist or re-emits stripped secrets
- Prevention: `privacy_generation`. A weaker writer refuses. Down-migration is forbidden
- Detection: schema version and privacy generation on product-health
- Failure behavior: refuse the weaker writer. Do not rewrite records
- Recovery: stay on the privacy-preserving file. The refusal is recorded on the external envelope. A bounded read-only adapter must not export prohibited fields and must not present a corrupt file as `COMPLETE`
- Residual risk: `UNSET`
- Required test: rollback fixtures that open a stronger store with a weaker build and fail closed
- Status: `ARCHITECTURE_DEFINED`
- Implementation: `NOT_STARTED`

## Product-boundary note

T1 through T15 do not add a block, redact, or spend-cap action to Optics. Where current source can do those things, the inventory records them as co-located Phantom Engine enforcement. Extending that enforcement is not a mitigation in this model.

## A6 threat-model exit

Fifteen cases are specified with the required fields. Residual risk is unset on purpose. Council may add cases. The producer does not fill council verdicts.
