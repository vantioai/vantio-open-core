"""Adversarial installer inputs. A local server stands in for a network attacker."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tests.dev_policy import ephemeral_dev_key, signed_envelope
from tests.factory import default_files, host, pins_for, write_bundle
from tests.test_one_command import _signature
from vantio_install import constants
from vantio_install.artifact_verify import artifact_trust_override, fetch_to_file, verify_archive_file
from vantio_install.cli import main
from vantio_install.signed_policy import dev_trust

TX = "vantio-tx-33333333-3333-4333-8333-333333333333"


class _Attack(BaseHTTPRequestHandler):
    body = b"attacker-bytes-not-the-archive\n"

    def do_GET(self) -> None:  # noqa: N802
        payload = type(self).body
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        return


class AdversarialInstallTests(unittest.TestCase):
    def test_substituted_archive_is_corrupt(self) -> None:
        private = Ed25519PrivateKey.generate()
        payload = b"pe-archive-fixture\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "archive.bin"
            path.write_bytes(payload)
            record = _signature(payload, "archive.bin", private)
            path.write_bytes(b"substituted-archive\n")
            result = verify_archive_file(
                path,
                record,
                trust_keys={record["key_id"]: base64.b64decode(record["public_key_b64"])},
            )
        self.assertEqual(result["reason"], "CORRUPT_ARTIFACT")
        self.assertTrue(result["bytes_hashed_here"])
        self.assertNotEqual(result["disposition"], "VERIFIED")

    def test_self_nominated_key_is_not_verified(self) -> None:
        private = Ed25519PrivateKey.generate()
        payload = b"evil"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evil.bin"
            path.write_bytes(payload)
            record = _signature(payload, "evil.bin", private)
            result = verify_archive_file(path, record, trust_keys={})
        self.assertEqual(result["reason"], "UNTRUSTED_KEY")
        self.assertNotEqual(result["disposition"], "VERIFIED")

    def test_loopback_redirect_is_not_fetched(self) -> None:
        class _Redirect(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.2/elsewhere")
                self.end_headers()

            def log_message(self, fmt: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), _Redirect)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        port = server.server_address[1]
        with tempfile.TemporaryDirectory() as tmp:
            result = fetch_to_file(f"http://127.0.0.1:{port}/x", Path(tmp) / "out.bin")
        self.assertFalse(result["fetched"])
        self.assertNotEqual(result["disposition"], "FETCHED")
        self.assertEqual(result["reason"], "INTERRUPTED_DOWNLOAD")

    def test_local_mitm_does_not_replace_the_archive(self) -> None:
        private = Ed25519PrivateKey.generate()
        policy_private, policy_key = ephemeral_dev_key("dev-nonprod-mitm-policy")
        root = Path(tempfile.mkdtemp(prefix="vantio-mitm-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        files = default_files()
        original_pins = constants.FROZEN_PINS
        pins = pins_for(files)
        constants.FROZEN_PINS = pins
        self.addCleanup(lambda: setattr(constants, "FROZEN_PINS", original_pins))
        bundle = root / "bundle"
        write_bundle(bundle, pins, files)
        archive = bundle / "artifacts" / "phantom-engine" / pins["pe_archive_name"]
        before = archive.read_bytes()
        record = _signature(before, pins["pe_archive_name"], private)
        signature_path = root / "signature.json"
        signature_path.write_text(json.dumps(record), encoding="utf-8")
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
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Attack)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
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
        os.environ["VANTIO_INSTALL_ALLOW_LIVE"] = "1"
        self.addCleanup(lambda: os.environ.pop("VANTIO_INSTALL_ALLOW_LIVE", None))
        port = server.server_address[1]
        argv = [
            "install",
            "--bundle",
            str(bundle),
            "--config",
            str(config_path),
            "--state-dir",
            str(root / "state"),
            "--fixture-host",
            str(host_path),
            "--transaction-id",
            TX,
            "--json",
            "--yes",
            "--i-accept-live-mutations",
            "--signature-file",
            str(signature_path),
            "--policy-file",
            str(policy_path),
            "--artifact-url",
            f"http://127.0.0.1:{port}/archive.bin",
        ]
        pinned = {record["key_id"]: base64.b64decode(record["public_key_b64"])}
        with dev_trust((policy_key,)), artifact_trust_override(pinned):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(argv)
        body = json.loads(buf.getvalue())
        self.assertNotEqual(code, 0, body)
        self.assertEqual(body["reason"], "CORRUPT_ARTIFACT", body)
        self.assertEqual(archive.read_bytes(), before)
        self.assertEqual(hashlib.sha256(before).hexdigest(), hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertFalse((root / "prefix").exists())


if __name__ == "__main__":
    unittest.main()
