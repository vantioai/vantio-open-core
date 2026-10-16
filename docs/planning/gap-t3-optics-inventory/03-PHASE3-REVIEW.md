# T3 — Phase 3 implementation review

Audience: INTERNAL

Label: **Lab-only**

- UTC: 2026-10-16T16:33:04Z
- Reviewer: Composer (different model family from Grok producer)
- SHA reviewed: `6ed9a5916fc3ac6e7e8685ff3f309caf8797cd23`
- Verdict: **ACCEPT WITH NON-BLOCKING NOTES**

This review covers only commit `6ed9a5916fc3ac6e7e8685ff3f309caf8797cd23`. `git rev-parse HEAD` on branch `gap/t3-optics-inventory` matched that SHA at review start.

## What was checked

- Program rules (`PROGRAM-RULES_4269.md`): observe-only, no proxy hop, no prices, banned words absent, Lab-only labeling, no Phantom Engine scope widening, no Shipped claims.
- Design and council artifacts: `00-DESIGN.md`, `01-COUNCIL-VERDICT.md`, `02-RISK-REGISTER.md`.
- Implementation: all modules under `packages/optics-agent-inventory/src/optics_agent_inventory/`, `scripts/gap-t3/proof_inventory_accuracy.py`, `scripts/gap-t3/payload.py`.
- Evidence (read, not re-run): `docs/planning/gap-t3-optics-inventory/evidence/inventory-accuracy.json`.
- Fixture tests: `python3 -m unittest discover -s tests/optics-agent-inventory -t tests/optics-agent-inventory -q` — **19 tests, OK**.

### Criteria (pass / note)

| Criterion | Result |
| --- | --- |
| No conversation content retained (argv bodies, environ values, MCP env/headers/descriptions, run-log path/error) | Pass. Parser allowlists structure; fixture tests and lab canary gate; `content_stored` is false. |
| Coverage fail-closed (`covered` / `partial` / `unenrolled` / `unknown` only) | Pass. `coverage.py` raises on other names; host and workload logic match §6. |
| Run logs never create identity | Pass. `runs.py` annotates only live, recognized pids with start-time and NSpid checks; fixtures cover stale pid and live annotation. |
| `enrolled_scope_unreadable` includes host processes; kernel threads excluded | Pass. `_scope_unreadable` in `inventory.py`; pid 2 / `PF_KTHREAD` / kthreadd ancestor in `procfs.py`; fixtures cover host-process and kernel cases. |
| hidepid includes `ptraceable` and `hidepid=4` | Pass. `_HIDING` in `procfs.py`; fixture exercises `invisible`, `ptraceable`, `2`, `4`, `noaccess`; root exempt. |
| MCP client config does not create `mcp_server` | Pass. Role from comm/exe basename only; decoy `sleep` + `.cursor/mcp.json` absent from workloads. |
| Missing container id → `unenrolled`, not host process | Pass. `containers.parse_cgroup` + enrollment + fixture `test_missing_container_marker_is_unenrolled`. |
| Container proof not tautological | Pass (evidence). Discovery and strict precision/recall 1.0; three host passes (`unknown` / `covered` / `partial`); lineage socket reach from `private_hosts` with `endpoint_map_contains_lineage_ip` false; `canary_absent` true. |
| Races / TOCTOU / exceptions / privilege leaks | Pass for stated threat model. Directory fd + start-time recheck; `O_NOFOLLOW` on allowlisted paths; no `/proc/<pid>/mem`; cmdline/environ discarded after extraction; fixture deny bits drive partial caps. |
| No prices; not Phantom Engine coverage; not Shipped | Pass in code, README, report `label`, and evidence. |

## Non-blocking notes

1. **Design §4.3 — missing endpoint map file:** `load_endpoint_map` treats `FileNotFoundError` as `endpoint_map_unreadable` (host at most `partial`). Design text says a missing file should behave as an absent map. Current behavior is fail-closed but uses the wrong reason and can over-cap on a bad path.
2. **Design §4.6 — default `--runs-dir`:** CLI does not auto-select `$VANTIO_HOME/runs` or `~/.vantio/runs`; callers must pass `--runs-dir` (lab proof and tests do). README documents `runs_unreadable` when a runs directory is used.
3. **Design §4.4 — MCP file reads:** `_mcp` scans allowlisted paths for every pid, not only `agent_runtime` / MCP server candidates. Decoys stay off the workload list; extra reads are a spec drift and minor cost only.
4. **Design §10 — `privacy.py`:** Not present; `content_stored` and caps live inline. No functional gap for this track.
5. **Design §4.5 — optional `docker`/`podman` name lookup:** Not implemented; `container_name` may be null (UTS lab hostname still works in the lab).
6. **`scan_incomplete`:** Listed in `coverage.py` but not emitted by the scanner; no observed path needs it today.
7. **Fixture gap:** Symlink `--out` refusal is implemented in `__main__.py` (`O_EXCL` \| `O_NOFOLLOW`) but not covered by a unit test (enrollment symlink is tested).
8. **Risk R16:** Non-ESRCH cgroup read failure → container `missing` → workload `unenrolled` without host step-6 `unreadable_identity`; matches accepted design and risk register.

## Label and gates

Label: **Lab-only**. This package’s `covered` / `enrolled` vocabulary is inventory-only and is not Phantom Engine coverage. Approval-gate items in design §11 remain open (merge, publish, production enrollment, public claims, eBPF load, external send).
