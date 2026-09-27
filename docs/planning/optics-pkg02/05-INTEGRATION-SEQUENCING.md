# Optics PKG-02 — integration sequencing

Audience: INTERNAL_RESTRICTED

This file recommends an order. It does not create the versions and it does not start the work.

## 1. Facts that constrain the order

- The live Node writer is `packages/vantio-cli/bin/interceptor.cjs` inside `@vantio/cli` `0.3.24`. That package is frozen. A Node writer change is a future CLI version.
- `@vantio/agent-sdk` `0.2.4` does not write a run log. Leading with it would invent a second Node record path.
- `vantio-agent-sdk` `3.1.0` is merged source. It is unpublished from this force. It has no release candidate and no seal. Its tests lock `opticsStatus` `SUCCESS` on recorded calls. Editing it would change that locked behavior and would violate the Python hard stop.
- The two languages already disagree on empty runs, byte zeros, `schema_status`, process ids, `failure_kind`, and timestamp form. Activating either writer first would publish that dialect as the contract.
- CLI 0.3.24 display will show `SUCCESS` for any call row. Customers who keep that CLI cannot be told that a new file is understood.
- Rollback, client proof, and claim integrity get worse if both writers flip in one change.
- The private contract already maps both envelope shapes. That mapper is the adapter. It is not live.

## 2. Options

| Option | What it would do | Why it is not the selection |
| --- | --- | --- |
| A. Node first | A future CLI writes contract records before Python does | The only Node writer today is the frozen CLI. Going first still needs the shared fixtures, and Python readers would not exist. |
| B. Python first | A future Python writes contract records before Node does | Python 3.1.0 cannot be the vehicle. Its current `SUCCESS` default would become the de facto optics token if it shipped first. |
| C. Parallel branches, shared conformance, including activation | Both future writers land together | Activation together is a big-bang. The shared corpus is the part worth keeping. |
| D. Adapters, then activation | Inert adapters and fixtures first. Each writer turns on in its own later release | Matches frozen CLI, unpublished Python, independent versions, and rollback. |

## 3. Recommendation

Select option D. Use the shared-corpus half of option C for the inert adapter stage only.

Order:

1. Unit A. Shared vocabulary fixtures. No writer import.
2. Unit B and Unit C in parallel branches. Node adapter and Python adapter, both inert, both scored on the same fixtures.
3. Unit F. A reader that can explain legacy files and future files without writing either. It can ship with the adapters. It still does not rewrite files.
4. Unit D. Node writer activation on `PKG02-FUTURE-CLI-UNASSIGNED` only, after B and F, and only with a client proof that CLI 0.3.24 is not the reader of the new file.
5. Unit E. Python writer activation on `PKG02-FUTURE-PYTHON-UNASSIGNED` only, after C and F. Not on 3.1.0.

Units D and E do not share a commit. Either can roll back without the other. Neither includes `@vantio/cli` `0.3.24`.

`PKG02-FUTURE-NODE-SDK-UNASSIGNED` is not in this order. The local Node record stays on the future CLI until a Founder decision says the SDK should write one.

## 4. Version placeholders

| Surface | Current | First eligible placeholder |
| --- | --- | --- |
| CLI writer | `0.3.24` frozen | `PKG02-FUTURE-CLI-UNASSIGNED` |
| Node SDK | `0.2.4` non-writer | `PKG02-FUTURE-NODE-SDK-UNASSIGNED` (not selected) |
| Python SDK | `3.1.0` unpublished, not to be altered | `PKG02-FUTURE-PYTHON-UNASSIGNED` |
| Evidence contract | `0.0.0-unstable-pre-1.0` private | Unchanged by activation. Still not a stable schema. |

No placeholder is a version that exists. This file does not bump `package.json` or `pyproject.toml`.

## 5. Claim integrity

Until Unit D or Unit E is separately authorized, shipped, and proved, the product claim stays the claim of the frozen writers: local metadata on supported paths, no prompts, no enforcement by Optics. A planning `FULL` cell is not that proof. `scope_complete` stays false. Windows, macOS, and WSL stay unclaimed by this packet.
