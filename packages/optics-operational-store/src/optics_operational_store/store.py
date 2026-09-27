"""Application-owned operational store.

Callers use put, get, and the query request. A caller-supplied SQL string is
rejected. The schema below is executed only by this module.

schema_status stays unstable-pre-1.0. operational_schema_version 1 is the
first migrator this module writes. It is not the legacy JSON schema_version 2
and it is not a stable schema. Evidence tier stays UNSET.
"""

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from optics_operational_store.posture import (
    EVIDENCE_TIER,
    NODE_BINDING,
    OPERATIONAL_SCHEMA_VERSION,
    PACKAGE_VERSION,
    PRIVACY_GENERATION,
    SCHEMA_STATUS,
)

_CONTRACT_SRC = Path(__file__).resolve().parents[4] / "packages" / "optics-evidence-contract" / "src"
if str(_CONTRACT_SRC) not in sys.path:
    sys.path.insert(0, str(_CONTRACT_SRC))

import validate as evidence_validate  # noqa: E402

MAX_OPERATIONAL_VERSION = OPERATIONAL_SCHEMA_VERSION
WRITER_PRIVACY_GENERATION = PRIVACY_GENERATION
QUERY_LIMIT_DEFAULT = 100
QUERY_LIMIT_MAX = 500
STORE_NAME = "store.sqlite"
ID_NAME = "store.id"
BACKUP_NAME = "store.sqlite.backup"
UNREADABLE_STORE_ID = "store-id-unreadable"
LIMITATION = "Operational store page. Not a portable proof."
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$")
SAFE_ID_RE = re.compile(r"^[0-9a-f]{32}$")

EXCLUDED_ORIGINS = (
    "LEGACY_UNMARKED",
    "SIMULATED_DEMO",
    "IMPORTED",
    "TEST_FIXTURE",
    "PRODUCT_HEALTH",
    "DERIVED_DIAGNOSTIC",
)
KNOWN_ORIGINS = frozenset(("LOCAL_OBSERVATION",) + EXCLUDED_ORIGINS)
REQUEST_FIELDS = frozenset(
    {
        "time_start",
        "time_end",
        "run_id",
        "session_id",
        "trace_id",
        "process_id",
        "provider_id",
        "destination_host",
        "application_status",
        "optics_status",
        "issue_location",
        "http_status",
        "duration_min_ms",
        "duration_max_ms",
        "lifecycle",
        "coverage",
        "origin",
        "freshness",
        "limit",
        "cursor",
        "sort",
    }
)
SQL_FIELDS = frozenset({"sql", "statement", "where", "query"})
REGEX_FIELDS = frozenset({"regex", "regexp", "pattern"})
ENVELOPE_KEYS = (
    "record_type",
    "schema_status",
    "safe_store_id",
    "schema_version",
    "product_version",
    "failure_timestamp",
    "integrity_result",
    "recovery_state",
    "last_known_successful_integrity_check",
    "remediation_code",
    "backup_availability",
    "preserved_bytes_sha256",
    "replacement_store_id",
)
IDENTITY_FIELDS = (
    "record_type",
    "event_id",
    "run_id",
    "trace_id",
    "destination_host",
    "producer_id",
    "evidence_origin",
)
FILTER_SQL = {
    "run_id": "run_id = ?",
    "session_id": "session_id = ?",
    "trace_id": "trace_id = ?",
    "process_id": "process_id = ?",
    "provider_id": "provider_id = ?",
    "destination_host": "destination_host = ?",
    "application_status": "application_status = ?",
    "optics_status": "optics_status = ?",
    "issue_location": "issue_location = ?",
    "http_status": "http_status = ?",
    "lifecycle": "lifecycle = ?",
    "coverage": "coverage = ?",
    "origin": "evidence_origin = ?",
}


def _now():
    moment = datetime.now(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _detach(value):
    if value is None:
        return None
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError):
        return None


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unreadable_open(paths):
    handle = StoreHandle(paths)
    envelope, target = _write_envelope(
        paths,
        _read_store_id(paths["store_id"]),
        None,
        "UNREADABLE",
        "STOPPED_PRESERVED",
        "INTEGRITY_FAILED",
        None,
        "ABSENT" if not paths["backup"].exists() else "AVAILABLE",
        None,
    )
    _note_envelope(handle, envelope, target, "STOPPED_PRESERVED")
    handle.reason_code = "INTEGRITY_FAILED"
    handle.integrity = "UNREADABLE"
    return handle


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _chmod_file(path):
    if path.exists() and not path.is_symlink():
        os.chmod(path, 0o600)


def _chmod_dir(path):
    if path.exists() and not path.is_symlink():
        os.chmod(path, 0o700)


def _write_new(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def _evidence_root(explicit):
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    override = os.environ.get("VANTIO_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".vantio").resolve()


def _paths(root):
    optics = root / "optics"
    return {
        "root": root,
        "optics": optics,
        "store": optics / STORE_NAME,
        "store_id": optics / ID_NAME,
        "backup": optics / BACKUP_NAME,
        "recovery_dir": optics / "recovery",
        "wal": Path(str(optics / STORE_NAME) + "-wal"),
        "shm": Path(str(optics / STORE_NAME) + "-shm"),
    }


def _symlink_blocked(paths):
    for key in ("optics", "store", "store_id", "backup", "recovery_dir", "wal", "shm"):
        candidate = paths[key]
        if candidate.is_symlink():
            return True
    return False


def _ro_uri(path):
    return "file:" + quote(path.as_posix(), safe="/") + "?mode=ro"


def _connect(path, readonly):
    # timeout 0 does not wait on a lock. It is not an NFR busy-timeout selection.
    if readonly:
        return sqlite3.connect(_ro_uri(path), uri=True, timeout=0, isolation_level=None)
    return sqlite3.connect(path, timeout=0, isolation_level=None)


def _journal_is_wal(conn):
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    return row is not None and str(row[0]).lower() == "wal"


def _integrity_ok(conn):
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error:
        return False
    if len(rows) != 1:
        return False
    return str(rows[0][0]).lower() == "ok"


def _user_version(conn):
    try:
        row = conn.execute("PRAGMA user_version").fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return None


def _table_names(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall()
    return {str(row[0]) for row in rows}


def _read_meta(conn):
    if "store_meta" not in _table_names(conn):
        return None
    rows = conn.execute("SELECT meta_key, meta_value FROM store_meta").fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def _install_schema(conn, store_id, checked_at):
    statements = [
        """
        CREATE TABLE IF NOT EXISTS store_meta (
          meta_key TEXT PRIMARY KEY,
          meta_value TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS records (
          row_id INTEGER PRIMARY KEY,
          record_type TEXT NOT NULL,
          operational_schema_version INTEGER NOT NULL,
          privacy_generation INTEGER NOT NULL,
          body_json TEXT NOT NULL,
          identity_hash TEXT NOT NULL,
          event_id TEXT,
          run_id TEXT,
          session_id TEXT,
          trace_id TEXT,
          process_id TEXT,
          provider_id TEXT,
          destination_host TEXT,
          application_status TEXT,
          optics_status TEXT,
          issue_location TEXT,
          http_status INTEGER,
          lifecycle TEXT,
          evidence_origin TEXT,
          coverage TEXT,
          started_at TEXT,
          duration_ms INTEGER,
          producer_id TEXT,
          producer_sequence INTEGER,
          sampling TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS drops (
          drop_id INTEGER PRIMARY KEY,
          dropped_at TEXT NOT NULL,
          drop_count INTEGER NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS records_started_at ON records (started_at, producer_id, producer_sequence, event_id, row_id)",
        "CREATE INDEX IF NOT EXISTS records_run_id ON records (run_id)",
        "CREATE INDEX IF NOT EXISTS records_event_id ON records (event_id)",
        "CREATE INDEX IF NOT EXISTS records_origin_time ON records (evidence_origin, started_at)",
        "CREATE INDEX IF NOT EXISTS drops_dropped_at ON drops (dropped_at)",
    ]
    for statement in statements:
        conn.execute(statement)
    meta = {
        "schema_status": SCHEMA_STATUS,
        "operational_schema_version": str(OPERATIONAL_SCHEMA_VERSION),
        "privacy_generation": str(WRITER_PRIVACY_GENERATION),
        "safe_store_id": store_id,
        "migration_state": "IDLE",
        "last_known_successful_integrity_check": checked_at,
    }
    for key, value in meta.items():
        conn.execute(
            "INSERT INTO store_meta (meta_key, meta_value) VALUES (?, ?) "
            "ON CONFLICT(meta_key) DO UPDATE SET meta_value = excluded.meta_value",
            (key, value),
        )
    conn.execute("PRAGMA user_version = %d" % OPERATIONAL_SCHEMA_VERSION)


def _read_store_id(path):
    if not path.exists() or path.is_symlink():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if SAFE_ID_RE.fullmatch(text):
        return text
    return None


def _write_store_id(path, store_id):
    if path.exists():
        return _read_store_id(path) == store_id
    if path.is_symlink():
        return False
    _write_new(path, (store_id + "\n").encode("ascii"))
    return True


def _envelope_path(paths, store_id):
    safe = store_id if store_id and SAFE_ID_RE.fullmatch(store_id) else UNREADABLE_STORE_ID
    return paths["recovery_dir"] / f"{safe}.recovery.json", safe


def _write_envelope(paths, store_id, schema_version, integrity_result, recovery_state, remediation_code, preserved_hash, backup_availability, last_check):
    if paths["recovery_dir"].is_symlink() or paths["optics"].is_symlink():
        return None, None
    try:
        paths["recovery_dir"].mkdir(mode=0o700, exist_ok=True)
    except OSError:
        return None, None
    if paths["recovery_dir"].is_symlink():
        return None, None
    _chmod_dir(paths["recovery_dir"])
    target, safe_id = _envelope_path(paths, store_id)
    if target.is_symlink():
        return None, None
    envelope = {
        "record_type": "recovery_envelope",
        "schema_status": SCHEMA_STATUS,
        "safe_store_id": safe_id,
        "schema_version": schema_version,
        "product_version": PACKAGE_VERSION,
        "failure_timestamp": _now(),
        "integrity_result": integrity_result,
        "recovery_state": recovery_state,
        "last_known_successful_integrity_check": last_check,
        "remediation_code": remediation_code,
        "backup_availability": backup_availability,
        "preserved_bytes_sha256": preserved_hash,
        "replacement_store_id": None,
    }
    if set(envelope.keys()) != set(ENVELOPE_KEYS):
        return None, None
    payload = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    temporary = paths["recovery_dir"] / f".{safe_id}.recovery.json.tmp"
    try:
        if temporary.exists() or temporary.is_symlink():
            return None, None
        _write_new(temporary, payload)
        os.replace(temporary, target)
    except OSError:
        return None, None
    _chmod_file(target)
    return envelope, target


def _backup_database(paths):
    source = paths["store"]
    target = paths["backup"]
    if target.is_symlink() or source.is_symlink():
        return "UNKNOWN"
    if target.exists():
        return "AVAILABLE"
    try:
        _write_new(target, source.read_bytes())
    except OSError:
        return "UNKNOWN"
    return "AVAILABLE"


def _chmod_sidecars(paths):
    for key in ("store", "wal", "shm", "store_id", "backup"):
        _chmod_file(paths[key])


class StoreHandle(object):
    def __init__(self, paths):
        self.paths = paths
        self.opened = False
        self.healthy = False
        self.writes_enabled = False
        self.application_continues = True
        self.default_write_path = False
        self.evidence_tier = EVIDENCE_TIER
        self.node_binding = NODE_BINDING
        self.schema_status = SCHEMA_STATUS
        self.reason_code = None
        self.file_created = False
        self.conn = None
        self.safe_store_id = None
        self.user_version = None
        self.privacy_generation = None
        self.integrity = "UNKNOWN"
        self.recovery = None
        self.recovery_path = None
        self.recovery_state = None
        self.diagnostic_failures = 0
        self._last_check = None

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        _chmod_sidecars(self.paths)

    def put(self, record, application_result=None, sql=None, statement=None):
        return put(self, record, application_result=application_result, sql=sql, statement=statement)

    def get(self, event_id=None, run_id=None, sql=None, statement=None):
        return get(self, event_id=event_id, run_id=run_id, sql=sql, statement=statement)

    def query(self, request=None):
        return query(self, request)

    def salvage(self):
        return salvage(self)


def _stopped(paths, reason, integrity="UNKNOWN"):
    handle = StoreHandle(paths)
    handle.reason_code = reason
    handle.integrity = integrity
    return handle


def _note_envelope(handle, envelope, path, state):
    handle.recovery = envelope
    handle.recovery_path = path
    handle.recovery_state = state
    return handle


def open_store(evidence_root=None, create=False, writer_privacy_generation=WRITER_PRIVACY_GENERATION, inject_migration_fault=False, sql=None, statement=None, **_ignored):
    # PKG-02 writer flags are not this package's create switch. They never open a binding.
    del _ignored
    root = _evidence_root(evidence_root)
    paths = _paths(root)
    if sql is not None or statement is not None:
        return _stopped(paths, "SQL_REJECTED")
    if _symlink_blocked(paths):
        return _stopped(paths, "SYMLINK_REFUSED")
    store_path = paths["store"]
    if not store_path.exists():
        if not create:
            return _stopped(paths, "STORE_ABSENT")
        if not root.exists() or not root.is_dir() or root.is_symlink():
            return _stopped(paths, "STORE_ROOT_ABSENT")
        return _create_store(paths)
    if not store_path.is_file():
        return _stopped(paths, "STORE_NOT_A_FILE")
    try:
        before = _sha256_file(store_path)
    except OSError:
        return _unreadable_open(paths)
    return _open_existing(paths, before, writer_privacy_generation, inject_migration_fault)


def _create_store(paths):
    handle = StoreHandle(paths)
    try:
        paths["optics"].mkdir(mode=0o700, exist_ok=True)
    except OSError:
        handle.reason_code = "STORE_UNAVAILABLE"
        return handle
    if paths["optics"].is_symlink() or paths["store"].exists() or paths["store"].is_symlink():
        handle.reason_code = "SYMLINK_REFUSED" if paths["store"].is_symlink() else "STORE_UNAVAILABLE"
        return handle
    _chmod_dir(paths["optics"])
    store_id = secrets.token_hex(16)
    try:
        conn = _connect(paths["store"], readonly=False)
    except sqlite3.Error:
        handle.reason_code = "STORE_UNAVAILABLE"
        return handle
    handle.file_created = True
    _chmod_file(paths["store"])
    try:
        if not _journal_is_wal(conn):
            conn.close()
            handle.reason_code = "WAL_UNAVAILABLE"
            return handle
        checked_at = _now()
        conn.execute("BEGIN IMMEDIATE")
        _install_schema(conn, store_id, checked_at)
        conn.execute("COMMIT")
    except sqlite3.Error:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        conn.close()
        handle.reason_code = "STORE_UNAVAILABLE"
        return handle
    if not _write_store_id(paths["store_id"], store_id):
        conn.close()
        handle.reason_code = "STORE_UNAVAILABLE"
        return handle
    handle.conn = conn
    handle.opened = True
    handle.healthy = True
    handle.writes_enabled = True
    handle.safe_store_id = store_id
    handle.user_version = OPERATIONAL_SCHEMA_VERSION
    handle.privacy_generation = WRITER_PRIVACY_GENERATION
    handle.integrity = "OK"
    handle._last_check = checked_at
    handle.reason_code = "OK"
    _chmod_sidecars(paths)
    return handle


def _open_existing(paths, before_hash, writer_privacy_generation, inject_migration_fault):
    handle = StoreHandle(paths)
    try:
        probe = _connect(paths["store"], readonly=True)
    except OSError:
        return _unreadable_open(paths)
    except sqlite3.Error:
        try:
            after = _sha256_file(paths["store"])
        except OSError:
            return _unreadable_open(paths)
        preserved = before_hash if after == before_hash else None
        envelope, target = _write_envelope(
            paths,
            _read_store_id(paths["store_id"]),
            None,
            "UNREADABLE",
            "STOPPED_PRESERVED",
            "INTEGRITY_FAILED",
            preserved,
            "ABSENT" if not paths["backup"].exists() else "AVAILABLE",
            None,
        )
        _note_envelope(handle, envelope, target, "STOPPED_PRESERVED")
        handle.reason_code = "INTEGRITY_FAILED"
        handle.integrity = "UNREADABLE"
        return handle
    try:
        version = _user_version(probe)
        intact = _integrity_ok(probe)
        meta = _read_meta(probe) if intact else None
        names = _table_names(probe) if intact else set()
    except sqlite3.Error:
        intact = False
        version = None
        meta = None
        names = set()
    probe.close()
    after = _sha256_file(paths["store"])
    if after != before_hash:
        handle.reason_code = "BYTES_CHANGED"
        handle.integrity = "FAILED"
        return handle
    sidecar_id = _read_store_id(paths["store_id"])
    last_check = None if meta is None else meta.get("last_known_successful_integrity_check")
    allowed_tables = {"store_meta", "records", "drops"}
    if intact and not names <= allowed_tables:
        return _migration_stopped(paths, handle, before_hash, sidecar_id, version, last_check)
    if not intact:
        envelope, target = _write_envelope(
            paths,
            sidecar_id,
            version,
            "FAILED",
            "STOPPED_PRESERVED",
            "INTEGRITY_FAILED",
            before_hash,
            "ABSENT" if not paths["backup"].exists() else "AVAILABLE",
            last_check,
        )
        _note_envelope(handle, envelope, target, "STOPPED_PRESERVED")
        handle.reason_code = "INTEGRITY_FAILED"
        handle.integrity = "FAILED"
        handle.user_version = version
        return handle
    if version is not None and version > MAX_OPERATIONAL_VERSION:
        envelope, target = _write_envelope(
            paths,
            sidecar_id,
            version,
            "OK",
            "RECOVERY_REQUIRED",
            "NEWER_SCHEMA_REFUSED",
            before_hash,
            "ABSENT" if not paths["backup"].exists() else "AVAILABLE",
            last_check,
        )
        _note_envelope(handle, envelope, target, "RECOVERY_REQUIRED")
        handle.reason_code = "NEWER_SCHEMA_REFUSED"
        handle.integrity = "OK"
        handle.user_version = version
        return handle
    needs_migration = version is None or version < OPERATIONAL_SCHEMA_VERSION or "store_meta" not in names
    if needs_migration:
        return _migrate(paths, handle, before_hash, sidecar_id, last_check, inject_migration_fault)
    if meta is None:
        return _migration_stopped(paths, handle, before_hash, sidecar_id, version, last_check)
    try:
        stored_privacy = int(meta.get("privacy_generation", "0"))
        stored_operational = int(meta.get("operational_schema_version", "0"))
    except ValueError:
        return _migration_stopped(paths, handle, before_hash, sidecar_id, version, last_check)
    if stored_operational > MAX_OPERATIONAL_VERSION:
        envelope, target = _write_envelope(
            paths,
            sidecar_id or meta.get("safe_store_id"),
            version,
            "OK",
            "RECOVERY_REQUIRED",
            "NEWER_SCHEMA_REFUSED",
            before_hash,
            "ABSENT" if not paths["backup"].exists() else "AVAILABLE",
            last_check,
        )
        _note_envelope(handle, envelope, target, "RECOVERY_REQUIRED")
        handle.reason_code = "NEWER_SCHEMA_REFUSED"
        handle.integrity = "OK"
        handle.user_version = version
        return handle
    if writer_privacy_generation < stored_privacy:
        envelope, target = _write_envelope(
            paths,
            sidecar_id or meta.get("safe_store_id"),
            version,
            "OK",
            "RECOVERY_REQUIRED",
            "WEAKER_WRITER_REFUSED",
            before_hash,
            "ABSENT" if not paths["backup"].exists() else "AVAILABLE",
            last_check,
        )
        _note_envelope(handle, envelope, target, "RECOVERY_REQUIRED")
        handle.reason_code = "WEAKER_WRITER_REFUSED"
        handle.integrity = "OK"
        handle.user_version = version
        handle.privacy_generation = stored_privacy
        return handle
    meta_id = meta.get("safe_store_id")
    if not meta_id or not SAFE_ID_RE.fullmatch(meta_id):
        return _migration_stopped(paths, handle, before_hash, sidecar_id, version, last_check)
    if sidecar_id is not None and sidecar_id != meta_id:
        return _migration_stopped(paths, handle, before_hash, sidecar_id, version, last_check)
    try:
        conn = _connect(paths["store"], readonly=False)
        if not _journal_is_wal(conn):
            conn.close()
            handle.reason_code = "WAL_UNAVAILABLE"
            handle.integrity = "OK"
            return handle
    except sqlite3.Error:
        handle.reason_code = "STORE_UNAVAILABLE"
        handle.integrity = "OK"
        return handle
    if not _write_store_id(paths["store_id"], meta_id):
        conn.close()
        handle.reason_code = "STORE_UNAVAILABLE"
        return handle
    checked_at = _now()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE store_meta SET meta_value = ? WHERE meta_key = ?",
            (checked_at, "last_known_successful_integrity_check"),
        )
        conn.execute("COMMIT")
    except sqlite3.Error:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        conn.close()
        handle.reason_code = "STORE_UNAVAILABLE"
        return handle
    handle.conn = conn
    handle.opened = True
    handle.healthy = True
    handle.writes_enabled = True
    handle.safe_store_id = meta_id
    handle.user_version = version
    handle.privacy_generation = stored_privacy
    handle.integrity = "OK"
    handle._last_check = checked_at
    handle.reason_code = "OK"
    _chmod_sidecars(paths)
    return handle


def _migration_stopped(paths, handle, before_hash, store_id, version, last_check):
    backup = _backup_database(paths)
    after = _sha256_file(paths["store"])
    preserved = before_hash if after == before_hash else None
    envelope, target = _write_envelope(
        paths,
        store_id,
        version,
        "OK",
        "RECOVERY_REQUIRED",
        "MIGRATION_FAILED",
        preserved,
        backup,
        last_check,
    )
    _note_envelope(handle, envelope, target, "RECOVERY_REQUIRED")
    handle.reason_code = "MIGRATION_FAILED"
    handle.integrity = "OK"
    handle.user_version = version
    return handle


def _migrate(paths, handle, before_hash, store_id, last_check, inject_migration_fault):
    backup = _backup_database(paths)
    if backup != "AVAILABLE":
        envelope, target = _write_envelope(
            paths,
            store_id,
            0,
            "OK",
            "RECOVERY_REQUIRED",
            "MIGRATION_FAILED",
            before_hash,
            backup,
            last_check,
        )
        _note_envelope(handle, envelope, target, "RECOVERY_REQUIRED")
        handle.reason_code = "MIGRATION_FAILED"
        handle.integrity = "OK"
        return handle
    try:
        conn = _connect(paths["store"], readonly=False)
    except sqlite3.Error:
        return _migration_failure(paths, handle, before_hash, store_id, last_check)
    try:
        if inject_migration_fault:
            conn.close()
            return _migration_failure(paths, handle, before_hash, store_id, last_check)
        names = _table_names(conn)
        foreign = names - {"store_meta", "records", "drops"}
        if foreign:
            conn.close()
            return _migration_failure(paths, handle, before_hash, store_id, last_check)
        if not _journal_is_wal(conn):
            conn.close()
            return _migration_failure(paths, handle, before_hash, store_id, last_check)
        minted = store_id or secrets.token_hex(16)
        checked_at = _now()
        conn.execute("BEGIN IMMEDIATE")
        _install_schema(conn, minted, checked_at)
        conn.execute("COMMIT")
    except sqlite3.Error:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        conn.close()
        return _migration_failure(paths, handle, before_hash, store_id, last_check)
    if not _write_store_id(paths["store_id"], minted):
        conn.close()
        return _migration_failure(paths, handle, before_hash, store_id, last_check)
    handle.conn = conn
    handle.opened = True
    handle.healthy = True
    handle.writes_enabled = True
    handle.safe_store_id = minted
    handle.user_version = OPERATIONAL_SCHEMA_VERSION
    handle.privacy_generation = WRITER_PRIVACY_GENERATION
    handle.integrity = "OK"
    handle._last_check = checked_at
    handle.reason_code = "OK"
    _chmod_sidecars(paths)
    return handle


def _migration_failure(paths, handle, before_hash, store_id, last_check):
    after = _sha256_file(paths["store"])
    preserved = before_hash if after == before_hash else None
    version = None
    try:
        probe = _connect(paths["store"], readonly=True)
        version = _user_version(probe)
        probe.close()
    except sqlite3.Error:
        version = None
    envelope, target = _write_envelope(
        paths,
        store_id,
        version,
        "OK",
        "RECOVERY_REQUIRED",
        "MIGRATION_FAILED",
        preserved,
        "AVAILABLE" if paths["backup"].exists() else "ABSENT",
        last_check,
    )
    _note_envelope(handle, envelope, target, "RECOVERY_REQUIRED")
    handle.reason_code = "MIGRATION_FAILED"
    handle.integrity = "OK"
    handle.user_version = version
    return handle


def _reject_sql(sql, statement):
    return sql is not None or statement is not None


def _rollback(conn):
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        pass


def _load_stored_body(text):
    try:
        loaded = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _corrupt_body_result(handle, application_result):
    _rollback(handle.conn)
    if handle.diagnostic_failures == 0:
        handle.diagnostic_failures = 1
    return _result(False, "REQUIRED_EVIDENCE_CORRUPT", application_result)


def _result(stored, reason, application_result, record=None, duplicate=False):
    return {
        "application_continues": True,
        "application_result": _detach(application_result),
        "default_write_path": False,
        "duplicate": duplicate,
        "evidence_tier": EVIDENCE_TIER,
        "reason_code": reason,
        "record": record,
        "schema_status": SCHEMA_STATUS,
        "stored": stored,
        "writes_enabled": stored,
    }


def _note_drop(handle):
    if handle.conn is None or not handle.writes_enabled:
        handle.diagnostic_failures += 1
        return
    try:
        handle.conn.execute("BEGIN IMMEDIATE")
        handle.conn.execute(
            "INSERT INTO drops (dropped_at, drop_count) VALUES (?, ?)",
            (_now(), 1),
        )
        handle.conn.execute("COMMIT")
    except sqlite3.Error:
        try:
            handle.conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        if handle.diagnostic_failures == 0:
            handle.diagnostic_failures = 1


def _identity_hash(record):
    payload = {name: record.get(name) for name in IDENTITY_FIELDS}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _column_text(record, name):
    value = record.get(name)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return None


def _column_int(record, name):
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def put(handle, record, application_result=None, sql=None, statement=None):
    if _reject_sql(sql, statement) or isinstance(record, str):
        return _result(False, "SQL_REJECTED", application_result)
    if isinstance(record, dict) and (SQL_FIELDS & set(record.keys())):
        return _result(False, "SQL_REJECTED", application_result)
    if not handle.writes_enabled or handle.conn is None:
        return _result(False, handle.reason_code or "WRITE_STOPPED", application_result)
    if not isinstance(record, dict):
        _note_drop(handle)
        return _result(False, "REJECT_RECORD", application_result)
    try:
        validated = evidence_validate.validate_evidence(record, {"applicationResult": application_result})
    except Exception:
        if handle.diagnostic_failures == 0:
            handle.diagnostic_failures = 1
        return _result(False, "VALIDATOR_FAULT", application_result)
    emitted = validated.get("record") if isinstance(validated, dict) else None
    if not isinstance(emitted, dict):
        _note_drop(handle)
        reason = validated.get("reason_code") if isinstance(validated, dict) else "REJECT_RECORD"
        return _result(False, reason or "REJECT_RECORD", application_result)
    body = json.dumps(emitted, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    identity = _identity_hash(emitted)
    event_id = _column_text(emitted, "event_id")
    try:
        handle.conn.execute("BEGIN IMMEDIATE")
        if event_id is not None:
            existing = handle.conn.execute(
                "SELECT body_json, identity_hash FROM records WHERE event_id = ?",
                (event_id,),
            ).fetchall()
        else:
            existing = []
        same = [row for row in existing if row[1] == identity]
        if same:
            loaded = _load_stored_body(same[0][0])
            if loaded is None:
                return _corrupt_body_result(handle, application_result)
            handle.conn.execute("COMMIT")
            return _result(True, "IDEMPOTENT_DUPLICATE", application_result, loaded, duplicate=True)
        if existing:
            emitted = dict(emitted)
            emitted["identity_conflict"] = "PRODUCER_SEQUENCE"
            body = json.dumps(emitted, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            rewritten = []
            for row in existing:
                previous = _load_stored_body(row[0])
                if previous is None:
                    return _corrupt_body_result(handle, application_result)
                previous["identity_conflict"] = "PRODUCER_SEQUENCE"
                rewritten.append((previous, row[1]))
            for previous, previous_hash in rewritten:
                handle.conn.execute(
                    "UPDATE records SET body_json = ? WHERE event_id = ? AND identity_hash = ?",
                    (
                        json.dumps(previous, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                        event_id,
                        previous_hash,
                    ),
                )
        handle.conn.execute(
            """
            INSERT INTO records (
              record_type, operational_schema_version, privacy_generation, body_json, identity_hash,
              event_id, run_id, session_id, trace_id, process_id, provider_id, destination_host,
              application_status, optics_status, issue_location, http_status, lifecycle,
              evidence_origin, coverage, started_at, duration_ms, producer_id, producer_sequence, sampling
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _column_text(emitted, "record_type") or "observation_event",
                OPERATIONAL_SCHEMA_VERSION,
                WRITER_PRIVACY_GENERATION,
                body,
                _identity_hash(emitted),
                event_id,
                _column_text(emitted, "run_id"),
                _column_text(emitted, "session_id"),
                _column_text(emitted, "trace_id"),
                None if emitted.get("process_id") is None else str(emitted.get("process_id")),
                _column_text(emitted, "provider_id"),
                _column_text(emitted, "destination_host"),
                _column_text(emitted, "application_status"),
                _column_text(emitted, "optics_status"),
                _column_text(emitted, "issue_location"),
                _column_int(emitted, "http_status"),
                _column_text(emitted, "lifecycle"),
                _column_text(emitted, "evidence_origin"),
                _column_text(emitted, "coverage"),
                _column_text(emitted, "started_at"),
                _column_int(emitted, "duration_ms"),
                _column_text(emitted, "producer_id"),
                _column_int(emitted, "producer_sequence"),
                _column_text(emitted, "sampling"),
            ),
        )
        handle.conn.execute("COMMIT")
    except sqlite3.Error:
        try:
            handle.conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        if handle.diagnostic_failures == 0:
            handle.diagnostic_failures = 1
        return _result(False, "WRITE_STOPPED", application_result)
    _chmod_sidecars(handle.paths)
    return _result(True, "OK", application_result, json.loads(body))


def get(handle, event_id=None, run_id=None, sql=None, statement=None):
    if _reject_sql(sql, statement):
        return {"application_continues": True, "reason_code": "SQL_REJECTED", "records": [], "writes_enabled": False}
    if not handle.healthy or handle.conn is None:
        return {
            "application_continues": True,
            "completeness": "UNAVAILABLE",
            "reason_code": handle.reason_code or "STORE_UNAVAILABLE",
            "records": [],
            "writes_enabled": False,
        }
    if (event_id is None) == (run_id is None):
        return {"application_continues": True, "reason_code": "REJECTED_FIELD", "records": [], "writes_enabled": True}
    if event_id is not None:
        if not isinstance(event_id, str):
            return {"application_continues": True, "reason_code": "REJECTED_FIELD", "records": [], "writes_enabled": True}
        lookup = "SELECT body_json FROM records WHERE event_id = ? ORDER BY row_id ASC"
        value = event_id
    else:
        if not isinstance(run_id, str):
            return {"application_continues": True, "reason_code": "REJECTED_FIELD", "records": [], "writes_enabled": True}
        lookup = "SELECT body_json FROM records WHERE run_id = ? ORDER BY row_id ASC"
        value = run_id
    try:
        rows = handle.conn.execute(lookup, (value,)).fetchall()
    except sqlite3.Error:
        return {"application_continues": True, "reason_code": "WRITE_STOPPED", "records": [], "writes_enabled": False}
    records = []
    for row in rows:
        try:
            records.append(json.loads(row[0]))
        except ValueError:
            return {
                "application_continues": True,
                "completeness": "UNAVAILABLE",
                "reason_code": "REQUIRED_EVIDENCE_CORRUPT",
                "records": [],
                "writes_enabled": False,
            }
    return {
        "application_continues": True,
        "reason_code": "OK",
        "records": records,
        "schema_status": SCHEMA_STATUS,
        "writes_enabled": handle.writes_enabled,
    }


def _query_rejected(reason):
    return {
        "application_continues": True,
        "accepted": False,
        "completeness": "UNAVAILABLE",
        "completenessReasons": ["REQUIRED_EVIDENCE_UNAVAILABLE"],
        "declaredScope": None,
        "default_write_path": False,
        "dropState": "UNKNOWN",
        "evidence_tier": EVIDENCE_TIER,
        "freshness": "UNKNOWN",
        "hasMore": False,
        "integrityState": "UNKNOWN",
        "limitation": LIMITATION,
        "matchingRecords": None,
        "next_cursor": None,
        "reason_code": reason,
        "returnedRecords": 0,
        "rows": [],
        "samplingState": "UNKNOWN",
        "scanned_bounded": True,
        "schema_status": SCHEMA_STATUS,
    }


def _bounded_int(value, lower, upper):
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < lower or value > upper:
        return None
    return value


def _validate_request(request):
    if request is None:
        request = {}
    if isinstance(request, str):
        return None, "SQL_REJECTED"
    if not isinstance(request, dict):
        return None, "REJECTED_FIELD"
    keys = set(request.keys())
    if keys & SQL_FIELDS:
        return None, "SQL_REJECTED"
    if keys & REGEX_FIELDS:
        return None, "REGEX_REJECTED"
    unknown = keys - REQUEST_FIELDS
    if unknown:
        return None, "REJECTED_FIELD"
    if request.get("freshness") == "CURRENT":
        return None, "CURRENT_NOT_EMITTED"
    limit = request.get("limit", QUERY_LIMIT_DEFAULT)
    limit = _bounded_int(limit, 1, QUERY_LIMIT_MAX)
    if limit is None:
        return None, "LIMIT_REJECTED"
    sort = request.get("sort", "started_at_asc")
    if sort not in ("started_at_asc", "started_at_desc"):
        return None, "REJECTED_FIELD"
    time_start = request.get("time_start")
    time_end = request.get("time_end")
    has_time = time_start is not None or time_end is not None
    if has_time and (not isinstance(time_start, str) or not isinstance(time_end, str) or not TIMESTAMP_RE.fullmatch(time_start) or not TIMESTAMP_RE.fullmatch(time_end)):
        return None, "TIME_RANGE_REQUIRED"
    if not has_time and not isinstance(request.get("run_id"), str):
        return None, "TIME_RANGE_REQUIRED"
    origin = request.get("origin", "LOCAL_OBSERVATION")
    if origin not in KNOWN_ORIGINS:
        return None, "REJECTED_FIELD"
    for name in ("duration_min_ms", "duration_max_ms"):
        if name in request and _bounded_int(request[name], 0, 9007199254740991) is None:
            return None, "REJECTED_FIELD"
    if "http_status" in request and _bounded_int(request["http_status"], 0, 999) is None:
        return None, "REJECTED_FIELD"
    for name in ("run_id", "session_id", "trace_id", "provider_id", "destination_host", "application_status", "optics_status", "issue_location", "lifecycle", "coverage"):
        if name in request and not isinstance(request[name], str):
            return None, "REJECTED_FIELD"
    if "process_id" in request and not isinstance(request["process_id"], (str, int)):
        return None, "REJECTED_FIELD"
    if isinstance(request.get("process_id"), bool):
        return None, "REJECTED_FIELD"
    cursor = request.get("cursor")
    decoded = None
    if cursor is not None:
        if not isinstance(cursor, str):
            return None, "CURSOR_REJECTED"
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
        except (ValueError, UnicodeError):
            return None, "CURSOR_REJECTED"
        if not isinstance(decoded, dict) or set(decoded.keys()) != {"started_at", "producer_id", "producer_sequence", "event_id", "row_id"}:
            return None, "CURSOR_REJECTED"
    normalized = dict(request)
    normalized["limit"] = limit
    normalized["sort"] = sort
    normalized["origin"] = origin
    normalized["_cursor"] = decoded
    return normalized, None


def _cursor_clause(sort):
    started = "started_at < ?" if sort == "started_at_desc" else "started_at > ?"
    return (
        "("
        + started
        + " OR (started_at = ? AND producer_id > ?)"
        + " OR (started_at = ? AND producer_id = ? AND producer_sequence > ?)"
        + " OR (started_at = ? AND producer_id = ? AND producer_sequence = ? AND event_id > ?)"
        + " OR (started_at = ? AND producer_id = ? AND producer_sequence = ? AND event_id = ? AND row_id > ?)"
        + ")"
    )


def _cursor_params(decoded):
    return [
        decoded["started_at"],
        decoded["started_at"],
        decoded["producer_id"],
        decoded["started_at"],
        decoded["producer_id"],
        decoded["producer_sequence"],
        decoded["started_at"],
        decoded["producer_id"],
        decoded["producer_sequence"],
        decoded["event_id"],
        decoded["started_at"],
        decoded["producer_id"],
        decoded["producer_sequence"],
        decoded["event_id"],
        decoded["row_id"],
    ]


def _scope_completeness(scope_rows):
    # A4: completeness is a property of the declared scope, including rows past this page.
    reasons = []
    sampled = False
    unsampled = True
    for sampling, lifecycle, record_type, issue_location, body_text in scope_rows:
        if sampling not in (None, "UNSAMPLED"):
            sampled = True
            unsampled = False
            reasons.append("SAMPLING_NOT_UNSAMPLED")
        if record_type == "run_envelope" and lifecycle not in (None, "COMPLETE"):
            reasons.append("RUN_LIFECYCLE_NOT_COMPLETE")
        if issue_location == "COVERAGE":
            reasons.append("COVERAGE_GAP_IN_SCOPE")
        try:
            body = json.loads(body_text)
        except (ValueError, TypeError):
            reasons.append("REQUIRED_EVIDENCE_CORRUPT")
            continue
        if not isinstance(body, dict):
            reasons.append("REQUIRED_EVIDENCE_CORRUPT")
            continue
        conflict = body.get("identity_conflict")
        if conflict == "PARENT":
            reasons.append("PARENT_CONFLICT")
        elif conflict == "PRODUCER_SEQUENCE":
            reasons.append("PRODUCER_SEQUENCE_CONFLICT")
    return reasons, sampled, unsampled


def query(handle, request=None):
    normalized, reason = _validate_request(request)
    if reason is not None:
        return _query_rejected(reason)
    if not handle.healthy or handle.conn is None:
        refused = _query_rejected(handle.reason_code or "STORE_UNAVAILABLE")
        refused["integrityState"] = "FAILED" if handle.integrity in ("FAILED", "UNREADABLE") else "UNKNOWN"
        if handle.recovery_state == "STOPPED_PRESERVED":
            refused["completeness"] = "UNAVAILABLE"
            refused["completenessReasons"] = ["REQUIRED_EVIDENCE_UNAVAILABLE"]
        return refused
    clauses = ["evidence_origin = ?"]
    params = [normalized["origin"]]
    for name, sql_text in FILTER_SQL.items():
        if name == "origin" or name not in normalized:
            continue
        value = normalized[name]
        if name == "process_id":
            value = str(value)
        clauses.append(sql_text)
        params.append(value)
    if "time_start" in normalized:
        clauses.append("started_at >= ?")
        clauses.append("started_at <= ?")
        params.extend([normalized["time_start"], normalized["time_end"]])
    if "duration_min_ms" in normalized:
        clauses.append("duration_ms >= ?")
        params.append(normalized["duration_min_ms"])
    if "duration_max_ms" in normalized:
        clauses.append("duration_ms <= ?")
        params.append(normalized["duration_max_ms"])
    scope_sql = " AND ".join(clauses)
    page_sql = scope_sql
    page_params = list(params)
    decoded = normalized.get("_cursor")
    if decoded is not None:
        page_sql = page_sql + " AND " + _cursor_clause(normalized["sort"])
        page_params.extend(_cursor_params(decoded))
    direction = "DESC" if normalized["sort"] == "started_at_desc" else "ASC"
    order = "started_at %s, producer_id ASC, producer_sequence ASC, event_id ASC, row_id ASC" % direction
    try:
        total = handle.conn.execute("SELECT COUNT(*) FROM records WHERE " + scope_sql, params).fetchone()[0]
        fetched = handle.conn.execute(
            "SELECT row_id, body_json, started_at, producer_id, producer_sequence, event_id, sampling, lifecycle, record_type, issue_location "
            "FROM records WHERE " + page_sql + " ORDER BY " + order + " LIMIT ?",
            page_params + [normalized["limit"] + 1],
        ).fetchall()
        if "time_start" in normalized:
            drop_count = handle.conn.execute(
                "SELECT COALESCE(SUM(drop_count), 0) FROM drops WHERE dropped_at >= ? AND dropped_at <= ?",
                (normalized["time_start"], normalized["time_end"]),
            ).fetchone()[0]
            drops_scoped = True
        else:
            drop_count = handle.conn.execute("SELECT COALESCE(SUM(drop_count), 0) FROM drops").fetchone()[0]
            drops_scoped = False
        scope_rows = handle.conn.execute(
            "SELECT sampling, lifecycle, record_type, issue_location, body_json FROM records WHERE "
            + scope_sql
            + " ORDER BY started_at ASC, producer_id ASC, producer_sequence ASC, event_id ASC, row_id ASC",
            params,
        ).fetchall()
    except sqlite3.Error:
        return _query_rejected("STORE_UNAVAILABLE")
    has_more = len(fetched) > normalized["limit"]
    page = fetched[: normalized["limit"]]
    scope_reasons, sampled, unsampled = _scope_completeness(scope_rows)
    rows = []
    for row in page:
        try:
            body = json.loads(row[1])
        except (ValueError, TypeError):
            continue
        if not isinstance(body, dict):
            continue
        rows.append(body)
    reasons = list(scope_reasons)
    if int(drop_count) > 0 and drops_scoped:
        reasons.append("DROPS_IN_SCOPE")
        drop_state = "DROPS_IN_SCOPE"
    elif int(drop_count) > 0:
        reasons.append("EVALUATION_INCOMPLETE")
        drop_state = "UNKNOWN"
    else:
        drop_state = "NO_DROPS"
    unique_reasons = []
    for token in reasons:
        if token not in unique_reasons:
            unique_reasons.append(token)
    if unique_reasons:
        completeness = "PARTIAL"
    else:
        completeness = "COMPLETE"
    included = [normalized["origin"]]
    excluded = [name for name in ("LOCAL_OBSERVATION",) + EXCLUDED_ORIGINS if name not in included]
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = base64.urlsafe_b64encode(
            json.dumps(
                {
                    "event_id": last[5],
                    "producer_id": last[3],
                    "producer_sequence": last[4],
                    "row_id": last[0],
                    "started_at": last[2],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii")
    return {
        "accepted": True,
        "application_continues": True,
        "completeness": completeness,
        "completenessReasons": unique_reasons,
        "declaredScope": {
            "filters": {key: normalized[key] for key in REQUEST_FIELDS if key in normalized and not key.startswith("_")},
            "origins_excluded": excluded,
            "origins_included": included,
            "time_end": normalized.get("time_end"),
            "time_start": normalized.get("time_start"),
        },
        "default_write_path": False,
        "dropState": drop_state,
        "evidence_tier": EVIDENCE_TIER,
        "freshness": "UNKNOWN",
        "hasMore": has_more,
        "integrityState": "OK",
        "limitation": LIMITATION,
        "matchingRecords": int(total),
        "next_cursor": next_cursor,
        "reason_code": "OK",
        "returnedRecords": len(rows),
        "rows": rows,
        "samplingState": "SAMPLED" if sampled else ("UNSAMPLED" if unsampled else "UNKNOWN"),
        "scanned_bounded": True,
        "schema_status": SCHEMA_STATUS,
    }


def salvage(handle):
    if handle.recovery_state != "STOPPED_PRESERVED":
        refused = _query_rejected("SALVAGE_NOT_CLASSIFIED")
        refused["completeness"] = "UNAVAILABLE"
        return refused
    paths = handle.paths
    before = None
    if paths["store"].exists() and not paths["store"].is_symlink():
        try:
            before = _sha256_file(paths["store"])
        except OSError:
            before = None
    envelope = dict(handle.recovery or {})
    envelope["recovery_state"] = "READ_ONLY_SALVAGE"
    envelope["integrity_result"] = handle.integrity if handle.integrity in ("FAILED", "UNREADABLE") else "FAILED"
    written, target = _write_envelope(
        paths,
        envelope.get("safe_store_id"),
        envelope.get("schema_version"),
        envelope["integrity_result"],
        "READ_ONLY_SALVAGE",
        envelope.get("remediation_code") or "INTEGRITY_FAILED",
        before,
        envelope.get("backup_availability") or "UNKNOWN",
        envelope.get("last_known_successful_integrity_check"),
    )
    if written is not None:
        handle.recovery = written
        handle.recovery_path = target
        handle.recovery_state = "READ_ONLY_SALVAGE"
    after = None
    if before is not None:
        try:
            after = _sha256_file(paths["store"])
        except OSError:
            after = None
    if before is not None and after != before:
        return _query_rejected("BYTES_CHANGED")
    answer = _query_rejected("SALVAGE_UNAVAILABLE")
    answer["accepted"] = True
    answer["completeness"] = "UNAVAILABLE"
    answer["completenessReasons"] = ["REQUIRED_EVIDENCE_UNAVAILABLE"]
    answer["integrityState"] = "FAILED"
    answer["rows"] = []
    answer["matchingRecords"] = None
    return answer
