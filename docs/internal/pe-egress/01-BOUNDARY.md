# Track 6 boundary

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_EGRESS_PROGRAM_REVISION_READY_FOR_COUNCIL`

That classification means the branch is ready for a separate council. It is not a council verdict, not a merge, and not a customer proof.

## What this force contains

- `packages/pe-egress-authority/` — private decision package `@vantio/pe-egress-authority` at `0.0.0-internal`.
- `tests/pe-egress/` — direct, adversarial, and isolation tests.
- `docs/internal/pe-egress/` — this packet.

The package is not a pnpm workspace member. `@vantio/cli` `0.3.24` does not import it. The npm publish allowlist does not name it.

## What this force keeps closed

- Customer deploy, stranger-host execution, and announcements.
- Credential create or rotate, and any money movement.
- Reopening CLI `0.3.24` or changing sealed Python `3.1.0` bytes.
- Copying Phantom customer-manual bodies into this public repository.
- A formal SLSA claim, a certification claim, or an internal-to-external proof promotion.
- Live eBPF load, `bpftool`, kernel verifier runs, image build, Helm install, and cluster apply.
- Wiring this authority into `vantio run`, the interceptor, or the Python SDK.
- A self-assigned council pass. `03-PENDING-COUNCIL.md` stays `PENDING_INDEPENDENT_COUNCIL`.

## Evidence rule

`ALLOWED` is emitted only when the supplied case satisfies the policy on a path that can see the dimensions the policy constrains. A missing fact stays `EVIDENCE_UNAVAILABLE`. A path that cannot carry out a decision stays `ENFORCEMENT_GAP` or `UNSUPPORTED`. A contradictory or unclassifiable case stays `UNKNOWN`. None of those four results is rewritten to `ALLOWED`.

The package opens no socket and does not read the network.
