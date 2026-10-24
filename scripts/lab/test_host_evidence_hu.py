#!/usr/bin/env python3
"""Fixture tests for the H-U guest row. They do not call a cloud or a real host."""

from __future__ import annotations

import contextlib
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

    def test_key_id_allowlist_accepts_the_lab_artifact_id(self) -> None:
        allowed = (
            "test-nonprod-artifact-lab-ci",
            "dev-nonprod-lab-ci",
            "test-nonprod-ed25519-2026-10-02",
        )
        for key_id in allowed:
            self.assertTrue(hu._document_ok(_trust(key_id)), key_id)
        self.assertFalse(hu._document_ok(_trust("prod-artifact-lab")))
        self.assertFalse(hu._record_ok({"key_id": "test-nonprod-lab", "key_class": "production", "not_a_production_root": True}))

    def test_key_level_flag_is_enough_when_the_top_level_flag_is_absent(self) -> None:
        payload = {
            "keys": [
                {
                    "key_class": "test",
                    "key_id": "test-nonprod-ed25519-2026-10-02",
                    "not_a_production_root": True,
                }
            ]
        }
        self.assertTrue(hu._document_ok(payload))
        payload["not_a_production_root"] = False
        self.assertFalse(hu._document_ok(payload))

    def test_regrade_rejects_a_forged_or_incomplete_transcript(self) -> None:
        good = hu.transcript(hu.passing_facts())
        stop_facts = hu.passing_facts()
        stop_facts["cursor_stores"] = "present"
        stopped = hu.transcript(stop_facts)
        cases = {
            "duplicate": good + stopped,
            "missing": "\n".join(line for line in good.splitlines() if "item=mounts" not in line) + "\n",
            "reordered": good.replace(
                "H-U item=mounts result=PASS\nH-U item=cursor_stores result=PASS",
                "H-U item=cursor_stores result=PASS\nH-U item=mounts result=PASS",
            ),
            "extra_json": good + "H-U-JSON {\"schema\":\"vantio.lab.host-evidence.h-u/v1\",\"facts\":{}}\n",
            "mismatched": good.replace("H-U item=mounts result=PASS", "H-U item=mounts result=STOP"),
            "extra_line": good.replace("H-U verdict=PASS", "H-U note=1\nH-U verdict=PASS"),
        }
        for name, text in cases.items():
            self.assertEqual(hu.accept_transcript(text)["verdict"], "STOP", name)
        self.assertEqual(hu.accept_transcript(good)["verdict"], "PASS")
        self.assertEqual(hu.accept_transcript(good, expect_trust="none")["verdict"], "STOP")


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

    def test_expect_trust_none_passes_only_when_nothing_is_staged(self) -> None:
        facts, _text = self._collect(trust=False)
        graded = hu.grade(hu._with_expect(facts, "none"))
        self.assertEqual(graded["verdict"], "PASS")
        self.assertIs(graded["none_staged"], True)
        item = next(row for row in graded["items"] if row["name"] == "staged_trust")
        self.assertEqual(item["result"], "PASS")
        dirty, _text = self._collect(trust=False, key=True)
        self.assertEqual(hu.grade(hu._with_expect(dirty, "none"))["verdict"], "STOP")
        named, bundle = self._tree(trust=False)
        (bundle / "notes-trust.json").write_text("{}\n", encoding="utf-8")
        walked = hu.collect(bundle, root=named)
        self.assertEqual(hu.grade(hu._with_expect(walked, "none"))["verdict"], "STOP")
        broken, broken_bundle = self._tree(trust=False)
        (broken_bundle / "lab-artifact-trust.json").write_text("{", encoding="utf-8")
        unreadable = hu.collect(broken_bundle, root=broken)
        self.assertTrue(unreadable["trust_unreadable"])
        self.assertEqual(hu.grade(hu._with_expect(unreadable, "none"))["verdict"], "STOP")
        self.assertEqual(hu.grade(hu._with_expect(unreadable, "some"))["verdict"], "STOP")

    def test_every_home_directory_is_on_the_same_path_the_guest_uses(self) -> None:
        root, bundle = self._tree()
        other = root / "home" / "otherbot" / ".aws"
        other.mkdir(parents=True)
        (other / "credentials").write_text(SECRET_CRED, encoding="utf-8")
        facts = hu.collect(bundle, root=root)
        self.assertTrue(any(hit.endswith("/home/otherbot/.aws/credentials") for hit in facts["credential_hits"]))
        text = hu.transcript(facts)
        self.assertNotIn(SECRET_CRED, text)
        self.assertEqual(hu.grade(facts)["verdict"], "STOP")
        source = (ROOT / "scripts/lab/host_evidence_hu.py").read_text(encoding="utf-8")
        homes = source[source.index("def _homes("): source.index("def _home_children(")]
        self.assertLess(homes.index("_home_children"), homes.index('root == Path("/")'))
        home = root / "home"
        home.chmod(0)
        try:
            blocked = hu.collect(bundle, root=root)
        finally:
            home.chmod(0o755)
        self.assertEqual(blocked["credential_paths"], "unreadable")
        self.assertEqual(hu.grade(blocked)["verdict"], "STOP")

    def test_an_unexpected_error_prints_six_stops_and_hides_the_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(hu, "collect", side_effect=RuntimeError(SECRET_CRED)):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = hu.main(["--bundle", tmp])
        text = stdout.getvalue()
        self.assertEqual(code, 6)
        self.assertEqual(text.count("result=STOP"), 6)
        self.assertIn("H-U verdict=STOP", text)
        self.assertIn('"error":"exception"', text)
        self.assertNotIn(SECRET_CRED, text)
        self.assertEqual(hu.accept_transcript(text)["verdict"], "STOP")

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
        aws_call = aws.index('sudo -n python3 "$here/host_evidence_hu.py"')
        self.assertIn("--expect-trust some", aws)
        self.assertLess(aws_call, aws.index('if [ "${2:-}" = "lsm-guard" ]'))
        gcp_call = gcp.index('sudo -n python3 "$here/host_evidence_hu.py"')
        self.assertIn("--expect-trust some", gcp)
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
        start = aws.index("def gate_host_evidence")
        gate = aws[start:start + 2500]
        self.assertIn('"sudo"', gate)
        self.assertIn('"-n"', gate)
        self.assertIn('"--expect-trust"', gate)
        self.assertIn('expect_trust="none"', gcp)


if __name__ == "__main__":
    unittest.main()
