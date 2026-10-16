# T4 risk register

Track: MCP and tool-call awareness.  
Timestamp (UTC): 2026-10-16T16:03:15Z. The earlier stamp `2026-10-16T16:05:00Z` was ahead of the clock and is withdrawn.  
This register is part of the design packet. It is updated again when the proof evidence exists. It does not close a risk by renaming it.

| Id | Risk | Label | Why it remains |
| --- | --- | --- | --- |
| R1 | Plain-language instructions in a tool result, with none of the structures in design section 8, reach the workload | Out of scope | Detecting that would be content scoring. This track does not do that |
| R2 | Confusable tool names outside the finite Greek/Cyrillic map, including single-script non-Latin lookalikes | Roadmap for a full UTS #39 skeleton. Residual for this track | The map is not the Unicode confusables database |
| R3 | Unpinned tools can change description between lists without a rug-pull finding. Fields outside the schema pin object can still change if a future MCP field is added and not listed | Accepted residual | A pin is operator configuration. The first observation is not approval. The pin object is `inputSchema`, `outputSchema`, `annotations`, `title`, `_meta` |
| R4 | `hash_unbounded`: two schemas that share a 64 KiB canonical prefix are not distinguished. Enforce withholds instead of matching. Observe does not emit `ALLOW` | Accepted residual | The walker will not hash an unbounded document |
| R5 | Enforce withholds a legitimate frame larger than 256 KiB, and also a smaller frame that exceeds a walk cap: 128 array elements, 64 keys in one object, 256 shape nodes, or depth 32. A modest `structuredContent` array can hit those caps and be `truncated_shape` | Accepted availability cost | Past the cap the frame is not fully classifiable, so enforce does not allow it |
| R6 | `hidden_unicode_channel` flags U+200D, which emoji ZWJ sequences use. `control_token` flags the literal `<system>`. `chat_role_frame` flags legitimate `structuredContent` that is a chat turn. `injection: "block"` in enforce withholds those frames | Accepted false-positive cost | The detector is structural. The operator chooses `log` or `block` |
| R7 | `prompts/get` results, JSON-RPC `error.message` and `error.data`, `elicitation/create`, `roots/list`, `notifications/message`, `completion/complete`, and resource blob bytes are not scanned | Accepted residual | `prompts/get` is role and content by schema. Error text often reaches a model and is still unscanned. The other methods are outside this track's scanned set. Blobs are not decoded |
| R8 | Raw chunked HTTP, HTTP/2, and WebSocket are not framed | Roadmap | `fetch` bodies are already decoded and use `inspectExchange`. A raw chunked capture returns `chunked_unsupported` |
| R9 | Argument rules are literal code-unit compares. `/data/../etc/passwd` matches prefix `/data/`. Case, NFKC, and percent-encoding are not folded | Accepted residual | A prefix is not a filesystem jail. This track does not claim path canonicalization |
| R10 | Argument-rule order is first match wins. An allow before a narrower deny shadows the deny | Accepted configuration hazard | The proof records this order. The library does not reorder rules |
| R11 | In-process outbound stdio is invisible unless the caller passes a copy to `observeBuffer` or opts into a gate | Accepted residual | A `Writable` has no fan-out. A passive tap would be a false claim |
| R12 | Single-stream enforce withhold does not answer the workload. The workload waits for its own timeout | Accepted availability cost | That gate does not hold the return path. The pair gate does answer, and it is opt-in |
| R13 | Host copy cannot withhold a write that has already returned. TLS socket bytes are ciphertext. Host enforce has no hook in this design | Roadmap | Phantom Engine attachment is not in this repository. No verifier result is claimed |
| R14 | The in-process library runs wherever Node runs. That does not extend Phantom Engine beyond enrolled Linux | Label boundary | Docs and records must call host enforcement Roadmap, and must not call this library Phantom Engine |
| R15 | No default-path wiring. A workload that does not call the library is unchanged | Roadmap for wiring, which is an approval gate | Loading it from `vantio run` would change customer-visible Observe behavior |
| R16 | "Verified" covers the proof script's assertions on this workspace only | Verified for those assertions after the script passes. Not a host proof | There is no enrolled-host run in this track |
| R17 | `tombstone_overflow` is never cleared. Every new session stays stale for the rest of the process | Accepted availability cost | Clearing it would forget that an evicted catalog was lost |
| R18 | HMAC values cannot be correlated across processes or restarts | Accepted operational limit | The key exists only in that process, which is what keeps the digests from being confirmed offline |
| R19 | A pinned tool called before this process has seen `tools/list` follows the name policy with no pin comparison | Accepted residual | Rug-pull comparison runs when a list arrives. A restart does not invent a stale flag. The call is not reported as a pin match |
| R20 | Existing sentences that say enforcement is Phantom Engine, in `interceptor.cjs` and the `@vantio/gate-mcp` README, stay as they are | Label boundary | This track must not describe the in-process library as Phantom Engine on those surfaces |
