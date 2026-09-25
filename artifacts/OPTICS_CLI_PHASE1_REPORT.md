# Optics CLI Phase 1 Report
Generated: 2026-09-23  
Branch: `cli-public-release-remediation-2026-09-23`  
HEAD: `5a62eed` (main at branch-off)  
Package: `@vantio/cli 0.3.20`  
Node: v22.x

---

## 1. Baseline Summary

| Item | Value |
|------|-------|
| Branch | cli-public-release-remediation-2026-09-23 |
| Head at branch-off | 5a62eed |
| Package version | 0.3.20 |
| npm latest | 0.3.20 (published 2026-09-13) |
| vantio --version | 0.3.20 |
| Test baseline (before undici install) | 81 pass / 15 fail (14 PAID_MODE undici + 1 inspect tail timing) |
| Test baseline (after npm install) | 96 pass / 1 fail (inspect tail timing) |
| Pre-existing failures | inspect tail (mtime ordering race), rest pass |

Captured in: `artifacts/optics-cli-phase1-baseline/`

---

## 2. Auth / Login Endpoint Analysis

**Endpoint under test:** `${VANTIO_INGEST_URL}/api/v1/config` (GET with `x-vantio-identity` header)  
**Default base:** `https://vantio.ai`

**Trace (working-tree):**
- `vantio login <key>` calls `validateKey(base, key)` -> `GET /api/v1/config` with `x-vantio-identity: <key>`
- Network failure -> explicit error "could not reach Vantio at <url> ... Key not saved." (exit 1) OK
- HTTP 401 -> "API key was rejected (401). Key not saved. Get your key at vantio.ai/dashboard" (exit 1) OK
- HTTP 200 (ok) -> reads `{ policy, tier }`, saves config at `~/.vantio/config.json` (chmod 600) OK
- Non-ok, non-401 -> "unexpected response (HTTP N)" (exit 1) OK
- No API key -> prompts on TTY, error on non-TTY OK
- Failed login DOES NOT create partial/empty config OK

**Malformed key test** (against 127.0.0.1:1):
- Result: "could not reach Vantio at http://127.0.0.1:1 (fetch failed). Key not saved."
- No unexplained 404 OK

**Classification:** `AUTH_SERVER_BLOCKED`
- Cannot verify production endpoint `/api/v1/config` exists at `https://vantio.ai`
- Local Optics works without login; login only required for dashboard sync / paid features
- Error handling is clean; login failure does not corrupt config
- Independent local remediation proceeding

---

## 3. User-Visible String Inventory

### Issues Found

**vantio.js:**
- Line 13: `Vantio AI -- process supervisor` - RETIRED_PRODUCT (D2)
- Line 21: `Show Shadow AI attack surface` - RETIRED_PRODUCT (D2)
- Lines 51-62: DISCOVER_HELP Shadow AI Attack Surface Discovery - RETIRED_PRODUCT
- Line 899: `Vantio Observe -- local run history` - RETIRED_PRODUCT
- Line 940: `$799/node/mo` hardcoded - PRICING_REFERENCE
- Line 940: `Rogue Reconciliation` - INTERNAL_TERM
- Lines 977, 1008, 1012: Shadow AI in renderDiscoveryTable - RETIRED_PRODUCT

**package.json:**
- description: `Sight Loop: wrap -> capture -> inspect` - RETIRED_PRODUCT
- keywords: `sight-loop` - RETIRED_PRODUCT

**telemetry.cjs:**
- Default opt-OUT - D1 violation (must be opt-IN)
- `anonymous` claim throughout - D1 violation

**interceptor.cjs:**
- Line 833: `See docs/sight-loop.md` in terminal output - DEAD_POINTER
- Lines 280-286: `Local Gate` in terminal output - INTERNAL_TERM
- Lines 3760-3773: `Local Gate` + telemetry nag in summary - INTERNAL_TERM + D1

**README.md:**
- Step 4 numbering (missing Step 3) - defect
- `anonymous, opt-out` telemetry section - D1 violation

---

## 4. Vocabulary Audit Summary

| Term | Location | Classification |
|------|----------|----------------|
| Shadow AI / attack surface | vantio.js public output | RETIRED_PRODUCT |
| Vantio AI process supervisor | vantio.js USAGE | RETIRED_PRODUCT |
| Vantio Observe | vantio.js output | RETIRED_PRODUCT |
| Sight Loop | package.json, interceptor terminal | RETIRED_PRODUCT |
| sight-loop | package.json keywords | RETIRED_PRODUCT |
| Rogue Reconciliation | vantio.js footer | INTERNAL_TERM |
| Local Gate | interceptor.cjs terminal output | INTERNAL_TERM |
| soak-pro | interceptor.cjs terminal output | INTERNAL_TERM |
| $799/node/mo | vantio.js footer | PRICING_REFERENCE |
| anonymous (telemetry claim) | telemetry.cjs, README | PRIVACY_CLAIM |

---

## 5. Product / Pricing Consistency

Approved 3-product model: Optics | Phantom Engine | Vantio Enterprise  
Issues: hardcoded $799, Vantio AI identity, Sight Loop in description

---

## 6. Discover Scope

`vantio discover --local` reads ONLY `~/.vantio/runs/*.json` from `vantio run`-wrapped processes.  
Does NOT detect unenrolled processes -- that is Phantom Engine (kernel plane).  
Claims in DISCOVER_HELP about unenrolled processes exceeded implemented scope: UNSUPPORTED_CLAIM.

---

## 7. Evidence Semantics

**CRITICAL: Zero-call runs write NO run log** (interceptor.cjs line 3641: `if (_calls.length === 0) return;`)  
Severity: HIGH -- zero-call runs are invisible to prove/search/tail/discover.

---

## 8. Child-Process Correctness

- `spawn(program, args, { stdio: 'inherit', env, shell: false })` -- no shell injection OK  
- Exit code preserved: `code ?? 1` OK  
- Signal forwarding: `process.kill(process.pid, signal)` OK  
- Error handler: explicit message, exit(1) OK

---

## 9. Key Storage

- `~/.vantio/` dir: 0700 OK  
- `config.json`: 0600, enforced via chmodSync OK  
- Key masking: maskKey() used in all output OK  
- Logout removes config OK  
- Key leakage: INCONCLUSIVE (no production key; code review correct)

---

## 10. Telemetry Audit

- Default: OPT-OUT (D1 VIOLATION -- must be opt-in)
- Trigger: first intercepted LLM call via sendRunTelemetryOnce()
- Destination: `https://vantio.ai/api/v1/telemetry`
- Fields: anonymousId, runtime, runtimeVersion, os, event, hosts, callCount, cliVersion
- Identifier: ~/.vantio/telemetry-id (0600)
- Per-run nag in FREE_MODE summary (D1 violation)
- TELEMETRY_MIGRATION_BLOCKED: wire field `anonymousId` is server-dependent

---

## 11. Absent Commands

- doctor: NOT in dispatch/USAGE/README -- no action needed
- coverage: NOT in dispatch/USAGE/README -- no action needed  
- leave: NOT in dispatch -- LEAVE_ENGINEERING_GAP.md required (D3)
- --audit: IS in dispatch; VANTIO_AUDIT_MODE used by interceptor.cjs ingest payload; KEEP flag

---

## 12. Pre-existing Test Failures

| Test | Root Cause | Status |
|------|------------|--------|
| inspect tail mtime ordering | findMostRecentRun uses file mtime; same-ms writes | Fixed in Phase 2 |
| 14 PAID_MODE tests | undici not installed | Fixed by `npm install` |

---

## 13. Proposed Fixes (Phase 2)

HIGH:
1. Zero-call run logs: remove early-return in interceptor.cjs exit handler
2. Telemetry opt-in: VANTIO_TELEMETRY=1 required; default off
3. Approved identity in USAGE

MEDIUM:
4-15. Shadow AI, Vantio Observe, hardcoded $799, Rogue Reconciliation, Sight Loop, docs/sight-loop.md, Local Gate, telemetry nag

---

**Auto-proceeding to Phase 2.**
