"""Posture constants for the operational store. Not a stable schema."""

AUDIENCE = "INTERNAL_RESTRICTED"
SCHEMA_STATUS = "unstable-pre-1.0"
PACKAGE_VERSION = "0.0.0-unstable-pre-1.0"
OPERATIONAL_SCHEMA_VERSION = 1
PRIVACY_GENERATION = 1
EVIDENCE_TIER = "UNSET"
NODE_BINDING = "UNSELECTED"
FOUNDER_DECISION_9 = "UNRESOLVED"

POSTURE = (
    "PRIVATE",
    "NOT_SHIPPED",
    "NO_DEFAULT_WRITE_PATH",
    "NO_LIVE_WRITER",
    "NO_CLI_REOPEN",
    "NO_CUSTOMER_MIGRATION",
    "NO_STABLE_SCHEMA",
    "NODE_BINDING_UNSELECTED",
)

PKG02_WRITER_FLAGS = (
    "activate",
    "emit",
    "migrate",
    "publish",
    "seal",
    "sqlite",
    "write",
)
