"""shield() for the future Python line.

The wrapped callable's return value is unchanged when record validation fails.
"""

import functools
import uuid
from typing import Any, Callable, Optional

from vantio_future.observe import force_reset, install, uninstall


class VantioContext:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id


class _Shield:
    def __init__(self, trace_id: Optional[str]):
        self.trace_id = trace_id or str(uuid.uuid4())

    async def __aenter__(self) -> VantioContext:
        install(self.trace_id)
        return VantioContext(self.trace_id)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            uninstall()
        except Exception:
            force_reset()
        return None

    def __call__(self, fn: Callable) -> Callable:
        return _decorate(fn, self.trace_id)


def _decorate(fn: Callable, trace_id: Optional[str]) -> Callable:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        async with _Shield(trace_id):
            return await fn(*args, **kwargs)

    return wrapper


def shield(fn: Optional[Callable] = None, *, trace_id: Optional[str] = None):
    """Async decorator or context manager. Observation is metadata only."""
    if fn is None:
        return _Shield(trace_id)
    return _decorate(fn, trace_id)
