#!/usr/bin/env python3
"""H-U guest host evidence: names and presence only.

The row is captured on the lab guest before any battery is graded. It records
mount points and filesystem types, whether a few named paths exist, and two
fields from staged trust files. It does not read credential files, key bytes,
or prompts.

scripts/release does not open a production signing-key path or environment
variable. The name this row refuses is private-key.pem, the filename the lab
bundle refuses to stage. signer_kid is a separate item: release/pe-canonical-seal.json
on the guest must contain JSON null.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tarfile
from pathlib import Path
from typing import Mapping

SCHEMA = "vantio.lab.host-evidence.h-u/v1"
ITEM_NAMES = (
    "mounts",
    "cursor_stores",
    "credential_paths",
    "production_signing_key",
    "staged_trust",
    "signer_kid",
)
TRUST_FILENAMES = frozenset(
    {
        "lab-artifact-trust.json",
        "lab-dev-trust.json",
        "signature.json",
        "test_nonprod_2026_10_02.json",
    }
)
TAR_NAMES = ("contract.tar", "self-service.tar", "t5-egress.tar")
CREDENTIAL_TAILS = (
    Path(".config") / "gh",
    Path(".aws") / "credentials",
    Path(".config") / "gcloud",
)
MOUNT_RE = re.compile(r"^/[A-Za-z0-9._+/-]{0,200}$")
FSTYPE_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
PATH_RE = re.compile(r"^/[A-Za-z0-9._+/-]{1,200}$")
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
KEY_ID_RE = re.compile(r"^(test|dev)-nonprod-[a-z0-9-]+$")
KEY_CLASSES = frozenset({"test", "test_non_production", "dev_non_production"})
ITEM_LINE = re.compile(r"^H-U item=([a-z_]+) result=(PASS|STOP)$")
VERDICT_LINE = re.compile(r"^H-U verdict=(PASS|STOP)$")
JSON_LINE = re.compile(r"^H-U-JSON \{.*\}$")
MAX_JSON = 65536
MAX_MOUNTS = 256
MAX_TAR = 50_000_000


def passing_facts() -> dict:
    """Synthetic facts a unit test can grade. Not read from a host."""
    return {
        "mounts_readable": True,
        "mounts": [{"fstype": "ext4", "mount": "/"}, {"fstype": "proc", "mount": "/proc"}],
        "cursor_stores": "absent",
        "credential_paths": "absent",
        "credential_hits": [],
        "production_signing_key": "absent",
        "signing_key_hits": [],
        "trust_docs": 1,
        "trust_nonprod": True,
        "trust_unreadable": False,
        "bundle_names_clean": True,
        "expect_trust": "some",
        "none_staged": False,
        "signer_kid_null": True,
    }


def grade(facts: object) -> dict:
    """Turn collected facts into the public row. Unknown fact keys are ignored."""
    body = facts if isinstance(facts, dict) else {}
    mounts = _clean_mounts(body.get("mounts"))
    mounts_ok = body.get("mounts_readable") is True and bool(mounts)
    cursor = body.get("cursor_stores")
    cursor_ok = cursor == "absent" and not _cursor_mounted(mounts)
    if _cursor_mounted(mounts):
        cursor_ok = False
    credential_ok = body.get("credential_paths") == "absent" and not _hits(body.get("credential_hits"))
    signing_ok = body.get("production_signing_key") == "absent" and not _hits(body.get("signing_key_hits"))
    trust_ok = _trust_ok(body)
    signer_ok = body.get("signer_kid_null") is True
    items = [
        {"name": "mounts", "result": _word(mounts_ok)},
        {"name": "cursor_stores", "result": _word(cursor_ok)},
        {"name": "credential_paths", "result": _word(credential_ok)},
        {"name": "production_signing_key", "result": _word(signing_ok)},
        {"name": "staged_trust", "result": _word(trust_ok)},
        {"name": "signer_kid", "result": _word(signer_ok)},
    ]
    verdict = "PASS" if all(item["result"] == "PASS" for item in items) else "STOP"
    document: dict = {
        "items": items,
        "mounts": mounts if mounts_ok else [],
        "schema": SCHEMA,
        "verdict": verdict,
    }
    if signer_ok:
        document["signer_kid"] = None
    if trust_ok and body.get("expect_trust") == "none" and body.get("none_staged") is True:
        document["none_staged"] = True
    present = _safe_paths(_hits(body.get("credential_hits")) + _hits(body.get("signing_key_hits")))
    if present:
        document["present"] = present
        document["verdict"] = "STOP"
    return document


def transcript(facts: Mapping) -> str:
    """Guest stdout: one line per item, the verdict, then facts for a re-grade."""
    document = grade(facts)
    lines = [f"H-U item={item['name']} result={item['result']}" for item in document["items"]]
    lines.append(f"H-U verdict={document['verdict']}")
    payload = {"facts": _public_facts(facts), "schema": SCHEMA}
    lines.append("H-U-JSON " + json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return "\n".join(lines) + "\n"


def accept_transcript(text: str, *, expect_trust: str | None = None) -> dict:
    """Re-grade one transcript. Extra, missing, or reordered H-U lines are STOP."""
    if len(text) > 200_000:
        return _missing()
    items: list[str] = []
    verdicts: list[str] = []
    blobs: list[str] = []
    for raw in text.splitlines():
        if not raw.startswith("H-U"):
            continue
        if ITEM_LINE.fullmatch(raw):
            items.append(raw)
        elif VERDICT_LINE.fullmatch(raw):
            verdicts.append(raw)
        elif JSON_LINE.fullmatch(raw):
            blobs.append(raw)
        else:
            return _missing()
    if len(items) != 6 or len(verdicts) != 1 or len(blobs) != 1:
        return _missing()
    names: list[str] = []
    results: list[str] = []
    for line in items:
        matched = ITEM_LINE.fullmatch(line)
        if matched is None:
            return _missing()
        names.append(matched.group(1))
        results.append(matched.group(2))
    if tuple(names) != ITEM_NAMES:
        return _missing()
    raw_json = blobs[0][len("H-U-JSON ") :]
    if len(raw_json) > MAX_JSON:
        return _missing()
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return _missing()
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        return _missing()
    facts = payload.get("facts")
    document = grade(facts)
    graded = [item["result"] for item in document["items"]]
    verdict_word = VERDICT_LINE.fullmatch(verdicts[0])
    if verdict_word is None or results != graded or verdict_word.group(1) != document["verdict"]:
        document["verdict"] = "STOP"
    if expect_trust in {"some", "none"}:
        printed = facts.get("expect_trust") if isinstance(facts, dict) else None
        if printed != expect_trust:
            document["verdict"] = "STOP"
    return document


def collect(bundle: Path, *, root: Path | None = None, mounts_text: str | None = None) -> dict:
    """Stat names under root. root None means the guest filesystem."""
    fs = root if root is not None else Path("/")
    mounts, readable = _mounts(fs, mounts_text)
    homes, homes_readable = _homes(fs)
    credential_state, credential_hits = _group(_credential_paths(homes))
    if not homes_readable:
        credential_state = "unreadable"
    signing_state, signing_hits = _group(_signing_paths(fs, bundle, homes))
    if not homes_readable and signing_state == "absent":
        signing_state = "unreadable"
    trust_docs, trust_nonprod, trust_unreadable = _trust(bundle)
    cursor = _presence(fs / "cursor" / "stores")
    if _cursor_mounted(mounts):
        cursor = "present"
    return {
        "credential_hits": credential_hits,
        "credential_paths": credential_state,
        "cursor_stores": cursor,
        "mounts": mounts,
        "mounts_readable": readable,
        "bundle_names_clean": _bundle_names_clean(bundle),
        "expect_trust": "some",
        "none_staged": False,
        "production_signing_key": signing_state,
        "signer_kid_null": _signer_kid_null(bundle),
        "signing_key_hits": signing_hits,
        "trust_docs": trust_docs,
        "trust_nonprod": trust_nonprod,
        "trust_unreadable": trust_unreadable,
    }


def write_public(path: Path, payload: Mapping) -> None:
    """Rewrite an H-U file to the public fields and a sha256 sidecar."""
    clean = public_from_mapping(payload)
    text = json.dumps(clean, indent=2, sort_keys=True) + "\n"
    if "PRIVATE KEY" in text or "ghp_" in text or "BEGIN " in text:
        raise ValueError("token_in_evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("evidence_symlink")
    path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    if sidecar.is_symlink():
        raise ValueError("evidence_symlink")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")


def public_from_mapping(payload: Mapping) -> dict:
    """Keep schema, verdict, items, mounts, and a null signer_kid. Drop the rest."""
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("h_u")
    verdict = payload.get("verdict")
    if verdict not in {"PASS", "STOP"}:
        raise ValueError("h_u")
    items_in = payload.get("items")
    if not isinstance(items_in, list):
        raise ValueError("h_u")
    by_name: dict[str, str] = {}
    for item in items_in:
        if not isinstance(item, dict):
            raise ValueError("h_u")
        name = item.get("name")
        result = item.get("result")
        if name not in ITEM_NAMES or result not in {"PASS", "STOP"}:
            raise ValueError("h_u")
        by_name[name] = result
    if set(by_name) != set(ITEM_NAMES):
        raise ValueError("h_u")
    mounts = _clean_mounts(payload.get("mounts"))
    if by_name["mounts"] == "PASS" and not mounts:
        raise ValueError("h_u")
    document: dict = {
        "items": [{"name": name, "result": by_name[name]} for name in ITEM_NAMES],
        "mounts": mounts,
        "schema": SCHEMA,
        "verdict": verdict,
    }
    if by_name["signer_kid"] == "PASS":
        if payload.get("signer_kid") is not None:
            raise ValueError("h_u")
        document["signer_kid"] = None
    elif "signer_kid" in payload and payload.get("signer_kid") is not None:
        raise ValueError("h_u")
    if payload.get("none_staged") is True and by_name["staged_trust"] == "PASS":
        document["none_staged"] = True
    elif "none_staged" in payload and payload.get("none_staged") is not True:
        raise ValueError("h_u")
    present = payload.get("present")
    if present not in (None, []):
        safe = _safe_paths(present if isinstance(present, list) else ["bad"])
        if not isinstance(present, list) or safe != present:
            raise ValueError("h_u")
        document["present"] = safe
        if verdict == "PASS":
            raise ValueError("h_u")
    if verdict == "PASS" and any(item["result"] != "PASS" for item in document["items"]):
        raise ValueError("h_u")
    return document


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except Exception:
        sys.stdout.write(transcript(_exception_facts()))
        return 6


def _main(argv: list[str] | None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    bundle = Path("/var/lib/vantio-lab/guest")
    out: Path | None = None
    expect = "some"
    index = 0
    while index < len(args):
        flag = args[index]
        if flag in {"--bundle", "--out", "--expect-trust"} and index + 1 < len(args):
            value = args[index + 1]
            if flag == "--bundle":
                bundle = Path(value)
            elif flag == "--out":
                out = Path(value)
            elif value not in {"some", "none"}:
                print(_usage(), file=sys.stderr)
                return 2
            else:
                expect = value
            index += 2
            continue
        print(_usage(), file=sys.stderr)
        return 2
    facts = _with_expect(collect(bundle), expect)
    document = grade(facts)
    sys.stdout.write(transcript(facts))
    if out is not None:
        try:
            write_public(out, document)
        except (OSError, ValueError):
            print("H-U file not written", file=sys.stderr)
            return 6
    return 0 if document["verdict"] == "PASS" else 6


def _word(ok: bool) -> str:
    return "PASS" if ok else "STOP"


def _missing() -> dict:
    return {
        "items": [{"name": name, "result": "STOP"} for name in ITEM_NAMES],
        "mounts": [],
        "schema": SCHEMA,
        "verdict": "STOP",
    }


def _usage() -> str:
    return "usage: host_evidence_hu.py --bundle DIR [--out FILE] [--expect-trust some|none]"


def _with_expect(facts: Mapping, expect: str) -> dict:
    """Absent means some. The guest does not choose none by itself."""
    body = dict(facts)
    mode = expect if expect in {"some", "none"} else "some"
    body["expect_trust"] = mode
    body["none_staged"] = (
        mode == "none"
        and body.get("trust_docs") == 0
        and not isinstance(body.get("trust_docs"), bool)
        and body.get("trust_unreadable") is not True
        and body.get("bundle_names_clean") is True
    )
    return body


def _exception_facts() -> dict:
    return {
        "bundle_names_clean": False,
        "credential_hits": [],
        "credential_paths": "unreadable",
        "cursor_stores": "unreadable",
        "error": "exception",
        "expect_trust": "some",
        "mounts": [],
        "mounts_readable": False,
        "none_staged": False,
        "production_signing_key": "unreadable",
        "signer_kid_null": False,
        "signing_key_hits": [],
        "trust_docs": 0,
        "trust_nonprod": False,
        "trust_unreadable": True,
    }


def _trust_ok(body: Mapping) -> bool:
    expect = body.get("expect_trust")
    if expect not in {"some", "none"}:
        expect = "some"
    if body.get("trust_unreadable") is True:
        return False
    docs = body.get("trust_docs")
    if isinstance(docs, bool) or not isinstance(docs, int):
        return False
    if expect == "none":
        return docs == 0 and body.get("bundle_names_clean") is True and body.get("none_staged") is True
    return docs >= 1 and body.get("trust_nonprod") is True


def _public_facts(facts: Mapping) -> dict:
    """Facts the guest may print. Mounts and path names only."""
    graded = grade(facts)
    body = facts if isinstance(facts, dict) else {}

    def _state(key: str) -> str:
        value = body.get(key)
        if value in {"absent", "present", "unreadable"}:
            return value
        return "unreadable"

    docs = body.get("trust_docs")
    if isinstance(docs, bool) or not isinstance(docs, int):
        docs = 0
    expect = body.get("expect_trust")
    if expect not in {"some", "none"}:
        expect = "some"
    public = {
        "bundle_names_clean": body.get("bundle_names_clean") is True,
        "credential_hits": _safe_paths(_hits(body.get("credential_hits"))),
        "credential_paths": _state("credential_paths"),
        "cursor_stores": _state("cursor_stores"),
        "expect_trust": expect,
        "mounts": graded["mounts"] if body.get("mounts_readable") is True else [],
        "mounts_readable": body.get("mounts_readable") is True and bool(graded["mounts"]),
        "none_staged": body.get("none_staged") is True,
        "production_signing_key": _state("production_signing_key"),
        "signer_kid_null": body.get("signer_kid_null") is True,
        "signing_key_hits": _safe_paths(_hits(body.get("signing_key_hits"))),
        "trust_docs": docs,
        "trust_nonprod": body.get("trust_nonprod") is True,
        "trust_unreadable": body.get("trust_unreadable") is True,
    }
    if body.get("error") == "exception":
        public["error"] = "exception"
    return public


def _clean_mounts(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > MAX_MOUNTS:
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            return []
        mount = item.get("mount")
        fstype = item.get("fstype")
        if not isinstance(mount, str) or not isinstance(fstype, str):
            return []
        if MOUNT_RE.fullmatch(mount) is None or FSTYPE_RE.fullmatch(fstype) is None:
            return []
        if set(item) - {"mount", "fstype"}:
            return []
        rows.append({"fstype": fstype, "mount": mount})
    return rows


def _cursor_mounted(mounts: list[dict[str, str]]) -> bool:
    for row in mounts:
        mount = row["mount"]
        if mount == "/cursor/stores" or mount.startswith("/cursor/stores/"):
            return True
    return False


def _hits(value: object) -> list[str]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        return ["bad"]
    return [item for item in value if isinstance(item, str)]


def _safe_paths(paths: list[str]) -> list[str]:
    kept: list[str] = []
    for path in paths:
        if PATH_RE.fullmatch(path) is None:
            continue
        kept.append(path)
    return kept


def _mounts(root: Path, mounts_text: str | None) -> tuple[list[dict[str, str]], bool]:
    if mounts_text is None:
        for relative in (Path("proc/self/mounts"), Path("proc/mounts")):
            path = root / relative
            try:
                mounts_text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                mounts_text = None
                continue
            break
    if not isinstance(mounts_text, str) or not mounts_text.strip():
        return [], False
    rows: list[dict[str, str]] = []
    for line in mounts_text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3 or "\\" in parts[1]:
            return [], False
        mount, fstype = parts[1], parts[2]
        if MOUNT_RE.fullmatch(mount) is None or FSTYPE_RE.fullmatch(fstype) is None:
            return [], False
        rows.append({"fstype": fstype, "mount": mount})
        if len(rows) > MAX_MOUNTS:
            return [], False
    if not rows:
        return [], False
    return rows, True


def _homes(root: Path) -> tuple[list[Path], bool]:
    """Homes under root, including every /home/* name. One path for live and tests."""
    found = [root / "root"]
    readable = _home_children(root / "home", found)
    if root == Path("/"):
        try:
            found.append(Path(pwd.getpwuid(os.getuid()).pw_dir))
        except KeyError:
            pass
        sudo_user = os.environ.get("SUDO_USER", "")
        if USER_RE.fullmatch(sudo_user or ""):
            found.append(Path("/home") / sudo_user)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in found:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique, readable


def _home_children(home: Path, found: list[Path]) -> bool:
    try:
        info = home.lstat()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if not stat.S_ISDIR(info.st_mode):
        return False
    try:
        children = list(home.iterdir())
    except OSError:
        return False
    for child in children:
        try:
            child_info = child.lstat()
        except OSError:
            return False
        if stat.S_ISDIR(child_info.st_mode) and USER_RE.fullmatch(child.name):
            found.append(child)
    return True


def _credential_paths(homes: list[Path]) -> list[Path]:
    return [home / tail for home in homes for tail in CREDENTIAL_TAILS]


def _signing_paths(root: Path, bundle: Path, homes: list[Path]) -> list[Path]:
    paths = [
        bundle / "private-key.pem",
        bundle / "vantio_install" / "trust" / "private-key.pem",
        root / "opt" / "vantio-enterprise" / "private-key.pem",
        root / "opt" / "vantio-enterprise" / "vantio_enterprise_protocol" / "private-key.pem",
    ]
    for home in homes:
        paths.append(home / "private-key.pem")
        paths.append(home / ".config" / "vantio" / "private-key.pem")
    return paths


def _presence(path: Path) -> str:
    try:
        path.lstat()
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable"
    return "present"


def _group(paths: list[Path]) -> tuple[str, list[str]]:
    hits: list[str] = []
    state = "absent"
    for path in paths:
        found = _presence(path)
        if found == "absent":
            continue
        shown = path.as_posix()
        if not shown.startswith("/"):
            shown = "/" + shown
        hits.append(shown)
        if found == "unreadable":
            state = "unreadable"
        elif state != "unreadable":
            state = "present"
    return state, hits


def _trust(bundle: Path) -> tuple[int, bool, bool]:
    payloads = _trust_payloads(bundle)
    if any(item is False for item in payloads):
        return 0, False, True
    if not payloads:
        return 0, True, False
    ok = all(_document_ok(payload) for payload in payloads)
    return len(payloads), ok, False


def _forbidden_name(name: str) -> bool:
    if name.endswith(".pem") or name.endswith(".key"):
        return True
    return name.endswith(".json") and "trust" in name


def _bundle_names_clean(bundle: Path) -> bool:
    """Names only. No file bytes. A pem, key, or trust json is not clean."""
    if not bundle.is_dir():
        return False
    try:
        for path in bundle.rglob("*"):
            if _forbidden_name(path.name):
                return False
            if path.is_symlink():
                continue
            if path.is_file() and path.name.endswith(".tar"):
                if not _tar_names_clean(path):
                    return False
    except OSError:
        return False
    return True


def _tar_names_clean(path: Path) -> bool:
    try:
        if path.stat().st_size <= 0 or path.stat().st_size > MAX_TAR:
            return False
        with tarfile.open(path, "r:*") as tar:
            for member in tar.getmembers():
                base = member.name.rsplit("/", 1)[-1]
                if _forbidden_name(base):
                    return False
    except (OSError, tarfile.TarError, ValueError):
        return False
    return True


def _trust_payloads(bundle: Path) -> list[object]:
    if not bundle.is_dir():
        return []
    found: list[object] = []
    candidates = [bundle / name for name in TRUST_FILENAMES]
    candidates.append(bundle / "vantio_enterprise_protocol" / "trust" / "test_nonprod_2026_10_02.json")
    try:
        children = list(bundle.iterdir())
    except OSError:
        return [False]
    for child in children:
        if not child.is_dir():
            continue
        for name in TRUST_FILENAMES:
            candidates.append(child / name)
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        found.append(_read_json_file(path))
    for name in TAR_NAMES:
        tar_path = bundle / name
        if tar_path.is_file():
            found.extend(_tar_trust(tar_path))
    return found


def _read_json_file(path: Path) -> object:
    try:
        if path.stat().st_size <= 0 or path.stat().st_size > MAX_JSON:
            return False
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False


def _tar_trust(path: Path) -> list[object]:
    found: list[object] = []
    try:
        if path.stat().st_size <= 0 or path.stat().st_size > MAX_TAR:
            return [False]
        with tarfile.open(path, "r:*") as tar:
            for member in tar.getmembers():
                name = member.name
                if name.startswith("/") or ".." in name.split("/"):
                    continue
                if name.rsplit("/", 1)[-1] not in TRUST_FILENAMES:
                    continue
                if not member.isfile() or member.size <= 0 or member.size > MAX_JSON:
                    return [False]
                handle = tar.extractfile(member)
                if handle is None:
                    return [False]
                raw = handle.read(MAX_JSON + 1)
                if len(raw) > MAX_JSON:
                    return [False]
                try:
                    found.append(json.loads(raw.decode("utf-8")))
                except (UnicodeError, json.JSONDecodeError):
                    return [False]
    except (OSError, tarfile.TarError, ValueError):
        return [False]
    return found


def _document_ok(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if "not_a_production_root" in payload and payload.get("not_a_production_root") is not True:
        return False
    keys = payload.get("keys")
    records: list[dict] = []
    if isinstance(keys, list) and keys:
        records.extend(item for item in keys if isinstance(item, dict))
        if len(records) != len(keys):
            return False
    else:
        records.append(payload)
    return bool(records) and all(_record_ok(item) for item in records)


def _record_ok(record: Mapping) -> bool:
    if record.get("not_a_production_root") is not True:
        return False
    key_id = record.get("key_id")
    if not isinstance(key_id, str) or KEY_ID_RE.fullmatch(key_id) is None or key_id.startswith("prod-"):
        return False
    key_class = record.get("key_class")
    if key_class is None:
        return True
    if not isinstance(key_class, str) or key_class == "production":
        return False
    return key_class in KEY_CLASSES


def _signer_kid_null(bundle: Path) -> bool:
    path = bundle / "pe-canonical-seal.json"
    try:
        if not path.is_file() or path.stat().st_size <= 0 or path.stat().st_size > MAX_JSON:
            return False
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(body, dict) or "signer_kid" not in body:
        return False
    return body.get("signer_kid") is None


if __name__ == "__main__":
    raise SystemExit(main())
