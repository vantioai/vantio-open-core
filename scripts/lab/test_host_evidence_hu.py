#!/usr/bin/env python3
"""Fixture tests for the H-U guest row. They do not call a cloud or a real host."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import host_evidence_hu as hu

ROOT = Path(__file__).resolve().parents[2]
SECRET_CRED = "CRED-BYTES-DO-NOT-PRINT"
SECRET_KEY = "-----BEGIN PRIVATE KEY-----\nKEY-BYTES\n-----END PRIVATE KEY-----\n"
SECRET_STORE = "CURSOR-STORE-BYTES"
KID = "synthetic-kid-not-from-a-host"


def _trust(key_id: str = "test-nonprod-ed25519-2026-10-02", root_flag: bool = True) -> dict:
    return {
        "not_a_production_root": root_flag,
        "keys": [
            {
                "key_class": "test",
                "key_id": key_id,
                "not_a_production_root": root_flag,
            }
        ],
    }


class GradeTests(unittest.TestCase):
    def test_passing_facts_are_pass_with_a_null_signer(self) -> None:
        document = hu.grade(hu.passing_facts())
        self.assertEqual(document["verdict"], "PASS")
        self.assertIsNone(document["signer_kid"])
        self.assertEqual([item["result"] for item in document["items"]], ["PASS"] * 6)
        text = hu.transcript(hu.passing_facts())
        for name in hu.ITEM_NAMES:
            self.assertIn(f"H-U item={name} result=PASS", text)
        self.assertIn("H-U verdict=PASS", text)
        self.assertNotIn(SECRET_KEY, text)

    def test_each_violation_stops(self) -> None:
        cases = {
            "mounts": {"mounts_readable": False, "mounts": []},
            "cursor_stores": {"cursor_stores": "present"},
            "credential_paths": {"credential_paths": "present", "credential_hits": ["/root/.aws/credentials"]},
            "production_signing_key": {"production_signing_key": "present", "signing_key_hits": ["/opt/vantio-enterprise/private-key.pem"]},
            "staged_trust": {"trust_docs": 0, "trust_nonprod": False},
            "signer_kid": {"signer_kid_null": False},
        }
        for name, updates in cases.items():
            facts = hu.passing_facts()
            facts.update(updates)
            document = hu.grade(facts)
            self.assertEqual(document["verdict"], "STOP", name)
            item = next(row for row in document["items"] if row["name"] == name)
            self.assertEqual(item["result"], "STOP", name)
            self.assertNotIn("signer_kid", document) if name == "signer_kid" else None
            rendered = json.dumps(document)
            self.assertNotIn(KID, rendered)
            self.assertNotIn(SECRET_KEY, rendered)

    def test_a_cursor_mount_stops_even_when_the_path_flag_says_absent(self) -> None:
        facts = hu.passing_facts()
        facts["mounts"] = [{"fstype": "ext4", "mount": "/cursor/stores"}]
        document = hu.grade(facts)
        self.assertEqual(document["verdict"], "STOP")
        item = next(row for row in document["items"] if row["name"] == "cursor_stores")
        self.assertEqual(item["result"], "STOP")

    def test_a_guest_verdict_that_disagrees_with_the_facts_stops(self) -> None:
        facts = hu.passing_facts()
        facts["cursor_stores"] = "present"
        text = hu.transcript(facts).replace("H-U verdict=STOP", "H-U verdict=PASS")
        document = hu.accept_transcript(text)
        self.assertEqual(document["verdict"], "STOP")
        self.assertEqual(hu.accept_transcript("no row")["verdict"], "STOP")

    def test_dev_nonprod_key_id_passes(self) -> None:
        self.assertTrue(
            hu._document_ok(
                {
                    "not_a_production_root": True,
                    "key_id": "dev-nonprod-lab-ci",
                }
            )
        )
        self.assertFalse(hu._document_ok(_trust("prod-artifact-example")))


class CollectTests(unittest.TestCase):
    def _tree(
        self,
        *,
        trust: bool = True,
        seal: bool = True,
        kid: object = None,
        mounts: bool = True,
        cursor: bool = False,
        cred: bool = False,
        key: bool = False,
        key_id: str = "test-nonprod-ed25519-2026-10-02",
        root_flag: bool = True,
        tar_only: bool = False,
    ) -> tuple[Path, Path]:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        if mounts:
            proc = tmp / "proc" / "self"
            proc.mkdir(parents=True)
            (proc / "mounts").write_text("disk / ext4 rw 0 0\nproc /proc proc rw 0 0\n", encoding="utf-8")
        (tmp / "root").mkdir()
        (tmp / "home" / "labuser").mkdir(parents=True)
        bundle = tmp / "bundle"
        bundle.mkdir()
        if trust and not tar_only:
            (bundle / "lab-artifact-trust.json").write_text(
                json.dumps(_trust(key_id, root_flag)),
                encoding="utf-8",
            )
        if tar_only:
            raw = json.dumps(_trust(key_id, root_flag)).encode("utf-8")
            info = tarfile.TarInfo("vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json")
            info.size = len(raw)
            with tarfile.open(bundle / "contract.tar", "w") as tar:
                tar.addfile(info, io.BytesIO(raw))
        if seal:
            (bundle / "pe-canonical-seal.json").write_text(
                json.dumps({"schema": 1, "signer_kid": kid}),
                encoding="utf-8",
            )
        if cursor:
            store = tmp / "cursor" / "stores"
            store.mkdir(parents=True)
            (store / "note").write_text(SECRET_STORE, encoding="utf-8")
        if cred:
            aws = tmp / "home" / "labuser" / ".aws"
            aws.mkdir()
            (aws / "credentials").write_text(SECRET_CRED, encoding="utf-8")
        if key:
            (bundle / "private-key.pem").write_text(SECRET_KEY, encoding="utf-8")
        return tmp, bundle

    def _collect(self, **kwargs) -> tuple[dict, str]:
        root, bundle = self._tree(**kwargs)
        facts = hu.collect(bundle, root=root)
        return facts, hu.transcript(facts)

    def test_a_clean_fixture_passes_and_keeps_mounts(self) -> None:
        facts, text = self._collect()
        document = hu.grade(facts)
        self.assertEqual(document["verdict"], "PASS")
        self.assertEqual(document["mounts"], [{"fstype": "ext4", "mount": "/"}, {"fstype": "proc", "mount": "/proc"}])
        self.assertNotIn("disk", text)

    def test_contract_tar_trust_is_enough(self) -> None:
        facts, _text = self._collect(tar_only=True)
        self.assertEqual(hu.grade(facts)["verdict"], "PASS")

    def test_presence_stops_without_printing_bytes(self) -> None:
        for kwargs, banned in (
            ({"cursor": True}, SECRET_STORE),
            ({"cred": True}, SECRET_CRED),
            ({"key": True}, "KEY-BYTES"),
            ({"key": True}, "BEGIN PRIVATE KEY"),
            ({"kid": KID}, KID),
            ({"root_flag": False}, SECRET_CRED),
        ):
            facts, text = self._collect(**kwargs)
            self.assertEqual(hu.grade(facts)["verdict"], "STOP", kwargs)
            self.assertNotIn(banned, text, kwargs)

    def test_missing_trust_seal_or_mounts_stop(self) -> None:
        for kwargs in ({"trust": False}, {"seal": False}, {"mounts": False}):
            facts, text = self._collect(**kwargs)
            self.assertEqual(hu.grade(facts)["verdict"], "STOP", kwargs)
            self.assertNotIn(SECRET_KEY, text)

    def test_cli_writes_only_the_public_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "h-u.json"
            with mock.patch.object(hu, "collect", return_value=hu.passing_facts()):
                code = hu.main(["--bundle", tmp, "--out", str(out)])
            body = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(body["schema"], hu.SCHEMA)
        self.assertEqual(body["verdict"], "PASS")
        self.assertIsNone(body["signer_kid"])
        self.assertNotIn("facts", body)


class WiringTests(unittest.TestCase):
    def test_both_guest_scripts_stop_before_battery_modes(self) -> None:
        aws = (ROOT / "scripts/aws/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        gcp = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        for path in (
            ROOT / "scripts/aws/lab-guests/enterprise-rows.sh",
            ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh",
        ):
            checked = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
        aws_call = aws.index('python3 "$here/host_evidence_hu.py"')
        self.assertLess(aws_call, aws.index('if [ "${2:-}" = "lsm-guard" ]'))
        gcp_call = gcp.index('python3 "$here/host_evidence_hu.py"')
        self.assertLess(gcp.index("  exit 0\nfi"), gcp_call)
        self.assertLess(gcp_call, gcp.index('if [ "$mode" = "lsm-guard" ]'))
        self.assertNotIn("VANTIO_LAB_CLOUD", aws)

    def test_runners_gate_before_grading(self) -> None:
        aws = (ROOT / "scripts/aws/w3_lab_steps.py").read_text(encoding="utf-8")
        self.assertLess(aws.index('raise lab.GuardAbort("h_u")'), aws.index("battery_verdict = phase_battery_verdict"))
        gcp = (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8")
        block = gcp[gcp.index("def run_batteries"): gcp.index("def run_self_service")]
        self.assertLess(block.index("require_host_evidence"), block.index("_prepare_lab_lsm"))
        self.assertLess(block.index("require_host_evidence"), block.index("_run_one_battery"))
        arm = (ROOT / ".github/workflows/w3-lab-auto-arm.yml").read_text(encoding="utf-8")
        self.assertIn("w3-lab-h-u.json", arm)


if __name__ == "__main__":
    unittest.main()
