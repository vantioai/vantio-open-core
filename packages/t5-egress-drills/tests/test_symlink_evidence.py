"""Symlink containment and evidence shape."""

from __future__ import annotations

import os
import tempfile
import threading
import unittest

import support

from t5_egress.evidence import EvidenceRejected, evidence_record, sha256_hex
from t5_egress.symlink import open_beneath, open_workload_root, read_beneath, resolve_mask


class SymlinkTests(unittest.TestCase):
    def test_inside_file_and_escape(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            outside = tempfile.mkdtemp()
            try:
                sentinel = outside + "/secret"
                with open(sentinel, "w", encoding="utf-8") as handle:
                    handle.write("SENTINEL-OUTSIDE")
                with open(root + "/note", "w", encoding="utf-8") as handle:
                    handle.write("inside")
                os.symlink("note", root + "/inner")
                os.symlink(sentinel, root + "/escape")
                os.mkdir(root + "/sub")
                os.symlink(outside, root + "/outdir")
                root_fd = open_workload_root(root)
                self.assertIsInstance(root_fd, int)
                assert isinstance(root_fd, int)
                try:
                    decision, data = read_beneath(root_fd, "note")
                    self.assertEqual(decision.action, "ALLOW")
                    self.assertEqual(data, b"inside")
                    inner, inner_data = read_beneath(root_fd, "inner")
                    self.assertEqual(inner.action, "ALLOW")
                    self.assertEqual(inner_data, b"inside")
                    escaped, escaped_data = read_beneath(root_fd, "escape")
                    self.assertEqual(escaped.reason, "symlink_escape")
                    self.assertEqual(escaped_data, b"")
                    dotted, _ = read_beneath(root_fd, "../" + os.path.basename(outside) + "/secret")
                    self.assertIn(dotted.reason, {"symlink_escape", "path_absent", "path_not_relative", "open_failed"})
                    self.assertNotEqual(dotted.action, "ALLOW")
                    via_dir, via_data = read_beneath(root_fd, "outdir/secret")
                    self.assertNotEqual(via_dir.action, "ALLOW")
                    self.assertNotIn(b"SENTINEL-OUTSIDE", via_data)
                    absolute = open_beneath(root_fd, "/etc/passwd")
                    self.assertEqual(absolute.reason, "path_not_relative")
                finally:
                    os.close(root_fd)
                linked = os.path.join(tempfile.mkdtemp(), "root")
                os.symlink(root, linked)
                self.assertEqual(open_workload_root(linked).reason, "symlink_root")
            finally:
                os.remove(sentinel)
                os.rmdir(outside)

    def test_race_never_reads_the_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            outside = tempfile.mkdtemp()
            try:
                sentinel_path = outside + "/secret"
                with open(sentinel_path, "wb") as handle:
                    handle.write(b"SENTINEL-OUTSIDE")
                target = root + "/flip"
                with open(target, "wb") as handle:
                    handle.write(b"inside")
                root_fd = open_workload_root(root)
                assert isinstance(root_fd, int)
                stop = threading.Event()

                def flip() -> None:
                    while not stop.is_set():
                        try:
                            os.remove(target)
                        except FileNotFoundError:
                            pass
                        try:
                            os.symlink(sentinel_path, target)
                        except FileExistsError:
                            continue
                        try:
                            os.remove(target)
                        except FileNotFoundError:
                            pass
                        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                        os.write(fd, b"inside")
                        os.close(fd)

                thread = threading.Thread(target=flip)
                thread.start()
                try:
                    for _ in range(80):
                        _decision, data = read_beneath(root_fd, "flip")
                        self.assertNotIn(b"SENTINEL-OUTSIDE", data)
                finally:
                    stop.set()
                    thread.join()
                    os.close(root_fd)
                with open(sentinel_path, "rb") as handle:
                    self.assertEqual(handle.read(), b"SENTINEL-OUTSIDE")
            finally:
                os.remove(sentinel_path)
                os.rmdir(outside)

    def test_resolve_mask_includes_beneath_and_magic(self) -> None:
        self.assertEqual(resolve_mask() & 0x08, 0x08)
        self.assertEqual(resolve_mask() & 0x02, 0x02)
        self.assertEqual(resolve_mask() & 0x01, 0x01)
        self.assertEqual(resolve_mask() & 0x04, 0)


class EvidenceTests(unittest.TestCase):
    def test_hash_and_forbidden_keys(self) -> None:
        digest = sha256_hex(b"synthetic")
        record = evidence_record("t5-dns-allow-list", "pass", [{"name": "listed", "packet_sha256": digest}])
        self.assertEqual(record["label"], "Lab-only")
        self.assertNotIn("synthetic", str(record))
        with self.assertRaises(EvidenceRejected):
            evidence_record("t5-get-write", "pass", [{"name": "bad", "query": "secret"}])


if __name__ == "__main__":
    unittest.main()
