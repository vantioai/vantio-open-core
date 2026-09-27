# Pending independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `PE_EGRESS_PROGRAM_REVISION_READY_FOR_COUNCIL`

The producer does not sit this council and does not write the verdict.

## Checklist

- The diff is the private package, `tests/pe-egress/`, and `docs/internal/pe-egress/`.
- CLI `0.3.24` and Python `3.1.0` are unchanged.
- The package is absent from `pnpm-workspace.yaml` and from `.github/workflows/npm-publish.yml`.
- `evaluate` returns only the nine `PE_EGRESS_V1` tokens.
- Direct tests cover each token. Adversarial tests cover redirect, DNS change, open-socket retry, spend, dry-run, unscanned bodies, sensitive deny, sockets, descendants, patterns, credentials, TLS, host observations, cgroup attach, uprobe observe-only, and prefix boundaries.
- Revision tests cover an unverified TLS peer, an application path that cannot see the resolved address, redirect hop integrity, integer IP spelling, and a host observation that did not drop. They also cover a redirect with no destination hostname and an allow-list DNS answer set with no destination IP. Those assertions check the result token. `optimistic_allow` remains false and is not the check.
- `this_force_executed_host` and `this_force_executed_network` stay false.
- No customer manual body, no eBPF load, no stranger host, no publish, no merge in this force.

## Out of scope for the verdict

A pass on this packet does not authorize a customer deploy, a kernel run, a CLI release, or a claim that host enforcement was re-proved.
