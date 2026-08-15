"""
Process-lifetime wrap for `vantio run python …`.

Installs the same urllib / requests / httpx / aiohttp / socket / subprocess-curl
hooks as shield(), then writes the run log on interpreter exit. Browser paths stay outside.
"""
from __future__ import annotations

import atexit
import os
import uuid

from vantio._http_observe import install, uninstall

_installed = False


def install_process_wrap() -> None:
    global _installed
    if _installed:
        return
    tid = os.environ.get("VANTIO_TRACE_ID") or str(uuid.uuid4())
    os.environ.setdefault("VANTIO_TRACE_ID", tid)
    install(tid)
    atexit.register(_shutdown)
    _installed = True


def _shutdown() -> None:
    try:
        uninstall()
    except Exception:
        return
