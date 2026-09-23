# OPTICS CLI — Phase 1 Closure Inventory
**Generated:** 2026-09-23  
**Branch:** `cli-public-release-remediation-2026-09-23`  
**HEAD:** `92cfcc0f14ada1c5396e1796a90fd43c22fc0a56`  
**Package:** `@vantio/cli` 0.3.21  
**Node:** v22.x  

---

## 1. Repo State Verification

| Item | Value | Match Expected? |
|------|-------|----------------|
| Branch | `cli-public-release-remediation-2026-09-23` | ✓ |
| HEAD SHA | `92cfcc0f14ada1c5396e1796a90fd43c22fc0a56` | ✓ (matches brief) |
| Remote tip | `92cfcc0f14ada1c5396e1796a90fd43c22fc0a56` | ✓ (local == remote) |
| Working tree | Clean | ✓ |
| Untracked files affecting build/package | None | ✓ |
| Package version | 0.3.21 | ✓ |
| Merge-base with main | `5a62eedaa77d71665491cd1c49e8a67dfdf7df3f` | — |
| CI checks (PR #45) | All 4 PASS | ✓ |
| npm-publish triggered | NO (branch not `main`) | ✓ |
| Release/tag created | NO | ✓ |

**Full commit list on branch (from merge-base with main):**

```
92cfcc0 cursoragent@cursor.com  copy/identity: interceptor.cjs public-release remediation
6bd03e8 zach@vantio.ai          artifacts: Phase 1 report and Phase 3 final report
42704b1 zach@vantio.ai          copy/identity+evidence: vantio.js
f3b05b3 zach@vantio.ai          tests: update assertions for new identity and opt-in telemetry; add zero-call run log test
78b34b8 zach@vantio.ai          docs+tests: README telemetry docs, test assertions
a72bbb5 zach@vantio.ai          telemetry+tests: opt-in telemetry, updated test assertions
8884f91 zach@vantio.ai          docs+telemetry+tests: package.json, telemetry opt-in, npmignore, LEAVE_ENGINEERING_GAP
```

---

## 2. Candidate Tarball Provenance

**Reported SHA-256:** `5cd8d94e703fe6cc87b35fbefe7c09c1ccdce77b88c16c5c97adf9521aa59242`

**Evidence:**
- The stale Phase 3 report (commit 6bd03e8) recorded this SHA-256 and stated:
  > "NOTE: interceptor.cjs local commits (9 total including ef4908a, 47cfa34, abc011e, ab3ecc9) were NOT pushed to remote due to shell unavailability ... Local HEAD: ab3ecc954d03287719fe82f3ed06e2d66b72bd55"
- The local HEAD at Phase 3 report time was `ab3ecc954d03...`, which is NOT the
  final integrated HEAD `92cfcc0f14...`.
- Commit `92cfcc0` (the final interceptor commit) was pushed AFTER the Phase 3
  report was written. The tarball was therefore built from a local state that
  predates this commit.
- The final pushed commit `92cfcc0` may or may not be byte-for-byte identical
  to the local `ab3ecc9` state — they cover the same 5 described changes but are
  different commits. Without the original unpushed local commits, byte-for-byte
  identity cannot be verified.
- No tarball file exists in the working tree (all `.tgz` files absent from repo).

**Classification:** `BUILT_BEFORE_FINAL_HEAD`

The reported tarball was built from a local commit that predates the final integrated
HEAD. The SHA-256 `5cd8d94e...` cannot be certified as the release candidate. A new
tarball MUST be built from `92cfcc0` (and any Phase 2 changes) and its SHA-256
supersedes the reported value.

---

## 3. Stale Phase 3 Report Assertions Affected by interceptor.cjs (92cfcc0)

The prior Phase 3 report was written at local HEAD `ab3ecc954d03...` BEFORE the
final interceptor commit `92cfcc0`. The following assertions must be retested:

| Prior Assertion | Status After 92cfcc0 | Action Required |
|-----------------|---------------------|-----------------|
| "Local Gate in terminal — CLEAR (remote interceptor.cjs still has old version)" | NOW actually clear | Reconfirm from 92cfcc0 |
| "soak-pro credential hint removed" | Implicit in 92cfcc0 (confirmed in diff: removes soak-pro from FREE_MODE summary) | Reconfirm |
| "docs/sight-loop.md pointer removed" | Clear per 92cfcc0 diff | Reconfirm |
| "workflow: sight_loop field removed from run log" | Clear per 92cfcc0 diff (field dropped) | Reconfirm |
| "upgrade_gate renamed to upgrade_optics in run log" | Clear per 92cfcc0 diff | Reconfirm |
| "telemetry nag removed from FREE_MODE summary" | Clear per 92cfcc0 diff | Reconfirm |
| "zero-call run writes run log — PASS" | Confirmed in 92cfcc0 diff (early return moved after log write) | Reconfirm |
| "mediation: metadata.mediation \|\| 'sight_loop' — NOT addressed" | UNRESOLVED (still at line 495) | REQUIRES FIX (Phase 2) |
| Tarball SHA256 `5cd8d94e...` | INVALIDATED (BUILT_BEFORE_FINAL_HEAD) | NEW PACK REQUIRED |
| "Behavioral matrix all PASS" | Conditional on rerun from 92cfcc0 | Full rerun required |
| Phase 3 report provenance ("generated from final HEAD") | FALSE (was generated from local pre-push state) | Regenerate |

**Conclusion:** The prior Phase 3 report is NOT authoritative. It is superseded by
this closure run. All assertions will be rerun in Phase 3.

---

## 4. mediation || "sight_loop" Trace

**Location:** `packages/vantio-cli/bin/interceptor.cjs`, line 495  
```js
mediation: metadata.mediation || "sight_loop",
```

This is in the `report()` function (lines 478–514), which is the cloud sync ingest path.

**Guard:** `if (FREE_MODE || !INGEST_URL || !cloudSyncActive) return;`  
(line 479 — fires only when cloud sync is active, i.e., paid mode with valid API key)

**Escape vector analysis:**

| Surface | Can "sight_loop" appear? | Notes |
|---------|-------------------------|-------|
| Local run log (`~/.vantio/runs/*.json`) | NO | Run log schema does not include a `mediation` field per call |
| Proof HTML/MD (`vantio prove`) | NO | Proof reads from run log; `mediation` not in run log calls |
| stdout / stderr | NO | Not printed to terminal |
| `vantio search` / `tail` / `diff` output | NO | Read from run log only |
| Usage telemetry (`/api/v1/telemetry`) | NO | Telemetry fields are explicit; no `mediation` in telemetry.cjs |
| Auth requests (`/api/v1/config`) | NO | Only identity header, no `mediation` field |
| Remote ingest (`/api/v1/ingest`) | **YES** | `eventPayload.mediation` sent for enforcement events (BLOCKED_HOST, BLOCKED_SIZE, BLOCKED_SPEND, ENFORCEMENT_GAP, DRY_RUN_*) that do not set their own mediation value |
| Package docs / npm README | NO | No `sight_loop` string in any public document |
| External schemas / consumers | UNKNOWN | Server-side consumers of the ingest API may read the `mediation` field |
| Source code (comment line 480) | YES (source only) | Comment says "Additive Optics Sight Loop fields"; this is in source, not user-visible output |

**Classification:** `EXTERNAL_PROTOCOL_VALUE`

The string `"sight_loop"` is emitted as a value in an external network protocol
payload (HTTPS POST to the server's ingest endpoint). While this only occurs for
paid-mode users with cloud sync active, the value IS sent externally as part of the
event payload schema. Legacy server consumers of this field may have seen
`"sight_loop"` values from previous versions.

**Action Required (Phase 2):** Replace default with neutral accurate value
(`"optics_enforcement"` for enforcement events). Update code comment. Add
regression tests proving the retired name is not emitted.  
**Historical compatibility:** Server must accept both old `"sight_loop"` values
(already sent in prior versions) and new `"optics_enforcement"` values. This
change only affects the client-side default — no server-side change is in scope.

---

## 5. --audit / VANTIO_AUDIT_MODE Classification

**Source evidence:**
- `interceptor.cjs` line 52: `const AUDIT_MODE = process.env.VANTIO_AUDIT_MODE === "1";`
- `interceptor.cjs` line 507: `auditMode: AUDIT_MODE,` (field in ingest POST body)
- `vantio.js` line 30: `--audit, -a   Set VANTIO_AUDIT_MODE=1 in the child environment`
- `vantio.js` line 369: `...(values.audit ? { VANTIO_AUDIT_MODE: "1" } : {})`
- No other code reads or acts on `AUDIT_MODE` or `VANTIO_AUDIT_MODE` in any file

**Effect trace:**
- In FREE_MODE (no API key): `report()` never fires; `AUDIT_MODE` is set in the
  child environment but nothing reads it locally. Zero observable local effect.
- In paid mode: `auditMode: true` is added to the ingest POST body. The server
  may use this field for event categorization. No local behavior changes.
- There is no local audit log, no local audit output, no different enforcement
  behavior, no different proof output, no different run log schema.

**Classification:** `METADATA_ONLY`

`VANTIO_AUDIT_MODE` only sets the `auditMode` field in the cloud ingest payload.
It has zero observable local effect in free mode and zero local behavioral
difference in paid mode. It is a server-side tag only.

**Current public exposure:**
- Listed in USAGE flags: `--audit, -a   Set VANTIO_AUDIT_MODE=1 in the child environment (marks events on the enforce plane).`
- README Flags section documents it with accurate caveat: "Has no observable local effect in Optics-only (free) mode; the flag is passed through to the interceptor for paid enforce-plane correlation."
- Example in USAGE: `vantio prove --format=md --out=audit.md` — this is NOT the `--audit` flag, it is a `prove` format argument (different command; keep as-is)

**Action Required (Phase 2):** Remove `--audit, -a` from public USAGE flags.
Remove `--audit` from README Flags section. Preserve internal `VANTIO_AUDIT_MODE`
env var compatibility. Add regression test asserting `--audit` is absent from
public help output.

---

## 6. Auth Endpoint Classification

**Source evidence:**
- `vantio.js` line 249: `const res = await fetch(\`${base}/api/v1/config\`, ...)`
- Error handling: explicit messages for network failure, 401, unexpected status
- Key storage: `~/.vantio/config.json` chmod 600
- Key masking: maskKey() used in all output
- Login error handling verified clean (no partial writes, no 404 confusion)
- No mock test of the production endpoint behavior beyond 401/200/network-fail
- No authorized production testing was performed (no real credential available)

**Classification:** `AUTH_DEPLOYMENT_UNVERIFIED`

The endpoint `/api/v1/config` is correctly implemented in source. The README Step 3
already has honest language: trial required, no public self-serve key dashboard,
`vantio.ai/dashboard` redirects to docs. However:
- Login/whoami/logout appear prominently in the primary USAGE text
- `vantio login vk_live_xxx` appears in USAGE examples
- This constitutes advertising that login works without verified production evidence

**Action Required (Phase 2):**
- Remove login/whoami/logout from primary USAGE listing in vantio.js
- Remove `vantio login vk_live_xxx` from USAGE examples
- Write FOUNDER_COPY_CHANGE_REQUEST.md for proposed replacement wording
- Keep login/whoami/logout as functional commands (they work correctly when called directly)
- Keep README Step 3 as-is (already has appropriate optional/trial language)
- Update test that asserts `vantio login` appears in `--help` output

---

## 7. Test Suite Baseline (Final HEAD: 92cfcc0)

```
Test runner: node --test
Results: 99 pass / 0 fail / 0 skip
Duration: ~17s
```

Tests cover: identity strings, telemetry opt-in behavior, zero-call run log,
login/whoami/logout against mock, prove/search/tail/diff against mock logs, 
interceptor PAID_MODE enforcement, undici/node_http/node_net/curl/wget/ws,
SIGTERM forwarding, exit code preservation.

---

## 8. Auto-Proceeding to Phase 2

The following residuals require code changes:
1. `mediation: metadata.mediation || "sight_loop"` → replace default (EXTERNAL_PROTOCOL_VALUE)
2. `--audit, -a` in public USAGE → remove (METADATA_ONLY)
3. Login/whoami/logout in primary USAGE → remove from primary (AUTH_DEPLOYMENT_UNVERIFIED)
4. Code comment "Additive Optics Sight Loop fields" → update (INTERNAL, but accurate hygiene)
