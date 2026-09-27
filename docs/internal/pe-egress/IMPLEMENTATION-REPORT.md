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

The producer run reported 76 tests, 4 suites, and 0 failures.

The first revision closed six council holds. An unverified TLS peer stays `ENFORCEMENT_GAP`. An application path that cannot see the resolved address returns `ENFORCEMENT_GAP` for IP-list membership and for a DNS answer set constrained by that list. An empty redirect list is `EVIDENCE_UNAVAILABLE`, and a hop list that does not start at the destination is `UNKNOWN`. Exact IP blocks use the same integer address as CIDR blocks, including a leading-zero spelling and an IPv4-mapped form. A host observation with `dropped: false` returns `ENFORCEMENT_GAP` (`host_did_not_drop`) for a redirect hop, a port, or a TLS name mismatch. The tests assert the result token. `optimistic_allow` stays false.

The second revision closes the two holds still open at `970b56db`. A missing destination hostname is a redirect mismatch, so a blocked one-hop path is not `clear` / `single_hop`. On `host_tc_enrolled` that hop is `ENFORCEMENT_GAP` (`host_did_not_drop`) when `dropped` is false, and `UNKNOWN` (`host_drop_unexplained`) when `dropped` is true. The same shape on `app_fetch` is not `ALLOWED`. An observed two-hop chain with no hostname anchor and no block-list hit is `UNKNOWN`. A hostname that is present, including `203.0.113.10`, still mismatches a different hop as `UNKNOWN` (`redirect_unclassifiable`), and an empty hop list stays `EVIDENCE_UNAVAILABLE`. An application allow-list with no destination IP and DNS answers `203.0.113.9` plus `198.51.100.9` is `ENFORCEMENT_GAP` (`dns_answer_not_visible`). Supplied `203.0.113.009` and `::ffff:198.51.100.10` on an application path stay `ENFORCEMENT_GAP`.

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
