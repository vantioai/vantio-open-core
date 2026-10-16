"""Failures the operator commands print by reason code."""

from __future__ import annotations


class PackageError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
