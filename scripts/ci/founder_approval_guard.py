#!/usr/bin/env python3
"""Fail a PR that touches protected paths unless a repo admin applied the
founder-approved label after the PR's latest push.

Runs from the BASE branch under pull_request_target. It never checks out or
executes PR code. Uses only the GitHub REST API with GITHUB_TOKEN.
"""
from __future__ import annotations

import fnmatch
import json
import os
import sys
import urllib.request
from pathlib import Path

LABEL = os.environ.get("FOUNDER_LABEL", "founder-approved")
API = os.environ.get("GITHUB_API_URL", "https://api.github.com")


def gh(path: str, method: str = "GET") -> object:
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        return json.loads(body) if body else None


def paged(path: str) -> list:
    out, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        chunk = gh(f"{path}{sep}per_page=100&page={page}")
        if not chunk:
            return out
        out.extend(chunk)
        if len(chunk) < 100:
            return out
        page += 1


def load_globs(path: Path) -> list[str]:
    globs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            globs.append(line)
    return globs


def protected_hits(files: list[dict], globs: list[str]) -> list[str]:
    hits = []
    for f in files:
        for name in {f.get("filename"), f.get("previous_filename")} - {None}:
            if any(fnmatch.fnmatchcase(name, g) for g in globs):
                hits.append(name)
    return sorted(set(hits))


def latest_label_event(events: list[dict]) -> dict | None:
    """Most recent labeled/unlabeled event for LABEL, in API order."""
    last = None
    for ev in events:
        if ev.get("event") in ("labeled", "unlabeled") and (ev.get("label") or {}).get("name") == LABEL:
            last = ev
    return last


def decide(hits, labels, label_event, actor_permission) -> tuple[bool, str]:
    if not hits:
        return True, "no protected paths changed"
    if LABEL not in labels:
        return False, f"protected paths changed and the '{LABEL}' label is missing"
    if not label_event or label_event.get("event") != "labeled":
        return False, f"no '{LABEL}' labeled event found"
    if actor_permission != "admin":
        return False, f"'{LABEL}' was applied by a non-admin ({(label_event.get('actor') or {}).get('login')})"
    return True, f"'{LABEL}' applied by admin {(label_event.get('actor') or {}).get('login')}"


def main() -> int:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    repo = os.environ["GITHUB_REPOSITORY"]
    pr = event["pull_request"]
    num = pr["number"]
    action = event.get("action")
    labels = {l["name"] for l in pr.get("labels", [])}

    # A new push invalidates any earlier approval: drop the label, then fail.
    if action == "synchronize" and LABEL in labels:
        gh(f"/repos/{repo}/issues/{num}/labels/{LABEL}", method="DELETE")
        labels.discard(LABEL)
        print(f"removed '{LABEL}' after a new push; re-approval required")

    globs = load_globs(Path(os.environ.get("GUARD_PATHS", ".github/founder-approval-paths.txt")))
    files = paged(f"/repos/{repo}/pulls/{num}/files")
    hits = protected_hits(files, globs)
    label_event, perm = None, None
    if hits and LABEL in labels:
        label_event = latest_label_event(paged(f"/repos/{repo}/issues/{num}/events"))
        login = ((label_event or {}).get("actor") or {}).get("login")
        if login:
            perm = gh(f"/repos/{repo}/collaborators/{login}/permission").get("permission")
    ok, why = decide(hits, labels, label_event, perm)
    print(json.dumps({"pr": num, "head": pr["head"]["sha"], "protected_hits": hits, "ok": ok, "reason": why}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
