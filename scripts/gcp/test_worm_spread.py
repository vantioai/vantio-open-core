"""Worm-spread grades. No GCP and no model download."""

from __future__ import annotations

import json
import py_compile
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import offline_deliver as od
import worm_spread as worm

ROOT = Path(__file__).resolve().parents[2]
GUEST = ROOT / "scripts/gcp/lab-guests/worm_spread.py"
SEAL = "ab" * 32


def completed(text: str = "", code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=text, stderr="")


def side(anchor: int = 9) -> dict:
    return {
        "file": {"errno": 13, "anchor": anchor, "pid": 40},
        "egress": {"errno": 110, "anchor": anchor, "pid": 41},
        "model_loaded": True,
        "model_reason": "completion_ok",
        "optics": {"listener": True, "events": [{"id": "worm.file.a", "pid": 40}]},
    }


class FakeOd:
    def __init__(self, side_a: dict, side_b: dict, uninstall: str = "UNINSTALL_VERIFIED\n") -> None:
        self.side_a = side_a
        self.side_b = side_b
        self.uninstall = uninstall
        self.commands: list[tuple[str, str]] = []
        self.copied: list[str] = []
        self.GUEST_DIR = "/var/lib/vantio-lab/guest"

    def _enabled(self, env: dict) -> None:
        return None

    def require_lab_project(self, project: str) -> str:
        if project != worm.LAB_PROJECT or "navera" in project.lower():
            raise SystemExit("refusing project")
        return project

    def instance_name(self, run_id: str) -> str:
        return f"vantio-gcp-lab-{run_id}"

    def _gate_ok(self, env: dict) -> dict:
        return {"expected_oop_usd": "0", "abort": False}

    def brain_requested(self, env: dict) -> bool:
        return env.get("REDTEAM_BRAIN") == "true"

    def refuse_batteries(self, env: dict) -> str:
        return SEAL

    def redact(self, text: str) -> str:
        return text

    def _evidence_dir(self, env: dict) -> Path:
        return Path(env["EVIDENCE_DIR"])

    def peer_ip(self, project: str, name: str) -> str:
        if name == "vantio-gcp-lab-12":
            return "10.1.0.5"
        if name == "vantio-gcp-lab-b-12":
            return "10.1.0.6"
        return "8.8.8.8"

    def _stage_payload(self, env: dict, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("seal.oci.tar", "contract.tar", "enterprise-rows.sh", "debs.tar", "ca-certificates.crt"):
            (dest / name).write_bytes(b"x")

    def _scp_to(self, project: str, name: str, sources: list[Path]) -> None:
        self.copied.extend(path.name for path in sources)

    def _ssh(self, project: str, name: str, command: str) -> subprocess.CompletedProcess[str]:
        self.commands.append((name, command))
        if "uninstall" in command:
            return completed(self.uninstall)
        return completed("ok")

    def _scp_from(self, project: str, name: str, remote: str, dest: Path) -> bool:
        payload = self.side_a if remote.endswith("a.json") else self.side_b
        dest.write_text(json.dumps(payload), encoding="utf-8")
        return True


def env(tmp: str, **extra: str) -> dict:
    base = {
        "GCP_LAB_EXECUTE": "1",
        "GCP_LAB_PROJECT": worm.LAB_PROJECT,
        "GITHUB_RUN_ID": "12",
        "EVIDENCE_DIR": tmp,
        "RUNNER_TEMP": tmp,
        "REDTEAM_BRAIN": "true",
        "WORM_SPREAD": "true",
        "STOP_AFTER_MINUTES": "90",
        "WORM_SCRIPT": str(GUEST),
        "BRAIN_DIR": str(Path(tmp) / "missing-brain"),
    }
    base.update(extra)
    return base


class WormTests(unittest.TestCase):
    def test_both_ends_pass_only_with_anchors(self) -> None:
        report = worm.grade_report(side(), side(), "UNINSTALL_VERIFIED\n", "UNINSTALL_VERIFIED\n")
        self.assertTrue(worm.acceptance(report))
        bare = side(anchor=0)
        bare["egress"]["anchor"] = 0
        missed = worm.grade_report(bare, side(), "UNINSTALL_VERIFIED\n", "UNINSTALL_VERIFIED\n")
        self.assertFalse(worm.acceptance(missed))
        self.assertEqual(worm.grade_egress(110, 0, 41)["reason"], "not_graded")
        self.assertEqual(worm.grade_egress(110, 9, 41)["outcome"], "HELD")
        self.assertEqual(worm.grade_file(0, 0, 40)["reason"], "file_landed")

    def test_private_peers_and_the_pair_cost(self) -> None:
        self.assertTrue(worm.private_peer("10.1.0.6"))
        self.assertFalse(worm.private_peer("8.8.8.8"))
        self.assertFalse(worm.private_peer("192.0.2.2"))
        self.assertFalse(worm.private_peer("127.0.0.1"))
        gross = worm.pair_under_cap(120)
        self.assertLess(gross, worm.rtbrain.GROSS_RUN_CAP_USD)
        self.assertGreater(gross, worm.rtbrain.estimate_gross_usd("e2-standard-4", 120, worm.rtbrain.BRAIN_DISK_GB))
        self.assertEqual(worm.delete_order("12"), ["vantio-gcp-lab-b-12", "vantio-gcp-lab-12"])
        with self.assertRaises(SystemExit):
            worm.refuse_scope(worm.LAB_PROJECT, worm.SOAK_INSTANCE)
        with self.assertRaises(SystemExit):
            worm.refuse_scope("beaming-opus-511014-c5", "vantio-gcp-lab-12")

    def test_execute_fails_closed_when_the_peer_is_public(self) -> None:
        class Public(FakeOd):
            def peer_ip(self, project: str, name: str) -> str:
                return "8.8.8.8"

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                worm.execute(env(tmp), Public(side(), side()))

    def test_execute_records_both_vms_when_the_rows_hold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeOd(side(), side())
            code = worm.execute(env(tmp), fake)
            self.assertEqual(code, 0)
            hosts = {name for name, _command in fake.commands}
            self.assertEqual(hosts, {"vantio-gcp-lab-12", "vantio-gcp-lab-b-12"})
            joined = " ".join(command for _name, command in fake.commands)
            self.assertIn("PEER_IP=10.1.0.6", joined)
            self.assertIn("PEER_IP=10.1.0.5", joined)
            self.assertNotIn("shell=True", joined)
            demo = json.loads((Path(tmp) / worm.DEMO_NAME).read_text(encoding="utf-8"))
            self.assertEqual(demo["kind"], "asciinema")
            self.assertIn("acceptance=pass", "\n".join(demo["transcript"]))

    def test_create_adds_the_micro_peer_after_the_attacker(self) -> None:
        calls: list[list[str]] = []
        original_list = od._list_instances
        original_run = od._run_ok
        original_write = od.write_evidence
        original_output = od.github_output
        od._list_instances = lambda _project: []
        od._run_ok = lambda argv, _reason: calls.append(list(argv)) or completed()
        od.write_evidence = lambda *_args, **_kwargs: None
        od.github_output = lambda *_args, **_kwargs: None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                od.create_instance(
                    {
                        "GCP_LAB_EXECUTE": "1",
                        "GCP_LAB_PROJECT": "vantio-lab-oct08",
                        "GITHUB_RUN_ID": "12",
                        "GCP_LAB_GATE_JSON": json.dumps({"expected_oop_usd": "0", "abort": False}),
                        "STOP_AFTER_MINUTES": "90",
                        "REDTEAM_BRAIN": "true",
                        "WORM_SPREAD": "true",
                        "GCP_LAB_NOW_EPOCH": "1760000000",
                        "EVIDENCE_DIR": tmp,
                        "RUNNER_TEMP": tmp,
                    }
                )
        finally:
            od._list_instances = original_list
            od._run_ok = original_run
            od.write_evidence = original_write
            od.github_output = original_output
        names = [argv[4] for argv in calls if "create" in argv]
        self.assertEqual(names, ["vantio-gcp-lab-12", "vantio-gcp-lab-b-12"])
        peer = " ".join(calls[1])
        self.assertIn("--machine-type=e2-micro", peer)
        self.assertIn("--no-address", peer)
        self.assertIn("--network=vantio-lab-offline", peer)
        self.assertNotIn("navera", peer.lower())

    def test_teardown_deletes_the_peer_before_the_attacker(self) -> None:
        deleted: list[str] = []
        labels = od.offline_labels(1760000000, 90)
        instances = [
            {"name": "vantio-gcp-lab-12", "status": "RUNNING", "labels": labels, "zone": "us-central1-a"},
            {"name": "vantio-gcp-lab-b-12", "status": "RUNNING", "labels": labels, "zone": "us-central1-a"},
        ]
        originals = (od._list_instances, od._run_ok, od._creation_epoch, od.delete_objects, od.write_evidence, od.lab.execute_verify)
        od._list_instances = lambda _project: instances
        od._creation_epoch = lambda _project, _name: int(time.time()) - 60

        def run_ok(argv: list[str], _reason: str) -> subprocess.CompletedProcess[str]:
            deleted.append(argv[4])
            return completed()

        od._run_ok = run_ok
        od.delete_objects = lambda *_args, **_kwargs: None
        od.write_evidence = lambda *_args, **_kwargs: None

        def verify(env: dict) -> int:
            print(json.dumps({"status": "VERIFIED_REMOVED", "name": env.get("INSTANCE_NAME")}))
            return 0

        od.lab.execute_verify = verify
        try:
            with tempfile.TemporaryDirectory() as tmp:
                code = od.teardown_if_present(
                    {
                        "GCP_LAB_EXECUTE": "1",
                        "GCP_LAB_PROJECT": "vantio-lab-oct08",
                        "GITHUB_RUN_ID": "12",
                        "EVIDENCE_DIR": tmp,
                        "WORM_SPREAD": "true",
                    }
                )
        finally:
            od._list_instances, od._run_ok, od._creation_epoch, od.delete_objects, od.write_evidence, od.lab.execute_verify = originals
        self.assertEqual(code, 0)
        self.assertEqual(deleted, ["vantio-gcp-lab-b-12", "vantio-gcp-lab-12"])

    def test_guest_attempt_stays_bounded(self) -> None:
        py_compile.compile(str(GUEST), doraise=True)
        text = GUEST.read_text(encoding="utf-8")
        self.assertNotIn("shell=True", text)
        self.assertIn("phantom-box", text)
        workflow = (ROOT / ".github/workflows/gcp-lab-provision.yml").read_text(encoding="utf-8")
        self.assertIn("worm_spread:", workflow)
        self.assertIn("run-worm-spread", workflow)
        self.assertIn("default: false", workflow)

    def test_prune_keeps_the_demo_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            worm.write_demo(directory, ["worm.egress.a outcome=HELD errno=110 anchor=9"])
            kept = od.prune_evidence(directory)
            self.assertIn(worm.DEMO_NAME, kept)


if __name__ == "__main__":
    unittest.main()
