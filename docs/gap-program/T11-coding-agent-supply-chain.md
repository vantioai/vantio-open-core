# T11 — Coding-agent and supply-chain defense

Audience: INTERNAL

Phase: 1 design only. No feature code.

Track label: Roadmap

Written: 2026-10-16T15:48:08Z

## Question

How does an enrolled host notice that a plugin, hook, or skill changed, refuse to start the agent on a risky repo configuration, and block a child the agent tooling did not declare?

## Current evidence

`packages/pe-host-authority/src/descendant.cjs` can spawn a child in unit code and record that the child did not receive `VANTIO_TRACE_ID` or `VANTIO_ALLOW`. The function sets `kernel_executed: false`. `childWiden` rejects a widen with `REJECTED_NOT_AN_AUTHORITY_INPUT`. That is a unit behavior in this process. It is not a kernel block of an unknown child.

`scripts/aws/lab-guests/descendant_b1.py` and the GCP guest scripts under `scripts/gcp/` are lab batteries. This force does not run them. Program rules forbid an AWS or GCP lab from this agent. Their presence is not a pass.

The installer path leaves path deny disabled and traffic control audit-only. Optics does not see editor plugins. Gate does not hash a repository.

T0's charter is own-stack hygiene around OpenClaw CVE-2026-25253. This track depends on that charter and does not restate the CVE.

## Design

Before a declared coding agent starts, the host hashes a manifest of paths the customer listed. The default list, which the customer can shrink only through a T10 `WIDEN` because shrinking it loosens the check:

- `.cursor/`
- `.claude/`
- `.codex/`
- `AGENTS.md` and `CLAUDE.md` when present
- project MCP configuration files the customer names
- skill directories the customer names
- `.git/hooks/` and the path in `core.hooksPath` when set

A path that does not exist is recorded as absent. Absence is a stable state. A path that appears later is a change.

The manifest stores a hash per file, the file mode, and whether the file is a symlink. The hash is SHA-256 of the bytes. Symlink targets are recorded and are not followed outside the repository root. A symlink that escapes the root fails the check.

Risky configuration means a difference from the last approved manifest, not the mere presence of a hook or a local command. A hook or an MCP command that is already in that manifest may start. Any one of these, when it is not in the manifest or its hash has changed, refuses the start:

- a git hook that is executable
- an MCP server entry whose transport is a local command
- a skill or plugin file whose hash is not in the last approved manifest
- a hook or skill that changed since that manifest

Refusal is fail closed: the agent process is not started. A human may approve the new manifest through T10. Until that approval is applied on the host, the old manifest remains the only one that can start the agent. Timeout on that approval is deny, so the new manifest does not become active.

Unknown children:

- The enrolled agent and the tool binaries named in the approved manifest are the known set.
- A child whose executable is outside that set is an unknown child.
- An unknown child is blocked on the enrolled host once this control is implemented. The block uses the existing enrolled decision path. It does not add a second enforcement engine.
- The child's egress is denied with the child's identity set to `UNVERIFIED` unless T6 has a verified reference for it. T6 does not let the child inherit a widen.

TOCTOU: hash the manifest, refuse on mismatch, then hash again immediately before the start. A change between the two hashes aborts the start. Phase 3 of the program is where that race is tested. This phase names it.

## Threat model

| Threat | Response |
| --- | --- |
| Repo commit adds a start hook | Hash mismatch refuses the start |
| Symlink points at a file outside the repo | Escape check fails closed |
| Agent spawns a shell not in the manifest | Unknown child is denied once the control exists |
| Agent renames a known binary over an unknown one | The second hash before start, and the executable identity at exec, must match the manifest. A mismatch denies |
| Operator disables the check to unblock a deadline | Disabling the check is a loosen and needs T10. Timeout denies the loosen |
| Compromised company agent runtime | T0. This track does not trust an unreviewed runtime as the hasher |
| Lab script graded as a product block | This document refuses that grade |

## Failure modes

Fail closed on start and on unknown children. A hasher error, an unreadable file, a symlink escape, a manifest that fails to parse, or a missing manifest denies the start. Reason: starting on an unknown toolchain is the risk this track exists to refuse.

Observe of the refusal fails open for the log line and closed for the process. The agent does not start.

If the block mechanism is not loaded, the host does not report the agent as covered. The start is still refused by the userspace gate in front of the process. Reason: a missing kernel program must not become an allow. The userspace gate is the same enrolled decision path, not a new product.

## Edge cases

- Generated files that change every start, such as a local cache inside `.cursor/`. The customer manifest can mark a cache path as volatile only through an approval. A volatile path is not a silent default.
- Two repositories in one workspace. Each root has its own manifest. A hash of the wrong root is a mismatch.
- The agent is started outside `vantio run` and outside the enrolled cgroup. Optics already states that skip is possible. Phantom Engine coverage is the enrolled cgroup. An unenrolled start is not reported as protected. T3 inventory is what shows that gap. This track does not claim the unenrolled start was blocked.
- Hook is a binary already running. The control applies at the next start. It does not kill a process this design has not been authorized to kill.

## Memory footprint

The manifest is a list of hashes. A later implementation caps the file count and the bytes read per file. Over the cap, the start is refused. This document does not set the cap as a measured product limit. The hasher must not load an entire repository into memory to hash one file.

## eBPF verifier limits

No new program in phase 1. A later unknown-child block has to fit the verifier. If the verifier rejects it, the userspace start gate still refuses, and the loader does not install a partial program that allows unknown execs. Instruction counts are measured at that later load. They are not estimated here.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | Own-stack hygiene for the hasher and for any company coding-agent runtime. CVE work stays in T0 |
| T1 | The start gate runs on an enrolled host. Stranger-host proof is T1 |
| T2 | Sandbox verification is where the unknown-child denial should be shown |
| T3 | Inventory lists the agent, the known tools, and the unenrolled gap |
| T4 | MCP command entries are the risky config this track flags. T4 sees the tool call after start. T11 decides whether the start happens |
| T5 | Unknown-child egress is part of the egress drills |

T6 labels the agent and refuses a child widen. T10 approves a manifest change. T12 shows the refusal reason before a human is asked to approve.

## Rollback

Restore the last applied manifest from the host's copy. Do not adopt the manifest that failed the check. If the last applied manifest is missing, the start stays refused until a human approves a new one. Rollback does not delete the hash log. Rollback does not loosen the default path list.

## Proof plan

Phase 2, local fixtures only, no cloud lab:

- A temp git repo with an executable `.git/hooks/pre-commit` is refused.
- A one-byte change to `AGENTS.md` after approval is refused until a new approval is applied.
- A symlink from `.cursor/hooks` to a path outside the repo is refused.
- A child executable not in the manifest is recorded as denied by the userspace gate. The test does not claim a kernel `execve` deny unless the Phantom Engine program is actually loaded, which this phase does not do.
- `descendant.cjs` remains a unit test and is not cited as this proof.

## Risks

- Volatile-path exceptions become the default and hide hook changes.
- The userspace gate is skipped by a direct exec on an unenrolled cgroup, and a dashboard still shows the host as covered.
- AWS or GCP descendant batteries are re-run by a later agent that does not own the lab slot.

## Approval gates

- No cloud lab. No install on a host the company does not own.
- Founder decision before the start gate is placed on a company workstation.
- Draft PR only.

## Council

Verdict: PASS_WITH_NONBLOCKING_NOTES

Recorded from the Claude Opus review of design head `3c2c581a48ef001c3ef78df232926d6c236acb88`. Detail is in `COUNCIL-VERDICT.md`. The producer does not sit the council.
