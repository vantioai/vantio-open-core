# Optics production plan — program boundary

Audience: INTERNAL_RESTRICTED

Producer role: planning producer only. This agent does not sit the independent council, does not self-assign a council pass, and does not open Gate 8.

Producer identity: Cursor cloud agent `bc-e139d03a-e24f-5d71-95e9-2a71dc8ac633`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-e139d03a-e24f-5d71-95e9-2a71dc8ac633

Producer classification: `OPTICS_STORE_OPTION_C_VERIFIED_PLAN_READY_FOR_COUNCIL`

That classification means this planning packet is ready for a separate council. It is not a council verdict, not an implementation authorization, and not evidence that a store exists.

## 1. Locked input

| Item | Value verified at planning time |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `587f3b94d47ea958f91d3a99125cd55931d995f1` |
| Commit subject | Merge pull request #63 from `vantioai/implementation/optics-pkg02-unit-a-vocabulary` |
| `origin/main` | Same commit |
| Planning branch | `cursor/optics-store-option-c-plan-c633` |
| Writable path | `docs/planning/optics-production/` only |
| Store record | `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY` |
| Gate 8 | Closed |
| CLI | `@vantio/cli` `0.3.24` |
| Python | `vantio-agent-sdk` `3.1.0` in `packages/vantio-agent-sdk-py/pyproject.toml` |
| Node SDK | `@vantio/agent-sdk` `0.2.4` |
| Evidence contract | `@vantio/optics-evidence-contract` `0.0.0-unstable-pre-1.0` |
| Vocabulary package | `@vantio/optics-record-vocabulary` `0.0.0-unstable-pre-1.0`, private |
| Schema | `schema_status` `unstable-pre-1.0` |

Input hashes are in `PRODUCTION-MANIFEST.json`.

## 2. What this force does

- Verifies the ratified Store Option C record and the implementation constraints that record already states.
- Isolates any future database behind the application store contract (`O2`, the existing `PKG-05` interface). This packet does not write that interface.
- Sketches `O1` self-health design boundaries from the accepted A5 architecture.
- Orders Optics production packages `O1`–`O20` by dependency. O-numbers are identities. Execution order is the graph in `04-DEPENDENCY-ORDER.md`.
- Maps each O package onto an existing PKG, roadmap section, or architecture section. The map does not add a mechanism.

## 3. What this force keeps closed

- Product code, package manifests, tests, workflows, tags, GitHub releases, npm, PyPI, TestPyPI, and Twine.
- A database file, a Node SQLite binding, a schema, WAL, a migration, record conversion, and an in-memory adapter.
- CLI `0.3.24`. This plan does not patch, republish, or retag it.
- Live imports of `@vantio/optics-evidence-contract` or `@vantio/optics-record-vocabulary` into the CLI, the Python SDK, or the Node SDK.
- UI, a daemon, OTLP, SIEM export, alerting, retention commands, and `vantio doctor`.
- Gate 8. A8 stays a historical name for the earlier planning packet. This force does not start an implementation.
- Founder decisions 2–13.
- Architecture files, the roadmap file, and public docs.

`schema_status` stays `unstable-pre-1.0`.

## 4. Product boundary

Optics is free, in-process observation of bounded structural metadata. It records destination, process, timing, size, and trace context. It does not store prompts or completions. It does not block, redact, or cap a call.

Phantom Engine is enforcement. Co-located block, redact, and cap branches in the current interceptor are outside this plan. A future store must not become a host-enforcement path.

## 5. How to read O1–O20

The A8 planning council already accepted seventeen implementation packages, `PKG-01` through `PKG-17`. This packet does not replace that map and does not split those packages into new builds.

`O1`–`O20` is the production dependency view this force was asked to write:

- Sixteen O packages name an existing PKG as the satisfaction owner.
- `PKG-01` is an external predecessor. It is already on this commit as a private contract. It is not re-planned as an O package.
- `O11` and `O14` are ordering constraints inside `PKG-12` and `PKG-10`. They are not a second implementation.
- `O19` and `O20` are roadmap workstreams the architecture already specifies. They have no new package.

Unit A of `PKG-02` is on this commit because pull request #63 merged. The notes in that merge still say the producer classification `OPTICS_PKG02_UNIT_A_READY_FOR_COUNCIL` is not a council verdict. This plan does not upgrade that sentence. The vocabulary package is private. Live products do not import it.

## 6. Council handoff

`10-INDEPENDENT-COUNCIL-REPORT.md` is `PENDING_COUNCIL`. A separate agent fills it. This producer stops at `OPTICS_STORE_OPTION_C_VERIFIED_PLAN_READY_FOR_COUNCIL`.
