"""Live license slot. Keys in this file are generated in memory and are not stored."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from vantio_install.license_token import (
    issue_token,
    keys_from_mapping,
    license_trust_override,
    packaged_license_keys,
    verify_token,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-license-trust.py"
TRUST = ROOT / "vantio_install" / "trust" / "license-public-keys.json"
LOADER = ROOT / "vantio_install" / "license_token.py"
NOW = 1_800_000_000
LIVE_KID = "lic-live-2026-10"
PLACEHOLDER = {
    "keys": [
        {
            "kid": LIVE_KID,
            "alg": "Ed25519",
            "public_key_b64": "",
            "mode": "live",
            "placeholder": True,
        }
    ]
}


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_license_trust", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _public(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _standard(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _row(private: Ed25519PrivateKey, *, kid: str = LIVE_KID, mode: str = "live") -> dict:
    return {"kid": kid, "alg": "Ed25519", "public_key_b64": _standard(_public(private)), "mode": mode}


def _payload(**overrides: object) -> dict:
    body = {
        "v": 1,
        "kid": LIVE_KID,
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


def _key_with_url_alphabet() -> Ed25519PrivateKey:
    private = Ed25519PrivateKey.generate()
    for _ in range(64):
        encoded = _standard(_public(private))
        if "+" in encoded or "/" in encoded:
            return private
        private = Ed25519PrivateKey.generate()
    raise RuntimeError("encoding stayed inside the shared alphabet")


def _run(args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


class LoaderTests(unittest.TestCase):
    def test_packaged_placeholder_is_rejected(self) -> None:
        payload = json.loads(TRUST.read_text(encoding="utf-8"))
        self.assertEqual(payload, PLACEHOLDER)
        self.assertEqual(packaged_license_keys(), ())
        private = Ed25519PrivateKey.generate()
        token = issue_token(_payload(), private)
        self.assertEqual(verify_token(token, now=NOW)["reason"], "UNKNOWN_KID")

    def test_placeholder_mark_rejects_a_32_byte_key(self) -> None:
        private = Ed25519PrivateKey.generate()
        row = _row(private)
        self.assertEqual(len(keys_from_mapping({"keys": [row]})), 1)
        marked = dict(row)
        marked["placeholder"] = True
        self.assertEqual(keys_from_mapping({"keys": [marked]}), ())
        cleared = dict(row)
        cleared["placeholder"] = False
        self.assertEqual(keys_from_mapping({"keys": [cleared]}), ())
        with self.assertRaises(ValueError):
            with license_trust_override((marked,)):
                pass

    def test_generated_key_verifies_live_kid(self) -> None:
        private = Ed25519PrivateKey.generate()
        token = issue_token(_payload(), private)
        with license_trust_override((_row(private),)):
            verified = verify_token(token, now=NOW)
        self.assertTrue(verified["ok"], verified["reason"])
        self.assertEqual(verified["reason"], "VERIFIED")
        self.assertEqual(verified["payload"]["kid"], LIVE_KID)
        self.assertEqual(verified["payload"]["mode"], "live")

    def test_tampered_token_is_rejected(self) -> None:
        private = Ed25519PrivateKey.generate()
        token = issue_token(_payload(), private)
        tampered = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
        self.assertNotEqual(tampered, token)
        with license_trust_override((_row(private),)):
            refused = verify_token(tampered, now=NOW)
        self.assertEqual(refused["reason"], "BAD_SIGNATURE")
        self.assertFalse(refused["ok"])

    def test_wrong_kid_is_unknown(self) -> None:
        private = Ed25519PrivateKey.generate()
        token = issue_token(_payload(kid="lic-other-2026-10"), private)
        with license_trust_override((_row(private),)):
            refused = verify_token(token, now=NOW)
        self.assertEqual(refused["reason"], "UNKNOWN_KID")

    def test_expired_token_is_rejected(self) -> None:
        private = Ed25519PrivateKey.generate()
        token = issue_token(_payload(exp=10), private)
        with license_trust_override((_row(private),)):
            refused = verify_token(token, now=10)
        self.assertEqual(refused["reason"], "EXPIRED")
        self.assertEqual(refused["exp"], 10)

    def test_base64url_public_key_is_rejected(self) -> None:
        private = _key_with_url_alphabet()
        standard = _row(private)
        url = dict(standard)
        url["public_key_b64"] = base64.urlsafe_b64encode(_public(private)).decode("ascii").rstrip("=")
        self.assertNotEqual(url["public_key_b64"], standard["public_key_b64"])
        self.assertTrue(set("-_") & set(url["public_key_b64"]))
        self.assertEqual(keys_from_mapping({"keys": [url]}), ())
        stripped = dict(standard)
        stripped["public_key_b64"] = standard["public_key_b64"].rstrip("=")
        self.assertEqual(keys_from_mapping({"keys": [stripped]}), ())
        self.assertEqual(len(keys_from_mapping({"keys": [standard]})), 1)
        with self.assertRaises(ValueError):
            with license_trust_override((url,)):
                pass
        token = issue_token(_payload(), private)
        with license_trust_override((standard,)):
            self.assertEqual(verify_token(token, now=NOW)["reason"], "VERIFIED")

    def test_duplicate_live_kid_fails_closed(self) -> None:
        first = Ed25519PrivateKey.generate()
        second = Ed25519PrivateKey.generate()
        token = issue_token(_payload(), first)
        with license_trust_override((_row(first),)):
            self.assertEqual(verify_token(token, now=NOW)["reason"], "VERIFIED")
        with license_trust_override((_row(first), _row(second))):
            self.assertEqual(verify_token(token, now=NOW)["reason"], "DUPLICATE_KID")
        with license_trust_override((_row(second), _row(first))):
            self.assertEqual(verify_token(token, now=NOW)["reason"], "DUPLICATE_KID")
        with license_trust_override((_row(first), _row(first))):
            self.assertEqual(verify_token(token, now=NOW)["reason"], "DUPLICATE_KID")

    def test_sixty_four_byte_value_is_not_trusted(self) -> None:
        row = {
            "kid": LIVE_KID,
            "alg": "Ed25519",
            "mode": "live",
            "public_key_b64": base64.b64encode(os.urandom(64)).decode("ascii"),
        }
        self.assertEqual(len(base64.b64decode(row["public_key_b64"], validate=True)), 64)
        self.assertEqual(keys_from_mapping({"keys": [row]}), ())

    def test_loader_has_no_env_or_url_trust(self) -> None:
        text = LOADER.read_text(encoding="utf-8")
        self.assertNotIn("os.environ", text)
        self.assertNotIn("getenv", text)
        self.assertNotIn("urlopen", text)


class CheckerTests(unittest.TestCase):
    def test_checker_reads_the_packaged_file_and_rejects_it(self) -> None:
        self.assertEqual(CHECKER._DEFAULT, TRUST)
        proc = _run([])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "FAIL\n")
        self.assertIn("placeholder row is not a trusted key", proc.stderr)
        self.assertIn("public_key_b64 must be standard padded base64 of 32 bytes", proc.stderr)

    def test_valid_row_passes_and_mutations_fail(self) -> None:
        private = _key_with_url_alphabet()
        public_b64 = _row(private)["public_key_b64"]
        other = _row(Ed25519PrivateKey.generate())
        wide = base64.b64encode(os.urandom(64)).decode("ascii")
        pem = "-----BEGIN PRIVATE KEY-----\nnot-a-key\n-----END PRIVATE KEY-----"

        def document(row: dict, extra: list[dict] | None = None) -> str:
            return json.dumps({"keys": [row, *(extra or [])]})

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-public-keys.json"
            path.write_text(document(_row(private)), encoding="utf-8")
            passed = _run([str(path)])
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual(passed.stdout, "PASS\n")
            self.assertNotIn(public_b64, passed.stdout)
            self.assertEqual(passed.stderr, "")

            def expect_fail(text: str, reason: str) -> None:
                path.write_text(text, encoding="utf-8")
                failed = _run([str(path)])
                self.assertEqual(failed.returncode, 1, failed.stderr)
                self.assertEqual(failed.stdout, "FAIL\n")
                self.assertIn(reason, failed.stderr)
                self.assertNotIn(public_b64, failed.stdout)
                self.assertNotIn(public_b64, failed.stderr)
                self.assertNotIn(other["public_key_b64"], failed.stdout + failed.stderr)
                self.assertNotIn(wide, failed.stdout + failed.stderr)
                self.assertNotIn(pem, failed.stdout + failed.stderr)

            marked = _row(private)
            marked["placeholder"] = True
            expect_fail(document(marked), "placeholder row is not a trusted key")
            url_row = _row(private)
            url_row["public_key_b64"] = base64.urlsafe_b64encode(_public(private)).decode("ascii").rstrip("=")
            expect_fail(document(url_row), "public_key_b64 must be standard padded base64 of 32 bytes")
            unpadded = _row(private)
            unpadded["public_key_b64"] = public_b64.rstrip("=")
            expect_fail(document(unpadded), "public_key_b64 must be standard padded base64 of 32 bytes")
            alg = _row(private)
            alg["alg"] = "Ed25519x"
            expect_fail(document(alg), "live alg must be Ed25519")
            mode = _row(private)
            mode["mode"] = "test"
            expect_fail(document(mode), "expected exactly one live row")
            kid = _row(private)
            kid["kid"] = "lic-test-2026-10"
            expect_fail(document(kid), "live kid must be lic-live-2026-10")
            wide_row = _row(private)
            wide_row["public_key_b64"] = wide
            expect_fail(document(wide_row), "private-key material")
            pem_row = _row(private)
            pem_row["public_key_b64"] = pem
            expect_fail(document(pem_row), "private-key material")
            expect_fail(document(_row(private), [_row(private)]), "duplicate kid")
            expect_fail(document(_row(private), [other]), "expected exactly one live row")

    def test_env_and_url_do_not_supply_a_key(self) -> None:
        private = Ed25519PrivateKey.generate()
        public_b64 = _row(private)["public_key_b64"]
        decoy = json.dumps({"keys": [_row(private)]})
        proc = _run([], {"VANTIO_LICENSE_PUBLIC_KEYS": decoy})
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "FAIL\n")
        self.assertNotIn(public_b64, proc.stdout)
        self.assertNotIn(public_b64, proc.stderr)
        url = _run(["https://vantio.ai/api/pe/license-keys"])
        self.assertEqual(url.returncode, 1)
        self.assertEqual(url.stdout, "FAIL\n")
        self.assertIn("usage:", url.stderr)
        flagged = _run(["--trust", str(TRUST)])
        self.assertEqual(flagged.returncode, 1)
        self.assertEqual(flagged.stdout, "FAIL\n")
        self.assertIn("usage:", flagged.stderr)
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("urllib", text)
        self.assertNotIn("requests", text)
        self.assertNotIn("os.environ", text)
        self.assertNotIn("getenv", text)
