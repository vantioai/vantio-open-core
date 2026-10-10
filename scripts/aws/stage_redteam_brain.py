#!/usr/bin/env python3
"""Download the pinned Qwen brain on the runner and lay it out for SSH copy.

The lab guest has no route for this download. Hashes stay in redteam_brain.py.
"""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gcp"))

import redteam_brain  # noqa: E402


def safe_extract(tar_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if not parts or member.name.startswith("/") or ".." in parts:
                raise ValueError("runtime_member")
            if member.issym() or member.islnk():
                link = member.linkname
                if link.startswith("/") or ".." in Path(link).parts:
                    raise ValueError("runtime_member")
        tar.extractall(dest, members=members)


def stage(directory: str) -> None:
    root = Path(directory)
    redteam_brain.fetch(str(root))
    safe_extract(root / redteam_brain.RUNTIME_NAME, root)
    server = root / "llama-b11540" / "llama-server"
    model = root / redteam_brain.MODEL_NAME
    if not server.is_file() or not model.is_file():
        raise ValueError("brain_layout")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or not args[0] or args[0].startswith("-"):
        print("usage: stage_redteam_brain.py DIR", file=sys.stderr)
        return 2
    stage(args[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
