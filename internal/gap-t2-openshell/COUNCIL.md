# T2 council — NVIDIA OpenShell 0.1.x and Phantom Engine

Audience: INTERNAL_RESTRICTED

Phase: 1 of the Three-Phase Sandbox Protocol. This commit is the design and the verdict. It contains no reconciliation code.

Recorded: 2026-10-16T15:48:53Z

Open-core base: `69671e97fa359b685232ec7dd4e9fb4badc7be57`

Phantom Engine tip read for this council: `deb6faa33e5cbb887622df5017ce74d2571fa9e8` (2026-10-15T18:40:35Z)

Public pricing in every artifact from this track: Contact Vantio. No prices are copied here.

## Verdict

**differentiate**

Phantom Engine and OpenShell answer different questions and sit in different places. The deployment shape on a host Vantio enrolls is side by side: OpenShell sandboxes the agent, and Phantom Engine keeps an independent kernel record of that host. The join between those records is Rogue Reconciliation. Folding Phantom Engine into the OpenShell supervisor, middleware, or gateway would make the check depend on the path it is supposed to check, and it would put a required relay on the Phantom Engine data path.

| Option | Council result |
| --- | --- |
| integrate | Stop. No middleware, no fork, no credential broker, no shared policy prover, no NVIDIA contact. |
| coexist | The allowed deployment shape: same enrolled Linux host, separate trust mechanisms, no code coupling. |
| differentiate | The product verdict. Independent kernel observation beneath the sandbox, joined by Rogue Reconciliation. |

Positioning line, internal only: "Independent verification beneath any agent sandbox." See `POSITIONING.md`.

## Labels

| Result | Label | Why |
| --- | --- | --- |
| This comparison | Recorded from the sources below on 2026-10-16. It is a document, not a live interop run. | Sources were read. The two runtimes were not executed together. |
| Reconciliation logic that follows this design | Lab-only, after the fixture proof exists. | The join can run on this runner against recorded fixtures. |
| Phantom Engine beneath a live OpenShell sandbox on an enrolled host | Roadmap | This runner is not an enrolled host. See the feasibility probe. |

Remaining risks are in `RISK-REGISTER.md`. This document does not say the design is unbreakable or audited.

## Scope of the later code

The later commit may add a userspace join under `internal/gap-t2-openshell/`. That join:

- Reads a closed snapshot of recorded Phantom Engine observations, OpenShell OCSF records, and Gate records.
- Emits `BYPASS_INDICATOR` when an in-scope kernel observation has a correlation subject and a usable clock, and neither an OpenShell record nor a Gate record matches it.
- Stays on Observe. It does not enroll a host, load an eBPF program, open a socket, or change a policy.
- Covers supported AI workloads on enrolled Linux machines only. A kernel row whose cgroup is outside the run's binding table is out of scope.
- Drops every field that is not on the output allowlist, and rejects a snapshot that carries conversation fields or secret fields.
- Does not vendor Phantom Engine. `CONTRIBUTING.md` keeps the engine out of this repository.

## Sources

Read 2026-10-16. OpenShell citations are the v0.1.4 documentation set unless a row names another tag. v0.1.0 is the GA tag. v0.1.4 is the newest stable release tag at research time.

| Source | Identity | Used for |
| --- | --- | --- |
| [NVIDIA technical blog, 28 Sep 2026](https://developer.nvidia.com/blog/add-runtime-controls-to-ai-agents-with-nvidia-openshell/) | Alex Watson, Ali Golshan | Gateway, supervisor, sandbox, MCP inspection, OCSF, prover, child processes |
| [NVIDIA Newsroom, 28 Sep 2026](https://nvidianews.nvidia.com/news/open-agent-safety-platform) | Open Agent Safety Platform | OpenShell software versus Sentry on BlueField-4 |
| [GitHub NVIDIA/OpenShell](https://github.com/NVIDIA/OpenShell) | Apache-2.0. Tag `v0.1.0` is `496ebba293f5cc2bb2753444dddd534f0b4aeb6a` (2026-09-25). Tag `v0.1.4` is `5a7728c304b5528e954e9ae900cf21f84e1a12b1` (2026-10-13). Milestone closed 28 Sep 2026. | License, release, README mechanism summary |
| [PyPI openshell 0.1.0](https://pypi.org/project/openshell/0.1.0/) | Apache-2.0, Python >=3.11 | Package license and the 0.1.0 description |
| [Architecture v0.1.4](https://docs.nvidia.com/openshell/v0.1.4/about/architecture) | Landlock, seccomp user notification, runtimes, authentication | Enforcement location and credential boundary |
| [Sandbox policies v0.1.4](https://docs.nvidia.com/openshell/v0.1.4/how-it-works/policies/overview) | Landlock, process, network proxy | When each control takes effect |
| [Network rules v0.1.4](https://docs.nvidia.com/openshell/v0.1.4/how-it-works/policies/network-rules) | `protocol: mcp` | MCP method and tool rules |
| [Policy prover v0.1.4](https://docs.nvidia.com/openshell/v0.1.4/how-it-works/policies/prover) | `openshell-prover`, SMT | What a boundary check covers |
| [OCSF JSON export v0.1.4](https://docs.nvidia.com/openshell/v0.1.4/observability/ocsf-json-export) | OCSF 1.8.0, best-effort | Evidence shape and loss |
| `vantioai/vantio-phantom-engine` `docs/product-spec.md` | blob `25db3754ab75508083e0763c9c6d92254e7967a5`, header 6 Oct 2026 | Scope, local verification versus managed-cloud target |
| `vantioai/vantio-phantom-engine` `architecture_state.md` | blob `417ea2b29198a1bde81a21082a150528c2a0679a`, header 1 Jul 2026, body includes later rows | Program list and status matrix |
| `vantioai/vantio-phantom-engine` `scripts/demo_bypass_reconciliation.sh` | blob `5335da9fed695242e124d21ec4358ce474c8578f` | Existing kernel-versus-app `BYPASS_INDICATOR` |
| This repo `docs/observe-only.md`, `docs/PRODUCT_LINEUP.md`, `docs/planning/boot-hold/PE-COMPANION.md`, `packages/vantio-gate-mcp` | open-core `69671e97` | Public fence and Gate dry-run limit |

The 15 Oct 2026 Phantom Engine commit message on `deb6faa3` describes a cgroup-ancestor correction. This council did not re-run that lab. A commit message is repository evidence.

## Comparison

### Enforcement location

OpenShell places the agent inside a sandbox boundary. On the current Linux backend the workload uses one non-root identity and no Linux capabilities. Landlock limits filesystem access. Seccomp user notification stages TCP opens and DNS queries. The sandbox forwards those operations to the supervisor over the Sandbox Protocol. The supervisor, on the trusted side of the boundary, checks policy and opens the real connection. The mediated channel is the workload's only egress. Docker and Podman build that fence by turning workload networking off. Kubernetes relies on NetworkPolicy that allows only the supervisor service, and the gateway documentation states the CNI must enforce NetworkPolicy. A MicroVM guest has no network device; the channel is vsock. Filesystem, Landlock, and process settings take effect at sandbox start. Network rules are enforced by the sandbox network proxy and can change while the sandbox runs.

Phantom Engine runs on the enrolled Linux host. The programs recorded in `architecture_state.md` are `sched_process_fork`, `SSL_write` and `gnutls_record_send` uprobes, execve and execveat tracepoints, an openat observe kprobe, a TC egress classifier, an opt-in `cgroup_skb/egress` program, and the Absolute Control path-deny kprobes and BPF LSM hooks. The TLS uprobes record `OBSERVED`. A uprobe does not block the write. Drops are a separate path: scoped TC returns `TC_ACT_SHOT` for an enrolled cgroup whose destination is outside the allowlist, and `cgroup_skb/egress` is the opt-in path for container-bridge egress. An unattributable packet whose cgroup id is 0 passes, so an empty enrolled map drops nothing. Hostile root and a hostile kernel are outside the program contract in that file. Managed-cloud Kubernetes and a live Spanner write remain target design in `docs/product-spec.md`. Local `kind` results in the status matrix are local tests. They are not a production-cluster claim.

### Child-process inheritance

OpenShell starts the agent as an owned child. The 28 Sep 2026 technical blog states that filesystem, process, and network controls remain in place when the agent starts a shell, runs generated code, launches child processes, or proposes delegation to sub-agents. The architecture page identifies the calling program from trusted `/proc` data. Children share the sandbox Landlock domain, the sandbox user, and the seccomp mediation. A disconnected supervisor freezes the agent. This council did not find a Phantom-style trace-id copy on fork in the OpenShell architecture page. Inheritance there is the sandbox boundary around every process inside it.

Phantom Engine copies `trace_id` from parent TGID to child on `sched_process_fork`, using the parent's TGID from `bpf_get_current_pid_tgid` because the tracepoint's parent pid field is a thread id. The 1 Jul 2026 matrix records strong WSL2 evidence that a curl child showed up in the trace map without its own `--inject`, and records fork and uprobe attach inside a local `kind` pod. The same matrix still asks for an isolated fork-only test before calling that evidence conclusive. PID values from the eBPF helper and userspace PIDs diverge on the measured hosts. Self-calibration with a spawned curl child is the primary translation. A sched or NSpid heuristic is the fallback. `cgroup_skb` attachment to descendants of an enrolled slice is a parent re-verify item in open-core `docs/planning/boot-hold/PE-COMPANION.md`. The architecture roadmap still says Kubernetes `--enroll-watch` does not auto-attach `cgroup_skb` to pod cgroups.

The reconciler treats a parent process record as a process event. It does not let that record cover a later network or file observation from a child.

### MCP semantics

OpenShell `protocol: mcp` applies to sandbox-to-server MCP Streamable HTTP. Rules name an MCP method and, for `tools/call`, a tool name. The published template allows `initialize`, `notifications/initialized`, `tools/list`, and `tools/call` of `read_status`, and denies `tools/call` of `delete_resource`. Omitting `mcp.versions` allows only the `2025-11-25` revision. The sessionless `2026-07-28` revision is opt-in and requires `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` headers that match the body. Tool argument matching is not supported. Server responses and SSE messages are relayed without MCP policy parsing. An `Upgrade` on an MCP endpoint is answered with `403` before it reaches the server. WebSocket is a separate protocol on a different host or port. The policy prover reports MCP rules as unsupported. It does not ignore them and still return `within_boundary`.

Phantom Engine does not parse MCP methods. Gate in this repository is a dry-run evaluate MCP. `packages/vantio-gate-mcp` does not block a live call. A kernel observation of a TLS write can be joined to an OpenShell network or HTTP record for the same destination. The join uses destination and action class. It does not read tool arguments, prompts, or completions.

### Credential handling

OpenShell keeps provider credentials on the trusted side. The supervisor adds a credential only to a request that policy allows for that provider. The sandbox holds no gateway signing key, no gateway JWT, and no provider credentials. User client certificates stay outside the supervisor and the workload. The gateway is the signer. Tokens are bound to one sandbox generation. AWS SigV4 signing, in the provider documentation, happens on the proxy side. An agent proposal cannot approve itself. The policy advisor defaults to human review.

Phantom Engine is not a credential broker. This track must not teach it to become one. The reconciler rejects a snapshot that contains secret-shaped keys or values, and the output allowlist has no place to store them. AI output does not grant a permission, a binding, or a cleared indicator.

### Policy proving

OpenShell's `openshell-prover` uses an SMT solver. A boundary check compares a candidate policy with an operator boundary across filesystem paths, L4 network, REST, process identity, and the Landlock compatibility setting. `within_boundary` means the modeled candidate allows nothing beyond the modeled boundary in those domains. The prover documentation states that this does not mean the policy is safe for a task, and it does not mean a running sandbox enforces it. GraphQL, MCP, WebSocket, and JSON-RPC return `unsupported`. A passing proposal-risk check does not imply a passing boundary check. Exit status is `within_boundary` (0), `exceeds_boundary` (1), `error` (2), or `unsupported` / `inconclusive` (3). Anything other than `within_boundary` is a failed check in OpenShell's own instructions.

Phantom Engine's recorded proof object is the kernel event and the local NDJSON ledger. The product spec marks a live Spanner write as target design. Signed-policy ceiling behavior in `architecture_state.md` requires a verified Ed25519 document when deny is on. An unsigned file does not replace compiled defaults. Optics `vantio prove` exports observations. It is not an SMT proof. This track does not add a prover and does not call either product audited.

### Evidence and OCSF

OpenShell can emit OCSF 1.8.0 JSON. Sandbox JSON is opt-in through `ocsf_json_enabled`. The export document says collection is best-effort and is not a complete audit history. The console writer uses a bounded queue of 1,024 lines and drops new lines when that queue is full. Supervisor files rotate daily, keep three files, and on Docker, Podman, and Kubernetes live on tmpfs or an emptyDir. `metadata.uid` identifies the event. `container.uid` identifies the sandbox. Network Activity is class 4001, HTTP Activity is 4002, Process Activity is 1007. Downgrade targets `1.1` and `1.3` strip `ai_model` and the `ai_operation` profile. The gateway JSONL sink does not archive the supervisor's full structured records.

Phantom Engine's ledger columns recorded in the architecture file are `TraceId`, `Pid`, `EventTimestamp`, `EventType`, `ActionTaken`, `BytesObserved`, `BytesSevered`, and `RawSyscallId`. Observe rows use `OBSERVED`. The case-study timestamps are monotonic nanoseconds from the kernel clock. OpenShell `time` in the published example is a Unix millisecond value. Those clocks are not interchangeable. The existing private demo joins kernel rows to app-layer rows by trace id and emits `BYPASS_INDICATOR` when the kernel row has no app-layer row. This track keeps that indicator name and adds the OpenShell corpus. An OpenShell `metadata.uid` is not a Vantio trace id.

### Fleet management

OpenShell Gateway manages sandbox lifecycle, policy delivery, provider attachment, and identity. Workspaces separate tenants. Compute drivers cover Docker, Podman, MicroVM, and Kubernetes. Shared Kubernetes can run multiple gateway replicas with PostgreSQL. The gateway documentation describes OIDC. The supervisor, not the gateway, makes the per-request allow decision.

Phantom Engine enrollment is per host and per cgroup. The loader can watch a node-local Kubernetes API for pods marked for enrollment. That watch was exercised against local `kind` in the status matrix. Production managed Kubernetes remains target design in the product spec. The open-core boot-hold units install a hold and a loader slot. They do not embed the loader binary. This track does not add a fleet manager and does not change those units.

### Hardware: BlueField and Sentry

The 28 Sep 2026 newsroom post describes two layers. OpenShell is the open-source runtime for agents on CPUs, including third-party Arm and Intel platforms in that post's wording, with a performance story aimed at NVIDIA Vera. NVIDIA Sentry is a reference design on BlueField-4 DPUs, built with DOCA, placed out of band. In a Vera Rubin POD the post says BlueField-4 sits on the node's path to the model and can quarantine an agent that leaves its software boundary. The OpenShell v0.1.4 architecture page describes Docker, Podman, Kubernetes, and MicroVM. It does not describe BlueField as a sandbox runtime.

Phantom Engine has no BlueField program, no DOCA program, and no Sentry program in the files read for this council. Its hardware assumption is an enrolled Linux host with kernel 5.8 or newer, BTF, and `CAP_BPF`. A DPU on the path to a model and a host eBPF program on an enrolled machine are different trust positions. This track does not port Phantom Engine to BlueField and does not claim the host program replaces Sentry.

## Threat model for the join

The workload under test is a supported AI agent on one enrolled Linux host. OpenShell may be the sandbox on that host. Phantom Engine may be loaded on that host. The agent, a child process, or a generated program may speak MCP or raw TLS.

The event this track flags:

1. The kernel observation is on an enrolled cgroup listed in the run's binding table.
2. The observation has an action class and a correlation subject (network destination, file path, or process executable).
3. The observation has a Unix millisecond timestamp, or a Gate record matches its trace id.
4. No OpenShell record matches the sandbox binding, action class, subject, and time window.
5. No Gate record matches the trace id under the rules below.

That condition is `BYPASS_INDICATOR`. It means the supplied OpenShell and Gate snapshots have no matching row. It does not, by itself, mean a sandbox escape was reproduced on hardware.

In scope for the indicator: a TLS write, a connect, an exec, or an open that the kernel snapshot attributes to the enrolled cgroup, with no matching sandbox or Gate row. The deliberate drill is a kernel `TLS_EGRESS` to a reserved fixture host while the OpenShell snapshot contains only a process record for the parent.

Out of scope: prompt scoring, content moderation, model evaluation, an identity provider, generic malware scanning, packet floods, physical robot safety, and any host that is not enrolled. Traffic with cgroup id 0 is outside the binding table and produces no indicator.

## Join rules

A run is a closed snapshot.

```text
schema: vantio.internal.openshell_reconciliation.run.v1
host_id: enrolled host identifier
window_ms: integer 0 through 60000, inclusive on both ends
bindings: 1 to 64 rows of { cgroup_id, sandbox_id }
```

`cgroup_id` is a decimal string. `sandbox_id` is 1 to 128 characters from `[A-Za-z0-9._-]`. One cgroup maps to one sandbox. A repeated cgroup, including an identical repeat, rejects the run with `AMBIGUOUS_BINDING` and emits no findings.

Kernel rows accept the field names already used by the private demo (`EventType` or `event_type`, and the same pattern for action, trace, pid, path). The join uses these derived fields:

| Derived field | Rule |
| --- | --- |
| `action_class` | `TLS_EGRESS`, `NETWORK_BLOCK`, `SYSCALL_CONNECT` are `network`. `SYSCALL_OPENAT` and `SYSCALL_OPEN` are `file`. `SYSCALL_EXECVE` and `SYSCALL_EXECVEAT` are `process`. Any other type is not a class. |
| `subject` | Network: lowercase host, one trailing dot removed, port 1 through 65535. File: the path string, length 1 through 4096, no NUL. Process: the executable path, same limits. A string `Payload` is ignored. |
| `trace_id` | Optional. Canonical form is 16 lowercase hex digits, from a `0x` prefix and leading-zero pad. |
| `observed_at_ms` | Required for an OpenShell match. Values from `1700000000000` through `4102444800000` (2023-11-14 through 2100-01-01 UTC) are Unix milliseconds. A monotonic `EventTimestamp` outside that range does not become a Unix time. |

OpenShell rows accept an OCSF object. `container.uid` is the sandbox id. Class 4001 and 4002 are `network`. Class 1007 is `process`. `dst_endpoint.domain` and `dst_endpoint.port` are the network subject. `actor.process.name` is the process subject when the class is process. `metadata.uid` is stored only as an event id and is never compared to a trace id. HTTP bodies, headers, and URLs with userinfo are not copied.

Gate rows require a trace id. Host, destination, and time are optional. A Gate row with no trace id rejects the run.

Match an OpenShell row only when all of these hold:

- The kernel cgroup's binding names that row's sandbox id.
- Action classes are equal.
- Subjects are equal.
- Both Unix times exist and the absolute difference is within `window_ms`.
- Process id is not a key. Event id is not a key. Time alone is not a key.

Match a Gate row when trace ids are equal. A Gate host, when present, equals the run host. Subjects, when both present, are equal. Times, when both present, fall inside the window. A Gate row with a trace id and no timestamp can still match. A parent process OpenShell row does not satisfy a child network or file kernel row.

Indicators for each kernel row:

| Condition | Indicator |
| --- | --- |
| Cgroup absent from the binding table, or host id differs | `OUT_OF_SCOPE` |
| In scope, and either the class, the subject, or a usable clock is missing, and no Gate trace match exists | `UNATTRIBUTED` |
| In scope, subject and clock are usable, OpenShell misses, Gate misses | `BYPASS_INDICATOR` |
| OpenShell matches, or Gate matches, or both | `RECONCILED_OK` |

`RECONCILED_OK` records which side matched. `decision_mismatch` is true only when a matched row says the action was allowed (`OpenShell` disposition `Allowed`, or Gate action `ALLOWED`) and the kernel action is `NETWORK_BLOCK` or `BLOCKED`. `OBSERVED` is not an allow, so it does not mismatch a denial. Mismatch does not change the indicator.

A rejected run has status `rejected`, an empty finding list, and one of these reason codes: `AMBIGUOUS_BINDING`, `CORRUPT_LINE`, `LIMIT_EXCEEDED`, `SECRET_FIELD`, `CONVERSATION_FIELD`, `SCHEMA`, `KERNEL_RECORD`, `OPENSHELL_RECORD`, `GATE_RECORD`. Invalid input does not produce a cleared run and does not produce a bypass finding.

Secret keys, matched case-insensitively on the final path segment: `authorization`, `api_key`, `apikey`, `token`, `secret`, `password`, `credential`, `credentials`, `bearer`, `access_key`, `private_key`, `client_secret`. Secret values: a bearer token, an `sk-` prefix, an `AKIA` access-key shape, or a PEM private-key banner. Conversation keys: `prompt`, `prompts`, `completion`, `completions`, `messages`, `tool_arguments`, `input_text`, `output_text`. Keys `__proto__`, `prototype`, and `constructor` reject the run. The error names the reason code and a path of key names. It does not contain the value.

Caps: 4,096 records on each side, 65,536 bytes per NDJSON line, JSON depth 16, 64 keys per object, 4,096 array elements. Crossing a cap rejects the run.

Output fields are an allowlist: indicator, reason, kernel index, action class, subject, matched flags, decision mismatch, and the canonical trace id when one was present. The function is synchronous and keeps no module-level record store.

## Failure mode

The join fails closed.

Reason: the condition under test is a missing audit row. Treating a missing row, a corrupt line, or an ambiguous binding as a successful reconcile would hide the bypass class. A rejected snapshot produces no `RECONCILED_OK` and no `BYPASS_INDICATOR`. An in-scope, fully attributed kernel row with no match produces `BYPASS_INDICATOR`.

`UNATTRIBUTED` is the honest residue when the kernel row cannot be compared. A monotonic kernel timestamp is in that residue. Calling it a bypass would invent a miss that the clocks cannot support. Calling it reconciled would clear an event that was not checked against OpenShell.

Known false indicator: OpenShell's own export drops lines when the 1,024-line queue is full, and it can delete JSONL on rotation. A dropped OCSF row becomes `BYPASS_INDICATOR` if the kernel row is fully attributed. The indicator's reason stays `no_matching_openshell_or_gate_record`. Operators read that as "absent from the supplied snapshot."

Phantom Engine's pass of cgroup id 0 is unchanged by this track. Those packets are out of scope for the indicator. That pass is a recorded property of scoped TC, and it is a different default from OpenShell's sandbox egress fence.

## Memory, verifier, dependencies

The later module uses Node's standard library only. Working memory is the snapshot plus indexes bounded by the caps above. It loads no eBPF program, so it does not change verifier limits. The architecture file already records that a combined path-check program walked about twice the instructions of a single-path program and was split for that reason. This track adds no kernel program.

The proof script reads the fixture files, then calls the pure function. It does not resolve fixture paths, does not spawn, and does not open a socket. It writes one evidence file under `internal/gap-t2-openshell/evidence/`.

## Lab feasibility probe

Probe time: 2026-10-16T15:48:53Z, on this cloud-agent runner.

| Check | Result |
| --- | --- |
| Kernel | Linux 6.12.94+ |
| User | uid 1000, `sudo -n` succeeds |
| Effective capabilities | empty (`capsh` current set `=i`). `cap_bpf` is in the bounding set only |
| `kernel.unprivileged_bpf_disabled` | 2 |
| `/sys/fs/bpf` | present, mode `drwx-----T`, owner root |
| Docker | not installed |
| Podman | not on `PATH` |
| `/dev/kvm` | present |
| `vantio-loader` | not in this repository |
| Available memory | about 4.9 GiB |

Decision: do not install Docker, OpenShell, or the Phantom Engine loader here. This runner is not an enrolled Vantio host, and the program forbids installing onto infrastructure Vantio does not own. A live "kernel beneath OpenShell" drill stays Roadmap. The fixture proof is the Lab-only result.

## Rollback

Revert this branch. The design changes no host, no enrollment, no package publish, and no public README. After the code commit, rollback is the same revert: the module has no install step and the proof writes only its evidence file.

## Approval gates

These stay closed.

- Contact NVIDIA, or any partner, about OpenShell, Sentry, BlueField, or this comparison.
- Merge this branch. Apply a founder-approved label.
- Change the public website, the public README, or a Roadmap-to-Shipped claim.
- Enroll a production host, restart a phantom box, widen IAM, or print a secret.
- Spend money, publish an image, or move the public pin off `e0b19d55`.
- Treat local `kind` or WSL2 rows as managed-cloud verification.
- Run the AWS or GCP labs named in the program rules.

## Dependencies on other tracks

No other gap-program branch is present on open-core `69671e97`. This design does not wait on one. A future live join waits on a Phantom Engine adapter that stamps Unix milliseconds next to the monotonic kernel timestamp, and on an enrolled host that the company owns. Those are dependencies of the Roadmap label, not of the Lab-only fixture join.
