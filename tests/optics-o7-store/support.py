"""Shared fixtures for the O7 store tests. This file does not import sqlite3."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "optics-operational-store" / "src"))

CORPUS = json.loads((ROOT / "tests" / "optics-evidence-contract" / "corpus.json").read_text(encoding="utf-8"))
CANARY = "sk-CANARYPROMPT0001"


def clean_record():
    return dict(CORPUS["bases"]["observation"])


def record_with(**patch):
    body = clean_record()
    body.update(patch)
    return body
