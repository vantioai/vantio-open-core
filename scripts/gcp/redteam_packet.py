"""Grade lab observations into a redacted packet. No GCP and no network.

An enrolled open that returns EACCES and a ledger row naming that pid is
HELD. The same deny with no ledger row naming the pid is FAIL_GAP. A
successful open of a protected path is FAIL_GAP with silent_success.
A row that did not run stays GAP.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping

PUBLIC_PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
TRACKING_SEAL = "16c9e5638c169e5fdd3fd7291b3225a809b18abfe464d717c2d31a398d5bda6a"
POLICY_ALLOW_SEAL = "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753"
CLAIM_CAP = "INTERNAL_CLEAN_HOST_PROOF"
OUTCOMES = frozenset({"HELD", "FAIL_GAP", "GAP", "INCONCLUSIVE", "REFUSED_UNSAFE"})
ID_RE = re.compile(r"^[a-z0-9_.]{1,64}$")
REASON_RE = re.compile(r"^[a-z0-9_]{1,48}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_RE = re.compile(r"PRIVATE KEY|ghp_|ya29\.|AKIA[0-9A-Z]{16}")

CASE_TECHNIQUE = {
    "moved": "pe.escape.move",
    "clone3": "pe.escape.clone3",
    "reparent": "pe.escape.reparent",
    "double_fork": "pe.escape.double_fork",
    "setsid": "pe.escape.setsid",
    "unshare": "pe.escape.unshare",
    "setns": "pe.escape.setns",
    "vfork": "pe.escape.vfork",
    "ancestor_8": "pe.escape.cgroup_v2",
}
CASE_ALIAS = {
    "unshare": "pe.escape.namespace",
}
CONTROL_TECHNIQUE = {
    "ancestor_9": "pe.control.ancestor_9",
    "unenrolled": "pe.control.unenrolled",
}


def _row(
    technique_id: str,
    outcome: str,
    *,
    silent: bool = False,
    attributed: bool = False,
    errno: int | None = None,
    reason: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "attributed": attributed,
        "id": technique_id,
        "outcome": outcome,
        "silent_success": silent,
    }
    if errno is not None:
        body["errno"] = errno
    if reason:
        body["reason"] = reason
    return body


def grade_tamper(errno: int | None, attributed: bool) -> dict[str, Any]:
    """Grade a pin or bpf tamper. A deny is HELD only with a ledger row for that pid."""
    if isinstance(errno, bool) or not isinstance(errno, int):
        return {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "not_executed"}
    if errno == 0:
        return {"outcome": "FAIL_GAP", "silent_success": True, "attributed": False, "reason": "tamper_succeeded"}
    if attributed:
        return {"outcome": "HELD", "silent_success": False, "attributed": True, "reason": "attributed_deny"}
    return {"outcome": "FAIL_GAP", "silent_success": False, "attributed": False, "reason": "unattributed_deny"}


def grade_open(errno: int | None, attributed: bool, *, executed: bool = True) -> dict[str, Any]:
    """Grade one enrolled open. EACCES is errno 13, the loader's override."""
    if not executed or errno is None:
        return {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "not_executed"}
    if errno == 0:
        return {
            "outcome": "FAIL_GAP",
            "silent_success": True,
            "attributed": False,
            "reason": "protected_open_succeeded",
        }
    if errno == 13 and attributed:
        return {"outcome": "HELD", "silent_success": False, "attributed": True, "reason": "attributed_deny"}
    if errno == 13:
        return {
            "outcome": "FAIL_GAP",
            "silent_success": False,
            "attributed": False,
            "reason": "unattributed_deny",
        }
    return {"outcome": "INCONCLUSIVE", "silent_success": False, "attributed": False, "reason": "other_errno"}


# DenyAttr in the pinned map. pid at 0, timestamp_ns at 16, kind at 32.
# File denies are kind 1. Self-protection denies are kind 4. Both name the pid.
DENY_KIND_FILE = 1
DENY_KIND_SELF = 4
DENY_ATTR_SIZE = 40


def deny_record_names(record: bytes, pid: int) -> bool:
    """True when a pinned deny slot names this pid."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if len(record) < DENY_ATTR_SIZE:
        return False
    got = int.from_bytes(record[0:4], "little")
    timestamp = int.from_bytes(record[16:24], "little")
    kind = int.from_bytes(record[32:36], "little")
    return got == pid and timestamp != 0 and kind in (DENY_KIND_FILE, DENY_KIND_SELF)


def completion_text(body: bytes) -> str | None:
    """Model text from a llama-server 200 body. An error object is not a completion."""
    text = body.decode(errors="replace").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(parsed, dict) or parsed.get("error"):
        return None
    content = parsed.get("content")
    if not isinstance(content, str) or not content.strip():
        choices = parsed.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            content = choices[0].get("text")
            if not isinstance(content, str):
                message = choices[0].get("message")
                if isinstance(message, dict):
                    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    return None


def fetch_local_completion(port: int, deadline: float) -> tuple[bool, str]:
    """POST 127.0.0.1 only. Retry both llama.cpp routes until a real completion.

    The server accepts TCP before the GGUF is resident and answers 503.
    One failed POST is not a failed model. Nothing here calls a paid API.
    """
    native = json.dumps(
        {"prompt": "Reply with one word: file", "n_predict": 8, "temperature": 0}
    ).encode("utf-8")
    openai = json.dumps(
        {"prompt": "Reply with one word: file", "max_tokens": 8, "temperature": 0}
    ).encode("utf-8")
    routes = (
        (f"http://127.0.0.1:{int(port)}/completion", native),
        (f"http://127.0.0.1:{int(port)}/v1/completions", openai),
    )
    while time.time() < deadline:
        for url, payload in routes:
            request = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    body = response.read(4000)
            except urllib.error.HTTPError:
                continue
            except OSError:
                continue
            text = completion_text(body)
            if text is None:
                continue
            lowered = text.lower()
            if "ignore previous" in lowered or "private key" in lowered:
                return True, "reply_rejected"
            return True, "completion_ok"
        time.sleep(0.2)
    return False, "completion_failed"
