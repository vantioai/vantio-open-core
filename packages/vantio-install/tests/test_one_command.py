"""One-command install. The public pin is not moved. Live gates stay required."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tests.dev_policy import ephemeral_dev_key, signed_envelope
from tests.factory import default_files, host, pins_for, write_bundle
from vantio_install import constants
from vantio_install.artifact_verify import canonical_descriptor, fetch_to_file, verify_archive_file
from vantio_install.cli import main
from vantio_install.signed_policy import dev_trust

PACKAGE = Path(__file__).resolve().parents[1]
PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
TX = "vantio-tx-22222222-2222-4222-8222-222222222222"


def _signature(payload: bytes, filename: str, private: Ed25519PrivateKey) -> dict:
    document = {"filename": filename, "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}
    raw_public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signature = private.sign(canonical_descriptor(document))
    return {
        "document": document,
        "key_class": "test_non_production",
        "key_id": "test-nonprod-artifact-install",
        "not_a_production_root": True,
        "public_key_b64": base64.b64encode(raw_public).decode("ascii"),
        "signature_b64": base64.b64encode(signature).decode("ascii"),
    }


class OneCommandTests(unittest.TestCase):
    def test_public_pin_source_is_unchanged(self) -> None:
        text = (PACKAGE / "vantio_install" / "constants.py").read_text(encoding="utf-8")
        self.assertIn(PIN, text)
        self.assertEqual(constants.FROZEN_PINS["pe_archive_sha256"], PIN)

    def test_signature_hashes_the_file_and_refuses_a_production_key(self) -> None:
        private = Ed25519PrivateKey.generate()
        payload = b"pe-archive-fixture\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "archive.bin"
            path.write_bytes(payload)
            record = _signature(payload, "archive.bin", private)
            verified = verify_archive_file(
                path,
                record,
                trust_keys={record["key_id"]: base64.b64decode(record["public_key_b64"])},
            )
            self.assertEqual(verified["disposition"], "VERIFIED")
            self.assertTrue(verified["bytes_hashed_here"])
            self.assertFalse(verified["public_pin_moved"])
            path.write_bytes(b"tampered")
            corrupt = verify_archive_file(
                path,
                record,
                trust_keys={record["key_id"]: base64.b64decode(record["public_key_b64"])},
            )
            self.assertEqual(corrupt["reason"], "CORRUPT_ARTIFACT")
            record["not_a_production_root"] = False
            path.write_bytes(payload)
            refused = verify_archive_file(path, record, trust_keys={})
            self.assertEqual(refused["reason"], "PRODUCTION_KEY_REFUSED")
            phantom = fetch_to_file("http://phantom-box.example/archive", Path(tmp) / "out.bin")
            self.assertEqual(phantom["reason"], "PHANTOM_BOX_REFUSED")
            self.assertFalse(phantom["fetched"])

    def test_install_requires_both_gates_and_can_reach_observe_healthy(self) -> None:
        private = Ed25519PrivateKey.generate()
        root = Path(tempfile.mkdtemp(prefix="vantio-one-command-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        files = default_files()
        original = constants.FROZEN_PINS
        pins = pins_for(files)
        constants.FROZEN_PINS = pins
        self.addCleanup(lambda: setattr(constants, "FROZEN_PINS", original))
        bundle = root / "bundle"
        write_bundle(bundle, pins, files)
        archive_name = pins["pe_archive_name"]
        archive = bundle / "artifacts" / "phantom-engine" / archive_name
        record = _signature(files["archive"], archive_name, private)
        signature_path = root / "signature.json"
        signature_path.write_text(json.dumps(record), encoding="utf-8")
        trust_path = root / "artifact-trust.json"
        trust_path.write_text(
            json.dumps(
                {
                    "keys": [
                        {
                            "key_class": "test_non_production",
                            "key_id": record["key_id"],
                            "not_a_production_root": True,
                            "public_key_b64": record["public_key_b64"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        policy_private, policy_key = ephemeral_dev_key("dev-nonprod-install-policy")
        policy_path = root / "policy.json"
        policy_path.write_text(
            json.dumps(
                signed_envelope(
                    {"enforcement": "NOT_ENABLED", "install_mode": "observe-only"},
                    policy_private,
                    policy_key,
                )
            ),
            encoding="utf-8",
        )
        host_path = root / "host.json"
        host_path.write_text(json.dumps(host()), encoding="utf-8")
        workload = root / "workload"
        workload.mkdir()
        config = {
            "install_mode": "observe-only",
            "enforcement": "NOT_ENABLED",
            "iface": "ens5",
            "workload_roots": [str(workload)],
            "evidence_root": str(root / "evidence"),
            "dry_run": True,
            "otlp": "DISABLED",
            "path_deny": "disabled",
            "traffic_control": "audit-only",
            "transfer_required": False,
            "transfer_source_cidrs": [],
            "artifact_source": "sealed_archive",
            "install_motion": "customer-local",
            "enterprise_inclusion": "OPTIONAL_SOURCE_ONLY_NOT_PACKAGED_AUTHORITY",
            "non_interactive": True,
            "stage_dir": str(root / "stage"),
            "prefix": str(root / "prefix"),
        }
        config_path = root / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        state = root / "state"
        argv = [
            "install",
            "--bundle",
            str(bundle),
            "--config",
            str(config_path),
            "--state-dir",
            str(state),
            "--evidence-dir",
            str(root / "evidence"),
            "--fixture-host",
            str(host_path),
            "--transaction-id",
            TX,
            "--json",
            "--signature-file",
            str(signature_path),
            "--artifact-trust",
            str(trust_path),
            "--policy-file",
            str(policy_path),
            "--yes",
        ]
        os.environ.pop("VANTIO_INSTALL_ALLOW_LIVE", None)
        with dev_trust((policy_key,)):
            code, body = _run(argv)
            self.assertEqual(body["reason"], "LIVE_GATES_REQUIRED", body)
            self.assertNotEqual(code, 0)
            self.assertFalse((root / "prefix").exists())
            self.assertFalse(body["live_gates_replaced"])
            self.assertFalse(body["protected_entered"])
            protected = argv + ["--requested-protection", "PROTECTED"]
            code, body = _run(protected)
            self.assertEqual(body["reason"], "ENFORCEMENT_HELD", body)
            self.assertFalse((root / "prefix").exists())
            os.environ["VANTIO_INSTALL_ALLOW_LIVE"] = "1"
            self.addCleanup(lambda: os.environ.pop("VANTIO_INSTALL_ALLOW_LIVE", None))
            code, body = _run(argv + ["--i-accept-live-mutations"])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "HEALTHY", body)
        self.assertEqual(body["protection_state"], "OBSERVE")
        self.assertEqual(body["enforcement"], "NOT_ENABLED")
        self.assertEqual(body["proof_state"], "NOT_PROVED")
        self.assertFalse(body["public_pin_moved"])
        self.assertTrue(body["bytes_hashed_here"])


def _run(argv: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, json.loads(buf.getvalue())
