# Pending independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `PE_EGRESS_PROGRAM_READY_FOR_COUNCIL`

The producer does not sit this council and does not write the verdict.

## Checklist

- The diff is the private package, `tests/pe-egress/`, and `docs/internal/pe-egress/`.
- CLI `0.3.24` and Python `3.1.0` are unchanged.
- The package is absent from `pnpm-workspace.yaml` and from `.github/workflows/npm-publish.yml`.
- `evaluate` returns only the nine `PE_EGRESS_V1` tokens.
- Direct tests cover each token. Adversarial tests cover redirect, DNS change, open-socket retry, spend, dry-run, unscanned bodies, sensitive deny, sockets, descendants, patterns, credentials, TLS, host observations, cgroup attach, uprobe observe-only, and prefix boundaries.
- `this_force_executed_host` and `this_force_executed_network` stay false.
- No customer manual body, no eBPF load, no stranger host, no publish, no merge in this force.

## Out of scope for the verdict

A pass on this packet does not authorize a customer deploy, a kernel run, a CLI release, or a claim that host enforcement was re-proved.
