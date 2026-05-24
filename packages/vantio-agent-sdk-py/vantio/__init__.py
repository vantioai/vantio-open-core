"""
[ ∅ VANTIO ] Agent SDK — Python
Zero-line AI governance telemetry. Zero dependencies beyond stdlib.
"""
from .sdk import shield, report_anomaly, get_current_trace_id, VantioContext

__all__ = ["shield", "report_anomaly", "get_current_trace_id", "VantioContext"]
__version__ = "0.1.0"
