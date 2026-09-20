# Claim Scrub Report — vantio-open-core
**Date:** 2026-09-20  
**Authority:** CEO decision 2026-09-20 — Align public GitHub open-core to locked commercial model.  
**Branch:** `cursor/claim-scrub-open-core-1ed9`

---

## Canonical Model (locked)

1. **Optics** — free observe-only entry (this repo)
2. **Phantom Engine** — primary paid product; Observe/Enforce/Control are functions inside PE; $799/node/mo
3. **Vantio Enterprise** — optional governance add-on; "talk to sales"

Gate is NOT a current standalone public SKU. Gate may remain as internal/legacy/compat identifier, clearly labeled.

---

## Phase 1 — File Classification

| File | Classification | Decision |
|------|---------------|----------|
| `docs/PRODUCT_LINEUP.md` | PUBLIC | CONFLICT — scrubbed |
| `docs/observe-only.md` | PUBLIC | CONFLICT — scrubbed |
| `docs/getting-started-tier01.md` | PUBLIC | CONFLICT — scrubbed |
| `docs/optics-mcp.md` | PUBLIC | CONFLICT — scrubbed |
| `docs/sight-loop.md` | PUBLIC | CONFLICT — scrubbed |
| `docs/gate-mcp.md` | PUBLIC | CONFLICT — scrubbed (relabeled legacy/compat) |
| `docs/dogfood-optics.md` | PUBLIC | CONFLICT — scrubbed |
| `docs/surfaces.md` | PUBLIC | CONFLICT — scrubbed |
| `docs/prove.md` | PUBLIC | CONFLICT — scrubbed (Pro/Enterprise → PE/Enterprise) |
| `docs/framework-integrations.md` | PUBLIC | CONFLICT — scrubbed (Pro/Enterprise → PE/Enterprise) |
| `packages/vantio-agent-sdk-py/CHANGELOG.md` | CUSTOMER_SHIPPED | CONFLICT — scrubbed |
| `packages/vantio-agent-sdk-py/README.md` | CUSTOMER_SHIPPED | CONFLICT — scrubbed |
| `packages/vantio-agent-sdk/README.md` | CUSTOMER_SHIPPED | CONFLICT — scrubbed |
| `packages/vantio-agent-sdk/package.json` | CUSTOMER_SHIPPED | CONFLICT — scrubbed |
| `packages/vantio-optics-mcp/README.md` | CUSTOMER_SHIPPED | CONFLICT — scrubbed |
| `packages/vantio-optics-mcp/package.json` | CUSTOMER_SHIPPED | CONFLICT — scrubbed |
| `packages/vantio-gate-mcp/README.md` | CUSTOMER_SHIPPED | CONFLICT — scrubbed (legacy/compat label) |
| `packages/vantio-gate-mcp/server.json` | CUSTOMER_SHIPPED | CONFLICT — scrubbed ("Pro API key" → "Phantom Engine API key") |
| `README.md` | PUBLIC | CONFLICT — scrubbed |
| `CONTRIBUTING.md` | PUBLIC | CONFLICT — scrubbed (added legacy/compat note) |
| `integrations/hooks/openclaw-plugin.example.md` | PUBLIC | CONFLICT — scrubbed |
| `integrations/hooks/README.md` | PUBLIC | CONFLICT — scrubbed |
| `examples/adapters/llamaindex-py/README.md` | CUSTOMER_SHIPPED | CONFLICT — scrubbed |
| `docs/specs/*` | INTERNAL_ONLY | Gate symbols used as internal code identifiers — no rename per task rules |
| `docs/webhooks.md` | INTERNAL | Gate event names are API identifiers — no rename per task rules |
| `architecture_state.md` | INTERNAL | `vantio-pro` reference labeled archival — no change |

---

## Phase 2 — Before/After Summary

### Removed entirely as a purchasable public SKU
- `Gate ($499)` / `Gate ($499/month)` as a line in pricing tables
- `### Enforce · Vantio Gate ($499)` as a feature-layer section
- Four-product commercial ladder: Optics → Gate → Phantom Engine → Enterprise

### Replaced with canonical 3-product model
**Before:** Optics (Free) · Gate ($499) · Phantom Engine ($799/node) · Enterprise (talk to sales)  
**After:** Optics (Free) · Phantom Engine ($799/node/mo) · Enterprise (talk to sales)

### Upgrade path — before
> Residual risk closes with **Vantio Gate**, then **Vantio Phantom Engine**

### Upgrade path — after
> Residual risk closes with **Vantio Phantom Engine** ($799/node/mo) — see vantio.ai/pricing

### Gate — retained as internal/legacy/compat
- `@vantio/gate-mcp` package retained; labeled "legacy/compat; Gate is not a current standalone public SKU" in: README, package description, CONTRIBUTING.md, docs/gate-mcp.md, docs/surfaces.md
- Internal code symbols (`gate_evaluate`, `VANTIO_GATE_BLOCKED`, `GateBlockedError`, `gate.blocked` webhook event names) — NOT renamed per task rules

---

## Phase 3 — Verification Sweep Results

### Search: `$499` / `499/month` / `Gate.*$`
- Only remaining hit: `packages/vantio-agent-sdk-py/CHANGELOG.md` line 7 — **intentional historical note**, clearly labeled

### Search: four-product commercial model / old ladder
- No remaining hits in public/customer-shipped files

### Search: `Gate.*standalone.*SKU` / `Gate.*pro` / `Pro.*Gate`
- Only remaining hits are our own "Gate is not a current standalone public SKU" corrections

### Search: `$50,000` / `$50k` / `$100k` ARR language
- None found in any file

### Search: `vantio-pro`
- Only in `architecture_state.md` (INTERNAL, labeled "archival only")

---

## Remaining CONFLICT Items

**None** — all public/customer-facing stale claims have been resolved.

### Items intentionally NOT changed (per task rules)

| Pattern | Reason |
|---------|--------|
| `gate_evaluate`, `gate_get_policy`, `gate_residual_risk`, `gate_normalize_policy`, `gate_explain`, `gate_upgrade_path` | Internal MCP tool names — no dependency analysis done; rename prohibited |
| `GateBlockedError`, `VANTIO_GATE_BLOCKED` | Internal error class and constant names in code |
| `gate.dry_run_blocked`, `gate.enforcement_gap`, `gate.blocked` | Webhook event type identifiers (API surface) |
| `docs/specs/WRAP_*.md` references to "Gate host-block / size / spend path" | INTERNAL_ONLY spec docs; Gate used as internal function name |
| `vantio.ai/gate` URL in `@vantio/gate-mcp` package.json / server.json | Package-level URLs for a real (legacy/compat) package |

---

## Confirmations

- **AE (Autonomous Enterprise) imports:** None introduced — no AE code imported
- **Package publish:** No `npm publish`, `pnpm publish`, or PyPI publish performed
- **Merge:** PR is draft — not merged
- **Enforcement semantics:** No changes to interceptor logic, fail-open behavior, or package code

---

CLAIM_SCRUB_OPEN_CORE: COMPLETE
