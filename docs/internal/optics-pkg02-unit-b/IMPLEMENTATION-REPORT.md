# PKG-02 Unit B implementation report

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification before council: `OPTICS_PKG02_UNIT_B_READY_FOR_COUNCIL`

This classification means the Unit B branch is ready for a separate council agent. It is not a council verdict, not a merge, and not a statement that a writer exists.

The producer did not sit the council.

## What landed

Private package `@vantio/optics-node-adapter` at `0.0.0-unstable-pre-1.0`. That version matches the unstable posture. It is not a bump of CLI `0.3.24`, Node SDK `0.2.4`, Python `3.1.0`, `@vantio/optics-evidence-contract`, or `@vantio/optics-record-vocabulary`.

The package is not in `pnpm-workspace.yaml`. It calls `validateEvidence` and `validateBytes` on copies. Live CLI sources do not import it.

## Checks

From the repository root:

```sh
node --test tests/optics-node-adapter/*.test.cjs
node --test tests/optics-record-vocabulary/*.test.cjs
```

The direct suite scores all 34 Unit A fixtures. Expected `optics_status` has to be on the detached envelope or event. `optics_health` is not accepted in its place. `cli-empty-call-file` stores `NOT_OBSERVED` on the envelope. `inherited-trace` stores `UNAVAILABLE` on the envelope. The suite also checks absent, null, and unknown readings, byte zero versus missing versus explicit zero, status dimensions, and origin preservation.

The adversarial suite checks a prohibited canary, an enforcement token, a 65-call bound, an own getter and an inherited accessor that must not run, a path that must not be opened, a refused writer option, caller-object isolation, fail-open application results, an oversized session, a non-zero timestamp offset, null versus omitted span, frozen `displayCall` still returning `SUCCESS`, and a real CLI `0.3.24` run file whose bytes do not change when the adapter package is loaded and a copy is adapted. Object, JSON text, and bytes of that file share `optics_health` `NOT_OBSERVED` and `trace_id_basis` `ASSERTED_CONTEXT`.

## Revision

Council finding `OPTICS_PKG02_UNIT_B_NEEDS_REVISION` on `56ec23c3dd4c80d52596767eb557931768824d48` is addressed here. Text and byte copies use the Unit A snapshot. Envelope-only fixtures store `optics_status` on the detached record. Inherited accessors are not read. This revision's classification before council is `OPTICS_PKG02_UNIT_B_REVISION_READY_FOR_COUNCIL`. That is not a council verdict, not a merge, and not a writer.

## Hard-stop attestations

- No CLI, Python SDK, or Node SDK source change, and no version bump.
- No PKG-01 behavior change.
- No live writer and no live emission.
- No SQLite, migration, UI, daemon, exporter, or alerting.
- No stable schema.
- No release candidate, seal, publish, tag, or announcement.
- No Units D, E, or F.
- Draft pull request only. Not marked ready. Not merged.
- Council is a separate agent. This producer did not run it.
