# Optics 0.3.21 — login retirement, Phase 3

**Verdict:** `PASS_WITH_NONBLOCKING_NOTES`  
**Founder path:** `RELEASE_PATH_2_LOGIN_RETIREMENT`  
**Package:** `@vantio/cli` `0.3.21` (unpublished; registry latest is `0.3.20`)  
**Starting HEAD:** `3e1c024f4079e1c51d1d028bfc6d22e02f00e76a`  
**Product HEAD (code):** `3525c6a6be3a24fef4cce6f58766d741687b428c`  
**PR:** https://github.com/vantioai/vantio-open-core/pull/45 — remains DRAFT and `[DO NOT MERGE]`

This document records the account-free release candidate. It does not authorize merge, npm publication, a tag, a GitHub release, a production change, or Phantom Engine work.

The suite numbers in the "Package suite before this report" section were produced on the package tree of `3525c6a` immediately before this file was added. A documentation commit does not change `packages/vantio-cli`. The post-commit confirmation run is appended at the end of this file when that run finishes, and that confirmation is the final-HEAD total. The earlier `3525c6a` log (`duration_ms 15936.11702`) is not reused.

---

## Repository state at product HEAD

| Item | Value |
|---|---|
| Branch | `cli-public-release-remediation-2026-09-23` |
| Starting HEAD (local, origin, PR #45 tip before this report) | `3e1c024f4079e1c51d1d028bfc6d22e02f00e76a` |
| Product commits after start | `cceda4dca332d50b3b5771c467e3526b74546c6b` retire public Optics 0.3.21 account and login surfaces |
| | `3525c6a6be3a24fef4cce6f58766d741687b428c` keep the Optics pack local and show call status in proofs |
| Remote tip before this report | `3525c6a6be3a24fef4cce6f58766d741687b428c` (matches local) |
| Working tree before this report | clean |
| Diff `3e1c024..3525c6a` | 12 files changed, 603 insertions(+), 721 deletions(-) |
| Version | `0.3.21` |
| `npm view @vantio/cli version` | `0.3.20` |
| `0.3.21` in the published version list | absent |

Files changed from `3e1c024` through `3525c6a`:

- `artifacts/FOUNDER_COPY_CHANGE_REQUEST.md`
- `artifacts/OPTICS_CLI_LOGIN_RETIREMENT_PHASE1.md`
- `packages/vantio-cli/.npmignore`
- `packages/vantio-cli/README.md`
- `packages/vantio-cli/bin/interceptor.cjs`
- `packages/vantio-cli/bin/llm-hosts.cjs`
- `packages/vantio-cli/bin/python-wrap/sitecustomize.py`
- `packages/vantio-cli/bin/vantio.js`
- `packages/vantio-cli/package.json`
- `packages/vantio-cli/test/account-retirement.test.js`
- `packages/vantio-cli/test/interceptor.test.js`
- `packages/vantio-cli/test/vantio-cli.test.js`

This report is an additional documentation file. It does not change the package.

---

## Direct-command compatibility

| Command | Decision |
|---|---|
| `vantio login` | Not dispatched. Exit 1. stderr: `vantio: unknown command 'login'` plus the account-free usage text. The usage text does not list login, whoami, or logout. No network. |
| `vantio whoami` | Same as login, with `unknown command 'whoami'`. No network. |
| `vantio logout` | Hidden local compatibility. Deletes `~/.vantio/config.json` if that file exists. Does not read the file, print key material, or open a socket. stdout is only the approved identity and the approved description. Absent from help, README, examples, usage errors, package metadata, and shell completion (the package ships no completion script). |

Preserving logout does not put it on a public surface. Typing the old command still removes a leftover local file. login and whoami cannot be reached through help, README, usage errors, completion, or package metadata. The string `login` or `whoami` appears in stderr only as the unknown-command echo of the token the operator typed.

## Stored-config compatibility

`vantio run`, `discover`, `prove`, `search`, `tail`, and `diff` do not read `~/.vantio/config.json`.

A leftover file is left in place until `vantio logout`. It is not migrated, printed, or transmitted.

The stranger walk wrote a synthetic file:

```json
{"apiKey":"synthetic-canary-9f3c2a-stored-key","ingestUrl":"http://127.0.0.1:<local-port>"}
```

Ordinary runs with that file present contacted only the agent's own `POST /v1/ok` and `POST /v1/fail`. They did not request `/api/v1/config` or `/api/v1/ingest`. `vantio logout` then removed the file (`logout.state = config_removed`) and printed only the two approved sentences.

## Remote ingest

Ordinary local Optics does not call `https://vantio.ai/api/v1/config` or `/api/v1/ingest`.

`isPublicCloudHost()` treats `vantio.ai`, `www.vantio.ai`, and an unparseable base as public. On a public base, `VANTIO_API_KEY` is ignored, so a key in the environment still does not fetch config or post ingest.

An explicit `VANTIO_INGEST_URL` on a different host, together with `VANTIO_API_KEY`, still loads policy from that host's `/api/v1/config` and can post `/api/v1/ingest`. That path is the existing control-plane client. It is not documented as Optics 0.3.21 functionality, and it is not the default. Phantom Engine behavior was not changed.

No paid tier is inferred from the missing production config route. Local runs record `free_mode: true` and `plane: "optics"` without a credential.

## Telemetry

Default is off. `VANTIO_TELEMETRY` must be `1`. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` overrides an opt-in.

The stranger walk's default runs produced no `/api/v1/telemetry` hit. The explicit opt-in, pointed at the local sink (`VANTIO_INGEST_URL` set to that sink, not production), posted one body:

- `event`: `run`
- `hosts`: `["127.0.0.1"]`
- `callCount`: `0`
- `cliVersion`: `0.3.21`
- `anonymousId`: a random UUID
- no API key and no canary

`callCount: 0` is what `sendRunTelemetryOnce` sends. The README table describes `callCount` as the number of intercepted calls at the time of the ping. That sentence is broader than the code. See non-blocking notes. The opt-in was not sent to production.

## Public copy removed

Removed from help, usage errors, README, and the package description:

- login, whoami, and logout as commands a user is told to run
- trial keys
- public API-key setup
- dashboard account sync and remote paid-tier synchronization
- self-service billing and Stripe Checkout
- account setup through hello@vantio.ai
- `/api/v1/config` and `/api/v1/ingest` as available Optics 0.3.21 services
- Free / Pro / Enterprise ladder, Gate-as-product, Shadow AI, and Sight Loop on those public surfaces

No "temporarily unavailable", "coming soon", outage, or return-date sentence was added.

Identity, kept exactly:

`Vantio Optics | Free Observability for AI Agents`

Description, kept exactly:

`Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.`

## FOUNDER_COPY_CHANGE_REQUEST

`artifacts/FOUNDER_COPY_CHANGE_REQUEST.md` keeps the original proposal as historical text and marks it superseded. The proposal was not adopted.

Remaining sentence that still names hello@vantio.ai, unchanged:

`Retention: Unknown. Contact hello@vantio.ai for the data retention policy.`

That sentence is the telemetry retention contact. It is not an account-setup instruction. No new sentence was written for it. Classification: `STILL_REQUIRES_FOUNDER_COPY` only if the Founder wants different retention wording. It does not block this account-free candidate.

No other public sentence is waiting on new Founder copy for this retirement.

---

## Package suite before this report

Command, from `/workspace`:

```bash
pnpm --filter @vantio/cli run test
```

That script runs `node --test`. Exit code `0`.

| TAP field | Value |
|---|---|
| tests | 106 |
| suites | 18 |
| pass | 106 |
| fail | 0 |
| cancelled | 0 |
| skipped | 0 |
| todo | 0 |
| duration_ms | 16368.109387 |

Log: `/tmp/cli-test-pre-report.txt` (not committed).

Lint, same tree:

```bash
pnpm --filter @vantio/cli run lint
```

Exit code `0` (`node --check` on `vantio.js`, `interceptor.cjs`, `telemetry.cjs`, `llm-hosts.cjs`).

Unavailable tests: none reported. Nothing was skipped. This suite does not install a live Python SDK and does not claim cluster or Phantom Engine verification.

Account-retirement coverage inside that suite includes primary help, command help, usage errors, README and package metadata, login/whoami not dispatched, logout local deletion, legacy config ignored, no `/api/v1/config` or `/api/v1/ingest` on the public host (with and without a synthetic key), telemetry default-off, telemetry opt-in not using config or ingest, an explicit non-public control plane still able to load policy, zero-call proof, and a non-2xx proof status.

---

## Candidate tarball

Built from product HEAD `3525c6a6be3a24fef4cce6f58766d741687b428c` after deleting `/tmp/vantio-cli-*.tgz`.

```bash
cd packages/vantio-cli && npm pack --pack-destination /tmp
```

| Item | Value |
|---|---|
| Filename | `vantio-cli-0.3.21.tgz` |
| Path | `/tmp/vantio-cli-0.3.21.tgz` |
| Size | 49624 bytes |
| SHA-256 | `db6a786b0bb9a0e86aa765f3453038c441a6bd3384fe38947dc5ddeb2c7a307b` |

This checksum supersedes `5d5ecba0b9ce09c7b10cbf66df9147a1e9b13a176c4ace602682b26e0910652f`.

Packaged files (7):

- `package/bin/interceptor.cjs`
- `package/bin/llm-hosts.cjs`
- `package/bin/telemetry.cjs`
- `package/bin/vantio.js`
- `package/package.json`
- `package/README.md`
- `package/bin/python-wrap/sitecustomize.py`

No `.pyc`, no tests, no artifacts. A documentation commit does not change these bytes. The tarball is repacked after the final commit; if the hash matches, provenance stays this checksum.

---

## Stranger walk

No nested container runtime is installed (`docker` and `podman` are absent). The walk installed only `/tmp/vantio-cli-0.3.21.tgz` into a clean npm prefix (`/tmp/optics-stranger/prefix`) with a clean `HOME` (`/tmp/optics-stranger/home`). Node was `v22.22.2`. `npm latest` was not installed. No production login was attempted. No real credential was used.

Script: `/tmp/optics-stranger/walk.sh`. Outputs: `/tmp/optics-stranger/out/`.

| Step | Exit | Result |
|---|---|---|
| `npm install -g /tmp/vantio-cli-0.3.21.tgz` | 0 | prefix install |
| `vantio --version` | 0 | `0.3.21` |
| `vantio --help` and command help | 0 | approved identity and description; no account promotion |
| `vantio run` with no program | 1 | `vantio run: no program specified` |
| `vantio frobnicate` | 1 | unknown command; usage has no account commands |
| `vantio login` | 1 | unknown command; no network |
| `vantio whoami` | 1 | unknown command; no network |
| zero-call `vantio run node -e 'process.exit(0)'` | 0 | trace `0x40dada9d3725476b` |
| `vantio run node -e 'process.exit(9)'` | 9 | trace `0xea1c6aeccb67444b`; child status preserved |
| `vantio prove` HTML and Markdown with no `--run` | 0 | latest zero-call log (the exit-9 run): 0 calls, "No calls recorded in this run log." |
| supported `POST /v1/ok` | 0 | agent stdout `{"status":200,"text":"{\"ok\":true}"}`; proof `OBSERVED`, status 200, 11 bytes, trace `0x2aa62561413c458c` |
| `POST /v1/fail` | 0 | agent stdout `{"status":503,"text":"{\"error\":\"upstream\"}"}`; proof `OBSERVED`, status 503, 20 bytes, trace `0x78bb12f474f8454f` |
| `vantio discover` and `discover --local` | 0 | `Scanned 4 run log(s) from ~/.vantio/runs`; 2 calls, 31 bytes |
| `vantio search 127.0.0.1` | 0 | both calls, `OBSERVED`, statuses visible via method/path |
| `vantio tail -n 5` | 0 | latest fail call, 20 bytes |
| `vantio diff` success vs fail | 0 | calls +0, bytes +9 |
| telemetry default | — | no telemetry hit on the default runs |
| `VANTIO_TELEMETRY=1` to the local sink | 0 | one `POST /api/v1/telemetry`; no config; no ingest |
| `vantio logout` | 0 | config removed; stdout is the two approved sentences |

`strace -f -e trace=network` on the success and fail runs recorded `127.0.0.1` only.

Server hit log for the default runs: `POST /v1/ok`, `POST /v1/fail`. No `/api/v1/config`. No `/api/v1/ingest`. The canary string `synthetic-canary-9f3c2a` appears in that hit log because the test agent posted it to the local server. It does not appear in CLI stdout, stderr, HTML proofs, Markdown proofs, discover/search/tail/diff output, telemetry body, or the five run logs.

Run logs have no `machine` field and no `cwd`. They do record `platform`, `arch`, `node_version`, `pid`, and `ppid`.

### HTML inspection

All three proofs (`zero.html`, `ok.html`, `fail.html`) use one h1:

`Vantio Optics | Free Observability for AI Agents`

and one subtitle, the approved description. The document title is `Vantio Proof — <trace>`.

Zero-call HTML: total calls 0, and the sentence "No calls recorded in this run log."

Success HTML: one row, host `127.0.0.1`, action `OBSERVED`, status 200, 11 bytes.

Fail HTML: one row, host `127.0.0.1`, action `OBSERVED`, status 503, 20 bytes.

Footer links: `https://vantio.ai` and `https://vantio.ai/privacy`.

Link check (`curl -L --max-time 25`):

| URL | HTTP |
|---|---|
| `https://vantio.ai` | 200 |
| `https://vantio.ai/optics` | 200 |
| `https://vantio.ai/privacy` | 200 |
| `https://vantio.ai/install` | 200 |
| `https://pypi.org/project/vantio-agent-sdk` | 200 |
| `https://github.com/vantioai/vantio-open-core` | 200 |
| `https://img.shields.io/npm/v/@vantio/cli.svg` | 200 |
| `https://www.npmjs.com/package/@vantio/cli` | 403 (also 403 with a browser User-Agent) |

The npm page result is `UNVERIFIED` from this client. The registry still serves the package name at `0.3.20`. The link was not removed.

Asserts that held on the visible walk output and the three HTML proofs:

- one Optics identity
- no login, account, or dashboard instruction
- no trial-key claim
- no billing claim
- no Gate product name in help, README, or proof prose
- no Free / Pro / Enterprise ladder
- no Shadow AI claim
- no eBPF or kernel claim
- no Sight Loop string
- no hostname, username, or home path in the proofs or run logs
- action label `OBSERVED` (the prose does not say Optics enforced a policy)
- zero-call, HTTP 200, and HTTP 503 evidence match the local server
- child exit 9 preserved
- no telemetry unless opted in
- canary absent from Optics outputs
- proof links return 200

`vantio prove --out <path>` prints that path on stdout. The path is the one the walk passed. It is not written into the HTML.

---

## Independent reviews

Each review judges Optics 0.3.21 as an account-free local product.

### A. CISO / privacy / security

| Item | Status |
|---|---|
| No real credential created, stored as a live secret, or sent | PASS |
| Synthetic canary absent from proofs, run logs, CLI stdout/stderr, and telemetry | PASS |
| `logout` does not read or print the stored file and does not use the network | PASS |
| Default runs do not call `/api/v1/config` or `/api/v1/ingest` | PASS |
| A stored synthetic key and a public-host key do not activate those routes | PASS |
| Telemetry stays off unless `VANTIO_TELEMETRY=1`, and the opt-in body has no key and no prompt | PASS |
| Opt-in during the walk was aimed at the local sink, not production | PASS |
| Production endpoints were not modified | PASS |
| Retention period for `POST /api/v1/telemetry` | UNVERIFIED — README says Unknown and points at hello@vantio.ai; this run did not ask the operator |
| npmjs.com HTML for the package page, from this client | UNVERIFIED — HTTP 403 |
| Non-public `VANTIO_INGEST_URL` plus `VANTIO_API_KEY` can still reach a caller-chosen control plane | PASS as undisclosed compatibility; it is not the default and it is not advertised |

Review A overall: **PASS**. No FAIL. No BLOCKED.

### B. Linux / process / product engineering

| Item | Status |
|---|---|
| Version, help, local run, child status 9, prove, discover, search, tail, diff | PASS |
| Zero-call proof is 0 calls; success proof is status 200 and 11 bytes; fail proof is status 503 and 20 bytes | PASS |
| Discover total (2 calls, 31 bytes) equals 11 + 20 | PASS |
| Package suite exit 0, 106 pass, 0 fail, 0 skip | PASS |
| Pack is 7 files, 49624 bytes, no bytecode | PASS |
| `strace` peers on the instrumented runs | PASS — `127.0.0.1` only |
| Nested container image | UNVERIFIED — no docker or podman; isolation was a clean prefix, a clean HOME, and strace |
| `vantio prove` with no `--run` rendered the exit-9 zero-call log, not the earlier zero-call log | PASS — both logs have 0 calls |
| Telemetry `callCount` is hardcoded to 0 while the README describes a live count | PASS for the local product path; the wording mismatch is a non-blocking note |
| `prove --out` echoes the operator-supplied path | PASS |

Review B overall: **PASS**. No FAIL. No BLOCKED.

### C. Public buyer / design partner

| Item | Status |
|---|---|
| Identity and description match the approved sentences | PASS |
| Quickstart is install, then `vantio run`; no trial key, login, dashboard, or billing step | PASS |
| Help and README do not offer login, whoami, logout, Stripe, Checkout, or a Free / Pro / Enterprise ladder | PASS |
| No coming-soon or temporary-outage claim | PASS |
| Proof links that were checked return 200, except the npm HTML page | PASS for vantio.ai, privacy, install, PyPI, and GitHub |
| npm package page from this client | UNVERIFIED |
| Proof metric labels "PII redacted" and "Blocked" | PASS as counts (both 0 on these runs). The action shown is `OBSERVED`. The labels are a non-blocking note, not a claim that a policy blocked or redacted a call |
| stderr line "auditor-ready artifact" | PASS as a pointer to `vantio prove`. It is not a formal audit attestation. Non-blocking wording |
| hello@vantio.ai retention line | PASS as recorded residual copy; it does not tell the buyer to create an account |

Review C overall: **PASS**. No FAIL. No BLOCKED.

---

## Non-blocking notes

1. This machine has no container runtime. The stranger walk was a clean npm prefix, a clean HOME, and `strace`, not a fresh container image.
2. `https://www.npmjs.com/package/@vantio/cli` returned HTTP 403 to `curl`, including a browser User-Agent. `npm view` shows `0.3.20`. The shields.io badge returned 200. The link was left in place.
3. Local proofs show "PII redacted" 0 and "Blocked" 0. Those counts match the run log (`redacted: 0`, `blocked: 0`). The call action is `OBSERVED`.
4. Opt-in telemetry sends `callCount: 0`. The README describes that field as the number of intercepted calls at ping time. The code path sends 0 on the first in-scope call.
5. The run summary suggests an "auditor-ready" proof. The file is a local metadata report.
6. `interceptor.cjs` still contains the control-plane client: `Vantio Gate blocked` error text, `/api/v1/config`, and `/api/v1/ingest`. Those paths run when `VANTIO_INGEST_URL` is not the public host and `VANTIO_API_KEY` is set. Ordinary local use does not take them. They are not in help or the README.
7. The only remaining hello@ sentence is the telemetry retention line in the README.

---

## Lists

**FAIL:** none.

**BLOCKED:** none.

**UNKNOWN:** none.

**UNVERIFIED:**

- A nested container was not available, so the walk is not a container-image result.
- The npmjs.com package HTML page, from this client (HTTP 403).
- The operator's retention period for opt-in telemetry.

**INCONCLUSIVE:** none.

---

## Confirmations

- PR #45 remains open, draft, and titled with `[DO NOT MERGE]`. This task does not merge it.
- No merge was performed.
- No npm publication was performed. `0.3.21` is not in the registry version list.
- No tag and no GitHub release were created.
- No production endpoint was changed. `GET /api/v1/config` was not deployed, repaired, recreated, redirected, or replaced.
- No real credential was used or written into an output.
- Public pricing was not changed.
- Phantom Engine behavior was not changed.
- Commits are additive. History was not rewritten and nothing was force-pushed.

## Residual Founder decisions

1. Keep, replace, or delete the README sentence `Retention: Unknown. Contact hello@vantio.ai for the data retention policy.`
2. Whether a later release should drop the hidden local `vantio logout` compatibility command.
3. Whether a later, separately scoped product should keep the unadvertised non-public control-plane client (`VANTIO_INGEST_URL` plus `VANTIO_API_KEY`).
4. Any future account or cloud-sync capability. This release does not schedule one.
5. Merge of PR #45, npm publication of `0.3.21`, and any tag or release. This result does not authorize them.

---

## Final-HEAD confirmation

Report commit `c8a41a12aa7f02384e4e4a55b498ea5d50dd0fec` is the first documentation commit. It does not change `packages/vantio-cli`. The suite and the pack below were executed on that commit.

Command, from `/workspace`, at `c8a41a12aa7f02384e4e4a55b498ea5d50dd0fec`:

```bash
pnpm --filter @vantio/cli run test
```

Exit code `0`.

| TAP field | Value |
|---|---|
| tests | 106 |
| suites | 18 |
| pass | 106 |
| fail | 0 |
| cancelled | 0 |
| skipped | 0 |
| todo | 0 |
| duration_ms | 16460.205521 |

Log: `/tmp/cli-test-c8a41a1.txt` (not committed).

Repack at the same commit, after deleting `/tmp/vantio-cli-*.tgz`:

```bash
cd packages/vantio-cli && npm pack --pack-destination /tmp
```

Exit code `0`. Filename `vantio-cli-0.3.21.tgz`. Size 49624 bytes. SHA-256 `db6a786b0bb9a0e86aa765f3453038c441a6bd3384fe38947dc5ddeb2c7a307b`. npm shasum (SHA-1) `a4b8cf50b26a2beaeb6608d03e50eb3028220466`. Seven packaged files, listed above. The checksum matches the pack from product HEAD `3525c6a6be3a24fef4cce6f58766d741687b428c`.

Diff `3e1c024f4079e1c51d1d028bfc6d22e02f00e76a..c8a41a12aa7f02384e4e4a55b498ea5d50dd0fec`: 13 files changed, 1006 insertions(+), 721 deletions(-).

The commit that adds this section is documentation-only. A repeat of the same test command and the same `npm pack` is run after that commit. Pass, fail, and skip counts, and the tarball SHA-256, are the final-HEAD result when they match this table. That repeat is recorded in the PR body.
