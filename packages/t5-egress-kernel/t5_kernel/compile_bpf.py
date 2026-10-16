"""Compile the lab program. This does not call the bpf syscall."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "bpf" / "t5_egress.bpf.c"
SECTIONS = ("cgroup_skb/egress", "cgroup/connect4", "cgroup/connect6", "license")


def compile_object(destination: Path) -> dict[str, object]:
    clang = shutil.which("clang")
    if clang is None:
        return {"status": "skipped", "reason": "clang_missing", "label": "Roadmap", "attached": False}
    destination.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [clang, "-O2", "-g", "-target", "bpf", "-D__TARGET_ARCH_x86", "-c", str(SOURCE), "-o", str(destination)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {
            "status": "fail",
            "reason": "compile",
            "label": "Roadmap",
            "attached": False,
            "stderr": completed.stderr[-500:],
        }
    blob = destination.read_bytes()
    missing = [name for name in SECTIONS if name.encode() not in blob and name.replace("/", "_").encode() not in blob]
    # Section names are in the ELF string table.
    section_text = _section_names(destination)
    missing = [name for name in SECTIONS if name not in section_text]
    if missing:
        return {"status": "fail", "reason": "sections", "missing": missing, "label": "Roadmap", "attached": False}
    if b"GPL" not in blob:
        return {"status": "fail", "reason": "license", "label": "Roadmap", "attached": False}
    return {
        "status": "pass",
        "label": "Lab-only",
        "attached": False,
        "reason": "compiled_not_loaded",
        "sections": list(SECTIONS),
        "bytes": len(blob),
    }


def _section_names(path: Path) -> str:
    readelf = shutil.which("readelf") or shutil.which("llvm-readelf")
    if readelf is None:
        return path.read_bytes().decode("latin1", errors="ignore")
    completed = subprocess.run([readelf, "-S", str(path)], check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return path.read_bytes().decode("latin1", errors="ignore")
    return completed.stdout
