"""Assemble, sign, and verify a stranger-host evidence bundle.

AWAITING_OUTSIDE_REVIEW verifies only with the pinned TEST trust document.
Fixture signatures keep host_proof false.
"""

from __future__ import annotations

import base64
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from constants import (
    BASE_SHA,
    BUNDLE_FILES,
    CLAIM_AWAITING,
    CLAIM_FIXTURE,
    FORBIDDEN_JSON_FIELDS,
    LABEL,
    MAX_BYTES,
    PRIVATE_KEY_RE,
    REFUSED_CLAIMS,
    SCHEMA,
    TIER,
    TOKEN_PREFIXES,
    TRUST_KEY_ID,
    TRUST_MEMBER,
    TRUST_SHA256,
)
from errors import PackageError
from grade import grade_evidence


def dump(body: object) -> str:
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def canonical(document: Mapping[str, object]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _scan_bytes(blob: bytes, *, tokens: bool = True) -> None:
    if len(blob) > MAX_BYTES:
        raise PackageError("secret_scan")
    if PRIVATE_KEY_RE.search(blob):
        raise PackageError("private_key_in_bundle")
    if not tokens:
        return
    for prefix in TOKEN_PREFIXES:
        if prefix in blob:
            raise PackageError("secret_scan")


def _scan_json(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_JSON_FIELDS:
                raise PackageError("secret_scan")
            _scan_json(item)
        return
    if isinstance(value, list):
        for item in value:
            _scan_json(item)


def scan_tree(directory: Path) -> None:
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        blob = path.read_bytes()
        _scan_bytes(blob, tokens=path.name != "SIGNATURE.json")
        if path.suffix == ".json" and path.name != "SIGNATURE.json":
            try:
                parsed = json.loads(blob.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise PackageError("secret_scan") from exc
            _scan_json(parsed)


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def load_trust_bytes(path: Path) -> bytes:
    if tarfile.is_tarfile(path):
        try:
            with tarfile.open(path, "r:*") as tar:
                member = tar.getmember(TRUST_MEMBER)
                if not member.isfile() or member.size <= 0 or member.size > MAX_BYTES:
                    raise PackageError("trust_not_test")
                if member.name != TRUST_MEMBER or ".." in member.name.split("/"):
                    raise PackageError("trust_not_test")
                handle = tar.extractfile(member)
                if handle is None:
                    raise PackageError("trust_not_test")
                blob = handle.read(MAX_BYTES + 1)
        except (tarfile.TarError, KeyError, OSError) as exc:
            raise PackageError("trust_not_test") from exc
    else:
        try:
            blob = path.read_bytes()
        except OSError as exc:
            raise PackageError("trust_not_test") from exc
    if len(blob) > MAX_BYTES:
        raise PackageError("trust_not_test")
    _scan_bytes(blob, tokens=False)
    return blob


def trust_key(blob: bytes) -> dict[str, object]:
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError("trust_not_test") from exc
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list) or len(keys) != 1 or not isinstance(keys[0], dict):
        raise PackageError("trust_not_test")
    key = keys[0]
    if key.get("key_id") != TRUST_KEY_ID:
        raise PackageError("trust_not_test")
    if key.get("environment") != "NON-PRODUCTION" or key.get("label") != "TEST":
        raise PackageError("trust_not_test")
    if key.get("not_a_production_root") is not True:
        raise PackageError("trust_not_test")
    public = key.get("public_key_b64")
    if not isinstance(public, str) or not public:
        raise PackageError("trust_not_test")
    return key


def _load_private(path: Path) -> Ed25519PrivateKey:
    try:
        blob = path.read_bytes()
    except OSError as exc:
        raise PackageError("trust_not_test") from exc
    if len(blob) > MAX_BYTES:
        raise PackageError("trust_not_test")
    try:
        loaded = load_pem_private_key(blob, password=None)
    except (ValueError, TypeError) as exc:
        raise PackageError("trust_not_test") from exc
    if not isinstance(loaded, Ed25519PrivateKey):
        raise PackageError("trust_not_test")
    return loaded


def _public_matches(key: Mapping[str, object], private: Ed25519PrivateKey) -> bool:
    try:
        raw = base64.b64decode(str(key["public_key_b64"]), validate=True)
    except (ValueError, KeyError) as exc:
        raise PackageError("trust_not_test") from exc
    return private.public_key().public_bytes_raw() == raw


def file_hashes(directory: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in BUNDLE_FILES:
        path = directory / name
        if not path.is_file():
            raise PackageError("signature_invalid")
        blob = path.read_bytes()
        if len(blob) > MAX_BYTES:
            raise PackageError("secret_scan")
        rows.append({"path": name, "sha256": sha256_bytes(blob)})
    return rows


def write_sums(directory: Path, rows: list[dict[str, str]]) -> None:
    lines = [f"{item['sha256']}  {item['path']}" for item in rows]
    (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def signed_document(claim: str, rows: list[dict[str, str]]) -> dict[str, object]:
    return {
        "claim_cap": claim,
        "files": rows,
        "key_id": TRUST_KEY_ID,
        "schema": SCHEMA,
    }


def _manifest(claim: str, created_utc: str) -> dict[str, object]:
    return {
        "base_sha": BASE_SHA,
        "claim_cap": claim,
        "created_utc": created_utc,
        "label": LABEL,
        "production_root": False,
        "public_pin_moved": False,
        "schema": SCHEMA,
        "tier": TIER,
    }


def _load_json(path: Path) -> object:
    blob = path.read_bytes()
    _scan_bytes(blob)
    try:
        parsed = json.loads(blob.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError("secret_scan") from exc
    _scan_json(parsed)
    return parsed


def assemble(
    directory: Path,
    *,
    host: object,
    seal: object,
    enterprise: object,
    descendant_pre: object,
    boot: object,
    serial_text: str,
    descendant_post: object,
    uninstall: object,
    teardown: object,
    claim: str,
    created_utc: str,
) -> dict[str, object]:
    if claim not in {CLAIM_FIXTURE, CLAIM_AWAITING}:
        raise PackageError("claim_refused")
    if directory.exists() and any(directory.iterdir()):
        raise PackageError("signature_invalid")
    directory.mkdir(parents=True, exist_ok=True)
    serial = serial_text if isinstance(serial_text, str) else ""
    boot_body = dict(boot) if isinstance(boot, Mapping) else {}
    embedded = boot_body.get("serial_log")
    if not serial and isinstance(embedded, str):
        serial = embedded
    boot_public = {key: value for key, value in boot_body.items() if key != "serial_log"}
    if isinstance(serial, str):
        encoded = serial.encode("utf-8")
        boot_public["serial_sha256"] = sha256_bytes(encoded)
        boot_public["serial_bytes"] = len(encoded)
    members: dict[str, object] = {
        "host-record.json": host,
        "seal.json": seal,
        "rows-enterprise.json": enterprise,
        "rows-descendant-pre.json": descendant_pre,
        "boot-evidence.json": boot_public,
        "rows-descendant-post.json": descendant_post,
        "uninstall.json": uninstall,
        "teardown.json": teardown,
    }
    for name, body in members.items():
        _scan_json(body)
        text = dump(body)
        _scan_bytes(text.encode("utf-8"))
        (directory / name).write_text(text, encoding="utf-8")
    serial_bytes = serial.encode("utf-8")
    _scan_bytes(serial_bytes)
    (directory / "serial.log").write_text(serial, encoding="utf-8")
    (directory / "secret-scan.txt").write_text("SECRET_SCAN_CLEAN\n", encoding="utf-8")
    (directory / "MANIFEST.json").write_text(dump(_manifest(claim, created_utc)), encoding="utf-8")
    graded = grade_evidence(
        host=host,
        seal=seal,
        enterprise=enterprise,
        descendant_pre=descendant_pre,
        boot=boot_public,
        descendant_post=descendant_post,
        uninstall=uninstall,
        teardown=teardown,
        serial_text=serial,
    )
    (directory / "grade.json").write_text(dump(graded), encoding="utf-8")
    scan_tree(directory)
    write_sums(directory, file_hashes(directory))
    return graded


def sign_bundle(directory: Path, private_path: Path, trust_path: Path, *, claim: str) -> None:
    if claim not in {CLAIM_FIXTURE, CLAIM_AWAITING}:
        raise PackageError("claim_refused")
    if _inside(private_path, directory):
        raise PackageError("private_key_in_bundle")
    trust_blob = load_trust_bytes(trust_path)
    digest = sha256_bytes(trust_blob)
    key = trust_key(trust_blob)
    if claim == CLAIM_AWAITING and digest != TRUST_SHA256:
        raise PackageError("trust_hash")
    if claim == CLAIM_FIXTURE and digest == TRUST_SHA256:
        raise PackageError("trust_hash")
    private = _load_private(private_path)
    if not _public_matches(key, private):
        raise PackageError("trust_not_test")
    manifest_path = directory / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise PackageError("signature_invalid")
    manifest["claim_cap"] = claim
    manifest_path.write_text(dump(manifest), encoding="utf-8")
    rows = file_hashes(directory)
    document = signed_document(claim, rows)
    signature = private.sign(canonical(document))
    body = {
        "algorithm": "ed25519",
        "claim_cap": claim,
        "environment": "NON-PRODUCTION",
        "key_id": TRUST_KEY_ID,
        "label": "TEST",
        "not_a_production_root": True,
        "public_key_b64": key["public_key_b64"],
        "signature_b64": _b64(signature),
        "trust_document_b64": _b64(trust_blob),
        "trust_sha256": digest,
    }
    text = dump(body)
    _scan_bytes(text.encode("utf-8"))
    (directory / "SIGNATURE.json").write_text(text, encoding="utf-8")
    write_sums(directory, rows)
    scan_tree(directory)


def _read_signature(directory: Path) -> dict[str, object]:
    path = directory / "SIGNATURE.json"
    if not path.is_file():
        raise PackageError("signature_invalid")
    parsed = _load_json(path)
    if not isinstance(parsed, dict):
        raise PackageError("signature_invalid")
    return parsed


def verify_bundle(directory: Path) -> dict[str, object]:
    scan_tree(directory)
    signature = _read_signature(directory)
    claim = signature.get("claim_cap")
    if claim in REFUSED_CLAIMS or claim not in {CLAIM_FIXTURE, CLAIM_AWAITING}:
        raise PackageError("claim_refused")
    if signature.get("key_id") != TRUST_KEY_ID or signature.get("environment") != "NON-PRODUCTION":
        raise PackageError("trust_not_test")
    if signature.get("label") != "TEST" or signature.get("not_a_production_root") is not True:
        raise PackageError("trust_not_test")
    trust_b64 = signature.get("trust_document_b64")
    if not isinstance(trust_b64, str):
        raise PackageError("trust_not_test")
    try:
        trust_blob = base64.b64decode(trust_b64, validate=True)
    except ValueError as exc:
        raise PackageError("trust_not_test") from exc
    digest = sha256_bytes(trust_blob)
    if signature.get("trust_sha256") != digest:
        raise PackageError("trust_hash")
    if claim == CLAIM_AWAITING and digest != TRUST_SHA256:
        raise PackageError("trust_hash")
    if claim == CLAIM_FIXTURE and digest == TRUST_SHA256:
        raise PackageError("trust_hash")
    key = trust_key(trust_blob)
    if key.get("public_key_b64") != signature.get("public_key_b64"):
        raise PackageError("trust_not_test")
    rows = file_hashes(directory)
    document = signed_document(str(claim), rows)
    sums_path = directory / "SHA256SUMS"
    if not sums_path.is_file():
        raise PackageError("signature_invalid")
    expected_sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in rows)
    if sums_path.read_text(encoding="utf-8") != expected_sums:
        raise PackageError("signature_invalid")
    try:
        raw_sig = base64.b64decode(str(signature.get("signature_b64")), validate=True)
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(str(key["public_key_b64"]), validate=True))
        public.verify(raw_sig, canonical(document))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise PackageError("signature_invalid") from exc
    graded = _grade_directory(directory)
    stored = _load_json(directory / "grade.json")
    if stored != graded:
        raise PackageError("grade_mismatch")
    manifest = _load_json(directory / "MANIFEST.json")
    if not isinstance(manifest, dict) or manifest.get("claim_cap") != claim:
        raise PackageError("claim_refused")
    if manifest.get("label") != LABEL or manifest.get("tier") != TIER or manifest.get("public_pin_moved") is not False:
        raise PackageError("claim_refused")
    host_proof = claim == CLAIM_AWAITING and graded["result"] == "PASS"
    return {
        "claim_cap": claim,
        "grade": graded,
        "host_proof": host_proof,
        "label": LABEL,
        "ok": True,
        "tier": TIER,
    }


def _grade_directory(directory: Path) -> dict[str, object]:
    def load(name: str) -> object:
        return _load_json(directory / name)

    serial = (directory / "serial.log").read_text(encoding="utf-8", errors="replace")
    return grade_evidence(
        host=load("host-record.json"),
        seal=load("seal.json"),
        enterprise=load("rows-enterprise.json"),
        descendant_pre=load("rows-descendant-pre.json"),
        boot=load("boot-evidence.json"),
        descendant_post=load("rows-descendant-post.json"),
        uninstall=load("uninstall.json"),
        teardown=load("teardown.json"),
        serial_text=serial,
    )
