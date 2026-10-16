"""Lab-only observe inventory of recognized AI workloads on one Linux procfs view.

Importing this package does not scan, enroll, or write a report.
"""

from optics_agent_inventory.inventory import ScanConfig, scan

PACKAGE_VERSION = "0.0.0-unstable-pre-1.0"
SCHEMA_STATUS = "unstable-pre-1.0"
LABEL = "lab-only"
CONTENT_STORED = False

__all__ = [
    "CONTENT_STORED",
    "LABEL",
    "PACKAGE_VERSION",
    "SCHEMA_STATUS",
    "ScanConfig",
    "scan",
]
