"""Identity of the future Python writer line.

The sealed 3.1.0 tree is a different package. 3.0.15 is not a vehicle.
"""

FUTURE_VERSION = "PKG02-FUTURE-PYTHON-UNASSIGNED"
SEALED_PYTHON_VERSION = "3.1.0"
NEVER_VEHICLE_VERSION = "3.0.15"
PRODUCER = "python_observe"
RUNTIME = "python"
SCHEMA_VERSION = 0
SCHEMA_STATUS = "unstable-pre-1.0"
LEGACY_SCHEMA_VERSION = 2
UNICODE_PROFILE_ID = "PKG01-UCD-16.0.0"
CLAIMED_CPYTHON = "3.12"
AUDIENCE = "INTERNAL_RESTRICTED"
CLASSIFICATION = "OPTICS_PKG02_UNIT_E_READY_FOR_COUNCIL"
EMPTY_SHIELD_DISPOSITION = "NOT_OBSERVED_ENVELOPE"
ACTIVATES_UNIT_E = True
ACTIVATES_UNIT_D = False
REGISTRY_PUBLISH = False
SEALED = False
MERGED = False

PROHIBITED_RECORD_NAMES = frozenset(
    {
        "anonymousId",
        "completion",
        "completions",
        "cost",
        "data_note",
        "error",
        "est_spend_usd",
        "failure_response",
        "machine",
        "message",
        "messages",
        "plane",
        "prompt",
        "prompts",
        "provider",
        "residual",
        "status_labels",
        "usage",
        "workflow",
    }
)
