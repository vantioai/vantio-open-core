# Dependency order

Audience: INTERNAL_RESTRICTED

Producer classification: `OPTICS_STORE_OPTION_C_VERIFIED_PLAN_READY_FOR_COUNCIL`

No dates. No durations. An edge means the successor waits for the predecessor. O-numbers are identities, so `O7` can sit later in the graph than its number suggests. The edge list in `PACKAGES.json` is the machine-readable copy.

`PKG-01` is outside the O range. It is already on this commit as a private contract. Live writers do not import it.

## 1. Edges

| Predecessor | Successor | Why it waits |
| --- | --- | --- |
| PKG-01 | O1 | Health records use the same denylist |
| PKG-01 | O2 | The store contract inserts allowlisted records |
| PKG-01 | O3 | Writer vocabulary implements the evidence contract |
| PKG-01 | O4 | Proof fields are the allowlist |
| PKG-01 | O5 | Correlation stamps fields the contract accepts |
| PKG-01 | O12 | Fail-open includes the privacy exception |
| PKG-01 | O13 | Coverage tokens stay distinct from origins |
| PKG-01 | O15 | Trends need origin rules |
| PKG-01 | O18 | Denylist before any network export |
| PKG-01 | O19 | Annotations stay off the observation origin enum |
| PKG-01 | O20 | A release posture inherits the privacy invariant |
| O1 | O10 | The query envelope reads drop and integrity state |
| O1 | O12 | Recovery disclosure and drop counts need the health model |
| O1 | O13 | Diagnostic commands read self-health |
| O2 | O6 | Binding evaluation targets a fixed interface |
| O2 | O7 | Persistence implements the interface |
| O2 | O10 | The query engine calls the interface |
| O2 | O11 | Cardinality caps apply to contract fields |
| O2 | O12 | Overload and crash behavior bind to interface failures |
| O2 | O19 | Annotation storage is separate from observation rows |
| O3 | O5 | A cross-runtime correlation claim needs one vocabulary |
| O4 | O8 | A preservation claim needs portable proof |
| O4 | O18 | Export privacy and proof rules come first |
| O5 | O10 | Correlation before session-aware querying |
| O6 | O7 | Binding selection before a file exists |
| O11 | O12 | Structural caps before fail-open claims them |
| O12 | O7 | Fail-open before the store is a default write path |
| O7 | O8 | A file exists before legacy rows are copied into it |
| O7 | O9 | Retention acts on persistent rows |
| O7 | O10 | File-backed query mode only. The memory-adapter mode does not wait |
| O7 | O20 | Upgrade posture includes schema refusal |
| O8 | O20 | Upgrade posture includes legacy compatibility |
| O10 | O14 | Freshness and completeness are fields of that envelope |
| O10 | O15 | Completeness before trends and indicators |
| O10 | O16 | Query before UI |
| O10 | O17 | Alerts read completeness |
| O12 | O17 | An Optics failure must not become an application failure page |
| O15 | O17 | Indicators before alerts that would read them |
| O16 | O19 | A visible distinction waits on the UI truth contract |

Decision gates that are not packages:

| Gate | What it blocks |
| --- | --- |
| Founder decision 9 | `O6`, then `O7` |
| Founder decision 13 | `O16` |
| Founder decision 3 | `O17` |
| Founder decision 12 | `O18` |
| Founder decision 10 | Any emitter of freshness `CURRENT` |
| Founder decision 6 | Any promote of `LEGACY_UNMARKED` |
| Founder decision 2 | Any usage or cost field |
| Founder decision 5 | Any encryption claim |
| Founder decision 8 | Any Windows ACL claim beyond owner-only intent |

## 2. Layers

Layer 0. `PKG-01` private contract, present and unwired.

Layer 1, parallel after layer 0. `O1` sketch (this packet), `O2` contract (specified, not coded), `O3` inert vocabulary source, `O4` proof library, `O5` identity rules that do not write a file.

Layer 2. `O11` after `O2`. `O12` after `O1`, `O2`, and `O11`. `O6` after `O2` and decision 9. `O13` after `O1`. Cross-runtime `O5` claims after `O3`.

Layer 3. `O7` after `O6` and `O12`. This layer is the first layer that could create a database. This packet does not enter it.

Layer 4. `O8` and `O9` after `O7`. File-backed `O10` after `O7`. Memory-adapter `O10` can start from layer 2 once `O5`, `O2`, `O1`, and `O12` are accepted.

Layer 5. `O14` and `O15` after `O10`.

Layer 6. `O16` after decision 13 and `O10`. `O17` after decision 3, `O15`, `O10`, and `O12`. `O18` after decision 12, `PKG-01`, and `O4`. `O19` storage rules after `O2`; the visible distinction after `O16`.

Layer 7. `O20` after `O7` and `O8`. It authorizes no release.

## 3. Path before any database file

1. `PKG-01` allowlist. Present as a private contract. Not wired into live writers.
2. `O2` store contract accepted, including an in-memory adapter and a rejected SQL string. Not written by this packet.
3. `O1` health model accepted. The sketch in this packet is the design boundary. It is not the code.
4. `O11` structural caps, then `O12` fail-open behavior for contract and interface failures.
5. Founder decision 9, then an `O6` selection record. This packet selects nothing.
6. Only a later force may open `O7`.

Option C ratification is step 0 of the architecture record. It is not step 6.

## 4. Path before a migration claims evidence was preserved

1. `PKG-01`, then `O4` portable proof.
2. `O7` store file, under the path in section 3.
3. `O8` explicit copy, with originals kept.

## 5. Path before a trend or a UI

1. `PKG-01` origin rules.
2. `O5` correlation.
3. `O10` query envelope.
4. `O15` trends after `O10`.
5. `O16` UI after `O10` and after decision 13.

## 6. Work that can wait

These do not block `O7` once section 3 is met, and `O7` itself stays unauthorized:

- `O9` retention commands. Default retention is unbounded.
- `O13` coverage command.
- `O4` as a customer-facing export. It is required before an `O8` preservation claim.
- `O16`, `O17`, `O18`, `O19`’s visible distinction, and `O20`.

## 7. Work that must not run in parallel

| Pair | Order |
| --- | --- |
| `O2` and `O7` | Contract first. No database in the contract force |
| `O6` and `O7` | Binding selected first |
| `O12` and `O7` default-path enablement | Fail-open first |
| `O4` and an `O8` preservation claim | Proof first |
| `O7` and `O8` | Store first |
| `O5` and session-aware `O10` | Correlation first |
| `O10` and `O16` | Query first |
| `O1` and `O13` commands | Self-health first |
| Decision 9 and `O6` | Decision first. This packet is not that decision |
| Decision 3 and `O17` | Decision first |
| Decision 12 and `O18` | Decision first |
| Decision 13 and `O16` | Decision first |
| Any O package and CLI `0.3.24` | The CLI stays frozen. No O package patches it |

## 8. Critical path inside this packet

This packet completes the Option C verification, the `O1` sketch, and the `O1`–`O20` graph. The next code, when a separate force is authorized, is still `O2` as an interface and an in-memory adapter, with `PKG-01` as the allowlist. That code is not in this commit.
