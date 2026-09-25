#!/usr/bin/env python3
"""Download two named assets from a draft custody release. Never builds."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TAG_RE = re.compile(r"^custody-py-[0-9]+\.[0-9]+\.[0-9]+$")
WHEEL_RE = re.compile(r"^vantio_agent_sdk-[0-9]+\.[0-9]+\.[0-9]+-py3-none-any\.whl$")
SDIST_RE = re.compile(r"^vantio_agent_sdk-[0-9]+\.[0-9]+\.[0-9]+\.tar\.gz$")
REPO = "vantioai/vantio-open-core"


def fail(message: str) -> None:
    sys.stderr.write(f"vantio-release: {message}\n")
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch sealed PyPI assets from custody")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--wheel-name", required=True)
    parser.add_argument("--sdist-name", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not TAG_RE.match(args.tag):
        fail("custody tag is not a Python custody tag")
    if not WHEEL_RE.match(args.wheel_name) or args.version not in args.wheel_name:
        fail("wheel filename does not match the requested version")
    if not SDIST_RE.match(args.sdist_name) or args.version not in args.sdist_name:
        fail("sdist filename does not match the requested version")
    for name in (args.wheel_name, args.sdist_name):
        if any(char in name for char in "*?[]"):
            fail("asset name must be exact")

    dest = Path(args.dest)
    commands = []
    for name in (args.wheel_name, args.sdist_name):
        commands.append(
            [
                "gh",
                "release",
                "download",
                args.tag,
                "--repo",
                REPO,
                "--pattern",
                name,
                "--dir",
                str(dest),
                "--clobber",
            ]
        )
    if args.dry_run:
        for command in commands:
            sys.stdout.write(" ".join(command) + "\n")
        return
    dest.mkdir(parents=True, exist_ok=True)
    for command in commands:
        result = subprocess.run(command, check=False)
        asset_name = command[7]
        if result.returncode != 0:
            fail(f"custody download failed for {asset_name}")
        if not (dest / asset_name).is_file():
            fail(f"custody download did not produce {asset_name}")


if __name__ == "__main__":
    main()
