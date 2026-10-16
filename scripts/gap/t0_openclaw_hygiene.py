#!/usr/bin/env python3
"""Fail-closed pin and allow-list check for Vantio's OpenClaw references.

The checker reads security/openclaw/*.json and walks install-shaped files in
this repository. It does not pull an image, start a container, or contact a
registry. A missing pin, a floating tag, a version below the CVE floor, a
hash mismatch, or a ClawHavoc indicator is a failure.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

PIN_SCHEMA = "vantio.openclaw.pin/1"
ALLOW_SCHEMA = "vantio.openclaw.allowlist/1"
INDICATOR_SCHEMA = "vantio.openclaw.clawhavoc-indicators/1"
INVENTORY_SCHEMA = "vantio.openclaw.inventory/1"
PATCH_SCHEMA = "vantio.openclaw.patch-spec/1"

FIXED_VERSION = "2026.1.29"
PINNED_VERSION = "2026.10.4"
PINNED_INDEX_DIGEST = "sha256:614004ec2cf2e6095124ea544dc8d950c49306aef445a1fc300b88717e24261a"
PINNED_NPM_INTEGRITY = "sha512-+FH0StZF1tlTazM7JJGY6JePeJmhFNSRByi2Q3jXPRiLO7o4dJh2xa9Vy4Dk8Cd2ic8B7Zkf5NfEaCCWUkgqnQ=="
PINNED_NPM_SHASUM = "ac000cc196b31208b0108c171780a3312ea26e5e"
# sha256 of the canonical indicator lists. The lists themselves stay in
# indicators.json so this file does not have to embed campaign strings.
INDICATOR_FINGERPRINT = "41719fac356a95bc23c0e94bfc29017720bb5ce9e118daadafff671c9604bf4d"
REQUIRED_FLOATING_PATHS = (
    "plane1-openclaw/docker-compose.yml",
    "scripts/start_plane1_openclaw.sh",
    "scripts/plane1_openclaw_desktop_enable.sh",
    "agent-hands/docker-compose.yml",
    "docs/ops/OPENCLAW_PLANE1_PHANTOM_BOX.md",
)
POLICY_FILES = {
    "security/openclaw/pin.json",
    "security/openclaw/allowlist.json",
    "security/openclaw/indicators.json",
    "security/openclaw/inventory.json",
    "security/openclaw/patch-spec.json",
}

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
INTEGRITY_RE = re.compile(r"^sha512-[A-Za-z0-9+/]+={0,2}$")
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_HEX_RE = re.compile(r"^[0-9a-f]{40}$")
BLOB_RE = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_NAME = "openclaw/" + "openclaw"
FLOATING_IMAGE_REF = "ghcr.io/" + _IMAGE_NAME + ":" + "latest"
PINNED_IMAGE_REF = "ghcr.io/" + _IMAGE_NAME + "@" + PINNED_INDEX_DIGEST
_PKG_OPEN = "open" + "claw"
_PKG_LEGACY = "clawd" + "bot"
IMAGE_RE = re.compile(
    rf"(?i)(?<![A-Za-z0-9._@-]){_IMAGE_NAME}"
    rf"(?::(?P<tag>[A-Za-z0-9._+-]+)|@(?P<digest>sha256:[0-9a-f]{{64}}))?"
)
NPM_AT_RE = re.compile(
    rf"(?i)(?<![A-Za-z0-9._@/-])(?P<name>{_PKG_OPEN}|{_PKG_LEGACY})"
    rf"\s*@\s*(?P<spec>[^\s'\"`,;]+)"
)
NPM_KEY_RE = re.compile(
    rf"""(?i)["'](?P<name>{_PKG_OPEN}|{_PKG_LEGACY})["']\s*:\s*["'](?P<spec>[^"']+)["']"""
)
INSTALL_SUFFIXES = {
    ".yml",
    ".yaml",
    ".sh",
    ".bash",
    ".toml",
    ".tf",
    ".json",
    ".json5",
    ".env",
    ".mk",
    ".mjs",
    ".js",
    ".cjs",
    ".ts",
    ".tsx",
    ".py",
    ".dockerfile",
}
INSTALL_NAMES = {
    "dockerfile",
    "containerfile",
    "makefile",
    "compose.yml",
    "compose.yaml",
    "docker-compose.yml",
    "docker-compose.yaml",
}
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
}
MAX_INSTALL_BYTES = 2_000_000
FLOATING_TAGS = {"latest", "main", "stable"}
RANGE_MARKERS = ("^", "~", "*", ">", "<", " ", "||", "latest", "x")


@dataclass(frozen=True)
class Calver:
    parts: tuple[int, ...]
    prerelease: str | None


@dataclass(frozen=True)
class Finding:
    code: str
    detail: str
    severity: str = "error"


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)
    approval_gates: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    def add(self, code: str, detail: str, severity: str = "error") -> None:
        self.findings.append(Finding(code, detail, severity))


def parse_calver(text: str) -> Calver:
    raw = text.strip()
    if raw[:1] in {"v", "V"}:
        raw = raw[1:]
    if not raw or raw in {"latest", "main", "stable"}:
        raise ValueError(f"not a version: {text}")
    core, sep, pre = raw.partition("-")
    pieces = core.split(".")
    if not pieces or any(not piece.isdigit() for piece in pieces):
        raise ValueError(f"not a version: {text}")
    if sep and not pre:
        raise ValueError(f"not a version: {text}")
    return Calver(tuple(int(piece) for piece in pieces), pre if sep else None)


def compare_calver(left: Calver, right: Calver) -> int:
    width = max(len(left.parts), len(right.parts))
    left_parts = left.parts + (0,) * (width - len(left.parts))
    right_parts = right.parts + (0,) * (width - len(right.parts))
    if left_parts != right_parts:
        return -1 if left_parts < right_parts else 1
    if left.prerelease is None and right.prerelease is None:
        return 0
    if left.prerelease is None:
        return 1
    if right.prerelease is None:
        return -1
    if left.prerelease == right.prerelease:
        return 0
    return -1 if left.prerelease < right.prerelease else 1


def version_below(text: str, floor: str) -> bool:
    return compare_calver(parse_calver(text), parse_calver(floor)) < 0


def load_json(path: Path) -> Mapping[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not an object")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _require_str(data: Mapping[str, object], key: str, code: str, result: CheckResult) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        result.add(code, f"missing {key}")
        return ""
    return value


def _kind_handled(kind: str) -> None:
    if kind == "plugin":
        return
    if kind == "skill":
        return
    if kind == "hook":
        return
    if kind == "mcp":
        return
    if kind == "example":
        return
    if kind == "enterprise-ops-pointer":
        return
    raise ValueError(f"unhandled allow-list kind: {kind}")


def _source_handled(source: str) -> None:
    if source == "git":
        return
    if source == "npm":
        return
    if source == "image-bundled":
        return
    if source == "in-repo":
        return
    if source == "enterprise-ops":
        return
    raise ValueError(f"unhandled allow-list source: {source}")


def indicator_fingerprint(indicators: Mapping[str, object]) -> str:
    payload = {
        key: indicators.get(key)
        for key in (
            "ipv4",
            "domains",
            "urls",
            "repositories",
            "publishers",
            "denied_marketplace_skill_ids",
            "patterns",
        )
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _indicator_needles(indicators: Mapping[str, object]) -> list[str]:
    needles: list[str] = []
    for key in ("ipv4", "domains", "urls", "repositories", "publishers"):
        values = indicators.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, str) and item:
                needles.append(item)
    return needles


def _text_hits(text: str, needles: Sequence[str], patterns: Sequence[str]) -> list[str]:
    hits: list[str] = []
    for needle in needles:
        if needle in text:
            hits.append(needle)
    for pattern in patterns:
        if re.search(pattern, text):
            hits.append(f"pattern:{pattern}")
    return hits


def _is_install_shaped(path: Path) -> bool:
    name = path.name.lower()
    if name in INSTALL_NAMES or name.startswith("dockerfile") or name.endswith(".dockerfile"):
        return True
    if name == ".env" or name.endswith(".env"):
        return True
    return path.suffix.lower() in INSTALL_SUFFIXES


def _walk_install_files(root: Path, result: CheckResult) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in root.walk():
        kept: list[str] = []
        for name in dirnames:
            if name in SKIP_DIR_NAMES:
                continue
            child = dirpath / name
            if child.is_symlink():
                result.add("SYMLINK_INSTALL_FILE", child.relative_to(root).as_posix())
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = dirpath / name
            if not _is_install_shaped(path):
                continue
            relative = path.relative_to(root).as_posix()
            if relative in POLICY_FILES:
                continue
            if path.is_symlink():
                result.add("SYMLINK_INSTALL_FILE", relative)
                continue
            found.append(path)
    return found


def _check_package_spec(name: str, spec: str, relative: str, result: CheckResult) -> None:
    if name.lower() == _PKG_LEGACY:
        result.add("CLAWDBOT_UNPINNED", f"{relative} names {_PKG_LEGACY} ({spec})")
        return
    if any(marker in spec.lower() for marker in RANGE_MARKERS):
        result.add("FLOATING_REF", f"{relative} package spec {spec}")
        return
    try:
        below = version_below(spec, FIXED_VERSION)
    except ValueError:
        result.add("UNPARSEABLE_TAG", f"{relative} package spec {spec}")
        return
    if below:
        result.add("AFFECTED_TAG", f"{relative} package {spec} is below {FIXED_VERSION}")
        return
    if spec.lstrip("vV") != PINNED_VERSION:
        result.add("TAG_WITHOUT_DIGEST", f"{relative} package {spec} is not {PINNED_VERSION}")


def _scan_install_files(
    root: Path,
    floor: str,
    indicators: Mapping[str, object],
    result: CheckResult,
) -> None:
    if floor != FIXED_VERSION:
        result.add("PIN_FLOOR", "scan floor drifted from the code constant")
    index_digest = PINNED_INDEX_DIGEST
    needles = _indicator_needles(indicators)
    patterns = indicators.get("patterns")
    pattern_list = [item for item in patterns if isinstance(item, str)] if isinstance(patterns, list) else []
    for path in _walk_install_files(root, result):
        if path.stat().st_size > MAX_INSTALL_BYTES:
            result.add("INSTALL_FILE_TOO_LARGE", path.relative_to(root).as_posix())
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            result.add("INSTALL_FILE_NOT_TEXT", path.relative_to(root).as_posix())
            continue
        relative = path.relative_to(root).as_posix()
        for match in IMAGE_RE.finditer(text):
            tag = match.group("tag")
            digest = match.group("digest")
            if digest:
                if digest.lower() != index_digest:
                    result.add("PIN_DIGEST_MISMATCH", f"{relative} has {digest}")
                continue
            if tag is None or tag.lower() in FLOATING_TAGS:
                result.add("FLOATING_REF", f"{relative} has {match.group(0)}")
                continue
            try:
                below = version_below(tag, FIXED_VERSION)
            except ValueError:
                result.add("UNPARSEABLE_TAG", f"{relative} has tag {tag}")
                continue
            if below:
                result.add("AFFECTED_TAG", f"{relative} tag {tag} is below {FIXED_VERSION}")
                continue
            result.add("TAG_WITHOUT_DIGEST", f"{relative} tag {tag} has no digest")
        for match in NPM_AT_RE.finditer(text):
            _check_package_spec(match.group("name"), match.group("spec"), relative, result)
        for match in NPM_KEY_RE.finditer(text):
            _check_package_spec(match.group("name"), match.group("spec"), relative, result)
        hits = _text_hits(text, needles, pattern_list)
        if hits:
            result.add("INDICATOR_HIT", f"{relative} contains {hits[0]}")


def _check_pin(pin: Mapping[str, object], result: CheckResult) -> str:
    if pin.get("schema") != PIN_SCHEMA:
        result.add("PIN_SCHEMA", "pin.json schema mismatch")
    floor = _require_str(pin, "fixed_version", "PIN_FLOOR", result)
    if floor and floor != FIXED_VERSION:
        result.add("PIN_FLOOR", f"fixed_version {floor} is not {FIXED_VERSION}")
        floor = FIXED_VERSION
    image = pin.get("image")
    if not isinstance(image, dict):
        result.add("PIN_IMAGE", "pin.json image missing")
        return floor
    version = _require_str(image, "version", "PIN_VERSION", result)
    index_digest = _require_str(image, "index_digest", "PIN_DIGEST", result)
    amd64 = _require_str(image, "linux_amd64_manifest_digest", "PIN_DIGEST", result)
    config_digest = _require_str(image, "config_digest", "PIN_DIGEST", result)
    for digest in (index_digest, amd64, config_digest):
        if digest and not DIGEST_RE.fullmatch(digest):
            result.add("PIN_DIGEST_SHAPE", digest)
    if version and version != PINNED_VERSION:
        result.add("PIN_VERSION", f"image version {version} is not {PINNED_VERSION}")
    if index_digest and index_digest != PINNED_INDEX_DIGEST:
        result.add("PIN_DIGEST_MISMATCH", "index digest is not the pinned digest")
    npm = pin.get("npm")
    if not isinstance(npm, dict):
        result.add("PIN_NPM", "pin.json npm missing")
        return floor
    npm_version = _require_str(npm, "version", "PIN_NPM", result)
    integrity = _require_str(npm, "integrity", "PIN_NPM", result)
    shasum = _require_str(npm, "shasum", "PIN_NPM", result)
    if npm_version and npm_version != PINNED_VERSION:
        result.add("PIN_NPM", f"npm version {npm_version} is not {PINNED_VERSION}")
    if integrity and integrity != PINNED_NPM_INTEGRITY:
        result.add("PIN_INTEGRITY_SHAPE", "openclaw npm integrity is not the pinned integrity")
    if shasum and shasum != PINNED_NPM_SHASUM:
        result.add("PIN_INTEGRITY_SHAPE", "openclaw npm shasum is not the pinned shasum")
    runbook = pin.get("runbook_image")
    if isinstance(runbook, dict) and isinstance(runbook.get("version"), str) and floor:
        try:
            if version_below(str(runbook["version"]), floor):
                result.add("PIN_VERSION_BELOW_FLOOR", "runbook image is below the floor")
        except ValueError as exc:
            result.add("PIN_VERSION", str(exc))
    return floor


def _check_entry(
    entry: Mapping[str, object],
    pin: Mapping[str, object],
    indicators: Mapping[str, object],
    root: Path,
    result: CheckResult,
) -> str:
    entry_id = _require_str(entry, "id", "ALLOWLIST_ENTRY", result)
    kind = _require_str(entry, "kind", "ALLOWLIST_KIND", result)
    source = _require_str(entry, "source", "ALLOWLIST_SOURCE", result)
    try:
        _kind_handled(kind)
    except ValueError as exc:
        result.add("ALLOWLIST_UNKNOWN_KIND", str(exc))
        return entry_id
    denied = indicators.get("denied_marketplace_skill_ids")
    if isinstance(denied, list) and entry_id in denied and source != "image-bundled":
        result.add("MARKETPLACE_DENIED", f"{entry_id} is not image-bundled")
    try:
        _source_handled(source)
    except ValueError as exc:
        result.add("ALLOWLIST_UNKNOWN_SOURCE", str(exc))
        return entry_id
    publishers = indicators.get("publishers")
    publisher = entry.get("publisher")
    if isinstance(publisher, str) and isinstance(publishers, list) and publisher in publishers:
        result.add("PUBLISHER_BLOCKED", f"{entry_id} publisher {publisher}")
    marketplace_allowed = entry.get("marketplace_install_allowed")
    if marketplace_allowed is not False:
        result.add("MARKETPLACE_FLAG", f"{entry_id} must set marketplace_install_allowed false")
    if entry.get("binds_image") is True:
        image = pin.get("image")
        if not isinstance(image, dict) or not isinstance(image.get("index_digest"), str):
            result.add("PIN_DIGEST", f"{entry_id} cannot bind a missing image digest")
    if source == "git":
        commit = _require_str(entry, "git_commit", "HASH_MISMATCH", result)
        package_hash = _require_str(entry, "package_json_sha256", "HASH_MISMATCH", result)
        if commit and not re.fullmatch(r"[0-9a-f]{40}", commit):
            result.add("HASH_MISMATCH", f"{entry_id} git commit")
        if package_hash and not SHA256_HEX_RE.fullmatch(package_hash):
            result.add("HASH_MISMATCH", f"{entry_id} package.json sha256")
    if source == "npm":
        version = _require_str(entry, "version", "PIN_VERSION", result)
        integrity = _require_str(entry, "integrity", "HASH_MISMATCH", result)
        shasum = _require_str(entry, "shasum", "HASH_MISMATCH", result)
        package = entry.get("package")
        if package in {_PKG_OPEN, _PKG_LEGACY} and version:
            try:
                if version_below(version, FIXED_VERSION):
                    result.add("PIN_VERSION_BELOW_FLOOR", f"{entry_id} {version}")
                elif version != PINNED_VERSION:
                    result.add("TAG_WITHOUT_DIGEST", f"{entry_id} package version {version}")
            except ValueError as exc:
                result.add("PIN_VERSION", str(exc))
        if integrity and not INTEGRITY_RE.fullmatch(integrity):
            result.add("PIN_INTEGRITY_SHAPE", entry_id)
        if shasum and not SHA1_HEX_RE.fullmatch(shasum):
            result.add("HASH_MISMATCH", f"{entry_id} shasum")
    if source == "in-repo":
        rel = _require_str(entry, "path", "HOOK_PATH", result)
        expected = _require_str(entry, "sha256", "HOOK_HASH", result)
        if rel and expected:
            file_path = root / rel
            if not file_path.is_file() or file_path.is_symlink():
                result.add("HOOK_HASH_MISMATCH", f"{entry_id} missing {rel}")
            elif sha256_file(file_path) != expected:
                result.add("HOOK_HASH_MISMATCH", f"{entry_id} {rel}")
    if source == "enterprise-ops":
        blob = _require_str(entry, "git_blob", "ALLOWLIST_BLOB", result)
        if blob and not BLOB_RE.fullmatch(blob):
            result.add("ALLOWLIST_BLOB", entry_id)
        if entry.get("indicator_scan") != "clear":
            result.add("INDICATOR_HIT", f"{entry_id} indicator_scan is not clear")
    needles = _indicator_needles(indicators)
    patterns = indicators.get("patterns")
    pattern_list = [item for item in patterns if isinstance(item, str)] if isinstance(patterns, list) else []
    blob_text = json.dumps(entry, sort_keys=True)
    hits = _text_hits(blob_text, needles, [])
    if hits:
        result.add("INDICATOR_HIT", f"{entry_id} field contains {hits[0]}")
    if pattern_list and source != "enterprise-ops":
        # Patterns are for skill bodies. Allow-list metadata should not carry them.
        meta_hits = _text_hits(blob_text, [], pattern_list)
        if meta_hits:
            result.add("INDICATOR_HIT", f"{entry_id} matches {meta_hits[0]}")
    return entry_id


def _check_allowlist(
    allow: Mapping[str, object],
    pin: Mapping[str, object],
    indicators: Mapping[str, object],
    root: Path,
    result: CheckResult,
) -> set[str]:
    if allow.get("schema") != ALLOW_SCHEMA:
        result.add("ALLOWLIST_SCHEMA", "allowlist schema mismatch")
    entries = allow.get("entries")
    ids: set[str] = set()
    if not isinstance(entries, list) or not entries:
        result.add("ALLOWLIST_EMPTY", "allow-list has no entries")
        return ids
    for entry in entries:
        if not isinstance(entry, dict):
            result.add("ALLOWLIST_ENTRY", "entry is not an object")
            continue
        entry_id = _check_entry(entry, pin, indicators, root, result)
        if entry_id in ids:
            result.add("ALLOWLIST_DUPLICATE", entry_id)
        if entry_id:
            ids.add(entry_id)
    return ids


def expected_install_to(entry: Mapping[str, object]) -> str:
    source = entry.get("source")
    if source == "git":
        commit = entry.get("git_commit")
        package_hash = entry.get("package_json_sha256")
        return (
            f"git checkout {commit} && "
            "sha256sum -c <(printf '%s  package.json\\n' "
            f"{package_hash}) && openclaw plugins install ."
        )
    if source == "npm" and entry.get("id") == "plane1-fs-proof":
        return f"npx -y {entry.get('package')}@{entry.get('version')}"
    if source == "npm":
        return f"openclaw plugins install {entry.get('package')}@{entry.get('version')}"
    raise ValueError(f"no install replacement for source {source}")


def _check_replacement_hash(
    entry_id: str,
    command_to: str,
    entries: Sequence[Mapping[str, object]],
    result: CheckResult,
) -> None:
    match = next((entry for entry in entries if entry.get("id") == entry_id), None)
    if match is None:
        result.add("ALLOWLIST_MISS", entry_id)
        return
    try:
        expected = expected_install_to(match)
    except ValueError as exc:
        result.add("ALLOWLIST_SOURCE", str(exc))
        return
    if command_to != expected:
        result.add("PATCH_SPEC_MISMATCH", f"{entry_id} replacement is not the exact pin command")


def _check_patch(
    inventory: Mapping[str, object],
    patch: Mapping[str, object],
    pin: Mapping[str, object],
    ids: set[str],
    entries: Sequence[Mapping[str, object]],
    result: CheckResult,
) -> None:
    if inventory.get("schema") != INVENTORY_SCHEMA:
        result.add("INVENTORY_SCHEMA", "inventory schema mismatch")
    if patch.get("schema") != PATCH_SCHEMA:
        result.add("PATCH_SCHEMA", "patch-spec schema mismatch")
    if patch.get("apply") != "approval-gate":
        result.add("PATCH_APPLY", "patch-spec apply must stay approval-gate")
    image_from = _require_str(patch, "image_from", "PATCH_SPEC", result)
    image_to = _require_str(patch, "image_to", "PATCH_SPEC", result)
    if image_from != FLOATING_IMAGE_REF:
        result.add("PATCH_SPEC", "image_from is not the floating ref this track found")
    if image_to != PINNED_IMAGE_REF:
        result.add("PATCH_SPEC_MISMATCH", "image_to is not the pinned index digest")
    floating = inventory.get("floating_images")
    targets = patch.get("targets")
    if not isinstance(floating, list) or not isinstance(targets, list):
        result.add("PATCH_SPEC", "floating images or targets missing")
        return
    found_paths = {item.get("path") for item in floating if isinstance(item, dict)}
    for required in REQUIRED_FLOATING_PATHS:
        if required not in found_paths:
            result.add("INVENTORY_UNPATCHED", f"required path missing: {required}")
    target_by_path: dict[str, Mapping[str, object]] = {}
    for target in targets:
        if not isinstance(target, dict):
            result.add("PATCH_SPEC", "target is not an object")
            continue
        path = target.get("path")
        if isinstance(path, str):
            target_by_path[path] = target
    for item in floating:
        if not isinstance(item, dict):
            result.add("INVENTORY_UNPATCHED", "floating image is not an object")
            continue
        path = item.get("path")
        if not isinstance(path, str):
            result.add("INVENTORY_UNPATCHED", "floating image has no path")
            continue
        target = target_by_path.get(path)
        if target is None:
            result.add("INVENTORY_UNPATCHED", path)
            continue
        if item.get("ref") != image_from:
            result.add("INVENTORY_UNPATCHED", f"{path} ref is not image_from")
        if item.get("occurrences") != target.get("occurrences"):
            result.add("PATCH_SPEC_MISMATCH", f"{path} occurrence count")
        if item.get("git_blob") != target.get("git_blob"):
            result.add("PATCH_SPEC_MISMATCH", f"{path} blob")
        occurrences = item.get("occurrences")
        if not isinstance(occurrences, int) or occurrences < 1:
            result.add("INVENTORY_UNPATCHED", f"{path} occurrences")
    unpinned = inventory.get("unpinned_installs")
    replacements = patch.get("install_replacements")
    if not isinstance(unpinned, list) or not isinstance(replacements, list):
        result.add("PATCH_SPEC", "unpinned installs or replacements missing")
        return
    replacement_by_id = {
        item.get("id"): item for item in replacements if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for item in unpinned:
        if not isinstance(item, dict):
            result.add("INVENTORY_UNPATCHED", "unpinned install is not an object")
            continue
        entry_id = item.get("id")
        if not isinstance(entry_id, str) or entry_id not in ids:
            result.add("ALLOWLIST_MISS", f"unpinned install {entry_id}")
            continue
        replacement = replacement_by_id.get(entry_id)
        if not isinstance(replacement, dict):
            result.add("INVENTORY_UNPATCHED", f"no replacement for {entry_id}")
            continue
        command_from = replacement.get("from")
        command_to = replacement.get("to")
        if command_from != item.get("command") or not isinstance(command_to, str) or not command_to:
            result.add("PATCH_SPEC_MISMATCH", f"{entry_id} install replacement")
            continue
        if image_from in command_to or command_to == item.get("command"):
            result.add("FLOATING_REF", f"{entry_id} replacement still floats")
        _check_replacement_hash(entry_id, command_to, entries, result)


def evaluate(root: Path) -> CheckResult:
    result = CheckResult()
    security = root / "security" / "openclaw"
    pin_path = security / "pin.json"
    if not pin_path.is_file():
        result.add("PIN_MISSING", "security/openclaw/pin.json")
        return result
    try:
        pin = load_json(pin_path)
        allow = load_json(security / "allowlist.json")
        indicators = load_json(security / "indicators.json")
        inventory = load_json(security / "inventory.json")
        patch = load_json(security / "patch-spec.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result.add("PIN_MISSING", str(exc))
        return result
    if indicators.get("schema") != INDICATOR_SCHEMA:
        result.add("INDICATOR_SCHEMA", "indicators schema mismatch")
    for key in (
        "ipv4",
        "domains",
        "urls",
        "repositories",
        "publishers",
        "denied_marketplace_skill_ids",
        "patterns",
    ):
        values = indicators.get(key)
        if not isinstance(values, list) or not values:
            result.add("INDICATOR_SCHEMA", f"{key} is empty")
    if indicator_fingerprint(indicators) != INDICATOR_FINGERPRINT:
        result.add("INDICATOR_SCHEMA", "indicator set does not match the pinned fingerprint")
    floor = _check_pin(pin, result)
    ids = _check_allowlist(allow, pin, indicators, root, result)
    raw_entries = allow.get("entries")
    entries = [entry for entry in raw_entries if isinstance(entry, dict)] if isinstance(raw_entries, list) else []
    _check_patch(inventory, patch, pin, ids, entries, result)
    if floor:
        _scan_install_files(root, floor, indicators, result)
    result.approval_gates.extend(
        [
            "phantom-box-readonly-verify",
            "phantom-box-apply-image-pin",
            "phantom-box-recreate-only-if-version-below-2026.1.29",
            "phantom-box-rotate-gateway-token-only-if-affected",
        ]
    )
    return result


def repo_root_from(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "security" / "openclaw" / "pin.json").is_file():
            return candidate
    return current


def main(argv: Sequence[str]) -> int:
    root = repo_root_from(Path(__file__).resolve())
    if len(argv) > 1:
        root = Path(argv[1]).resolve()
    result = evaluate(root)
    for item in result.findings:
        print(f"{item.severity}\t{item.code}\t{item.detail}")
    print(f"ok={result.ok} errors={sum(item.severity == 'error' for item in result.findings)}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
