# T3 — Council verdict (phase 1, design)

Audience: INTERNAL

Label: **Lab-only**

- UTC: 2026-10-16T16:03:12Z
- Reviewer: Claude Opus, different model family from the Grok producer
- Verdict: **ACCEPT WITH NON-BLOCKING NOTES**

## Scope of this verdict

This verdict covers the design only: `00-DESIGN.md` and `02-RISK-REGISTER.md` as they are on disk at the timestamp above. No product code exists yet, so none was reviewed. Program rule phase 3 still applies: a reviewer from a different model family must review the final implementation head, the proof script, and the evidence artifact before any claim is made. A review of earlier commits does not count.

## What was checked

- Program rules: observe only, no enforcement path, no required proxy hop, no conversation content kept, AI capability never grants permissions, Phantom Engine scope not widened, no prices, banned words absent, Lab-only label present.
- Existing-code claims, spot-checked against `main` (`98cb6c3`):
  - `packages/vantio-cli/bin/vantio.js`: `discoverLocalCommand` reads `~/.vantio/runs/*.json` and groups calls by host. The help text says it is not a fleet inventory.
  - `packages/vantio-cli/bin/llm-hosts.cjs`: exact hosts, suffix match only for dotted names, regional Bedrock / Vertex / Hugging Face patterns, Ollama on loopback port 11434, and the closed `guessProvider` labels.
  - `docs/products/optics/KNOWN-LIMITATIONS.md`: the line "Fleet inventory: `discover` is this machine's run logs."
  - Run logs are written at process exit (`interceptor.cjs` `process.on("exit")`, Python `uninstall()`), and Python logs have no `ppid`. This drove required edit 1.
- Fail-open coverage upgrades, content retention paths, scope widening, contradictions, unnamed risks, and whether the lab proof could pass without testing what it claims to.

## Required edits from earlier rounds, and where they are addressed

| # | Required edit | Addressed in |
| --- | --- | --- |
| 1 | Run logs never create or strengthen identity. Annotation needs a live pid, the start-time rule, a matching pid-namespace depth, and source `run_log`. | §1 table, §4.3 item 3, §4.6, §5 ("Run logs are not in this list"), §7, §9.1 fixtures, R15 |
| 2 | Unreadable `fd/` or `environ` in the enrolled scope caps the host at `partial`. This includes host-process pids when `host_processes` is true. Kernel threads are excluded (pid 2, a pid-2 ancestor, `PF_KTHREAD`). A non-root scan with `host_processes: true` is documented as normally `partial`. | §4.7, §6.2, §6.4 step 8, §8 Failure, §9.1 fixtures, §9.2 pass C |
| 3 | A non-root scanner on a proc mount that hides pids gets host `unknown` (`proc_restricted`): `hidepid=2`, `invisible`, `noaccess`, `ptraceable`, `hidepid=4`. `hidepid=1` stays on the path where an unreadable status gives host `unknown`. | §4.8, §6.4 step 3, §9.1 fixture, R13 |
| 4 | An MCP client config never makes a process an MCP server. A kept config is tagged `basis: config` on an agent runtime. Decoy added. | §4.4, §5 precedence step 2, §9.1, §9.2 `vantio-t3-decoy-mcpconfig` |
| 5 | Container identity fails closed: CRI-O and container markers give `missing`, and only `host_process` can be enrolled by `host_processes`. Enrollment requires exact 64-hex equality. A `missing` container is `unenrolled`. | §4.5, §6.2, §6.3 |
| 6 | Lab proof: passes B and C exercise host `covered` and `partial`. Rows are scored as a multiset with an explicit merge rule. At least one reach must come from a socket whose process argv has no catalog host, and the non-catalog and ambiguous sockets must not appear. The endpoint map is specified, the fallback uses a private mount namespace, and stand-in binaries are recorded. | §4.3, §6.1, §9.1, §9.2 |
| 7 | Every cap has a defined outcome. Comm matching uses the 15-byte truncation. Pid reads go through a directory handle with a start-time recheck. | §4 preamble, §4.1, §4.3, §8 cap table |
| 8 | Risks named: socket attribution on real hosts, MCP servers under generic interpreters, the pid-namespace view, docker-group access, run-log skew. Phantom Engine vocabulary split stated. Banned word removed. | Design opening paragraphs, R8, R11–R15, risk-register preamble |

## Non-blocking notes (resolve during implementation or the phase-3 review)

1. The §3 threat-model rows for "`/proc` hides other users' pids" and "An enrolled cgroup contains a process…" still list the older, shorter set of hidepid values and mention only enrolled cgroups. §4.7, §4.8, and §6.4 are the binding text. Update the threat table so it doesn't drift.
2. §6.3 no longer treats container `missing` as `partial`, so a pid whose `cgroup` read fails becomes `unenrolled` and does not touch host coverage. `/proc/<pid>/cgroup` is world-readable, so this should only happen in a race. Count a non-ESRCH `cgroup` read failure the same as an unreadable `status` (§6.4 step 6), or name it in the risk register.
3. The §9.1 fixtures name `hidepid=invisible` and `hidepid=ptraceable`. Add the numeric `hidepid=2` and `hidepid=4` spellings so older-kernel mountinfo is exercised.
4. In the default runs directory, a mix of files from different users can set `runs_unreadable` and hold the host at `partial`. That is fail-closed and acceptable. Say so in the implementation's operator note so it isn't read as a bug.
5. The phase-3 reviewer should check TOCTOU on the directory-handle reads, the canary search across stdout, stderr, `--out`, and the evidence file, and that the evidence file records the source of each socket-derived name (the private hosts file or the endpoint map).

## Label and gates

Label: **Lab-only**. A passing lab does not move anything to Verified or Shipped. The approval-gate items in design §11 stay gated: merge, the founder-approved label, publish, production enrollment, public claim edits, an eBPF load, cloud labs, and sending anything outside the company.
