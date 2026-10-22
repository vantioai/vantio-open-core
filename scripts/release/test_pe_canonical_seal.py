#!/usr/bin/env python3
"""The canonical seal file is the only source of the current pin and lane seal."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "release"))
sys.path.insert(0, str(ROOT / "packages" / "vantio-install"))

import pe_canonical_seal as seal  # noqa: E402
from vantio_install import constants  # noqa: E402

ALLOWLIST = ROOT / "release" / "pe-seal-literal-allowlist.json"
MIRROR_DOCS = (
    "packages/vantio-install/docs/ARTIFACT-PATH.md",
    "packages/vantio-install/docs/STAGE-B-ARTIFACT-PATH.md",
    "packages/vantio-install/docs/NETWORK-TRANSFER-ALLOWLIST.md",
)
RUNTIME_READERS = (
    "packages/vantio-install/vantio_install/constants.py",
    "packages/t5-egress-kernel/t5_kernel/loader.py",
    "scripts/clean-host/t5/t5_battery.py",
    "scripts/aws/lab-guests/phase2_grade.py",
    "scripts/aws/enterprise_bundle.py",
    "scripts/gap/t1-stranger-host/constants.py",
    "scripts/gcp/offline_deliver_1.py",
    "scripts/gcp/redteam_packet.py",
    "scripts/release/seal-identity-recheck.mjs",
    "scripts/release/engine-archive-rebuild.mjs",
    ".github/workflows/w3-lab-auto-arm.yml",
)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", ".pytest_cache"}
TEXT_SUFFIXES = {
    ".py",
    ".mjs",
    ".js",
    ".cjs",
    ".yml",
    ".yaml",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".sh",
    ".c",
    ".h",
    ".mdc",
}


def _load_allowlist() -> dict[str, object]:
    body = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise AssertionError("allowlist")
    return body


def _current() -> set[str]:
    body = seal.load()
    public = body["public_pin"]
    lane = body["lane_seal"]
    if not isinstance(public, dict) or not isinstance(lane, dict):
        raise AssertionError("roles")
    pin = public["archive_sha256"]
    lane_sha = lane["sha256"]
    if not isinstance(pin, str) or not isinstance(lane_sha, str):
        raise AssertionError("digest")
    return {pin, lane_sha}


def _historical() -> set[str]:
    body = seal.load_history()
    found = set()
    for key in ("previous_working_seal", "plumbing_only_seal", "tracking_seal"):
        value = body[key]
        if not isinstance(value, str):
            raise AssertionError(key)
        found.add(value)
    for entry in body.get("retired_lane_seals") or []:
        found.add(entry["sha256"])
    return found


def _history_path(rel: str) -> bool:
    parts = rel.split("/")
    return rel.startswith("archive/") or rel.startswith("evidence/") or "archive" in parts or "evidence" in parts


def _scan() -> list[str]:
    current = _current()
    historical = _historical()
    known = current | historical
    allow = _load_allowlist()
    records = set(allow.get("historical_records") or [])
    mirrors = set(allow.get("mirror_docs") or [])
    special = {
        "release/pe-canonical-seal.json",
        "release/pe-seal-history.json",
        "release/pe-seal-literal-allowlist.json",
    }
    offenders: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if _history_path(rel) or rel in special or rel in records or rel in mirrors:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(digest in text for digest in known):
            offenders.append(rel)
    return sorted(offenders)


class CanonicalSealTests(unittest.TestCase):
    def test_installer_and_helper_read_the_same_pin(self) -> None:
        body = seal.load()
        public = body["public_pin"]
        assert isinstance(public, dict)
        self.assertEqual(constants.FROZEN_PINS["pe_archive_sha256"], seal.public_pin())
        self.assertEqual(constants.LIVE_CANONICAL_IDENTITY["pe_archive_sha256"], seal.public_pin())
        self.assertEqual(constants.FROZEN_PINS["pe_source_commit"], public["source_commit"])
        self.assertEqual(constants.FROZEN_PINS["pe_manifest_digest"], public["manifest_digest"])
        self.assertEqual(constants.FROZEN_PINS["pe_archive_name"], public["archive_basename"])
        self.assertNotEqual(seal.public_pin(), seal.lane_seal())
        self.assertIsNone(body["signer_kid"])
        self.assertEqual(body["updated"], "2026-10-22")

    def test_mirror_docs_keep_the_json_literals(self) -> None:
        body = seal.load()
        public = body["public_pin"]
        assert isinstance(public, dict)
        allow = _load_allowlist()
        self.assertEqual(list(allow["mirror_docs"]), list(MIRROR_DOCS))
        for rel in MIRROR_DOCS:
            text = (ROOT / rel).read_text(encoding="utf-8")
            shas = re.findall(r"SHA-256: `([0-9a-f]{64})`", text)
            source = re.search(r"Source commit: `([0-9a-f]{40})`", text)
            manifest = re.search(r"Manifest digest: `(sha256:[0-9a-f]{64})`", text)
            self.assertIn(public["archive_sha256"], shas, rel)
            self.assertIsNotNone(source, rel)
            self.assertIsNotNone(manifest, rel)
            assert source is not None and manifest is not None
            self.assertEqual(source.group(1), public["source_commit"])
            self.assertEqual(manifest.group(1), public["manifest_digest"])

    def test_runtime_readers_do_not_embed_a_known_seal(self) -> None:
        known = _current() | _historical()
        allow = _load_allowlist()
        records = set(allow.get("historical_records") or [])
        for rel in RUNTIME_READERS:
            text = (ROOT / rel).read_text(encoding="utf-8")
            for digest in known:
                self.assertNotIn(digest, text, rel)
            self.assertNotIn(rel, records)

    def test_history_file_does_not_carry_the_current_roles(self) -> None:
        text = (ROOT / "release" / "pe-seal-history.json").read_text(encoding="utf-8")
        for digest in _current():
            self.assertNotIn(digest, text)
        allow_text = ALLOWLIST.read_text(encoding="utf-8")
        for digest in _current() | _historical():
            self.assertNotIn(digest, allow_text)

    def test_new_seal_literals_fail(self) -> None:
        offenders = _scan()
        self.assertEqual(offenders, [], "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
