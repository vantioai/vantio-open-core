# @vantio/pe-egress-authority

PRIVATE. NOT SHIPPED. INTERNAL_PROOF.

This package is the Track 6 egress authority for council review. It decides a supplied case. It does not attach to a process, load eBPF, open a socket, or ship inside `@vantio/cli`.

`evaluate` returns one token from `PE_EGRESS_V1`:

`ALLOWED`, `DENIED`, `REDACTED`, `CONTAINED`, `REVOKED`, `UNSUPPORTED`, `ENFORCEMENT_GAP`, `EVIDENCE_UNAVAILABLE`, `UNKNOWN`.

A missing fact is not `ALLOWED`.
