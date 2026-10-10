"""Red-team grades. No GCP and no model download."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import redteam_packet as packet


class GradeTests(unittest.TestCase):
    def test_unattributed_deny_is_fail_gap(self) -> None:
        grade = packet.grade_open(13, False)
        self.assertEqual(grade["outcome"], "FAIL_GAP")
        self.assertFalse(grade["silent_success"])
        self.assertEqual(grade["reason"], "unattributed_deny")

    def test_attributed_deny_is_held(self) -> None:
        grade = packet.grade_open(13, True)
        self.assertEqual(grade["outcome"], "HELD")
        self.assertTrue(grade["attributed"])
        self.assertFalse(grade["silent_success"])

    def test_successful_open_is_silent_fail_gap(self) -> None:
        grade = packet.grade_open(0, False)
        self.assertEqual(grade["outcome"], "FAIL_GAP")
        self.assertTrue(grade["silent_success"])

    def test_descendant_sample_without_pid_event_fails(self) -> None:
        rows = packet.rows_from_descendant(
            {
                "post": {
                    "cases": [
                        {
                            "name": "moved",
                            "samples": [
                                {
                                    "expect_deny": True,
                                    "file_errno": 13,
                                    "file_event": False,
                                    "egress_event": False,
                                }
                            ],
                        }
                    ]
                }
            }
        )
        self.assertEqual(rows[0]["id"], "pe.escape.move")
        self.assertEqual(rows[0]["outcome"], "FAIL_GAP")
        self.assertFalse(rows[0]["silent_success"])

    def test_unshare_also_covers_the_namespace_row(self) -> None:
        rows = packet.rows_from_descendant(
            {
                "cases": [
                    {
                        "name": "unshare",
                        "expect_deny": True,
                        "file_errno": 13,
                        "file_event": True,
                        "egress_event": True,
                    }
                ]
            }
        )
        ids = {row["id"]: row["outcome"] for row in rows}
        self.assertEqual(ids["pe.escape.unshare"], "HELD")
        self.assertEqual(ids["pe.escape.namespace"], "HELD")

    def test_public_pin_is_not_a_working_seal(self) -> None:
        rows = packet.installer_and_supply_rows("ab" * 32)
        graded = {row["id"]: row["outcome"] for row in rows}
        self.assertEqual(graded["inst.downgrade"], "HELD")
        self.assertEqual(graded["inst.artifact_substitution"], "HELD")
        self.assertEqual(graded["supply.seal_repro"], "GAP")
        self.assertTrue(packet.corrupt_digest_refused("abcd"))
        self.assertTrue(packet.corrupt_digest_refused(packet.PUBLIC_PIN))

    def test_packet_writer_drops_paths_and_keeps_grades(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "redteam-packet.json"
            packet.write_packet(
                path,
                {
                    "attempts": [
                        {
                            "id": "pe.escape.move",
                            "outcome": "FAIL_GAP",
                            "silent_success": False,
                            "attributed": False,
                            "errno": 13,
                            "reason": "unattributed_deny",
                            "path": "/tmp/secret",
                            "pid": 99,
                        }
                    ],
                    "seal_sha256": "ab" * 32,
                    "bundle_commit": "cd" * 20,
                    "model_sha256": "ef" * 32,
                    "model_loaded": False,
                    "machine_type": "e2-standard-4",
                    "gross_usd": "0.2072",
                    "campaign_complete": True,
                    "hostname": "phantom-box",
                },
            )
            body = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("path", body["attempts"][0])
            self.assertNotIn("pid", body["attempts"][0])
            self.assertNotIn("hostname", body)
            self.assertEqual(body["attempts"][0]["outcome"], "FAIL_GAP")
            self.assertEqual(body["machine_type"], "e2-standard-4")
            self.assertEqual(body["counts"]["FAIL_GAP"], 1)
            self.assertEqual(body["open_shell"], "not_run")


if __name__ == "__main__":
    unittest.main()
