"""Fail-closed coverage states. The set is exactly four names."""

from __future__ import annotations

COVERED = "covered"
PARTIAL = "partial"
UNENROLLED = "unenrolled"
UNKNOWN = "unknown"

_ORDER = (
    ("proc_unreadable", UNKNOWN),
    ("scan_incomplete", UNKNOWN),
    ("scan_cap", UNKNOWN),
    ("proc_restricted", UNKNOWN),
    ("enrollment_missing", UNKNOWN),
    ("enrollment_symlink", UNKNOWN),
    ("enrollment_unreadable", UNKNOWN),
    ("enrollment_schema", UNKNOWN),
    ("host_id_mismatch", UNENROLLED),
    ("unreadable_identity", UNKNOWN),
    ("enrolled_workload_unknown", UNKNOWN),
    ("enrolled_workload_partial", PARTIAL),
    ("runs_unreadable", PARTIAL),
    ("endpoint_map_unreadable", PARTIAL),
    ("enrolled_scope_unreadable", PARTIAL),
)


def coverage_name(value: str) -> str:
    if value == COVERED:
        return COVERED
    if value == PARTIAL:
        return PARTIAL
    if value == UNENROLLED:
        return UNENROLLED
    if value == UNKNOWN:
        return UNKNOWN
    raise RuntimeError("coverage outside the closed set")


def host_coverage(reasons: list[str]) -> str:
    """First reason in the design's priority order selects the host state."""
    present = set(reasons)
    for reason, state in _ORDER:
        if reason in present:
            return coverage_name(state)
    return coverage_name(COVERED)
