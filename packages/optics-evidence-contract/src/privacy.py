"""Value checks. Detection text is never returned to callers."""

import json
import unicodedata
from pathlib import Path

policy = json.loads(
    (Path(__file__).resolve().parent.parent / "contract" / "prohibited-fields.json").read_text(encoding="utf-8")
)

_CONFUSABLE = {pair[0]: pair[1] for pair in policy["confusables"]}
_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


_SAFE_NAME_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")
_EXACT_NAMES = set(policy["prohibited_field_names"])
_SEPARATORS = set("-_ .:/" + "\\|,;\t")
_NAMES = set()
_PAYLOAD = set()
_BAGGAGE = set()


def _name_control(code):
    return (
        code <= 0x1F
        or code == 0x7F
        or code in (0x2028, 0x2029, 0xFEFF)
        or 0x200B <= code <= 0x200F
        or 0x202A <= code <= 0x202E
        or 0x2066 <= code <= 0x2069
    )


def _comparison_form(name):
    if not isinstance(name, str):
        return ""
    text = unicodedata.normalize("NFC", name)
    decoded = _percent_decode_once(text)
    if decoded["changed"] and not decoded["prohibited"] and decoded["text"]:
        text = unicodedata.normalize("NFC", decoded["text"])
    out = []
    for ch in text:
        code = ord(ch)
        if _name_control(code) or ch in _SEPARATORS:
            continue
        if 65 <= code <= 90:
            out.append(chr(code + 32))
        else:
            out.append(ch)
    return "".join(out)


def normalize_name(name):
    return _comparison_form(name)


comparison_form = _comparison_form


def _safe_grammar(name):
    if not name or len(name) > 64:
        return False
    if name[0] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
        return False
    return all(ch in _SAFE_NAME_CHARS for ch in name)


def classify_field_name(name):
    if not isinstance(name, str):
        return {
            "comparison": "",
            "payload": False,
            "baggage": False,
            "prohibited": False,
            "detector": False,
            "control": False,
            "oversized": False,
            "exact": False,
            "safe": False,
            "locator_kind": "redacted",
            "disguised": False,
        }
    control = any(_name_control(ord(ch)) for ch in name)
    oversized = len(name) > 128 or len(name.encode("utf-8")) > 128
    comparison = "" if oversized else _comparison_form(name)
    payload = comparison != "" and comparison in _PAYLOAD
    baggage = comparison != "" and comparison in _BAGGAGE
    prohibited = comparison != "" and comparison in _NAMES
    detector = (not oversized) and contains_prohibited(name)
    exact = name in _EXACT_NAMES
    safe_grammar = (
        not control
        and not detector
        and not oversized
        and unicodedata.normalize("NFC", name) == name
        and _safe_grammar(name)
    )
    locator_kind = "safe" if safe_grammar else "redacted"
    if (payload or prohibited) and not exact:
        locator_kind = "prohibited"
    if exact and not detector and not control and not oversized:
        locator_kind = "safe"
    return {
        "comparison": comparison,
        "payload": payload,
        "baggage": baggage,
        "prohibited": prohibited,
        "detector": detector,
        "control": control,
        "oversized": oversized,
        "exact": exact,
        "safe": locator_kind == "safe",
        "locator_kind": locator_kind,
        "disguised": locator_kind == "prohibited",
    }


def is_prohibited_name(name):
    return normalize_name(name) in _NAMES


def is_payload_name(name):
    return normalize_name(name) in _PAYLOAD


def is_baggage_name(name):
    return normalize_name(name) in _BAGGAGE


def _digit(ch):
    return "0" <= ch <= "9"


def _hex(ch):
    return _digit(ch) or "a" <= ch <= "f" or "A" <= ch <= "F"


def _starts(text, prefix, index):
    if index + len(prefix) > len(text):
        return False
    for i, ch in enumerate(prefix):
        if text[index + i].lower() != ch.lower():
            return False
    return True


def _has_bearer(text):
    lower = text.lower()
    start = 0
    while start < len(lower):
        at = lower.find("bearer", start)
        if at < 0:
            return False
        i = at + 6
        if i >= len(text) or text[i] not in " \t":
            start = at + 6
            continue
        while i < len(text) and text[i] in " \t":
            i += 1
        n = 0
        while i < len(text):
            ch = text[i]
            if not (ch.isalnum() or ch in "-._~+/="):
                break
            n += 1
            i += 1
        if n >= 8:
            return True
        start = at + 6
    return False


def _has_basic(text):
    lower = text.lower()
    start = 0
    while start < len(lower):
        at = lower.find("basic", start)
        if at < 0:
            return False
        i = at + 5
        if i >= len(text) or text[i] not in " \t":
            start = at + 5
            continue
        while i < len(text) and text[i] in " \t":
            i += 1
        n = 0
        while i < len(text):
            ch = text[i]
            if not (ch.isalnum() or ch in "+/="):
                break
            n += 1
            i += 1
        if n >= 8:
            return True
        start = at + 5
    return False


def _has_cookie(text):
    lower = text.lower()
    return "set-cookie" in lower or "cookie:" in lower or "cookie=" in lower


def _has_openai(text):
    for i in range(len(text)):
        for prefix in policy["openai_prefixes"]:
            if not _starts(text, prefix, i):
                continue
            n = 0
            j = i + len(prefix)
            while j < len(text) and text[j].isalnum():
                n += 1
                j += 1
            if n >= policy["openai_tail_min"]:
                return True
    return False


def _cloud_tail(text, start):
    end = start + policy["cloud_akia_tail"]
    if end > len(text):
        return False
    for ch in text[start:end]:
        if not (("A" <= ch <= "Z") or _digit(ch)):
            return False
    return True


def _has_cloud(text):
    for i in range(0, max(0, len(text) - 19)):
        head = text[i:i + 4]
        if head in ("AKIA", "ASIA") and _cloud_tail(text, i + 4):
            return True
    if "AIza" in text or "ya29." in text:
        return True
    for marker in ("xoxb-", "xoxp-", "xoxa-", "ghp_", "github_pat_"):
        if marker in text:
            return True
    return False


def _has_pem(text):
    upper = text.upper()
    return any(marker in upper for marker in policy["pem_markers"])


def _has_jwt(text):
    start = 0
    while start < len(text):
        at = text.find("eyJ", start)
        if at < 0:
            return False
        dot = text.find(".", at + 3)
        if dot < 0 or dot - (at + 3) < 8:
            start = at + 3
            continue
        n = 0
        i = dot + 1
        while i < len(text) and (text[i].isalnum() or text[i] in "-_"):
            n += 1
            i += 1
        if n >= 4:
            return True
        start = at + 3
    return False


def _has_db(text):
    lower = text.lower()
    return any(scheme + "://" in lower for scheme in policy["db_schemes"])


def has_db_scheme(text):
    return _has_db(text)


def _has_userinfo(text):
    scheme = text.find("://")
    if scheme < 0:
        return False
    rest = text[scheme + 3:]
    slash = rest.find("/")
    authority = rest if slash < 0 else rest[:slash]
    return "@" in authority and authority.find("@") > 0


def has_sensitive_query(text):
    q = text.find("?")
    if q < 0:
        return False
    parts = text[q + 1:].split("#", 1)[0].split("&")
    for part in parts:
        if "=" not in part:
            continue
        name = part.split("=", 1)[0].lower()
        if name in policy["sensitive_query_names"]:
            return True
    return False


def _unicode_alnum(ch):
    code = ord(ch)
    if 48 <= code <= 57 or 65 <= code <= 90 or 97 <= code <= 122:
        return True
    if code < 128:
        return False
    return unicodedata.category(ch)[0] in ("L", "N")


def _has_email(text):
    if not isinstance(text, str) or text == "":
        return False
    chars = list(unicodedata.normalize("NFC", text))
    for i, ch in enumerate(chars):
        if ch != "@":
            continue
        left = i - 1
        while left >= 0 and (_unicode_alnum(chars[left]) or chars[left] in "._%+-"):
            left -= 1
        if i - left - 1 < 1:
            continue
        right = i + 1
        dot = -1
        while right < len(chars) and (_unicode_alnum(chars[right]) or chars[right] in ".-"):
            if chars[right] == ".":
                dot = right
            right += 1
        if dot > i + 1 and right - dot - 1 >= 2:
            return True
    return False


def _has_ssn(text):
    i = 0
    while i + 11 <= len(text):
        if i > 0 and _digit(text[i - 1]):
            i += 1
            continue
        chunk = text[i:i + 11]
        if (
            _digit(chunk[0]) and _digit(chunk[1]) and _digit(chunk[2]) and chunk[3] == "-"
            and _digit(chunk[4]) and _digit(chunk[5]) and chunk[6] == "-"
            and _digit(chunk[7]) and _digit(chunk[8]) and _digit(chunk[9]) and _digit(chunk[10])
            and (i + 11 == len(text) or not _digit(text[i + 11]))
        ):
            return True
        i += 1
    return False


def _has_phone(text):
    i = 0
    while i < len(text):
        p = i
        separated = False
        if text[p:p + 1] == "(":
            if not (
                p + 4 < len(text) and _digit(text[p + 1]) and _digit(text[p + 2]) and _digit(text[p + 3]) and text[p + 4] == ")"
            ):
                i += 1
                continue
            p += 5
            separated = True
        else:
            if not (p + 2 < len(text) and _digit(text[p]) and _digit(text[p + 1]) and _digit(text[p + 2])):
                i += 1
                continue
            p += 3
        if p < len(text) and text[p] in "-. ":
            separated = True
            p += 1
        if not (p + 2 < len(text) and _digit(text[p]) and _digit(text[p + 1]) and _digit(text[p + 2])):
            i += 1
            continue
        p += 3
        if p < len(text) and text[p] in "-. ":
            separated = True
            p += 1
        if not separated or not (p + 3 < len(text) and all(_digit(text[p + k]) for k in range(4))):
            i += 1
            continue
        end = p + 4
        before = text[i - 1] if i > 0 else ""
        after = text[end] if end < len(text) else ""
        if _digit(before) or _digit(after):
            i += 1
            continue
        return True
    return False


def _has_card(text):
    i = 0
    while i < len(text):
        if not _digit(text[i]):
            i += 1
            continue
        if i > 0 and _digit(text[i - 1]):
            i += 1
            continue
        digits = 0
        separated = False
        j = i
        while j < len(text):
            if _digit(text[j]):
                digits += 1
                separated = False
                j += 1
                continue
            if text[j] in " -" and not separated and digits > 0 and j + 1 < len(text) and _digit(text[j + 1]):
                separated = True
                j += 1
                continue
            break
        if 13 <= digits <= 19 and (j >= len(text) or not _digit(text[j])):
            before = text[i - 1] if i > 0 else ""
            after = text[j] if j < len(text) else ""
            if not (before.isalpha() or after.isalpha()):
                return True
        i = max(j, i + 1)
    return False


def _has_mrn(text):
    start = 0
    while start < len(text):
        at = text.find("MRN:", start)
        if at < 0:
            return False
        n = 0
        i = at + 4
        while i < len(text) and text[i].isalnum():
            n += 1
            i += 1
        if n >= 6:
            return True
        start = at + 4
    return False


def has_username_path(text):
    return any(marker in text for marker in policy["username_path_markers"])


def scan_direct(text):
    if not text:
        return False
    return (
        _has_pem(text) or _has_bearer(text) or _has_basic(text) or _has_cookie(text)
        or _has_openai(text) or _has_cloud(text) or _has_jwt(text) or _has_db(text)
        or _has_userinfo(text) or has_sensitive_query(text) or _has_email(text)
        or _has_ssn(text) or _has_phone(text) or _has_card(text) or _has_mrn(text)
    )


def _percent_decode_once(text):
    if "%" not in text:
        return {"changed": False, "text": text, "prohibited": False}
    raw = bytearray()
    changed = False
    i = 0
    while i < len(text):
        code = ord(text[i])
        if text[i] == "%" and i + 2 < len(text) and _hex(text[i + 1]) and _hex(text[i + 2]):
            raw.append(int(text[i + 1:i + 3], 16))
            changed = True
            i += 3
            continue
        if code > 127:
            return {"changed": True, "text": "", "prohibited": True}
        raw.append(code)
        i += 1
    if not changed:
        return {"changed": False, "text": text, "prohibited": False}
    try:
        return {"changed": True, "text": raw.decode("utf-8"), "prohibited": False}
    except UnicodeDecodeError:
        return {"changed": True, "text": "", "prohibited": True}


def _fold(text):
    nfkc = unicodedata.normalize("NFKC", text)
    return "".join(_CONFUSABLE.get(ch, ch) for ch in nfkc)


def _b64_char(ch, allow_slash):
    return ch.isalnum() or ch == "+" or (allow_slash and ch == "/")


def _decode_b64(run):
    if len(run) % 4 != 0:
        return None
    raw = bytearray()
    for i in range(0, len(run), 4):
        c0 = _B64.find(run[i])
        c1 = _B64.find(run[i + 1])
        c2raw = run[i + 2]
        c3raw = run[i + 3]
        c2 = 0 if c2raw == "=" else _B64.find(c2raw)
        c3 = 0 if c3raw == "=" else _B64.find(c3raw)
        if c0 < 0 or c1 < 0 or c2 < 0 or c3 < 0:
            return None
        if c2raw == "=" and c3raw != "=":
            return None
        raw.append((c0 << 2) | (c1 >> 4))
        if c2raw != "=":
            raw.append(((c1 & 15) << 4) | (c2 >> 2))
        if c3raw != "=":
            raw.append(((c2 & 3) << 6) | c3)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _scan_runs(text, allow_slash):
    i = 0
    while i < len(text):
        if not _b64_char(text[i], allow_slash) and text[i] != "=":
            i += 1
            continue
        start = i
        while i < len(text) and _b64_char(text[i], allow_slash):
            i += 1
        pads = 0
        while i < len(text) and text[i] == "=" and pads < 2:
            pads += 1
            i += 1
        run = text[start:i]
        if allow_slash and "+" not in run and "=" not in run:
            continue
        body_len = len(run) - pads
        if body_len < policy["base64_min_run"]:
            continue
        if len(run) > policy["base64_max_run"]:
            return True
        interesting = pads > 0 or "+" in run or any("A" <= ch <= "Z" for ch in run)
        if not interesting or len(run) % 4 != 0:
            continue
        decoded = _decode_b64(run)
        if decoded and scan_direct(decoded):
            return True
    return False


def _scan_base64(text):
    if _scan_runs(text, False):
        return True
    if ("=" in text or "+" in text) and "/" in text and _scan_runs(text, True):
        return True
    return False


def contains_prohibited(value):
    if not isinstance(value, str) or value == "":
        return False
    if len(value) > 8192:
        return True
    if scan_direct(value):
        return True
    decoded = _percent_decode_once(value)
    if decoded["prohibited"]:
        return True
    if decoded["changed"] and scan_direct(decoded["text"]):
        return True
    if _scan_base64(value):
        return True
    folded = _fold(value)
    if folded != value and scan_direct(folded):
        return True
    if decoded["changed"]:
        folded_decoded = _fold(decoded["text"])
        if folded_decoded != decoded["text"] and scan_direct(folded_decoded):
            return True
    return False


def sensitive_path(text):
    if not isinstance(text, str) or text == "":
        return False
    nfc = unicodedata.normalize("NFC", text)
    if contains_prohibited(text) or contains_prohibited(nfc) or has_username_path(text) or has_username_path(nfc):
        return True
    decoded = _percent_decode_once(nfc)
    if decoded["prohibited"]:
        return True
    if not decoded["changed"]:
        return False
    form = unicodedata.normalize("NFC", decoded["text"])
    return contains_prohibited(form) or has_username_path(form)


_NAMES.update(_comparison_form(name) for name in policy["prohibited_field_names"])
_PAYLOAD.update(_comparison_form(name) for name in policy["payload_drop_record_names"])
_BAGGAGE.update(_comparison_form(name) for name in policy["baggage_names"])
