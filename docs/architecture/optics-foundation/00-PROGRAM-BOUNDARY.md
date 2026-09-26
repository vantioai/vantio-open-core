# Optics Foundation — program boundary

Audience: INTERNAL_RESTRICTED

Producer: architecture producer for stages A0–A6. This agent is not the independent council.

Source main SHA verified before this branch was created: `d6b74d41808a43f251d6de46e1313625a025d16d` (merge of PR #54).

Branch: `architecture/optics-foundation-a0-a7`

Writable path for this Force: `docs/architecture/optics-foundation/` only.

## Purpose

Turn the merged Optics best-in-class requirements roadmap into a decision-ready architecture for the Optics evidence foundation: current-state inventory, evidence and privacy contract, operational store and portable proof, schema and migration, correlation and bounded query, self-observability and reliability, threat model, decision pack, and implementation gates.

The roadmap file `docs/internal/optics-best-in-class-roadmap.md` is requirements input. It is not implementation authorization. This pack does not change that file.

## Product boundary

Optics is free, in-process observability. It records bounded structural metadata: destination, process, timing, size, and trace context. It does not store prompts or completions. It does not enforce. It can be bypassed outside supported paths.

Phantom Engine is enforceable application-path policy and host-level authority. Gate is the internal name for that enforcement function set. This architecture does not move enforcement into Optics, and it does not describe Optics records as host enforcement.

The current Node interceptor and Python HTTP observe module contain co-located enforcement branches that run only when a non-public control plane and API key are present. Those branches are inventoried as existing source. They are outside the Optics foundation contract. This pack does not extend them.

## What this Force does

- Records what the source, tests, and docs do today, including disagreements.
- Defines the evidence model, privacy allowlist, store recommendation, proof boundary, schema rules, correlation and query contract, reliability contract, threat model, and gates.
- Leaves numeric performance budgets at target `NOT_SET`.
- Marks unresolved product choices as `NEEDS_FOUNDER_DECISION`.
- Leaves independent council seat verdicts unfilled.

## What this Force does not authorize

- Product code, package version changes, CLI reopen, Python seal or build, PyPI, TestPyPI, Twine, npm publish, git tags, or GitHub releases.
- Credentials, live store implementation, SQLite creation, migrations, or record conversion.
- `vantio ui`, `vantio doctor`, a daemon, an OTLP exporter, alerting, or background update behavior.
- A stable schema declaration. Every schema in this pack is unstable and pre-1.0.
- Public copy, announcement, or website changes.
- Treating internal proof, a producer pass, or a healthy local view as customer validation.
- Stage A8, or any implementation Force.

## Hard stops attested by the producer

| Stop | Attestation |
| --- | --- |
| No product code | This change is Markdown and JSON under `docs/architecture/optics-foundation/` only. |
| No package change | No `package.json`, lockfile, or Python project metadata is modified. |
| No CLI reopen | `@vantio/cli@0.3.24` is not patched, republished, or retagged. |
| No Python seal or publish | `vantio-agent-sdk` 3.1.0 source is read, not sealed, built, or uploaded. |
| No release action | No tag, GitHub release, npm publish, or PyPI action. |
| No credentials | No secret is read or written. |
| No store implementation | No database file, migration, or conversion is executed. |
| No UI, daemon, OTLP, or alerting | Those surfaces are named only as future dependents or explicit non-goals. |
| No stable schema | `schema_status` remains `unstable-pre-1.0`. |
| No invented numeric budgets | Budget targets stay `NOT_SET`. The roadmap example “<5ms p99” is not adopted. |
| No silent architecture decisions | Open choices are listed as unresolved Founder decisions. |
| Council not performed | `10-INDEPENDENT-COUNCIL-REPORT.md` is `PENDING_SEPARATE_COUNCIL`. |
| A8 not started | No implementation tasks are filed. |

## Stage order

A0 inventory, A1 evidence and privacy, A2 store and proof, A3 schema and migration, A4 correlation and query, A5 reliability, A6 threat model and gates. A later document in this set does not authorize skipping a blocked earlier stage. None of A0–A6 is blocked.

## Evidence tiers

This pack assigns none of: `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, `CUSTOMER_VALIDATED`.

Producer completion is not proof. Requirement status in `TRACEABILITY-MATRIX.json` is only `TARGET_DESIGN`, `ARCHITECTURE_DEFINED`, `ARCHITECTURE_BLOCKED`, or `NEEDS_FOUNDER_DECISION`.
