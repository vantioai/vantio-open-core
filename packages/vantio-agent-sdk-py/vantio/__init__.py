"""
Vantio Optics Python SDK — Sight Loop observe via shield().
Metadata-only telemetry. Zero dependencies beyond stdlib.
"""
from .sdk import (
    shield,
    report_anomaly,
    get_current_trace_id,
    VantioContext,
    fetch_policy,
    redact_pii,
    VantioPolicy,
    RedactionResult,
)

__all__ = [
    "shield",
    "report_anomaly",
    "get_current_trace_id",
    "VantioContext",
    "fetch_policy",
    "redact_pii",
    "VantioPolicy",
    "RedactionResult",
]
__version__ = "3.0.1"
