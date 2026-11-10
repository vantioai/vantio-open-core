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


def trusted_key(path):
    if len(sys.argv) >= 4 and sys.argv[1] == "--trust-b64":
        return base64.b64decode(sys.argv[2])
    for candidate in (path + ".head.trust", path + ".trust", "/run/vantio-ledger-trust"):
        try:
            raw = open(candidate, encoding="utf-8").read().strip()
        except OSError:
            continue
        if raw:
            return base64.b64decode(raw)
    raise SystemExit(
        "ledger trust key missing. Pass --trust-b64 or the loader's vantio-ledger-trust file."
    )


def check(path):
    trust = trusted_key(path)
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
            if key is None:
                if got_prev != bytes(32):
                    raise SystemExit(f"row {number}: chain does not start at a zero checkpoint")
                if pub != trust:
                    raise SystemExit(
                        f"row {number}: chain key is not the trusted key anchored outside the ledger"
                    )
                key = Ed25519PublicKey.from_public_bytes(pub)
            elif got_prev == bytes(32):
                raise SystemExit(f"row {number}: zero chain_prev is only valid on the genesis row")
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
    check_head(path, key, rows, prev)
    print(f"ledger-ok rows={rows} skipped_legacy={skipped}")


def check_head(path, key, rows, final_hash):
    head_path = path + ".head"
    try:
        raw = open(head_path, encoding="utf-8").read()
    except OSError:
        raise SystemExit(f"ledger head missing: {head_path}")
    head = json.loads(raw)
    pub = base64.b64decode(head.get("chain_key", ""))
    sig = base64.b64decode(head.get("sig", ""))
    if pub != key.public_bytes(Encoding.Raw, PublicFormat.Raw):
        raise SystemExit("ledger head key does not match the chain")
    body = {
        "chain_key": head["chain_key"],
        "count": head["count"],
        "final_hash": head["final_hash"],
    }
    try:
        key.verify(sig, canonical(body))
    except InvalidSignature:
        raise SystemExit("ledger head signature rejected")
    if int(head["count"]) != rows:
        raise SystemExit(
            f"ledger head count {head['count']} does not match {rows} signed rows"
        )
    if bytes.fromhex(head["final_hash"]) != final_hash:
        raise SystemExit("ledger head final hash does not match the last row")


def self_test():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import tempfile

    def stamp_chain(key, rows):
        prev = bytes(32)
        pub = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
        out = []
        for body in rows:
            digest = hashlib.sha256(prev + canonical(body)).digest()
            sig = key.sign(digest)
            row = dict(body)
            row["chain_prev"] = prev.hex()
            row["chain_hash"] = digest.hex()
            row["chain_sig"] = base64.b64encode(sig).decode()
            row["chain_key"] = pub
            out.append(row)
            prev = digest
        head_body = {"chain_key": pub, "count": len(out), "final_hash": prev.hex()}
        head = dict(head_body)
        head["sig"] = base64.b64encode(key.sign(canonical(head_body))).decode()
        return out, head

    key = Ed25519PrivateKey.generate()
    other = Ed25519PrivateKey.generate()
    good, head = stamp_chain(key, [{"n": 1}, {"n": 2}])
    directory = tempfile.mkdtemp()
    path = directory + "/ledger.ndjson"
    head_path = path + ".head"

    def write(rows, head_doc):
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        if head_doc is None:
            try:
                os_remove = __import__("os").remove
                os_remove(head_path)
            except OSError:
                pass
        else:
            with open(head_path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(head_doc))

    write(good, head)
    with open(path + ".trust", "w", encoding="utf-8") as handle:
        handle.write(good[0]["chain_key"])
    check(path)
    mutated = json.loads(json.dumps(good))
    mutated[1]["n"] = 9
    write(mutated, head)
    try:
        check(path)
    except SystemExit as exc:
        if "hash chain broken" not in str(exc):
            raise
    else:
        raise SystemExit("mutated row was accepted")
    foreign, _ = stamp_chain(other, [{"n": 9}])
    # Keep a non-zero previous link so the reject is the foreign key.
    foreign[0]["chain_prev"] = good[-1]["chain_hash"]
    write(good + foreign, head)
    try:
        check(path)
    except SystemExit as exc:
        if "chain key changed" not in str(exc):
            raise
    else:
        raise SystemExit("foreign key was accepted")
    zeroed = json.loads(json.dumps(good))
    zeroed[1]["chain_prev"] = "00" * 32
    write(zeroed, head)
    try:
        check(path)
    except SystemExit as exc:
        if "zero chain_prev" not in str(exc):
            raise
    else:
        raise SystemExit("zero chain_prev after genesis was accepted")
    write(good[:1], head)
    try:
        check(path)
    except SystemExit as exc:
        if "count" not in str(exc):
            raise
    else:
        raise SystemExit("truncated chain was accepted")
    attacker, attacker_head = stamp_chain(other, [{"attacker": 1}])
    write(attacker, attacker_head)
    try:
        check(path)
    except SystemExit as exc:
        if "not the trusted key" not in str(exc):
            raise
    else:
        raise SystemExit("attacker-only row was accepted")
    resigned, resigned_head = stamp_chain(other, [{"n": 1}, {"n": 2}])
    write(resigned, resigned_head)
    try:
        check(path)
    except SystemExit as exc:
        if "not the trusted key" not in str(exc):
            raise
    else:
        raise SystemExit("a ledger re-signed under a new key was accepted")
    print("ledger-self-test-ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        self_test()
    elif len(sys.argv) == 4 and sys.argv[1] == "--trust-b64":
        check(sys.argv[3])
    elif len(sys.argv) == 2:
        check(sys.argv[1])
    else:
        raise SystemExit("usage: verify_ledger.py [--trust-b64 KEY] <file.ndjson>")
