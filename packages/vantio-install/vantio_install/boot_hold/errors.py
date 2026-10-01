"""Errors for the boot-hold command."""

from __future__ import annotations


class BootHoldError(Exception):
    def __init__(self, message: str, *, exit_code: int = 4, state: str = "FAILED_SAFE") -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.state = state
