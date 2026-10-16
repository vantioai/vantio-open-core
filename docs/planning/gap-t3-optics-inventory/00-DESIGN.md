# T3 — Optics agent discovery and inventory

Audience: INTERNAL

Label: **Lab-only**

Status: design, revised after the phase-1 council required changes. Still before implementation. This file is not a customer claim and does not move any item from Roadmap to Shipped.

Track: Market-readiness gap closure, T3. Branch `gap/t3-optics-inventory`.

Question this track answers, as an observe snapshot of one procfs view: **where are the recognized AI workloads, which catalog destinations were observed, and which closed capability classes were observed.** The report field is `observed_reach`. It is not a promise of every destination the process could open later. It does not grant permissions. AI capability is not authority.

`covered` and `enrolled` in this package are inventory words. They are not Phantom Engine enrollment and not Phantom Engine coverage. A report from this package must not be cited as Phantom Engine coverage.

Public pricing is out of this document. No prices are recorded here.

## 1. What already exists

Checked against this repo at `main` (`98cb6c3`) and the private Phantom Engine tree as of `docs/product-spec.md` last updated 2026-10-06. Product-spec prices are not copied here.

| Surface | Where | What it actually does |
| --- | --- | --- |
| `vantio discover` | `packages/vantio-cli/bin/vantio.js` `discoverLocalCommand` | Reads `~/.vantio/runs/*.json` for this machine. Groups wrapped calls by destination hostname. Help text says it is not a fleet inventory. |
| Destination catalog | `packages/vantio-cli/bin/llm-hosts.cjs` | Exact hosts, dotted suffix match, regional Bedrock / Vertex / Hugging Face patterns, Ollama on loopback port 11434. Parallel to the Python SDK observe set. |
| Wrap observe | `packages/vantio-cli/bin/interceptor.cjs` `process.on("exit")` and Python `_http_observe.py` `uninstall()` | A run file is written when the wrapped process exits. The writer's pid is in the writer's pid namespace. Published Python logs have no `ppid`. |
| Documented gap | `docs/products/optics/KNOWN-LIMITATIONS.md` | "Fleet inventory: `discover` is this machine's run logs." |
| Privacy rule already in force | `docs/products/optics/PRIVACY-AND-SECURITY.md` | Free records keep structural metadata. Prompts and bodies are not the record. URL paths can still hold secrets, so this track does not copy paths. |
| Phantom Engine coverage words | `vantio-phantom-engine` `docs/enterprise/REFERENCE_MONITOR.md`, `python/pe_ingress_truth.py` | Different vocabulary (`coverage_unknown`, `not_enrolled`, `cannot_see`, `honest_idle`). Not this package. |

This track does not edit `docs/products/**`, `README.md`, the installer pin, or the Phantom Engine repo. `vantio discover` keeps its current stdout contract.

The extension is a new unstable package, `packages/optics-agent-inventory`. Identity comes from live process metadata. Run logs never create or strengthen identity.

## 2. Scope boundary

In scope:

- One Linux host, userspace, read-only, one procfs view.
- Recognized AI workloads in that view.
- Coverage states, exact names: `covered`, `partial`, `unenrolled`, `unknown`.
- Signals: process lineage, binary basename, model/API endpoints, MCP server structure, container identity.
- A local container lab on the runner and fixture `/proc` trees.

Out of scope, and not implemented:

- Conversation content, prompts, completions, request bodies, headers, query strings, URL paths, environ values.
- Enforcement, blocking, redaction, spend caps, a proxy hop, eBPF, TC, a resident daemon.
- Fleet aggregation, other hosts, Windows, macOS, a browser, a cluster claim.
- Scoring prompts, content moderation, model evaluation, an identity provider, generic AV/WAF/DDoS.
- Production enrollment, real credentials, public website or README edits, package publish.
- Changing Phantom Engine coverage words or attaching its programs.

Phantom Engine remains the product that enforces on enrolled Linux the customer owns. This package only observes. A workload this catalog does not recognize is absent from the list. Absence is not a claim that no agent exists. Host `covered` describes the procfs view the scanner had, not every namespace on the machine.

## 3. Threat model

| Threat | Failure if untreated | Behavior |
| --- | --- | --- |
| Content in argv, environ, MCP JSON, or a run log is copied into the report | Conversation or secret retention | Extract allowlisted structure. Drop the rest before any object is retained. Tests and the lab plant an alphanumeric canary and require stdout, stderr, and `--out` to exclude it. |
| A finished run log's pid is reused | An unrelated live process inherits old destinations and can look `covered` | Run logs never create identity. Annotation rules are in section 4.6. |
| `covered` is read as "every agent on the machine is known" | Silent miss of a renamed binary | `recognition_limit` is fixed text. `covered` means recognized enrolled workloads in this view had complete signals and the scan of this view finished. |
| An enrolled cgroup contains a process whose fds or environ the scanner cannot read | Host `covered` while an agent in that cgroup was invisible | Host reason `enrolled_scope_unreadable`. Host coverage is then at most `partial`. |
| `/proc` hides other users' pids | The scanner lists nothing and still says `covered` | If the scanner is not root and the proc mount uses `hidepid=2`, `hidepid=invisible`, or `hidepid=noaccess`, host coverage is `unknown` (`proc_restricted`). |
| Missing evidence is upgraded to `covered` | False assurance | Fail closed. Section 6. |
| Enrollment file or `--out` is a symlink | Secret disclosure or a write through a link | `O_NOFOLLOW`. Refuse symlinks. `--out` uses `O_EXCL` and mode `0600`. |
| MCP client config is treated as a running server | Any shell in that directory becomes an MCP server | Only a basename-matched candidate is role `mcp_server`. Section 4.4. |
| An unrecognized runtime cgroup is called a host process | `host_processes: true` enrolls someone else's container | Section 4.5. |
| MCP file or cmdline is huge | Memory exhaustion | Caps in section 8. |
| `/proc/<pid>/root` is used to read arbitrary files | Privilege leak | Allowlisted relative paths only. Last component `O_NOFOLLOW`. No `/proc/<pid>/mem`. No fd contents except `socket:[inode]` symlinks. |
| Short-lived process between snapshots | Missed workload | Point-in-time snapshot. Named residual. |
| Catalog name collision | False workload | Named residual. Lab decoys must stay out. |
| Interactive client to a catalog host | Counted as a covered agent | Interactive basenames are weak unless an agent ancestor absorbs them. |
| Runtime CLI name lookup | Command lines with secrets, and docker-group access which is root-equivalent | Format is id and name only. The tool does not require the docker group. If the socket is not accessible, names stay null and the scan continues. The lab user is not added to that group. |
| Tool is asked to enforce | Scope break | No enforce path. |

## 4. Signals

A signal is `present`, `absent`, or `missing`. `missing` means the read failed, was refused, or was cut by a cap. `absent` means the read succeeded and the thing was not there. Container identity may also be `host_process` or `missing` as in section 4.5.

Pid reads use a directory file descriptor opened on `/proc/<pid>` (`O_DIRECTORY`). Every later read uses `openat` on that fd. Start time is `/proc/<pid>/stat` field 22 plus `btime` from `/proc/stat`, divided by `SC_CLK_TCK`. The same start time is read again before the pid is accepted. A mismatch, or `ENOENT` on the directory fd, discards the pid as a race. It does not become a workload and does not mark the host unknown.

### 4.1 Process lineage

From `status` (`Name`, `PPid`, `NSpid`) and `exe`, via the directory fd. Stored per hop: pid, ppid, comm, exe basename. The chain stops at pid 1, a missing parent, a parent in a different container id, or depth 64. Reaching depth 64 without a boundary sets `lineage=missing`. A disappeared parent (ESRCH) ends the chain as `present`. An existing parent whose status cannot be read is `missing`.

`comm` is at most 15 bytes. Catalog matching uses the full basename and the 15-byte prefix of each catalog name, so a truncated comm still matches. `text-generation-launcher` matches comm `text-generation`. `mcp-server-filesystem` matches comm `mcp-server-file`.

Cmdline is not stored. At most 4096 bytes are read, split on NUL and whitespace, and discarded after host extraction.

### 4.2 Binaries

Exe symlink basename, with a trailing ` (deleted)` removed. The binary file is not hashed and not copied. Unreadable exe on an otherwise recognized process is `binary=missing`. Recognition may still come from comm.

### 4.3 Model and API endpoints

Observed destinations only. Sources are `socket`, `argv`, and `run_log`.

1. **Sockets.** `net/tcp` and `net/tcp6` in that process's netns, attributed only through `fd` symlinks `socket:[inode]`. At most 512 fds are examined. A 513th fd sets `endpoints=missing` for that process. Listen state `0A` versus established `01`. Loopback and unspecified bind on port **11434** is Ollama. Any other remote address is emitted only when the IP resolves to **exactly one** catalog hostname. Sources of names, in order: the process mount's `/etc/hosts` (through `root/etc/hosts`), then the operator endpoint map. If those sources disagree, or one IP has two catalog names, the IP is ambiguous and emits nothing. Unclassified sockets, including non-catalog peers, increment a count and are not printed as addresses.
2. **Argv tokens.** A token that is a catalog hostname, or an `http`/`https` URL whose host is a catalog hostname. Userinfo, path, query, and fragment are discarded. A non-catalog host is discarded. Source `argv`. This is not a packet observation.
3. **Run log annotation.** Section 4.6. Source `run_log`. Never creates a workload.

Catalog rules match `llm-hosts.cjs`: exact host, suffix only when the listed name contains a dot, regional patterns, Ollama loopback port 11434. A unit test parses `LLM_HOSTS` from that file and requires equality. `VANTIO_EXTRA_LLM_HOSTS` adds comma-separated hostnames that contain a dot and no `@`, `/`, `?`, or space.

Provider labels follow `guessProvider`. No new provider strings.

On a real host, catalog names usually come from DNS, not `/etc/hosts`. Socket attribution will often be empty unless the operator supplies an endpoint map. Observed reach is then mostly `argv` and `run_log`. That limit is named in the risk register. The lab must still show one `socket` item whose process argv contains no catalog hostname, so argv extraction cannot pass the bar alone.

#### Operator endpoint map

Optional file, `--endpoint-map`. Schema:

```json
{
  "schema": "vantio.optics.endpoint_map.v1",
  "map": [
    {"ip": "10.88.0.2", "host": "api.openai.com", "port": 443}
  ]
}
```

Open with `O_NOFOLLOW`. Refuse symlinks. Cap 65536 bytes. Each `host` must already be in the catalog. An IP with two different hosts, or a hosts-file name that disagrees with the map, is ambiguous and emits nothing for that IP. `port` when present must equal the socket port. Omitted `port` matches any port. A missing map file means the map is absent. A symlink, oversize file, or bad schema sets host reason `endpoint_map_unreadable` and host coverage at most `partial` (the map was requested and could not be trusted).

### 4.4 MCP servers

A process is an MCP **server** only when comm or exe basename equals `mcp-server` or matches `mcp-server` plus `-` or `.` and at least one more character, including the 15-byte comm prefix `mcp-server-file`.

Client config files do not make a server. These paths are read only for a process that is already `agent_runtime` or an MCP server candidate:

- `mcp.json`
- `.mcp.json`
- `.cursor/mcp.json`
- `.vscode/mcp.json`

Relative to `cwd` and `root`. The last component is opened with `O_NOFOLLOW`. Symlinks are not followed. Files larger than 65536 bytes are not parsed. On a candidate or agent runtime, an oversize or unreadable file at an allowlisted path that exists sets `mcp=missing`. A missing path is `absent`.

Kept from JSON, and only under `mcpServers` object values:

- server name if it matches `^[A-Za-z0-9_.:-]{1,64}$`
- `command` basename
- `url` host and port
- args that match `^--?[A-Za-z0-9-]{1,40}$`
- `basis`: `config` when the row came from a file, `process` when the row is the server process itself

Dropped always: `env`, `headers`, descriptions, prompts, positional args, paths.

A `sleep` or other non-agent whose directory contains `.cursor/mcp.json` is not a workload. The lab includes that decoy.

On an agent runtime, kept rows fill `mcp_servers` and answer what the agent is configured to start. They do not mean those servers were seen running. `basis` is `config`.

### 4.5 Container identity

Cgroup text from `cgroup`, via the directory fd. First parsed id wins:

- `docker-([0-9a-f]{64}).scope`
- `/docker/([0-9a-f]{64})`
- `libpod-([0-9a-f]{64})`
- `cri-containerd-([0-9a-f]{64})`
- `crio-([0-9a-f]{64}).scope`

Container markers, even when no 64-hex id is parsed: `kubepods`, `crio-`, `containerd`, `lxc`, `machine.slice`, `libpod`, `docker`.

| Cgroup text | Container signal |
| --- | --- |
| A 64-hex id parsed above | `present`, id set |
| A marker or any other 64-hex token, but no parsed id | `missing` |
| Neither a marker nor a 64-hex token | `host_process` |
| Unreadable cgroup | `missing` |

`host_process` is the only value `host_processes: true` can enroll. A `missing` container has no id, so it is never enrolled. A workload with container signal `missing` is `unenrolled` (section 6.3 step 2), not `partial` and not a host process.

Optional name lookup: `docker ps` or `podman ps` with format `{{.ID}} {{.Names}}` only, and only when that command works for the scanner uid without changing group membership. Failure leaves `container_name` null. UTS hostname from `root/etc/hostname` is used only when it matches `^vantio-t3-[a-z0-9-]{1,40}$` and the name is still null.

### 4.6 Existing Optics run logs

Optional `--runs-dir` (default: `$VANTIO_HOME/runs` or `~/.vantio/runs` when that directory exists). Run logs are written at process exit, so the recorded pid is usually dead or reused. They **never** create a workload and **never** move a weak identity to strong.

A log may add `observed_reach` with source `run_log` on a workload that was already recognized from live signals, and only when all of these hold:

- The pid is alive in the snapshot.
- The process start time is less than or equal to the log `started_at` plus 2 seconds, and less than or equal to `generated_at` when that field exists. A pid reused after the run has a later start and gets nothing.
- `NSpid` token count equals the scanner's own `NSpid` token count. A different depth skips the annotation. This is a heuristic. It is not proof of the initial pid namespace. The residual stays named.
- The workload already contains that pid.

Copied fields: call `hostname` and `provider` only, and only when the hostname is in the catalog. `ppid` in the log is ignored (Python logs omit it). `path`, `error`, headers, and every other field are not copied. `started_at` is compared and not copied into the report.

A missing runs directory is absent and does not change host coverage. A file that cannot be read or parsed sets host reason `runs_unreadable` and host coverage at most `partial`.

Fixture: a run log whose pid is now an unrelated `sleep` produces no workload and no reach row.

### 4.7 Credential names

Environ is scanned up to 262144 bytes. Only the presence of these **names** is retained: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `AZURE_OPENAI_API_KEY`, `MISTRAL_API_KEY`, `TOGETHER_API_KEY`, `FIREWORKS_API_KEY`, `DEEPSEEK_API_KEY`, `COHERE_API_KEY`, `XAI_API_KEY`. The bytes after `=` are discarded.

Unreadable environ on a process outside the enrolled scope is `absent`. The enrolled scope is: every pid whose parsed container id is listed, and, when `host_processes` is true, every pid whose container signal is `host_process`. Unreadable environ or unreadable `fd/` on any pid in that scope sets host reason `enrolled_scope_unreadable` and host coverage at most `partial`. The process is still not given a role unless another live signal recognized it. A root-owned `python3` in that scope, with no catalog argv, stays off the workload list and still prevents host `covered`.

Kernel threads are not in this rule. A pid is a kernel thread when it is pid 2, when an ancestor is pid 2, or when `stat` field 9 has `PF_KTHREAD` (`0x00200000`). A non-root scan with `host_processes: true` will normally stop at `partial`, because other users' host processes are unreadable. That cap is the honest result.

Name presence alone is **weak** identity (`credential_only`). It does not become `covered`.

### 4.8 Proc mount options

Read `/proc/self/mountinfo` for the mount on `/proc`. If the scanner's euid is not 0 and the options hide other users' pids, host coverage is `unknown` with reason `proc_restricted`. Those options are `hidepid=2`, `hidepid=invisible`, `hidepid=ptraceable`, `hidepid=4`, and `hidepid=noaccess`. `hidepid=1` is not this branch: those pids are still listed and step 6 of the host state catches status that cannot be read. Root is not given `proc_restricted`. An unprivileged scanner also cannot reliably tell that it is outside the initial pid namespace. The report field `host.proc_view` is `restricted` or `listed`. `host.scope_note` is always `procfs_view_only`.

## 5. Closed catalogs

Agent runtime basenames: `claude`, `claude-code`, `codex`, `cursor-agent`, `aider`, `goose`, `cody`.

Model server basenames: `ollama`, `ollama-runner`, `llama-server`, `vllm`, `lmstudio`, `text-generation-launcher`. Listening on TCP 11434 is the same role even when the basename is not in this list.

MCP basenames: section 4.4. `node`, `npx`, `uvx`, and `python` are not MCP servers. Servers started only under those names are a named residual miss unless some other signal recognizes them.

Interactive clients, never strong by themselves: `curl`, `wget`, `httpie`, `aria2c`, `chrome`, `chromium`, `firefox`, `msedge`.

Role precedence for a single process:

1. `local_model_server` if the basename or truncated comm matches, or it listens on 11434.
2. `mcp_server` if the basename or truncated comm matches section 4.4. A config file is not this step.
3. `agent_runtime` if the basename or truncated comm matches.
4. `api_client` if a catalog endpoint was extracted from argv or an attributed socket.
5. `credential_only` if a credential name is present.
6. Otherwise not a workload.

Run logs are not in this list.

`can_do` is only:

- `agent_runtime`
- `serve_local_model`
- `serve_mcp`
- `call_model_api`
- `hold_provider_credential_name`
- `reach:<provider>` for a provider in the closed provider set

These describe the snapshot. They are not grants. `reach:<provider>` means an observed destination, the same fact as `observed_reach`.

## 6. Workloads and coverage

### 6.1 Grouping

Seeds are processes with a role. In the same container id (or the same `host_process` bucket):

- A seed with no ancestor seed in that container starts a workload.
- A descendant is a member of the nearest ancestor workload.
- Exception: a descendant whose own role is `local_model_server` or `mcp_server` starts its own workload.
- An `api_client` or `credential_only` descendant of an `agent_runtime` is absorbed. Its observed reach is unioned. It is not a second row.
- Interactive-client children of an agent are absorbed. An interactive client with catalog reach and no agent ancestor is its own weak workload.

Two seeds that would share `container_id`, `role`, root comm, and root exe basename are **one** row. Pids and observed reach are unioned. The row is not emitted twice.

Workload id is the first 16 hex chars of SHA-256 over `container_id|role|root_comm|root_exe_basename`. Pids are not part of the id. Merged siblings therefore share an id and a row.

### 6.2 Enrollment

Operator file, test tenants only. Not a production enrollment change and not a Phantom Engine enrollment.

```json
{
  "schema": "vantio.optics.enrollment.v1",
  "host_id": "lab-runner",
  "host_processes": false,
  "containers": ["<64 hex chars>"]
}
```

Open with `O_NOFOLLOW`. Cap 65536 bytes. Each container entry must be exactly 64 hex characters. Match is exact equality with the parsed cgroup id. A shorter string is a schema error, not a prefix that enrolls many ids.

`host_processes` enrolls only workloads whose container signal is `host_process`. When it is true, section 4.7 also applies to every non-kernel `host_process` pid, not only to listed container ids. A non-root scanner with `host_processes: true` should expect host coverage `partial` on a normal multi-user machine. The lab sets `host_processes` to false so a fully readable container set can still be `covered`. Host id must equal `--host-id`.

| Enrollment read | Workload enrollment |
| --- | --- |
| File missing, symlink, unreadable, oversize, or schema invalid | `unknown` |
| Host id mismatch | `unenrolled` for every workload, host coverage `unenrolled` |
| Container id not listed | `unenrolled` |
| Container id listed, or host process and `host_processes` true | `enrolled` |

### 6.3 Workload state

Fail closed. The function is total on the four names; any other string raises.

1. Enrollment `unknown` → `unknown`.
2. Enrollment `unenrolled` → `unenrolled`. Weak versus strong is not consulted. A container signal of `missing` has no id and is not a host process, so it is unenrolled here and does not fall through to step 4.
3. Weak identity (`credential_only`, or interactive client without an agent ancestor) → `unknown`.
4. Any of lineage, binary, endpoints, or mcp is `missing` → `partial`. Container is not in this list. `host_process` is not `missing`.
5. Otherwise → `covered`.

`mcp=absent` and `container=host_process` do not block `covered`. Empty `observed_reach` does not block `covered`.

### 6.4 Host state

Fail closed. First match wins. Extra reasons that are true are still listed. They cannot raise the coverage.

1. Proc root unlistable → `unknown` (`proc_unreadable`).
2. Process cap, workload cap, or internal scan error → `unknown` (`scan_incomplete` or `scan_cap`).
3. Not root, and proc is mounted with a hiding option from section 4.8 (`hidepid=2`, `invisible`, `noaccess`, `ptraceable`, or `hidepid=4`) → `unknown` (`proc_restricted`).
4. Enrollment file unusable → `unknown` (`enrollment_missing`, `enrollment_symlink`, `enrollment_unreadable`, `enrollment_schema`).
5. Host id mismatch → `unenrolled` (`host_id_mismatch`).
6. A pid whose **status** cannot be read (not ESRCH) → `unknown` (`unreadable_identity`).
7. Any enrolled workload is `unknown` → `unknown` (`enrolled_workload_unknown`).
8. Any enrolled workload is `partial`, or `runs_unreadable`, or `endpoint_map_unreadable`, or any non-kernel pid in the enrolled scope (section 4.7) has unreadable `fd/` or `environ` → `partial` (`enrolled_workload_partial`, `runs_unreadable`, `endpoint_map_unreadable`, `enrolled_scope_unreadable`).
9. Otherwise → `covered`.

Unenrolled workloads do not change steps 7–9. Host `covered` with zero workloads uses reason `no_ai_workloads_observed` and still carries `recognition_limit` and `scope_note`.

`enrolled_scope_unreadable` is step 8, so it cannot override step 7. A host with an enrolled `unknown` workload stays `unknown` and may also list `enrolled_scope_unreadable`.

ESRCH and start-time mismatches are race counters, not host `unknown`.

## 7. Report

Stdout is one JSON object. `--out` is created with `O_NOFOLLOW | O_EXCL` and mode `0600`. An existing symlink is refused. No other write.

```json
{
  "schema": "vantio.optics.agent_inventory.v1",
  "schema_status": "unstable-pre-1.0",
  "label": "lab-only",
  "content_stored": false,
  "observed_at": "YYYY-MM-DDTHH:MM:SSZ",
  "recognition_limit": "catalog_process_endpoint_mcp_container",
  "host": {
    "host_id": "",
    "coverage": "unknown",
    "reasons": [],
    "proc_view": "listed",
    "scope_note": "procfs_view_only"
  },
  "workloads": []
}
```

`content_stored` is the constant `false`. Tests still search the bytes. `observed_at` is UTC. Workloads sort by `(container_id, role, workload_id)`.

Each workload: `workload_id`, `role`, `coverage`, `reasons`, `where` (host id, container id, container name or null, pids, lineage), `observed_reach` (host, port, provider, source `socket` or `argv` or `run_log`), `can_do`, `signals`, `mcp_servers`.

Reason codes are closed. They must not embed argv, paths, or file text.

Exit `0` when a report was produced, including `unknown` and empty. Exit `2` on bad arguments. Exit `3` when proc cannot be listed (the report is still printed, host `unknown`).

## 8. Resources, dependencies, failure, rollback

| Cap | Outcome |
| --- | --- |
| 20000 processes | Host `unknown`, `scan_cap`. The report does not claim `covered`. |
| 10000 workloads | Host `unknown`, `scan_cap`. |
| 4096 cmdline bytes | Extra bytes are not read. Not a coverage gap by itself. |
| 262144 environ bytes | Extra bytes are not a credential hit. Not a coverage gap by itself. |
| 65536 MCP bytes | `mcp=missing` for a candidate or agent runtime. |
| 65536 enrollment or endpoint-map bytes | That file is unusable. Section 6. |
| Lineage depth 64 | `lineage=missing` on that workload. |
| 512 fds per process | `endpoints=missing` on that process. |

Dependencies: Python 3.9+, Linux procfs. Standard library only. Optional `docker` or `podman` on `PATH` for names, never required. No eBPF, so verifier limits do not apply. This track must not load a kernel program.

Failure: coverage claims fail closed (section 6). A recognized pid whose read failed stays in the list as `partial` or `unknown`. Unrecognized pids are omitted. An unrecognized non-kernel pid in the enrolled scope whose `fd/` or `environ` cannot be read still caps the host at `partial`. The enrolled scope includes the host-process bucket when `host_processes` is true.

Rollback: delete `packages/optics-agent-inventory` and `docs/planning/gap-t3-optics-inventory`. Nothing is installed to a host unit, a package index, or an enrollment store. The proof deletes only containers it created under the `vantio-t3-` prefix and cgroups it created.

## 9. Proof

### 9.1 Fixture tests

`tests/optics-agent-inventory/` builds a fake proc tree. No container runtime.

Required cases:

- All four coverage states.
- Absorbed lineage, and two sibling `claude` roots merged to one row. The scorer treats rows as a multiset, so a duplicate key is a false positive.
- Decoy processes, including `sleep` with `.cursor/mcp.json` in its cwd.
- Argv userinfo, path, and query stripped.
- MCP `env`, `headers`, and description stripped.
- Run-log `path` and `error` stripped. A log whose pid is now `sleep` creates no workload.
- A log annotates an already-recognized pid only when the start-time rule holds, with source `run_log`.
- Symlink enrollment and symlink `--out` refused.
- Catalog lockstep with `llm-hosts.cjs`, including 15-byte comm prefixes.
- Ambiguous endpoint map emits nothing. A socket to a non-catalog IP is not printed.
- `hidepid=invisible` and `hidepid=ptraceable` as non-root yield host `unknown`.
- Unreadable `fd/` inside an enrolled cgroup yields host `partial` and `enrolled_scope_unreadable` even when no workload row is produced.
- The same cap applies when `host_processes` is true and a non-kernel host process has unreadable `fd/`. A kernel thread does not trip it.
- Truncated comm `mcp-server-file` and `text-generation` match.

### 9.2 Container lab

`scripts/gap-t3/proof_inventory_accuracy.py` seeds containers on this runner and writes `docs/planning/gap-t3-optics-inventory/evidence/inventory-accuracy.json`.

Runtime order: `docker`, then `podman`, then a Linux container built with `unshare` (mount, uts, ipc, pid, net) plus a cgroup named `docker-<64 hex>.scope`. The evidence records which runtime ran. Package installs (`docker.io`, `podman`, `iproute2`) are allowed only on this ephemeral runner, only if the selected runtime needs them, and are not a product dependency. The lab user is not added to the `docker` group.

The namespace fallback uses a **private** mount namespace and bind-mounts a lab hosts file over `/etc/hosts`. The runner's `/etc/hosts` must be unchanged, and the proof checks that. Socket names come from that private file or from the endpoint map in section 4.3. The evidence says which one was used.

The inventory subprocess runs as uid 1000. The partial container is the only root-owned lab process. Every decoy and every covered container runs as uid 1000, so pass B is not capped by `enrolled_scope_unreadable`.

Stand-in identities (a Python interpreter started with comm `ollama`, `claude`, `curl`, or `mcp-server-filesystem`) are listed in the evidence. They are not the upstream binaries.

Alphanumeric canary: `CANARYPROMPTT39F3C2A`. Planted in argv, an environ value, MCP description, MCP `env`, MCP `headers`, URL userinfo, URL path, URL query, a decoy file, and a run log's `path` and `error`. It must be absent from stdout, stderr, the `--out` file, and the evidence file.

| Container | Identity | In primary enrollment | Role | Coverage |
| --- | --- | --- | --- | --- |
| `vantio-t3-agent` | uid 1000. Argv URL with userinfo, path, and query. Held socket to a unique catalog IP. A second socket to a non-catalog IP. A third socket whose hosts map is ambiguous. Credential name set. | yes | `api_client` | `covered` |
| `vantio-t3-ollama` | comm `ollama`, listen 11434, uid 1000 | yes | `local_model_server` | `covered` |
| `vantio-t3-mcp` | comm `mcp-server-filesystem`, config with description, env, and header canaries, uid 1000 | yes | `mcp_server` | `covered` |
| `vantio-t3-lineage` | parent comm `claude`. Child argv has **no** catalog host. Child socket to a unique Anthropic IP. uid 1000 | yes | `agent_runtime` | `covered` |
| `vantio-t3-unenrolled` | same shape as the agent, uid 1000 | no | `api_client` | `unenrolled` |
| `vantio-t3-unknown` | python3, credential name only, uid 1000 | yes | `credential_only` | `unknown` |
| `vantio-t3-partial` | comm `claude`, uid 0 | yes | `agent_runtime` | `partial` |
| `vantio-t3-decoy-web` | python3 listen 8080, uid 1000 | yes | absent | absent |
| `vantio-t3-decoy-file` | `sleep`, file contains the canary and `api.openai.com`, uid 1000 | yes | absent | absent |
| `vantio-t3-decoy-curl` | comm `curl`, argv host `example.com`, uid 1000 | yes | absent | absent |
| `vantio-t3-decoy-mcpconfig` | `sleep`, cwd contains `.cursor/mcp.json`, uid 1000 | yes | absent | absent |

Primary pass match key: `(container_id, role, coverage)`, as a multiset.

- Discovery precision / recall: `(container_id, role)`, ignoring coverage.
- Strict precision / recall: the triple. A coverage mismatch is both a false positive and a false negative.
- Pass bar for the primary pass: all four figures equal 1. Host coverage is `unknown` because an enrolled workload is `unknown`. At least one `observed_reach` item has source `socket` and belongs to the lineage workload (no catalog host in the child argv). The non-catalog socket and the ambiguous socket do not appear. `content_stored` is false. The canary is absent.

Two more enrollment passes over the same running containers:

- **Pass B.** Enroll only agent, ollama, mcp, lineage, and the decoys. Host coverage must be `covered`. Those four workloads stay `covered`. Omitted containers are `unenrolled`. Decoys stay absent.
- **Pass C.** Pass B plus the partial container. That workload is `partial`. Host coverage is `partial` and reasons include `enrolled_scope_unreadable`.

## 10. Implementation map

Package `packages/optics-agent-inventory` version `0.0.0-unstable-pre-1.0`, not published.

| Module | Responsibility |
| --- | --- |
| `catalog.py` | Closed basenames, hosts, providers, 15-byte comm prefixes |
| `privacy.py` | Caps, canary helper for tests, constant `content_stored` |
| `procfs.py` | Directory-fd snapshot, start time, hidepid |
| `endpoints.py` | Sockets, argv hosts, endpoint map |
| `mcp.py` | Allowlisted MCP parse |
| `containers.py` | Cgroup id and optional names |
| `enrollment.py` | Schema, nofollow, exact ids |
| `runs.py` | Annotation only, never identity |
| `coverage.py` | The four states |
| `inventory.py` | Grouping and report assembly |
| `__main__.py` | CLI |

No edits under `packages/vantio-cli/**` or `docs/products/**`.

## 11. Approval gates

Not done in this track, and not implied by a passing lab:

- Merge, or the founder-approved label.
- Any publish, tag, GHCR push, or customer release. Public pin stays where it is.
- Production enrollment, real credentials, IAM changes.
- A README or website claim, including editing the known-limitations page.
- An eBPF load, a phantom-box restart, an AWS or GCP lab.
- Sending the report outside the company.
