# Implementation report

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL`

This classification means the branch is ready for a separate council. It is not a council verdict and not a statement that the live loader changed.

## What landed

Private package `@vantio/pe-ingress-authority` at `0.0.0-internal`. It is not in `pnpm-workspace.yaml`. Live CLI `0.3.24` and Python `3.1.0` do not import it.

The evaluator classifies listeners with the P0b envelope rule, then applies the authority contract in `03-AUTHORITY-CONTRACT.md`. Session helpers cover revoke, restart, and rollback. No source file in the package starts a process or writes a file.

## Checks

From the repository root:

```sh
node --test tests/pe-ingress/*.test.cjs
```

The producer run of that command reported 59 tests and 0 failures. A later revision on the same branch closed six hold-path gaps found by council `bc-b72399a9-4af2-507e-945d-2ee6a0278c12` (`PE_INGRESS_PROGRAM_NEEDS_REVISION`). A second council, `bc-f1ef6a5f-d98d-5fd5-9549-7bf00dd7eed2`, returned `PE_INGRESS_PROGRAM_NEEDS_REVISION` on `4ef50ae72c6a463bc1c3d8a72fa48d4c6da31df1`. This revision closes those four paths: a missing or empty later-behavior trace does not join the accept; a `cgroup_escape` or an unauthorized behavior is recorded when `post_accept` is an array or `behaviors` is one object; escape and deny are recorded when `accept` is null; a null `expected_listeners` entry is `stale_policy` and does not throw. An authorized behavior with no `cgroup_id` stays `post_accept_unjoined` in those shapes. The six earlier hold paths stay closed. Revision classification for this pass: `PE_INGRESS_PROGRAM_REVISION_READY_FOR_COUNCIL`. That is not a council verdict.

## Hard-stop attestations

- No edit to `vantio-phantom-engine` and no live loader mutation.
- No customer deploy and no stranger-host execution.
- No CLI `0.3.24` or Python `3.1.0` source or version change.
- No inbound packet drop and no `ActionTaken` of `ALLOWED` or `BLOCKED`.
- No shared freshness token other than `UNKNOWN`.
- No protection-state invention and no `ingress_protected_claim`.
- No credential create, rotate, or identity-provider call.
- Draft pull request only. Not marked ready. Not merged.
- Council is a separate agent. This producer did not run it.
