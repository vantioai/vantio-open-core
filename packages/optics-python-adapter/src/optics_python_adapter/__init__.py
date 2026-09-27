"""Inert PKG-02 Unit C Python adapter.

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA
"""

from optics_python_adapter.adapt import adapt_copy, adapt_fixture, canonical_json
from optics_python_adapter.posture import (
    AUDIENCE,
    CLAIMED_CPYTHON,
    CLASSIFICATION,
    FROZEN_VERSIONS,
    PACKAGE_VERSION,
    POSTURE,
    SCHEMA_STATUS,
    SCHEMA_VERSION,
)

__all__ = [
    "AUDIENCE",
    "CLAIMED_CPYTHON",
    "CLASSIFICATION",
    "FROZEN_VERSIONS",
    "PACKAGE_VERSION",
    "POSTURE",
    "SCHEMA_STATUS",
    "SCHEMA_VERSION",
    "adapt_copy",
    "adapt_fixture",
    "canonical_json",
]
