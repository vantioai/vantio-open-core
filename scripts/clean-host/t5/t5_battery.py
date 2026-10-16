"""Battery id t5-egress. Lab-only. Does not dispatch a cloud run."""

from __future__ import annotations

import tarfile
from pathlib import Path

BATTERY_ID = "t5-egress"
LANE_SEAL = "6d3ce580ffb5d52fa0bfb70bdee28409fa6282f86737011e3d85c1093f5ea403"
PUBLIC_PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
LAB_PROJECT = "vantio-lab-oct08"
GUEST_SCRIPT = Path(__file__).resolve().parents[2] / "aws" / "lab-guests" / "t5-egress.sh"
PACK_ROOTS = (
    "scripts/clean-host/t5",
    "packages/t5-egress-drills",
    "packages/t5-egress-kernel",
)


def pack_tree(repo: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w") as archive:
        for rel in PACK_ROOTS:
            root = repo / rel
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts or path.suffix == ".o":
                    continue
                archive.add(path, arcname=path.relative_to(repo).as_posix())


def lane_seal(value: str) -> bool:
    return value == LANE_SEAL and value != PUBLIC_PIN
