"""Read release/pe-canonical-seal.json and the retired-seal history file.

The public pin and the lane seal stay two roles. Their values are the
digests already pinned in this tree. A later edit of the JSON switches
both roles to one seal. This module does not choose a new digest.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping

HEX = frozenset("0123456789abcdef")


class SealFileError(ValueError):
    """The canonical seal file or the history file is missing or malformed."""


def _hex(value: object, size: int, label: str) -> str:
    if not isinstance(value, str) or len(value) != size or any(char not in HEX for char in value):
        raise SealFileError(label)
    return value


def _manifest(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise SealFileError("manifest_digest")
    _hex(value.removeprefix("sha256:"), 64, "manifest_digest")
    return value


def seal_path() -> Path:
    """Canonical JSON next to this module when copied, otherwise the repo file."""
    here = Path(__file__).resolve()
    sibling = here.with_name("pe-canonical-seal.json")
    if sibling.is_file():
        return sibling
    for parent in here.parents:
        candidate = parent / "release" / "pe-canonical-seal.json"
        if candidate.is_file():
            return candidate
    raise SealFileError("release/pe-canonical-seal.json")


def history_path() -> Path:
    here = Path(__file__).resolve()
    sibling = here.with_name("pe-seal-history.json")
    if sibling.is_file():
        return sibling
    for parent in here.parents:
        candidate = parent / "release" / "pe-seal-history.json"
        if candidate.is_file():
            return candidate
    raise SealFileError("release/pe-seal-history.json")


def _read_json(path: Path) -> Mapping[str, object]:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SealFileError(path.name) from exc
    if not isinstance(body, dict):
        raise SealFileError(path.name)
    return body


@lru_cache(maxsize=1)
def load() -> Mapping[str, object]:
    body = _read_json(seal_path())
    if body.get("schema") != 1:
        raise SealFileError("schema")
    public = body.get("public_pin")
    lane = body.get("lane_seal")
    if not isinstance(public, dict) or not isinstance(lane, dict):
        raise SealFileError("roles")
    _hex(public.get("archive_sha256"), 64, "archive_sha256")
    _hex(public.get("source_commit"), 40, "source_commit")
    _manifest(public.get("manifest_digest"))
    basename = public.get("archive_basename")
    if not isinstance(basename, str) or "/" in basename or not basename.endswith(".oci.tar"):
        raise SealFileError("archive_basename")
    _hex(lane.get("sha256"), 64, "lane_seal")
    note = lane.get("note")
    if not isinstance(note, str) or "one seal" not in note:
        raise SealFileError("lane_note")
    if body.get("signer_kid") is not None:
        raise SealFileError("signer_kid")
    updated = body.get("updated")
    if not isinstance(updated, str) or len(updated) != 10 or updated[4] != "-" or updated[7] != "-":
        raise SealFileError("updated")
    return body


@lru_cache(maxsize=1)
def load_history() -> Mapping[str, object]:
    body = _read_json(history_path())
    if body.get("schema") != 1:
        raise SealFileError("history_schema")
    for key in ("previous_working_seal", "plumbing_only_seal", "tracking_seal"):
        _hex(body.get(key), 64, key)
    return body


def _public(name: str) -> str:
    public = load()["public_pin"]
    if not isinstance(public, dict):
        raise SealFileError("public_pin")
    value = public[name]
    if not isinstance(value, str):
        raise SealFileError(name)
    return value


def public_pin() -> str:
    return _public("archive_sha256")


def source_commit() -> str:
    return _public("source_commit")


def manifest_digest() -> str:
    return _public("manifest_digest")


def archive_basename() -> str:
    return _public("archive_basename")


def lane_seal() -> str:
    lane = load()["lane_seal"]
    if not isinstance(lane, dict):
        raise SealFileError("lane_seal")
    value = lane["sha256"]
    if not isinstance(value, str):
        raise SealFileError("lane_seal")
    return value


def previous_working_seal() -> str:
    value = load_history()["previous_working_seal"]
    if not isinstance(value, str):
        raise SealFileError("previous_working_seal")
    return value


def plumbing_only_seal() -> str:
    value = load_history()["plumbing_only_seal"]
    if not isinstance(value, str):
        raise SealFileError("plumbing_only_seal")
    return value


def tracking_seal() -> str:
    value = load_history()["tracking_seal"]
    if not isinstance(value, str):
        raise SealFileError("tracking_seal")
    return value
