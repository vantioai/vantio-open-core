"""Battery id t5-egress. Lab-only. Does not dispatch a cloud run."""

from __future__ import annotations

import importlib.util
import sys
import tarfile
from pathlib import Path

BATTERY_ID = "t5-egress"


def _load_seal():
    origin = Path(__file__).resolve().parent
    for parent in (origin, *origin.parents):
        for candidate in (parent / "pe_canonical_seal.py", parent / "scripts" / "release" / "pe_canonical_seal.py"):
            if not candidate.is_file():
                continue
            cached = sys.modules.get("pe_canonical_seal")
            if cached is not None:
                return cached
            spec = importlib.util.spec_from_file_location("pe_canonical_seal", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["pe_canonical_seal"] = module
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("pe_canonical_seal.py")


_SEAL = _load_seal()
LANE_SEAL = _SEAL.lane_seal()
PUBLIC_PIN = _SEAL.public_pin()
LAB_PROJECT = "vantio-lab-oct08"
GUEST_SCRIPT = Path(__file__).resolve().parents[2] / "aws" / "lab-guests" / "t5-egress.sh"
PACK_ROOTS = (
    "scripts/clean-host/t5",
    "packages/t5-egress-drills",
    "packages/t5-egress-kernel",
)
PACK_FILES = (
    "scripts/release/pe_canonical_seal.py",
    "release/pe-canonical-seal.json",
    "release/pe-seal-history.json",
)


def pack_tree(repo: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w") as archive:
        for rel in PACK_FILES:
            path = repo / rel
            if path.is_file():
                archive.add(path, arcname=rel)
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
