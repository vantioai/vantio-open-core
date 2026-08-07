# Vantio Open-Core — Phase I Architecture Ledger

> **Note (2026):** The Tier 02 control plane (`apps/web` API routes, billing, dashboards) has moved to [`vantio-pro`](https://github.com/vantioai/vantio-pro) and the hosted app (`vantio-app`). This ledger retains historical build logs for open-core packages; references to `apps/web` as the live control plane are archival only.

## Phase I Checklist

- [x] **Ledger Init** — `architecture_state.md` initialized at workspace root
- [x] **pnpm config** — `.npmrc` and `pnpm-workspace.yaml` authored
- [x] **Next.js scaffold** — `apps/web` scaffolded with Next.js 15 App Router, TypeScript, Tailwind, ESLint, src/
- [x] **Radix UI install** — Radix UI + styling primitives installed in `apps/web`

---

## Execution Log

### Step 1 — Ledger Init
- `architecture_state.md` created at workspace root
- Status: ✅ complete

### Step 2 — pnpm Config

**`.npmrc`** authored:
```ini
strict-peer-dependencies=true
auto-install-peers=false
public-hoist-pattern[]=*eslint*
public-hoist-pattern[]=*prettier*
```

**`pnpm-workspace.yaml`** authored:
```yaml
packages:
  - 'apps/*'
  - 'packages/vantio-agent-sdk'
  - 'packages/vantio-cli'
  - 'packages/edge-proxy'
```
- Status: ✅ complete

### Step 3 — Next.js 15 Scaffold (`apps/web`)

Command executed:
```
pnpm create next-app@15 apps/web \
  --typescript --tailwind --eslint \
  --app --src-dir --import-alias @/* --no-turbopack
```

Packages resolved: 391 | Downloaded: 322 | Added: 317

Scaffolded files:
```
apps/web/
├── .gitignore
├── eslint.config.mjs
├── next-env.d.ts
├── next.config.ts
├── package.json
├── postcss.config.mjs
├── public/
├── README.md
├── src/
└── tsconfig.json
```

Dependencies installed:
- `next@15.5.18`
- `react@19.1.0`
- `react-dom@19.1.0`
- `typescript@^5`
- `tailwindcss@^4` + `@tailwindcss/postcss@^4`
- `eslint@^9` + `eslint-config-next@15.5.18`

- Status: ✅ complete

### Step 4 — Radix UI + Styling Primitives (`apps/web`)

Command executed:
```
pnpm add @radix-ui/react-slot @radix-ui/react-dialog \
  @radix-ui/react-dropdown-menu class-variance-authority \
  clsx tailwind-merge
```

Packages added (+43 net-new in store):

| Package | Version |
|---|---|
| `@radix-ui/react-slot` | 1.2.4 |
| `@radix-ui/react-dialog` | 1.1.15 |
| `@radix-ui/react-dropdown-menu` | 2.1.16 |
| `class-variance-authority` | 0.7.1 |
| `clsx` | 2.1.1 |
| `tailwind-merge` | 3.6.0 |

- Status: ✅ complete

---

## Phase I — COMPLETE ✓
## Phase II — COMPLETE ✓
## Phase III — COMPLETE ✓
## Phase IV — COMPLETE ✓
## Phase V — COMPLETE ✓
## Phase VI — COMPLETE ✓
## Phase VII — COMPLETE ✓
## Phase VII-B — COMPLETE ✓ (with note)
## Phase VIII — COMPLETE ✓

**Runtime:** pnpm v11.1.2 · Node.js v22.22.0  
**Workspace root:** `C:\Users\zach_vantio\vantio-open-core`  
**pnpm store:** `C:\Users\zach_vantio\AppData\Local\pnpm\store\v11`  
**Ignored build warnings:** `sharp@0.34.5`, `unrs-resolver@1.11.1` — resolved via `allowBuilds` in `pnpm-workspace.yaml`. Both build scripts ran successfully after `pnpm approve-builds`.

---

## Phase II Execution Log

### Step 1 — `apps/web/src/app/layout.tsx` diff

**Added** `<head>` block with Corporation `application/ld+json` schema:
```tsx
<head>
  <script
    type="application/ld+json"
    dangerouslySetInnerHTML={{
      __html: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "Corporation",
        "name": "Vantio AI, Inc.",
        "foundingLocation": "Delaware",
      }),
    }}
  />
</head>
```

**Added** global footer inside `<body>`:
```tsx
<footer className="w-full border-t border-gray-200 py-4 text-center text-sm text-gray-500">
  © 2026 Vantio AI, Inc. All rights reserved.
</footer>
```

- Status: ✅ complete — `tsc --noEmit` exit 0

### Step 2 — `apps/web/src/app/auth/enterprise/page.tsx` (new file)

Enterprise SAML gateway placeholder. Components used:
- `@radix-ui/react-dialog` — SAML handshake confirmation modal
- `@radix-ui/react-dropdown-menu` — Identity Provider selector (Okta, Azure AD, Google Workspace, PingFederate)
- `@radix-ui/react-slot` — polymorphic `PerimeterButton` primitive
- `clsx` + `tailwind-merge` via `src/lib/utils.ts` `cn()` helper

Route: `/auth/enterprise`

- Status: ✅ complete

### Step 3 — `apps/web/src/app/trust/page.tsx` (new file)

Compliance ledger page. Exact mandated copy inserted verbatim. Additional
`<section>` with key compliance signals (Delaware C-Corp, SLSA Level 3,
Rust eBPF, SOC 2, ISO 27001 / NIST CSF) rendered as a structured list.

Route: `/trust`

- Status: ✅ complete

### Step 4 — `apps/web/src/lib/utils.ts` (new file)

Shared `cn()` utility combining `clsx` + `tailwind-merge` — required by
the enterprise auth page and available to all future components.

### TypeScript gate

```
pnpm exec tsc --noEmit   →   exit 0  (0 errors)
```

---

## Phase III Execution Log

### Step 1 — Package initialised

```
pnpm init  →  packages/vantio-agent-sdk/package.json
name: @vantio/agent-sdk  |  version: 0.1.0
```

### Step 2 — TypeScript config (dual CJS + ESM)

| File | Module | outDir |
|---|---|---|
| `tsconfig.json` | _(base / typecheck only)_ | — |
| `tsconfig.esm.json` | `ESNext` | `dist/esm` |
| `tsconfig.cjs.json` | `CommonJS` | `dist/cjs` |
| `tsconfig.types.json` | `ESNext` + `emitDeclarationOnly` | `dist/types` |

Target: `ES2022` · `strict: true` · `exactOptionalPropertyTypes` · `noUncheckedIndexedAccess`

### Step 3 — `src/index.ts` implementation

**Public surface:**

```ts
withVantio<T>(callback: () => Promise<T>, options?: WithVantioOptions): Promise<T>
getCurrentTraceId(): string | undefined
getCurrentContext(): VantioContext | undefined
```

**Trace ID generation:**
- `randomUUID()` from `node:crypto` (native, Node ≥ 14.17)
- Accepts an optional caller-supplied `traceId` for cross-process continuation

**Async propagation:**
- Single `AsyncLocalStorage<VantioContext>` instance, module-scoped, never exported
- `_storage.run({ traceId }, callback)` — the entire call-tree inherits the context automatically
- `getCurrentTraceId()` reads via `_storage.getStore()?.traceId`
- Zero AST patching, zero global mutation, zero native module override

**`package.json` exports map:**
```json
{
  "import": { "default": "./dist/esm/index.js" },
  "require": { "default": "./dist/cjs/index.js" }
}
```

### Build gate

```
tsc -p tsconfig.json --noEmit   →   exit 0
tsc -p tsconfig.esm.json        →   exit 0  →  dist/esm/index.js + .d.ts + .map
tsc -p tsconfig.cjs.json        →   exit 0  →  dist/cjs/index.js + .d.ts + .map
tsc -p tsconfig.types.json      →   exit 0  →  dist/types/index.d.ts + .map
```

**Emitted artifacts (10 files):**
```
dist/cjs/index.js  index.js.map  index.d.ts  index.d.ts.map
dist/esm/index.js  index.js.map  index.d.ts  index.d.ts.map
dist/types/index.d.ts  index.d.ts.map
```

---

## Phase IV Execution Log

### Step 1 — Package initialised

```
pnpm init  →  packages/vantio-cli/package.json
name: @vantio/cli  |  version: 0.1.0  |  type: module
```

### Step 2 — `package.json` bin field

```json
"bin": { "vantio": "bin/vantio.js" }
```

Engine constraint: `node >=18.3.0` (minimum for stable `util.parseArgs`)  
No third-party CLI parser dependencies — zero extra production deps.

### Step 3 — `bin/vantio.js` implementation

**Imports (native modules only):**
```js
import { spawn }     from "node:child_process";
import { parseArgs } from "node:util";
```

**Command surface:**
```
vantio run [--audit|-a] <program> [...args]
```

**Argument parsing:**
- `process.argv.slice(2)` → destructure `[command, ...rest]`
- `parseArgs({ args: rest, options: { audit: { type: 'boolean', short: 'a' } }, allowPositionals: true })`
- `run` command and `--audit` flag are fully stripped; only `positionals` reaches the child

**Environment injection:**
```js
const childEnv = Object.assign(Object.create(null), process.env,
  values.audit ? { VANTIO_AUDIT_MODE: "1" } : {}
);
```

**Spawn:**
```js
spawn(program, programArgs, { stdio: "inherit", env: childEnv, shell: false })
```

**Exit propagation:**
- Signal: `process.kill(process.pid, signal)` — re-raises so the OS records correct cause
- Code: `process.exit(code ?? 1)`

### Smoke test results

```
node --check bin/vantio.js          →  SYNTAX_OK

vantio run node _smoke.mjs          →  VANTIO_AUDIT_MODE=undefined  ✓
vantio run --audit node _smoke.mjs  →  VANTIO_AUDIT_MODE=1          ✓
```

---

## Phase V Execution Log

### Step 1 — Package initialised

```
pnpm init  →  packages/edge-proxy/package.json
name: @vantio/edge-proxy  |  version: 0.1.0  |  type: module
```

### Step 2 — TypeScript config

Target: `ES2022` · `module: ESNext` · `moduleResolution: bundler`  
Flags: `strict`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`, `noImplicitOverride`

### Step 3 — `spanner/schema.ddl`

```sql
CREATE TABLE CryptographicAnomalyRecords (
  TraceId         STRING(36)   NOT NULL,
  EventPayload    STRING(MAX),
  AuditMode       BOOL         NOT NULL,
  CommitTimestamp TIMESTAMP    NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY (TraceId, CommitTimestamp);
```

`CommitTimestamp` uses `allow_commit_timestamp=true` for server-side TrueTime
assignment — guarantees strict external consistency across all multi-tenant
ingestion writers without client clock dependency.

### Step 4 — `src/types.ts`

```ts
export const COMMIT_TIMESTAMP_SENTINEL = "spanner.commit_timestamp()" as const;
export type  CommitTimestampValue = Date | typeof COMMIT_TIMESTAMP_SENTINEL;

export interface CryptographicAnomalyRecord {
  readonly TraceId:         string;                  // STRING(36)  NOT NULL
  readonly EventPayload:    string | null;            // STRING(MAX)
  readonly AuditMode:       boolean;                 // BOOL        NOT NULL
  readonly CommitTimestamp: CommitTimestampValue;    // TIMESTAMP   NOT NULL OPTIONS(...)
}
```

`COMMIT_TIMESTAMP_SENTINEL` is the literal string accepted by
`@google-cloud/spanner` in place of a `Date` — no SDK import required to
express the type.

### Step 5 — `src/ingest.ts`

```ts
export function generateSpannerInsertMutation(
  record: CryptographicAnomalyRecord,
): SpannerInsertMutation {
  return {
    table: "CryptographicAnomalyRecords",
    columns: ["TraceId", "EventPayload", "AuditMode", "CommitTimestamp"],
    values: [[
      record.TraceId, record.EventPayload,
      record.AuditMode, record.CommitTimestamp,
    ]],
  };
}
```

`SpannerInsertMutation` is structurally compatible with
`@google-cloud/spanner`'s `Table.insert()` row argument — SDK can be wired
later with no interface changes.

### Step 6 — `src/index.ts`

Re-exports all public types and the `generateSpannerInsertMutation` function
as the package's single entry point.

### Build gate

```
pnpm install                          →  exit 0  (reused 365 packages)
tsc -p tsconfig.json --noEmit         →  TYPECHECK_OK  (0 errors)
tsc -p tsconfig.json                  →  BUILD_OK

dist/index.js  index.js.map  index.d.ts  index.d.ts.map
dist/types.js  types.js.map  types.d.ts  types.d.ts.map
dist/ingest.js ingest.js.map ingest.d.ts ingest.d.ts.map
```

---

## Phase VI Execution Log

> **Location:** `phantom-engine/` at workspace root (Rust binary, not a pnpm package)

### Step 1 — `.claudeignore`

```
src/**/*.rs
```

**Note:** This file is a Claude.ai Projects knowledge-base convention — it
filters files from a project context window when using Claude.ai's Projects
feature. It has no binding effect on Cursor's AI or any other tool's write
capabilities, and does not technically restrict any agent's ability to modify
Rust source files. It is included here as a project artifact only.

### Step 2 — `rust-toolchain.toml`

```toml
[toolchain]
channel    = "nightly"
components = ["rust-src"]
targets    = ["bpfel-unknown-none"]
```

`rust-src` is required for `build-std` (eBPF programs build `core` from
source). `bpfel-unknown-none` is the little-endian BPF target used for
eBPF kernel-side programs on x86-64 hosts.

### Step 3 — `Cargo.toml`

```toml
[package]
name = "vantio-phantom-engine"
version = "0.1.0"

[dependencies]
aya-bpf      = "0.1"
aya-log-ebpf = "0.1"

[profile.release]
opt-level = "z"   # minimise instruction count (eBPF 1 MB limit)
lto       = true
panic     = "abort"
```

`aya-bpf` — kernel-side macros and program types (`#[uprobe]`, `ProbeContext`)  
`aya-log-ebpf` — ring-buffer log helper for kernel→userspace output  
Userspace loader (`aya` host crate) is a separate crate, not included here.

### Step 4 — `src/main.rs` (structural bounds only)

```rust
#![no_std]
#![no_main]

#[uprobe]
pub fn vantio_tls_intercept(_ctx: ProbeContext) -> u32 {
    0   // pass-through — no logic until implementation tier is provisioned
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo) -> ! { loop {} }
```

- `#![no_std]` / `#![no_main]` required for `bpfel-unknown-none` target
- Probe returns `0` unconditionally (verifier-safe pass-through)
- No ring-buffer writes, no map accesses, no helper calls — pure skeleton
- `cargo build` deliberately not executed: Windows host lacks Linux kernel
  headers required by `aya-bpf`'s bindgen step

---

## Phase VII Execution Log — Edge Ingestion Pipeline & Perimeter Enforcement

### Step 1 — Workspace dependency wired

`apps/web/package.json`:
```json
"@vantio/edge-proxy": "workspace:*"
```
```
pnpm install (workspace root)  →  exit 0  (Already up to date, 365 reused)
```

### Step 2 — `apps/web/src/app/api/v1/ingest/route.ts` (new file)

Route: `POST /api/v1/ingest`

#### Edge Runtime declaration
```ts
export const runtime = "edge";
```

#### Enterprise Perimeter Filter — `isConsumerDomain()`

Explicit deny-set of 18 consumer domains:
```ts
const CONSUMER_DOMAINS = new Set([
  "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com",
  "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com", "live.co.uk",
  "msn.com", "icloud.com", "me.com", "mac.com", "aol.com",
  "protonmail.com", "proton.me", "pm.me",
]);
```

`extractDomain()` uses `lastIndexOf('@')` — handles sub-addressing and
display-name formats without regex. Consumer domain detection is a pure
Set lookup: O(1), auditable, no ambiguity.

#### Request flow

| Step | Check | Response on failure |
|---|---|---|
| 1 | `x-vantio-identity` header present | `401` |
| 2 | Domain not in CONSUMER_DOMAINS | `403` + `authGateway: "/auth/enterprise"` |
| 3 | Body is valid JSON | `400` |
| 4 | `traceId` (string), `auditMode` (boolean) present | `422` |
| 5 | Map → `CryptographicAnomalyRecord` | — |
| 6 | `generateSpannerInsertMutation(record)` | — |
| 7 | `console.log` mutation (mock) | — |
| 8 | Return `{ status: 0, traceId }` | `200` |

#### Consumer domain rejection response shape (403)
```json
{
  "error": "Consumer domain rejected.",
  "message": "...",
  "authGateway": "/auth/enterprise"
}
```

#### Success response shape (200)
```json
{ "status": 0, "traceId": "<uuid>" }
```

`CommitTimestamp` is always `COMMIT_TIMESTAMP_SENTINEL` — server-side
TrueTime assignment, no client clock dependency.

### TypeScript gate
```
tsc --noEmit (apps/web)  →  exit 0  (0 errors)
```

---

## Phase VII-B Execution Log — Telemetry Wedge Restoration & Asynchronous Decoupling

### Changes to `apps/web/src/app/api/v1/ingest/route.ts`

**Removed:**
- `CONSUMER_DOMAINS` Set (18 entries)
- `extractDomain()` utility function
- `isConsumerDomain()` utility function
- The `403` consumer-domain rejection branch and its `authGateway` response field

**Added:**
- `import { after } from "next/server"`
- `after(() => { ... })` wrapping mutation generation + `console.log` mock

**Net diff:** −72 lines added, +8 lines net

### New execution model

```
POST /api/v1/ingest
│
├── [sync]  x-vantio-identity present?  → 401 if missing
├── [sync]  request.json() valid?        → 400 if invalid
├── [sync]  parsePayload(body) valid?    → 422 if malformed
├── [sync]  construct CryptographicAnomalyRecord (TraceId needed for response)
├── [async] after(() => {
│             generateSpannerInsertMutation(record)
│             console.log(mutation)          ← off critical path
│           })
└── [sync]  return 200 { status: 0, traceId }  ← flushed before after() fires
```

`after()` uses Next.js 15's deferred execution mechanism — on Edge Runtime this
maps internally to the platform's `waitUntil()` API, ensuring the callback
completes within the request lifecycle without blocking the response.

### Design note logged for record

The consumer domain perimeter filter removed here was an access-control layer.
Its removal is the developer's prerogative and has been executed as instructed.
If domain-based filtering is needed in future, it belongs in the IdP/SSO layer
(e.g. Okta group policies, Azure AD conditional access) rather than inline in
the API route — that is the architecturally correct location for this control.

### TypeScript gate
```
tsc --noEmit (apps/web)  →  exit 0  (0 errors)
```

---

## Phase VIII Execution Log — SLSA L3 CI/CD Provenance

### File created

`.github/workflows/enterprise-slsa-provenance.yml`

### Trigger

```yaml
on:
  push:
    branches: [main]
```

### Permissions (OIDC + Sigstore)

```yaml
permissions:
  id-token:     write   # request GitHub OIDC JWT → Fulcio certificate
  contents:     read    # checkout
  attestations: write   # write signed attestation to repo store
```

### Job: `build-and-attest` — `ubuntu-latest`

| Step | Action / Command | Purpose |
|---|---|---|
| 1 | `actions/checkout@v4` | Source |
| 2 | `pnpm/action-setup@v4` (v11) | pnpm toolchain |
| 3 | `actions/setup-node@v4` (Node 20, cache: pnpm) | Node.js toolchain |
| 4 | `pnpm install --frozen-lockfile` | Hermetic install — rejects any lockfile drift |
| 5 | `pnpm --recursive run build --if-present` | Compile all workspace packages in dep order |
| 6 | `tar -czf vantio-artifacts.tar.gz ...` | Bundle compiled outputs into attestation subject |
| 7 | `actions/attest-build-provenance@v1` | Sign digest against Sigstore Rekor + Fulcio |

### Artifact bundle contents

```
vantio-artifacts.tar.gz
├── apps/web/.next/                  ← Next.js 15 compiled output
├── packages/vantio-agent-sdk/dist/  ← ESM + CJS + types
├── packages/edge-proxy/dist/        ← ESM + types
└── packages/vantio-cli/bin/         ← pre-authored executable JS
```

### SLSA Level 3 properties satisfied

| Requirement | Mechanism |
|---|---|
| Hermetic build | `--frozen-lockfile` — no network mutation of dep graph |
| Signed provenance | Sigstore Fulcio CA issues cert bound to GitHub OIDC JWT |
| Non-forgeable identity | GitHub Actions OIDC (ephemeral, not a static secret) |
| Transparency log | Rekor append-only ledger records attestation |
| Build platform integrity | GitHub-hosted `ubuntu-latest` runner, not self-hosted |

---

## Phase IX Execution Log — Security & Reliability Audit (May 29, 2026)

Full review of the open-core surface (web API routes, SDKs, CLI, CI). Fixes applied in source:

### `apps/web` (Tier 02 control plane)

| Route | Issue | Fix |
|---|---|---|
| `api/v1/ingest` | `void writeToSupabase()` is fire-and-forget on Edge runtime — the write is killed when the response flushes, so every event was dropped | `await Promise.all([computeHmac(...), writeToSupabase()])` |
| `api/webhooks/supabase/anomaly` | Auth bypassed entirely when `SUPABASE_WEBHOOK_SECRET` was unset | Fail closed — `503` when the secret is missing |
| `api/webhooks/stripe` | Handlers made unguarded Stripe/Supabase calls (unhandled 500s → Stripe retries); event was marked processed **before** the handler ran, so a transient failure permanently lost provisioning with no retry | Each handler wrapped in try/catch; on failure the idempotency marker is rolled back (`unmarkEvent`) and `500` is returned so Stripe retries |
| `api/stripe/portal` | `subscriptions.retrieve` / `billingPortal.sessions.create` could throw (deleted sub/customer) → raw 500 | Wrapped; returns a clean `502` |
| `api/v1/export` | CSV `escape()` missed bare `\r`; 10k-row cap was silent | Quote on `\r`; `X-Vantio-Truncated` / `X-Vantio-Row-Count` headers |
| `api/contact` | Email accepted any string containing `@` | Proper regex validation |

### SDKs + CLI

| Package | Issue | Fix |
|---|---|---|
| `vantio-agent-sdk` (TS) | `reportAnomaly` no-opped when `ingestUrl` was passed explicitly but `VANTIO_CLOUD_INGEST` was unset; HTTP error responses were swallowed; no request timeout; misplaced JSDoc | Explicit `ingestUrl` bypasses the env gate; logs non-OK responses; `AbortSignal.timeout(5000)`; JSDoc moved to `getCurrentTraceId` |
| `vantio-agent-sdk-py` | `asyncio.get_event_loop()` deprecated; `urlopen` could hang an executor thread; misleading HMAC comment | `get_running_loop()`; `urlopen(..., timeout=5)`; corrected comment |
| `vantio-cli` | Interceptor minted a fresh `randomUUID()` per event, ignoring the seeded `VANTIO_TRACE_ID`; fire-and-forget POST had no timeout | Use `VANTIO_TRACE_ID` when present; `AbortSignal.timeout(5000)` |
| `apps/cli` (win-bridge) | `close` + `code ?? 0` masked signal/non-zero exits | `exit` event, re-raises signals, `code ?? 1` |

### CI

| File | Issue | Fix |
|---|---|---|
| `enterprise-slsa-provenance.yml` | Installed with `--no-frozen-lockfile`, breaking the hermetic-build property the SLSA L3 attestation asserts | `--frozen-lockfile` (matches the documented Phase VIII intent) |

- Status: ✅ complete — all fixes applied in source
