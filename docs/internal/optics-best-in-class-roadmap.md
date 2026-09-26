# Optics best-in-class roadmap

Internal planning capture only. This document does not authorize implementation, a release, a tag, a seal, or a publish. It makes no public claim. It assigns no dates and no timelines.

Out of scope for this capture: `packages/vantio-cli` (frozen at 0.3.24, LIVE_AND_CLIENT_PROVED) and the in-progress Python 3.1.0 diagnostic model work (PR #53).

## Section 1 — Data architecture

**FOUNDATIONAL.** Highest priority. Sequence this section before other roadmap items.

1. Local storage backend migration from per-run JSON files to an embedded local store (e.g., SQLite), keeping JSON as the export/proof format only. Rationale: current design does not scale to real customer call volume; search/tail/diff currently require file scanning.
2. Retention and pruning policy:
   - `vantio config set retention.max-age <duration>`
   - `vantio config set retention.max-size <size>`
   - `vantio prune --dry-run` / `vantio prune`
   - Must default to unbounded retention unless the customer configures a limit (never silently delete evidence).

## Section 2 — Correlation and analysis

**FUTURE.**

3. Session/workflow grouping: allow multiple related calls to be correlated under one parent session/run identifier distinct from a single call's trace ID. Design the schema change required; do not implement.
4. Cross-run trend/comparison command (e.g., `vantio trends --since=<window>`) showing error-rate and duration drift over time using only already-stored structural metadata (never inspecting content).
5. Usage/cost metadata: investigate whether token/usage fields are exposed by supported providers in structural response metadata (not body content inspection). Requires an explicit separate product decision before any implementation — design memo on feasibility and privacy boundary only.

## Section 3 — Local visual surface

**FUTURE, STRATEGIC.**

6. A fully local, localhost-only, read-only web UI (`vantio ui`) rendering the same on-disk evidence: timeline, session grouping, filters. No account, no cloud, no external network. Highest-leverage "feels mature" item; own dedicated future release — not folded into CLI or Python patch releases.

## Section 4 — CLI ergonomics

**FUTURE, LOW RISK, SMALL SCOPE EACH.**

7. Confirm and document `NO_COLOR` / `--no-color` support across all commands.
8. Shell completion: `vantio completion bash|zsh|fish`.
9. `vantio legend` explaining every status glyph/color/label.
10. Pager-awareness for long tail/search (`$PAGER`, `--no-pager`).
11. `--quiet` mode distinct from `--json` (exit code only).

## Section 5 — Coverage transparency

**FUTURE.**

12. `vantio status --coverage`: list every currently supported HTTP client/provider on this runtime, and explicitly state what is not covered.

## Section 6 — Security hard gates

Schedule with real priority. Not implemented in this capture.

13. Metadata redaction test suite: fixtures with tokens in headers/query strings; assert persisted record NEVER contains them. Same severity class as prompt/completion non-storage; release-blocking when implemented.
14. Fail-open reliability gate: prove if Optics write/observation path throws or is killed mid-run, wrapped app output/behavior is byte-identical to running without Optics. Document target max per-call overhead (e.g. "<5ms p99") to validate once implemented.

## Section 7 — Compatibility and documentation

**FUTURE.**

15. Versioned config file (e.g. `vantio.config.json`) as alternative to flags/env for redaction, retention, telemetry defaults.
16. Documented flag/schema deprecation policy once JSON schema exits unstable-pre-1.0.
17. Generated single reference (e.g. `vantio help --all`) so `--help` and public docs cannot drift.
18. Runnable multi-agent example repository for prospective customers.
