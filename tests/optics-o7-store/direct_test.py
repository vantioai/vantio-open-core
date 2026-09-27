"""Direct tests for the Python operational store."""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from support import clean_record, record_with

from optics_operational_store.posture import (
    EVIDENCE_TIER,
    NODE_BINDING,
    OPERATIONAL_SCHEMA_VERSION,
    PKG02_WRITER_FLAGS,
    PRIVACY_GENERATION,
    SCHEMA_STATUS,
)
from optics_operational_store.store import open_store


class DirectStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._umask = None

    def tearDown(self):
        if self._umask is not None:
            os.umask(self._umask)
        self._tmp.cleanup()

    def test_import_and_absent_open_create_nothing(self):
        home = Path.home() / ".vantio" / "optics" / "store.sqlite"
        before = home.exists()
        previous = os.environ.pop("VANTIO_HOME", None)
        try:
            handle = open_store(self.root)
        finally:
            if previous is not None:
                os.environ["VANTIO_HOME"] = previous
        self.assertFalse(handle.opened)
        self.assertFalse(handle.writes_enabled)
        self.assertTrue(handle.application_continues)
        self.assertFalse(handle.default_write_path)
        self.assertEqual(handle.reason_code, "STORE_ABSENT")
        self.assertEqual(handle.evidence_tier, EVIDENCE_TIER)
        self.assertEqual(handle.node_binding, NODE_BINDING)
        self.assertFalse((self.root / "optics" / "store.sqlite").exists())
        self.assertEqual(home.exists(), before)

    def test_pkg02_flags_do_not_create_a_file(self):
        flags = {name: True for name in PKG02_WRITER_FLAGS}
        handle = open_store(self.root, **flags)
        self.assertEqual(handle.reason_code, "STORE_ABSENT")
        self.assertFalse((self.root / "optics" / "store.sqlite").exists())

    def test_create_is_wal_owner_only_and_versioned(self):
        self._umask = os.umask(0)
        handle = open_store(self.root, create=True)
        try:
            self.assertTrue(handle.healthy)
            self.assertTrue(handle.writes_enabled)
            self.assertFalse(handle.default_write_path)
            self.assertEqual(handle.schema_status, SCHEMA_STATUS)
            self.assertEqual(handle.user_version, OPERATIONAL_SCHEMA_VERSION)
            self.assertNotEqual(handle.user_version, 2)
            self.assertEqual(handle.privacy_generation, PRIVACY_GENERATION)
            self.assertEqual(handle.integrity, "OK")
            store = self.root / "optics" / "store.sqlite"
            self.assertEqual(stat.S_IMODE(store.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((self.root / "optics").stat().st_mode), 0o700)
            mode = handle.conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(str(mode).lower(), "wal")
            self.assertEqual(handle.conn.execute("PRAGMA user_version").fetchone()[0], 1)
            privacy = handle.conn.execute(
                "SELECT meta_value FROM store_meta WHERE meta_key = 'privacy_generation'"
            ).fetchone()[0]
            self.assertEqual(privacy, "1")
            status = handle.conn.execute(
                "SELECT meta_value FROM store_meta WHERE meta_key = 'schema_status'"
            ).fetchone()[0]
            self.assertEqual(status, "unstable-pre-1.0")
            sidecar = (self.root / "optics" / "store.id").read_text(encoding="utf-8").strip()
            self.assertEqual(sidecar, handle.safe_store_id)
            self.assertNotIn("/", sidecar)
            self.assertEqual(stat.S_IMODE((self.root / "optics" / "store.id").stat().st_mode), 0o600)
            page = handle.conn.execute("PRAGMA page_size").fetchone()[0]
            self.assertIsInstance(page, int)
            busy = handle.conn.execute("PRAGMA busy_timeout").fetchone()[0]
            self.assertEqual(busy, 0)
        finally:
            handle.close()

    def test_put_get_and_query_round_trip(self):
        handle = open_store(self.root, create=True)
        try:
            stored = handle.put(clean_record(), application_result={"token": "APP"})
            self.assertTrue(stored["stored"])
            self.assertEqual(stored["reason_code"], "OK")
            self.assertEqual(stored["application_result"]["token"], "APP")
            self.assertIsNot(stored["application_result"], {"token": "APP"})
            self.assertEqual(stored["record"]["schema_version"], 0)
            self.assertEqual(stored["record"]["schema_status"], "unstable-pre-1.0")
            self.assertNotIn("prompt", stored["record"])
            fetched = handle.get(event_id="e.12.prod_clean_1.0")
            self.assertEqual(fetched["records"][0]["destination_host"], "api.example.com")
            page = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                }
            )
            self.assertEqual(page["completeness"], "COMPLETE")
            self.assertEqual(page["completenessReasons"], [])
            self.assertEqual(page["freshness"], "UNKNOWN")
            self.assertNotEqual(page["freshness"], "CURRENT")
            self.assertEqual(page["integrityState"], "OK")
            self.assertEqual(page["dropState"], "NO_DROPS")
            self.assertEqual(page["samplingState"], "UNSAMPLED")
            self.assertEqual(page["matchingRecords"], 1)
            self.assertEqual(page["returnedRecords"], 1)
            self.assertEqual(page["rows"][0]["event_id"], "e.12.prod_clean_1.0")
            self.assertEqual(page["declaredScope"]["origins_included"], ["LOCAL_OBSERVATION"])
            self.assertIn("TEST_FIXTURE", page["declaredScope"]["origins_excluded"])
            self.assertEqual(page["schema_status"], "unstable-pre-1.0")
            self.assertTrue(page["scanned_bounded"])
            version = handle.conn.execute("SELECT operational_schema_version FROM records").fetchone()[0]
            self.assertEqual(version, 1)
            wal = Path(str(self.root / "optics" / "store.sqlite") + "-wal")
            self.assertTrue(wal.exists())
            self.assertEqual(stat.S_IMODE(wal.stat().st_mode), 0o600)
        finally:
            handle.close()

    def test_reopen_keeps_the_row(self):
        handle = open_store(self.root, create=True)
        handle.put(clean_record())
        handle.close()
        again = open_store(self.root)
        try:
            self.assertTrue(again.healthy)
            self.assertFalse(again.file_created)
            fetched = again.get(event_id="e.12.prod_clean_1.0")
            self.assertEqual(len(fetched["records"]), 1)
        finally:
            again.close()

    def test_default_origin_excludes_fixture_rows(self):
        handle = open_store(self.root, create=True)
        try:
            handle.put(clean_record())
            fixture = record_with(
                evidence_origin="TEST_FIXTURE",
                event_id="e.12.prod_clean_1.1",
                producer_sequence=1,
                sequence=1,
            )
            stored = handle.put(fixture)
            self.assertTrue(stored["stored"])
            page = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                }
            )
            self.assertEqual(page["matchingRecords"], 1)
            explicit = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                    "origin": "TEST_FIXTURE",
                }
            )
            self.assertEqual(explicit["matchingRecords"], 1)
            self.assertEqual(explicit["rows"][0]["evidence_origin"], "TEST_FIXTURE")
        finally:
            handle.close()

    def test_pagination_uses_an_opaque_cursor(self):
        handle = open_store(self.root, create=True)
        try:
            handle.put(clean_record())
            second = record_with(
                event_id="e.12.prod_clean_1.1",
                producer_sequence=1,
                sequence=1,
                started_at="2026-07-01T00:00:01.000Z",
            )
            self.assertTrue(handle.put(second)["stored"])
            first = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                    "limit": 1,
                    "sort": "started_at_asc",
                }
            )
            self.assertTrue(first["hasMore"])
            self.assertEqual(first["matchingRecords"], 2)
            self.assertEqual(first["returnedRecords"], 1)
            self.assertEqual(first["completeness"], "COMPLETE")
            self.assertIsNotNone(first["next_cursor"])
            self.assertNotIn("SELECT", first["next_cursor"])
            nxt = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                    "limit": 1,
                    "cursor": first["next_cursor"],
                }
            )
            self.assertEqual(nxt["returnedRecords"], 1)
            self.assertNotEqual(nxt["rows"][0]["event_id"], first["rows"][0]["event_id"])
            self.assertFalse(nxt["hasMore"])
        finally:
            handle.close()

    def test_vantio_home_is_the_evidence_root(self):
        previous = os.environ.get("VANTIO_HOME")
        os.environ["VANTIO_HOME"] = str(self.root)
        try:
            handle = open_store(create=True)
            try:
                self.assertTrue((self.root / "optics" / "store.sqlite").is_file())
                self.assertFalse((Path.home() / ".vantio" / "optics" / "store.sqlite").exists())
            finally:
                handle.close()
        finally:
            if previous is None:
                os.environ.pop("VANTIO_HOME", None)
            else:
                os.environ["VANTIO_HOME"] = previous

    def test_legacy_json_is_not_copied(self):
        runs = self.root / "runs"
        runs.mkdir()
        legacy = runs / "legacy.json"
        payload = b'{"vantio_run_log":"1","schema_version":2,"prompt":"leave-me"}\n'
        legacy.write_bytes(payload)
        handle = open_store(self.root, create=True)
        try:
            self.assertEqual(handle.get(run_id="legacy")["records"], [])
            count = handle.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            handle.close()
        self.assertEqual(legacy.read_bytes(), payload)

    def test_source_does_not_set_page_size_or_a_busy_timeout_pragma(self):
        source = (ROOT() / "packages" / "optics-operational-store" / "src" / "optics_operational_store" / "store.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("busy_timeout", source)
        self.assertNotIn("page_size", source)
        self.assertNotIn("PRAGMA key", source)
        self.assertNotIn("sqlcipher", source.lower())


def ROOT():
    return Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    unittest.main()
