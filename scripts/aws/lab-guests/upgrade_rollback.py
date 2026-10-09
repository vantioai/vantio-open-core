#!/usr/bin/env python3
"""Load the public pin, then the policy-allow seal, then the public pin again.

This is an image-file upgrade and rollback. It does not start the loader.
It does not move a child into a cgroup. Descendant enforcement is not scored.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(sys.argv[1] if len(sys.argv) > 1 else "/var/lib/vantio-lab/enterprise-bundle")
OUT = Path("/tmp/enterprise-pe-rows.json")
PUBLIC_PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
POLICY_ALLOW = "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load(path: Path) -> str:
    proc = subprocess.run(
        ["docker", "load", "-i", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    image = ""
    for line in text.splitlines():
        if line.startswith("Loaded image: "):
            image = line[len("Loaded image: ") :].strip()
    return image if proc.returncode == 0 else ""


def main() -> int:
    old = HERE / "public-pin.oci.tar"
    new = HERE / "seal.oci.tar"
    old_sha = sha256(old)
    new_sha = sha256(new)
    first = load(old)
    second = load(new)
    third = load(old)
    # The userspace planner's host rollback field is not executed here.
    passed = (
        old_sha == PUBLIC_PIN
        and new_sha == POLICY_ALLOW
        and first != ""
        and second != ""
        and first == third
        and first != second
    )
    body = {
        "battery": "upgrade-rollback",
        "descendant_enforcement": "EXCLUDED",
        "planner_host_rollback": "NOT_RUN",
        "public_pin_sha256": old_sha,
        "policy_allow_sha256": new_sha,
        "loaded_public_pin": first,
        "loaded_policy_allow": second,
        "loaded_after_rollback": third,
        "upgrade_rollback_pass": passed,
        "ceiling": "INTERNAL_CLEAN_HOST_PROOF",
    }
    text = json.dumps(body, indent=2) + "\n"
    OUT.write_text(text, encoding="utf-8")
    try:
        OUT.chmod(0o644)
    except OSError:
        pass
    print(text, flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
