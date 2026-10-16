"""Run one named drill and write its evidence file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from t5_egress.drills import DRILLS
from t5_egress.net_setup import netns_inode
from t5_egress.policy import load_policy_file


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print("usage: runner.py <drill-id> <evidence-path> <policy-path> [parent-netns-inode]", file=sys.stderr)
        return 2
    drill_id, evidence_path, policy_path = argv[0], argv[1], argv[2]
    parent_inode = int(argv[3]) if len(argv) == 4 else None
    drill = DRILLS.get(drill_id)
    if drill is None:
        print("unknown drill", file=sys.stderr)
        return 2
    policy = load_policy_file(Path(policy_path))
    if drill_id == "t5-symlink-escape":
        record = drill()
    else:
        record = drill(policy)
    record["ns_net_inode"] = netns_inode()
    record["parent_netns_inode"] = parent_inode
    record["ns_mnt_inode"] = Path("/proc/self/ns/mnt").stat().st_ino
    Path(evidence_path).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if record["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
