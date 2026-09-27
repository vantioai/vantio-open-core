# Evidence retention

Audience: INTERNAL_RESTRICTED

Retention in this lab is an operator-local copy of one accepted run file. It is not the product retention feature. The product has none: `docs/products/optics/KNOWN-LIMITATIONS.md` lists retention, prune, and max size as absent, and files stay until someone deletes them.

## 1. Where bytes live

| Location | Lifetime | Contents |
| --- | --- | --- |
| `$LAB_ROOT/home/.vantio/runs/<cycle-id>.json` | Until the next reset | The interceptor's original file |
| `$LAB_ROOT/retention/<cycle-id>/runs/<cycle-id>.json` | Until `expire --cycle` | Mode `0600` copy |
| `$LAB_ROOT/retention/<cycle-id>/manifest.json` | Until `expire --cycle` | Classification and bookkeeping hash |
| `$LAB_ROOT/cycles/<cycle-id>/` | Until an operator deletes `$LAB_ROOT` | Marker, agent logs, stop notes |
| `$LAB_ROOT/retention/<cycle-id>.expired` | Until an operator deletes `$LAB_ROOT` | Tombstone. No run bytes |
| Git, registries, and uploads | Not used | The scripts have no upload command. `LAB_ROOT` inside the repository is a stop. |

Reset deletes the disposable home and keeps `retention/`. A cycle can therefore survive reset only after `retain` has copied it.

## 2. Allowlist

`retain` copies one file: the run JSON named by `state.env`. It then runs the shape check on the copy.

The manifest is generated. It is not a second copy of the run. Its `run_file` object stores the base name, the byte length, and the SHA-256 of the copy.

Excluded even if they appear in the disposable home:

- `config.json`
- `telemetry-id`
- HTML or Markdown from `vantio prove`
- Agent stdout and stderr (those stay under `cycles/`)

`retain` exits 27 if a `config.json` or `telemetry-id` file is present under the retention directory after the copy.

## 3. Manifest fields

`scripts/emit-cycle-manifest.mjs` writes this object and no other tier:

| Field | Value |
| --- | --- |
| `document` | `CLEAN_HOST_CYCLE_MANIFEST` |
| `audience` | `INTERNAL_RESTRICTED` |
| `schema_status` | `unstable-pre-1.0` |
| `environment_class` | `CLEAN_HOST_INTERNAL_PROOF` |
| `evidence_tier` | `UNSET` |
| `stranger_host` | `NOT_RUN` |
| `phantom_box` | `EXCLUDED` |
| `customer_validation` | `UNSET` |
| `independent_verifier` | `UNSET` |
| `requirement_status_label` | `INTERNAL_PROOF` |
| `product_seal` | false |
| `bookkeeping_sha256_is_a_seal` | false |
| `cli_package` / `cli_version` | Read from `packages/vantio-cli/package.json` at retain time |
| `source_commit` | `git rev-parse HEAD` at retain time |
| `worktree_dirty` | true when `git status --porcelain` is non-empty |
| `cycle_id` | The current cycle |
| `run_file.sha256` | SHA-256 of the retained bytes |

The requirement-status note in the file says `INTERNAL_PROOF` names the lab class, is not an evidence tier, is not customer validation, and does not update the traceability matrix.

The SHA-256 is bookkeeping so the operator can detect a later edit of the copy. `docs/products/optics/PRIVACY-AND-SECURITY.md` records that `vantio prove` does not add a content hash or a signature. This manifest does not close that gap and does not create a certificate.

## 4. Citation rules

A bundle may be cited as a clean-host internal cycle with evidence tier `UNSET`.

A bundle may not be cited as:

- `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`
- a Phantom-Box soak result
- a customer workload
- a current pass that covers a later commit

`worktree_dirty: true` means the bytes were produced from a dirty tree. They are still tier `UNSET`. They are not a sealed tip.

Each cycle id is historical. Retaining a newer cycle does not refresh an older one. Stale evidence does not keep a current pass. This matches the evidence rule in `docs/internal/optics-best-in-class-roadmap.md`: stale evidence cannot retain a current pass. This lab assigns no pass to begin with.

## 5. Expiry

There is no automatic prune and no time-to-live. The operator deletes one cycle with:

`lifecycle.sh expire --cycle <id>`

The id must match `YYYYMMDDTHHMMSSZ-` plus 8 hex characters, and `retention/<id>/` must exist. `--all` is refused so a single invocation cannot clear the directory.

Expiry removes the bundle directory and leaves `retention/<id>.expired`. The tombstone records the id, the UTC time, `run_bytes=removed`, and the classification. It does not contain the run JSON.

If the expired id is the current cycle, `state.env` becomes `STOPPED` with reason `EXPIRED`. The disposable home is unchanged until reset.

## 6. Privacy of retained bytes

The shape check rejects a file that contains the fixture model string. The product writer stores the path and the host, not the request body. A secret placed in the URL path would be stored; the fixture path is `/v1/chat/completions`.

Retained files are mode `0600`. Directory modes are `0700`. Unix modes still depend on the platform. This lab does not set a Windows ACL. The design target is a Linux operator environment, which is where these scripts are written to run.

`LAB_ROOT` must sit outside the git worktree so a later `git add -A` in the repository does not pick up run files. The scripts do not add a gitignore entry, because the allowed root is outside the repository.

## 7. What retention does not store

- Prompts, completions, or the fixture request body
- API keys
- The operator telemetry id
- A machine hostname field (current writers do not set `machine`)
- An evidence tier other than `UNSET`
- A statement that stranger-host ran
