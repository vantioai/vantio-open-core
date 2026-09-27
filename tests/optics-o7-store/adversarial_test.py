"""Adversarial tests for the operational store. Caller SQL must not run."""

import json
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from support import CANARY, clean_record, record_with

from optics_operational_store.store import open_store


class AdversarialStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _create(self):
        handle = open_store(self.root, create=True)
        self.assertTrue(handle.healthy, handle.reason_code)
        return handle

    def test_caller_sql_is_rejected_and_does_not_change_the_file(self):
        handle = self._create()
        try:
            rejected = handle.put("DROP TABLE records")
            self.assertFalse(rejected["stored"])
            self.assertEqual(rejected["reason_code"], "SQL_REJECTED")
            self.assertTrue(rejected["application_continues"])
            rejected_arg = handle.put(clean_record(), sql="DELETE FROM records")
            self.assertEqual(rejected_arg["reason_code"], "SQL_REJECTED")
            named = handle.put({**clean_record(), "sql": "DROP TABLE records; " + CANARY})
            self.assertEqual(named["reason_code"], "SQL_REJECTED")
            page = handle.query({"sql": "SELECT * FROM records"})
            self.assertEqual(page["reason_code"], "SQL_REJECTED")
            self.assertEqual(page["rows"], [])
            self.assertNotEqual(page["completeness"], "COMPLETE")
            regex = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                    "pattern": ".*",
                }
            )
            self.assertEqual(regex["reason_code"], "REGEX_REJECTED")
            current = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                    "freshness": "CURRENT",
                }
            )
            self.assertEqual(current["reason_code"], "CURRENT_NOT_EMITTED")
            self.assertNotEqual(current.get("freshness"), "CURRENT")
            missing_time = handle.query({"destination_host": "api.example.com"})
            self.assertEqual(missing_time["reason_code"], "TIME_RANGE_REQUIRED")
            wide = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                    "limit": 501,
                }
            )
            self.assertEqual(wide["reason_code"], "LIMIT_REJECTED")
            injected = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                    "destination_host": "' OR '1'='1",
                }
            )
            self.assertEqual(injected["matchingRecords"], 0)
            names = {
                row[0]
                for row in handle.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            }
            self.assertIn("records", names)
            self.assertNotIn(b"DROP TABLE", (self.root / "optics" / "store.sqlite").read_bytes())
            self.assertNotIn(CANARY.encode("utf-8"), (self.root / "optics" / "store.sqlite").read_bytes())
            self.assertFalse((self.root / "optics" / "store.sqlite.new").exists())
        finally:
            handle.close()

    def test_prompt_canary_never_reaches_the_file_and_counts_as_a_drop(self):
        handle = self._create()
        try:
            handle.put(clean_record())
            dropped = handle.put({**clean_record(), "prompt": CANARY}, application_result={"token": "APP"})
            self.assertFalse(dropped["stored"])
            self.assertEqual(dropped["application_result"]["token"], "APP")
            self.assertTrue(dropped["application_continues"])
            blob = (self.root / "optics" / "store.sqlite").read_bytes()
            wal = Path(str(self.root / "optics" / "store.sqlite") + "-wal")
            if wal.exists():
                blob += wal.read_bytes()
            self.assertNotIn(CANARY.encode("utf-8"), blob)
            page = handle.query(
                {
                    "time_start": "2026-09-27T00:00:00.000Z",
                    "time_end": "2026-09-27T23:59:59.000Z",
                }
            )
            self.assertEqual(page["dropState"], "DROPS_IN_SCOPE")
            self.assertEqual(page["completeness"], "PARTIAL")
            self.assertIn("DROPS_IN_SCOPE", page["completenessReasons"])
            self.assertNotEqual(page["completeness"], "COMPLETE")
            self.assertEqual(page["rows"], [])
        finally:
            handle.close()

    def test_idempotent_duplicate_and_identity_conflict(self):
        handle = self._create()
        try:
            first = handle.put(clean_record())
            second = handle.put(clean_record())
            self.assertTrue(second["duplicate"])
            self.assertEqual(handle.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
            conflict = handle.put(record_with(destination_host="api.example.org"))
            self.assertTrue(conflict["stored"])
            self.assertFalse(conflict["duplicate"])
            rows = handle.get(event_id="e.12.prod_clean_1.0")["records"]
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["identity_conflict"] for row in rows}, {"PRODUCER_SEQUENCE"})
            self.assertEqual(first["record"]["destination_host"], "api.example.com")
        finally:
            handle.close()

    def test_locked_database_fails_open_without_waiting(self):
        holder = self._create()
        other = open_store(self.root)
        try:
            self.assertTrue(other.healthy)
            holder.conn.execute("BEGIN IMMEDIATE")
            result = other.put(clean_record(), application_result={"token": "APP"})
            self.assertFalse(result["stored"])
            self.assertEqual(result["reason_code"], "WRITE_STOPPED")
            self.assertTrue(result["application_continues"])
            self.assertEqual(result["application_result"]["token"], "APP")
            self.assertNotIn("locked", json_text(result).lower())
            holder.conn.execute("ROLLBACK")
        finally:
            other.close()
            holder.close()

    def test_torn_file_is_preserved_and_salvage_is_not_complete(self):
        store = self.root / "optics"
        store.mkdir()
        target = store / "store.sqlite"
        original = b"not-a-database-torn-bytes"
        target.write_bytes(original)
        os.chmod(target, 0o600)
        handle = open_store(self.root, create=True)
        try:
            self.assertFalse(handle.writes_enabled)
            self.assertTrue(handle.application_continues)
            self.assertEqual(handle.reason_code, "INTEGRITY_FAILED")
            self.assertEqual(handle.recovery_state, "STOPPED_PRESERVED")
            self.assertEqual(target.read_bytes(), original)
            self.assertFalse((store / "store.sqlite.new").exists())
            envelope = handle.recovery
            self.assertEqual(envelope["record_type"], "recovery_envelope")
            self.assertEqual(envelope["schema_status"], "unstable-pre-1.0")
            self.assertEqual(envelope["recovery_state"], "STOPPED_PRESERVED")
            self.assertEqual(envelope["integrity_result"], "FAILED")
            self.assertEqual(envelope["remediation_code"], "INTEGRITY_FAILED")
            self.assertIsNone(envelope["replacement_store_id"])
            self.assertNotIn("prompt", envelope)
            self.assertNotIn(CANARY, json_text(envelope))
            self.assertNotIn("/", envelope["safe_store_id"])
            recovery = handle.recovery_path
            self.assertEqual(stat.S_IMODE(recovery.stat().st_mode), 0o600)
            self.assertNotIn(b"hostname", recovery.read_bytes())
            page = handle.query(
                {
                    "time_start": "2026-07-01T00:00:00.000Z",
                    "time_end": "2026-07-01T01:00:00.000Z",
                }
            )
            self.assertEqual(page["completeness"], "UNAVAILABLE")
            self.assertNotEqual(page["completeness"], "COMPLETE")
            self.assertEqual(page["rows"], [])
            salvaged = handle.salvage()
            self.assertIn(salvaged["completeness"], ("PARTIAL", "UNAVAILABLE"))
            self.assertNotEqual(salvaged["completeness"], "COMPLETE")
            self.assertEqual(salvaged["rows"], [])
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(handle.recovery["recovery_state"], "READ_ONLY_SALVAGE")
        finally:
            handle.close()

    def test_newer_schema_and_weaker_writer_do_not_rewrite(self):
        handle = self._create()
        handle.put(clean_record())
        handle.close()
        db = self.root / "optics" / "store.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        conn.close()
        before = db.read_bytes()
        newer = open_store(self.root)
        try:
            self.assertEqual(newer.reason_code, "NEWER_SCHEMA_REFUSED")
            self.assertFalse(newer.writes_enabled)
            self.assertEqual(newer.recovery["remediation_code"], "NEWER_SCHEMA_REFUSED")
            self.assertEqual(newer.recovery["recovery_state"], "RECOVERY_REQUIRED")
            self.assertEqual(newer.recovery["integrity_result"], "OK")
            refused = newer.put(clean_record())
            self.assertFalse(refused["stored"])
        finally:
            newer.close()
        self.assertEqual(db.read_bytes(), before)
        conn = sqlite3.connect(db)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
        conn.execute("PRAGMA user_version = 1")
        conn.execute("UPDATE store_meta SET meta_value = '2' WHERE meta_key = 'privacy_generation'")
        conn.commit()
        conn.close()
        before_privacy = db.read_bytes()
        weaker = open_store(self.root, writer_privacy_generation=1)
        try:
            self.assertEqual(weaker.reason_code, "WEAKER_WRITER_REFUSED")
            self.assertFalse(weaker.writes_enabled)
            self.assertEqual(weaker.recovery["remediation_code"], "WEAKER_WRITER_REFUSED")
            self.assertFalse(weaker.put(clean_record())["stored"])
        finally:
            weaker.close()
        self.assertEqual(db.read_bytes(), before_privacy)

    def test_symlink_escape_does_not_create_an_outside_file(self):
        outside = self.root / "outside"
        outside.mkdir()
        optics = self.root / "evidence" / "optics"
        optics.parent.mkdir()
        optics.symlink_to(outside)
        handle = open_store(self.root / "evidence", create=True)
        self.assertEqual(handle.reason_code, "SYMLINK_REFUSED")
        self.assertFalse(handle.writes_enabled)
        self.assertTrue(handle.application_continues)
        self.assertFalse((outside / "store.sqlite").exists())
        self.assertFalse(list(outside.iterdir()))

    def test_file_symlink_is_not_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        optics = self.root / "optics"
        optics.mkdir()
        (optics / "store.sqlite").symlink_to(outside / "escaped.sqlite")
        handle = open_store(self.root, create=True)
        self.assertEqual(handle.reason_code, "SYMLINK_REFUSED")
        self.assertFalse((outside / "escaped.sqlite").exists())

    def test_migration_fault_keeps_the_file_and_the_backup(self):
        optics = self.root / "optics"
        optics.mkdir()
        db = optics / "store.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()
        before = db.read_bytes()
        failed = open_store(self.root, inject_migration_fault=True)
        try:
            self.assertEqual(failed.reason_code, "MIGRATION_FAILED")
            self.assertFalse(failed.writes_enabled)
            self.assertTrue(failed.application_continues)
            self.assertEqual(failed.recovery["remediation_code"], "MIGRATION_FAILED")
            self.assertEqual(failed.recovery["backup_availability"], "AVAILABLE")
            self.assertIsNone(failed.recovery["replacement_store_id"])
        finally:
            failed.close()
        self.assertEqual(db.read_bytes(), before)
        backup = optics / "store.sqlite.backup"
        self.assertTrue(backup.is_file())
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(backup.read_bytes(), before)
        self.assertFalse((optics / "store.sqlite.new").exists())
        conn = sqlite3.connect(db)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 0)
        conn.close()

    def test_foreign_tables_are_not_replaced(self):
        optics = self.root / "optics"
        optics.mkdir()
        db = optics / "store.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE evil (secret TEXT)")
        conn.execute("INSERT INTO evil (secret) VALUES ('keep')")
        conn.commit()
        conn.close()
        before = db.read_bytes()
        failed = open_store(self.root)
        try:
            self.assertEqual(failed.reason_code, "MIGRATION_FAILED")
            self.assertFalse(failed.writes_enabled)
        finally:
            failed.close()
        conn = sqlite3.connect(db)
        self.assertEqual(conn.execute("SELECT secret FROM evil").fetchone()[0], "keep")
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        conn.close()
        self.assertIn("evil", names)
        self.assertNotIn("records", names)
        self.assertEqual(db.read_bytes(), before)
        self.assertFalse((optics / "store.sqlite.new").exists())

    def test_empty_database_migrates_forward_without_deleting_the_backup(self):
        optics = self.root / "optics"
        optics.mkdir()
        db = optics / "store.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()
        original = db.read_bytes()
        handle = open_store(self.root)
        try:
            self.assertTrue(handle.healthy, handle.reason_code)
            self.assertEqual(handle.user_version, 1)
            self.assertTrue(handle.put(clean_record())["stored"])
        finally:
            handle.close()
        backup = optics / "store.sqlite.backup"
        self.assertEqual(backup.read_bytes(), original)
        self.assertTrue(db.stat().st_size >= len(original))

    def _window(self, **extra):
        window = {
            "time_start": "2026-07-01T00:00:00.000Z",
            "time_end": "2026-07-01T01:00:00.000Z",
        }
        window.update(extra)
        return window

    def _assert_off_page_scope(self, handle, reason):
        full = handle.query(self._window())
        page = handle.query(self._window(limit=1))
        self.assertEqual(full["matchingRecords"], 2)
        self.assertFalse(full["hasMore"])
        self.assertEqual(full["completeness"], "PARTIAL")
        self.assertEqual(full["completenessReasons"], [reason])
        self.assertEqual(page["matchingRecords"], 2)
        self.assertTrue(page["hasMore"])
        self.assertEqual(page["returnedRecords"], 1)
        self.assertEqual(page["rows"][0]["event_id"], "e.12.prod_clean_1.0")
        self.assertEqual(page["completeness"], "PARTIAL")
        self.assertEqual(page["completenessReasons"], full["completenessReasons"])
        self.assertIn(reason, page["completenessReasons"])
        self.assertNotEqual(page["completeness"], "COMPLETE")
        self.assertNotEqual(page["completenessReasons"], [])

    def test_off_page_coverage_gap_is_scope_partial(self):
        handle = self._create()
        try:
            self.assertTrue(handle.put(clean_record())["stored"])
            stored = handle.put(
                record_with(
                    producer_sequence=1,
                    sequence=1,
                    started_at="2026-07-01T00:00:01.000Z",
                    coverage_gap="EVIDENCED",
                )
            )
            self.assertTrue(stored["stored"], stored["reason_code"])
            self.assertEqual(stored["record"]["issue_location"], "COVERAGE")
            gap = handle.conn.execute(
                "SELECT issue_location FROM records WHERE event_id = ?",
                (stored["record"]["event_id"],),
            ).fetchone()[0]
            self.assertEqual(gap, "COVERAGE")
            self._assert_off_page_scope(handle, "COVERAGE_GAP_IN_SCOPE")
        finally:
            handle.close()

    def test_off_page_partial_run_is_scope_partial(self):
        handle = self._create()
        try:
            self.assertTrue(handle.put(clean_record())["stored"])
            stored = handle.put(
                {
                    "record_type": "run_envelope",
                    "schema_status": "unstable-pre-1.0",
                    "schema_version": 0,
                    "producer": "node_interceptor",
                    "cli_or_sdk_version": "0.3.24",
                    "evidence_origin": "LOCAL_OBSERVATION",
                    "producer_id": "prod_clean_1",
                    "run_id": "run_clean_1",
                    "started_at": "2026-07-01T00:00:03.000Z",
                    "lifecycle": "PARTIAL",
                    "identity_conflict": "NONE",
                }
            )
            self.assertTrue(stored["stored"], stored["reason_code"])
            self.assertEqual(stored["record"]["record_type"], "run_envelope")
            self.assertEqual(stored["record"]["lifecycle"], "PARTIAL")
            row = handle.conn.execute(
                "SELECT record_type, lifecycle FROM records WHERE record_type = 'run_envelope'"
            ).fetchone()
            self.assertEqual(tuple(row), ("run_envelope", "PARTIAL"))
            self._assert_off_page_scope(handle, "RUN_LIFECYCLE_NOT_COMPLETE")
        finally:
            handle.close()

    def test_off_page_parent_conflict_is_scope_partial(self):
        handle = self._create()
        try:
            self.assertTrue(handle.put(clean_record())["stored"])
            stored = handle.put(
                record_with(
                    producer_sequence=2,
                    sequence=2,
                    started_at="2026-07-01T00:00:02.000Z",
                    parent_conflict=True,
                )
            )
            self.assertTrue(stored["stored"], stored["reason_code"])
            self.assertEqual(stored["record"]["identity_conflict"], "PARENT")
            body = json.loads(
                handle.conn.execute(
                    "SELECT body_json FROM records WHERE event_id = ?",
                    (stored["record"]["event_id"],),
                ).fetchone()[0]
            )
            self.assertEqual(body["identity_conflict"], "PARENT")
            self._assert_off_page_scope(handle, "PARENT_CONFLICT")
        finally:
            handle.close()

    def test_unreadable_store_fails_open_and_preserves_bytes(self):
        handle = self._create()
        handle.close()
        target = self.root / "optics" / "store.sqlite"
        original = target.read_bytes()
        before = target.stat()
        os.chmod(target, 0)
        opened = None
        try:
            opened = open_store(self.root)
            self.assertFalse(opened.writes_enabled)
            self.assertTrue(opened.application_continues)
            self.assertFalse(opened.file_created)
            self.assertEqual(opened.reason_code, "INTEGRITY_FAILED")
            self.assertEqual(opened.integrity, "UNREADABLE")
            self.assertEqual(opened.recovery_state, "STOPPED_PRESERVED")
            preserved = target.stat()
            self.assertEqual(preserved.st_ino, before.st_ino)
            self.assertEqual(preserved.st_size, before.st_size)
            self.assertEqual(stat.S_IMODE(preserved.st_mode), 0)
            self.assertFalse((self.root / "optics" / "store.sqlite.new").exists())
            envelope = opened.recovery
            self.assertEqual(envelope["record_type"], "recovery_envelope")
            self.assertEqual(envelope["recovery_state"], "STOPPED_PRESERVED")
            self.assertEqual(envelope["integrity_result"], "UNREADABLE")
            self.assertEqual(envelope["remediation_code"], "INTEGRITY_FAILED")
            self.assertIsNone(envelope["preserved_bytes_sha256"])
            self.assertIsNone(envelope["replacement_store_id"])
            self.assertEqual(stat.S_IMODE(opened.recovery_path.stat().st_mode), 0o600)
            page = opened.query(self._window())
            self.assertEqual(page["completeness"], "UNAVAILABLE")
            self.assertNotEqual(page["completeness"], "COMPLETE")
            self.assertEqual(page["rows"], [])
            salvaged = opened.salvage()
            self.assertNotEqual(salvaged["completeness"], "COMPLETE")
            self.assertEqual(salvaged["rows"], [])
            after_salvage = target.stat()
            self.assertEqual(after_salvage.st_ino, before.st_ino)
            self.assertEqual(after_salvage.st_size, before.st_size)
            os.chmod(target, 0o600)
            self.assertEqual(target.read_bytes(), original)
        finally:
            if opened is not None:
                opened.close()
            os.chmod(target, 0o600)

    def test_duplicate_put_with_corrupt_body_fails_open(self):
        handle = self._create()
        try:
            self.assertTrue(handle.put(clean_record())["stored"])
            handle.conn.execute("UPDATE records SET body_json = ?", ("not-json",))
            try:
                again = handle.put(clean_record(), application_result={"token": "APP"})
            except (json.JSONDecodeError, ValueError) as exc:
                self.fail("put raised %s" % type(exc).__name__)
            self.assertFalse(again["stored"])
            self.assertFalse(again["duplicate"])
            self.assertTrue(again["application_continues"])
            self.assertEqual(again["application_result"]["token"], "APP")
            self.assertEqual(again["reason_code"], "REQUIRED_EVIDENCE_CORRUPT")
            self.assertEqual(handle.conn.execute("SELECT body_json FROM records").fetchone()[0], "not-json")
            self.assertEqual(handle.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
            other = record_with(
                producer_sequence=1,
                sequence=1,
                started_at="2026-07-01T00:00:01.000Z",
            )
            followed = handle.put(other, application_result={"token": "APP"})
            self.assertTrue(followed["stored"], followed["reason_code"])
            self.assertEqual(followed["application_result"]["token"], "APP")
        finally:
            handle.close()

    def test_conflict_put_with_corrupt_body_fails_open(self):
        handle = self._create()
        try:
            self.assertTrue(handle.put(clean_record())["stored"])
            handle.conn.execute("UPDATE records SET body_json = ?", ("not-json",))
            conflict = record_with(destination_host="api.example.org")
            try:
                refused = handle.put(conflict, application_result={"token": "APP"})
            except (json.JSONDecodeError, ValueError) as exc:
                self.fail("put raised %s" % type(exc).__name__)
            self.assertFalse(refused["stored"])
            self.assertTrue(refused["application_continues"])
            self.assertEqual(refused["application_result"]["token"], "APP")
            self.assertEqual(refused["reason_code"], "REQUIRED_EVIDENCE_CORRUPT")
            self.assertEqual(handle.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
            self.assertEqual(handle.conn.execute("SELECT body_json FROM records").fetchone()[0], "not-json")
        finally:
            handle.close()

    def test_missing_lifecycle_is_not_scope_complete(self):
        handle = self._create()
        try:
            self.assertTrue(handle.put(clean_record())["stored"])
            stored = handle.put(
                {
                    "record_type": "run_envelope",
                    "schema_status": "unstable-pre-1.0",
                    "schema_version": 0,
                    "producer": "node_interceptor",
                    "cli_or_sdk_version": "0.3.24",
                    "evidence_origin": "LOCAL_OBSERVATION",
                    "producer_id": "prod_clean_1",
                    "run_id": "run_clean_1",
                    "started_at": "2026-07-01T00:00:03.000Z",
                    "identity_conflict": "NONE",
                }
            )
            self.assertTrue(stored["stored"], stored["reason_code"])
            self.assertEqual(stored["record"]["record_type"], "run_envelope")
            self.assertNotIn("lifecycle", stored["record"])
            column = handle.conn.execute(
                "SELECT lifecycle FROM records WHERE record_type = 'run_envelope'"
            ).fetchone()
            self.assertIsNone(column[0])
            self._assert_off_page_scope(handle, "RUN_LIFECYCLE_NOT_COMPLETE")
        finally:
            handle.close()

    def test_unsearchable_optics_directory_fails_open(self):
        handle = self._create()
        self.assertTrue(handle.put(clean_record())["stored"])
        handle.close()
        optics = self.root / "optics"
        target = optics / "store.sqlite"
        original = target.read_bytes()
        before = target.stat()
        os.chmod(optics, 0)
        opened = None
        try:
            try:
                opened = open_store(self.root)
            except PermissionError as exc:
                self.fail("open_store raised PermissionError: %s" % exc)
            self.assertFalse(opened.writes_enabled)
            self.assertTrue(opened.application_continues)
            self.assertFalse(opened.file_created)
            self.assertEqual(opened.reason_code, "INTEGRITY_FAILED")
            self.assertEqual(opened.integrity, "UNREADABLE")
            self.assertEqual(opened.recovery_state, "STOPPED_PRESERVED")
            self.assertEqual(stat.S_IMODE(optics.stat().st_mode), 0)
            envelope = opened.recovery
            self.assertIsNotNone(envelope)
            self.assertEqual(envelope["record_type"], "recovery_envelope")
            self.assertEqual(envelope["recovery_state"], "STOPPED_PRESERVED")
            self.assertEqual(envelope["integrity_result"], "UNREADABLE")
            self.assertEqual(envelope["remediation_code"], "INTEGRITY_FAILED")
            self.assertEqual(envelope["safe_store_id"], "store-id-unreadable")
            self.assertIsNone(envelope["preserved_bytes_sha256"])
            self.assertIsNone(envelope["replacement_store_id"])
            self.assertNotIn("prompt", envelope)
            self.assertNotIn(CANARY, json_text(envelope))
            recovery = opened.recovery_path
            self.assertIsNotNone(recovery)
            self.assertEqual(recovery.parent.name, "optics-recovery")
            self.assertEqual(recovery.name, "store-id-unreadable.recovery.json")
            self.assertEqual(recovery.resolve().parent, (self.root / "optics-recovery").resolve())
            self.assertEqual(stat.S_IMODE(recovery.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(recovery.parent.stat().st_mode), 0o700)
            self.assertNotIn(b"hostname", recovery.read_bytes())
            page = opened.query(self._window())
            self.assertEqual(page["completeness"], "UNAVAILABLE")
            self.assertNotEqual(page["completeness"], "COMPLETE")
            self.assertEqual(page["rows"], [])
            try:
                salvaged = opened.salvage()
            except PermissionError as exc:
                self.fail("salvage raised PermissionError: %s" % exc)
            self.assertNotEqual(salvaged["completeness"], "COMPLETE")
            self.assertEqual(salvaged["rows"], [])
            self.assertEqual(stat.S_IMODE(optics.stat().st_mode), 0)
            try:
                again = open_store(self.root, create=True)
            except PermissionError as exc:
                self.fail("open_store create=True raised PermissionError: %s" % exc)
            try:
                self.assertEqual(again.recovery_state, "STOPPED_PRESERVED")
                self.assertFalse(again.file_created)
                self.assertFalse(again.writes_enabled)
            finally:
                again.close()
        finally:
            if opened is not None:
                opened.close()
            os.chmod(optics, 0o700)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode) & 0o777, 0o600)
        preserved = target.stat()
        self.assertEqual(preserved.st_ino, before.st_ino)
        self.assertEqual(preserved.st_size, before.st_size)
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse((optics / "store.sqlite.new").exists())
        self.assertFalse((optics / "recovery").exists())


def json_text(value):
    return json.dumps(value)


if __name__ == "__main__":
    unittest.main()
