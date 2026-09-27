"""Value checks. Detection text is never returned to callers."""

import json
from pathlib import Path

import unicode_profile

_CONTRACT = Path(__file__).resolve().parent.parent / "contract"
policy = json.loads((_CONTRACT / "prohibited-fields.json").read_text(encoding="utf-8"))
detector_spec = json.loads((_CONTRACT / "detector-classes.json").read_text(encoding="utf-8"))
_FIELD_NAME_MAX_BYTES = json.loads((_CONTRACT / "normalization.json").read_text(encoding="utf-8"))["bounds"]["field_name_max_bytes"]

_CONFUSABLE = {pair[0]: pair[1] for pair in policy["confusables"]}
_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_CLASS_CODES = {}


def utf8_bytes(text):
    """UTF-8 byte length. Lone surrogates count as 3 bytes, matching Node Buffer.byteLength."""
    if not isinstance(text, str):
        return 0
    total = 0
    index = 0
    length = len(text)
    while index < length:
        code = ord(text[index])
        if 0xD800 <= code <= 0xDBFF and index + 1 < length:
            nxt = ord(text[index + 1])
            if 0xDC00 <= nxt <= 0xDFFF:
                total += 4
                index += 2
                continue
        if code <= 0x7F:
            total += 1
        elif code <= 0x7FF:
            total += 2
        elif code <= 0xFFFF:
            total += 3
        else:
            total += 4
        index += 1
    return total


def _class_codes(name):
    if name in _CLASS_CODES:
        return _CLASS_CODES[name]
    definition = detector_spec["classes"].get(name) or {}
    codes = set()
    for part in definition.get("union") or []:
        codes.update(_class_codes(part))
    for pair in definition.get("ranges") or []:
        codes.update(range(pair[0], pair[1] + 1))
    for code in definition.get("codepoints") or []:
        codes.add(code)
    _CLASS_CODES[name] = codes
    return codes


_ASCII_ALPHA = _class_codes("ASCII_ALPHA")
_ASCII_DIGIT = _class_codes("ASCII_DIGIT")
_ASCII_ALNUM = _class_codes("ASCII_ALNUM")
_ASCII_HEX = _class_codes("ASCII_HEX")
_BEARER_EXTRA = set(detector_spec["tails"]["bearer"]["extra"])
_BASIC_EXTRA = set(detector_spec["tails"]["basic"]["extra"])
_JWT_EXTRA = set(detector_spec["tails"]["jwt_extra"])
_PAN_SEPARATORS = set(detector_spec["pan"]["separators"])
_BASE64_EXTRA = set(detector_spec["base64_standard_extra"])


def _unit_code(ch):
    if not ch:
        return -1
    return ord(ch)


def _in_class(ch, codes):
    code = _unit_code(ch)
    return code >= 0 and code in codes


def _non_ascii(ch):
    return _unit_code(ch) > detector_spec["non_ascii"]["min_exclusive"]


def _ascii_map(text, spec):
    out = []
    for ch in text:
        code = ord(ch)
        if spec["from"] <= code <= spec["to"]:
            out.append(chr(code + spec["delta"]))
        else:
            out.append(ch)
    return "".join(out)


def ascii_fold(text):
    return _ascii_map(text, detector_spec["ascii_case_fold"]["lower"])


def ascii_fold_upper(text):
    return _ascii_map(text, detector_spec["ascii_case_fold"]["upper"])


def _contract_form(text, form):
    normalized = unicode_profile.normalize_text(text, form)
    if not normalized["ok"]:
        return None
    return normalized["text"]


def contract_nfc(text):
    return _contract_form(text, "NFC")


def _strip_format(text):
    parts = []
    changed = False
    for ch in text:
        if unicode_profile.is_format(ord(ch)):
            changed = True
            continue
        parts.append(ch)
    if not changed:
        return text
    return "".join(parts)


def _match_prefix_at(text, prefix, index, case_sensitive):
    cursor = index
    skipped = 0
    part = 0
    while part < len(prefix):
        if cursor >= len(text):
            return -1
        got = text[cursor]
        want = prefix[part]
        same = got == want if case_sensitive else ascii_fold(got) == ascii_fold(want)
        if same:
            cursor += 1
            part += 1
            continue
        if part > 0 and skipped < 1 and _non_ascii(got):
            skipped += 1
            cursor += 1
            continue
        return -1
    return cursor


def _utf8_prefix(text, max_bytes):
    total = 0
    count = 0
    for ch in text:
        code = ord(ch)
        if code <= 0x7F:
            width = 1
        elif code <= 0x7FF:
            width = 2
        elif code <= 0xFFFF:
            width = 3
        else:
            width = 4
        if total + width > max_bytes:
            break
        total += width
        count += 1
    return text[:count]


def _scan_tail(text, start, allowed):
    ascii_count = 0
    insertions = 0
    index = start
    while index < len(text):
        ch = text[index]
        if _non_ascii(ch):
            insertions += 1
            index += 1
            continue
        if allowed(ord(ch)):
            ascii_count += 1
            index += 1
            continue
        break
    return {"ascii": ascii_count, "insertions": insertions, "end": index}


def _tail_hit(scanned, minimum):
    if scanned["ascii"] >= minimum:
        return True
    return bool(
        detector_spec["credential_tails"]["mixed_script_matches_when_ascii_tail_and_insertion"]
        and scanned["insertions"] > 0
        and scanned["ascii"] > 0
    )


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
    text = _contract_form(name, "NFC")
    if text is None:
        return ""
    decoded = _percent_decode_once(text)
    if decoded["changed"] and not decoded["prohibited"] and decoded["text"]:
        text = _contract_form(decoded["text"], "NFC")
        if text is None:
            return ""
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
    oversized = utf8_bytes(name) > _FIELD_NAME_MAX_BYTES
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
        and _contract_form(name, "NFC") == name
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
    return _in_class(ch, _ASCII_DIGIT)


def _hex(ch):
    return _in_class(ch, _ASCII_HEX)


def _starts(text, prefix, index):
    folded_prefix = ascii_fold(prefix)
    if index + len(folded_prefix) > len(text):
        return False
    for i, ch in enumerate(folded_prefix):
        if ascii_fold(text[index + i]) != ch:
            return False
    return True


def _has_bearer(text):
    index = 0
    while index < len(text):
        end = _match_prefix_at(text, "Bearer", index, False)
        if end < 0:
            index += 1
            continue
        cursor = end
        if cursor >= len(text) or text[cursor] not in " \t":
            index += 1
            continue
        while cursor < len(text) and text[cursor] in " \t":
            cursor += 1
        scanned = _scan_tail(text, cursor, lambda code: code in _ASCII_ALNUM or code in _BEARER_EXTRA)
        if _tail_hit(scanned, detector_spec["tails"]["bearer"]["minimum"]):
            return True
        index += 1
    return False


def _has_basic(text):
    index = 0
    while index < len(text):
        end = _match_prefix_at(text, "Basic", index, False)
        if end < 0:
            index += 1
            continue
        cursor = end
        if cursor >= len(text) or text[cursor] not in " \t":
            index += 1
            continue
        while cursor < len(text) and text[cursor] in " \t":
            cursor += 1
        scanned = _scan_tail(text, cursor, lambda code: code in _ASCII_ALNUM or code in _BASIC_EXTRA)
        if _tail_hit(scanned, detector_spec["tails"]["basic"]["minimum"]):
            return True
        index += 1
    return False


def _has_cookie(text):
    folded = ascii_fold(text)
    return "set-cookie" in folded or "cookie:" in folded or "cookie=" in folded


def _has_openai(text):
    for index in range(len(text)):
        for prefix in policy["openai_prefixes"]:
            end = _match_prefix_at(text, prefix, index, False)
            if end < 0:
                continue
            scanned = _scan_tail(text, end, lambda code: code in _ASCII_ALNUM)
            if _tail_hit(scanned, policy["openai_tail_min"]):
                return True
    return False


def _has_marker(text, marker, case_sensitive):
    for index in range(len(text)):
        if _match_prefix_at(text, marker, index, case_sensitive) >= 0:
            return True
    return False


def _has_cloud(text):
    for index in range(len(text)):
        for head in detector_spec["akia_prefixes"]:
            end = _match_prefix_at(text, head, index, False)
            if end < 0:
                continue
            scanned = _scan_tail(text, end, lambda code: code in _ASCII_ALNUM)
            if _tail_hit(scanned, policy["cloud_akia_tail"]):
                return True
    for marker in detector_spec["presence_markers_ascii_case_insensitive"]:
        if _has_marker(text, marker, False):
            return True
    return False


def _has_pem(text):
    folded = ascii_fold_upper(text)
    return any(ascii_fold_upper(marker) in folded for marker in policy["pem_markers"])


def _has_jwt(text):
    index = 0
    while index < len(text):
        end = _match_prefix_at(text, "eyJ", index, False)
        if end < 0:
            index += 1
            continue
        first = _scan_tail(text, end, lambda code: code in _ASCII_ALNUM or code in _JWT_EXTRA)
        if first["ascii"] < detector_spec["tails"]["jwt_first_minimum"] or text[first["end"]:first["end"] + 1] != ".":
            index += 1
            continue
        second = _scan_tail(text, first["end"] + 1, lambda code: code in _ASCII_ALNUM or code in _JWT_EXTRA)
        if _tail_hit(second, detector_spec["tails"]["jwt_second_minimum"]):
            return True
        index += 1
    return False


def _has_db(text):
    folded = ascii_fold(text)
    return any(ascii_fold(scheme) + "://" in folded for scheme in policy["db_schemes"])


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
        name = ascii_fold(part.split("=", 1)[0])
        if name in policy["sensitive_query_names"]:
            return True
    return False


def _email_class(ch):
    code = ord(ch)
    if code in _ASCII_ALNUM:
        return "ALNUM"
    if code < 128:
        return "OTHER"
    category = unicode_profile.category_of(code)
    if category == "UNKNOWN_TO_PROFILE":
        return "UNKNOWN"
    if category in ("LETTER", "NUMBER"):
        return "ALNUM"
    return "OTHER"


def _has_email(text):
    if not isinstance(text, str) or text == "":
        return False
    nfc = _contract_form(text, "NFC")
    if nfc is None:
        return True
    chars = list(nfc)
    for i, ch in enumerate(chars):
        if ch != "@":
            continue
        left = i - 1
        unknown = False
        while left >= 0:
            kind = _email_class(chars[left])
            if kind == "ALNUM" or chars[left] in "._%+-":
                left -= 1
                continue
            if kind == "UNKNOWN":
                unknown = True
                left -= 1
                continue
            break
        if i - left - 1 < 1 and not unknown:
            continue
        right = i + 1
        dot = -1
        while right < len(chars):
            kind = _email_class(chars[right])
            if kind == "ALNUM" or chars[right] in ".-":
                if chars[right] == ".":
                    dot = right
                right += 1
                continue
            if kind == "UNKNOWN":
                unknown = True
                right += 1
                continue
            break
        if unknown and (dot != -1 or i - left - 1 >= 1):
            return True
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
            if ord(text[j]) in _PAN_SEPARATORS and not separated and digits > 0 and j + 1 < len(text) and _digit(text[j + 1]):
                separated = True
                j += 1
                continue
            break
        if detector_spec["pan"]["min_digits"] <= digits <= detector_spec["pan"]["max_digits"] and (j >= len(text) or not _digit(text[j])):
            before = text[i - 1] if i > 0 else ""
            after = text[j] if j < len(text) else ""
            if not (_in_class(before, _ASCII_ALPHA) or _in_class(after, _ASCII_ALPHA)):
                return True
        i = max(j, i + 1)
    return False


def _has_mrn(text):
    prefix = detector_spec["prefixes_intentionally_case_sensitive"][0]
    index = 0
    while index < len(text):
        end = _match_prefix_at(text, prefix, index, True)
        if end < 0:
            index += 1
            continue
        scanned = _scan_tail(text, end, lambda code: code in _ASCII_ALNUM)
        if _tail_hit(scanned, detector_spec["tails"]["mrn_minimum"]):
            return True
        index += 1
    return False


def has_username_path(text):
    return any(marker in text for marker in policy["username_path_markers"])


def _scan_direct_raw(text):
    if not text:
        return False
    return (
        _has_pem(text) or _has_bearer(text) or _has_basic(text) or _has_cookie(text)
        or _has_openai(text) or _has_cloud(text) or _has_jwt(text) or _has_db(text)
        or _has_userinfo(text) or has_sensitive_query(text) or _has_email(text)
        or _has_ssn(text) or _has_phone(text) or _has_card(text) or _has_mrn(text)
    )


def scan_direct(text):
    if not text:
        return False
    if _scan_direct_raw(text):
        return True
    view = _strip_format(text)
    return view != text and _scan_direct_raw(view)


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
    nfkc = _contract_form(text, "NFKC")
    if nfkc is None:
        return None
    return "".join(_CONFUSABLE.get(ch, ch) for ch in nfkc)


def _b64_char(ch, allow_slash):
    code = _unit_code(ch)
    if code < 0 or code > detector_spec["non_ascii"]["min_exclusive"]:
        return False
    if code in _ASCII_ALNUM or code in _BASE64_EXTRA:
        return True
    return allow_slash and code == detector_spec["base64_slash"]


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


def _scan_all(text):
    if scan_direct(text):
        return True
    decoded = _percent_decode_once(text)
    if decoded["prohibited"]:
        return True
    if decoded["changed"] and decoded["text"] and scan_direct(decoded["text"]):
        return True
    if _scan_base64(text):
        return True
    folded = _fold(text)
    if folded is None:
        return True
    if folded != text and scan_direct(folded):
        return True
    if decoded["changed"] and decoded["text"]:
        folded_decoded = _fold(decoded["text"])
        if folded_decoded is None:
            return True
        if folded_decoded != decoded["text"] and scan_direct(folded_decoded):
            return True
    return False


def contains_prohibited(value):
    if not isinstance(value, str) or value == "":
        return False
    if not unicode_profile.profile_ready():
        return True
    size = utf8_bytes(value)
    text = _utf8_prefix(value, detector_spec["max_scan_bytes"]) if size > detector_spec["max_scan_bytes"] else value
    return _scan_all(text)


def _boundary_candidate(prefix):
    view = _strip_format(prefix)
    if not view:
        return False
    index = len(view) - 1
    digits = 0
    while index >= 0 and _digit(view[index]):
        digits += 1
        index -= 1
    if 0 < digits < detector_spec["pan"]["min_digits"]:
        before = view[index] if index >= 0 else ""
        if not _in_class(before, _ASCII_ALPHA):
            return True
    window_start = max(0, len(view) - 80)
    heads = list(detector_spec["akia_prefixes"]) + list(policy["openai_prefixes"])
    for start in range(window_start, len(view)):
        for head in heads:
            end = _match_prefix_at(view, head, start, False)
            if end < 0:
                continue
            if end >= len(view):
                return True
            scanned = _scan_tail(view, end, lambda code: code in _ASCII_ALNUM)
            minimum = policy["cloud_akia_tail"] if head in detector_spec["akia_prefixes"] else policy["openai_tail_min"]
            if scanned["end"] == len(view) and scanned["ascii"] < minimum:
                return True
    at = view.rfind("@")
    if window_start <= at < len(view) - 1:
        domain = True
        for cursor in range(at + 1, len(view)):
            kind = _email_class(view[cursor])
            if not (kind in ("ALNUM", "UNKNOWN") or view[cursor] in ".-"):
                domain = False
                break
        if domain:
            dot = view.rfind(".")
            if dot < at or len(view) - dot - 1 < 2:
                return True
    return False


def scan_bounded_prefix(text):
    if not isinstance(text, str) or text == "":
        return {"matched": False, "boundary": False}
    if not unicode_profile.profile_ready():
        return {"matched": True, "boundary": False}
    prefix = _utf8_prefix(text, detector_spec["max_scan_bytes"])
    matched = contains_prohibited(prefix)
    cut = utf8_bytes(text) > utf8_bytes(prefix)
    return {"matched": matched, "boundary": cut and not matched and _boundary_candidate(prefix)}


def sensitive_path(text):
    if not isinstance(text, str) or text == "":
        return False
    if not unicode_profile.profile_ready():
        return True
    nfc = _contract_form(text, "NFC")
    if nfc is None:
        return True
    if contains_prohibited(text) or contains_prohibited(nfc) or has_username_path(text) or has_username_path(nfc):
        return True
    decoded = _percent_decode_once(nfc)
    if decoded["prohibited"]:
        return True
    if not decoded["changed"]:
        return False
    form = _contract_form(decoded["text"], "NFC")
    if form is None:
        return True
    return contains_prohibited(form) or has_username_path(form)


def profile_ready():
    return unicode_profile.profile_ready()


def profile_id():
    return unicode_profile.profile_id()


def profile_version():
    return unicode_profile.profile_version()


def set_profile_unavailable_for_test(flag):
    unicode_profile.set_profile_unavailable_for_test(flag)


_NAMES.update(_comparison_form(name) for name in policy["prohibited_field_names"])
_PAYLOAD.update(_comparison_form(name) for name in policy["payload_drop_record_names"])
_BAGGAGE.update(_comparison_form(name) for name in policy["baggage_names"])
