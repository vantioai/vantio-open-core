# Trust public keys

The installer includes public keys for license tokens and for production artifact signatures. Private keys are not in this repository. Agents do not generate, read, or store private keys.

## Which file holds which key

| File | Key id | Role |
| --- | --- | --- |
| `packages/vantio-install/vantio_install/trust/license-public-keys.json` | `lic-live-2026-10` | Ed25519 public key for live license tokens |
| `packages/vantio-install/vantio_install/trust/artifact-public-keys.json` | `prod-artifact-2026-11` | Ed25519 public key for production artifact signatures |
| `packages/vantio-install/vantio_install/trust/dev-public-keys.json` | none | Empty. Not a production key |

The license key id is the `kid` field. The file is schema 2, `build_mode` is `live`, and `revoked_kids` is an empty list. The public key is standard base64 of the raw 32-byte key, in `public_key_b64`. A live build of this package trusts that one key. A test build trusts none of the keys in that file.

The artifact key id is the `key_id` field. The loader reads `key_id`, `key_class` (`production`), and `public_key_b64`. The id `prod-artifact-2026-11` is the published filename `prod-artifact-2026-11.pub` with the extension removed. Confirm that name before relying on it.

## Fingerprints

Each fingerprint is the SHA-256 of the raw 32-byte Ed25519 public key. It is not the SHA-256 of a PEM file.

| Key id | SHA-256 of the raw public key |
| --- | --- |
| `lic-live-2026-10` | `9ddf4480807c44e963864dafaace202755c21af2acdd6a1f2a887457f69531c5` |
| `prod-artifact-2026-11` | `aea8a06fe3dfd090e3c35e5a4dee6015e5e283ac7b66caf6f14a58f91ae724e4` |

From the trust file:

```bash
python3 -c '
import base64, hashlib, json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
raw = base64.b64decode(doc["keys"][0]["public_key_b64"], validate=True)
if len(raw) != 32:
    raise SystemExit("expected a raw 32-byte public key")
print(hashlib.sha256(raw).hexdigest())
' packages/vantio-install/vantio_install/trust/license-public-keys.json
```

Use the artifact trust file in that command to print the other fingerprint.

From a PEM SubjectPublicKeyInfo file that contains only the public key:

```bash
openssl pkey -pubin -in KEY.pub -outform DER | tail -c 32 | sha256sum
```

The PEM file must be an Ed25519 public key. The last 32 bytes of that DER encoding are the raw key. Compare the printed digest to the table above.

## Rotation

1. Choose a new dated key id. License ids look like `lic-live-YYYY-MM`. Artifact ids look like `prod-artifact-YYYY-MM`.
2. Add the new public key to the trust file in a new installer release. Leave the previous public key in the file.
3. Sign new license tokens and new artifact signatures with the new key id.
4. Keep the previous public key until every outstanding license token signed by it has expired. An annual token is the longest wait.
5. Remove the previous public key in a later installer release.

The private half of a rotated key stays in the production secret store. This repository does not configure that store, and the private half is not part of the installer release.

## Revocation

Add a license key id to `revoked_kids` in `license-public-keys.json` and release the installer with that list. The loader drops a revoked id and keeps every other well-formed key. A malformed entry, a duplicate id, or a key whose mode does not match `build_mode` empties the whole set, so a revocation edit has to leave schema 2 and the remaining key records valid.

Artifact trust has no `revoked_kids` list. An installer release that removes a `key_id` from `artifact-public-keys.json` is what stops the installer from trusting that artifact key.

## Private keys

Private keys are never in this repository. Agents never handle them.
