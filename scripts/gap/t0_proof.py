#!/usr/bin/env python3
"""Repeatable proof for the T0 OpenClaw hygiene checker.

Writes evidence/gap/t0-own-stack-hygiene/proof.json. `--check` regenerates the
payload and compares it to the committed evidence, ignoring the timestamp.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from t0_openclaw_hygiene import (
    compare_calver,
    evaluate,
    parse_calver,
    repo_root_from,
    version_below,
)

DESIGN_COMMIT = "39ad6c2f8373a29823159f5212dff6ebfb2f68d2"
EVIDENCE_RELATIVE = Path("evidence/gap/t0-own-stack-hygiene/proof.json")


def _copy_minimal(source: Path, dest: Path) -> None:
    security = source / "security" / "openclaw"
    target = dest / "security" / "openclaw"
    target.mkdir(parents=True)
    for path in security.iterdir():
        if path.is_file():
            shutil.copy2(path, target / path.name)
    allow = json.loads((target / "allowlist.json").read_text(encoding="utf-8"))
    for entry in allow["entries"]:
        rel = entry.get("path")
        if not isinstance(rel, str):
            continue
        src = source / rel
        if not src.is_file():
            continue
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _codes(root: Path) -> set[str]:
    return {item.code for item in evaluate(root).findings if item.severity == "error"}


def _case(name: str, closed: bool) -> dict[str, object]:
    return {"name": name, "fail_closed": closed}


def negative_cases(source: Path) -> list[dict[str, object]]:
    floor = "2026.1.29"
    cases = [
        _case("version-2026.1.28-affected", version_below("2026.1.28", floor)),
        _case("version-2026.1.29-patched", not version_below("2026.1.29", floor)),
        _case(
            "version-2026.1.29-beta-below-release",
            version_below("2026.1.29-beta.1", floor),
        ),
        _case(
            "calver-2026.10.4-after-2026.6.34",
            compare_calver(parse_calver("2026.10.4"), parse_calver("2026.6.34")) > 0,
        ),
        _case(
            "lexicographic-trap",
            "2026.10.4" < "2026.6.34"
            and compare_calver(parse_calver("2026.10.4"), parse_calver("2026.6.34")) > 0,
        ),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        floating = base / "floating"
        _copy_minimal(source, floating)
        docker = floating / "deploy" / "Dockerfile"
        docker.parent.mkdir(parents=True)
        docker.write_text("FROM ghcr.io/openclaw/openclaw:latest\n", encoding="utf-8")
        cases.append(_case("floating-tag-rejected", "FLOATING_REF" in _codes(floating)))

        affected = base / "affected"
        _copy_minimal(source, affected)
        bad = affected / "deploy" / "Dockerfile"
        bad.parent.mkdir(parents=True)
        bad.write_text("FROM ghcr.io/openclaw/openclaw:2026.1.28\n", encoding="utf-8")
        cases.append(_case("affected-tag-rejected", "AFFECTED_TAG" in _codes(affected)))

        publisher = base / "publisher"
        _copy_minimal(source, publisher)
        allow_path = publisher / "security" / "openclaw" / "allowlist.json"
        allow = json.loads(allow_path.read_text(encoding="utf-8"))
        allow["entries"][0]["publisher"] = "zaycv"
        allow_path.write_text(json.dumps(allow), encoding="utf-8")
        cases.append(_case("blocked-publisher-rejected", "PUBLISHER_BLOCKED" in _codes(publisher)))

        marketplace = base / "marketplace"
        _copy_minimal(source, marketplace)
        allow_path = marketplace / "security" / "openclaw" / "allowlist.json"
        allow = json.loads(allow_path.read_text(encoding="utf-8"))
        for entry in allow["entries"]:
            if entry["id"] == "clawhub":
                entry["source"] = "clawhub-marketplace"
                entry["binds_image"] = False
        allow_path.write_text(json.dumps(allow), encoding="utf-8")
        cases.append(_case("marketplace-clawhub-rejected", "MARKETPLACE_DENIED" in _codes(marketplace)))

        mismatch = base / "mismatch"
        _copy_minimal(source, mismatch)
        allow_path = mismatch / "security" / "openclaw" / "allowlist.json"
        allow = json.loads(allow_path.read_text(encoding="utf-8"))
        for entry in allow["entries"]:
            if entry["id"] == "optics-hook-helper":
                entry["sha256"] = "0" * 64
        allow_path.write_text(json.dumps(allow), encoding="utf-8")
        cases.append(_case("hook-hash-mismatch-rejected", "HOOK_HASH_MISMATCH" in _codes(mismatch)))

        missing = base / "missing"
        missing.mkdir()
        cases.append(_case("missing-pin-rejected", "PIN_MISSING" in _codes(missing)))
    return cases


def build_payload(root: Path) -> dict[str, object]:
    result = evaluate(root)
    cases = negative_cases(root)
    return {
        "schema": "vantio.gap.t0.proof/1",
        "design_commit": DESIGN_COMMIT,
        "label": "Lab-only",
        "verified_subset": [
            "git reads named in docs/gap/t0-own-stack-hygiene/00-DESIGN.md",
            "registry digests recorded in security/openclaw/pin.json",
        ],
        "cve": "CVE-2026-25253",
        "fixed_version": "2026.1.29",
        "pinned_version": "2026.10.4",
        "running_version": "unknown",
        "affected": "unknown",
        "registry_latest_affected": False,
        "checker_ok": result.ok,
        "error_count": sum(item.severity == "error" for item in result.findings),
        "approval_gates": list(result.approval_gates),
        "negative_cases": cases,
        "negative_cases_closed": all(case["fail_closed"] is True for case in cases),
    }


def evidence_path(root: Path) -> Path:
    return root / EVIDENCE_RELATIVE


def write_evidence(root: Path) -> Mapping[str, object]:
    payload = build_payload(root)
    document = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **payload,
    }
    path = evidence_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def check_evidence(root: Path) -> None:
    path = evidence_path(root)
    committed = json.loads(path.read_text(encoding="utf-8"))
    fresh = build_payload(root)
    committed_payload = {key: value for key, value in committed.items() if key != "generated_at_utc"}
    if committed_payload != fresh:
        raise SystemExit("evidence payload does not match a fresh proof run")
    if committed.get("checker_ok") is not True or committed.get("negative_cases_closed") is not True:
        raise SystemExit("evidence does not record a closed proof")


def main(argv: list[str]) -> int:
    root = repo_root_from(Path(__file__).resolve())
    if "--check" in argv:
        check_evidence(root)
        print("proof check ok")
        return 0
    document = write_evidence(root)
    print(f"wrote {evidence_path(root)} checker_ok={document['checker_ok']}")
    return 0 if document["checker_ok"] and document["negative_cases_closed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
