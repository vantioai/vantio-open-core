# Optics CLI login retirement — Phase 1 inventory

**Date:** 2026-09-23  
**Branch:** `cli-public-release-remediation-2026-09-23`  
**Starting HEAD:** `3e1c024f4079e1c51d1d028bfc6d22e02f00e76a` (local and `origin` matched; PR #45 head matched; working tree clean)  
**Package version:** `0.3.21` (npm latest published is `0.3.20`; `0.3.21` is not in the published version list)  
**Prior candidate tarball:** none present in the workspace. Superseded checksum recorded by the task: `5d5ecba0b9ce09c7b10cbf66df9147a1e9b13a176c4ace602682b26e0910652f`  
**Prior auth class:** `AUTH_ENDPOINT_SOURCE_ONLY`  
**Founder path:** `RELEASE_PATH_2_LOGIN_RETIREMENT`

## What ordinary local use did at that HEAD

- `vantio run` read `~/.vantio/config.json` and injected `apiKey` into the child as `VANTIO_API_KEY` when the environment had no key.
- With a key and the default base `https://vantio.ai`, `bin/interceptor.cjs` called `GET /api/v1/config` and, after a paid tier, `POST /api/v1/ingest`.
- `vantio discover` without `--local` called `GET /api/v1/discover` using a stored or environment key, and told a user with no key to run `vantio login`.
- `vantio login` and `vantio whoami` called `GET /api/v1/config`. `vantio logout` deleted the local file only.
- Help omitted the three commands. README Step 3 still documented trial keys, Stripe Checkout, `hello@vantio.ai` for a key, login, whoami, logout, and dashboard sync.
- Install, `--help`, `--version`, and a zero-call run did not themselves call config or ingest unless a stored key was injected on `run`.
- Telemetry stayed off unless `VANTIO_TELEMETRY=1`, and its route is `/api/v1/telemetry`.

## Classification of the public hits

| Surface | Class |
|---|---|
| README Step 3, account command block, `VANTIO_API_KEY` / ingest env rows, enforcement section | PUBLIC_DOCUMENTATION |
| `vantio login`, `whoami`, `logout` dispatch | PUBLIC_COMMAND |
| Discover-without-`--local` login prompt and remote fetch | REMOTE_DEPENDENCY |
| Run injection of stored `apiKey` | REMOTE_DEPENDENCY |
| Interceptor config fetch and ingest when a key is present | REMOTE_DEPENDENCY |
| Logout file delete | LOCAL_ONLY_BEHAVIOR |
| Local prove, search, tail, diff, discover `--local` | LOCAL_ONLY_BEHAVIOR |
| Login/whoami/logout unit tests against a mock server | TEST_FIXTURE |
| `artifacts/OPTICS_CLI_AUTH_ENDPOINT_READONLY_2026-09-23.md` | HISTORICAL_EVIDENCE |
| Prior FOUNDER_COPY proposal to restore login copy | HISTORICAL_EVIDENCE — not adopted |
| Telemetry opt-in | separate from account behavior |

`login`, `whoami`, and `logout` were not in primary help. They were still reachable by typing the command, and login/whoami/logout were documented in the README, so hiding them from help did not keep them non-public.
