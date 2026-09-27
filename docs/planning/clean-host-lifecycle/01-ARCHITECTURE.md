# Clean-host architecture

Audience: INTERNAL_RESTRICTED

Environment class: `CLEAN_HOST_INTERNAL_PROOF`

Evidence tier: `UNSET`

This document describes the lab. It does not claim the lab has been proved on a stranger host.

## 1. Environment

A clean host in this lab is a disposable process environment on the operator's machine:

- `HOME` points at `$LAB_ROOT/home`.
- `VANTIO_HOME` is unset.
- Control-plane variables are unset.
- Telemetry opt-in is unset, and the disable flags are set for the capture process.
- The only in-scope extra hostname is `127.0.0.1`, and capture sets that itself.
- The fixture is `scripts/fixtures/minimal-agent.js`, talking to a loopback HTTP server bound to `127.0.0.1`.

The lab reuses the free observe path already in this repository. `@vantio/cli` `0.3.24` injects `packages/vantio-cli/bin/interceptor.cjs` with `node --require`. The free path records metadata in a local JSON file. It does not block, and it does not store prompts or completions.

This environment is the producer's machine, or a later operator's machine, with a redirected home directory. The roadmap's `STRANGER_HOST_PROVED` tier is a host that is not the producer's development environment. This lab does not create that host.

## 2. Independence from Phantom-Box

Phantom-Box, in this repository, is the local dogfood control plane. The interceptor selects it only from explicit signals:

```69:73:packages/vantio-cli/bin/interceptor.cjs
// Explicit phantom-box soak only — do NOT infer from localhost (breaks unit tests
// that spin up ephemeral mock control planes on 127.0.0.1).
const SOAK_LOCAL = process.env.VANTIO_SOAK_LOCAL === "1";
// Local control plane (Phantom-Box / dogfood) — never upsell Optics-only.
const LOCAL_GATE = SOAK_LOCAL || /:5001\/?$/.test(String(INGEST_URL || ""));
```

`VANTIO_SOAK_LOCAL` is classified internal in `docs/governance/ENV-VARS.json`. It is a soak harness flag. The governance note says it is not a supported customer setting.

`docs/dogfood-optics.md` points Phantom Box soak status at `../../docs/BUILD_STATUS.md` and `../../docs/MULTI_TIER_SOAK.md`. Those links resolve outside this repository. They are not inputs to this design. Port `5001` is the local `vantio-pro` bind recorded in `artifacts/OPTICS_CLI_AUTH_ENDPOINT_READONLY_2026-09-23.md`. That server is not in this repository, and this lab does not start it.

The clean-host lab excludes Phantom-Box by construction:

| Signal | Lab rule |
| --- | --- |
| `VANTIO_SOAK_LOCAL=1` | Stop. Do not capture. |
| `VANTIO_INGEST_URL` containing `:5001` | Stop. The product regex is the suffix `/:5001\/?$/`. The lab refuses the port anywhere in the URL, including a path after the port. |
| Any other `VANTIO_INGEST_URL` | Stop. The free path leaves the variable unset. The interceptor then defaults the public host and, with no key, stays in free mode. |
| `VANTIO_API_KEY` or `VANTIO_IDENTITY` | Stop. A key is what turns on the control-plane client. |
| `VANTIO_API_BASE`, `VANTIO_CLOUD_INGEST`, `VANTIO_AUDIT_MODE=1` | Stop. Those belong to control-plane or audit paths. |
| Loopback fixture on `127.0.0.1` | Allowed. The interceptor comment says localhost is not Phantom-Box. |

The lab does not infer Phantom-Box from `127.0.0.1`. The fixture server is a test double for one HTTP response. It is not a control plane.

## 3. Why HOME is the isolation boundary

Writers and readers do not share one override:

| Component | Data directory |
| --- | --- |
| Node interceptor | `VANTIO_HOME` or `homedir()/.vantio` (`interceptor.cjs` run-log write) |
| CLI readers (`prove`, `search`, `tail`, `diff`, `discover`, `status`) | `homedir()/.vantio` only. `configDir()` in `vantio.js` joins `homedir()` and `.vantio`. |
| CLI telemetry id | `homedir()/.vantio/telemetry-id` |
| Python writer | `VANTIO_HOME` or the home directory `.vantio` |
| Optics MCP reader | `VANTIO_HOME` or the home directory `.vantio` |

`docs/products/optics/KNOWN-LIMITATIONS.md` records that CLI readers ignore `VANTIO_HOME`. Setting only `VANTIO_HOME` would let the writer and the CLI reader see different directories. This lab therefore redirects `HOME` and leaves `VANTIO_HOME` unset. Capture does not shell out to the CLI. The run file is the artifact. A later operator who wants `vantio prove` can run it with the same redirected `HOME`. This design does not call `vantio prove`, because the HTML writer does not pass mode `0600` and the HTML rendering is not a seal.

## 4. Components

```
operator shell
  lifecycle.sh
    preflight → reset → capture → retain → expire
                     ↘ stop

$LAB_ROOT/                         mode 0700, outside the repo, outside ~/.vantio
  state.env                        current cycle
  home/                            disposable HOME
    .clean-host-cycle
    .vantio/runs/<cycle-id>.json   written by the interceptor
  cycles/<cycle-id>/               logs and stop notes
  retention/<cycle-id>/            copied run file + manifest
  retention/<cycle-id>.expired     tombstone, no run bytes
```

| Piece | Source already in this repo | Lab role |
| --- | --- | --- |
| Interceptor | `packages/vantio-cli/bin/interceptor.cjs` | Observe the fixture call |
| Fixture | `scripts/fixtures/minimal-agent.js` | One POST to the loopback server |
| Loopback server | Started by `scripts/capture.sh` | Binds `127.0.0.1` on an ephemeral port |
| Shape check | `scripts/inspect-run.mjs` | Accept one free-mode `OBSERVED` call to `127.0.0.1` |
| Manifest | `scripts/emit-cycle-manifest.mjs` | Record classification and a bookkeeping SHA-256 |

Capture sets `VANTIO_EXTRA_LLM_HOSTS=127.0.0.1` on the fixture process only. `llm-hosts.cjs` does not treat `127.0.0.1` as an LLM host unless that variable names it, except Ollama on port `11434`. The fixture port is ephemeral and is not `11434`.

## 5. Lifecycle states

| State | Meaning |
| --- | --- |
| `ABSENT` | No `state.env` |
| `RESET_READY` | Disposable home exists for a new cycle id. No accepted run file yet. |
| `CAPTURED` | One run file passed the shape check and still lives only under the disposable home. |
| `RETAINED` | A copy and a manifest exist under `retention/<cycle-id>/`. The evidence tier on that manifest is `UNSET`. |
| `STOPPED` | A stop was recorded. Retention already copied is kept. The disposable home is wiped on the next reset. |

`expire` of the current retained cycle moves that cycle to `STOPPED` and deletes the bundle. A tombstone remains.

## 6. Data the run file is allowed to hold

The Node writer stores hostname, provider guess, method, path, scheme, sizes, HTTP status, `ok`, content-type, duration, action, timestamp, redaction count, and error class. The envelope adds trace id, pid, ppid, Node version, platform, arch, times, CLI version, and summary counts. `docs/products/optics/PRIVACY-AND-SECURITY.md` is the product description of that set.

The shape check requires all of the following:

- `vantio_run_log` `1`, `schema_version` `2`, `plane` `optics`, `free_mode` true
- one call, action `OBSERVED`, hostname `127.0.0.1`, method `POST`, path `/v1/chat/completions`, HTTP 200
- `summary.blocked` 0, `summary.redacted` 0, `summary.est_spend_usd` null
- the fixture model string from `scripts/fixtures/minimal-agent.js` is absent from the file bytes
- no `evidence_tier` field and no `workflow` field on the run object

`workflow` is a Python writer field. This Node cycle rejects it so a different writer cannot be relabeled as this capture.

## 7. Trust boundary

| Inside | Outside |
| --- | --- |
| Disposable `HOME` under `$LAB_ROOT` | The operator's real `~/.vantio` |
| Loopback `127.0.0.1` | Phantom-Box, port `5001`, and any set ingest URL |
| Retention copies of accepted run files | Git, npm, PyPI, and any upload |
| Bookkeeping SHA-256 in the cycle manifest | A product seal, signature, or evidence tier |

Capture records a snapshot of the operator's real `~/.vantio` before the fixture and compares it afterward. A change stops the cycle. The comparison can false-stop if another process writes that directory during the same window. The lab fails closed in that case.

## 8. Failure behavior

The product interceptor fails open for the agent: a control-plane miss does not change the application result. This lab never enters that client, because the key and the ingest URL are absent.

The lab scripts fail closed. A stop leaves the cycle out of `retention/` unless a bundle was already written by `retain`. A rejected run file stays in the disposable home until the next reset, which deletes that home. Reset is refused while status is `CAPTURED` unless the operator passes `--abandon`.

## 9. What a finished cycle is

A retained cycle is an operator-local copy of one free-mode run file plus a manifest. The manifest says:

- environment class `CLEAN_HOST_INTERNAL_PROOF`
- evidence tier `UNSET`
- stranger-host `NOT_RUN`
- Phantom-Box `EXCLUDED`
- requirement-status label `INTERNAL_PROOF`
- `product_seal` false
- `bookkeeping_sha256_is_a_seal` false

The bookkeeping hash lets an operator see whether the copy still matches the bytes that were retained. `vantio prove` does not add a content hash or a signature. This lab does not add one either.

## 10. Out of scope

- A second machine, a VM image, a container build, or a Kubernetes job.
- Kernel, eBPF, or TLS interception. Those are Phantom Engine subjects and are not exercised here.
- Customer traffic, provider traffic, or any host other than `127.0.0.1`.
- Python `shield`, the Node SDK control-plane client, and Gate MCP.
- Changing CLI `0.3.24` so that readers honor `VANTIO_HOME`. The lab routes around that gap by redirecting `HOME`.
