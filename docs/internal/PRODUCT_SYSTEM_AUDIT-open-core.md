# Product System Audit — `vantio-open-core`

**Audit date:** 2026-09-20  
**Auditor:** Cursor Cloud Agent (read-only; no code changes to product/marketing/legal surfaces)  
**Branch:** `cursor/product-system-audit-open-core-60bf`  
**Canonical product model applied:**
- Optics — free observability; observational only; no bypass-resistant enforcement
- Phantom Engine — primary paid product; Observe + Enforce + Control; $799/enrolled node/mo; 14-day trial
- Vantio Enterprise — optional governance/evidence add-on to Phantom Engine
- Gate — NOT a current standalone public SKU; may exist only as internal enforcement, package/compat IDs, legacy migration, clearly labeled historical docs, or redirect/checkout compatibility

---

## 1. Repo Role in Product System

**This repo is the Vantio Optics open-core:** the free, MIT-licensed observe plane for AI agent egress. It ships:

| Package | npm / PyPI name | Role |
|---|---|---|
| `packages/vantio-cli` | `@vantio/cli` (0.3.20) | CLI runner — `vantio run`, `vantio prove`, `vantio search`, `vantio tail`, `vantio diff`, `vantio discover`, `vantio login/logout/whoami` |
| `packages/vantio-agent-sdk` | `@vantio/agent-sdk` | Node.js SDK — `shield()`, `AsyncLocalStorage` trace propagation |
| `packages/vantio-agent-sdk-py` | `vantio-agent-sdk` (3.0.13) | Python SDK — `@shield` decorator, `urllib`/`requests`/`httpx`/`aiohttp`/`http.client`/`urllib3`/`socket`/curl+wget subprocess wrap |
| `packages/vantio-optics-mcp` | `@vantio/optics-mcp` (0.1.2) | Read-only MCP server — list/inspect local runs, `vantio prove`, discover, upgrade path |
| `packages/vantio-gate-mcp` | `@vantio/gate-mcp` (0.1.0) | Gate dry-run MCP — evaluate hostname/size/spend, fetch live Gate policy (requires API key), explain fences |

Supporting infrastructure in-repo: Docker observe wrapper (`deploy/docker/`), Kubernetes observe job example (`deploy/k8s/`), agent host hooks (`integrations/hooks/`), VS Code extension (`extensions/vantio-optics/`), GitHub Actions for CI/publish/SLSA provenance.

The control plane (`vantio-pro`) and the kernel-enforcement layer (`vantio-phantom-engine`) live in separate repos not audited here.

---

## 2. Inventory

### Packages (present and built)

| Item | Status |
|---|---|
| `@vantio/cli` — `bin/vantio.js`, `bin/interceptor.cjs`, `bin/telemetry.cjs`, `bin/llm-hosts.cjs`, `bin/python-wrap/sitecustomize.py` | PASS — present, syntactically valid, CI-gated |
| `@vantio/agent-sdk` — TypeScript, ESM + CJS + types dist | PASS — build verified in CI |
| `vantio-agent-sdk` (Python) — `vantio/sdk.py`, `_http_observe.py`, `_process_wrap.py`, `_telemetry.py` | PASS — PyPI 3.0.13 (distribution-audit-2026-07-01 confirmed 3.0.0 healthy) |
| `@vantio/optics-mcp` — read-only MCP over local run logs | PASS — present, tested |
| `@vantio/gate-mcp` — dry-run eval + live policy fetch MCP | PARTIAL (see §3-C below) |

### Install paths

| Path | Status |
|---|---|
| `npm install -g @vantio/cli` | PARTIAL — distribution-audit-2026-07-01 documented a 4-version slip where registry was stuck at 0.1.0. npm-publish.yml has since been fixed with distinguishing error handling. The OPTICS_CLI_INSPECT spec (2026-08-15) notes the registry was still at 0.3.16 while source had search/tail/diff. NPM_TOKEN validity is not auditable from this environment. |
| `pip install vantio-agent-sdk` | PASS — distribution-audit-2026-07-01 confirmed PyPI healthy at 3.0.0. pyproject.toml now at 3.0.13. |
| `npx -y @vantio/optics-mcp` | PARTIAL — package exists and is publishable; actual registry version unverifiable from this env |
| `npx -y @vantio/gate-mcp` | PARTIAL — same caveat as optics-mcp |

### Verifiers

| Verifier | Status |
|---|---|
| `vantio prove` — HTML/Markdown report from local run logs | TESTED_LOCAL — generates from `~/.vantio/runs/*.json` written by the interceptor |
| `scripts/sight-loop-prove.sh` — offline wrap → capture → prove cycle | TESTED_LOCAL — script spins up a mock LLM host on localhost, verifies full Sight Loop without real LLM endpoints |
| CI `pnpm test` for all JS packages | PASS — `ci.yml` runs lint + typecheck + tests on push/PR |
| Python SDK `python -m unittest discover` | PASS — `ci.yml` runs against Python 3.10/3.11/3.12 |

### Evidence exporters

- `vantio prove` — self-contained HTML or Markdown from local run logs
- `vantio search`, `vantio tail`, `vantio diff` — inspect local run logs
- `vantio discover --local` — aggregate local wrap history

### Gate identifiers in this repo

The package name `@vantio/gate-mcp` and `vantio-gate` MCP name, homepage `https://vantio.ai/gate`, and the `UPGRADE_PATH` structure in `packages/vantio-gate-mcp/src/policy.js` all reference "Gate" as a product tier. Multiple doc files use `Gate ($499)` pricing language. See §3-A and §3-C for conflict analysis.

---

## 3. Public Claim vs Code/Docs Conflicts

### 3-A. CONFLICT — Gate presented as a current standalone public SKU at $499 in multiple docs

**Canonical model:** Gate is NOT a current standalone public SKU.

**Files with $499 Gate language:**

| File | Quote |
|---|---|
| `docs/PRODUCT_LINEUP.md:5` | `**Vantio Optics** (Free) · **Vantio Gate** ($499) · **Vantio Phantom Engine** ($799/node) · **Vantio Enterprise** (talk to sales)` |
| `docs/PRODUCT_LINEUP.md:18` | `\| **Gate** ($499) \| **Enforce** · rules that stick where the agent is wired …` |
| `docs/PRODUCT_LINEUP.md:41` | `### Enforce · Vantio Gate ($499)` |
| `docs/observe-only.md:30` | `## What Optics does not do → Vantio Gate ($499)` |
| `docs/observe-only.md:50` | `## What Optics does not cover → Vantio Phantom Engine ($799/node)` |
| `packages/vantio-agent-sdk-py/README.md:5` | `Gate ($499/month). Phantom Engine … $799/node` |
| `packages/vantio-agent-sdk-py/README.md:7` | `> **Optics** (Free) · **Gate** ($499/month) · **Phantom Engine** ($799/node) · **Enterprise** (talk to sales)` |
| `packages/vantio-agent-sdk-py/CHANGELOG.md:5` | `Optics Observe Free, Gate Enforce $499/month, Phantom Engine Control $799/node/month…` |
| `docs/getting-started-tier01.md:70` | `To attach **Vantio Gate** (Pro) or an Enterprise on-prem control plane:` |
| `README.md:88` | `Residual risk closes with **Vantio Gate**, then **Vantio Phantom Engine** — see vantio.ai/pricing.` |

**Files that correctly say Gate is NOT a separate current SKU:**

| File | Quote |
|---|---|
| `packages/vantio-cli/README.md:45` | `To attach **Phantom Engine** enforcement or an Enterprise on-prem control plane (Gate is not a separate current SKU):` |
| `packages/vantio-cli/README.md:210` | `…the interceptor fetches policy from the enforce-plane control plane ([`vantio-pro`]; Gate is not a separate current SKU)` |
| `packages/vantio-cli/README.md:81` | `The CLI may still print a technical `pro` tier from the enforce-plane API; that is not a current SKU.` |
| `docs/surfaces.md:1` (note at top) | `> **Gate commercial/production:** deferred until Stripe/banking. Gate MCP dry-run may exist as POC; do not market as production enforce.` |
| `docs/dogfood-optics.md:50` | `**Gate commercial/production** (Stripe/banking) is deferred — see surfaces.md.` |

**Verdict: CONFLICT.** The CLI README and surfaces.md are correct and aligned with the canonical model. `docs/PRODUCT_LINEUP.md`, `docs/observe-only.md`, `docs/getting-started-tier01.md`, the Python SDK README and CHANGELOG, and the root README all contradict the canonical model by presenting Gate as a current $499 purchasable SKU. These files need to be updated to remove the $499 Gate pricing and align with the "Gate is not a separate current SKU" statement.

**Remediation (docs/marketing surfaces only — not audited here for edit):**
- `docs/PRODUCT_LINEUP.md` — remove Gate as a standalone $499 SKU; present as internal enforcement tier or remove entirely
- `docs/observe-only.md` — replace Gate ($499) references with Phantom Engine as the enforce/control product
- `packages/vantio-agent-sdk-py/README.md` and `CHANGELOG.md` — update pricing block
- Root `README.md` — update upgrade path language
- `docs/getting-started-tier01.md` — update "Connect Gate / Enterprise" section to match "Connect Phantom Engine / Enterprise"

### 3-B. CONFLICT — `packages/vantio-gate-mcp/src/policy.js` UPGRADE_PATH conflates Phantom Engine with Vantio Enterprise

```js
// packages/vantio-gate-mcp/src/policy.js lines 30-38
{
  plane: "Control",
  brand: "Vantio Phantom Engine",
  sku: "Enterprise",   // ← INCORRECT
  workflow: "Rogue Reconciliation",
  note: "Not exposed as free-form agent tools",
},
```

**Canonical model:** Phantom Engine is the primary paid product at $799/node. Vantio Enterprise is a separate governance/evidence add-on. Labeling Phantom Engine's SKU as "Enterprise" conflates the two and misrepresents the pricing structure to agents consuming this MCP's `gate_upgrade_path` tool.

**Remediation:** Change to `sku: "Phantom Engine ($799/node)"` and add a fourth entry for `Enterprise` as the add-on if desired.

### 3-C. PARTIAL — Gate MCP is shipped but Gate is commercially deferred

`packages/vantio-gate-mcp` exists in the workspace and is published/publishable as `@vantio/gate-mcp`. It has `homepage: "https://vantio.ai/gate"` in `package.json`. The `surfaces.md` note explicitly says "Gate MCP dry-run may exist as POC; do not market as production enforce." The package README correctly says "Dry-run evaluate only. Live enforce = `vantio run` + Gate policy." However, tools `gate_get_policy` and `gate_residual_risk` call a live API (`api.vantio.ai/api/v1/config`, `api.vantio.ai/api/v1/residual-risk`) — these are live production API dependencies, not just local dry-run logic.

**Verdict:** PARTIAL. The dry-run fence is well-documented. But the live API endpoint dependencies in `gate_get_policy` / `gate_residual_risk` are a real runtime dependency on a backend that is "deferred until Stripe/banking." These tools will fail gracefully (returning `ok: false`) when the API is unreachable, but this creates user-visible failures in a "POC" package that is publicly installable. No overclaim in the code; the surface tension is that the package is publicly installable while the commercial offering it depends on is deferred.

### 3-D. CONFLICT — architecture_state.md references moved infrastructure

`architecture_state.md` describes `apps/web` (Next.js control plane, Supabase, Stripe webhook routes, edge-proxy package) as if they are part of this repo. The top-of-file note acknowledges this: "The Tier 02 control plane (`apps/web`) has moved to `vantio-pro`." However, the file also contains live build logs for these components (Phases V-VIII) that no longer apply to this open-core repo.

This is not a claim conflict but creates confusion for contributors about what this repo contains.

### 3-E. CONFLICT — `.env.example` contains variables belonging to moved `apps/web` / `vantio-pro`

`.env.example` lists Supabase, Stripe, Upstash Redis, Resend, and Slack webhook variables. These are all backend dependencies for `apps/web` which has moved to `vantio-pro`. This file is a stale artifact in the open-core repo and may mislead contributors into thinking this repo has a backend.

### 3-F. PARTIAL — SLSA L3 inconsistency in npm-publish.yml

The `npm-publish.yml` publish job (line 78) uses `pnpm install --no-frozen-lockfile` while the test job uses `--frozen-lockfile`. The `enterprise-slsa-provenance.yml` workflow (Phase VIII, corrected in Phase IX) uses `--frozen-lockfile`. The regular publish workflow that ships the actual npm packages does not meet the hermetic build requirement of SLSA L3.

```yaml
# .github/workflows/npm-publish.yml line 78 — publish job
run: pnpm install --no-frozen-lockfile   # ← NOT hermetic
```

```yaml
# .github/workflows/ci.yml line 29 — test job  
run: pnpm install --frozen-lockfile      # ← hermetic (correct)
```

---

## 4. Customer Path

### 4-1. Install

| Step | Status | Notes |
|---|---|---|
| `npm install -g @vantio/cli` | PARTIAL | Version drift risk documented (2026-07-01: stuck at 0.1.0 for 4 versions; 2026-08-15: stuck at 0.3.16 while source had new commands). npm-publish.yml improved; NPM_TOKEN validity unverifiable externally. |
| `pip install vantio-agent-sdk` | PASS | PyPI healthy as of distribution audit. Ubuntu/Debian PEP 668 caveat not documented in main README. |
| Docker: `Dockerfile.observe` | PASS | Functional `vantio run` entrypoint; pins `@vantio/cli@^0.3.1` (range, not exact). |
| K8s example job | PASS | Correctly labeled "observe only — not Phantom Engine host protection." |

### 4-2. First-Run Verify

| Step | Status | Notes |
|---|---|---|
| Offline Sight Loop verify | PASS | `scripts/sight-loop-prove.sh` spins up a local mock LLM server, runs `vantio run` + `vantio prove`, and exits 0. Verifiable by any developer with `node` and `openssl` installed. |
| Node.js agent: `vantio run node agent.js` | PASS | Interceptor injected via `NODE_OPTIONS --require`. Works without an API key. |
| Python agent: `vantio run python agent.py` | PARTIAL | Requires `pip install vantio-agent-sdk` first. `vantio run python` without the SDK injects `sitecustomize.py` but the SDK's hooks are absent, so no events are generated. The CLI prints a notice in this case but the gap is not obvious from the top-level README. |
| Gate/Phantom policy load | TESTED_LOCAL | Policy fetched from `${INGEST_URL}/api/v1/config` on startup (5s timeout). No stranger-host verification available. |

### 4-3. Fail-Closed Rollback

**Status: BLOCKED (by design, not oversight, but not documented at the claim boundary)**

The interceptor explicitly **fails open** when the control plane is unreachable:

```js
// packages/vantio-cli/bin/interceptor.cjs line 146
// ── Default policy (fail-open until cloud policy loads) ──────────────────────

// line 290-293
  } catch {
    // Policy fetch failed — fail open (observe only). Never block the agent
    // because our control plane is unreachable.
  }
```

Additionally, all patch operations use `/* fail open */` catch blocks:

```js
// lines 1337, 1349, 1550, 1553, 1619-1622
try { patchFetch(mod); } catch { /* fail open */ }
try { patchRequest(mod); } catch { /* fail open */ }
```

**Implication:** If a customer deploys with Phantom Engine enforcement and the control plane (`vantio-pro`) is unreachable at agent startup, the interceptor silently falls back to observe-only mode. Agents continue running without any enforcement. There is no "fail closed" mode. This is a deliberate design choice (prioritizing agent availability over enforcement strictness) but is not surfaced to customers as an explicit policy choice or documented in the public-facing product docs.

**This is the most significant operational gap for enterprise customers who need guaranteed enforcement.** A network partition between the host and the Vantio control plane silently removes all enforcement.

### 4-4. Clean Removal / Uninstall

| Step | Status | Notes |
|---|---|---|
| `npm uninstall -g @vantio/cli` | PASS | Standard npm uninstall removes the binary. |
| `rm -rf ~/.vantio/` | PASS | Removes config.json and run logs. |
| Python SDK uninstall | PASS | Standard `pip uninstall vantio-agent-sdk`. |
| `NODE_OPTIONS` cleanup | PASS | `NODE_OPTIONS` is set in child process env only; removed when `vantio run` is no longer the launcher. |
| No persistent kernel/system state | PASS | This repo makes no kernel changes; Phantom Engine is a separate repo. |
| Documented uninstall path | PARTIAL | `vantio logout` is documented. Complete `rm -rf ~/.vantio/` uninstall path is not documented in the public quickstart or getting-started guide. |

---

## 5. Evidence: Export, Independence, Verifiability

### What exists

- **`vantio prove`** generates HTML or Markdown from `~/.vantio/runs/<trace-id>.json` files written by the interceptor on agent exit.
- Reports include: trace ID, machine/PID, timestamp, per-host byte counts, action labels (OBSERVED/ALLOWED/REDACTED/BLOCKED), and summary counts.
- Reports explicitly exclude prompts, completions, API keys, and PII.

### Independence assessment

| Dimension | Status | Notes |
|---|---|---|
| Content independence (no prompts) | PASS | The interceptor explicitly strips body content; run logs and proof artifacts contain only metadata |
| Independent verifier | PARTIAL | `vantio prove` reads logs written by the same interceptor that generated the events. The "auditor" tool is part of the same software under audit. A motivated agent could write forged run logs to `~/.vantio/runs/` and `vantio prove` would report them as genuine. |
| Chain of custody | PARTIAL | Trace IDs are random UUIDs. There is no signing or tamper-evident commitment (no Merkle hash, no HMAC, no append-only log). A local run log can be silently edited before `vantio prove` reads it. |
| Stranger-host verification | BLOCKED | "Stranger-host" is listed as out-of-scope in every spec file. No customer-site validation has been performed. The interceptor has been verified locally but not on uncontrolled third-party hosts. |
| Enterprise `vantio.ai/dashboard` sync | PARTIAL | Remote dashboard sync requires a paid API key + live `vantio-pro` backend. The CLI README correctly notes: "no public self-serve key dashboard today — vantio.ai/dashboard redirects to docs." Dashboard sync is not independently verifiable from this repo. |

### Summary on evidence quality

The proof artifacts are **TESTED_LOCAL, NOT independently verified.** For a design-partner readiness standard, the current evidence posture is: "this process made these metadata-only calls from this machine at this time" — self-attested, with no cryptographic tamper-evidence and no third-party corroboration. This is appropriate for initial conversations but insufficient for formal compliance submissions.

---

## 6. Coverage Map

### Supported paths (Node.js — inside `vantio run`)

| Path | Status |
|---|---|
| `globalThis.fetch` | PASS |
| `undici.fetch`, `undici.request`, `Client/Pool/Agent.request()` | PASS |
| `undici.stream`, `undici.pipeline`, `undici.dispatch`, `undici.connect`, `undici.upgrade` | PASS |
| Node `http/https.request/get`, `ClientRequest` | PASS |
| Node `http2.connect`, session `request()` | PASS |
| Node `net.Socket.connect`, `tls.connect` (in-scope hosts) | PASS |
| `globalThis.WebSocket`, `undici.WebSocket` (host-block + outbound frame size) | PASS |
| Spawned `curl` (including `env`/`timeout`/`nice` prefixes, `-K` url=, `-F` stat size, stdin size when stdin is file) | PASS |
| Spawned `wget` (including prefixes, `--post-file`/`@file` size, `-i` URL lists) | PASS |
| Spawned `httpie` (host-block + `--raw`/field redaction) | PASS |
| Spawned `aria2c` (host-block from argv URLs) | PASS |

### Supported paths (Python — with `vantio-agent-sdk`)

| Path | Status |
|---|---|
| `urllib.request.urlopen`, `OpenerDirector.open` | PASS |
| `requests`, `httpx`, `aiohttp` (when installed) | PASS |
| `http.client.HTTPConnection/HTTPSConnection` | PASS |
| `urllib3.HTTPConnectionPool.urlopen` (when installed) | PASS |
| `socket.connect`, `socket.connect_ex` (in-scope hosts) | PASS |
| Subprocess `curl` + `wget` (Python-spawned) | PASS |
| `pycurl` via `Curl` class (C extension) | PARTIAL — the WRAP_INLINE_REDACT spec notes "from pycurl import Curl before wrap install (named miss; C type has no class-method hook)" |

### Out-of-scope (intentional, documented)

| Gap | Status |
|---|---|
| Browsers / Chromium / CDP | TARGET_DESIGN (explicitly excluded from all specs) |
| Native sockets bypassing Python/Node layers | BLOCKED (requires Phantom Engine) |
| Subprocesses not under `vantio run` / `@shield` | BLOCKED (requires Phantom Engine) |
| Other language runtimes (Ruby, Go, Rust, Java, etc.) | BLOCKED |
| Processes started outside `vantio run` on the same host | BLOCKED (requires Phantom Engine kernel plane) |
| `wget -i` URL-list bodies (content) | TARGET_DESIGN |
| `curl -F` multipart file content rewriting for PII | TARGET_DESIGN |
| stdin `@-` pipe size | TARGET_DESIGN |

### Inside-out gap (compromised / external AI entering the environment)

The interceptor wraps **outbound** calls from supervised processes. It has no visibility into:
- Inbound connections to supervised processes
- Traffic from processes that were not launched under `vantio run`
- Network-layer traffic (requires Phantom Engine eBPF kernel plane)
- Processes that modify the interceptor or `NODE_OPTIONS` to bypass it

An external or compromised AI agent that enters the host through a side channel (inbound connection, socket hand-off, deserialization attack) and spawns its own processes will not be visible to Optics. Phantom Engine is the architectural answer to this, but Phantom Engine's K8s cgroup enforcement and TC `TC_ACT_SHOT` drops remain unverified on a real cluster (per `vantio-phantom-engine/architecture_state.md`).

---

## 7. Product ↔ Autonomous Enterprise Contamination

### Findings

| Finding | File | Severity |
|---|---|---|
| `.env.example` contains Supabase, Stripe, Upstash Redis, Resend, Slack webhook variables belonging to the moved `vantio-pro` backend | `.env.example` | Medium — misleads contributors; stale artifact |
| `architecture_state.md` describes `apps/web` build phases (Next.js, Supabase, Stripe routes, edge-proxy) for a repo that no longer contains those components | `architecture_state.md` | Low — historical log, top note clarifies, but the document is confusing |
| `packages/vantio-gate-mcp/src/policy.js` `fetchCloudConfig` and `fetchResidualRisk` call `api.vantio.ai` (different base than CLI's `vantio.ai`) | `policy.js:165,199` | Low — runtime dependency, handled gracefully with `ok: false` returns |
| `vantio run` summary print ("→ Run `vantio login` to enforce policy and persist events") in free mode — the README correctly says login is optional and for dashboard sync only; this message conflates "login" with "enforcement" | `packages/vantio-cli/README.md:142` | Low — minor UX confusion |
| No dependency on founder reports, private prompts, shared internal credentials, private ops DBs, or undocumented internal endpoints in the open-core packages | — | PASS |

### Product / Autonomous Enterprise boundary

The open-core packages are correctly scoped: they are the observe plane for the product-facing customer stack. The internal ops automation (SDR-Agent, OSINT-Agent, orchestrator described in the ground-truth rules) does not appear in this repo. No contamination of internal ops workflows into open-core product surfaces was found.

---

## 8. Forward-Looking AGI/ASI: Architecture Assessment

### No overclaims found

No AGI/ASI containment claims were found anywhere in this repo. No claims of "universal Linux/endpoint" coverage, "complete control of every agent," reverse engineering of external actions, or physical-safety guarantees. This is appropriate.

### Architecture posture under capability growth

**Capability ≠ authority** design is correctly implemented at the interceptor level:
- The interceptor patches outbound call paths; it does not execute agent code, inspect agent goals, or limit agent reasoning
- `blocked_hosts` blocks access to specific LLM endpoints; a more capable agent could route around this via allowed hosts or unlisted endpoints
- The `allowed_hosts` allowlist is more robust (only listed hosts allowed) but is also only enforced on the wrapped call paths

**Authority durability observations:**
- Policy is fetched from the control plane at startup (one-time, 5-second timeout). A long-running agent could be running stale policy after control-plane policy changes. There is no periodic re-poll mechanism documented in this repo.
- The interceptor applies policy to the current process only. `spawn`/`exec` of child processes injects `NODE_OPTIONS` (for Node children) or `PYTHONPATH` (for Python children), but other language runtimes spawned by an agent are not instrumented.
- A sufficiently capable agent that inspects `process.env.NODE_OPTIONS` could find the interceptor path and potentially unload it; there is no re-injection or tamper detection at the open-core layer.

**Forward-looking summary:** The observe plane (Optics) is an honest, appropriately scoped observability SDK for today's agentic workloads. It is correctly described as "bypassable by design" with the closed path requiring Phantom Engine kernel enforcement. The architecture does not make impossible claims about controlling a more capable AI; the capability-growth boundary is acknowledged through the explicit bypass documentation.

---

## 9. Top Severity-Ordered Findings and Remediation Order

### SEV-1 — CONFLICT: Gate presented as a $499 current standalone SKU in public-facing docs

**Files:** `docs/PRODUCT_LINEUP.md`, `docs/observe-only.md`, `packages/vantio-agent-sdk-py/README.md`, `packages/vantio-agent-sdk-py/CHANGELOG.md`, root `README.md`, `docs/getting-started-tier01.md`

**Impact:** Customers arriving at these docs expect a $499 Gate product that can be purchased. No such product is currently available via self-serve Stripe checkout. This creates sales confusion, missed pipeline, and potential misrepresentation.

**Remediation:** Update all public-facing docs to remove Gate $499 pricing. Align with the canonical model: Phantom Engine ($799/node, 14-day trial) is the primary paid product. Gate enforcement capability is included within Phantom Engine on enrolled nodes. If Gate is to remain visible as a migration/compat identifier, label it as "legacy migration path" or "included in Phantom Engine."

**Priority for design-partner readiness:** This is the highest-priority item for any customer conversation — a prospect who asks to buy Gate at $499 will hit a dead end.

### SEV-2 — BLOCKED: Fail-open enforcement with no documented fail-closed option

**File:** `packages/vantio-cli/bin/interceptor.cjs` lines 146, 290-293, and all `/* fail open */` catch blocks

**Impact:** If the Phantom Engine control plane is unreachable at agent startup, the interceptor silently falls back to observe-only mode. An enterprise customer who believes enforcement is active may have their agents running without enforcement during control-plane outages. This is undocumented in any customer-facing material.

**Remediation:** Either (a) add a documented `VANTIO_ENFORCE_FAIL_CLOSED=1` environment variable that causes the interceptor to abort the child process if policy cannot be loaded, or (b) add a prominent warning in the product docs that enforcement is startup-only and fails open on control-plane unavailability. Option (a) is required for any enterprise customer who needs guaranteed enforcement.

### SEV-3 — PARTIAL: Version drift between source and npm registry (recurring)

**Files:** `docs/distribution-audit-2026-07-01.md`, `docs/specs/OPTICS_CLI_INSPECT_2026-08-15.md`

**Impact:** First-time users follow the quickstart but get a version that is missing documented commands. The distribution audit shows this has happened at least twice (stuck at 0.1.0, then stuck at 0.3.16). The npm-publish.yml fix improves error visibility but does not prevent drift if NPM_TOKEN expires or is revoked.

**Remediation:** Implement post-publish registry version verification (the step was removed because it failed in CI; the root cause was not fully diagnosed). Add automated alerting if the live `npm view @vantio/cli version` diverges from `packages/vantio-cli/package.json version` on the main branch.

### SEV-4 — CONFLICT: UPGRADE_PATH in gate-mcp/policy.js conflates Phantom Engine with Enterprise SKU

**File:** `packages/vantio-gate-mcp/src/policy.js` line 34

**Impact:** Any agent consuming the `gate_upgrade_path` MCP tool receives `sku: "Enterprise"` for Phantom Engine, implying Enterprise pricing when the canonical product is $799/node Phantom Engine. This misrepresents the pricing structure in a machine-readable format that agents may relay to users.

**Remediation:** Update UPGRADE_PATH to use `sku: "Phantom Engine ($799/enrolled node/mo)"` and optionally add Vantio Enterprise as a fourth entry.

### SEV-5 — PARTIAL: Evidence not independently verifiable; no tamper-evident commitment

**File:** `packages/vantio-cli/bin/vantio.js` (generateHtmlReport, generateMarkdownReport), `packages/vantio-cli/bin/interceptor.cjs` (run log write)

**Impact:** `vantio prove` reports are self-generated by the same system under audit. Run logs can be modified before proof generation. There is no HMAC, signature, or append-only commitment. For design-partner conversations with compliance teams, this limits the evidentiary weight of the proof artifacts.

**Remediation:** Add HMAC signing of run log entries at write time using a derived key (e.g., from the trace ID + a machine-specific nonce). Include the HMAC in the proof artifact so an auditor can verify that the log entries were not modified after the run. This does not require a trusted third party — even self-signing is better than no integrity check.

### SEV-6 — PARTIAL: Python `vantio run` without SDK installed silently does not intercept

**File:** `packages/vantio-cli/bin/vantio.js` (isPythonRuntime path), root `README.md:30`

**Impact:** A user who reads `vantio run python agent.py` in the README and runs it without installing `vantio-agent-sdk` will see the `vantio run` prefix accepted with no error, but no LLM calls will be intercepted. The CLI injects `sitecustomize.py` on `PYTHONPATH`, but without the SDK's hooks present, this is a no-op. The root README does note this, but the warning is easy to miss.

**Remediation:** When the interceptor detects `isPythonRuntime(program)` and the injected `sitecustomize.py` finds no `vantio-agent-sdk` installed, print a prominent one-time warning: "[ ∅ VANTIO ] Python SDK not found — no calls will be intercepted. Run: pip install vantio-agent-sdk". This is partial observability loss, not partial enforcement loss, but it directly degrades the Optics value proposition.

### SEV-7 — LOW: `.env.example` is a stale artifact from the moved `apps/web` / `vantio-pro` backend

**File:** `.env.example`

**Impact:** Contributors to this open-core repo may be confused by Supabase, Stripe, and Slack webhook variables that belong to a closed-source backend.

**Remediation:** Replace `.env.example` with a minimal file containing only the variables relevant to open-core development (`VANTIO_API_KEY`, `VANTIO_INGEST_URL`, `VANTIO_TELEMETRY_DISABLED`, `VANTIO_EXTRA_LLM_HOSTS`, `VANTIO_SOAK_LOCAL`). Move the full `.env.example` with backend vars to `vantio-pro`.

### SEV-8 — LOW: SLSA L3 inconsistency in npm-publish.yml

**File:** `.github/workflows/npm-publish.yml:78`

**Impact:** The publish job uses `--no-frozen-lockfile`, making the actual published npm artifacts non-hermetically built. The SLSA enterprise-slsa-provenance.yml workflow uses `--frozen-lockfile` correctly, but that workflow produces a separate attestation artifact, not the npm-published packages themselves.

**Remediation:** Change the publish job to `pnpm install --frozen-lockfile`. If the lockfile is consistently out of date during publish (which would cause the job to fail), fix the lockfile first rather than bypassing it.

---

## 10. What Was NOT Tested / Inaccessible

| Item | Reason |
|---|---|
| Live npm registry version of `@vantio/cli`, `@vantio/optics-mcp`, `@vantio/gate-mcp` | No internet access to `registry.npmjs.org` from audit environment |
| Live PyPI version of `vantio-agent-sdk` | Same — no outbound internet |
| `vantio.ai/api/v1/config` endpoint behavior | No API key and no internet access |
| `api.vantio.ai/api/v1/config` and `/api/v1/residual-risk` (gate-mcp endpoints) | No API key and no internet access |
| `vantio.ai/dashboard` redirect behavior | No browser / internet |
| `vantio-pro` repo (Gate/control plane) | Separate closed-source repo; not in this workspace |
| `vantio-phantom-engine` repo | Separate proprietary repo; not in this workspace |
| Actual policy enforcement behavior with a real API key | No API key available |
| Phantom Engine eBPF enforcement on Linux | Not in this repo; requires privileged kernel environment |
| K8s cluster enrollment, cgroup scoping, TC `TC_ACT_SHOT` drops | Not in this repo; requires real cluster |
| Python SDK on Ubuntu 23.04+ with PEP 668 (externally-managed-environment) | Not reproduced, but documented in distribution-audit-2026-07-01 |
| `packages/vantio-cli/bin/interceptor.cjs` full runtime behavior | Audited by source reading only; functional tests are in `test/interceptor.test.js` (not executed) |
| Gate `vantio-gate-mcp` live policy enforcement path | Dry-run MCP only; live enforcement requires `vantio-pro` backend |
| Stranger-host validation | Explicitly out of scope in all specs; none available |
| Design-partner customer validation | No partner results available in this repo |

---

## Appendix: File-Level Truth Label Summary

| File | Status | Primary Issue |
|---|---|---|
| `docs/PRODUCT_LINEUP.md` | CONFLICT | Gate $499 standalone SKU |
| `docs/observe-only.md` | CONFLICT | Gate $499 referenced |
| `docs/getting-started-tier01.md` | CONFLICT | Gate Pro referenced as purchasable |
| `packages/vantio-agent-sdk-py/README.md` | CONFLICT | Gate $499 pricing |
| `packages/vantio-agent-sdk-py/CHANGELOG.md` | CONFLICT | Gate $499 pricing |
| `README.md` | CONFLICT | Gate $499 upgrade path reference |
| `packages/vantio-cli/README.md` | PASS | Correctly states Gate is not a separate current SKU |
| `docs/surfaces.md` | PASS | Correctly marks Gate commercial as deferred |
| `docs/dogfood-optics.md` | PASS | Correctly marks Gate commercial as deferred |
| `packages/vantio-gate-mcp/src/policy.js` | CONFLICT (minor) | UPGRADE_PATH conflates Phantom Engine SKU with Enterprise |
| `packages/vantio-gate-mcp/src/server.js` | PASS | Dry-run fence clearly stated |
| `packages/vantio-cli/bin/interceptor.cjs` | PARTIAL | Fail-open design not documented publicly |
| `packages/vantio-cli/bin/vantio.js` | PASS | Run, prove, search, tail, diff, discover all present |
| `architecture_state.md` | PARTIAL | Historical build log for moved components |
| `.env.example` | PARTIAL | Stale artifact from moved backend |
| `.github/workflows/npm-publish.yml` | PARTIAL | `--no-frozen-lockfile` in publish job |
| `scripts/sight-loop-prove.sh` | PASS | Offline first-run verification path present |
| All `docs/specs/WRAP_*.md` | PASS | Out-of-scope clearly labeled; stranger-host, browser, Stripe all listed as excluded |
| `deploy/docker/Dockerfile.observe` | PASS | Correctly labeled observe-only |
| `deploy/k8s/optics-observe-job.example.yaml` | PASS | Correctly labeled observe-only |
| `integrations/hooks/` | PASS | Observe-only hooks, fenced correctly |
| `extensions/vantio-optics/extension.js` | PASS | Read-only commands, no enforce |

---

*Audit conducted read-only. No product, marketing, or legal surfaces were modified. All evidence is sourced from files in this repository at commit HEAD on 2026-09-20.*
