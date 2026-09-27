# Track 6 implementation report

Audience: INTERNAL_RESTRICTED

Producer classification before council: `PE_EGRESS_PROGRAM_REVISION_READY_FOR_COUNCIL`

This classification means the branch is ready for a separate council. It is not a council verdict, not a merge, and not a statement that a host was enrolled.

## What landed

Private package `@vantio/pe-egress-authority` at `0.0.0-internal`. `evaluate` decides a supplied egress case and returns one `PE_EGRESS_V1` token. It does not attach to a process.

The path catalog covers the application surfaces named by the interceptor and the Python wrap, plus host declarations taken from the wave-1 coverage matrix. Host rows require a supplied observation. This force does not execute them.

## Checks

From the repository root:

```sh
node --test tests/pe-egress/*.test.cjs
```

The producer run reported 72 tests, 4 suites, and 0 failures.

The revision closes six council holds. An unverified TLS peer stays `ENFORCEMENT_GAP`. An application path that cannot see the resolved address returns `ENFORCEMENT_GAP` for IP-list membership and for a DNS answer set constrained by that list. An empty redirect list is `EVIDENCE_UNAVAILABLE`, and a hop list that does not start at the destination is `UNKNOWN`. Exact IP blocks use the same integer address as CIDR blocks, including a leading-zero spelling and an IPv4-mapped form. A host observation with `dropped: false` returns `ENFORCEMENT_GAP` (`host_did_not_drop`) for a redirect hop, a port, or a TLS name mismatch. The new tests assert the result token. `optimistic_allow` stays false.

## Hard-stop attestations

- No CLI `0.3.24` or Python `3.1.0` source change, and no version bump.
- No live interceptor or SDK wiring.
- No network call and no eBPF load.
- No customer deploy, stranger host, announcement, credential change, or money movement.
- No customer-manual body copied into this repository.
- No formal SLSA or certification claim.
- No promotion of this internal decision into external proof.
- Draft pull request only. Not marked ready. Not merged.
- Council is a separate agent. This producer did not run it.
