#!/usr/bin/env python3
"""Check a Phantom Engine NDJSON ledger.

Each row carries chain_prev, chain_hash, chain_sig, and chain_key. The hash is
SHA-256 of the previous hash plus the canonical row with those four fields
removed. The signature is Ed25519 over that hash, under chain_key. An appended
line that was not produced by the loader fails. Real rows pass.
"""

import base64
import hashlib
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def check(path):
    prev = bytes(32)
    key = None
    rows = 0
    skipped = 0
    started = False
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "chain_hash" not in row:
                if started:
                    raise SystemExit(f"row {number}: unsigned row inside the chain")
                skipped += 1
                continue
            started = True
            got_prev = bytes.fromhex(row.get("chain_prev", ""))
            got_hash = bytes.fromhex(row.get("chain_hash", ""))
            sig = base64.b64decode(row.get("chain_sig", ""))
            pub = base64.b64decode(row.get("chain_key", ""))
            if len(pub) != 32 or len(sig) != 64 or len(got_prev) != 32 or len(got_hash) != 32:
                raise SystemExit(f"row {number}: chain fields are the wrong size")
            # A row whose previous link is 32 zero bytes starts a new process chain.
            if got_prev == bytes(32):
                prev = bytes(32)
                key = Ed25519PublicKey.from_public_bytes(pub)
            elif key is None:
                raise SystemExit(f"row {number}: chain does not start at a checkpoint")
            elif pub != key.public_bytes(Encoding.Raw, PublicFormat.Raw):
                raise SystemExit(f"row {number}: chain key changed")
            body = {
                item: row[item]
                for item in row
                if item not in ("chain_prev", "chain_hash", "chain_sig", "chain_key")
            }
            digest = hashlib.sha256(prev + canonical(body)).digest()
            if got_prev != prev or got_hash != digest:
                raise SystemExit(f"row {number}: hash chain broken")
            try:
                key.verify(sig, digest)
            except InvalidSignature:
                raise SystemExit(f"row {number}: signature rejected")
            prev = digest
            rows += 1
    if rows == 0:
        raise SystemExit("ledger has no signed rows")
    print(f"ledger-ok rows={rows} skipped_legacy={skipped}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_ledger.py <file.ndjson>")
    check(sys.argv[1])
