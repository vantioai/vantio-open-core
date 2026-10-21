"""Filesystem root for installer mutations.

A fixture command writes under the state directory. A live command writes
under ``/``. Fixture tests do not touch the machine running the suite.
"""

from __future__ import annotations

from pathlib import Path


def server_root(ctx: dict, *, create: bool = False) -> Path:
    if ctx.get("fixture_host"):
        root = Path(ctx["state_dir"]) / "server-root"
        if create:
            root.mkdir(parents=True, exist_ok=True)
        return root
    return Path("/")
