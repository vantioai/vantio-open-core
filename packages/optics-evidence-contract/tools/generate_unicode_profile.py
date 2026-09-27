"""Build the pinned PKG-01 Unicode profile from committed UCD sources.

No network. Output is canonical JSON (sorted keys, compact separators, trailing
newline). Re-running this script reproduces the contract files byte for byte.
"""

import hashlib
import json
from pathlib import Path

GENERATOR = "pkg01-unicode-gen-1"
PROFILE_ID = "PKG01-UCD-16.0.0"
PROFILE_VERSION = "16.0.0"
SOURCE_VERSION = "16.0.0"

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contract" / "unicode-source"
CONTRACT = ROOT / "contract"

SBASE = 0xAC00
LBASE = 0x1100
VBASE = 0x1161
TBASE = 0x11A7
LCOUNT = 19
VCOUNT = 21
TCOUNT = 28
NCOUNT = VCOUNT * TCOUNT
SCOUNT = LCOUNT * NCOUNT
MAX_DEPTH = 32

HANGUL = {
    "sbase": SBASE,
    "lbase": LBASE,
    "vbase": VBASE,
    "tbase": TBASE,
    "lcount": LCOUNT,
    "vcount": VCOUNT,
    "tcount": TCOUNT,
    "ncount": NCOUNT,
    "scount": SCOUNT,
}


def sha256_file(path):
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_unicode_data(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(";")
        rows.append(parts)
    assigned = []
    index = 0
    while index < len(rows):
        parts = rows[index]
        start = int(parts[0], 16)
        name = parts[1]
        if name.endswith(", First>"):
            end_parts = rows[index + 1]
            end = int(end_parts[0], 16)
            if not end_parts[1].endswith(", Last>"):
                raise SystemExit("unpaired UnicodeData range at " + parts[0])
            assigned.append((start, end, parts))
            index += 2
            continue
        assigned.append((start, start, parts))
        index += 1
    return assigned


def parse_exclusions(path):
    codes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        body = line.split("#", 1)[0].strip()
        if not body:
            continue
        codes.append(int(body, 16))
    return sorted(set(codes))


def decomposition_of(field):
    if not field:
        return None
    tokens = field.split()
    if tokens[0].startswith("<"):
        kind = "compatibility"
        tokens = tokens[1:]
    else:
        kind = "canonical"
    return kind, [int(token, 16) for token in tokens]


def hangul_decompose(code):
    index = code - SBASE
    if index < 0 or index >= SCOUNT:
        return None
    l_index = index // NCOUNT
    v_index = (index % NCOUNT) // TCOUNT
    t_index = index % TCOUNT
    lead = LBASE + l_index
    vowel = VBASE + v_index
    if t_index == 0:
        return [lead, vowel]
    return [lead, vowel, TBASE + t_index]


def build_tables(assigned, exclusions):
    canonical = {}
    compatibility = {}
    combining = {}
    letters = []
    numbers = []
    others = []
    formats = []

    def add_range(bucket, start, end):
        if bucket and bucket[-1][1] + 1 == start:
            bucket[-1][1] = end
        else:
            bucket.append([start, end])

    for start, end, parts in assigned:
        category = parts[2]
        cc = int(parts[3])
        decomp = decomposition_of(parts[5])
        coarse = "OTHER"
        if category.startswith("L"):
            coarse = "LETTER"
        elif category.startswith("N"):
            coarse = "NUMBER"
        for code in range(start, end + 1):
            if cc:
                combining[code] = cc
            if decomp and start == end:
                kind, seq = decomp
                if kind == "canonical":
                    canonical[code] = seq
                else:
                    compatibility[code] = seq
        bucket = letters if coarse == "LETTER" else numbers if coarse == "NUMBER" else others
        add_range(bucket, start, end)
        if category == "Cf":
            add_range(formats, start, end)

    exclusion = set(exclusions)
    for code, seq in canonical.items():
        if len(seq) != 2 or combining.get(seq[0], 0) != 0:
            exclusion.add(code)
    return {
        "canonical": canonical,
        "compatibility": compatibility,
        "combining": combining,
        "exclusion": exclusion,
        "letters": letters,
        "numbers": numbers,
        "others": others,
        "formats": formats,
    }


def ccc(tables, code):
    return tables["combining"].get(code, 0)


def decompose_fully(tables, codes, compatibility):
    out = []

    def rec(code, depth):
        if depth > MAX_DEPTH:
            raise SystemExit("decomposition depth exceeded")
        hangul = hangul_decompose(code)
        if hangul:
            for part in hangul:
                rec(part, depth + 1)
            return
        seq = None
        if compatibility and code in tables["compatibility"]:
            seq = tables["compatibility"][code]
        elif code in tables["canonical"]:
            seq = tables["canonical"][code]
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
            left = ccc(tables, out[index])
            right = ccc(tables, out[index + 1])
            if left > right > 0:
                out[index], out[index + 1] = out[index + 1], out[index]
                changed = True
    return out


def compose_pair(tables, compose_map, left, right):
    l_index = left - LBASE
    if 0 <= l_index < LCOUNT:
        v_index = right - VBASE
        if 0 <= v_index < VCOUNT:
            return SBASE + (l_index * VCOUNT + v_index) * TCOUNT
    s_index = left - SBASE
    if 0 <= s_index < SCOUNT and s_index % TCOUNT == 0:
        t_index = right - TBASE
        if 0 < t_index < TCOUNT:
            return left + t_index
    return compose_map.get((left, right))


def compose(tables, compose_map, codes):
    if not codes:
        return []
    result = [codes[0]]
    starter = 0 if ccc(tables, codes[0]) == 0 else None
    previous = 0
    for code in codes[1:]:
        cc = ccc(tables, code)
        if starter is not None and (previous < cc or previous == 0):
            composed = compose_pair(tables, compose_map, result[starter], code)
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


def normalize(tables, compose_map, codes, form):
    compatibility = form == "NFKC"
    decomposed = decompose_fully(tables, codes, compatibility)
    return compose(tables, compose_map, decomposed)


def compose_map_of(tables):
    mapping = {}
    for code, seq in tables["canonical"].items():
        if code in tables["exclusion"]:
            continue
        if len(seq) == 2 and ccc(tables, seq[0]) == 0:
            mapping[(seq[0], seq[1])] = code
    return mapping


def pairs(mapping):
    return [[code, seq] for code, seq in sorted(mapping.items())]


def dump(path, payload):
    text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return text.encode("utf-8")


def assert_known(tables, compose_map):
    checks = [
        ("NFKC", [0x00A0], [0x0020]),
        ("NFKC", [0xFB01], [0x0066, 0x0069]),
        ("NFKC", [0x1CCF0], [0x0030]),
        ("NFKC", [0x1CCF4], [0x0034]),
        ("NFKC", [0x1CCF9], [0x0039]),
        ("NFKC", [0xFF21], [0x0041]),
        ("NFC", [0x0065, 0x0301], [0x00E9]),
        ("NFC", [0x00E9], [0x00E9]),
        ("NFKC", [0x00E9], [0x00E9]),
        ("NFC", [0x212B], [0x00C5]),
        ("NFC", [0xAC00], [0xAC00]),
        ("NFC", [0x1100, 0x1161], [0xAC00]),
        ("NFKC", [0x200B], [0x200B]),
    ]
    for form, source, expected in checks:
        got = normalize(tables, compose_map, source, form)
        if got != expected:
            raise SystemExit("vector mismatch " + form + " " + hex(source[0]) + " got " + str(got))


def category_of(tables, code):
    def inside(ranges):
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

    if inside(tables["letters"]):
        return "LETTER"
    if inside(tables["numbers"]):
        return "NUMBER"
    if inside(tables["others"]):
        return "OTHER"
    return "UNKNOWN_TO_PROFILE"


def main():
    assigned = parse_unicode_data(SOURCE / "UnicodeData.txt")
    exclusions = parse_exclusions(SOURCE / "CompositionExclusions.txt")
    tables = build_tables(assigned, exclusions)
    compose_map = compose_map_of(tables)
    assert_known(tables, compose_map)
    if category_of(tables, 0x0870) != "LETTER":
        raise SystemExit("U+0870 category")
    if category_of(tables, 0x1C89) != "LETTER":
        raise SystemExit("U+1C89 category")
    if category_of(tables, 0x1CCF4) != "NUMBER":
        raise SystemExit("U+1CCF4 category")
    if category_of(tables, 0x0378) != "UNKNOWN_TO_PROFILE":
        raise SystemExit("U+0378 category")
    if category_of(tables, 0x200B) != "OTHER":
        raise SystemExit("U+200B category")

    nfkc_payload = {
        "canonical": pairs(tables["canonical"]),
        "combining_class": [[code, value] for code, value in sorted(tables["combining"].items())],
        "compatibility": pairs(tables["compatibility"]),
        "composition_exclusion": sorted(tables["exclusion"]),
        "generator": GENERATOR,
        "hangul": HANGUL,
        "max_decomposition_depth": MAX_DEPTH,
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
    }
    category_payload = {
        "format_controls": tables["formats"],
        "generator": GENERATOR,
        "letter": tables["letters"],
        "number": tables["numbers"],
        "other": tables["others"],
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
        "unknown_label": "UNKNOWN_TO_PROFILE",
    }
    vectors = [
        {"category": "NUMBER", "form": "NFKC", "input": [0x1CCF0], "output": [0x0030]},
        {"category": "NUMBER", "form": "NFKC", "input": [0x1CCF4], "output": [0x0034]},
        {"category": "NUMBER", "form": "NFKC", "input": [0x1CCF9], "output": [0x0039]},
        {"category": "OTHER", "form": "NFKC", "input": [0x00A0], "output": [0x0020]},
        {"category": "LETTER", "form": "NFKC", "input": [0xFB01], "output": [0x0066, 0x0069]},
        {"category": "LETTER", "form": "NFKC", "input": [0xFF21], "output": [0x0041]},
        {"category": "LETTER", "form": "NFC", "input": [0x0065, 0x0301], "output": [0x00E9]},
        {"category": "LETTER", "form": "NFC", "input": [0x00E9], "output": [0x00E9]},
        {"category": "LETTER", "form": "NFC", "input": [0x212B], "output": [0x00C5]},
        {"category": "LETTER", "form": "NFC", "input": [0x1100, 0x1161], "output": [0xAC00]},
        {"category": "OTHER", "form": "NFKC", "input": [0x200B], "output": [0x200B]},
        {"category": "LETTER", "form": "NFKC", "input": [0x0870], "output": [0x0870]},
        {"category": "LETTER", "form": "NFKC", "input": [0x1C89], "output": [0x1C89]},
        {"category": "UNKNOWN_TO_PROFILE", "form": "NFKC", "input": [0x0378], "output": [0x0378]},
        {"category": "OTHER", "form": "NFKC", "input": [0xFEFF], "output": [0xFEFF]},
    ]
    for vector in vectors:
        got = normalize(tables, compose_map, vector["input"], vector["form"])
        if got != vector["output"]:
            raise SystemExit("emitted vector drifted " + str(vector["input"]))
        if category_of(tables, vector["input"][0]) != vector["category"]:
            raise SystemExit("emitted category drifted " + str(vector["input"]))

    profile_payload = {
        "bounds": {
            "max_code_points": 8192,
            "max_decomposition_depth": MAX_DEPTH,
            "max_expansion_ratio": 16,
            "max_input_bytes": 8192,
            "max_output_bytes": 65536,
        },
        "category_membership": ["LETTER", "NUMBER", "OTHER", "UNKNOWN_TO_PROFILE"],
        "category_scope": "Unicode 16.0.0 assigned scalar values. L* is LETTER. N* is NUMBER. Every other assigned general category is OTHER. Assigned Cf code points are format controls and also OTHER. Scalars absent from the assigned ranges are UNKNOWN_TO_PROFILE. No host category API is consulted.",
        "compatibility_policy": "Compatibility decompositions are detection-only. The original code unit sequence is never replaced in stored fields. A governed detector hit on the normalized or format-stripped view omits the original value.",
        "email_unknown_policy": "UNKNOWN_TO_PROFILE inside an email-shaped local or domain span fails closed. The value is omitted. The original span is not stored.",
        "format_control_policy": "Pinned Cf code points are removed only in the detector comparison view. Removal is not persisted. If the view is detector-positive, the field is rejected and the original is absent. Ordinary text with a format control and no governed secret is unchanged.",
        "generator": GENERATOR,
        "host_icu": False,
        "host_python_unicodedata": False,
        "id": PROFILE_ID,
        "normalization": "NFKC",
        "normalization_scope": "Contract NFKC and NFC from the pinned decomposition tables and Hangul syllable arithmetic in UAX #15. NFC is comparison-only for field names, session ids, and email spans. NFKC is detection-only. Locale is not an input.",
        "prefix_disruption": {
            "format_controls_skipped_in_detector_view": True,
            "governed_prefixes_only": True,
            "max_non_ascii_insertions_per_prefix": 1,
            "no_fuzzy_ascii": True,
            "no_transliteration": True,
        },
        "profile_version": PROFILE_VERSION,
        "scan_boundary": {
            "completeness_token": "SCAN_INCOMPLETE",
            "does_not_claim_detector_match": True,
            "privacy_event": None,
            "reason_when_over_cap": "MAX_SIZE_EXCEEDED",
            "window_codepoints": 80,
        },
        "size_only": {
            "privacy_event": None,
            "reason_code": "MAX_SIZE_EXCEEDED",
            "scan_state": "SIZE_ONLY",
        },
        "source_unicode_version": SOURCE_VERSION,
        "unknown_profile_policy": "Missing or unverified profile data is a validator configuration failure. Records are not accepted and input strings are not copied into the result.",
        "verification_vectors": vectors,
        "version": PROFILE_VERSION,
    }

    nfkc_bytes = dump(CONTRACT / "unicode-nfkc-map.json", nfkc_payload)
    category_bytes = dump(CONTRACT / "unicode-category-ranges.json", category_payload)
    profile_bytes = dump(CONTRACT / "unicode-profile.json", profile_payload)
    metadata = {
        "category_scope": profile_payload["category_scope"],
        "compatibility_policy": profile_payload["compatibility_policy"],
        "generation_method": "Parse committed UnicodeData.txt and CompositionExclusions.txt. Expand First/Last ranges. Derive canonical and compatibility decompositions, non-zero combining classes, and full composition exclusions (script exclusions plus canonical singletons and non-starters). Hangul composition and decomposition are arithmetic. No host Unicode library and no network.",
        "generator": GENERATOR,
        "max_file_bytes": 8000000,
        "normalization_scope": profile_payload["normalization_scope"],
        "outputs": [
            {"name": "unicode-category-ranges.json", "sha256": hashlib.sha256(category_bytes).hexdigest()},
            {"name": "unicode-nfkc-map.json", "sha256": hashlib.sha256(nfkc_bytes).hexdigest()},
            {"name": "unicode-profile.json", "sha256": hashlib.sha256(profile_bytes).hexdigest()},
        ],
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
        "sources": [
            {"name": "CompositionExclusions.txt", "sha256": sha256_file(SOURCE / "CompositionExclusions.txt"), "unicode_version": SOURCE_VERSION},
            {"name": "UnicodeData.txt", "sha256": sha256_file(SOURCE / "UnicodeData.txt"), "unicode_version": SOURCE_VERSION},
        ],
        "update_procedure": "Replace the committed UCD sources with one Unicode version, run tools/generate_unicode_profile.py offline, and review the verification vectors. Do not regenerate during validation or tests. Do not mix host ICU or CPython unicodedata into the outputs.",
        "verification_vectors": len(vectors),
    }
    dump(CONTRACT / "unicode-profile-metadata.json", metadata)
    print("letters", len(tables["letters"]), "numbers", len(tables["numbers"]), "other", len(tables["others"]))
    print("canonical", len(tables["canonical"]), "compatibility", len(tables["compatibility"]), "ccc", len(tables["combining"]))
    print("formats", len(tables["formats"]), "exclusions", len(tables["exclusion"]))
    print("nfkc", len(nfkc_bytes), "categories", len(category_bytes), "profile", len(profile_bytes))


if __name__ == "__main__":
    main()
