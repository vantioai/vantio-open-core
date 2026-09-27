# Track 6 architecture

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_EGRESS_PROGRAM_READY_FOR_COUNCIL`

These notes are the producer's architecture record for an independent council. They are not a council finding.

## Decision

`evaluate(case)` returns one `result` from `PE_EGRESS_V1`:

`ALLOWED`, `DENIED`, `REDACTED`, `CONTAINED`, `REVOKED`, `UNSUPPORTED`, `ENFORCEMENT_GAP`, `EVIDENCE_UNAVAILABLE`, `UNKNOWN`.

`authority_disposition` is the policy outcome when the path cannot carry it out. `would_result` repeats that outcome on a gap. `live_wire_action` is an annotation for the existing interceptor spellings `BLOCKED_HOST`, `BLOCKED_SIZE`, `BLOCKED_SPEND`, `DRY_RUN_BLOCKED_*`, `REDACTED`, `ALLOWED`, and `ENFORCEMENT_GAP`. It is not a tenth result, and it is not an Optics display token. This packet does not add names to `docs/governance/STATUS-TOKENS.json`.

`SUCCESS` is not a result. A case that smuggles `result` or `success` is `UNKNOWN`.

## Order

The first proved condition wins.

1. Malformed case, unknown path, or a smuggled result: `UNKNOWN`.
2. Declared unsupported path (browser, QUIC, unmanaged cloud, host not enrolled): `UNSUPPORTED`.
3. Raw-syscall path, or a bypass kind other than browser: `ENFORCEMENT_GAP`. Browser bypass is `UNSUPPORTED`.
4. Policy field types that cannot be classified: `UNKNOWN`. Missing `enforce` or `scope`: `EVIDENCE_UNAVAILABLE`.
5. `policy_loaded: false`: `ENFORCEMENT_GAP` (`fail_open_policy_not_loaded`). Missing latch: `EVIDENCE_UNAVAILABLE`.
6. Host plane without a supplied observation: `EVIDENCE_UNAVAILABLE`. A drop claimed with no attach, or on the uprobe path, is `UNKNOWN`.
7. Open-socket retry, then a descendant the path does not govern, then destination, protocol/port, HTTP method/path, direct-socket visibility, credential, pattern, redirect, DNS, TLS, sensitive data, payload size, child-process resource, spend.
8. If the policy would stop or redact and `enforce` is false: `ENFORCEMENT_GAP` (`enforce_off`). If `dry_run` is true: `ENFORCEMENT_GAP` (`dry_run_pass_through`). If `dry_run` was omitted on a stopping result: `EVIDENCE_UNAVAILABLE`.
9. A cgroup path with no attach, or forwarded cgroup id 0, becomes `ENFORCEMENT_GAP` (`cgroup_skb_not_attached`) after the policy outcome is known. The uprobe path becomes `ENFORCEMENT_GAP` (`uprobe_observe_only`). Missing evidence is not replaced by that gap.

`DENIED` on an application path is limited to what that path can see. An IP list, a TLS peer name, a sensitive-text deny, and credential revocation are not interceptor behaviors. Those stay `ENFORCEMENT_GAP` unless the case supplies `evidence: "supplied"` and a `control_id` for a control that actually applied. Redaction of materialized text is a path capability on fetch, undici, Node HTTP, HTTP/2 writes, Python HTTP, and inline child-tool argv. Streams, files, and pipes are `ENFORCEMENT_GAP` (`unscanned_body`).

Application scope `llm_and_named` leaves a destination that is neither catalog-scoped nor list-named as `UNSUPPORTED`. Scope `all_egress` on that same path is `ENFORCEMENT_GAP` (`out_of_scope_pass_through`), because the wrap does not see general traffic. A host observation is not filtered by the LLM catalog.

## Dimensions

Every decision carries the same dimension keys: destination, protocol/port, HTTP method/path, direct socket, redirect, retry, DNS, TLS, descendant, credential, sensitive data, payload size, resource, spend, pattern, bypass, and path support. A key the case does not raise is `not_in_attempt`. A key that decided the result is `triggered`, `gap`, `unavailable`, `unsupported`, or `unknown`.

## What a host `ALLOWED` means

It means the supplied observation and the policy agree, and no gap rule fired. It does not mean this force loaded a program, verified a kernel, or enrolled a node. `evidence_class` is `SUPPLIED_CASE_EVIDENCE`. `this_force_executed_host` and `this_force_executed_network` are false.

## Collision with other vocabularies

| Spelling | This packet | Elsewhere |
| --- | --- | --- |
| `ALLOWED` | Policy permits the supplied case on a path that can see the constraints | SDK action token. Not a protection state |
| `DENIED` | The authority's stop. Wire annotation may be `BLOCKED_HOST`, `BLOCKED_SIZE`, or `BLOCKED_SPEND` | Not an Optics display token |
| `UNKNOWN` | Unclassifiable or contradictory evidence | Honest absence. Not `protected` |
| `SUCCESS` | Not emitted | Optics display for a stored observation |
