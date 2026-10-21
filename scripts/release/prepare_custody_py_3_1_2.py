#!/usr/bin/env python3
"""Print the custody-py-3.1.2 release command.

This script checks the sealed wheel and sdist, then prints the operator
command. It does not create a git tag, and it does not create a GitHub release.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAG = "custody-py-3.1.2"
WHEEL = "vantio_agent_sdk-3.1.2-py3-none-any.whl"
SDIST = "vantio_agent_sdk-3.1.2.tar.gz"
PINS = ROOT / "docs/programs/release-engineering/SEALED-RELEASE-PINS.json"
REFUSED = "REFUSED: this script does not create custody-py-3.1.2"


def fail(message: str, code: int = 1) -> None:
    sys.stderr.write(message + "\n")
    raise SystemExit(code)


def main() -> None:
    if any(arg in {"--apply", "--create", "--tag"} for arg in sys.argv[1:]):
        fail(REFUSED, 2)
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    row = pins["python"]
    if row.get("custody_tag") != TAG or row.get("custody_tag_created") is not False:
        fail("REFUSED: custody tag pin is not an uncreated 3.1.2 record")
    if row.get("state") != "SEALED_BYTES_RECORDED_NOT_PUBLISHED":
        fail("REFUSED: python pin state is not sealed bytes recorded and unpublished")
    expected = {
        WHEEL: (row["wheel_path"], row["wheel_sha256"], row["wheel_bytes"]),
        SDIST: (row["sdist_path"], row["sdist_sha256"], row["sdist_bytes"]),
    }
    for name, (rel, digest, size) in expected.items():
        path = ROOT / rel
        data = path.read_bytes()
        if path.name != name or len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            fail(f"REFUSED: {name} does not match the sealed pin")
    sys.stdout.write("TAG_CREATED false\n")
    sys.stdout.write("git tag is not created by this script\n")
    sys.stdout.write(
        "gh release create custody-py-3.1.2 "
        "--repo vantioai/vantio-open-core "
        "--title custody-py-3.1.2 "
        "--notes 'Sealed vantio-agent-sdk 3.1.2 wheel and sdist. "
        "The tag is a selector. SHA-256 in scripts/release/stage_sealed_pypi.py is the integrity gate.' "
        "artifacts/sealed/vantio_agent_sdk-3.1.2-py3-none-any.whl "
        "artifacts/sealed/vantio_agent_sdk-3.1.2.tar.gz\n"
    )


if __name__ == "__main__":
    main()
