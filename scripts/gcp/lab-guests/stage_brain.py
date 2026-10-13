#!/usr/bin/env python3
"""Lay the pinned llama.cpp build out where the guest brain looks.

The campaign copies the gguf and llama-b11540-bin-ubuntu-x64.tar.gz into
/var/lib/vantio-lab/guest. That archive already contains llama-b11540/.
ask_brain reads VANTIO_BRAIN_DIR/llama-b11540/llama-server and the gguf
beside that directory.
"""

from __future__ import annotations

import os
import shutil
import sys
import tarfile
from pathlib import Path

MODEL_NAME = "qwen2.5-3b-instruct-q4_k_m.gguf"
MODEL_BYTES = 2104932768
RUNTIME_NAME = "llama-b11540-bin-ubuntu-x64.tar.gz"
SERVER_REL = Path("llama-b11540") / "llama-server"
LIBRARY_REL = Path("llama-b11540") / "libllama-server-impl.so"


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


def stage(source: Path, dest: Path, *, model_bytes: int = MODEL_BYTES) -> tuple[Path, Path]:
    source = source.resolve()
    dest = dest.resolve()
    if not source.is_dir():
        raise ValueError("brain_source")
    tar_path = source / RUNTIME_NAME
    model_src = source / MODEL_NAME
    if not tar_path.is_file() or not model_src.is_file():
        raise ValueError("brain_files_absent")
    if model_src.stat().st_size != model_bytes:
        raise ValueError("model_size")
    safe_extract(tar_path, dest)
    server = dest / SERVER_REL
    library = dest / LIBRARY_REL
    model_dst = dest / MODEL_NAME
    if not server.is_file() or server.is_symlink() or not library.is_file():
        raise ValueError("brain_layout")
    if model_dst.exists():
        if model_dst.stat().st_size != model_bytes:
            raise ValueError("model_size")
    else:
        try:
            os.link(model_src, model_dst)
        except OSError:
            shutil.copy2(model_src, model_dst)
    if model_dst.stat().st_size != model_bytes:
        raise ValueError("model_size")
    for path in (dest, server.parent):
        if path.is_dir() and not path.is_symlink():
            path.chmod(path.stat().st_mode | 0o755)
    server.chmod(server.stat().st_mode | 0o755)
    print(f"brain_staged server={server} model={model_dst}", flush=True)
    return server, model_dst


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or not args[0] or not args[1] or args[0].startswith("-"):
        print("usage: stage_brain.py SOURCE DEST", file=sys.stderr)
        return 2
    try:
        stage(Path(args[0]), Path(args[1]))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
