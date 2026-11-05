"""Packaged production public keys. Throwaway keys are generated inside the test."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from vantio_install.artifact_verify import (
    load_artifact_trust,
    packaged_artifact_path_override,
    packaged_artifact_trust,
    packaged_production_trust,
)
from vantio_install.bundle_fetch import verify_unpacked
from vantio_install.license_token import (
    BUILD_MODE,
    issue_token,
    keys_from_mapping,
    packaged_license_keys,
    usable_license_keys,
    verify_token,
)

PACKAGE = Path(__file__).resolve().parents[1]
TRUST = PACKAGE / "vantio_install" / "trust"
LICENSE_PATH = TRUST / "license-public-keys.json"
ARTIFACT_PATH = TRUST / "artifact-public-keys.json"
LICENSE_KID = "lic-live-2026-10"
ARTIFACT_KEY_ID = "prod-artifact-2026-11"
LICENSE_RAW_SHA256 = "9ddf4480807c44e963864dafaace202755c21af2acdd6a1f2a887457f69531c5"
ARTIFACT_RAW_SHA256 = "aea8a06fe3dfd090e3c35e5a4dee6015e5e283ac7b66caf6f14a58f91ae724e4"
NOW = 1_800_000_000


def _public(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _payload(**overrides: object) -> dict:
    body = {
        "v": 1,
        "kid": LICENSE_KID,
        "sku": "phantom-engine",
        "cus": "cus_lab",
        "sub": "sub_lab",
        "qty": 1,
        "interval": "month",
        "iat": 1_700_000_000,
        "exp": 4_000_000_000,
        "mode": "live",
    }
    body.update(overrides)
    return body


def _license_entry(private: Ed25519PrivateKey, kid: str, mode: str) -> dict:
    return {"kid": kid, "alg": "Ed25519", "mode": mode, "public_key_b64": _b64(_public(private))}


def _load_license() -> dict:
    return json.loads(LICENSE_PATH.read_text(encoding="utf-8"))


class LicenseTrustTests(unittest.TestCase):
    def test_live_build_has_one_key_and_a_test_build_has_none(self) -> None:
        document = _load_license()
        self.assertEqual(document["schema"], 2)
        self.assertEqual(document["build_mode"], "live")
        self.assertEqual(document["revoked_kids"], [])
        self.assertEqual(BUILD_MODE, "live")
        live = usable_license_keys("live")
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["kid"], LICENSE_KID)
        self.assertEqual(live[0]["mode"], "live")
        self.assertEqual(len(live[0]["public_key"]), 32)
        self.assertEqual(hashlib.sha256(live[0]["public_key"]).hexdigest(), LICENSE_RAW_SHA256)
        self.assertEqual(packaged_license_keys(), live)
        self.assertEqual(usable_license_keys("test"), ())
        self.assertNotIn("PRIVATE", LICENSE_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("-----BEGIN", LICENSE_PATH.read_text(encoding="utf-8"))

    def test_test_signed_token_and_throwaway_signature_are_refused(self) -> None:
        private = Ed25519PrivateKey.generate()
        test_token = issue_token(_payload(kid="lic-test-2026-10", mode="test"), private)
        refused = verify_token(test_token, now=NOW)
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["reason"], "UNKNOWN_KID")
        unconfigured = verify_token(test_token, keys=usable_license_keys("test"), now=NOW)
        self.assertEqual(unconfigured["reason"], "TRUST_NOT_CONFIGURED")
        throwaway = issue_token(_payload(), private)
        bad = verify_token(throwaway, now=NOW)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["reason"], "BAD_SIGNATURE")
        self.assertIsNone(bad["payload"])

    def test_malformed_entries_empty_the_set(self) -> None:
        base = _load_license()
        extra = _license_entry(Ed25519PrivateKey.generate(), "lic-live-2099-01", "live")
        cases = []
        schema = copy.deepcopy(base)
        schema["schema"] = 1
        cases.append(schema)
        missing = copy.deepcopy(base)
        del missing["schema"]
        cases.append(missing)
        placeholder = copy.deepcopy(base)
        placeholder["keys"][0]["public_key_b64"] = "not-a-public-key"
        cases.append(placeholder)
        broken = copy.deepcopy(base)
        broken["keys"].append(dict(extra, public_key_b64="AAAA"))
        cases.append(broken)
        duplicate = copy.deepcopy(base)
        duplicate["keys"].append(dict(base["keys"][0]))
        cases.append(duplicate)
        mixed = copy.deepcopy(base)
        mixed["keys"].append(_license_entry(Ed25519PrivateKey.generate(), "lic-test-2099-01", "test"))
        cases.append(mixed)
        prefix = copy.deepcopy(base)
        prefix["keys"][0]["kid"] = "lic-test-2026-10"
        cases.append(prefix)
        mode = copy.deepcopy(base)
        mode["build_mode"] = "test"
        cases.append(mode)
        revoked = copy.deepcopy(base)
        revoked["revoked_kids"] = LICENSE_KID
        cases.append(revoked)
        repeated = copy.deepcopy(base)
        repeated["revoked_kids"] = ["lic-live-2099-01", "lic-live-2099-01"]
        cases.append(repeated)
        for case in cases:
            self.assertEqual(keys_from_mapping(case), ())
            self.assertEqual(usable_license_keys("live", case), ())
            self.assertEqual(usable_license_keys("test", case), ())

    def test_revocation_drops_one_kid_and_a_changed_byte_misses_the_fingerprint(self) -> None:
        document = _load_license()
        kept = _license_entry(Ed25519PrivateKey.generate(), "lic-live-2099-01", "live")
        document["keys"].append(kept)
        document["revoked_kids"] = [LICENSE_KID]
        loaded = keys_from_mapping(document)
        self.assertEqual([item["kid"] for item in loaded], ["lic-live-2099-01"])
        self.assertEqual(usable_license_keys("test", document), ())
        flipped = _load_license()
        raw = bytearray(base64.b64decode(flipped["keys"][0]["public_key_b64"], validate=True))
        raw[0] ^= 0x01
        flipped["keys"][0]["public_key_b64"] = _b64(bytes(raw))
        mutated = keys_from_mapping(flipped)
        self.assertEqual(len(mutated), 1)
        self.assertNotEqual(hashlib.sha256(mutated[0]["public_key"]).hexdigest(), LICENSE_RAW_SHA256)


class ArtifactTrustTests(unittest.TestCase):
    def test_packaged_production_key_is_not_a_test_key(self) -> None:
        keys = packaged_production_trust()
        self.assertEqual(set(keys), {ARTIFACT_KEY_ID})
        self.assertEqual(len(keys[ARTIFACT_KEY_ID]), 32)
        self.assertEqual(hashlib.sha256(keys[ARTIFACT_KEY_ID]).hexdigest(), ARTIFACT_RAW_SHA256)
        self.assertEqual(packaged_artifact_trust(), {})
        self.assertEqual(load_artifact_trust(ARTIFACT_PATH), {})
        text = ARTIFACT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("PRIVATE", text)
        self.assertNotIn("-----BEGIN", text)
        document = json.loads(text)
        self.assertEqual(document["keys"][0]["key_id"], ARTIFACT_KEY_ID)
        self.assertEqual(document["keys"][0]["key_class"], "production")

    def test_throwaway_signature_is_refused(self) -> None:
        private = Ed25519PrivateKey.generate()
        pinned = packaged_production_trust()[ARTIFACT_KEY_ID]
        body = b"fixture\n"
        digest = hashlib.sha256(body).hexdigest()
        sums = f"{digest}  fixture.bin\n".encode("ascii")
        signature = bytearray(private.sign(sums))
        record = {
            "algorithm": "Ed25519",
            "key_id": ARTIFACT_KEY_ID,
            "key_class": "production",
            "public_key_b64": _b64(pinned),
            "signature_b64": _b64(bytes(signature)),
        }
        self.assertEqual(self._verify(body, sums, record), "SIGNATURE_INVALID")
        signature[0] ^= 0x01
        record["signature_b64"] = _b64(bytes(signature))
        self.assertEqual(self._verify(body, sums, record), "SIGNATURE_INVALID")
        record["key_id"] = "prod-artifact-throwaway"
        record["public_key_b64"] = _b64(_public(private))
        record["signature_b64"] = _b64(private.sign(sums))
        self.assertEqual(self._verify(body, sums, record), "UNTRUSTED_KEY")

    def test_changed_trust_byte_is_not_the_pinned_key(self) -> None:
        pinned = packaged_production_trust()[ARTIFACT_KEY_ID]
        mutated = bytearray(pinned)
        mutated[-1] ^= 0x01
        document = {
            "keys": [
                {
                    "key_id": ARTIFACT_KEY_ID,
                    "key_class": "production",
                    "alg": "Ed25519",
                    "public_key_b64": _b64(bytes(mutated)),
                }
            ]
        }
        body = b"fixture\n"
        digest = hashlib.sha256(body).hexdigest()
        sums = f"{digest}  fixture.bin\n".encode("ascii")
        record = {
            "algorithm": "Ed25519",
            "key_id": ARTIFACT_KEY_ID,
            "key_class": "production",
            "public_key_b64": _b64(pinned),
            "signature_b64": _b64(Ed25519PrivateKey.generate().sign(sums)),
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trust.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with packaged_artifact_path_override(path):
                loaded = packaged_production_trust()
                self.assertNotEqual(loaded[ARTIFACT_KEY_ID], pinned)
                self.assertNotEqual(hashlib.sha256(loaded[ARTIFACT_KEY_ID]).hexdigest(), ARTIFACT_RAW_SHA256)
                reason = self._verify(body, sums, record)
        self.assertEqual(reason, "UNTRUSTED_KEY")

    def _verify(self, body: bytes, sums: bytes, record: dict) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / "fixture.bin").write_bytes(body)
            (tree / "SHA256SUMS").write_bytes(sums)
            (tree / "SHA256SUMS.sig").write_text(json.dumps(record), encoding="utf-8")
            result = verify_unpacked(tree, production=True)
        self.assertIn("reason", result)
        return str(result["reason"])
