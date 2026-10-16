# Evidence bundle

UTC: 2026-10-16T15:47:41Z

Schema: `vantio.stranger-host-evidence/v1`

Label inside the manifest: `Roadmap`. Tier: `UNSET`.

## Layout

```
<bundle>/
  MANIFEST.json
  host-record.json
  seal.json
  rows-enterprise.json
  rows-descendant-pre.json
  boot-evidence.json
  serial.log
  rows-descendant-post.json
  uninstall.json
  teardown.json
  secret-scan.txt
  grade.json
  SHA256SUMS
  SIGNATURE.json
```

`assemble` writes every file except `SIGNATURE.json`, then the hashes, then the grade. `sign` adds `SIGNATURE.json` and refreshes `SHA256SUMS` so the signature file is not a member of the signed set. `verify` recomputes the hashes, checks the signature, and grades the evidence again. A grade file that disagrees with that fresh grade fails verification with `grade_mismatch`.

Each member is at most 2_000_000 bytes. `assemble` refuses a private-key PEM header, a token prefix `AKIA`, `ghp_`, `xoxb-`, or `sk_live_`, and any JSON field named `prompt`, `messages`, or `completion`.

## Manifest

`MANIFEST.json` carries:

- `schema`
- `created_utc`
- `claim_cap`: `FIXTURE_NOT_A_HOST_PROOF` or `AWAITING_OUTSIDE_REVIEW`
- `label`: `Roadmap`
- `tier`: `UNSET`
- `public_pin_moved`: false
- `production_root`: false
- `base_sha`: `69671e97fa359b685232ec7dd4e9fb4badc7be57`

`claim_cap` values `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, `CUSTOMER_VALIDATED`, and `SHIPPED` are refused.

## Canonical bytes

`SHA256SUMS` lists `sha256` and a relative path for every file except itself and `SIGNATURE.json`, sorted by path. The signed document is:

```json
{"claim_cap":"...","files":[{"path":"...","sha256":"..."}],"key_id":"test-nonprod-ed25519-2026-10-02","schema":"vantio.stranger-host-evidence/v1"}
```

Encoding is UTF-8 JSON with sorted keys and separators `,` and `:`. The signature is Ed25519 over those bytes.

## TEST key only

`SIGNATURE.json` includes the trust document, its sha256, `key_id`, `environment`, `label`, `not_a_production_root`, `public_key_b64`, and `signature_b64`.

Verification accepts `AWAITING_OUTSIDE_REVIEW` only when:

- the trust document sha256 is `2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876`
- there is one key
- `key_id` is `test-nonprod-ed25519-2026-10-02`
- `environment` is `NON-PRODUCTION`
- `label` is `TEST`
- `not_a_production_root` is true
- the signature verifies with that public key
- the bundle contains no private-key PEM

The public installer pin is not a signing key. A production environment, a second key, or any other key id is refused.

`FIXTURE_NOT_A_HOST_PROOF` is the local proof's claim. Its trust document must use the same identity fields and must not hash to the pinned TEST document. `verify` reports `host_proof` false for that claim even when every step passes.

The pinned trust bytes and the TEST private key are not in this repository. `sign --claim awaiting` refuses a trust file whose hash is not the pin. Producing an outside-review signature is an operator action with the existing TEST key. This track does not issue a key.

## Boot evidence

`boot-evidence.json` stores `boot_id`, `cmdline`, `enabled_lsm`, `serial_boot_id`, `serial_sha256`, and `serial_bytes`. `serial.log` is the hypervisor serial text. Both are required for step 6.

## Uninstall evidence

`uninstall.json` stores `status` (`VERIFIED_REMOVED` or `NOT_REMOVED`), `uninstall_verified_line`, `bpftool_vantio_lines`, `bpffs_vantio_names`, and optional `notes`.
