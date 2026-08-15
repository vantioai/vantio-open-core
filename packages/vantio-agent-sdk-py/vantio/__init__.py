"""
Vantio Optics Python SDK — Sight Loop observe via shield().
Zero dependencies beyond stdlib. Optional observe of requests/httpx/aiohttp when installed.
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
__version__ = "3.0.9"
