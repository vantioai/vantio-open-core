"""CLI for the lab-only agent inventory. Read-only. No enrollment changes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from optics_agent_inventory.inventory import ScanConfig, scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="optics-agent-inventory",
        description="Lab-only inventory of recognized AI workloads in one procfs view.",
    )
    parser.add_argument("--proc", default="/proc", type=Path)
    parser.add_argument("--mountinfo", type=Path)
    parser.add_argument("--enrollment", type=Path)
    parser.add_argument("--endpoint-map", type=Path)
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--host-id", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    mountinfo = args.mountinfo
    if mountinfo is None and args.proc == Path("/proc"):
        mountinfo = Path("/proc/self/mountinfo")
    report, code = scan(
        ScanConfig(
            proc_root=args.proc,
            host_id=args.host_id,
            euid=os.geteuid(),
            enrollment_path=args.enrollment,
            endpoint_map_path=args.endpoint_map,
            mountinfo_path=mountinfo,
            runs_dir=args.runs_dir,
        )
    )
    payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    sys.stdout.buffer.write(payload)
    if args.out is not None:
        try:
            fd = os.open(os.fspath(args.out), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except OSError as err:
            sys.stderr.write(f"optics-agent-inventory: could not create output file: {err.errno}\n")
            return 2
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
