# T3 risk register

Audience: INTERNAL

Label: **Lab-only**

These risks stay open after a passing lab. None is closed by the fixture tests or the runner containers. Do not describe the result as independently certified.

| ID | Risk | Why it remains | Mitigation in this track |
| --- | --- | --- | --- |
| R1 | A renamed or unknown binary with no catalog endpoint, no MCP basename, and no credential name is invisible. Host `covered` plus `no_ai_workloads_observed` does not mean the host has no agent. | Recognition is catalog and signal based. | `recognition_limit` on every report. |
| R2 | A non-agent whose comm is a catalog basename (`claude`, `codex`, `cody`) is listed. | Basename collision. | Lab decoys cover the other direction. Collision stays a residual. |
| R3 | The snapshot misses processes that exit between scans, and misses destinations that are not in the socket table at that moment. | Userspace procfs, no tracepoint. | Named. No kernel program is attached to hide the gap. |
| R4 | Argv and `/etc/hosts` can disagree with the true peer. Source `argv` is not a packet. An ambiguous hosts map is dropped, which can hide a real destination. | No TLS SNI and no eBPF. | `observed_reach[].source` is `socket`, `argv`, or `run_log`. Ambiguous maps emit nothing. |
| R5 | Another user's unreadable exe makes an enrolled catalog comm `partial` even when the process is the real binary. | Cross-uid proc permissions. | That is the intended partial state, not a silent drop. |
| R6 | Run logs and MCP files can contain secrets in fields this parser drops. A future field added to the allowlist would retain them. | Allowlists rot. | Allowlist is explicit. The lab plants a canary outside the allowlist. |
| R7 | Container names from the runtime CLI can be wrong or absent. | The CLI is optional and untrusted. | Enrollment matches the cgroup id. Name may be null. The tool does not require the docker group. |
| R8 | The runner lab is not a customer host, not a cluster, and not Phantom Engine enrollment. | Lab-only by construction. | Evidence label `lab-only`. This package's `covered` is not Phantom Engine coverage. No product doc is edited to say otherwise. |
| R9 | `credential_only` treats a key name as an AI workload. A build job can hold a key and be listed as `unknown`. | Weak signal is sensitive. | State stays `unknown`, never `covered`. |
| R10 | Shared rootfs on the namespace fallback means a bug outside the allowlist would see host files. | Fallback runtime. | Allowlist and `O_NOFOLLOW`. Private bind-mount for the lab hosts file. Proof checks the host hosts file is unchanged. |
| R11 | On real hosts, socket peers are DNS and CDN addresses. `/etc/hosts` will not name them. Observed reach will often be argv or run-log only. | No packet hostname. | Named. The lab still requires one socket-sourced row so the proof is not argv-only. An operator map is optional and exact. |
| R12 | MCP servers started as `node`, `npx`, `uvx`, or `python` are not MCP servers in this catalog. | Those basenames are shared with ordinary programs. | Named miss. A basename `mcp-server…` is required for role `mcp_server`. |
| R13 | An unprivileged scanner cannot reliably tell that it is outside the initial pid namespace, or that another mount of proc exists. Host `covered` is the view it had. | Kernel does not give an unprivileged process a trustworthy "I see everything" bit beyond hidepid. | `host.scope_note` is `procfs_view_only`. hidepid as non-root forces `unknown`. |
| R14 | `docker` or `podman` group membership is root-equivalent. Using it to learn names is a privilege decision. | Socket access can control the runtime. | Name lookup is optional. The lab does not add the scanner uid to that group. |
| R15 | Run-log pid annotation can still attach an old destination if start-time skew exceeds 2 seconds or `NSpid` depth collides. | Clocks and nested namespaces. | Annotation cannot create identity. A failed check adds nothing. |

Approval-gate items: merge, founder-approved label, publish, production enrollment, public claim edits, eBPF load, cloud labs, external send. See the design, section 11.
