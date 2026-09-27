"""Load the private evidence contract from the repository source tree."""

import sys
from pathlib import Path

_CONTRACT_SRC = Path(__file__).resolve().parents[4] / "packages" / "optics-evidence-contract" / "src"
if str(_CONTRACT_SRC) not in sys.path:
    sys.path.insert(0, str(_CONTRACT_SRC))

import canonical
import validate

REPO_ROOT = Path(__file__).resolve().parents[4]


def canonical_json(value):
    return canonical.canonical_json(value)


def validate_evidence(value):
    return validate.validate_evidence(value)
