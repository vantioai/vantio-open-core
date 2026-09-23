# INTERNAL_RESTRICTED — Optics CLI auth endpoint read-only verification

**Audience:** Founder / CEO only. Not public copy. Not a release note.  
**Date:** 2026-09-23  
**Track:** Optics / `@vantio/cli` 0.3.21 public-release remediation  
**Branch:** `cli-public-release-remediation-2026-09-23`  
**Draft PR:** https://github.com/vantioai/vantio-open-core/pull/45 (remains DRAFT, `[DO NOT MERGE]`)  
**Authorized step:** A) AUTH ENDPOINT READ-ONLY VERIFICATION AND RELEASE-PATH DECISION EVIDENCE ONLY  
**Starting HEAD:** `4166f10a316cb34324ea59063a6f40670fab86e8`  
**Base:** `main` @ `5a62eedaa77d71665491cd1c49e8a67dfdf7df3f`  
**This commit:** additive report only. Ending HEAD is the commit that adds this file. No CLI, website, API, deploy, or product file changed.

## Decision block

| Item | Value |
|---|---|
| Classification | `AUTH_ENDPOINT_SOURCE_ONLY` |
| Release path | `RELEASE_PATH_3_MORE_EVIDENCE_REQUIRED` |
| Optics verdict | `BLOCKED_AUTH` (unchanged) |
| Live result | Unauthenticated `GET https://vantio.ai/api/v1/config` → HTTP 404 HTML from the Vantio marketing site, three times, identical body |
| Expected service | Not reached. Response is the marketing `not-found` page (`x-matched-path: /404`), not a control-plane JSON handler |
| Next Founder decision | Decide whether `GET /api/v1/config` must be deployed on the host `@vantio/cli` calls by default, or whether login, whoami, logout, and dashboard-sync claims must be retired or relabeled in a separate CLI task. |

`AUTH_ENDPOINT_CONFIRMED_DEPLOYED` was not available. The live host did not return the control-plane contract, and this run did not send an API key.

## 1. Checkout

Verified before any live check:

- `git rev-parse HEAD` = `4166f10a316cb34324ea59063a6f40670fab86e8`
- Branch = `cli-public-release-remediation-2026-09-23`
- Working tree clean
- Merge-base with `origin/main` = `5a62eedaa77d71665491cd1c49e8a67dfdf7df3f`

No drift from the required tip. Tests were not re-run. The auth question does not depend on another local Optics rebuild.

## 2. Contract the CLI expects

Owner of the client call: `packages/vantio-cli/bin/vantio.js` on this tip.  
Default base: `https://vantio.ai` (`DEFAULT_BASE`). Override: `VANTIO_INGEST_URL`, else the `ingestUrl` saved at login.

| Piece | CLI expectation |
|---|---|
| Method | `GET` |
| URL | `{base}/api/v1/config` |
| Request headers | `x-vantio-identity: <api key>` only |
| Request body | None |
| Timeout | 8000 ms in `validateKey`; 5000 ms in `bin/interceptor.cjs` policy load |
| Success | Any HTTP 2xx. JSON is optional. When JSON parses, read `policy` and string `tier`. |
| `policy` fields that mark a policy active | `enforce`, `redact_pii`, non-empty `blocked_hosts` or `allowed_hosts`, `spend_cap_usd` > 0, `max_request_bytes` > 0 |
| Paid tier | `tier === "PRO"` or `tier === "ENTERPRISE"`. Any other or missing tier is treated as free for dashboard-sync copy. |
| Invalid key | HTTP 401. Body is not parsed. Login exits 1 and does not write `~/.vantio/config.json`. |
| Any other non-2xx | Login exits 1, key not saved, message `unexpected response (HTTP <status>)`. A 404 is this branch. |
| Network failure | Login exits 1, key not saved. |

Related commands on this tip:

- `login` calls `validateKey`, then writes `{ apiKey, ingestUrl, savedAt }` mode `0600` only after HTTP 2xx.
- `whoami` reads the local file and calls the same GET. It does not rotate or issue a key.
- `logout` deletes the local file only. It makes no HTTP call.
- Dashboard sync is a second step. `bin/interceptor.cjs` loads policy from the same GET, then sets cloud sync only when `tier` is `PRO` or `ENTERPRISE` (or local soak). Ingest is `POST /api/v1/ingest` and is out of this check. Fleet `discover` without `--local` calls `GET /api/v1/discover`, also out of this check.
- Primary `vantio --help` does not list login, whoami, or logout. README Step 3 still documents them.

Local unit tests mock this route. They are not evidence that production implements it.

## 3. Live read-only checks

Unauthenticated. No `x-vantio-identity`. No body. No cookie. No API key. No other URL.

Request:

```http
GET /api/v1/config HTTP/2
Host: vantio.ai
Accept: application/json
User-Agent: vantio-optics-auth-readonly-verify/0.3.21
```

Check 3 added `Cache-Control: no-cache` and `Pragma: no-cache`. The cache status stayed `HIT`.

| Check | UTC | America/New_York | Status | x-vercel-id | age (s) |
|---|---|---|---|---|---|
| 1 | 2026-09-23T05:03:00Z | 2026-09-23T01:03:00-0400 | 404 | `iad1::fttzl-1790139780388-8c5faecefc4e` | 14863 |
| 2 | 2026-09-23T05:03:02Z | 2026-09-23T01:03:02-0400 | 404 | `iad1::tbx5z-1790139782440-a4bdb4e81c86` | 14865 |
| 3 | 2026-09-23T05:05:24Z | 2026-09-23T01:05:24-0400 | 404 | `iad1::mbx9t-1790139924740-2cd030ecb364` | 15007 |

Shared response headers (non-sensitive):

| Header | Value |
|---|---|
| server | `Vercel` |
| content-type | `text/html; charset=utf-8` |
| content-disposition | `inline; filename="404"` |
| content-length | `42730` |
| x-matched-path | `/404` |
| x-vercel-cache | `HIT` |
| etag | `"303ab2fda40e971b4f37e838777c7b53"` |
| last-modified | `Wed, 23 Sep 2026 00:55:16 GMT` |
| cache-control | `public, max-age=0, must-revalidate` |
| strict-transport-security | `max-age=63072000; includeSubDomains; preload` |
| x-frame-options | `SAMEORIGIN` |
| x-content-type-options | `nosniff` |
| referrer-policy | `strict-origin-when-cross-origin` |
| permissions-policy | `camera=(), microphone=(), geolocation=(), interest-cohort=()` |
| x-dns-prefetch-control | `on` |
| access-control-allow-origin | `*` |

Redacted body: HTML document, 42730 bytes, SHA-256 `3aea0aa812bab33114e6d83925a6461a130cc261963cd418b62035dc1e133a8b` on all three checks. Title `Page not found | Vantio`. Heading `That page is not here.` Deployment attribute `data-dpl-id="dpl_ixTfUX1NEHqyV1yrpSLTfzunR1Et"`. No JSON body. No `Unauthenticated` or `Invalid API key` payload. No credential material.

Reproducible: yes. Three identical bodies and the same status, etag, matched path, and server.

The cached object was generated at 00:55:16Z. Client cache-bypass headers did not produce a miss. Vercel deployment history was not readable from this run (Vercel integration is unauthenticated and was not signed in). The observed response is the marketing 404 cached at that timestamp. `x-matched-path: /404` means this deployment matched the site not-found page. A Next.js route handler for `/api/v1/config`, even one that returned 404 JSON, would have matched that path instead.

## 4. What answered the request

The live page matches `vantioai/vantio-app` branch `cursor/vantio-web-next-main` (repository default branch, tip `7c9fc9b60139580f29f4b57c83c5c5fd32502ef0`, 2026-09-13T14:34:09Z):

- `app/not-found.tsx` title is absolute `Page not found | Vantio` and the heading is `That page is not here.`
- `next.config.ts` applies the same security-header set returned live, on `/:path*`.
- `app/api/` on that branch contains `billing`, `contact`, `design-partners`, `leads`, `portal`, `support`, and `telemetry`. There is no `app/api/v1/` directory.
- Commit history on that branch for `app/api/v1/config/route.ts` and for `src/app/api/v1/config/route.ts` is empty.
- No `middleware.ts` on that branch.
- `vercel.json` and `next.config.ts` redirects do not mention `/api/v1/config`. `/dashboard` on that branch redirects to `/docs`. This run did not live-check `/dashboard`.
- `app/api/telemetry/route.ts` is `GET /api/telemetry`, a marketing idle snapshot. It is not `/api/v1/config`.

`vantio-app` branch `main` (`fed1872258837f0dce076443f6628f8b8903b257`, last commit 2026-07-02T21:47:11Z) is a different tree. Its not-found copy is `404 · Blocked at the boundary` / `This page doesn't exist.` Production did not return that copy.

The 00:55:16Z cache timestamp is later than the default-branch tip commit. It is a deploy or cache time. This run could not bind `dpl_ixTfUX1NEHqyV1yrpSLTfzunR1Et` to a git SHA. The HTML fingerprint is the marketing not-found page, which is the page on the default branch and is not the page on `main`.

## 5. Where the handler exists in source

### 5.1 `vantio-app` `main` — hosted-app handler, not the live tree

Path: `src/app/api/v1/config/route.ts`  
Blob: `e6600c09f7f712fbabe716a622b5455d430405a4`  
Introduced: `f70df3d193d58dca22b386642acaeb9d5951cdd7` (2026-06-19, extract from open-core)  
Last edit: `d7b36f5b592ca8414289a7a7d8c2c7446ad1b32a` (2026-07-02T01:04:33Z, `fix(api): expose tenant tier in /api/v1/config response`)

| Piece | This handler |
|---|---|
| Runtime | Next.js `edge` |
| Method | `GET` |
| Registration | App Router file `src/app/api/v1/config/route.ts`. No separate middleware file was required for the route to exist. |
| Missing header | HTTP 401 `{ "error": "Unauthenticated.", "message": "x-vantio-identity header is required." }` |
| Unknown key | HTTP 401 `{ "error": "Invalid API key." }` after `tenants.api_key` lookup |
| Lookup failure | HTTP 500 `{ "error": "Failed to validate identity." }` |
| Rate limit | HTTP 429 when Upstash env is set. 120 requests / minute / key. Prefix `vantio:config`. |
| Non-PRO / non-ENTERPRISE success | HTTP 200 `{ policy: DEFAULT_POLICY, tier }` |
| Paid success | HTTP 200 `{ policy, tier }` from `tenant_policies` |
| Paid tenant with no policy row | HTTP 200 `{ policy: DEFAULT_POLICY }` and **no `tier` field** |
| Read failure | HTTP 200 `{ policy: DEFAULT_POLICY, tier }` |
| Env | `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`. Optional `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`. Values were not read. |

That missing-`tier` branch matters only if this file is later deployed. The current CLI treats a 200 without `tier` as a free plan. This run did not change the handler and did not verify the branch live.

### 5.2 `vantio-pro` — local control plane

Repository default branch: `cursor/vantio-pro-control-plane` @ `59f004162934ef595cad55d2e40d7512252f1276`.  
File: `vantio_pro/server.py`.  
Listen default: `127.0.0.1:5001` (`VANTIO_PRO_HOST` / `VANTIO_PRO_PORT`). `scripts/run_local.sh` uses the same default.  
Documented base in `docs/CONTRACT.md`: `http://127.0.0.1:5001`.

| Piece | This server |
|---|---|
| Method | `GET` |
| Path match | Exact `/api/v1/config` in `do_GET` |
| Auth accepted | `x-vantio-identity`, then `Authorization: Bearer`, then `?key=` or `?api_key=` |
| Missing key | HTTP 401 `{ "error": "missing api key" }` |
| Unknown key | HTTP 401 `{ "error": "unknown api key" }` |
| Success | HTTP 200 `{ "tier": <tenant tier>, "policy": <object> }`. May also include `never_block_stripped` and `never_block_note`. |
| Unmatched path | HTTP 404 `{ "error": "not found" }` JSON, which is not what vantio.ai returned |
| Storage | Local DB under `VANTIO_PRO_DATA_DIR`. Not the Supabase tenant lookup in the website handler. |

`docs/CONTRACT.md` success example is `{ tier, policy }` with the same policy fields the CLI reads. Its maturity notes describe multi-tenant cloud control as roadmap and the server as local / on-prem. This run did not start that server and did not send a key to it.

The `vantio-pro` README still frames a standalone Gate product. That framing is not current public SKU truth. Public SKUs remain Optics, Phantom Engine, and Vantio Enterprise. This report does not adopt that README's prices.

### 5.3 Open-core history

`apps/web/src/app/api/v1/config/route.ts` existed in this repo until `724b95435d20348974aac8cd543c5e58f611d527` (2026-06-18T21:53:25-0400), which removed `apps/web` and recorded the move to `vantio-app`. The deleted handler returned `{ policy }` and did not return `tier`. The CLI read of `data.tier` arrived later in `1354379` (2026-07-01). The July 2 website commit is the source change that added `tier` to the hosted handler. None of that history is what answered the live request.

`architecture_state.md` in open-core says the Tier 2 control plane moved to `vantio-pro` and `vantio-app`, and that its `apps/web` notes are archival. This repo's `vercel.json` only sets an install command. It does not publish `/api/v1/config`.

Org code search for the path found client callers in open-core and a control-plane mention in Phantom Engine reference architecture. It did not find a route file on the marketing branch. Phantom Engine was not modified. No Phantom Engine deploy was treated as the host of `https://vantio.ai`.

## 6. Why this classification

`AUTH_ENDPOINT_SOURCE_ONLY`

The handler exists in source. It is absent from the tree whose not-found page production returned. The live route is unregistered on that deployment.

Labels not selected:

| Label | Why it was not selected |
|---|---|
| `AUTH_ENDPOINT_CONFIRMED_DEPLOYED` | Live response is the marketing HTML 404. Success and invalid-key JSON were not observed. No key was sent. |
| `AUTH_ROUTE_MISCONFIGURED` | The live deployment has no rewrite or middleware for this path. `x-matched-path: /404` is the site not-found match. The local server's default bind is `127.0.0.1`, which is a different program, not a misrouted Vercel path. |
| `AUTH_ENDPOINT_REGRESSED` | A prior production deploy of `vantio-app` `main` is possible and was not proven. Vercel deployment history was not available. |
| `AUTH_ENDPOINT_INTENTIONALLY_RETIRED` | The marketing branch never contained the route, and `/dashboard` redirects to `/docs` in that branch's source. No Founder decision in this track retires the CLI contract. `FOUNDER_COPY_CHANGE_REQUEST.md` is still awaiting review. |
| `AUTH_ENDPOINT_MISSING` | Too narrow for this pass. It described the 404 alone. The handler is present on `vantio-app` `main` and in `vantio-pro`. |
| `AUTH_CONTRACT_MISMATCH` | There is no live JSON contract to compare. Source-only gap, recorded above: the website handler omits `tier` when a paid tenant has no policy row. |
| `AUTH_DEPLOYMENT_UNVERIFIED` | The live deployment answer is verified: marketing 404, three times. Unverified items are the historical Vercel alias and the git SHA inside `dpl_ixTfUX1NEHqyV1yrpSLTfzunR1Et`. |
| `AUTH_CONTRACT_UNKNOWN` | The client contract and both server sources are known. The live call did not reach either server. |

"Never deployed on any earlier production alias" is not claimed. "Not in the deployment that answered this check" is claimed.

## 7. Release path

`RELEASE_PATH_3_MORE_EVIDENCE_REQUIRED`

`RELEASE_PATH_1_AUTH_REPAIR` would mean the endpoint is intended to ship on the host the CLI calls, and a separate Founder-authorized deployment task must put it there before Optics can be released.

`RELEASE_PATH_2_LOGIN_RETIREMENT` would mean the endpoint is not intended to ship, and a separate Founder-authorized CLI task must retire or relabel login, whoami, logout, dashboard-sync claims, and the account-management docs.

Both are consistent with part of the evidence:

- The CLI still defaults to `https://vantio.ai` and still implements login against `GET /api/v1/config`. README Step 3 still tells a reader to run `vantio login` for a Phantom Engine or Enterprise key.
- The site that currently answers that host is the marketing tree. It does not register the route. Its source redirects `/dashboard` to `/docs`.
- A full handler remains on an older website branch and in the local `vantio-pro` server. The local server's own docs place it on `127.0.0.1:5001` and mark multi-tenant cloud control as roadmap.

Choosing repair or retirement from this evidence would invent the product decision the copy request already left open. This run does not start either task.

## 8. Founder copy request — pending, not applied

File: `artifacts/FOUNDER_COPY_CHANGE_REQUEST.md`  
Status in that file: `AWAITING FOUNDER REVIEW`  
This run did not edit it and did not change help text, README, or any other public copy.

Decisions still open in that file:

1. Whether production `/api/v1/config` is deployed and accepting trial keys. That file says yes would allow the proposed help block below, and no would leave login hidden from primary help with the README trial subsection as it is now. This verification answers the deployed half: it is not on the live host. It does not answer trial-key acceptance. No key was used.
2. Whether README Step 3 is approved as written. Current text says to request a trial via hello@vantio.ai, or complete Stripe Checkout once self-serve billing is live, and states that keys are not yet public and that `vantio.ai/dashboard` redirects to docs.
3. Whether any specific auth-unavailable sentence is approved for public help.

Proposed block in that file, still unused:

```text
Account (Phantom Engine / Enterprise trial key required):
  vantio login [key]          Save & validate your API key
  vantio logout               Remove the stored key
  vantio whoami               Show the stored key (masked) + connection status

  Get a key: hello@vantio.ai (trial) or vantio.ai/pricing (once self-serve is live).
  Free Optics — vantio run, prove, search, tail, diff, discover --local — needs no key.
```

Already done on this branch, and left as-is: login, logout, and whoami are absent from primary `vantio --help` and remain callable. README keeps them under "Account management (requires a trial key — see Step 3 above)."

## 9. Verdict

`BLOCKED_AUTH`

The production endpoint the CLI calls is not independently confirmed deployed. Its success schema and its invalid-key schema were not observed live. Source and local mocks were not treated as a working production login.

No reclassification toward PASS.

## 10. Hard-stop confirmations

| Stop | State |
|---|---|
| npm publish | Not done |
| Merge | Not done |
| Release tag | Not created |
| Production endpoint or config change | Not done |
| Real API key use, creation, issuance, rotation, or exposure | Not done |
| CLI, website, API, or deployment code change | Not done |
| Public copy or pricing change | Not done |
| Phantom Engine change | Not done |
| Force-push or history rewrite | Not done |
| PR #45 | Remains DRAFT and `[DO NOT MERGE]` |
| Optics remediation suite re-run | Not done |
| Endpoint repair, login retirement, copy application | Not started |

## 11. Next Founder decision

Decide whether `GET /api/v1/config` must be deployed on the host `@vantio/cli` calls by default, or whether login, whoami, logout, and dashboard-sync claims must be retired or relabeled in a separate CLI task.
