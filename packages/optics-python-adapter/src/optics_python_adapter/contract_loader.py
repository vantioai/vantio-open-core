"""Load the private evidence-contract mapper.

The adapter calls that mapper on copies. It does not import the live SDK.
The contract package is not installed, so its source directory is added to
the import path before the mapper modules are imported.
"""

import sys
from pathlib import Path

_CONTRACT_SRC = Path(__file__).resolve().parents[4] / "packages" / "optics-evidence-contract" / "src"
if str(_CONTRACT_SRC) not in sys.path:
    sys.path.insert(0, str(_CONTRACT_SRC))

import canonical
import validate


def repo_root():
    return Path(__file__).resolve().parents[4]


def contract_src():
    return _CONTRACT_SRC


def load_contract():
    return {
        "canonical_json": canonical.canonical_json,
        "failure_kinds": validate.FAILURES,
        "mediation": validate.MEDIATION,
        "methods": validate.METHODS,
        "network_kinds": validate.NETWORK_KINDS,
        "optics_status": validate.OPTICS_STATUS,
        "validate_evidence": validate.validate_evidence,
        "witness_field": validate.meta["trace_generation_witness"]["field"],
        "witness_value": validate.meta["trace_generation_witness"]["value"],
    }
