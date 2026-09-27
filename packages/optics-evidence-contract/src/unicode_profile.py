"""Pinned Unicode profile. Privacy truth comes from committed contract tables."""

import hashlib
import json
from pathlib import Path

_CONTRACT = Path(__file__).resolve().parent.parent / "contract"
_MAX_FILE_BYTES = 8000000
_SCALAR = 0x110000

_ready = False
_load_error = "UNLOADED"
_forced_off = False
_profile_id = None
_profile_version = None
_bounds = None
_canonical = {}
_compatibility = {}
_combining = {}
_exclusion = set()
_compose = {}
_letters = []
_numbers = []
_others = []
_formats = []
_hangul = None
_max_depth = 32


def _read_bounded(name):
    path = _CONTRACT / name
    size = path.stat().st_size
    if size <= 0 or size > _MAX_FILE_BYTES:
        raise OSError("UNICODE_PROFILE_SIZE")
    return path.read_bytes()


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _in_ranges(ranges, code):
    lo = 0
    hi = len(ranges) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end = ranges[mid]
        if code < start:
            hi = mid - 1
        elif code > end:
            lo = mid + 1
        else:
            return True
    return False


def _hangul_decompose(code):
    index = code - _hangul["sbase"]
    if index < 0 or index >= _hangul["scount"]:
        return None
    l_index = index // _hangul["ncount"]
    v_index = (index % _hangul["ncount"]) // _hangul["tcount"]
    t_index = index % _hangul["tcount"]
    lead = _hangul["lbase"] + l_index
    vowel = _hangul["vbase"] + v_index
    if t_index == 0:
        return [lead, vowel]
    return [lead, vowel, _hangul["tbase"] + t_index]


def _ccc(code):
    return _combining.get(code, 0)


def _mapping(code, use_compatibility):
    hangul_parts = _hangul_decompose(code)
    if hangul_parts:
        return hangul_parts
    if use_compatibility and code in _compatibility:
        return _compatibility[code]
    if code in _canonical:
        return _canonical[code]
    return None


def _decompose_fully(codes, use_compatibility):
    out = []

    def rec(code, depth):
        if depth > _max_depth:
            raise RuntimeError("UNICODE_PROFILE_DEPTH")
        seq = _mapping(code, use_compatibility)
        if seq:
            for part in seq:
                rec(part, depth + 1)
            return
        out.append(code)

    for code in codes:
        rec(code, 0)
    changed = True
    while changed:
        changed = False
        for index in range(len(out) - 1):
            left = _ccc(out[index])
            right = _ccc(out[index + 1])
            if left > right > 0:
                out[index], out[index + 1] = out[index + 1], out[index]
                changed = True
    return out


def _compose_pair(left, right):
    l_index = left - _hangul["lbase"]
    if 0 <= l_index < _hangul["lcount"]:
        v_index = right - _hangul["vbase"]
        if 0 <= v_index < _hangul["vcount"]:
            return _hangul["sbase"] + (l_index * _hangul["vcount"] + v_index) * _hangul["tcount"]
    s_index = left - _hangul["sbase"]
    if 0 <= s_index < _hangul["scount"] and s_index % _hangul["tcount"] == 0:
        t_index = right - _hangul["tbase"]
        if 0 < t_index < _hangul["tcount"]:
            return left + t_index
    return _compose.get(left * _SCALAR + right)


def _compose_codes(codes):
    if not codes:
        return []
    result = [codes[0]]
    starter = 0 if _ccc(codes[0]) == 0 else None
    previous = 0
    for code in codes[1:]:
        cc = _ccc(code)
        if starter is not None and (previous < cc or previous == 0):
            composed = _compose_pair(result[starter], code)
            if composed is not None:
                result[starter] = composed
                continue
        result.append(code)
        if cc == 0:
            starter = len(result) - 1
            previous = 0
        else:
            previous = cc
    return result


def _to_codes(text):
    codes = []
    index = 0
    length = len(text)
    while index < length:
        code = ord(text[index])
        if 0xD800 <= code <= 0xDBFF:
            if index + 1 >= length:
                return None
            nxt = ord(text[index + 1])
            if not (0xDC00 <= nxt <= 0xDFFF):
                return None
            codes.append(((code - 0xD800) << 10) + (nxt - 0xDC00) + 0x10000)
            index += 2
            continue
        if 0xDC00 <= code <= 0xDFFF:
            return None
        codes.append(code)
        index += 1
    return codes


def _from_codes(codes):
    return "".join(chr(code) for code in codes)


def _utf8_length(codes):
    total = 0
    for code in codes:
        if code <= 0x7F:
            total += 1
        elif code <= 0x7FF:
            total += 2
        elif code <= 0xFFFF:
            total += 3
        else:
            total += 4
    return total


def _category_lookup(code):
    if _in_ranges(_letters, code):
        return "LETTER"
    if _in_ranges(_numbers, code):
        return "NUMBER"
    if _in_ranges(_others, code):
        return "OTHER"
    return "UNKNOWN_TO_PROFILE"


def _check_vectors(vectors):
    for vector in vectors:
        normalized = _compose_codes(_decompose_fully(vector["input"], vector["form"] == "NFKC"))
        if normalized != vector["output"]:
            return False
        if _category_lookup(vector["input"][0]) != vector["category"]:
            return False
    return True


def _load_pair_map(pairs):
    return {pair[0]: pair[1] for pair in pairs}


def _build_compose():
    mapping = {}
    for code, seq in _canonical.items():
        if code in _exclusion:
            continue
        if len(seq) == 2 and _ccc(seq[0]) == 0:
            mapping[seq[0] * _SCALAR + seq[1]] = code
    return mapping


def _load_profile():
    global _ready, _load_error, _profile_id, _profile_version, _bounds, _canonical
    global _compatibility, _combining, _exclusion, _compose, _letters, _numbers, _others
    global _formats, _hangul, _max_depth
    metadata = json.loads(_read_bounded("unicode-profile-metadata.json").decode("utf-8"))
    outputs = {item["name"]: item["sha256"] for item in metadata["outputs"]}
    parsed = {}
    for name in ("unicode-profile.json", "unicode-nfkc-map.json", "unicode-category-ranges.json"):
        data = _read_bounded(name)
        if _sha256(data) != outputs[name]:
            raise OSError("UNICODE_PROFILE_HASH")
        parsed[name] = json.loads(data.decode("utf-8"))
    for source in metadata["sources"]:
        data = _read_bounded("unicode-source/" + source["name"])
        if _sha256(data) != source["sha256"]:
            raise OSError("UNICODE_PROFILE_SOURCE_HASH")
    profile = parsed["unicode-profile.json"]
    map_file = parsed["unicode-nfkc-map.json"]
    categories = parsed["unicode-category-ranges.json"]
    if profile["id"] != metadata["profile_id"] or profile["profile_version"] != metadata["profile_version"]:
        raise OSError("UNICODE_PROFILE_ID")
    if map_file["profile_id"] != profile["id"] or categories["profile_id"] != profile["id"]:
        raise OSError("UNICODE_PROFILE_ID")
    _profile_id = profile["id"]
    _profile_version = profile["profile_version"]
    _bounds = profile["bounds"]
    _hangul = map_file["hangul"]
    _max_depth = map_file["max_decomposition_depth"]
    _canonical = _load_pair_map(map_file["canonical"])
    _compatibility = _load_pair_map(map_file["compatibility"])
    _combining = {pair[0]: pair[1] for pair in map_file["combining_class"]}
    _exclusion = set(map_file["composition_exclusion"])
    _letters = categories["letter"]
    _numbers = categories["number"]
    _others = categories["other"]
    _formats = categories["format_controls"]
    _compose = _build_compose()
    if not _check_vectors(profile["verification_vectors"]):
        raise OSError("UNICODE_PROFILE_VECTOR")
    _ready = True
    _load_error = None


try:
    _load_profile()
except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
    _ready = False
    _load_error = "UNICODE_PROFILE_UNAVAILABLE"


def profile_ready():
    return _ready and not _forced_off


def set_profile_unavailable_for_test(flag):
    global _forced_off
    _forced_off = flag is True


def profile_id():
    return _profile_id


def profile_version():
    return _profile_version


def load_error():
    return _load_error


def category_of(code):
    if not profile_ready():
        return "UNKNOWN_TO_PROFILE"
    return _category_lookup(code)


def is_format(code):
    if not profile_ready():
        return False
    return _in_ranges(_formats, code)


def normalize_codes(codes, form):
    if form not in ("NFC", "NFKC"):
        return {"ok": False, "reason": "FORM"}
    if not profile_ready():
        return {"ok": False, "reason": "PROFILE"}
    if len(codes) > _bounds["max_code_points"]:
        return {"ok": False, "reason": "BOUND"}
    input_bytes = _utf8_length(codes)
    if input_bytes > _bounds["max_input_bytes"]:
        return {"ok": False, "reason": "BOUND"}
    if all(code <= 127 for code in codes):
        return {"ok": True, "codes": list(codes)}
    try:
        normalized = _compose_codes(_decompose_fully(codes, form == "NFKC"))
    except RuntimeError:
        return {"ok": False, "reason": "DEPTH"}
    output_bytes = _utf8_length(normalized)
    ratio = output_bytes / (input_bytes or 1)
    if output_bytes > _bounds["max_output_bytes"] or ratio > _bounds["max_expansion_ratio"]:
        return {"ok": False, "reason": "EXPANSION"}
    return {"ok": True, "codes": normalized}


def normalize_text(text, form):
    if not isinstance(text, str):
        return {"ok": False, "reason": "TYPE"}
    if not profile_ready():
        return {"ok": False, "reason": "PROFILE"}
    codes = _to_codes(text)
    if codes is None:
        return {"ok": False, "reason": "MALFORMED"}
    normalized = normalize_codes(codes, form)
    if not normalized["ok"]:
        return normalized
    return {"ok": True, "text": _from_codes(normalized["codes"])}
