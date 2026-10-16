"""GCP plan for battery id t5-egress.

This module does not call gcloud and does not start a guest. The keyless
workflow on main has no input that selects this battery. The only accepted
project is vantio-lab-oct08.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

_T5_DIR = Path(__file__).resolve().parents[1] / "clean-host" / "t5"
if str(_T5_DIR) not in sys.path:
    sys.path.insert(0, str(_T5_DIR))
import t5_battery as t5  # noqa: E402

STATIC_KEY_NAMES = (
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GCP_SA_KEY",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
)


def plan(env: Mapping[str, str]) -> dict[str, object]:
    project = env.get("GCP_LAB_PROJECT", "")
    hostname = env.get("GCP_LAB_INSTANCE", "")
    reasons: list[str] = []
    if "navera" in f"{project} {hostname}".lower():
        reasons.append("navera")
    if project != t5.LAB_PROJECT:
        reasons.append("project")
    if any(env.get(name) for name in STATIC_KEY_NAMES):
        reasons.append("static_key")
    reasons.append("workflow_has_no_t5_input")
    reasons.append("not_dispatched")
    return {
        "battery_id": t5.BATTERY_ID,
        "project": t5.LAB_PROJECT,
        "dispatch": False,
        "attached": False,
        "label": "Roadmap",
        "kernel_attach": "Roadmap",
        "reasons": reasons,
        "lane_seal_prefix": t5.LANE_SEAL[:8],
        "public_pin_prefix": t5.PUBLIC_PIN[:8],
    }


def main() -> int:
    decision = plan(os.environ)
    print(f"{decision['battery_id']} dispatch=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
