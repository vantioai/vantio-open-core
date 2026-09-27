# PKG-02 Unit D design

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

`vantio-pkg02 run node <script>` is a separate launcher. It sets `NODE_OPTIONS` so the child loads `packages/vantio-cli-pkg02/src/preload.cjs` and then the frozen `packages/vantio-cli/bin/interceptor.cjs`. The frozen file is not edited.

The preload replaces `fs.writeFileSync` before the interceptor binds it. When the interceptor later writes a `vantio_run_log` `"1"` file with `schema_version` `2` under the runs directory, the future writer parses that payload and writes a canonical document instead. `VANTIO_PKG02_WRITER=0` passes the frozen bytes through.

The child also wraps `globalThis.fetch` after the interceptor installs its own fetch. The wrapper records whether `content-length` was present. The frozen exit path stores `call.bytes || 0`, which collapses a missing length to `0`. The future file uses the wrapper note: a missing length omits `response_bytes`, and an explicit `0` stays `0`.

Each kept call is validated with `validateEvidence` before it is written. Enforcement actions are not observations. `ALLOWED` and `BLOCKED_*` are dropped. `action` on a written observation is `OBSERVED` or absent.

`run_id` receives the frozen `trace_id`. The canonical file does not also store that string as `trace_id`. `schema_version` on the file is `0`. Legacy `2` is only `compatibility.legacy_schema_version`.

`evidence_origin` `LOCAL_OBSERVATION` is written when the contract accepts producer `node_interceptor` and version `0.4.0-pkg02-unit-d`. A validator fault writes `optics_status` `OPTICS_ERROR` and does not claim that origin.

The workload exit code is the child status. A fault injection still returns that status. The in-process `application_result` passed to the composer is returned as it was passed.
