# 01 — Council verdict, T4 MCP and tool-call awareness

## 1. Header

- **Reviewer model family:** Claude Opus. The design author is Grok, a different model family.
- **First review observed (UTC):** 2026-10-16T15:52:02Z. Verdict `COUNCIL_UNSAT`.
- **Re-review observed (UTC):** 2026-10-16T16:01:07Z. Verdict `COUNCIL_SAT`, with required wording corrections N1–N10.
- **Wording re-check observed (UTC):** 2026-10-16T16:04:25Z. Verdict `WORDING_SAT`.
- **Subjects:**
  - `docs/programs/gap-t4-mcp-awareness/00-DESIGN.md`
  - `docs/programs/gap-t4-mcp-awareness/02-RISK-REGISTER.md`
- **Product code at this verdict:** none. `packages/vantio-mcp-awareness/` does not exist.
- **After `WORDING_SAT`:** one sentence was added to design section 8. A dropped inbound response on the single-stream gate also waits on the workload's own timeout. The reviewer had already marked that sentence optional and covered by risk R12. It does not change a seat.

## 2. First review

Seats S1, S2, S3, S4, and S6 were `UNSAT`. Seats S5, S7, S8, and S9 were `SAT`.

Blocking defects:

- **B1.** Duplicate-key detection covered `name` only. Retain caps and nested argument keys were undefined. Literal prefix was not distinguished from a filesystem jail.
- **B2.** Tool descriptions and `initialize` instructions were not scanned. A rug-pull block that waited for a later `tools/call` would already have forwarded the description.
- **B3.** Raw tool names, argument key names, methods, and an unkeyed sha256 of a string id could retain or confirm attacker-controlled text.
- **B4.** `tapReadable` could switch a paused readable to flowing mode. Web streams were named as tap targets. Outbound stdio had no observe path that stayed off the write path.
- **B5.** Session eviction, pending overflow, `catalog_unknown`, a missing server default, a dropped deny rule, a rule without `tool`, and a withheld outbound request had no stated outcome.
- **B6.** The host path claimed an enforce withhold on an asynchronous copy, named a 64 KiB per-CPU ring, and treated TLS socket bytes as if they were plaintext.

## 3. Re-review seats

| Seat | Verdict | Ground |
| --- | --- | --- |
| S1 Threat model | SAT | Duplicate keys anywhere are spoof-class. Retain caps, nested keys, and literal prefix are stated. Descriptions and instructions are scanned. Rug-pull block withholds the list frame. Read and write stay operator-classified |
| S2 Retention | SAT | Raw tool name, key name, and method are kept only from operator policy or the closed method set. String ids are HMAC under a per-process key. Observed description and schema digests are compared and discarded |
| S3 No proxy hop | SAT | `observeBuffer` takes a caller-owned copy. `tapReadable` attaches only when the readable is already flowing and already has a data listener, and it refuses a web stream. Both gates are opt-in and in-process |
| S4 Failure modes | SAT | Eviction, pending overflow, unknown catalog, missing default, incomplete policy, missing `tool`, and both withhold shapes have a stated observe outcome, enforce outcome, and reason. A mode typo cannot select enforce |
| S5 Hints do not grant permission | SAT | `server_id` comes from the host integration. `readOnlyHint` and the first list are not approval. An unmatched result cannot update the catalog |
| S6 eBPF and Phantom Engine | SAT | Host path is an Observe contract. No ring size is chosen. TLS plaintext is limited to future uprobes. Host enforce names no hook. No kernel JSON parser |
| S7 Scope | SAT | In-process code is not Phantom Engine and is not enrolled-host enforcement. The detector is structure, not content scoring |
| S8 Bounds, rollback, gates | SAT | Numeric caps, tombstones, rollback by not loading the package, and the approval-gate list are concrete |
| S9 Claims | SAT | No prices. No README, website, or Shipped edit. Pin `e0b19d55` is untouched. "Verified" is limited to the proof script's assertions |

Blocking defects on re-review: none.

## 4. Wording corrections the re-review required

Confirmed present at `WORDING_SAT`:

| Id | Correction |
| --- | --- |
| N1 | Timestamps are `2026-10-16T16:03:15Z`. The stamp `2026-10-16T16:05:00Z` is withdrawn |
| N2 | Walk-cap withhold is risk R5, not only the 256 KiB frame cap |
| N3 | `error.message` and `error.data` are unscanned, in the design and in R7 |
| N4 | A pinned call before `tools/list` does not compare a pin. Risk R19 |
| N5 | Production `createRuntime()` does not accept an HMAC key |
| N6 | The pair-gate error is written only at a frame boundary. Section 17 tests a partial child frame |
| N7 | The single-stream gate never synthesizes a replacement, in either direction |
| N8 | `tombstone_overflow` is not cleared. Risk R17 |
| N9 | HMAC values are not correlated across processes. Risk R18 |
| N10 | `interceptor.cjs` and the `@vantio/gate-mcp` README stay unchanged. Risk R20 |

Accepted residuals remain R1–R20 in `02-RISK-REGISTER.md`.

## 5. Verdict

`COUNCIL_SAT`

This verdict covers the design packet only. It is not a review of implementation commits. Those require a separate review of the final head.
