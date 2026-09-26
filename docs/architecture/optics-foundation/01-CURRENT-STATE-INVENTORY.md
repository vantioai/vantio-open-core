# A0 — Current-state source inventory

Classification: `OPTICS_FOUNDATION_A0_INVENTORY_COMPLETE`

Audience: INTERNAL_RESTRICTED

Method: read source, tests, and docs separately at main `d6b74d41808a43f251d6de46e1313625a025d16d`. Docs were not used as a substitute for source. Where they disagree, the finding is `CONFLICTING`. Nothing in this inventory was “fixed.”

Scope of inspection:

- Node CLI writer: `packages/vantio-cli/bin/interceptor.cjs`
- Node CLI reader and commands: `packages/vantio-cli/bin/vantio.js`
- Display and schema marker: `packages/vantio-cli/bin/optics-cx.cjs`
- Host catalog and Node provider guess: `packages/vantio-cli/bin/llm-hosts.cjs`
- Node product telemetry: `packages/vantio-cli/bin/telemetry.cjs`
- Python process wrap: `packages/vantio-cli/bin/python-wrap/sitecustomize.py`, `packages/vantio-agent-sdk-py/vantio/_process_wrap.py`, `packages/vantio-agent-sdk-py/vantio/_http_observe.py`, `packages/vantio-agent-sdk-py/vantio/_outcome.py`
- Python product telemetry: `packages/vantio-agent-sdk-py/vantio/_telemetry.py`
- Read-only MCP: `packages/vantio-optics-mcp/src/runs.js`
- Node SDK `packages/vantio-agent-sdk/src/index.ts` was checked for a run-log writer and does not write `~/.vantio/runs`.
- Tests under `packages/vantio-cli/test/` and `packages/vantio-agent-sdk-py/tests/`.
- Public docs `docs/sight-loop.md`, `docs/prove.md`, `docs/observe-only.md`, `docs/optics-otel-mapping.md`.

Classifications used here: `CURRENTLY_IMPLEMENTED`, `PARTIAL`, `ABSENT`, `UNKNOWN`, `CONFLICTING`.

Roadmap IDs are the 52 numbered requirements in `TRACEABILITY-MATRIX.json`. Sections 8–22 of the roadmap are unnumbered design input and are cited in later architecture docs, not as extra numeric IDs.

## Topic 1 — Node record path and shape

### Finding 1.1 — Node attach path

- File: `packages/vantio-cli/bin/vantio.js`, symbol `runCommand`
- Lines: 279–381
- Current behavior: `vantio run` splits flags from the child program. For Node runtimes (`node`, `npx`, `tsx`, `ts-node`) it prepends `--require <interceptor.cjs>` onto `NODE_OPTIONS`. It sets `VANTIO_TRACE_ID` to `VANTIO_TRACE_ID` from the parent or `0x` plus 16 hex characters from `randomUUID`.
- Evidence: source of `isNodeRuntime`, `extraNodeOptions`, and `childEnv`.
- Confidence: HIGH
- Limitation: a Node process not started under `vantio run`, and any runtime outside that name set, is not attached by this command.
- Roadmap IDs: OF-23-08, OF-23-29
- Classification: `CURRENTLY_IMPLEMENTED`

### Finding 1.2 — Node on-disk record shape

- File: `packages/vantio-cli/bin/interceptor.cjs`, symbol process `exit` handler
- Lines: 3679–3768
- Current behavior: on process exit the interceptor writes one JSON object. Envelope fields written in source: `vantio_run_log` `"1"`, `schema_version` `2`, `plane` `"optics"`, `data_note`, `trace_id` (`RUN_TRACE_ID`), `pid`, `ppid`, `node_version`, `platform`, `arch`, `started_at`, `generated_at`, `duration_ms`, `cli_version`, `free_mode`, `calls`, `summary`, `residual`. Each call is mapped to `hostname`, `provider`, `method`, `path`, `scheme`, `request_bytes`, `bytes`, `status`, `ok`, `content_type`, `duration_ms`, `action`, `ts`, `redactions`, `error`, `error_class`. Summary includes `total_calls`, `total_bytes`, `hosts`, `providers`, `errors`, `by_host`, `by_provider`, `redacted`, `blocked`, `est_spend_usd` (`null` when `FREE_MODE`).
- Evidence: object literal assigned to `log` immediately before `writeFileSync`.
- Confidence: HIGH
- Limitation: the envelope has no `schema_status`, no `evidence_origin`, no `machine`, no `workflow`, no span or session id, and no lifecycle state. Sparse in-memory records such as `blockHost` (`{ hostname, action }`, line 643) are normalized only by this mapper, so missing fields become null or zero at write time.
- Roadmap IDs: OF-01, OF-03, OF-13, OF-23-01, OF-23-04
- Classification: `PARTIAL`

### Finding 1.3 — Node free-tier call capture

- File: `packages/vantio-cli/bin/interceptor.cjs`, symbol `wrapFetch`
- Lines: 813–880
- Current behavior: in free mode an in-scope `fetch` records structural metadata and `action: "OBSERVED"`. Network failure records `ok: false`, `error: "network_error"`, and `error_class` from `err.name`. The response body is not stored. `responseMeta` (lines 142–156) keeps status, `ok`, content-type media type before `;`, and `Content-Length` when present.
- Evidence: `_calls.push` objects in the free-tier branch.
- Confidence: HIGH
- Limitation: response size is absent when `Content-Length` is absent. Streaming byte counts in the paid branch mutate `callRec.bytes` after push (lines 934–937) and can race the exit write.
- Roadmap IDs: OF-23-01, OF-23-10, OF-23-16
- Classification: `PARTIAL`

## Topic 2 — Python record path and shape

### Finding 2.1 — Python attach path

- File: `packages/vantio-cli/bin/python-wrap/sitecustomize.py`; `packages/vantio-agent-sdk-py/vantio/_process_wrap.py`, symbol `install_process_wrap`
- Lines: sitecustomize 1–31; `_process_wrap.py` 19–34
- Current behavior: `vantio run` for a Python runtime puts `bin/python-wrap` on `PYTHONPATH` (`vantio.js` lines 311–347). `sitecustomize` prefers `install_process_wrap`, which calls `_http_observe.install(trace_id)` and registers `uninstall` on `atexit`. Missing SDK writes a stderr warning and does not crash the agent.
- Evidence: both files.
- Confidence: HIGH
- Limitation: `docs/sight-loop.md` lines 20–32 tell Python users to use `@shield` instead of `vantio run`. Source supports both `vantio run python` and `shield()`. That doc sentence disagrees with `vantio.js` usage text (lines 45–46) and with `sitecustomize.py`.
- Roadmap IDs: OF-23-08, OF-23-32
- Classification: `CONFLICTING`

### Finding 2.2 — Python on-disk record shape

- File: `packages/vantio-agent-sdk-py/vantio/_http_observe.py`, symbol `_write_run_log`
- Lines: 2485–2538
- Current behavior: writes JSON only when `_calls` is non-empty and `_trace_id` is set. Envelope includes `vantio_run_log` `"1"`, `schema_version` `2`, `schema_status` from `SCHEMA_STATUS`, `plane` `"optics"`, `workflow` `"sight_loop"`, `data_note`, `status_labels`, `trace_id`, `runtime` `"python"`, `mediation`, `started_at`, `generated_at`, `calls` (the in-memory list), `summary`, `residual`. Summary has `total_calls`, `hosts`, `opticsStatus`, `applicationStatus`, `opticsLabel`, and customer summary fields. It does not write `pid`, `ppid`, `free_mode`, `duration_ms`, `by_host`, or `est_spend_usd`.
- Evidence: `payload` dict in `_write_run_log`.
- Confidence: HIGH
- Limitation: Node and Python envelopes are not the same object. Python `residual.note` (lines 2524–2526) describes Phantom Engine blocking and redaction inside an Optics run log.
- Roadmap IDs: OF-01, OF-23-30, OF-23-31
- Classification: `CONFLICTING`

### Finding 2.3 — Python per-call fields

- File: `packages/vantio-agent-sdk-py/vantio/_http_observe.py`, symbol `_record`; `packages/vantio-agent-sdk-py/vantio/_outcome.py`, symbol `apply_customer_outcome`
- Lines: `_record` 669–689; `apply_customer_outcome` 392–431
- Current behavior: a call record starts with `hostname`, `provider` (default `"other"`), `action`, `mediation`, `ts` (UTC ISO from `datetime.now`), plus caller extras (`path`, `status`, `ok`, `duration_ms`, `error`, `error_class`, `failure_kind`). It then sets `opticsStatus` `"SUCCESS"`, `applicationStatus` from HTTP status, human labels, and customer outcome lines: `applicationOutcomeLabel`, `applicationLabel`, `providerName` or `upstreamService`, `providerResponse`, `nextAction`, `nextActionCategory`. Catalog identity can replace provider `"other"`.
- Evidence: both functions.
- Confidence: HIGH
- Limitation: these human lines are persisted inside the observation record. The architecture in A1 separates derived diagnostics from observations. Today they are one object.
- Roadmap IDs: OF-23-01, OF-23-09, OF-23-21
- Classification: `PARTIAL`

## Topic 3 — Run-log locations

### Finding 3.1 — Writer roots disagree with the CLI reader root

- File: `interceptor.cjs` line 3695; `_http_observe.py` lines 2489–2490; `vantio.js` symbols `configDir` and `runsDir` lines 248 and 405; `packages/vantio-optics-mcp/src/runs.js` symbol `runsDir` lines 9–10
- Current behavior: the Node interceptor writes `$VANTIO_HOME/runs` or `~/.vantio/runs`. Python does the same with `VANTIO_HOME` or `expanduser("~")/.vantio/runs`. The CLI reader uses `homedir()/.vantio/runs` and does not read `VANTIO_HOME`. The MCP reader honors `VANTIO_HOME`.
- Evidence: the four symbols. `rg` over `packages/vantio-cli` shows `VANTIO_HOME` in the interceptor and in tests, not in `vantio.js`.
- Confidence: HIGH
- Limitation: a process started with `VANTIO_HOME` set can write a log the CLI will not list.
- Roadmap IDs: OF-01, OF-23-17
- Classification: `CONFLICTING`

### Finding 3.2 — Zero-call runs

- File: `interceptor.cjs` lines 3691–3694 (comment and unconditional write); `_http_observe.py` lines 2486–2487
- Current behavior: Node writes a run log on every exit, including zero calls. Python returns without writing when `_calls` is empty.
- Evidence: both writers. `docs/prove.md` lines 16–18 and 141–142 say a log is written when at least one LLM call was observed.
- Confidence: HIGH
- Limitation: “was this process attached and silent?” is answerable from a Node file and absent from Python.
- Roadmap IDs: OF-23-09, OF-23-15
- Classification: `CONFLICTING`

## Topic 4 — Naming

### Finding 4.1 — File name is a sanitized trace id

- File: `interceptor.cjs` lines 3763–3764; `_http_observe.py` lines 2528–2529; `vantio.js` symbol `demoCommand` lines 1447–1448
- Current behavior: the file name is the trace id with characters outside `[A-Za-z0-9_-]` replaced by `_`, truncated to 80 characters, plus `.json`. The same trace id overwrites the same file. `findRunByPrefix` (`vantio.js` 704–717) matches `filename.includes(normalizedPrefix)`.
- Evidence: the three writers and `findRunByPrefix`.
- Confidence: HIGH
- Limitation: truncation and character folding can collide. Prefix match can select the wrong file when one id contains another.
- Roadmap IDs: OF-03, OF-23-07
- Classification: `PARTIAL`

### Finding 4.2 — `trace_id` is a process-run id

- File: `vantio.js` lines 338–342; `interceptor.cjs` line 68; `_process_wrap.py` lines 23–24
- Current behavior: one id is generated per `vantio run` or per Python install. The Node fallback when the environment variable is missing is `randomUUID()` with no `0x` prefix. The CLI parent uses `0x` plus 16 hex digits. Python uses `uuid4` when the variable is missing. There is no per-call span id.
- Evidence: the three assignments.
- Confidence: HIGH
- Limitation: the field name `trace_id` does not match a W3C trace id or a per-call span. `docs/optics-otel-mapping.md` is explicit that the page is a sketch and that Optics does not export OTLP.
- Roadmap IDs: OF-03, OF-23-02
- Classification: `PARTIAL`

## Topic 5 — Write

### Finding 5.1 — Single exit write, not a transactional store

- File: `interceptor.cjs` lines 3763–3768; `_http_observe.py` lines 2528–2538
- Current behavior: both writers serialize the full call list once, at exit or `uninstall`. Node uses `writeFileSync` with mode `0o600`. Python writes with `open(..., "w")` then `os.chmod(path, 0o600)`, ignoring `OSError` from chmod. Neither write uses a temporary file and rename. Neither write is append-only.
- Evidence: the write calls. There is no `sqlite` import in these writers.
- Confidence: HIGH
- Limitation: a crash during `writeFileSync` / `open` can leave a partial file. A second process with the same trace id replaces the file.
- Roadmap IDs: OF-01, OF-23-16, OF-23-30
- Classification: `PARTIAL`

### Finding 5.2 — In-memory buffering

- File: `interceptor.cjs` lines 222–234; `_http_observe.py` symbols `_append` and `_lock` lines 107, 520–522
- Current behavior: calls accumulate in a process-local list. Python appends under `threading.Lock`. Node replaces `Array.push` to fire telemetry after each push. There is no disk write per call.
- Evidence: `_calls` and `_append`.
- Confidence: HIGH
- Limitation: `vantio tail --follow` cannot show calls until the exit rewrite, because the file does not grow during the run.
- Roadmap IDs: OF-14, OF-23-15, OF-23-16
- Classification: `PARTIAL`

## Topic 6 — Read

### Finding 6.1 — CLI JSON read

- File: `vantio.js`, symbols `readJsonFile`, `loadRunLog`, `tryLoadRunLog`, `listValidRunEntries`
- Lines: 720–732, 977–1026
- Current behavior: `readJsonFile` returns `{ unreadable }` or `{ corrupt }` or `{ json }`. `loadRunLog` exits 1 when the file is unreadable, corrupt, or `vantio_run_log !== "1"`. `tryLoadRunLog` returns null for those cases. `listValidRunEntries` exits 1 on corrupt via `failUnreadable`.
- Evidence: those functions.
- Confidence: HIGH
- Limitation: readers do not check `schema_version`. A future schema with the same marker is accepted.
- Roadmap IDs: OF-16, OF-23-30
- Classification: `PARTIAL`

### Finding 6.2 — MCP read skips corrupt files

- File: `packages/vantio-optics-mcp/src/runs.js`, symbol `listRunLogs`
- Lines: 13–48
- Current behavior: corrupt JSON is skipped. Valid logs require `vantio_run_log === "1"`. Sort key is file `mtime_ms`, not `generated_at`.
- Evidence: the `catch` that continues, and the sort.
- Confidence: HIGH
- Limitation: CLI search/discover exit on corrupt files; MCP hides them. The same directory does not have one read policy.
- Roadmap IDs: OF-23-09, OF-23-24
- Classification: `CONFLICTING`

## Topic 7 — Tail

### Finding 7.1 — Tail reads the end of one finished file

- File: `vantio.js`, symbols `tailCommand`, `printTailCalls`
- Lines: 1168–1273
- Current behavior: tail loads one run (prefix or most recent), prints the last `n` calls (default 20), or `--all`. `--json` is rejected together with `--follow`. `--follow` uses `fs.watch` on that path and prints calls only when `calls.length` grows.
- Evidence: `printTailCalls` slices `calls.slice(-lines)`; `refresh` compares lengths.
- Confidence: HIGH
- Limitation: because writers replace the whole file at exit, follow does not stream a live run. There is no pager and no `NO_COLOR` handling in `vantio.js` (`rg` found no `NO_COLOR`).
- Roadmap IDs: OF-07, OF-10, OF-23-24
- Classification: `PARTIAL`

## Topic 8 — Search

### Finding 8.1 — Substring scan of every run file

- File: `vantio.js`, symbols `searchCommand`, `callSearchBlob`
- Lines: 1028–1161
- Current behavior: optional free-text query plus `--host`, `--provider`, `--action`, `--run`, `--since` (`24h`, `7d`, `30d`). Matching is `String.includes` on lowercased hostname, provider, action, and a blob of trace id, host, provider, method, path, action, error, error_class. Results go through `publicCall`, which keeps hostname, provider, method, path, bytes, ts, http status, and the two display statuses.
- Evidence: the filter loop.
- Confidence: HIGH
- Limitation: no pagination, no cost limit, no index, no evidence-origin filter. The query is not a regular expression. Every `.json` file in the reader directory is parsed.
- Roadmap IDs: OF-01, OF-23-11, OF-23-24
- Classification: `PARTIAL`

## Topic 9 — Diff

### Finding 9.1 — Host rollup diff of two runs

- File: `vantio.js`, symbols `diffCommand`, `hostRollup`, `runTotals`
- Lines: 1276–1401
- Current behavior: two run prefixes. Output is total call delta, total byte delta, hosts added, hosts removed, and hosts whose call or byte counts changed. Prefers `summary.by_host` when present, otherwise sums `calls`.
- Evidence: `result` object in `diffCommand`.
- Confidence: HIGH
- Limitation: Python logs omit `by_host`, so diff falls back to call rows. Diff is not a trend over a time window. It does not compare status or duration.
- Roadmap IDs: OF-04, OF-23-06
- Classification: `PARTIAL`

## Topic 10 — Proof

### Finding 10.1 — Proof is a rendering of the run file

- File: `vantio.js`, symbols `proveCommand`, `proofJson`, `generateHtmlReport`, `generateMarkdownReport`, `publicCall`
- Lines: 428–644, 763–854
- Current behavior: `vantio prove` reads one run log and writes HTML (default, file `vantio-proof-<id>.html` in the current directory), Markdown, or unstable JSON. `--from` reads a caller-chosen path. `--out` writes that path. HTML/Markdown include trace id, pid, times, duration, cli version, host, status labels, http status, bytes, and timestamp. `publicCall` drops action, error, path query (path was already stored without query), and redaction counts from the JSON proof view. HTML default `writeFileSync` does not pass mode `0o600`.
- Evidence: `writeProof` and `publicCall`.
- Confidence: HIGH
- Limitation: the operational file and the proof rendering are the same evidence, re-encoded. There is no separate manifest, content hash, origin, or completeness field. `docs/prove.md` lines 91–102 describe action badges, machine, redacted count, and blocked count in the HTML report. `generateHtmlReport` uses `displayCall` columns (host, Optics status, application outcome, http, bytes, time) and does not print `log.machine`. The stored Node summary has redacted and blocked counts; the HTML generator’s visible table does not use action badges.
- Roadmap IDs: OF-23-25, OF-23-22
- Classification: `CONFLICTING`

### Finding 10.2 — MCP proof markdown

- File: `packages/vantio-optics-mcp/src/runs.js`, symbol `proveMarkdown`
- Lines: 87–149
- Current behavior: builds Markdown that includes action, method, path, status, duration, bytes, and a residual paragraph that names Phantom Engine pricing. It prints `log.machine` and defaults schema display to `1` when `schema_version` is missing (`log.schema_version ?? 1`).
- Evidence: the returned string template.
- Confidence: HIGH
- Limitation: CLI proof and MCP proof do not present the same columns. Writers do not set `machine`, so the MCP line is an em dash unless an older file contains it.
- Roadmap IDs: OF-23-25, OF-23-32
- Classification: `CONFLICTING`

## Topic 11 — Locking

### Finding 11.1 — No cross-process file lock

- File: `_http_observe.py` line 107 (`_lock`); `interceptor.cjs` `_calls` lines 222–234
- Current behavior: Python locks the in-memory list. Node relies on the single-threaded event loop. No `flock`, lockfile, or SQLite lock exists on the run directory.
- Evidence: repository search of CLI and Python observe modules shows no file-lock API around the run log write.
- Confidence: HIGH
- Limitation: two writers can replace or interleave the same path. Readers do not take a shared lock.
- Roadmap IDs: OF-01, OF-23-16
- Classification: `ABSENT`

## Topic 12 — Retention

### Finding 12.1 — No retention policy

- File: CLI command dispatch `vantio.js` lines 1640–1670
- Current behavior: commands are run, demo, status, logout, discover, prove, search, tail, diff. There is no prune, no max-age, and no max-size. Files remain until something outside this program deletes them.
- Evidence: the `switch` and the absence of a retention symbol in the CLI and Python writers.
- Confidence: HIGH
- Limitation: disk growth is unbounded, which matches the roadmap’s “no silent delete” rule only because nothing deletes. There is no customer-configured limit either.
- Roadmap IDs: OF-02, OF-23-23
- Classification: `ABSENT`

## Topic 13 — Cleanup

### Finding 13.1 — Logout deletes config only

- File: `vantio.js`, symbols `clearConfig`, `logoutCommand`
- Lines: 251–256, 384–392
- Current behavior: `vantio logout` deletes `~/.vantio/config.json` if present. It does not read the file and does not delete `runs/`.
- Evidence: `rmSync(configPath())` only.
- Confidence: HIGH
- Limitation: there is no selective deletion of one run, no deletion manifest, and no dry-run.
- Roadmap IDs: OF-02, OF-23-23
- Classification: `ABSENT`

## Topic 14 — Permissions

### Finding 14.1 — Unix modes on create, not a full ACL story

- File: `interceptor.cjs` lines 3697 and 3765; `_http_observe.py` lines 2491 and 2533–2536; `telemetry.cjs` lines 67–69; `_telemetry.py` lines 69–75
- Current behavior: run directory `mkdir` uses mode `0o700` when the writer creates it. Run files are written mode `0o600` (Python chmod after write). Telemetry id file is mode `0o600`. Telemetry directory create does not pass a mode. `directoryBytes` in `vantio.js` (lines 1480–1501) skips symbolic links when summing size. Writers do not test whether `runs` is a symlink before writing.
- Evidence: the mode arguments and `ent.isSymbolicLink()`.
- Confidence: HIGH
- Limitation: modes are subject to umask on create and are not reapplied if the directory already exists. No Windows ACL handling is present. A pre-created `~/.vantio` from telemetry can remain broader than `0700` while `runs` is `0700`.
- Roadmap IDs: OF-23-17
- Classification: `PARTIAL`

## Topic 15 — JSON schema markers

### Finding 15.1 — Marker split across file and stdout

- File: `optics-cx.cjs` lines 6 and 112–114; `interceptor.cjs` lines 3713–3715; `_http_observe.py` lines 2497–2500; `_outcome.py` line 16
- Current behavior: CLI stdout JSON is wrapped by `withSchema` and always gains `schema_status: "unstable-pre-1.0"`. The Node run file sets `vantio_run_log` and `schema_version: 2` and does not set `schema_status`. The Python run file sets all three, plus `workflow`. `docs/optics-otel-mapping.md` lines 5–7 say CLI JSON includes `schema_status`. That is true of command stdout and false of the Node run file.
- Evidence: the three emitters.
- Confidence: HIGH
- Limitation: readers key off `vantio_run_log === "1"` only. `schema_version` is not enforced. No JSON Schema document is shipped as a validator in these paths.
- Roadmap IDs: OF-16, OF-23-02, OF-23-30
- Classification: `CONFLICTING`

## Topic 16 — Run, trace, process, provider, and status fields

### Finding 16.1 — What is actually stored

- File: Node envelope `interceptor.cjs` 3713–3758; Python envelope `_http_observe.py` 2497–2527; display `optics-cx.cjs` `rollupCalls` 93–103 and `applicationStatusFromHttp` 53–59
- Current behavior:
  - Run identity: one `trace_id` per process attach. No separate `run_id`.
  - Process: Node stores `pid` and `ppid`. Python does not.
  - Provider: Node `guessProvider` on write. Python `resolve_provider` inside `apply_customer_outcome`, otherwise `"other"`.
  - Status: free-tier `action` is `OBSERVED`. Display `opticsStatus` for any recorded call is `SUCCESS` (`opticsStatusForRecordedCall`). `applicationStatus` is derived from HTTP status: 200–399 `SUCCESS`, 400–599 `APPLICATION_ERROR`, otherwise `UNAVAILABLE`. Mixed codes in one run become `PARTIAL`. Empty call list becomes `NOT_OBSERVED` for both. `ok` on the stored call is ignored by `applicationStatusFromHttp` (comment at `optics-cx.cjs` lines 51–52).
- Evidence: those functions. Python `_ok_for_http_status` (lines 569–572) now sets `ok` false for 4xx/5xx. The CLI comment still describes Python 3.0.x storing `ok: true` on errors. Current Python source does not do that.
- Confidence: HIGH
- Limitation: span id, parent span id, session id, and parent process id beyond Node `ppid` are absent. Optics status `SUCCESS` means “a call record exists,” not “the provider succeeded.”
- Roadmap IDs: OF-03, OF-23-01, OF-23-04, OF-23-21
- Classification: `PARTIAL`

### Finding 16.2 — `machine` is documented and not written

- File: `docs/prove.md` lines 94 and 115; `runs.js` line 120; writers inspected in findings 1.2 and 2.2
- Current behavior: prove docs and MCP markdown expect `log.machine`. Neither current writer assigns `machine`.
- Evidence: doc example versus writer object literals.
- Confidence: HIGH
- Limitation: a reader cannot tell a missing machine from an older file that never had the field.
- Roadmap IDs: OF-23-04, OF-23-32
- Classification: `CONFLICTING`

## Topic 17 — Privacy filters

### Finding 17.1 — Structural capture drops query and body

- File: `interceptor.cjs`, symbol `extractRequestMeta` lines 102–140; `responseMeta` lines 142–156; `_http_observe.py` `_host_port_from_url` lines 500–514
- Current behavior: persisted request URL parts are pathname and scheme, not the query string. Hostname comes from URL parsing. Bodies are not fields on the free-tier record. `content_type` is the media type only.
- Evidence: `path = u.pathname`; Python `parsed.path`.
- Confidence: HIGH
- Limitation: path segments can still carry secrets. Header maps are not stored, but a secret placed in a path is. There is no allowlist check at write time; the writer assigns a fixed key set and also, on Python, spreads `**extra` and then adds outcome strings that include `nextAction` prose.
- Roadmap IDs: OF-13, OF-23-20, OF-23-22
- Classification: `PARTIAL`

### Finding 17.2 — Redaction rewrites bytes in flight only when enforcement policy is on

- File: `interceptor.cjs` `redactBody` lines 392–399 and free-tier branch 813–870; `_http_observe.py` `_apply_body` lines 709–719
- Current behavior: free mode does not redact. Paid or policy mode can rewrite request bodies and store a `redactions` count, not the redacted text. Python transport classification (`test_outcome_clarity.py` `test_transport_classification_ignores_exception_text`) keeps exception message text, including a secret fixture, out of the phrase.
- Evidence: free-tier push has no redaction step; tests assert the classifier phrase.
- Confidence: HIGH
- Limitation: `docs/observe-only.md` lines 23–26 say Optics does not capture prompts and does not redact. The free path matches that. The same files can redact or block when not in free mode. A prompt canary test (`account-retirement.test.js` lines 221–234) asserts the canary is absent from the child stdout URL list, not from the run-log file.
- Roadmap IDs: OF-13, OF-23-22
- Classification: `PARTIAL`

## Topic 18 — Provider detection

### Finding 18.1 — Two algorithms

- File: `packages/vantio-cli/bin/llm-hosts.cjs`, symbol `guessProvider` lines 84–112; `packages/vantio-agent-sdk-py/vantio/_outcome.py`, symbol `resolve_provider` lines 189–205
- Current behavior: Node matches substrings (`h.includes("openai")`, `"anthropic"`, `"azure"`, and others) and returns `"local"` or `"other"`. Python uses an exact catalog host, a DNS suffix of a catalog host, regional patterns, or Ollama on port 11434, and otherwise leaves the record as upstream rather than guessing. Python’s module comment (lines 18–19) says identity is not inferred from a substring of an arbitrary hostname.
- Evidence: both functions.
- Confidence: HIGH
- Limitation: the same hostname can be `openai` in a Node log and `other` / upstream in a Python log. Node can label a non-provider host `openai` when the substring matches.
- Roadmap IDs: OF-23-21, OF-23-30
- Classification: `CONFLICTING`

### Finding 18.2 — In-scope host catalog

- File: `llm-hosts.cjs` lines 10–35 and `catalogInScope` 76–82; `_http_observe.py` `_LLM_HOSTS` and `_in_scope` lines 79–80 and 241–248
- Current behavior: both catalogs list named LLM API hosts plus regional Bedrock, Vertex, and Hugging Face endpoint patterns, plus Ollama on localhost port 11434. Extra hosts come from `VANTIO_EXTRA_LLM_HOSTS`. Python `_in_scope` also treats policy `blocked_hosts` and `allowed_hosts` as in scope.
- Evidence: the catalogs. Comments in both files say to keep them in lockstep.
- Confidence: HIGH
- Limitation: lockstep is a comment, not a shared generated table. Coverage of clients is the set of patched libraries, not a `vantio status --coverage` command. `status` (`vantio.js` `sdkRows`, lines 1504–1518) reports whether seven Node provider packages resolve from the current working directory.
- Roadmap IDs: OF-12, OF-23-05
- Classification: `PARTIAL`

## Topic 19 — URL and destination normalization

### Finding 19.1 — Hostname and path, limited normalization

- File: `interceptor.cjs` `destFromHref` lines 776–779; `extractRequestMeta` lines 116–124; Python `_host_port_from_url` lines 500–514; `llm-hosts.cjs` `hostListed` lines 37–49
- Current behavior: destination identity for scope checks is the URL hostname, lowercased in catalog checks, plus port (default 443/80 in `destFromHref`). Path stored is `pathname` or `parsed.path`. Query is not stored. Case folding is applied for catalog membership, not as a stored canonical field. IPv6, redirects, and proxies are not rewritten to a canonical destination. Redirect targets are observed only if a later request is itself in scope.
- Evidence: those parsers. No redirect-following normalizer exists in the writers.
- Confidence: HIGH
- Limitation: default ports may be stored only on some code paths (`destFromHref` computes port for scope; the free-tier call record does not include `port`). Python may store `port` only when a caller passed it.
- Roadmap IDs: OF-23-20
- Classification: `PARTIAL`

## Topic 20 — Demo and fixture

### Finding 20.1 — Demo writes a normal run file

- File: `vantio.js`, symbol `demoCommand`
- Lines: 1404–1477
- Current behavior: `vantio demo` builds one call to `optics-demo.invalid`, provider `openai`, `POST /v1/chat/completions`, status 200, bytes 0, `action: "OBSERVED"`, `duration_ms: 0`, and writes it with `vantio_run_log`, `schema_version` 2, `plane` `"optics"`, under the CLI runs directory. Stdout says the demo is an in-process stub with no network. The file has no origin field.
- Evidence: the `log` object and `writeFileSync`. Test `optics-cx.test.js` describe `vantio demo` checks stdout copy, not origin.
- Confidence: HIGH
- Limitation: discover, search, tail, diff, and prove treat this file like any other run. `optics-cx.test.js` `writeRun` and `inspect.test.js` `writeRun` create the same shape on disk for tests, outside the product command, with no origin field.
- Roadmap IDs: OF-23-13, OF-04
- Classification: `PARTIAL`

## Topic 21 — Import and export

### Finding 21.1 — Export is prove; import is not a store operation

- File: `vantio.js` `proveCommand` lines 784–789 and 832–854
- Current behavior: `--from` reads a path and renders it when the JSON value is an object. That path does not require `vantio_run_log` on the render path (the marker check is in `loadRunLog`, which `--from` does not call). Nothing copies the file into `runs/` with an imported origin. There is no JSONL export, no tabular export, and no OTLP exporter. `docs/optics-otel-mapping.md` line 3 states Optics does not export OTLP.
- Evidence: `proveCommand` control flow after `readJsonFile`.
- Confidence: HIGH
- Limitation: a caller can render a JSON object that was not produced by Optics. The rendering can be shared as a proof artifact without an origin stamp.
- Roadmap IDs: OF-23-25, OF-23-19
- Classification: `PARTIAL`

## Topic 22 — Version skew

### Finding 22.1 — Schema version is a constant, not a negotiation

- File: both writers set `schema_version: 2`. Readers ignore it except MCP display (`runs.js` line 127).
- Current behavior: Node CLI 0.3.24 and Python package version 3.1.0 (`vantio/__init__.py` line 26, `pyproject.toml` line 10) can write the same directory. Their envelopes differ (findings 1.2 and 2.2). No migration function exists. A newer file is not refused.
- Evidence: version constants and reader predicates.
- Confidence: HIGH
- Limitation: mixed files are already possible. Rollback to an older reader is “best effort parse,” not a refusal.
- Roadmap IDs: OF-16, OF-23-30
- Classification: `ABSENT`

## Topic 23 — Corrupt records, disk full, and write failure

### Finding 23.1 — Corrupt JSON handling is command-specific

- File: `vantio.js` `readJsonFile` 720–732; `failUnreadable` 734–737; `firstRunScan` 1521–1547; `discoverLocalCommand` 876 and 890; `runs.js` 46–48
- Current behavior: parse failure is `corrupt`. `status` keeps scanning and sets `runs.opticsStatus` to `OPTICS_ERROR` when any file is corrupt. `search`, `discover`, and `prove --list` call `failUnreadable`, which exits 1. `discoverLocalCommand` also has a `catch` that skips, but `failUnreadable` exits before that catch can continue the loop. MCP skips corrupt files. No command rebuilds an empty store.
- Evidence: the control flow above.
- Confidence: HIGH
- Limitation: one bad file blocks some inspections and disappears from others. There is no integrity record.
- Roadmap IDs: OF-23-09, OF-23-16, OF-23-30
- Classification: `PARTIAL`

### Finding 23.2 — Write errors are swallowed

- File: `interceptor.cjs` lines 3766–3768; `_http_observe.py` lines 2537–2538; `vantio.js` `writeProof` 836–844
- Current behavior: run-log `try/except` and `try/catch` discard every error, including `ENOSPC` / `EIO`. The agent exit continues. No product-health record is stored. `vantio prove` write failure exits 1 and prints the first line of the error. It does not label a partial proof.
- Evidence: empty `catch` / `except Exception: return`.
- Confidence: HIGH
- Limitation: evidence loss on a full disk is silent. That matches fail-open for the application and violates the roadmap’s “no silent evidence loss” design bullet. Both statements are true of different layers.
- Roadmap IDs: OF-14, OF-23-15, OF-23-16
- Classification: `PARTIAL`

## Topic 24 — Process exit, interruption, clock, and duration

### Finding 24.1 — Exit hook only

- File: `interceptor.cjs` line 3679 `process.on("exit")`; `_process_wrap.py` `atexit.register`
- Current behavior: the log is written from the exit hook or `uninstall`. `SIGKILL`, power loss, and a killed interpreter skip that hook. There is no `COMPLETE`, `PARTIAL`, `INTERRUPTED`, `ABANDONED`, or `RECOVERED` field. `vantio run` (`vantio.js` 372–380) forwards the child signal and, with `--json`, emits `opticsStatus: "OPTICS_ERROR"` on a signal. That JSON is stdout of the CLI, not a field inside the run file.
- Evidence: the handlers and `writeRunJson`.
- Confidence: HIGH
- Limitation: an empty or missing file is indistinguishable from “never attached” versus “killed before flush,” except that Node tries to write even for zero calls when the hook runs.
- Roadmap IDs: OF-14, OF-23-16
- Classification: `ABSENT`

### Finding 24.2 — Wall-clock duration

- File: `interceptor.cjs` free-tier `duration_ms = Date.now() - t0` lines 823 and 854, envelope `duration_ms: now - _startMs` line 3726; Python `_duration_ms` lines 597–598
- Current behavior: both use wall clocks (`Date.now`, `time.time`), not a monotonic clock. Python clamps with `max(0, ...)`. Node does not clamp. Timestamps are UTC ISO strings (`toISOString` with `Z` on Node; Python `datetime.now(timezone.utc).isoformat()`, which uses a `+00:00` offset).
- Evidence: those expressions.
- Confidence: HIGH
- Limitation: a backward step of the wall clock can store a negative Node duration. Tied timestamps have no sequence number. Nothing in source claims causality from timestamp order.
- Roadmap IDs: OF-23-16
- Classification: `PARTIAL`

## Topic 25 — Product telemetry and test coverage

### Finding 25.1 — Product telemetry is a separate channel

- File: `packages/vantio-cli/bin/telemetry.cjs`; `packages/vantio-agent-sdk-py/vantio/_telemetry.py`
- Lines: Node 1–12, 38–50, 81–110; Python 1–14, 34–47, 98–140
- Current behavior: disabled unless `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` forces off. POST to `{VANTIO_INGEST_URL or https://vantio.ai}/api/v1/telemetry` with an allowlist: `anonymousId`, `runtime`, `runtimeVersion`, `os`, `event` (`run` or `summary`), `hosts` (max 50), `callCount`, and optional `sdkVersion`, `cliVersion`, `redactedCount`, `blockedCount`, `framework`. Timeout 3 seconds. Errors swallowed. Node captures `fetch` at require time so the ping does not re-enter the patched fetch. Id file is `~/.vantio/telemetry-id`, not under `runs/`. Node fires once from `vantioRecordCall` after the first push (`interceptor.cjs` `sendRunTelemetryOnce`, lines 622–636). Python `send_run_telemetry_once` fires from `shield()` before observation, so that ping’s `callCount` is 0.
- Evidence: both modules and their tests (`telemetry.test.js`, `test_telemetry.py`).
- Confidence: HIGH
- Limitation: telemetry is off by default and separate from run logs. It is still optional product telemetry, not customer evidence. `status` reports posture only (`telemetryPosture` in `optics-cx.cjs` lines 105–110) and does not show last result.
- Roadmap IDs: OF-23-31
- Classification: `CURRENTLY_IMPLEMENTED`

### Finding 25.2 — Test coverage that exists, and coverage that does not

- File: `packages/vantio-cli/test/*.js`; `packages/vantio-agent-sdk-py/tests/*.py`
- Current behavior, from test names and the assertions read for this inventory:
  - Present: CLI dispatch, prove/tail usage errors, demo stdout, status JSON, search/tail/diff fixtures, corrupt run file exit 1 (`optics-cx.test.js` “a corrupt run file is exit 1”), `schema_status` on command JSON, interceptor integration through a child process (fetch, undici, http, http2, net, websocket, curl-class spawns, block/redact when a mock control plane is configured), telemetry allowlist and default-off, llm host catalog, Python urllib/requests/httpx/aiohttp/urllib3/pycurl/socket/subprocess observe and block, HTTP status versus `ok`, transport classification that drops exception text, wheel/sdist source match, version match.
  - Not present in these tests: SQLite, migrations, retention, cross-process locking, symlink confinement of the runs directory, disk-full evidence, `SIGKILL` flush, monotonic duration, evidence-origin exclusion of demo files, a privacy corpus that asserts header and query secrets never appear inside `~/.vantio/runs`, Node versus Python envelope equality, or customer-workload validation.
- Evidence: test file names and the assertions cited in findings 17.2 and 25.1. This inventory did not re-run the suites.
- Confidence: HIGH for absence of store/migration tests (no such files or symbols). MEDIUM for “no test asserts the canary inside the run file,” based on the canary test that checks stdout.
- Limitation: unit and integration tests are not `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`. This inventory does not assign those tiers.
- Roadmap IDs: OF-13, OF-14, OF-18, OF-23-22, OF-23-34
- Classification: `PARTIAL`

## Docs checked against source

| Doc claim | Source | Inventory result |
| --- | --- | --- |
| `docs/sight-loop.md` lines 107–111: native sockets and curl are not observed | `interceptor.cjs` lines 1–12 and Python `_install_socket` / `_install_curl_spawn` patch those paths when the process is wrapped | `CONFLICTING` |
| `docs/observe-only.md` lines 75–80: native sockets and curl can be skipped | Same patches observe them inside a wrapped process; unwrapped processes stay silent | `PARTIAL` (true for unwrapped processes, false as a blanket statement about wrapped processes) |
| `docs/prove.md` sample log includes `machine` and says write happens when calls were observed | Node writes without `machine` and writes even with zero calls; Python skips zero calls and also omits `machine` | `CONFLICTING` |
| `docs/prove.md` lines 157–159: `--audit` labels events in the proof artifact | `VANTIO_AUDIT_MODE` is copied into child env (`vantio.js` 343) and sent on cloud `report()` (`interceptor.cjs` 559). It is not a field in the local log or in `proofJson` | `CONFLICTING` |
| `docs/sight-loop.md` line 62: Optics does not block, redact, or cap | Free mode matches that. Non-free mode in the same files can block, redact, and cap | `CONFLICTING` as a description of the whole file; true of `FREE_MODE` |
| Roadmap: per-run JSON does not scale; search/tail/diff scan files | `searchCommand` and `listValidRunEntries` parse every JSON file | `CURRENTLY_IMPLEMENTED` behavior, and it is the gap OF-01 describes |

## A0 exit

The 25 topics are recorded from source. Disagreements are left as `CONFLICTING`. No product file was modified.

Classification: `OPTICS_FOUNDATION_A0_INVENTORY_COMPLETE`
