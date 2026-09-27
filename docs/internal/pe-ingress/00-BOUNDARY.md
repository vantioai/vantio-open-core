# Track 5 — Phantom Engine ingress authority boundary

Audience: INTERNAL_RESTRICTED

Producer role: inventory, architecture notes, and an in-process authority implementation. This agent does not sit the independent council, does not self-assign a council pass, and does not authorize a load, a publish, or a deploy.

Producer identity: Cursor cloud agent `bc-9ff0b560-ba53-5e6d-b8cc-0f62237258f5`, model Grok 4.7.

Producer classification: `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL`

That classification means this branch is ready for a separate council. It is not a council verdict, not a live enforce result, and not evidence that a loader, kernel, or host was proved in this force.

## 1. Locked input

| Item | Value |
| --- | --- |
| Writable repository | `vantioai/vantio-open-core` |
| Open-core base | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Base subject | Merge pull request #83, Founder MAIN ACCEPTED Wave 1 close |
| Branch | `cursor/pe-ingress-authority-58f5` |
| Private product tip read | `vantioai/vantio-phantom-engine` `631e435315cd780d83d3259e111893c1d0569bc3` |
| This force executed the private tree | No |

Writable paths:

- `packages/pe-ingress-authority/`
- `tests/pe-ingress/`
- `docs/internal/pe-ingress/`

The package is private, version `0.0.0-internal`, and not a pnpm workspace member.

## 2. What this force does

- Inventories the private ingress surface that was readable on the tip above.
- Records an authority contract for supplied evidence: listener class, workload identity, executable integrity, listener-policy version, post-accept behavior, health, revoke, restart, and rollback.
- Implements that contract in this process. Packet effect stays `NOT_APPLIED`. Evidence decision stays `observed`.
- Leaves `07-PENDING-COUNCIL.md` as `PENDING_INDEPENDENT_COUNCIL`.

## 3. What this force keeps closed

- Edits to `vantio-phantom-engine`, including `vantio-loader` and the eBPF sources.
- A live load, a loader reload, `bpftool`, a kernel verifier run, and `cargo build` of the Phantom crates.
- Customer deploy, stranger-host execution, and clean-host script execution.
- Credential create or rotate, money movement, and identity-provider calls.
- CLI `0.3.24`, Python `3.1.0`, and sealed or published Python bytes.
- A merge. Council is a separate agent.
- Copying `docs/operations-guide.md` (blob `1b973342b3bf7f6aa6cdad70de49fa6e26db0077`, class `CUSTOMER_SHIPPED`).

`live_loader_mutated` is false on every result. An input that asks to mutate the live loader is refused.

## 4. Evidence rule

Sentences about Phantom-Box, WSL2, or local `kind` in the private tree are `OBSERVED_FROM_REPOSITORY_EVIDENCE`. This force did not re-execute them. A `HELD` result is a decision about the evidence object passed to `evaluateIngress`. It is not an eBPF verdict and it is not protection state `protected`.
