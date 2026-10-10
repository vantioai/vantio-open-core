"""Lab-scoped trust reaches observe HEALTHY. Packaged trust stays empty."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tests.dev_policy import ephemeral_dev_key, signed_envelope
from tests.factory import default_files, host, pins_for, write_bundle
from vantio_install import constants
from vantio_install.artifact_verify import active_artifact_trust, canonical_descriptor, load_artifact_trust
from vantio_install.cli import main
import vantio_install.one_command as one_command
from vantio_install.signed_policy import active_dev_trust

ROOT = Path(__file__).resolve().parents[3]
STAGE_PATH = ROOT / "scripts" / "lab" / "stage_lab_trust.py"
PACKAGE = Path(__file__).resolve().parents[1]
PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
TX = "vantio-tx-22222222-2222-4222-8222-222222222222"


def _stage():
    spec = importlib.util.spec_from_file_location("stage_lab_trust", STAGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("stage")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(argv: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, json.loads(buf.getvalue())


class LabScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def test_packaged_trust_stays_empty_and_a_wrong_file_is_not_pinned(self) -> None:
        artifact = json.loads((PACKAGE / "vantio_install" / "trust" / "artifact-public-keys.json").read_text())
        dev = json.loads((PACKAGE / "vantio_install" / "trust" / "dev-public-keys.json").read_text())
        self.assertEqual(artifact, {"keys": []})
        self.assertEqual(dev, {"keys": []})
        self.assertEqual(constants.FROZEN_PINS["pe_archive_sha256"], PIN)
        stage = _stage()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrong = root / "wrong.bin"
            wrong.write_bytes(b"not-the-sealed-archive\n")
            dest = root / "placed.bin"
            self.assertFalse(stage.place_if_pin(wrong, dest, PIN))
            self.assertFalse(dest.exists())
            payload = b"lab-bytes\n"
            good = root / "good.bin"
            good.write_bytes(payload)
            self.assertTrue(stage.place_if_pin(good, dest, hashlib.sha256(payload).hexdigest()))
            self.assertEqual(dest.read_bytes(), payload)
            staged = root / "staged"
            (staged).mkdir()
            result = stage.stage(staged, root)
            self.assertFalse(result["archive_pin_match"])
            self.assertEqual(result["audience"], "LAB_NONPROD")
            trust = json.loads((staged / "lab-artifact-trust.json").read_text())
            self.assertTrue(trust["not_a_production_root"])
            self.assertTrue(trust["keys"][0]["key_id"].startswith("test-nonprod-artifact-lab-"))
            for path in staged.rglob("*"):
                if path.is_file():
                    self.assertNotIn(b"-----BEGIN ", path.read_bytes())
            self.assertEqual(
                json.loads((PACKAGE / "vantio_install" / "trust" / "artifact-public-keys.json").read_text()),
                {"keys": []},
            )

    def test_lab_scope_is_ignored_unless_the_environment_names_it(self) -> None:
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes_raw()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trust.json"
            path.write_text(
                json.dumps(
                    {
                        "audience": "LAB_NONPROD",
                        "keys": [
                            {
                                "key_class": "test_non_production",
                                "key_id": "test-nonprod-artifact-other",
                                "not_a_production_root": True,
                                "public_key_b64": base64.b64encode(public).decode("ascii"),
                            }
                        ],
                        "not_a_production_root": True,
                    }
                ),
                encoding="utf-8",
            )
            os.environ["VANTIO_LAB_SCOPE"] = "lab-nonprod"
            os.environ["VANTIO_LAB_ARTIFACT_TRUST"] = str(path)
            self.assertEqual(active_artifact_trust(), {})
            os.environ.pop("VANTIO_LAB_SCOPE")
            path.write_text(
                path.read_text().replace("test-nonprod-artifact-other", "test-nonprod-artifact-lab-other"),
                encoding="utf-8",
            )
            self.assertEqual(active_artifact_trust(), {})
            os.environ["VANTIO_LAB_SCOPE"] = "lab-nonprod"
            keys = active_artifact_trust()
            self.assertEqual(set(keys), {"test-nonprod-artifact-lab-other"})
            self.assertEqual(keys["test-nonprod-artifact-lab-other"], public)

    def test_lab_key_can_reach_observe_healthy_and_still_refuses_caller_trust(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="vantio-lab-scope-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        files = default_files()
        saved_pins = constants.FROZEN_PINS
        pins = pins_for(files)
        constants.FROZEN_PINS = pins
        self.addCleanup(lambda: setattr(constants, "FROZEN_PINS", saved_pins))
        bundle = root / "bundle"
        write_bundle(bundle, pins, files)
        archive_name = pins["pe_archive_name"]
        archive = bundle / "artifacts" / "phantom-engine" / archive_name
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes_raw()
        document = {
            "filename": archive_name,
            "sha256": hashlib.sha256(files["archive"]).hexdigest(),
            "size_bytes": len(files["archive"]),
        }
        signature = private.sign(canonical_descriptor(document))
        record = {
            "document": document,
            "key_class": "test_non_production",
            "key_id": "test-nonprod-artifact-lab-install",
            "not_a_production_root": True,
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "signature_b64": base64.b64encode(signature).decode("ascii"),
        }
        signature_path = root / "signature.json"
        signature_path.write_text(json.dumps(record), encoding="utf-8")
        artifact_trust = root / "lab-artifact-trust.json"
        artifact_trust.write_text(
            json.dumps(
                {
                    "audience": "LAB_NONPROD",
                    "keys": [
                        {
                            "key_class": "test_non_production",
                            "key_id": record["key_id"],
                            "not_a_production_root": True,
                            "public_key_b64": record["public_key_b64"],
                        }
                    ],
                    "not_a_production_root": True,
                }
            ),
            encoding="utf-8",
        )
        policy_private, policy_key = ephemeral_dev_key("dev-nonprod-lab-install")
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
        dev_trust_path = root / "lab-dev-trust.json"
        dev_trust_path.write_text(
            json.dumps(
                {
                    "audience": "LAB_NONPROD",
                    "keys": [
                        {
                            "key_class": "dev_non_production",
                            "key_id": policy_key.key_id,
                            "not_a_production_root": True,
                            "public_key_b64": base64.b64encode(policy_key.public_key).decode("ascii"),
                        }
                    ],
                    "not_a_production_root": True,
                }
            ),
            encoding="utf-8",
        )
        host_path = root / "host.json"
        host_path.write_text(json.dumps(host()), encoding="utf-8")
        workload = root / "workload"
        workload.mkdir()
        config = {
            "artifact_source": "sealed_archive",
            "dry_run": True,
            "enforcement": "NOT_ENABLED",
            "enterprise_inclusion": "OPTIONAL_SOURCE_ONLY_NOT_PACKAGED_AUTHORITY",
            "evidence_root": str(root / "evidence"),
            "iface": "ens5",
            "install_mode": "observe-only",
            "install_motion": "customer-local",
            "non_interactive": True,
            "otlp": "DISABLED",
            "path_deny": "disabled",
            "prefix": str(root / "prefix"),
            "stage_dir": str(root / "stage"),
            "traffic_control": "audit-only",
            "transfer_required": False,
            "transfer_source_cidrs": [],
            "workload_roots": [str(workload)],
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
            "--policy-file",
            str(policy_path),
            "--yes",
            "--i-accept-live-mutations",
        ]
        os.environ["VANTIO_LAB_ARTIFACT_TRUST"] = str(artifact_trust)
        os.environ["VANTIO_LAB_DEV_TRUST"] = str(dev_trust_path)
        os.environ["VANTIO_INSTALL_ALLOW_LIVE"] = "1"
        os.environ.pop("VANTIO_LAB_SCOPE", None)
        code, body = _run(argv)
        self.assertNotEqual(body.get("state"), "HEALTHY", body)
        self.assertIn(body.get("reason"), {"UNTRUSTED_DEV_KEY", "UNTRUSTED_KEY"})
        os.environ["VANTIO_LAB_SCOPE"] = "lab-nonprod"
        self.assertIn("test-nonprod-artifact-lab-install", active_artifact_trust())
        self.assertTrue(any(item.key_id == "dev-nonprod-lab-install" for item in active_dev_trust()))
        refused, refused_body = _run(argv + ["--artifact-trust", str(artifact_trust)])
        self.assertEqual(refused_body["reason"], "CALLER_TRUST_REFUSED", refused_body)
        del refused
        saved_apply = one_command.apply
        seen: dict[str, object] = {}

        def wrapped(ctx):
            seen["plan_sha256"] = ctx.get("plan_sha256")
            plan_path = ctx.get("plan_path")
            self.assertIsInstance(plan_path, Path)
            assert isinstance(plan_path, Path)
            self.assertEqual(seen["plan_sha256"], hashlib.sha256(plan_path.read_bytes()).hexdigest())
            return saved_apply(ctx)

        one_command.apply = wrapped
        self.addCleanup(lambda: setattr(one_command, "apply", saved_apply))
        code, body = _run(argv)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "HEALTHY", body)
        self.assertEqual(body["protection_state"], "OBSERVE")
        self.assertEqual(body["enforcement"], "NOT_ENABLED")
        self.assertFalse(body["protected_entered"])
        self.assertFalse(body["public_pin_moved"])
        self.assertEqual(constants.FROZEN_PINS["pe_archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
        protected, protected_body = _run(argv + ["--requested-protection", "PROTECTED"])
        self.assertEqual(protected_body["reason"], "ENFORCEMENT_HELD", protected_body)
        del protected
        loaded = load_artifact_trust(artifact_trust)
        self.assertIn("test-nonprod-artifact-lab-install", loaded)


class GuestArgTests(unittest.TestCase):
    def test_guest_argv_has_no_caller_trust(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "self_service_guest",
            ROOT / "scripts" / "aws" / "lab-guests" / "self_service.py",
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("guest")
        guest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guest)
        argv = guest.installer_argv(
            "install",
            "OBSERVE",
            bundle="/tmp/vantio-lab/bundle",
            policy="/tmp/vantio-lab/policy.json",
            signature="/tmp/vantio-lab/signature.json",
            state_dir="/var/lib/vantio/install",
            config="/tmp/vantio-lab/config.json",
            transaction_id=None,
        )
        self.assertNotIn("--artifact-trust", argv)
        self.assertNotIn("--fixture-host", argv)
        self.assertIn("--config", argv)
        self.assertIn("/tmp/vantio-lab/config.json", argv)
        text = (ROOT / "scripts" / "aws" / "lab-guests" / "self_service.py").read_text(encoding="utf-8")
        self.assertNotIn("apt-get", text)
        self.assertNotIn("enterprise-rows.sh", text)
