# T8 — OCSF, OTLP export, SIEM connectors, and WORM validation

Audience: INTERNAL

Phase: 1 design only. No feature code. This track does not merge the observability branch and does not copy its exporter.

Track label: Roadmap

Inherited lab label: Lab-only for the scoped 2026-10-10 drill. `product_otlp_export_authorized` remains false. That drill is not this track's label.

Written: 2026-10-16T15:48:08Z

## Question

How should enforcement and observe events leave the host in OCSF and OTLP shapes toward Sentinel, Splunk, syslog, and a webhook, and how should a WORM check be defined so a mutable local file cannot pass it?

## Inherited packet

Search on 2026-10-16 across `vantio-open-core`, `vantio-phantom-engine` `docs/`, `vantio-enterprise` `docs/`, and `vantio-deploy` `docs/` found one zero-cost local OTLP and SIEM drill. It is not a file dated 9 October 2026. It is the packet on `cursor/optics-observability-5bed` at `ef3a33a`, recorded 2026-10-10, draft pull request 191. Zach accepted a scoped pass that day. The acceptance is an exclusion list, not an unscoped pass.

Use these files on that branch as the plan of record. This document does not restate their procedures.

| Path on `ef3a33a` | Role |
| --- | --- |
| `docs/observability/COVERAGE.md` | Row results, gaps, and the scoped exclusion |
| `docs/observability/TRUST-BOUNDARY.md` | In-process attestation is not a receiver-verifiable signature |
| `docs/observability/CLAIM-WORDING.md` | Which sentences the scoped lab can support |
| `docs/observability/setup/` | Local collector, Jaeger, Tempo, syslog, webhook, OpenSearch, Grafana, and the HEC and Datadog mocks |
| `packages/optics-export/SCHEMA.md` | Candidate schema `vantio.observability.export` `1.0.0` |
| `deploy/observability/matrix/` | The lab runner |

Public docs on this base, including `docs/governance/canonical/product-boundary.md` and `docs/optics-otel-mapping.md`, still say there is no OTLP exporter. `packages/optics-otel-i3` on main is a default-disabled traces adapter and says the public docs remain unchanged. This design leaves both statements in force.

Inherited destinations and the limit this track accepts:

| Destination in the 2026-10-10 drill | What T8 does with it |
| --- | --- |
| Collector contrib 0.136.0 and 0.103.0, Jaeger 1.62.0, Tempo 2.7.1, Loki 3.4.2, Grafana 11.5.2, local webhook, local rsyslog | Keep as the lab method for a later phase. Do not rerun it here |
| Prometheus series scraped from the collector | The drill says this is not an Optics event count. T8 does not call it one |
| OpenSearch 2.19.1 | Lab only. Its own TLS listener was a gap. nginx in front of plaintext is not OpenSearch TLS |
| Splunk HEC mock and Datadog mock | Mocks. The products were not used. A Splunk product connector stays Roadmap |
| Microsoft Sentinel | Absent from the drill. Designed below. Not tested |
| OCSF | Absent from the candidate schema. Designed below. Not encoded |
| WORM | The local ledger is append-oriented NDJSON. The drill does not validate WORM. The validation below expects a mutable file to fail |

Inherited rules T8 keeps:

- Prompts, completions, bodies, headers, and query strings are not export fields. A canary that survives projection is dropped.
- `offer()` does not block the workload when the receiver is down. `sent` stays 0 until a real delivery. An HTTP 200 HTML page is not delivery.
- Remote plaintext is refused. TLS does not fall back to plaintext.
- The OTLP attribute `vantio.attestation` with the label `in-process` is not a signature a receiver can check.
- A co-resident caller that can bind its own object is an accepted exclusion. Closing it needs a signature from Phantom Engine or the Enterprise evidence signer over the canonical event bytes, with the private key outside the process. No production signing root is used. The public pin stays `e0b19d55`.
- The ten-minute closed-port run is a lab note: 25731 offers, max offer 4.792 ms, RSS delta 48533504 bytes inside the 64MB bound the drill used, queue 8, dropped 2851, sent 0, then a drain of the same queued batches. Those numbers are the drill's notes. They are not a product service level.

`@vantio/optics` on main does not gain an exporter from this document.

## Design

### Event shape

Start from the candidate schema on `ef3a33a`. Add the T6 fields `issuer`, `agent_identity`, `owner`, and `verification` when T6 exists. Until T6 is implemented, those fields are specified and absent, and an exported enforce event is incomplete by this design. Do not invent a workload id to fill them. The drill's `vantio.workload.id` stays an opaque lab field, not an owner.

OCSF is a second projection of the same projected event, pinned to a schema version chosen in phase 2. Proposed classes, to be rechecked against that pin before any encoder exists:

| Vantio record | Proposed OCSF class |
| --- | --- |
| Supported API call metadata | API Activity |
| Enrolled egress allow or drop | Network Activity |
| Process start or child seen by the host | Process Activity |

The projection uses the same privacy allowlist as the OTLP candidate. OCSF `actor` is the T6 reference. Raw assertions are not OCSF fields. Numeric class UIDs are copied from the pinned schema at implementation time, not from memory in this document.

### Connectors

| Connector | First shape | Label inside this track |
| --- | --- | --- |
| OTLP | The candidate HTTP/JSON, HTTP/protobuf, and gRPC transports on the inherited branch | Roadmap for product use. Lab-only only for the already recorded drill |
| syslog | RFC 5424 as the drill ran it, local listener | Roadmap for product use |
| webhook | Local listener, mTLS in the drill's final build | Roadmap for product use |
| Splunk | Keep the HEC mock. A Splunk product connector is a later force | Roadmap |
| Sentinel | Customer-operated syslog or CEF forwarder the customer already runs. Vantio does not open an Azure tenant, does not call Microsoft, and does not add a required proxy | Roadmap |

The Sentinel shape reuses the syslog connector so a customer forwarder can land events in Sentinel. A direct Azure Monitor ingestion API is a later option behind its own founder gate. It is not the first shape, because it needs a tenant this program will not create.

Delivery state is `QUEUED`, `SENT`, or `NOT_SENT`. A failed receiver leaves the workload path running and leaves the claim at `NOT_SENT`. That is the drill's rule, kept here.

### WORM validation

Local NDJSON is mutable by a process that can write the file. The product spec calls a live Spanner write `TARGET_DESIGN`. This track does not run that write, does not touch a GCP project, and does not call the local file WORM.

The validation fixture, when a later phase writes it, does three things:

1. Append a known event to a lab copy of the ledger format.
2. Truncate or rewrite that file from the same uid that can write it.
3. Expect the validator to report `MUTABLE_LOCAL_LEDGER` and to refuse an intact result.

A validator that says intact after step 2 is a failed test. There is no path in this design where the local file passes.

Spanner, or any other immutable store, stays out of phase 2 until a founder force names it and a lab the program allows is free. Lab agent `bc-8b310b16` owns the current lab slot. `6d3ce580` is not the working seal.

## Threat model

| Threat | Response |
| --- | --- |
| Export becomes a second copy of prompts | Allowlist from the inherited schema. Canary drop stays |
| Receiver down is reported as delivered | `sent` stays 0. HTML HTTP 200 is `NOT_SENT` |
| Co-resident process forges an event | Inherited exclusion. External signature is a later close, not this phase |
| SIEM mapping puts the raw T7 secret in an attribute | Secret and placeholder bytes are forbidden, same rule as canaries |
| Operator reads a truncated local file as a complete history | WORM validator returns `MUTABLE_LOCAL_LEDGER` |
| Sentinel connector opens a vendor account | Out of scope. Syslog to a customer forwarder only |

## Failure modes

The workload path fails open when the exporter cannot deliver. Reason: a SIEM outage must not become a required proxy and must not stop an enrolled agent by itself. The claim fails closed: undelivered events stay `NOT_SENT`, and a mutable ledger stays `MUTABLE_LOCAL_LEDGER`.

An exporter bug that would block `offer()` for longer than the drill's lab bound is a failed design. The drill's closed-port offers stayed under 5 ms in that lab note. Phase 2 reuses that method. It does not promote the number to a product limit in this document.

WORM validation fails closed on any write error, short read, or hash mismatch. It does not repair the file and it does not replace it with an empty store. That matches the Optics corrupt-store rule already in `docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md`: preserve bytes, do not present a partial salvage as complete.

## Edge cases

- Schema major version moves. Readers of major 1 ignore unknown attributes, as the candidate schema says. A breaking change is `2.0.0` with the deprecation window that schema already states. OCSF projection follows the same version, or it is dropped for that event and the event is `NOT_SENT` to the OCSF connector only.
- Fan-out to syslog and webhook. One failure does not mark the other destination sent.
- Identity fields absent because T6 is not built. The OCSF `actor` is omitted and the event is tagged incomplete. It is still not a prompt.
- Clock on the collector differs from the host. The host timestamp stays the event time. The collector receipt time is a separate field if the connector adds one.

## Memory footprint

The inherited drill bounded the closed-port RSS delta by 64MB and recorded 48533504 bytes for nine exporters. Phase 2 of T8 uses that same lab bound as a gate for a rerun. This document does not claim the product stays inside 64MB on a customer host. Queue length in the drill stayed at 8, with further events dropped and counted. A full queue drops and counts. It does not grow without a bound, and it does not block the workload.

## eBPF verifier limits

Export is userspace. No new eBPF program. Kernel events that already exist are inputs to the projection. Adding T6 strings inside a kernel map waits for the T6 verifier rule: reject the load rather than run an identity-blind allow.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | Exporter and collector configs are company code. T0 applies. This track does not ship them |
| T1 | No export from a stranger host is evidence of enrollment |
| T2 | A sandbox that can forge events is the co-resident exclusion. T8 does not close it |
| T3 | Inventory names the workload id the drill already carries. T3 must not be replaced by a free-typed string from the event |
| T4 | Tool-call metadata joins the same allowlist. Tool arguments that are prompts or secrets are not exported |
| T5 | Egress of the exporter itself is an egress. A denied exporter destination stays `NOT_SENT` and must not open a side channel by retrying through an unnamed host |

T6 supplies `agent_identity` and `owner`. T7 forbids secret bytes. T10's approval record is an event type under the same allowlist, without prompts.

## Rollback

Product rollback is the current main behavior: no public OTLP exporter, I3 disabled unless a caller passes the explicit enable flags the I3 readme already requires, and those flags are not turned on here.

Lab rollback, when a later phase runs the inherited matrix, is the drill's own enable-test-disable cycle: stop the local receivers, disable the exporter, confirm `sent` does not increase. This phase does not run that cycle.

WORM rollback is deleting the lab copy of the fixture file. It does not touch a customer ledger and does not truncate a file to "clean it".

## Proof plan

Phase 1 proof is `node scripts/gap-program/check-p1-design.mjs`, which checks that this document cites `ef3a33a` and does not authorize product OTLP.

Phase 2 proof, not authorized by this packet:

- Re-run the inherited matrix only on a local host, with the same mocks, and attach the new evidence beside the 2026-10-10 notes.
- Add an OCSF projection test that fails if a prompt canary or a T7 placeholder secret survives.
- Add the truncate fixture and require `MUTABLE_LOCAL_LEDGER`.
- Sentinel is a syslog fixture against a local listener. No Azure call.

## Risks

- Merging `cursor/optics-observability-5bed` and reading the scoped pass as product authorization.
- Calling the Prometheus scrape an Optics metric.
- Calling local NDJSON WORM because it is append-oriented in the happy path.
- A Sentinel design that quietly needs a paid tenant or a vendor thread.

## Approval gates

- Founder decision before `product_otlp_export_authorized` can change. This packet does not ask for that change.
- No Splunk product, Datadog product, or Sentinel tenant.
- No Spanner write and no GCP project.
- No public doc edit. Draft PR only.

## Council

Verdict: PENDING_INDEPENDENT_REVIEW

The producer does not write the verdict.
