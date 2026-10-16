# T4 — MCP and tool-call awareness

Status: design, pre-code.  
Track: Market-readiness gap program, T4.  
Repository: `vantioai/vantio-open-core`.  
Branch: `gap/t4-mcp-awareness`.  
Design timestamp (UTC): 2026-10-16T15:48:23Z.  
Revised (UTC): 2026-10-16T16:03:15Z after council `COUNCIL_UNSAT` (seats S1–S4 and S6), then wording corrections N1–N10 required by the re-review. The earlier stamp `2026-10-16T16:05:00Z` was ahead of the clock and is withdrawn. No product code is in this revision.

This document is the phase-1 boundary check. No product code belongs in the same commit as the council verdict.

## 1. What this track builds

A userspace library, `@vantio/mcp-awareness`, that:

1. Parses Model Context Protocol (MCP) JSON-RPC on stdio, HTTP, and SSE.
2. Records a closed-set method label, the operator's own tool name when the call names that tool, and an argument shape whose key names are operator-known. Everything else is a keyed digest.
3. Applies operator policy: allow a read tool and deny a write tool on the same server, match argument rules, detect tool-name spoofing, and detect a rug-pull (a tool description or input schema that changed after operator approval).
4. Detects tool results that carry injected instructions toward a protected workload, by pattern and structure. Logs them. Blocks them only when the operator turns that option on.
5. Observes from the workload's existing streams. It does not require a proxy hop.

"In-process gate" in this track means a library function inside a Node workload. It is not the Phantom Engine product, and it is not enforcement for a host that is not enrolled. Phantom Engine, here, means a future host observe path for an enrolled Linux workload. That attachment is not implemented. Host enforce is a separate Roadmap item and is not specified as a mechanism.

## 2. Scope boundary

In scope:

- Supported AI workloads. For Phantom Engine claims, enrolled Linux machines only.
- Both directions. Outbound: constrain the customer's own tool calls. Inbound: a tool result or a server-initiated sampling request that reaches that workload.
- Permissions in order: Observe, then Enforce. Control is not part of this track.

Out of scope, and not built:

- Prompt or answer scoring, content moderation, model evaluation.
- An identity provider.
- Generic antivirus, WAF, or DDoS protection.
- Robotic physical safety.
- A required network or process proxy.
- Parsing JSON inside an eBPF program.
- Changing the public website, the root README, or any "Shipped" claim.
- Wiring this library into the default `vantio run` interceptor or into the public tool list of `@vantio/gate-mcp`.
- npm publish, GHCR, tags, customer release, production signing.
- Prices. Public pricing language elsewhere stays "Contact Vantio". This packet contains none.

Phantom Engine still covers supported AI workloads on enrolled Linux only. This track does not widen that.

## 3. Threat model

Assets:

- The operator's allow and deny decisions.
- The tool catalog the operator approved (the operator's tool names and the pins in the policy file).
- The protected workload, which will treat a tool result as data to feed a model.

Trust:

- Operator policy is the only authority. A model, a tool, an MCP server, or this library's own classifier does not grant a permission.
- `serverInfo.name`, `annotations.readOnlyHint`, and any other server-supplied label are untrusted. They are not read/write classification.
- `server_id` is an argument from the host integration, a label the operator chose for a child process or an origin. It is never read from the JSON-RPC message or from `serverInfo.name`.

Adversaries:

| Id | Adversary | Capability |
| --- | --- | --- |
| A1 | Compromised or malicious MCP server | Sends `tools/list`, then changes a description or schema. Sends tool results. Sends `sampling/createMessage`. |
| A2 | Compromised workload | Issues `tools/call` with attacker-chosen names and arguments. |
| A3 | Man-in-the-parser | Crafts duplicate JSON keys, overlong frames, deep nesting, bad UTF-8, homoglyph tool names, mixed-script names, hidden Unicode. |
| A4 | Confused deputy on one server | A server offers both a read tool and a write tool. The workload is allowed to read and must not write. |

Cases:

| Id | Case | Detection | Not this |
| --- | --- | --- | --- |
| C1 | Read allowed and write denied on one `server_id` | Operator class or per-tool effect | Inferring read/write from the tool name or from `readOnlyHint` |
| C2 | Argument rule | Ephemeral compare of a policy-named key (`prefix`, `suffix`, `equals`, `enum`, `type`, `exists`, `absent`, `len_lte`, `len_gte`) | Regular expressions. Scoring the argument text |
| C3 | Tool-name spoof | Hidden characters, NFKC mismatch, mixed script, confusable skeleton equal to a different operator-named tool, any duplicate JSON key | A claim that every Unicode spoof is covered. The skeleton is a finite map, not the whole Unicode confusables database |
| C4 | Rug-pull | Operator-supplied `description_sha256` or `schema_sha256` differs from the hash of a later `tools/list`. `notifications/tools/list_changed` marks the catalog stale | Treating the first seen description as approval. That would let the server approve itself |
| C5 | Inbound instruction carriage | Structural patterns in a tool result, a `resources/read` result, a tool `description`, or `initialize` `instructions`, listed in section 8 | Judging whether prose is "malicious". Plain-language instructions with none of those structures are not flagged. `prompts/get` results are not scanned: their schema is role and content by design |
| C6 | Server asks the workload to sample | Method `sampling/createMessage` on a server-to-client request | Content scoring of the sampling prompt |

What we do not claim: this detector does not stop a tool result that is ordinary prose telling a model to ignore its instructions. That is content scoring, and it is out of scope. The risk register keeps that gap.

## 4. Wire formats

The parser accepts the JSON-RPC envelopes used by MCP on these transports. It does not negotiate the MCP lifecycle and it does not implement `initialize` as a session protocol. It parses messages it is given.

| Transport | Framing | Notes |
| --- | --- | --- |
| `stdio` | One JSON-RPC message per line, LF or CRLF. Empty lines ignored | MCP stdio. Messages must not contain raw newlines |
| `stdio` content-length | `Content-Length` header, then a body | Recognized so an LSP-style frame is not read as a broken line. Not the current MCP stdio default |
| `http` | A captured HTTP/1 request or response. Body interpreted by `Content-Type` | `application/json` is one JSON body. `text/event-stream` is handed to the SSE framer. Duplicate or non-integer `Content-Length` is rejected |
| `sse` | Events split on a blank line. `data:` lines joined with `\n`. Comment lines (`:`) ignored | Covers legacy HTTP+SSE and the streamable-HTTP SSE response |
| `json-body` | An already-separated body, as `fetch` exposes after decode | Used when the caller already split headers and body |

Not reassembled here: raw HTTP chunked transfer encoding. `fetch` bodies are already decoded. A raw chunked byte stream returns `chunked_unsupported` and is not treated as an allow. Doing the dechunk is an approval-gate item if a future host capture needs it.

JSON-RPC batches (a top-level array) are `batch_rejected`. MCP does not use batches. A batch is never an allow.

## 5. What is kept

A per-process key of 32 random bytes is created when the runtime starts (`node:crypto` `randomBytes`). The production entry `createRuntime()` does not accept a key. A test-only helper, not re-exported from the package entry, may inject one. A caller-chosen key would make digests confirmable, so that helper is not a production parameter. The key is never written to a record, a session export, a log, or the evidence file. Digests of attacker-controlled strings are HMAC-SHA256 with that key. The key is not shared across processes, so those digests cannot be correlated after a restart. That is an operational limit, not a retention of the text.

Kept on an observation record:

- Transport, direction, operator `server_id`, UTC timestamp.
- JSON-RPC kind (`request`, `notification`, `result`, `error`) and id type (`number`, `string`, `absent`).
- A finite numeric id, which cannot carry prose.
- For a string id: `id_hmac` only. The raw string is not a record field and not a session field. The in-process pair gate may copy the raw id into the one error frame it is writing, then drop it.
- Method label, and only when the method string is an exact member of the closed set in section 10. Otherwise `method_class: "other"` and `method_hmac`.
- Tool name, raw, only when it is an exact key of the operator `tools` object for that server. Any other name is `tool_hmac` plus spoof findings. A name that merely passes the stability checks is not stored raw. The server and the model can put prose in `params.name`.
- Argument shape: type, child types, string byte lengths, array lengths. A key name is raw only when it is an exact key named by an operator argument rule for that tool, or an exact property name previously stored from a pinned schema (section 10). Every other key is `key_hmac`. No string values.
- Finding ids and the decision.
- Pin results only: `description_pin_match` and `schema_pin_match` are `match`, `mismatch`, or `unpinned`. The runtime computes sha256 to compare with the operator's pin, then discards the digest. The record and the session do not store a digest of observed description or schema text, so a reader of the record cannot confirm a guessed description. The operator pin itself stays in the policy, which is operator configuration.

Ephemeral, dropped before the record is returned:

- String values for rule-named keys, used only to evaluate a rule.
- Frame bytes, description text, instructions text, and result text, used only to classify structure and to compute the pin comparison.

Never kept:

- Conversation content, tool-result text, file contents, prompts, completions, image bytes, raw string ids, tool names the operator did not write, argument values, argument key names the operator did not name.
- A log line that echoes any of those.

Retention caps, and what happens past them:

| Cap | Past the cap |
| --- | --- |
| 8 distinct rule keys per server | The server policy is `policy_incomplete`. Extra rules are `invalid_rules` and are not applied |
| 512 bytes for one rule value | The value is not compared. Finding `retain_truncated`. That rule does not match. Enforce withholds the call. Observe records the finding and does not emit `ALLOW` |
| Rule key is not a top-level argument name matching `^[A-Za-z0-9_.-]{1,64}$` | The rule is dropped as `invalid_rules`. A dotted name is a literal top-level key, not a nested path. Nested paths are out of scope |

`suffix`, `equals`, and `enum` compare JavaScript string code units. A `prefix` rule is a path prefix. Before that comparison the candidate and the rule value are decoded once and normalized lexically: `.` and `..` are resolved, repeated slashes collapse, and a NUL byte is rejected. A path that escapes the root, stays ambiguous, or still contains `%2e` or `%2f` after that one decode is `path_rejected`. In enforce that is a withhold. The match is on a path-segment boundary, so `/data/` does not match `/database`. This is not a filesystem jail: symlinks, case, and NFKC are not folded. The risk register says so.

The session stores: pin-match bits, HMAC identity of catalog names, pending rows keyed by numeric id or `id_hmac`, the closed property-name set of a pinned tool, and catalog flags. It does not store descriptions, schemas, arguments, results, raw string ids, or skeletons of names the operator did not write.

`initialize` instructions are structurally scanned (section 8), hashed for the pin comparison, and dropped. A mismatch against `approved_instructions_sha256` is `server_instructions_changed`. The field's existence is not itself an injection finding.

## 6. Observe path (no proxy hop)

A proxy hop means a separate process or network intermediary that traffic must traverse. This track does not add one.

### 6.1 In-process observe and the opt-in gate

No caller opens a socket, spawns a process, or requires traffic to traverse another hop.

1. **`observeBuffer(buffer, meta)`** parses a copy the caller already holds. It does not write, and it does not wrap a stream. This is how outbound stdio is observed without sitting on the write path: the workload, or the wrapper it already uses, hands over the bytes it is about to write. If the caller does not hand over a copy, this library cannot see a `Writable`. A Node `Writable` has no fan-out. There is no passive tap of `child.stdin`.
2. **`tapReadable(readable)`** observes inbound bytes on a Node `stream.Readable` the workload already reads (`child.stdout`). It adds a `data` listener only when `readableFlowing === true` and `listenerCount('data') >= 1`. Otherwise it returns `{ ok: false, reason: "not_flowing" }` and does not attach. Adding a listener to a paused or not-yet-flowing readable would switch it to flowing mode and can drop chunks before the workload's consumer exists. The tap does not call `pause`, `resume`, `read`, or `unshift`. It cannot block.
3. **Web streams.** A `ReadableStream` (`getReader`, no Node `on`) is not a tap target. `tapReadable` returns `{ ok: false, reason: "web_stream" }` and does not attach. The caller uses `inspectExchange` on buffers it already has.
4. **`inspectExchange`** is the pure function a future fetch hook can call with buffers it already has. This track does not modify `packages/vantio-cli/bin/interceptor.cjs` or the public tools of `@vantio/gate-mcp`.
5. **`createInProcessGate`** is an opt-in `Transform` on one stream the workload already owns. It buffers at most one frame, up to the frame cap, then forwards the original bytes or withholds them. Enforce uses it. Observe does not need it. A withhold on this single stream does not synthesize a reply: the gate does not hold the opposite direction. The decision callback reports `withheld: true` immediately. The workload's own request can wait until its own timeout. That availability cost is stated, not hidden.
6. **`createStdioPairGate`** is the opt-in in-process wrapper that holds both directions of a stdio pair the workload already created. It does not spawn the child and it does not listen. When it withholds a client-to-server request, it does not write that frame to the child. It pushes one JSON-RPC error onto the readable the workload already reads, and only at a frame boundary: the error is never spliced into a partially forwarded child frame. A partial child frame is finished (forwarded whole or withheld whole) before the error bytes are written. The error message is the fixed string `vantio_mcp_policy_block`. The error carries no payload bytes.

### 6.2 Phantom Engine, enrolled Linux — Observe contract only

JSON parsing does not belong in an eBPF program. A conforming parser needs unbounded loops, a large stack, and maps of strings. That will not pass the verifier. This track does not ship a program, and it does not claim verifier acceptance.

This repository does not contain the Phantom Engine loader. The host attachment is **Roadmap**.

What this track commits to, and no further:

- The userspace parser and policy in this library are what a future loader would run on bytes it already copied.
- The copy itself is not designed here. Choosing a ring primitive and a copy size without that loader would be a false claim. A future loader has to live with these constraints: a perf-event record's size field is 16 bits; a per-CPU array value is not a place for an arbitrary frame; a BPF ring buffer is not a per-CPU array.
- Socket bytes of a TLS connection are ciphertext. Plaintext needs userspace uprobes on the TLS library the workload actually links (`SSL_read` and `SSL_write` for OpenSSL, and only the libraries the loader attaches). Other stacks, including rustls, are outside that coverage until a probe exists. This track adds no probe. A local stdio pipe is plaintext and does not need a TLS probe.
- A copy that reaches userspace after `write` has returned cannot withhold that write. Host enforce needs a synchronous kernel decision point. This design does not name that hook, the helper, or the kernel config. Host enforce is **Roadmap**, separate from the Observe contract.
- If a future copy is short of a frame, the record is `truncated_capture`. On this Observe contract that is a gap log. It does not block, because this path has no block.

Nothing here claims cluster verification or a live enrolled host. Local in-process observe never needs a network path. The bytes are the workload's own pipe or a copy of a buffer it already had.

Lane K, founder Q11 and Q12, chooses the copy primitive in `04-HOST-COPY.md`. The sentences above are the phase-1 record. The later design uses a ring buffer and a 4096-byte cap. It does not load a program, and it does not withhold a write.

## 7. Policy

Schema `vantio.mcp_policy.v1`.

```json
{
  "schema": "vantio.mcp_policy.v1",
  "mode": "observe",
  "injection": "log",
  "rug_pull": "log",
  "servers": {
    "files": {
      "default": "deny",
      "class_defaults": { "read": "allow", "write": "deny" },
      "tools": {
        "read_file": { "class": "read" },
        "write_file": { "class": "write" }
      },
      "argument_rules": [
        {
          "id": "read-under-data",
          "tool": "read_file",
          "key": "path",
          "op": "prefix",
          "value": "/data/",
          "effect": "allow"
        }
      ],
      "approved": {
        "read_file": {
          "description_sha256": "<64 lowercase hex>",
          "schema_sha256": "<64 lowercase hex>"
        }
      },
      "approved_instructions_sha256": null
    }
  }
}
```

Normalization is fail-safe:

- `mode` other than `enforce` becomes `observe`. A typo does not turn enforcement on.
- `injection` and `rug_pull` other than `block` become `log`.
- Unknown rule operators, a missing `tool`, a missing or invalid `effect`, a key that fails the top-level name rule, and any rule past the 8-key retain cap are dropped and listed as `invalid_rules`.
- If `invalid_rules` is non-empty, the server is `policy_incomplete`. Enforce withholds every call and every list for that server. Reason: a dropped deny must not fail open into an allow. Observe stamps `policy_incomplete` on every decision, never emits `ALLOW`, and still forwards. `policy_incomplete` overrides a later step that would otherwise say `ALLOW`.
- A missing or invalid server `default` becomes `deny`. Absence does not grant allow. In observe, that deny is `WOULD_BLOCK` and still forwards.
- Policy objects are null-prototype maps. `__proto__`, `constructor`, and `prototype` are ordinary keys, never prototype writes.
- Class is operator-assigned. Server hints are not copied into the class.

Match order for a `tools/call`:

1. Frame and parse gates (section 9).
2. Spoof findings. A spoof suppresses every allow. Enforce always withholds a spoofed call. Reason: the name is not the tool the operator named.
3. Rug-pull on that tool, or a structural finding inside the `tools/list` or `initialize` frame itself. `rug_pull: "log"` records and forwards the frame. Reason: the operator asked to record, not to withhold. `rug_pull: "block"` plus `enforce` withholds that list or initialize frame so the changed description does not reach the workload, and withholds later calls to that tool while the mismatch stands. A structural finding in a description follows the `injection` setting on that same frame, not on a later call.
4. Inbound findings on server-to-client results, on `sampling/createMessage`, and on the scanned description and instructions fields.
5. Argument rules, first match wins. An earlier allow shadows a later deny. That order is the operator's, and the proof records it. A rule that cannot be evaluated (`retain_truncated`) does not match and, in enforce, withholds the call.
6. Per-tool `effect`, if set.
7. `class_defaults` for the tool's class.
8. Server `default`.
9. Unlisted server: Observe logs `server_unlisted` and forwards. Enforce withholds.

Read and write on the same server is step 7: `read_file` class `read` allows, `write_file` class `write` denies, one `server_id`, one policy object.

Approval is an operator hash. The first `tools/list` is not approval. AI output is not approval. There is no `approve_on_first_seen`.

Pagination: a `tools/list` result updates the catalog only when its id matches a pending row whose method is `tools/list`. An unmatched result never updates the catalog, even if the body contains `tools`. A result with `nextCursor` starts or extends a draft page and sets `catalog_incomplete`. Pins on that page are still compared. The draft replaces the live catalog only when a page arrives with no `nextCursor`. A call against an incomplete catalog is `catalog_unknown` for names not yet seen, not a spoof. `catalog_unknown` logs and forwards in observe. Enforce withholds it. Reason: the name was not in a catalog the operator's pin was checked against.

Pending rows are capped at 128 per session. The 129th call is `pending_overflow`. It is not stored, and no older row is evicted to make room. Evicting an older row would drop correlation and fail open on that result. Enforce withholds the overflowing call. Observe logs it and forwards.

An unmatched result is still scanned for inbound structure. It does not update the catalog. Observe forwards it (`LOG` if there is a finding, otherwise `ALLOW`). Enforce withholds it as `unmatched_result`. Reason: enforce cannot prove which tool the result answers.

`notifications/tools/list_changed` sets `stale`. A later call is `stale_catalog` until a list page lands. Enforce withholds a call while the catalog is stale. Reason: the description may already have changed and the new list has not been checked. Observe logs and forwards.

The session helper holds at most 64 sessions. Evicting one writes a tombstone for that `server_id` in a 64-slot table that stores the id and `must_relist` only. A new session for a tombstoned id starts `stale: true` with an empty catalog. A session that was stale when evicted cannot come back non-stale: the tombstone stays until a list page is checked. If the tombstone table is full, `tombstone_overflow` is set and every new session starts stale. The flag is not cleared. It lasts until the process exits. That is an availability cost. Enforce withholds calls on a restarted session until that list is checked. Reason: the catalog was lost, and a fresh empty session must not fail open. Observe logs `session_restarted` and forwards.

A pinned tool call before this session has seen `tools/list` follows the name policy and does not compare a pin, because there is no observed description yet. A process restart starts sessions non-stale. Tombstones exist only inside one process. Rug-pull comparison happens when a list arrives, which is the C4 case. A call with no list in this process is not reported as a pin match.

## 8. Inbound structure detector

This is not a moderation product. It looks for structures that carry instructions into the workload. It does not score the meaning of prose.

Scanned fields, then discarded: `result.content[].text`, `result.content[].resource.text`, `result.structuredContent`, the params of a server-to-client `sampling/createMessage`, each tool `description` on `tools/list`, and `initialize` `instructions`. Image and blob fields are not decoded.

Not scanned: `prompts/get` results. Their schema is role and content, so `chat_role_frame` would flag every successful prompts read. `error.message` and `error.data` are not scanned, even though a client may show them to a model. `elicitation/create`, `roots/list`, `notifications/message`, and `completion/complete` are not scanned in this track. Those gaps are in the risk register.

| Finding | Structure |
| --- | --- |
| `embedded_jsonrpc` | A content value parses as a JSON object with `jsonrpc` equal to `2.0` and a string `method` |
| `embedded_tool_catalog` | An object contains a `tools` array of objects that have both `name` and `inputSchema` |
| `chat_role_frame` | An object has `role` in `system`, `developer`, `user`, `assistant`, `tool` and also has `content` |
| `control_token` | A fixed byte sequence is present: `<\|im_start\|>`, `<\|im_end\|>`, `<\|system\|>`, `<\|user\|>`, `<\|assistant\|>`, `<<SYS>>`, `<</SYS>>`, `[INST]`, `[/INST]`, `<system>`, `</system>` |
| `hidden_unicode_channel` | A scanned text contains bidi controls (U+202A–U+202E, U+2066–U+2069), zero-width characters (U+200B–U+200D, U+FEFF), or tag characters (U+E0001, U+E0020–U+E007F) |
| `server_sampling_request` | The message method is `sampling/createMessage` and the direction is server-to-client |

Nested JSON objects inside a content string are parsed up to 8 objects and 64 KiB. Deeper leftovers are `truncated_shape`, not a silent allow.

`injection: "log"` records the finding and forwards, including in enforce mode. `injection: "block"` with `mode: "observe"` records `WOULD_BLOCK` and forwards. `injection: "block"` with `mode: "enforce"` withholds that message.

`createInProcessGate` never synthesizes a replacement, on either direction. It forwards the original frame or it drops that frame. The callback reports `withheld: true`. If the dropped frame was a request, or an inbound response the caller was waiting on, the workload waits on its own timeout. The gate does not answer.

Only `createStdioPairGate` writes a replacement, and only at a frame boundary on the workload-facing readable. The replacement is a JSON-RPC error whose message is the fixed string `vantio_mcp_policy_block` and whose data is the finding id. It contains no bytes from the withheld payload.

## 9. Failure modes

| Condition | Observe | Enforce | Reason |
| --- | --- | --- | --- |
| Listener throws, or the library throws | Catch, emit `GAP`, do not throw into the workload. Tap forwards because it is not on the write path | Gate withholds the frame it could not classify | Observe must not become an availability dependency. Enforce must not allow a tool call it could not see |
| Line that does not start with `{` and is not a content-length header | `ignored_non_json`, forward | `ignored_non_json`, forward | It is not an MCP frame. Stdio logs that leaked onto stdout must not desynchronize the stream |
| `{` line or body that is not JSON | `GAP`, forward | Withhold | A framed object that failed to parse is not classifiable |
| Oversize frame (over the cap) | `GAP`, drop the reassembly buffer, forward on the tap | Withhold | The frame is not classifiable, and memory is bounded |
| Invalid UTF-8 | `GAP` | Withhold | Same |
| Unlisted server, unknown tool, `catalog_unknown` | Log, forward | Withhold | Enforce fail-closed on authority. Observe fail-open so a missing policy line cannot stop a workload that has not stepped up to Enforce |
| `policy_incomplete` (any `invalid_rules`, including a dropped deny) | Stamp the finding, never `ALLOW`, forward | Withhold every call and list for that server | A deny the normalizer dropped must not become an allow |
| `retain_truncated` or more structure than the walker could finish | `LOG`, never `ALLOW`, forward | Withhold | The rule or the shape could not be evaluated |
| `pending_overflow` | `LOG`, forward, do not store, do not evict an older row | Withhold that call, do not store | Evicting an older id would fail open on its result |
| `unmatched_result` | Forward. `LOG` if a scan finding exists, otherwise `ALLOW`. Do not update the catalog | Withhold. Do not update the catalog | Enforce cannot prove which tool the result answers |
| Session evicted and recreated | `LOG` `session_restarted`, forward, session starts `stale` | Withhold until a list page is checked | A lost catalog must not come back as a non-stale empty session |
| Duplicate JSON key anywhere in the walked object | `WOULD_BLOCK`, forward | Withhold | Two parsers can keep different values. The first value is the one this walker saw, and that is not an allow |
| Withheld outbound request on the single-stream gate | Not used for enforce | No synthesized reply. Callback `withheld: true`. The workload's own timeout applies | That gate does not hold the return path |
| Withheld outbound request on the pair gate | Not used for enforce | No write to the child. One fixed JSON-RPC error, written only at a frame boundary on the workload's readable | The pair gate holds both directions in this process |
| Empty line, SSE comment | Ignore | Ignore | Not a message |
| `chunked_unsupported` | `GAP`, forward | Withhold | Not classifiable |
| Spoof | `WOULD_BLOCK`, forward | `BLOCK` | The name is not the approved tool |
| Operator deny (`write`, argument rule, default deny) | `WOULD_BLOCK`, forward | `BLOCK` | The operator denied it. Observe does not yet have permission to enforce |
| Operator allow | `ALLOW`, forward | `ALLOW`, forward | Explicit allow |
| Missing policy object | Treat as `mode: "observe"` | A missing policy cannot select enforce | Absence of policy grants nothing |

Actions are the closed set `ALLOW`, `LOG`, `WOULD_BLOCK`, `BLOCK`, `GAP`.

## 10. Spoof and rug-pull procedure

Closed method set. Any other method string is `method_class: "other"` plus `method_hmac`:

`initialize`, `ping`, `completion/complete`, `logging/setLevel`, `prompts/get`, `prompts/list`, `resources/list`, `resources/templates/list`, `resources/read`, `resources/subscribe`, `resources/unsubscribe`, `tools/call`, `tools/list`, `notifications/initialized`, `notifications/cancelled`, `notifications/progress`, `notifications/message`, `notifications/prompts/list_changed`, `notifications/resources/list_changed`, `notifications/resources/updated`, `notifications/tools/list_changed`, `notifications/roots/list_changed`, `sampling/createMessage`, `roots/list`, `elicitation/create`.

Tool-name checks, in order, on `params.name` of `tools/call` and on each `tools[].name` of a list:

1. Type must be a string. Otherwise `tool_name_type`.
2. Characters in the hidden set (bidi, zero-width, tags, C0 controls, DEL) are `hidden_chars_in_name`.
3. NFKC. If the normalized form differs, `nfkc_mismatch`.
4. More than one Unicode script in the name is `mixed_script_name`. Common and inherited scripts do not count as a second script.
5. A finite confusable map folds Greek and Cyrillic lookalikes to ASCII. If the skeleton equals a different catalog or approved name, `confusable_name`.
6. Any duplicate key in the walked JSON, including `method`, `params`, `id`, `name`, and argument keys, is `duplicate_key` and is spoof-class. The walker uses the first value and still withholds in enforce. `JSON.parse` would keep the last value and hide the first.
7. Two tools in one list with the same skeleton are `duplicate_tool_name`. The comparison uses the ephemeral skeleton against operator names, and HMAC equality between catalog entries. The raw skeleton of a name the operator did not write is not stored.

The confusable map is not UTS #39. Names that are not in the map and are a single non-Latin script are not called spoofs. That remaining gap is in the risk register.

Rug-pull comparison:

- Description pin is sha256 of the decoded description text (UTF-8), not of the JSON encoding. The digest is compared to the operator pin and then discarded.
- Schema pin is sha256 of a canonical JSON object whose present keys are only `inputSchema`, `outputSchema`, `annotations`, `title`, and `_meta`. Objects have sorted keys and no insignificant whitespace. Key order alone is not a change. An added or removed key is a change. Absent fields are omitted, so adding `title` later is a change.
- If the canonical form would exceed 64 KiB, the finding is `hash_unbounded`. The digest is not treated as a match against any pin. Enforce withholds. Observe records the finding and does not emit `ALLOW`. Two schemas that share a 64 KiB prefix are not distinguished on this path. That collision gap is in the risk register.
- A pinned digest that differs is `rug_pull_description` or `rug_pull_schema`. No pin means `unpinned` and no rug-pull finding. The first observation is not a pin.

For a pinned tool, property names of `inputSchema` are stored for argument-key retention only when the schema pin matches, each name matches `^[A-Za-z0-9_.-]{1,64}$`, and the count is at most 64. Those names are schema keys, not values. A mismatch does not replace the stored names with names from the new schema. Unpinned tools contribute no stored property names. The list envelope's own `tools` array is the catalog, not an `embedded_tool_catalog` finding. That finding applies to scanned text and to nested JSON inside scanned text, not to the list frame's catalog.

## 11. Memory and parser bounds

| Bound | Value |
| --- | --- |
| Max frame and reassembly buffer | 256 KiB |
| Max JSON depth | 32 |
| Max keys per object walked | 64 |
| Max array elements walked | 128 |
| Max shape nodes | 256 |
| Max tools in a catalog | 256 |
| Max sessions held by the helper | 64, then a tombstone and a stale replacement |
| Tombstones | 64 server ids and a `must_relist` bit. Overflow marks every new session stale |
| Max pending call ids | 128 per session, no eviction of older rows |
| Max retained argument values | 8 keys, 512 bytes each, evaluation only |
| Raw tool name on a record | Only an exact operator `tools` key, at most 128 characters |
| String id on a record or in a session | HMAC-SHA256 only, never the raw string |
| Nested content JSON objects | 8, and 64 KiB |
| Helper-tracked taps and gates | 64 each. Each buffer is at most 256 KiB, so the helper's frame buffers are at most 16 MiB |
| Host copy size | Not set by this track |

Past a bound, the walker stops, emits `truncated_shape` or `oversize`, and does not treat the message as an allow in enforce mode. Parsing is iterative for frames and depth-capped for JSON. Input is not passed to `eval` or to a regular expression built from the input. Rule operators are literals.

Sessions are replaced as a whole (copy on write). Decision and catalog update for one message finish before the function returns. There is no `await` between the check and the decision, so there is no TOCTOU window inside one call. The library does not read files, spawn processes, open sockets, or use the network.

## 12. eBPF verifier

No eBPF program is added. Verifier limits are why:

- Bounded loops in the verifier cannot walk arbitrary JSON.
- The stack is too small for a parser.
- A map of unbounded strings is the wrong place for a tool catalog.

A future loader may copy bytes and let userspace parse them. That copy is Roadmap, and it is Observe-only until a separate synchronous kernel decision point exists. This track does not choose the hook. The in-process library does not need the kernel.

## 13. Rollback

The library is not on the default load path. Rollback is: stop calling it, or delete `packages/vantio-mcp-awareness`. No migration, no on-disk conversation store, no interceptor change to revert, no enrollment change. In-memory sessions disappear with the process.

## 14. Dependencies

- Node.js built-ins only: `node:crypto`, `node:stream`. No new package installs.
- No dependency on other gap tracks.
- Phantom Engine attachment depends on the private loader and on an enrolled Linux host. Both are outside this repository and are approval gates.
- The public pin `e0b19d55` is untouched.

## 15. Labels

| Result | Label |
| --- | --- |
| In-process parser, policy, spoof, rug-pull, structural inbound detector, `observeBuffer`, conditional `tapReadable`, opt-in gates, after the proof script passes on this workspace | Verified, for that script's assertions only |
| Phantom Engine host copy on an enrolled Linux workload | Roadmap, and Observe-only in this contract |
| Phantom Engine host enforce (a synchronous kernel decision point) | Roadmap. No hook is chosen here |
| Default interceptor wiring, public Gate MCP tool, chunked-HTTP reassembly, HTTP/2, WebSocket, full UTS #39 skeleton, TLS-library uprobes | Roadmap |
| Natural-language injection with no listed structure | Out of scope, remaining risk, not a detector result |

No result in this track is called unbreakable. No result is called audited.

## 16. Approval gates (prepare up to the gate, do not cross)

- Merge this branch.
- Apply the founder-approved label.
- Load the library from the default interceptor.
- Add a public tool to `@vantio/gate-mcp` or `@vantio/optics-mcp`.
- Edit the root README, the website, or a Shipped claim.
- Publish to npm, GHCR, or a registry. Cut a tag. Use a production signing root.
- Attach a Phantom Engine program on a host. Restart phantom-box. Enroll a production machine.
- Run an AWS or GCP lab. Touch a GCP project. Spend money.
- Issue a real credential. Print a secret.
- Send this packet outside the company.

## 17. Tests the implementation must include

- Stdio split across chunks, CRLF, content-length framing, HTTP JSON, SSE multi-`data` events.
- Allow `read_file` and deny `write_file` on one server, in observe (`WOULD_BLOCK` forwards) and enforce (`BLOCK` withholds).
- Argument prefix allow and a narrower deny, first match wins.
- Homoglyph and hidden-character spoof, duplicate keys on `name`, `method`, and an argument, mixed script.
- A `/data/` prefix allows `/data/notes.txt` and does not allow `/data/../etc/passwd`, `/data/./../x`, `//data//../etc`, `..%2f`, or `/database`. A trailing slash does not change the segment. A path that escapes root or still contains an encoded dot or slash after one decode is `path_rejected`.
- Rug-pull on a changed description after a pinned hash, including a list that has no `list_changed` notification. With `rug_pull: "block"` and enforce, the list frame itself is withheld. Stale catalog after `list_changed`.
- A structural finding inside a tool description is decided on the list frame.
- Each inbound structure finding, a plain-language sentence that must not match, and a `prompts/get` result that must not match `chat_role_frame`.
- Canary string planted in an argument, a tool result, a string JSON-RPC id, and a tool name the operator did not write. Absent from the record, the session, and the replacement error. The evidence file does not contain the canary or a digest of it.
- An invalid deny rule makes the server `policy_incomplete` and enforce withholds.
- `tapReadable` refuses a paused readable and a web `ReadableStream`. When the precondition holds, a pre-existing listener still receives the original bytes. The process did not open a listen socket.
- `observeBuffer` does not write.
- Pair-gate enforce withhold writes the fixed error at a frame boundary and no payload bytes, including when a child frame is only partly received. Single-stream withhold writes nothing in either direction and reports `withheld: true`.
- An unmatched result does not change the catalog. Pending overflow does not drop an older row.
- Fuzz: deterministic seed, mutations of a corpus, no throw, buffer never over the cap, canary never in the output, decision action in the closed set.

## 18. Proof and evidence

`packages/vantio-mcp-awareness/scripts/proof.mjs` runs the cases in section 17 against the library, writes `docs/programs/gap-t4-mcp-awareness/evidence/t4-proof.json`, and exits non-zero on a failed assertion. The evidence file records UTC time, Node version, seed, assertion ids, and the label for each result. It contains no payload from the fixtures.

## 19. Package layout (for the later commit, not this one)

```
packages/vantio-mcp-awareness/
  package.json          zero dependencies
  src/bounds.js
  src/parse.js          frames and bounded JSON walk
  src/policy.js         normalize and decide
  src/catalog.js        session, spoof, rug-pull
  src/injection.js      structural inbound checks
  src/observe.js        tap and in-process gate
  src/index.js
  test/*.test.js
  scripts/proof.mjs
docs/programs/gap-t4-mcp-awareness/
  00-DESIGN.md
  01-COUNCIL-VERDICT.md
  02-RISK-REGISTER.md
  evidence/t4-proof.json
```

The package stays out of `pnpm-workspace.yaml` so the frozen lockfile does not change. Tests run with `node --test` and need no install.
