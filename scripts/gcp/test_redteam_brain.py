"""Cost and hash pins for the offline red-team brain. No download and no GCP."""

from __future__ import annotations

import importlib.util
import io
import tarfile
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import offline_deliver as od
import redteam_brain as brain
import redteam_campaign as campaign

ROOT = Path(__file__).resolve().parents[2]


def _stage_module():
    path = Path(__file__).resolve().parent / "lab-guests" / "stage_brain.py"
    spec = importlib.util.spec_from_file_location("stage_brain", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("stage_brain")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _add(tar: tarfile.TarFile, name: str, payload: bytes, *, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = mode
    tar.addfile(info, io.BytesIO(payload))


class BrainTests(unittest.TestCase):
    def test_e2_standard_4_for_two_hours_stays_under_the_dollar_cap(self) -> None:
        # 120 minutes is the longest life the lab will start.
        gross = brain.assert_under_cap(brain.BRAIN_MACHINE, 120, brain.BRAIN_DISK_GB)
        self.assertLess(gross, brain.GROSS_RUN_CAP_USD)
        self.assertLess(gross, brain.LAB_BUDGET_USD)
        quote = brain.brain_plan(90)
        self.assertEqual(quote["machine_type"], "e2-standard-4")
        self.assertEqual(quote["expected_oop_usd"], "0")
        self.assertEqual(quote["model_sha256"], brain.MODEL_SHA256)
        self.assertLess(Decimal(quote["gross_usd"]), Decimal("0.30"))

    def test_unknown_machine_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            brain.estimate_gross_usd("n2-standard-32", 10, Decimal("10"))

    def test_hash_pin_is_exact(self) -> None:
        self.assertTrue(brain.hashes_match(brain.MODEL_SHA256, brain.RUNTIME_SHA256))
        self.assertFalse(brain.hashes_match("ab" * 32, brain.RUNTIME_SHA256))
        self.assertEqual(brain.MODEL_BYTES, 2104932768)

    def test_guest_stage_lands_the_server_beside_the_weights(self) -> None:
        stage_brain = _stage_module()
        weights = b"gguf-bytes"
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            _add(tar, "llama-b11540/llama-server", b"#!/bin/server\n", mode=0o755)
            _add(tar, "llama-b11540/libllama-server-impl.so", b"impl")
            link = tarfile.TarInfo("llama-b11540/libllama.so")
            link.type = tarfile.SYMTYPE
            link.linkname = "libllama.so.0"
            tar.addfile(link)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "guest"
            dest = root / "brain"
            source.mkdir()
            (source / stage_brain.RUNTIME_NAME).write_bytes(buffer.getvalue())
            (source / stage_brain.MODEL_NAME).write_bytes(weights)
            server, model = stage_brain.stage(source, dest, model_bytes=len(weights))
            self.assertTrue(server.is_file())
            self.assertFalse(server.is_symlink())
            self.assertTrue(server.stat().st_mode & 0o111)
            self.assertEqual(model.read_bytes(), weights)
            self.assertEqual(model.stat().st_ino, (source / stage_brain.MODEL_NAME).stat().st_ino)
            self.assertTrue((dest / "llama-b11540" / "libllama.so").is_symlink())
            again, _model = stage_brain.stage(source, dest, model_bytes=len(weights))
            self.assertEqual(again, server)

    def test_guest_stage_refuses_an_escaping_member(self) -> None:
        stage_brain = _stage_module()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            _add(tar, "../outside", b"nope")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "guest"
            source.mkdir()
            (source / stage_brain.RUNTIME_NAME).write_bytes(buffer.getvalue())
            (source / stage_brain.MODEL_NAME).write_bytes(b"x")
            with self.assertRaises(ValueError) as caught:
                stage_brain.stage(source, root / "brain", model_bytes=1)
        self.assertEqual(str(caught.exception), "runtime_member")

    def test_guest_stage_refuses_a_short_model(self) -> None:
        stage_brain = _stage_module()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "guest"
            source.mkdir()
            (source / stage_brain.RUNTIME_NAME).write_bytes(b"not-a-tar")
            (source / stage_brain.MODEL_NAME).write_bytes(b"short")
            with self.assertRaises(ValueError) as caught:
                stage_brain.stage(source, Path(tmp) / "brain")
        self.assertEqual(str(caught.exception), "model_size")

    def test_campaign_points_the_guest_at_the_staged_brain(self) -> None:
        self.assertEqual(od.GUEST_DIR, campaign.GUEST_PAYLOAD)
        self.assertEqual(
            campaign.brain_stage_command(od.GUEST_DIR),
            "sudo python3 /var/lib/vantio-lab/guest/stage_brain.py "
            "/var/lib/vantio-lab/guest /var/lib/vantio-lab/brain",
        )
        self.assertEqual(
            campaign.brain_rows_command(od.GUEST_DIR),
            "sudo env VANTIO_BRAIN_DIR=/var/lib/vantio-lab/brain "
            "python3 /var/lib/vantio-lab/guest/redteam_rows.py /opt/vantio-enterprise",
        )
        with self.assertRaises(ValueError):
            campaign.brain_rows_command("/tmp/other")
        self.assertEqual(campaign.campaign_exit(True), 0)
        self.assertEqual(campaign.campaign_exit(False), 2)
        text = (ROOT / ".github/workflows/gcp-lab-provision.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/gcp/lab-guests/stage_brain.py", text)
        campaign_text = (ROOT / "scripts/gcp/redteam_campaign.py").read_text(encoding="utf-8")
        self.assertIn('payload_dir / "stage_brain.py"', campaign_text)


if __name__ == "__main__":
    unittest.main()
