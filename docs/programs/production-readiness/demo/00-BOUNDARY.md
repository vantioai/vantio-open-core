# WS6 — Investor demo design boundary

Audience: INTERNAL_RESTRICTED

Design producer: Cursor cloud agent `bc-da04b99d-56bf-55bb-b780-0531b9d953d7`, model Grok 4.7. That agent designed the first pack. It does not sit the independent council and does not assign a council pass.

This revision is a later docs-only edit on the same draft. It is not that producer and not council `bc-0b0275f0-8be5-507d-b4bb-2f0b22ddd8c0`.

Revision classification: `INVESTOR_DEMO_DESIGN_REVISION_READY_FOR_COUNCIL`

Council on tip `c2026a9c8d42130705f434faa0f79d922f473d31` returned `INVESTOR_DEMO_DESIGN_NEEDS_REVISION`. This revision answers that return. The classification means the directory is ready for a separate council again. It is not a council verdict, not a customer demonstration, not Wave 2 authorization, and not implementation.

The first producer classification on that tip was `INVESTOR_DEMO_DESIGN_READY_FOR_COUNCIL`.

## Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Base commit | `1df51d29a65a3913f1ef1f29fc00ead1335ef7a0` |
| Base subject | Add the Head of Product hiring package |
| Writable path | `docs/programs/production-readiness/demo/` only |
| Force | WS6 investor demo design |
| Wave | Design and scaffolding. Wave 2 implementation is not authorized |

## Founder beat source

The WS6 force asks for story beats 1–18 from a Founder Master Program. That program text is not in this repository at the base commit. It was not in the uploaded WS6 force. It was not in the uploaded master control plane force. `02-STORY-BEATS.md` therefore records `founder_text: ABSENT` on beats B01–B18. The eighteen beats are the deterministic room sequence this force proposes. They are not a quotation of founder-authored titles. A later force replaces the titles when founder text is in the tree. The simulation-label rule stays.

## What this force does

- Specifies a deterministic investor room that shows one Optics CLI path and states the product boundary in speech.
- Requires a simulation label on every synthetic event before an investor sees it.
- Records the CLI 0.3.24 demo behavior measured on the design host, including the missing origin field.
- Leaves claim rows and limitation rows as ledgers a council can check.
- Leaves Wave 2 as a scaffold marked not authorized.

## What this force does not authorize

- Product code, package versions, CLI patches, Python seal, tags, npm, PyPI, or a GitHub release.
- A live provider call, a Phantom Engine install, a kernel program, a cluster, or a bank connection.
- Copying a fixture into `~/.vantio/runs/`.
- Counting a demo file as customer activity.
- A council pass, customer validation, or an evidence tier above the local design-host transcript.

## Hard stops

| Stop | Attestation |
| --- | --- |
| Docs path only | Files in this change are under `docs/programs/production-readiness/demo/`. |
| CLI 0.3.24 | Unchanged. The design host ran the existing binary. It did not patch it. |
| No synthetic enforcement | No fixture uses `BLOCKED_HOST`, `BLOCKED_SIZE`, `BLOCKED_SPEND`, `REDACTED`, `ALLOWED`, or `DRY_RUN_BLOCKED_*` as a demo event. |
| No unlabeled event file | The failure-injection example sits inside a labeled wrapper. It is not a run log. |
| No registry contact | This force did not query npm or PyPI. Version facts are cited from files in the tree. |
| No Phantom Engine execution | This repository does not contain that product. The script does not enroll a host. |

## Document order

1. `01-SIMULATION-LABEL-RULE.md`
2. `02-STORY-BEATS.md`
3. `03-DEMO-SCRIPT.md`
4. `04-OPERATOR-RUNBOOK.md`
5. `05-RESET-OUTLINE.md`
6. `06-EXPECTED-OUTPUTS.md`
7. `07-FAILURE-INJECTION-OUTLINE.md`
8. `08-CLAIM-LEDGER.json`
9. `09-LIMITATION-LEDGER.json`
10. `10-WAVE2-SCAFFOLD.md`
11. `11-COUNCIL-SLOT.md`
12. `scaffolding/labeled-event-envelope.json`

Index: `DEMO-MANIFEST.json`.
