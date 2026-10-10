"""Red-team grades. No GCP and no model download."""

from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import redteam_packet as packet


class GradeTests(unittest.TestCase):
    def test_tamper_without_a_ledger_row_is_fail_gap(self) -> None:
        denied = packet.grade_tamper(13, False)
        self.assertEqual(denied["outcome"], "FAIL_GAP")
        self.assertFalse(denied["silent_success"])
        held = packet.grade_tamper(1, True)
        self.assertEqual(held["outcome"], "HELD")
        opened = packet.grade_tamper(0, False)
        self.assertEqual(opened["outcome"], "FAIL_GAP")
        self.assertTrue(opened["silent_success"])
        self.assertNotEqual(packet.grade_tamper(22, False)["outcome"], "INCONCLUSIVE")

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

    def test_loader_kill_is_held_only_with_an_attributed_deny(self) -> None:
        silent = packet.grade_open(0, True)
        self.assertEqual(silent["outcome"], "FAIL_GAP")
        self.assertTrue(silent["silent_success"])
        self.assertEqual(silent["reason"], "protected_open_succeeded")
        bare = packet.grade_open(13, False)
        self.assertEqual(bare["outcome"], "FAIL_GAP")
        self.assertEqual(bare["reason"], "unattributed_deny")
        held = packet.grade_open(13, True)
        self.assertEqual(held["outcome"], "HELD")
        self.assertTrue(held["attributed"])
        tamper = packet.grade_tamper(1, False)
        self.assertEqual(tamper["outcome"], "FAIL_GAP")
        self.assertEqual(packet.grade_tamper(1, True)["outcome"], "HELD")
        self.assertEqual(packet.grade_tamper(13, True)["outcome"], "HELD")
        record = bytearray(packet.DENY_ATTR_SIZE)
        record[0:4] = (4242).to_bytes(4, "little")
        record[16:24] = (9).to_bytes(8, "little")
        record[32:36] = (packet.DENY_KIND_FILE).to_bytes(4, "little")
        self.assertTrue(packet.deny_record_names(bytes(record), 4242))
        self.assertFalse(packet.deny_record_names(bytes(record), 4243))
        record[16:24] = (0).to_bytes(8, "little")
        self.assertFalse(packet.deny_record_names(bytes(record), 4242))
        record[16:24] = (9).to_bytes(8, "little")
        record[32:36] = (packet.DENY_KIND_SELF).to_bytes(4, "little")
        self.assertTrue(packet.deny_record_names(bytes(record), 4242))

    def test_completion_retries_a_loading_server_on_localhost(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                Handler.seen.append(self.path)
                if len(Handler.seen) == 1:
                    self.send_response(503)
                    self.end_headers()
                    return
                body = json.dumps({"content": "file"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        Handler.seen = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            loaded, reason = packet.fetch_local_completion(port, time.time() + 5)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertTrue(loaded)
        self.assertEqual(reason, "completion_ok")
        self.assertEqual(Handler.seen[0], "/completion")
        self.assertIn("/v1/completions", Handler.seen)

    def test_completion_error_body_is_not_a_loaded_model(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.dumps({"error": {"message": "loading"}}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            loaded, reason = packet.fetch_local_completion(port, time.time() + 0.5)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertFalse(loaded)
        self.assertEqual(reason, "completion_failed")


if __name__ == "__main__":
    unittest.main()
