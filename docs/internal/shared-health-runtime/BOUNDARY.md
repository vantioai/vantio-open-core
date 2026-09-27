# Shared health runtime boundary

Audience: INTERNAL_RESTRICTED

Producer classification: `SHARED_HEALTH_RUNTIME_READY_FOR_COUNCIL`

That classification means this runtime is ready for a separate council. It is not a council verdict, not a live enforcement result, and not evidence that any host was proved in this force.

Producer identity: Cursor cloud agent `bc-b14b44fd-76ad-52bf-ab51-5e0a065d88ae`, model Grok 4.7.

## 1. Locked input

| Item | Value |
| --- | --- |
| Writable repository | `vantioai/vantio-open-core` |
| Base | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Bound catalog | `c1de02538f66df94d58aef58bf0ec8459ae797ad` |
| Binding meanings | `vocabulary_status` `BOUND_TO_WS4_CATALOG`; `workstream_4` `RETRIEVED_AND_BOUND` |
| Package | `packages/shared-health-runtime/` |
| Tests | `tests/shared-health-runtime/` |

The catalog commit records `bound_into_pe_packet` false. The Phantom Engine packet on this base is the binding. This force does not edit that packet or the catalog directory.

## 2. What this force does

- Produces the twelve runtime states from caller evidence and catalog facts.
- Consumes those records and refuses a green bit.
- Keeps every emitted record on the evidence fields named by the force.
- Pins freshness to `UNKNOWN` under `FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN`.

## 3. What this force keeps closed

- Live Phantom Engine enforcement, eBPF loads, probes, and loader control.
- Edits under `docs/planning/shared-health-vocabulary/` and `docs/planning/phantom-engine-production/`.
- Edits to `docs/governance/STATUS-TOKENS.json`.
- CLI `0.3.24`, Node SDK `0.2.4`, and Python SDK `3.1.0`.
- Unit D, Unit E, O7, and I3.
- Customer deploy, stranger-host execution, publish, and announcements.
- A council pass. `docs/internal/shared-health-runtime/INDEPENDENT-COUNCIL.md` stays `PENDING_INDEPENDENT_COUNCIL`.
- Merge of this pull request.

## 4. Green bit

`audit.green` is false on every record this runtime seals. `consume` returns `green: false`. A healthy token is a vocabulary result of a caller-supplied protection fact. It is not a measured latch and it is not independent verification.
