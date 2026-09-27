"""Posture constants for the inert Python adapter.

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA
"""

POSTURE = (
    "PRIVATE",
    "INERT",
    "NOT_SHIPPED",
    "NO_LIVE_WRITER",
    "NO_LIVE_READER",
    "NO_MIGRATION",
    "NO_STABLE_SCHEMA",
)

AUDIENCE = "INTERNAL_RESTRICTED"
SCHEMA_STATUS = "unstable-pre-1.0"
SCHEMA_VERSION = 0
PACKAGE_VERSION = "0.0.0-unstable-pre-1.0"
CLAIMED_CPYTHON = "3.12"
CLASSIFICATION = "OPTICS_PKG02_UNIT_C_READY_FOR_COUNCIL"

FROZEN_VERSIONS = {
    "cli": "0.3.24",
    "node_sdk": "0.2.4",
    "python": "3.1.0",
    "evidence_contract": "0.0.0-unstable-pre-1.0",
    "vocabulary": "0.0.0-unstable-pre-1.0",
    "this_package": PACKAGE_VERSION,
}

PROHIBITED_CANONICAL_NAMES = frozenset(
    {
        "anonymousId",
        "applicationStatus",
        "bytes",
        "cost",
        "data_note",
        "est_spend_usd",
        "freshness",
        "hostname",
        "machine",
        "ok",
        "opticsStatus",
        "optics_trace_witness",
        "pid",
        "plane",
        "ppid",
        "prompt",
        "prompts",
        "residual",
        "status_labels",
        "traceId",
        "ts",
        "usage",
        "vantio_run_log",
        "widget_hint",
        "workflow",
    }
)
