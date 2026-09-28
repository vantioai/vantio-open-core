"""Small helpers. No installer success decisions live here."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_PEM = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_AKIA = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_AWS_SECRET = re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*\S+")
_AWS_KEY = re.compile(r"(?i)aws_access_key_id\s*[:=]\s*\S+")
_TOKEN = re.compile(r"\b(?:ghp_|github_pat_|glpat-|npm_|xox[baprs]-)[A-Za-z0-9_\-]{8,}\b")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*")
_HOME = re.compile(r"/home/vantioai\S*")
_SANDBOX = re.compile(r"vantio-sandbox")
_TOKEN_PATH = re.compile(r"absolute_control/secret\.token")
_PHANTOM = re.compile(r"(?i)phantom-box")
_CRM = re.compile(r"\bCRM\b")


def now_et() -> str:
    return datetime.now(ET).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path: Path, payload: object) -> None:
    atomic_write(path, canonical_json(payload))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def redact_text(text: str) -> str:
    """Replace secret-shaped and company-host strings before they land in a bundle."""
    text = _PEM.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _AKIA.sub("[REDACTED_AWS_ACCESS_KEY]", text)
    text = _AWS_SECRET.sub("aws_secret_access_key=[REDACTED]", text)
    text = _AWS_KEY.sub("aws_access_key_id=[REDACTED]", text)
    text = _TOKEN.sub("[REDACTED_TOKEN]", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _HOME.sub("[REDACTED_PATH]", text)
    text = _SANDBOX.sub("[REDACTED_PATH]", text)
    text = _TOKEN_PATH.sub("[REDACTED_PATH]", text)
    text = _PHANTOM.sub("[REDACTED_INTERNAL]", text)
    text = _CRM.sub("[REDACTED_INTERNAL]", text)
    return text


def pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
