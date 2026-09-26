"""Hand-written evidence validator. Same contract as validate.cjs.

schema_status is unstable-pre-1.0. schema_version 0 means unassigned.
This module does not write a store and does not import the live SDK.
"""

import json
import re
import unicodedata
from pathlib import Path

import canonical
import privacy
import walk

CONTRACT_DIR = Path(__file__).resolve().parent.parent / "contract"
enums = json.loads((CONTRACT_DIR / "enums.json").read_text(encoding="utf-8"))
meta = json.loads((CONTRACT_DIR / "contract-metadata.json").read_text(encoding="utf-8"))
bounds = walk.bounds

DISPOSITION_RANK = {name: index for index, name in enumerate(enums["disposition_rank"])}
REASON_RANK = {name: index for index, name in enumerate(enums["reason_priority"])}
ISSUE_LABELS = enums["issue_location_labels"]
WRITER_ORIGINS = set(enums["evidence_origin_writer"])
SESSION_BASIS = set(enums["session_id_basis"])
TRACE_BASIS = set(enums["trace_id_basis"])
OPTICS_STATUS = set(enums["optics_status"])
METHODS = set(enums["method"])
SCHEMES = set(enums["scheme"])
FAILURES = set(enums["failure_kind"])
NETWORK_KINDS = set(enums["network_failure_kinds"])
CONFIDENCE = set(enums["provider_confidence"])
MEDIATION = set(enums["mediation"])
PLATFORMS = set(enums["platform"])
ARCHES = set(enums["arch"])
LIFECYCLE = set(enums["lifecycle"])
CLOCK = set(enums["clock_quality"])
CONFLICT = set(enums["identity_conflict"])
RUNTIMES = set(enums["runtime"])
COVERAGE = set(enums["coverage_note"])
PRODUCERS = set(meta["recognized_producers"])
HEALTH_NAMES = set(enums["product_health_name"])
OUTCOME_LABELS = set(enums["application_outcome_label"])
PROVIDER_PHRASES = set(enums["provider_response_phrase"])
NEXT_ACTION = set(enums["next_action_category"])
ORIGINAL_ORIGIN = set(enums["original_evidence_origin"])

STRUCTURAL_EXCLUSIONS = {
    "workflow",
    "plane",
    "freemode",
    "estspendusd",
    "usage",
    "tokencount",
    "prompttokens",
    "completiontokens",
    "totaltokens",
    "cost",
    "costusd",
    "residual",
    "datanote",
    "statuslabels",
}

_TIME = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.(\d{1,6}))?(Z|\+00:00|-00:00)$"
)
_VERSION = re.compile(r"^[A-Za-z0-9._+-]+$")
_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_HEX = re.compile(r"^[0-9a-fA-F]+$")
_LEGACY_TRACE = re.compile(r"^0x[0-9a-fA-F]{1,126}$")
_LEGACY_SPAN = re.compile(r"^0x[0-9a-fA-F]+$")
_TRACEPARENT = re.compile(r"^00-([0-9a-fA-F]{32})-([0-9a-fA-F]{16})-[0-9a-fA-F]{2}$")
_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*)://")
_DNS = re.compile(r"^[a-z0-9.-]+$")
_IPV6 = re.compile(r"^[0-9a-fA-F:]+$")
_MEDIA = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$")
_PORT = re.compile(r"^[0-9]{1,5}$")
_EVENT = re.compile(r"^e\.[0-9]+\.[A-Za-z0-9_-]+\.[0-9]+$")
_PROVIDER = re.compile(r"^[a-z0-9_-]{1,64}$")
_TOKEN64 = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_SEEN_STATUS = re.compile(r"^[A-Za-z0-9._+-]{1,64}$")
_SHA = re.compile(r"^[0-9a-fA-F]{64}$")


class State(object):
    def __init__(self):
        self.dispositions = set()
        self.reasons = set()
        self.completeness = set()
        self.health = {
            "events_rejected": 0,
            "redaction_failures": 0,
            "rejected_context": 0,
            "session_id_rejected": 0,
        }
        self.accepted = set()
        self.normalized = set()
        self.stripped = set()
        self.rejected = set()
        self.privacy = False
        self.session_rejected = False
        self.context_rejected = False
        self.drop_record = False
        self.provenance = "NOT_APPLICABLE"
        self.destination_class = None
        self.destination_ip_class = None
        self.trace_meaning = None
        self.optics_internal = False
        self.network_no_http = False
        self.customer_exception = False
        self.coverage_evidenced = False
        self.coverage_unevidenced = False
        self.configuration_fault = False
        self.environment_fault = False
        self.http_status = None
        self.failure_identified = False
        self.reader_origin = None
        self.interrupted = False


def _add_disposition(state, disposition):
    state.dispositions.add(disposition)


def _add_reason(state, reason):
    state.reasons.add(reason)


def _mark_privacy(state):
    if state.privacy:
        return
    state.privacy = True
    state.completeness.add("REDACTION_DROP")
    state.health["redaction_failures"] = 1
    _add_reason(state, "REDACTION_DROP")


def _mark_session(state):
    if state.session_rejected:
        return
    state.session_rejected = True
    state.completeness.add("SESSION_ID_REJECTED")
    state.health["session_id_rejected"] = 1
    _add_reason(state, "SESSION_ID_REJECTED")
    _add_disposition(state, "REJECT_FIELD")


def _mark_context(state):
    if state.context_rejected:
        return
    state.context_rejected = True
    state.completeness.add("CONTEXT_REJECTED")
    state.health["rejected_context"] = 1
    _add_reason(state, "CONTEXT_REJECTED")
    _add_disposition(state, "REJECT_FIELD")


def _drop_record(state, reason):
    if not state.drop_record:
        state.drop_record = True
        state.completeness.add("EVENT_DROPPED")
        state.health["events_rejected"] = 1
    _add_reason(state, reason)
    _add_disposition(state, "REJECT_RECORD")
    state.optics_internal = True


def _put(state, record, name, value, kind):
    record[name] = value
    if kind == "accepted":
        state.normalized.discard(name)
        state.accepted.add(name)
        _add_disposition(state, "ACCEPT")
    else:
        state.accepted.discard(name)
        state.normalized.add(name)
        _add_disposition(state, "NORMALIZE")
        _add_reason(state, "NORMALIZED")


def _reject_field(state, name):
    state.rejected.add(name)
    _add_disposition(state, "REJECT_FIELD")


def _strip_key(state, name):
    state.stripped.add(name)
    _add_disposition(state, "STRIP")
    _add_reason(state, "UNKNOWN_FIELD_OMITTED")


def _highest(rank, values, fallback):
    best = fallback
    best_rank = rank.get(fallback, -1)
    for value in values:
        nxt = rank.get(value, -1)
        if nxt > best_rank:
            best_rank = nxt
            best = value
    return best


def _sorted(values):
    return sorted(values)


def _completeness_list(state):
    out = []
    for token in enums["completeness_tokens"]:
        if token in state.completeness:
            out.append(token)
    return out if out else ["NONE"]


def _health_label(health):
    if health["redaction_failures"] > 0:
        return "INTERNAL_PRIVACY_FAILURE"
    if health["events_rejected"] > 0:
        return "EVENT_REJECTED"
    if health["session_id_rejected"] > 0:
        return "SESSION_REJECTED"
    if health["rejected_context"] > 0:
        return "CONTEXT_REJECTED"
    return "NONE"


def _issue_location(state):
    if state.optics_internal:
        return "OPTICS"
    if state.network_no_http:
        return "NETWORK"
    if state.http_status is not None and 400 <= state.http_status <= 599:
        return "PROVIDER_INTERACTION"
    if state.customer_exception and state.http_status is None:
        return "CUSTOMER_APPLICATION"
    if state.coverage_evidenced:
        return "COVERAGE"
    if state.coverage_unevidenced:
        return "UNKNOWN"
    if state.configuration_fault:
        return "CONFIGURATION"
    if state.environment_fault:
        return "ENVIRONMENT"
    if state.http_status is not None and 200 <= state.http_status < 400:
        return "NONE"
    if state.http_status is not None and (state.http_status < 200 or state.http_status > 599):
        return "UNKNOWN"
    if state.failure_identified:
        return "UNKNOWN"
    return "NONE"


def _application_status_from_http(status):
    if status is None:
        return "UNAVAILABLE"
    if 200 <= status < 400:
        return "SUCCESS"
    if 400 <= status <= 599:
        return "APPLICATION_ERROR"
    return "UNAVAILABLE"


def _is_integer(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return abs(value) <= bounds["safe_integer_max"]


def _non_negative_int(value):
    if not _is_integer(value) or value < 0:
        return None
    return value


def _version_token(value, limit):
    if not isinstance(value, str):
        return None
    if len(value) < 1 or len(value) > limit:
        return None
    if not _VERSION.match(value):
        return None
    if privacy.contains_prohibited(value):
        return {"prohibited": True}
    return value


def _id_token(value, limit):
    if not isinstance(value, str):
        return None
    if len(value) < 1 or len(value) > limit:
        return None
    if not _ID.match(value):
        return None
    if privacy.contains_prohibited(value):
        return {"prohibited": True}
    return value


def _is_leap(year):
    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0


def _canonical_time(value):
    if not isinstance(value, str):
        return None
    match = _TIME.match(value)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))
    second = int(match.group(6))
    if month < 1 or month > 12 or hour > 23 or minute > 59 or second > 59:
        return None
    days = [0, 31, 29 if _is_leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if day < 1 or day > days[month]:
        return None
    fraction = (match.group(8) or "").ljust(3, "0")[:3]
    out = (
        match.group(1) + "-" + match.group(2) + "-" + match.group(3) + "T"
        + match.group(4) + ":" + match.group(5) + ":" + match.group(6) + "." + fraction + "Z"
    )
    return {"value": out, "changed": out != value}


def _has_control(text):
    for ch in text:
        code = ord(ch)
        if code <= 0x1F or code == 0x7F or code == 0x2028 or code == 0x2029:
            return True
    return False


def _is_noncharacter(code):
    if 0xFDD0 <= code <= 0xFDEF:
        return True
    return (code & 0xFFFE) == 0xFFFE


def _utf8_bytes(text):
    return len(text.encode("utf-8"))


def _hex_normalize(value, width):
    if not isinstance(value, str):
        return None
    if width and len(value) == width and _HEX.match(value):
        if re.match(r"^0+$", value):
            return None
        lower = value.lower()
        return {"value": lower, "changed": lower != value}
    return None


def _trace_normalize(value):
    if not isinstance(value, str) or walk.is_bound(value):
        return None
    if len(value) > bounds["trace_id_max_chars"]:
        return None
    if privacy.contains_prohibited(value):
        return {"prohibited": True}
    w3c = _hex_normalize(value, 32)
    if w3c:
        return w3c
    if _LEGACY_TRACE.match(value) and len(value) <= bounds["trace_id_max_chars"]:
        lower = "0x" + value[2:].lower()
        if re.match(r"^0x0+$", lower):
            return None
        return {"value": lower, "changed": lower != value}
    return None


def _span_normalize(value):
    if not isinstance(value, str) or walk.is_bound(value):
        return None
    if len(value) > bounds["span_id_max_chars"]:
        return None
    if privacy.contains_prohibited(value):
        return {"prohibited": True}
    w3c = _hex_normalize(value, 16)
    if w3c and len(value) <= bounds["span_id_max_chars"]:
        return w3c
    if _LEGACY_SPAN.match(value) and 3 <= len(value) <= bounds["span_id_max_chars"]:
        lower = "0x" + value[2:].lower()
        if re.match(r"^0x0+$", lower):
            return None
        return {"value": lower, "changed": lower != value}
    return None


def _parse_traceparent(value):
    if not isinstance(value, str):
        return None
    match = _TRACEPARENT.match(value)
    if not match:
        return None
    trace = _trace_normalize(match.group(1))
    span = _span_normalize(match.group(2))
    if not trace or trace.get("prohibited") or not span or span.get("prohibited"):
        return None
    return {"trace": trace["value"], "span": span["value"]}


def _is_ipv4(text):
    parts = text.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not re.match(r"^[0-9]{1,3}$", part):
            return False
        if len(part) > 1 and part.startswith("0"):
            return False
        if int(part) > 255:
            return False
    return True


def _is_ipv6(text):
    if "%" in text:
        return False
    if not _IPV6.match(text):
        return False
    if text.count("::") > 1:
        return False

    def check(side):
        if side == "":
            return True
        groups = side.split(":")
        return all(1 <= len(group) <= 4 for group in groups)

    halves = text.split("::")
    if len(halves) == 1:
        return len(text.split(":")) == 8 and check(text)
    if len(halves) != 2:
        return False
    if not check(halves[0]) or not check(halves[1]):
        return False
    left = 0 if halves[0] == "" else len(halves[0].split(":"))
    right = 0 if halves[1] == "" else len(halves[1].split(":"))
    return left + right < 8


def _normalize_host(value):
    if not isinstance(value, str) or walk.is_bound(value):
        return {"ok": False, "prohibited": walk.is_bound(value)}
    if len(value) < 1 or len(value) > bounds["host_max_chars"]:
        return {"ok": False, "prohibited": len(value) > bounds["host_max_chars"]}
    if _has_control(value) or "/" in value or "?" in value or "#" in value or "@" in value:
        return {"ok": False, "prohibited": True}
    if privacy.contains_prohibited(value) or privacy.has_username_path(value) or privacy.has_db_scheme(value):
        return {"ok": False, "prohibited": True}
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        if not _is_ipv6(inner):
            return {"ok": False, "prohibited": False}
        return {"ok": True, "value": inner.lower(), "ipClass": "ipv6", "changed": True}
    if _is_ipv4(value):
        return {"ok": True, "value": value, "ipClass": "ipv4", "changed": False}
    if ":" in value:
        if not _is_ipv6(value):
            return {"ok": False, "prohibited": False}
        lower = value.lower()
        return {"ok": True, "value": lower, "ipClass": "ipv6", "changed": lower != value}
    lower = value.lower()
    if not _DNS.match(lower):
        return {"ok": False, "prohibited": False}
    if lower.startswith(".") or lower.endswith(".") or ".." in lower:
        return {"ok": False, "prohibited": False}
    labels = lower.split(".")
    if any(len(label) < 1 or len(label) > bounds["label_max_chars"] for label in labels):
        return {"ok": False, "prohibited": False}
    return {"ok": True, "value": lower, "ipClass": "dns", "changed": lower != value}


def _normalize_path(value):
    if not isinstance(value, str) or walk.is_bound(value):
        oversize = walk.is_bound(value) and value.get("__optics_bound") == walk.OVERSIZE
        return {"ok": False, "oversize": oversize, "prohibited": True}
    if len(value) > bounds["path_max_chars"]:
        return {"ok": False, "oversize": True, "prohibited": privacy.contains_prohibited(value)}
    if _has_control(value) or "\\" in value or privacy.has_username_path(value):
        return {"ok": False, "prohibited": True}
    if "://" in value:
        return {"ok": False, "prohibited": True}
    path = value
    stripped = False
    if "#" in path or "?" in path:
        path = path.split("#", 1)[0].split("?", 1)[0]
        stripped = True
    if len(path) == 0:
        return {"ok": False, "prohibited": privacy.contains_prohibited(value)}
    if privacy.contains_prohibited(value) or privacy.contains_prohibited(path):
        return {"ok": False, "prohibited": True}
    return {"ok": True, "value": path, "changed": stripped or path != value}


def _content_type(value):
    if not isinstance(value, str) or walk.is_bound(value):
        return {"ok": False, "prohibited": True}
    base = value.split(";", 1)[0].strip().lower()
    if len(base) < 3 or len(base) > bounds["content_type_max_chars"]:
        return {"ok": False, "prohibited": privacy.contains_prohibited(value)}
    if not _MEDIA.match(base):
        return {"ok": False, "prohibited": privacy.contains_prohibited(value)}
    if privacy.contains_prohibited(base) or privacy.contains_prohibited(value):
        return {"ok": False, "prohibited": True}
    return {"ok": True, "value": base, "changed": base != value}


def _http_status(value):
    if isinstance(value, bool) or not _is_integer(value):
        return None
    if value < 100 or value > 599:
        return None
    return value


def _port_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and _PORT.match(value):
        number = int(value)
        if 1 <= number <= 65535:
            return {"value": number, "changed": True}
        return None
    if not _is_integer(value) or value < 1 or value > 65535:
        return None
    return {"value": value, "changed": False}


def _parse_authority(authority):
    host_text = authority
    port = None
    if authority.startswith("["):
        end = authority.find("]")
        if end == -1:
            return {"ok": False}
        host_text = authority[1:end]
        rest = authority[end + 1 :]
        if rest.startswith(":"):
            parsed = _port_number(rest[1:])
            if not parsed:
                return {"ok": False}
            port = parsed["value"]
        elif len(rest) != 0:
            return {"ok": False}
        host = _normalize_host(host_text)
        if not host["ok"]:
            return {"ok": False, "prohibited": host.get("prohibited")}
        return {"ok": True, "host": host["value"], "ipClass": host["ipClass"], "port": port, "hostChanged": True}
    colon = authority.rfind(":")
    if colon != -1 and authority.find(":") == colon:
        host_text = authority[:colon]
        parsed = _port_number(authority[colon + 1 :])
        if not parsed:
            return {"ok": False}
        port = parsed["value"]
    host = _normalize_host(host_text)
    if not host["ok"]:
        return {"ok": False, "prohibited": host.get("prohibited")}
    return {
        "ok": True,
        "host": host["value"],
        "ipClass": host["ipClass"],
        "port": port,
        "hostChanged": host["changed"],
    }


def _parse_destination(raw, state):
    if not isinstance(raw, str) or walk.is_bound(raw):
        return {"ok": False, "failClosed": True, "privacy": True}
    if len(raw) > bounds["destination_raw_max_chars"] or _has_control(raw):
        return {"ok": False, "failClosed": True, "privacy": True}
    if privacy.has_db_scheme(raw):
        return {"ok": False, "failClosed": True, "privacy": True}
    body = raw
    hash_at = body.find("#")
    if hash_at != -1:
        fragment = body[hash_at + 1 :]
        body = body[:hash_at]
        if fragment and privacy.contains_prohibited(fragment):
            _mark_privacy(state)
        _add_disposition(state, "NORMALIZE")
    query_at = body.find("?")
    if query_at != -1:
        query = body[query_at + 1 :]
        body = body[:query_at]
        _add_disposition(state, "STRIP")
        if privacy.has_sensitive_query(raw) or privacy.contains_prohibited(query):
            _mark_privacy(state)
        else:
            _add_reason(state, "QUERY_STRIPPED")
    scheme_match = _SCHEME.match(body)
    if not scheme_match:
        return {"ok": False, "failClosed": True, "privacy": privacy.contains_prohibited(raw)}
    scheme = scheme_match.group(1).lower()
    if scheme in privacy.policy["db_schemes"]:
        return {"ok": False, "failClosed": True, "privacy": True}
    if scheme not in SCHEMES or scheme == "unknown":
        return {"ok": False, "failClosed": True, "privacy": privacy.contains_prohibited(raw)}
    rest = body[scheme_match.end() :]
    slash = rest.find("/")
    authority = rest if slash == -1 else rest[:slash]
    path = None if slash == -1 else rest[slash:]
    if "@" in authority:
        at = authority.rfind("@")
        userinfo = authority[:at]
        hostport = authority[at + 1 :]
        if not userinfo or not hostport or "@" in hostport:
            return {"ok": False, "failClosed": True, "privacy": True}
        _add_disposition(state, "STRIP")
        _mark_privacy(state)
        _add_reason(state, "USERINFO_STRIPPED")
        parsed = _parse_authority(hostport)
        if not parsed["ok"]:
            return {"ok": False, "failClosed": True, "privacy": True}
        if path:
            normalized = _normalize_path(path)
            if not normalized["ok"]:
                return {"ok": False, "failClosed": True, "privacy": True}
            path = normalized["value"]
        return {
            "ok": True,
            "scheme": scheme,
            "host": parsed["host"],
            "port": parsed["port"],
            "path": path,
            "ipClass": parsed["ipClass"],
        }
    parsed = _parse_authority(authority)
    if not parsed["ok"]:
        return {
            "ok": False,
            "failClosed": True,
            "privacy": bool(parsed.get("prohibited")) or privacy.contains_prohibited(raw),
        }
    if path:
        normalized = _normalize_path(path)
        if not normalized["ok"]:
            return {"ok": False, "failClosed": True, "privacy": True}
        path = normalized["value"]
    return {
        "ok": True,
        "scheme": scheme,
        "host": parsed["host"],
        "port": parsed["port"],
        "path": path,
        "ipClass": parsed["ipClass"],
    }


def _string_secret(value):
    if walk.is_bound(value):
        return True
    return isinstance(value, str) and privacy.contains_prohibited(value)


def _consume_string_field(value):
    if walk.is_bound(value):
        return {"prohibited": True, "malformed": value.get("__optics_bound") == walk.MALFORMED_TEXT}
    if not isinstance(value, str):
        return {"bad": True}
    if privacy.contains_prohibited(value):
        return {"prohibited": True}
    return {"value": value}


def _check_session(value, basis, producer_ok):
    if walk.is_bound(value):
        malformed = value.get("__optics_bound") == walk.MALFORMED_TEXT
        return {"omit": True, "session": True, "privacy": not malformed, "malformed": malformed}
    if not isinstance(value, str) or not isinstance(basis, str):
        return {"omit": True, "session": True}
    if basis not in SESSION_BASIS:
        return {"omit": True, "session": True}
    if basis == "OPTICS_GENERATED" and not producer_ok:
        return {"omit": True, "session": True}
    if unicodedata.normalize("NFC", value) != value:
        return {"omit": True, "session": True}
    if _utf8_bytes(value) > bounds["session_id_max_bytes"]:
        return {"omit": True, "session": True, "privacy": privacy.contains_prohibited(value)}
    if value.startswith(" ") or value.endswith(" "):
        return {"omit": True, "session": True}
    if "/" in value or "\\" in value or "@" in value:
        return {"omit": True, "session": True, "privacy": privacy.contains_prohibited(value)}
    for ch in value:
        code = ord(ch)
        if code <= 0x1F or code == 0x7F or _is_noncharacter(code):
            return {"omit": True, "session": True}
    if privacy.contains_prohibited(value):
        return {"omit": True, "session": True, "privacy": True}
    return {"ok": True, "value": value, "basis": basis}


def _event_id_for(producer_id, sequence):
    return "e." + str(_utf8_bytes(producer_id)) + "." + producer_id + "." + str(sequence)


def _recognized_producer(producer, version, origin):
    if producer not in PRODUCERS:
        return False
    if not isinstance(version, str) or not re.match(r"^[A-Za-z0-9._+-]{1,32}$", version):
        return False
    if origin not in WRITER_ORIGINS:
        return False
    return True


def _apply_origin(state, record, requested_origin, producer, version, demo_host):
    if demo_host:
        _put(
            state,
            record,
            "evidence_origin",
            "SIMULATED_DEMO",
            "accepted" if requested_origin == "SIMULATED_DEMO" else "normalized",
        )
        state.reader_origin = "SIMULATED_DEMO"
        _add_reason(state, "SIMULATED_DEMO")
        _add_disposition(state, "REPLACE_WITH_SAFE_CATEGORY")
        state.provenance = "SUFFICIENT" if producer == "demo_command" else "INSUFFICIENT"
        return
    sufficient = _recognized_producer(producer, version, requested_origin)
    if producer == "demo_command" and requested_origin == "LOCAL_OBSERVATION":
        state.reader_origin = "LEGACY_UNMARKED"
        state.provenance = "INSUFFICIENT"
        _add_reason(state, "LEGACY_UNMARKED")
        _add_disposition(state, "REPLACE_WITH_SAFE_CATEGORY")
        return
    if requested_origin and requested_origin in WRITER_ORIGINS and sufficient:
        _put(state, record, "evidence_origin", requested_origin, "accepted")
        state.reader_origin = requested_origin
        state.provenance = "SUFFICIENT"
        return
    if requested_origin == "LOCAL_OBSERVATION" or not requested_origin:
        state.reader_origin = "LEGACY_UNMARKED"
        state.provenance = "INSUFFICIENT"
        _add_reason(state, "PROVENANCE_INSUFFICIENT" if requested_origin else "LEGACY_UNMARKED")
        _add_disposition(state, "REPLACE_WITH_SAFE_CATEGORY")
        return
    if requested_origin in WRITER_ORIGINS:
        state.reader_origin = "LEGACY_UNMARKED"
        state.provenance = "INSUFFICIENT"
        _add_reason(state, "PROVENANCE_INSUFFICIENT")
        _add_disposition(state, "REPLACE_WITH_SAFE_CATEGORY")
        return
    state.reader_origin = "LEGACY_UNMARKED"
    state.provenance = "INSUFFICIENT"
    _add_reason(state, "LEGACY_UNMARKED")
    _add_disposition(state, "REPLACE_WITH_SAFE_CATEGORY")


def _take(source, seen, key):
    if key in source:
        seen.add(key)
        return {"present": True, "value": source[key]}
    return {"present": False, "value": None}


def _tree_has_secret(value, depth):
    if depth > 8:
        return True
    if isinstance(value, str):
        return privacy.contains_prohibited(value)
    if walk.is_bound(value):
        return True
    if isinstance(value, list):
        return any(_tree_has_secret(item, depth + 1) for item in value)
    if isinstance(value, dict):
        for key in value.keys():
            if privacy.is_payload_name(key) or privacy.is_baggage_name(key):
                return True
            if privacy.is_prohibited_name(key) and privacy.normalize_name(key) not in STRUCTURAL_EXCLUSIONS:
                return True
            if _tree_has_secret(value[key], depth + 1):
                return True
        return False
    return False


def _sweep_leftovers(source, seen, state):
    for key in sorted(source.keys()):
        if key in seen:
            continue
        value = source[key]
        secret = _string_secret(value) or _tree_has_secret(value, 0)
        if privacy.is_payload_name(key):
            _strip_key(state, key)
            _mark_privacy(state)
            _drop_record(state, "PROMPT_COMPLETION_EXCLUDED")
            continue
        if privacy.is_baggage_name(key):
            _strip_key(state, key)
            _add_reason(state, "BAGGAGE_OMITTED")
            if secret:
                _mark_privacy(state)
            continue
        _strip_key(state, key)
        structural = privacy.normalize_name(key) in STRUCTURAL_EXCLUSIONS
        if secret or (privacy.is_prohibited_name(key) and not structural):
            _mark_privacy(state)


def _collect_destination(source, seen, state):
    proxy_keys = ["proxy", "proxy_url", "proxy_destination"]
    redirect_keys = ["redirect_url", "redirect_destination"]
    connected_keys = ["connected_host", "connected_url", "connected_destination"]
    requested_keys = ["requested_url", "requested_destination", "url", "destination"]
    proxy = False
    redirect = False
    for key in proxy_keys:
        item = _take(source, seen, key)
        if not item["present"]:
            continue
        proxy = True
        _strip_key(state, key)
        if _string_secret(item["value"]):
            _mark_privacy(state)
    for key in redirect_keys:
        item = _take(source, seen, key)
        if not item["present"]:
            continue
        redirect = True
        _strip_key(state, key)
        if _string_secret(item["value"]):
            _mark_privacy(state)
    explicit = _take(source, seen, "destination_host")
    explicit_port = _take(source, seen, "destination_port")
    explicit_scheme = _take(source, seen, "scheme")
    explicit_path = _take(source, seen, "path")
    connected_from = None
    for key in connected_keys:
        item = _take(source, seen, key)
        if not item["present"]:
            continue
        _strip_key(state, key)
        if connected_from is None:
            connected_from = item
    requested = None
    for key in requested_keys:
        item = _take(source, seen, key)
        if not item["present"]:
            continue
        _strip_key(state, key)
        if requested is None:
            requested = item
    if proxy:
        state.destination_class = "PROXY_OMITTED"
    elif redirect and not explicit["present"] and not connected_from:
        state.destination_class = "REDIRECT_OMITTED"
    parsed = []
    if connected_from:
        if isinstance(connected_from["value"], str) and "://" in connected_from["value"]:
            got = _parse_destination(connected_from["value"], state)
            if not got["ok"]:
                return {"fail": True, "privacy": got.get("privacy")}
            got["source"] = "connected"
            parsed.append(got)
        else:
            host = _normalize_host(connected_from["value"])
            if not host["ok"]:
                return {"fail": True, "privacy": host.get("prohibited")}
            parsed.append({
                "source": "connected",
                "ok": True,
                "host": host["value"],
                "ipClass": host["ipClass"],
                "port": None,
                "scheme": None,
                "path": None,
                "hostChanged": host["changed"],
            })
    if requested:
        got = _parse_destination(requested["value"], state)
        if not got["ok"]:
            return {"fail": True, "privacy": got.get("privacy")}
        got["source"] = "requested"
        parsed.append(got)
    chosen = None
    if explicit["present"]:
        host = _normalize_host(explicit["value"])
        if not host["ok"]:
            return {"fail": True, "privacy": host.get("prohibited")}
        chosen = {
            "host": host["value"],
            "ipClass": host["ipClass"],
            "hostChanged": host["changed"],
            "scheme": None,
            "port": None,
            "path": None,
            "source": "explicit",
        }
        if not state.destination_class:
            state.destination_class = "EXPLICIT"
    elif parsed:
        chosen = parsed[0]
        if not state.destination_class:
            state.destination_class = "CONNECTED" if chosen["source"] == "connected" else "REQUESTED_URL"
    for item in parsed:
        if chosen and item["host"] != chosen["host"]:
            state.configuration_fault = True
            _add_reason(state, "DESTINATION_CONFLICT")
            _add_disposition(state, "REJECT_FIELD")
            _reject_field(state, "destination_host")
            return {"conflict": True}
        if chosen and item["host"] == chosen["host"]:
            if chosen.get("port") is None and item.get("port") is not None:
                chosen["port"] = item["port"]
            if not chosen.get("scheme") and item.get("scheme"):
                chosen["scheme"] = item["scheme"]
            if not chosen.get("path") and item.get("path"):
                chosen["path"] = item["path"]
            if not chosen.get("ipClass") and item.get("ipClass"):
                chosen["ipClass"] = item["ipClass"]
    if not chosen:
        return {"empty": True, "explicitPort": explicit_port, "explicitScheme": explicit_scheme, "explicitPath": explicit_path}
    if explicit_port["present"] and explicit_port["value"] is None:
        if chosen.get("port") is None:
            chosen["portNullAccepted"] = True
    elif explicit_port["present"]:
        parsed_port = _port_number(explicit_port["value"])
        if not parsed_port:
            _reject_field(state, "destination_port")
            if _string_secret(explicit_port["value"]):
                _mark_privacy(state)
        elif chosen.get("port") is not None and chosen["port"] != parsed_port["value"]:
            state.configuration_fault = True
            _add_reason(state, "DESTINATION_CONFLICT")
            _add_disposition(state, "REJECT_FIELD")
            _reject_field(state, "destination_host")
            return {"conflict": True}
        else:
            chosen["port"] = parsed_port["value"]
            chosen["portChanged"] = parsed_port["changed"]
    if explicit_scheme["present"]:
        scheme = explicit_scheme["value"].lower() if isinstance(explicit_scheme["value"], str) else ""
        unknown_mismatch = scheme == "unknown" and explicit_scheme["value"] != "unknown"
        if scheme not in SCHEMES or unknown_mismatch:
            if scheme != "unknown":
                _reject_field(state, "scheme")
                if _string_secret(explicit_scheme["value"]):
                    _mark_privacy(state)
        if scheme in SCHEMES:
            if chosen.get("scheme") and chosen["scheme"] != scheme:
                state.configuration_fault = True
                _add_reason(state, "DESTINATION_CONFLICT")
                _reject_field(state, "scheme")
                return {"conflict": True}
            chosen["scheme"] = scheme
            chosen["schemeChanged"] = scheme != explicit_scheme["value"]
    if not chosen.get("scheme"):
        chosen["scheme"] = "unknown"
    if explicit_path["present"]:
        path_value = _normalize_path(explicit_path["value"])
        if not path_value["ok"]:
            _reject_field(state, "path")
            if path_value.get("oversize"):
                _add_reason(state, "PATH_OVERSIZE")
            if path_value.get("prohibited"):
                _mark_privacy(state)
        elif chosen.get("path") and chosen["path"] != path_value["value"]:
            state.configuration_fault = True
            _add_reason(state, "DESTINATION_CONFLICT")
            _reject_field(state, "path")
            return {"conflict": True}
        else:
            chosen["path"] = path_value["value"]
            chosen["pathChanged"] = path_value["changed"]
    return {"chosen": chosen}


def _store_destination(state, record, collected):
    if not collected or collected.get("fail"):
        if collected and collected.get("privacy"):
            _mark_privacy(state)
        _add_reason(state, "DESTINATION_UNSAFE")
        _add_disposition(state, "REJECT_FIELD")
        _reject_field(state, "destination_host")
        _reject_field(state, "destination_port")
        _reject_field(state, "scheme")
        _reject_field(state, "path")
        return
    if collected.get("conflict") or collected.get("empty"):
        return
    chosen = collected["chosen"]
    _put(state, record, "destination_host", chosen["host"], "normalized" if chosen.get("hostChanged") else "accepted")
    if chosen.get("port") is None:
        if chosen.get("portNullAccepted"):
            _put(state, record, "destination_port", None, "accepted")
    else:
        _put(
            state,
            record,
            "destination_port",
            chosen["port"],
            "normalized" if chosen.get("portChanged") else "accepted",
        )
    _put(state, record, "scheme", chosen["scheme"], "normalized" if chosen.get("schemeChanged") else "accepted")
    if chosen.get("path"):
        _put(state, record, "path", chosen["path"], "normalized" if chosen.get("pathChanged") else "accepted")
    state.destination_ip_class = chosen.get("ipClass") or None


def _common_identity(source, seen, state, record, kind):
    producer = _take(source, seen, "producer")
    version = _take(source, seen, "cli_or_sdk_version")
    producer_version = _take(source, seen, "producer_version")
    version_value = None
    if version["present"]:
        token = _version_token(version["value"], 32)
        if isinstance(token, dict) and token.get("prohibited"):
            _reject_field(state, "cli_or_sdk_version")
            _mark_privacy(state)
        elif isinstance(token, str):
            version_value = token
            _put(state, record, "cli_or_sdk_version", token, "accepted")
        elif version["value"] is not None:
            _reject_field(state, "cli_or_sdk_version")
    elif producer_version["present"]:
        _strip_key(state, "producer_version")
        token = _version_token(producer_version["value"], 32)
        if isinstance(token, str):
            version_value = token
            _put(state, record, "cli_or_sdk_version", token, "normalized")
    producer_value = None
    if producer["present"] and producer["value"] in PRODUCERS:
        producer_value = producer["value"]
        _put(state, record, "producer", producer["value"], "accepted")
    elif producer["present"]:
        _reject_field(state, "producer")
        if _string_secret(producer["value"]):
            _mark_privacy(state)
    run_id = _take(source, seen, "run_id")
    if run_id["present"] and run_id["value"] is not None:
        token = _id_token(run_id["value"], 80)
        if isinstance(token, dict) and token.get("prohibited"):
            _reject_field(state, "run_id")
            _mark_privacy(state)
        elif isinstance(token, str):
            _put(state, record, "run_id", token, "accepted")
        else:
            _reject_field(state, "run_id")
    parent = _take(source, seen, "parent_run_id")
    if parent["present"]:
        if parent["value"] is None:
            _put(state, record, "parent_run_id", None, "accepted")
        else:
            token = _id_token(parent["value"], 80)
            if isinstance(token, str):
                _put(state, record, "parent_run_id", token, "accepted")
            else:
                _reject_field(state, "parent_run_id")
                if isinstance(token, dict) and token.get("prohibited"):
                    _mark_privacy(state)
    producer_id = _take(source, seen, "producer_id")
    producer_id_value = None
    if producer_id["present"] and producer_id["value"] is not None:
        token = _id_token(producer_id["value"], 80)
        if isinstance(token, str):
            if record.get("run_id") and token == record.get("run_id"):
                state.configuration_fault = False
                _put(state, record, "producer_id", token, "accepted")
                _put(state, record, "identity_conflict", "PRODUCER_SEQUENCE", "normalized")
                producer_id_value = token
            else:
                producer_id_value = token
                _put(state, record, "producer_id", token, "accepted")
        else:
            _reject_field(state, "producer_id")
            if isinstance(token, dict) and token.get("prohibited"):
                _mark_privacy(state)
    sequence = _take(source, seen, "producer_sequence")
    sequence_value = None
    if sequence["present"] and sequence["value"] is not None:
        number = _non_negative_int(sequence["value"])
        if number is None:
            _reject_field(state, "producer_sequence")
        else:
            sequence_value = number
            _put(state, record, "producer_sequence", number, "accepted")
    if kind == "observation":
        seq = _take(source, seen, "sequence")
        if sequence_value is not None:
            if not seq["present"] or seq["value"] != sequence_value:
                _put(state, record, "sequence", sequence_value, "normalized")
                if seq["present"] and seq["value"] != sequence_value:
                    _put(state, record, "identity_conflict", "PRODUCER_SEQUENCE", "normalized")
            else:
                _put(state, record, "sequence", sequence_value, "accepted")
        elif seq["present"]:
            _reject_field(state, "sequence")
        if producer_id_value is not None and sequence_value is not None:
            canonical_id = _event_id_for(producer_id_value, sequence_value)
            event_id = _take(source, seen, "event_id")
            if len(canonical_id) <= bounds["event_id_max_chars"]:
                same = event_id["present"] and event_id["value"] == canonical_id
                _put(state, record, "event_id", canonical_id, "accepted" if same else "normalized")
        else:
            event_id = _take(source, seen, "event_id")
            if event_id["present"]:
                token = event_id["value"]
                ok = (
                    isinstance(token, str)
                    and _EVENT.match(token)
                    and len(token) <= bounds["event_id_max_chars"]
                    and not privacy.contains_prohibited(token)
                )
                if ok:
                    _put(state, record, "event_id", token, "accepted")
                else:
                    _reject_field(state, "event_id")
                    if _string_secret(event_id["value"]):
                        _mark_privacy(state)
    return {"producer": producer_value, "version": version_value}


def _apply_trace(source, seen, state, record):
    direct = _take(source, seen, "trace_id")
    basis = _take(source, seen, "trace_id_basis")
    inherited = _take(source, seen, "vantio_trace_id")
    parent_header = _take(source, seen, "traceparent")
    span = _take(source, seen, "span_id")
    parent_span = _take(source, seen, "parent_span_id")
    if inherited["present"]:
        _strip_key(state, "vantio_trace_id")
    if parent_header["present"]:
        _strip_key(state, "traceparent")
    accepted = []
    if direct["present"] and direct["value"] is not None:
        norm = _trace_normalize(direct["value"])
        if not norm or norm.get("prohibited"):
            _mark_context(state)
            if norm and norm.get("prohibited"):
                _mark_privacy(state)
        else:
            accepted.append({"trace": norm["value"], "changed": norm["changed"], "source": "trace_id"})
    if inherited["present"] and inherited["value"] is not None:
        norm = _trace_normalize(inherited["value"])
        if not norm or norm.get("prohibited"):
            _mark_context(state)
            if norm and norm.get("prohibited"):
                _mark_privacy(state)
            state.trace_meaning = "ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF"
        else:
            accepted.append({"trace": norm["value"], "changed": True, "source": "vantio_trace_id"})
            state.trace_meaning = "ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF"
    header_span = None
    if parent_header["present"] and parent_header["value"] is not None:
        parsed = _parse_traceparent(parent_header["value"])
        if not parsed:
            _mark_context(state)
            if _string_secret(parent_header["value"]):
                _mark_privacy(state)
        else:
            accepted.append({"trace": parsed["trace"], "changed": True, "source": "traceparent"})
            header_span = parsed["span"]
    distinct = []
    for item in accepted:
        if item["trace"] not in distinct:
            distinct.append(item["trace"])
    if len(distinct) > 1:
        _mark_context(state)
        state.configuration_fault = True
        _put(state, record, "trace_id", None, "normalized")
        _put(state, record, "trace_id_basis", None, "normalized")
        _put(state, record, "span_id", None, "normalized")
        _put(state, record, "parent_span_id", None, "normalized")
        return
    if len(distinct) == 1:
        item = accepted[0]
        if basis["present"] and basis["value"] in TRACE_BASIS:
            basis_value = basis["value"]
        elif item["source"] != "trace_id":
            basis_value = "ASSERTED_CONTEXT"
        else:
            _mark_context(state)
            _put(state, record, "trace_id", None, "normalized")
            _put(state, record, "trace_id_basis", None, "normalized")
            return
        _put(
            state,
            record,
            "trace_id",
            item["trace"],
            "normalized" if item["changed"] or item["source"] != "trace_id" else "accepted",
        )
        same_basis = basis["present"] and basis["value"] == basis_value
        _put(state, record, "trace_id_basis", basis_value, "accepted" if same_basis else "normalized")
    elif direct["present"] or inherited["present"] or parent_header["present"]:
        _put(state, record, "trace_id", None, "normalized")
        _put(state, record, "trace_id_basis", None, "normalized")
    if state.context_rejected and len(distinct) != 1:
        return
    if span["present"]:
        if span["value"] is None:
            _put(state, record, "span_id", None, "accepted")
        else:
            norm = _span_normalize(span["value"])
            if not norm or norm.get("prohibited"):
                _mark_context(state)
                _put(state, record, "span_id", None, "normalized")
                if norm and norm.get("prohibited"):
                    _mark_privacy(state)
            else:
                _put(state, record, "span_id", norm["value"], "normalized" if norm["changed"] else "accepted")
    elif header_span and not state.context_rejected:
        _put(state, record, "span_id", header_span, "normalized")
    if parent_span["present"]:
        if parent_span["value"] is None:
            _put(state, record, "parent_span_id", None, "accepted")
        else:
            norm = _span_normalize(parent_span["value"])
            if not norm or norm.get("prohibited"):
                _mark_context(state)
                _put(state, record, "parent_span_id", None, "normalized")
                if norm and norm.get("prohibited"):
                    _mark_privacy(state)
            else:
                _put(
                    state,
                    record,
                    "parent_span_id",
                    norm["value"],
                    "normalized" if norm["changed"] else "accepted",
                )


def _apply_session(source, seen, state, record, producer_ok):
    identifier = _take(source, seen, "session_id")
    basis = _take(source, seen, "session_id_basis")
    if not identifier["present"] and not basis["present"]:
        return
    if (
        not identifier["present"]
        or not basis["present"]
        or identifier["value"] is None
        or basis["value"] is None
    ):
        _mark_session(state)
        if _string_secret(identifier["value"]) or _string_secret(basis["value"]):
            _mark_privacy(state)
        return
    checked = _check_session(identifier["value"], basis["value"], producer_ok)
    if not checked.get("ok"):
        _mark_session(state)
        if checked.get("privacy"):
            _mark_privacy(state)
        return
    _put(state, record, "session_id", checked["value"], "accepted")
    _put(state, record, "session_id_basis", checked["basis"], "accepted")


def _apply_clock_and_status(source, seen, state, record, kind):
    for key in ("started_at", "ended_at"):
        if kind == "observation" and key == "ended_at":
            continue
        item = _take(source, seen, key)
        if not item["present"] or item["value"] is None:
            continue
        stamp = _canonical_time(item["value"])
        if not stamp:
            _reject_field(state, key)
            if _string_secret(item["value"]):
                _mark_privacy(state)
        else:
            _put(state, record, key, stamp["value"], "normalized" if stamp["changed"] else "accepted")
    duration = _take(source, seen, "duration_ms")
    if duration["present"] and duration["value"] is not None:
        number = _non_negative_int(duration["value"])
        if number is None:
            _reject_field(state, "duration_ms")
        else:
            _put(state, record, "duration_ms", number, "accepted")
    clock = _take(source, seen, "clock_quality")
    if clock["present"] and clock["value"] in CLOCK:
        _put(state, record, "clock_quality", clock["value"], "accepted")
    elif clock["present"] and clock["value"] is not None:
        _reject_field(state, "clock_quality")
    life = _take(source, seen, "lifecycle")
    if life["present"] and life["value"] in LIFECYCLE:
        _put(state, record, "lifecycle", life["value"], "accepted")
        if life["value"] == "INTERRUPTED":
            state.interrupted = True
    elif life["present"] and life["value"] is not None:
        _reject_field(state, "lifecycle")
    conflict = _take(source, seen, "identity_conflict")
    if "identity_conflict" not in record:
        if conflict["present"] and conflict["value"] in CONFLICT:
            _put(state, record, "identity_conflict", conflict["value"], "accepted")
        elif conflict["present"] and conflict["value"] is not None:
            _reject_field(state, "identity_conflict")
        elif kind in ("observation", "envelope"):
            _put(state, record, "identity_conflict", "NONE", "normalized")
    runtime = _take(source, seen, "runtime")
    if runtime["present"] and runtime["value"] in RUNTIMES:
        _put(state, record, "runtime", runtime["value"], "accepted")
    elif runtime["present"] and runtime["value"] is not None:
        _reject_field(state, "runtime")
    runtime_version = _take(source, seen, "runtime_version")
    if runtime_version["present"]:
        token = _version_token(runtime_version["value"], 32)
        if isinstance(token, str):
            _put(state, record, "runtime_version", token, "accepted")
        else:
            _reject_field(state, "runtime_version")
            if isinstance(token, dict) and token.get("prohibited"):
                _mark_privacy(state)
    platform = _take(source, seen, "platform")
    if platform["present"] and platform["value"] in PLATFORMS:
        _put(state, record, "platform", platform["value"], "accepted")
    elif platform["present"] and platform["value"] is not None:
        _reject_field(state, "platform")
        if _string_secret(platform["value"]):
            _mark_privacy(state)
    arch = _take(source, seen, "arch")
    if arch["present"] and arch["value"] in ARCHES:
        _put(state, record, "arch", arch["value"], "accepted")
    elif arch["present"] and arch["value"] is not None:
        _reject_field(state, "arch")
    for key in ("process_id", "parent_process_id"):
        item = _take(source, seen, key)
        if not item["present"]:
            continue
        if item["value"] is None:
            _put(state, record, key, None, "accepted")
        else:
            number = _non_negative_int(item["value"])
            if number is None:
                _reject_field(state, key)
            else:
                _put(state, record, key, number, "accepted")


def _apply_schema(state, record, source, seen, record_type):
    _put(
        state,
        record,
        "record_type",
        record_type,
        "accepted" if source.get("record_type") == record_type else "normalized",
    )
    seen.add("record_type")
    status = _take(source, seen, "schema_status")
    _put(
        state,
        record,
        "schema_status",
        "unstable-pre-1.0",
        "accepted" if status["present"] and status["value"] == "unstable-pre-1.0" else "normalized",
    )
    if status["present"] and status["value"] != "unstable-pre-1.0":
        _add_reason(state, "SCHEMA_STATUS_CORRECTED")
    version = _take(source, seen, "schema_version")
    _put(state, record, "schema_version", 0, "accepted" if version["present"] and version["value"] == 0 else "normalized")
    if version["present"] and _is_integer(version["value"]):
        return version["value"]
    return None


def _apply_observation_fields(source, seen, state, record):
    status = _take(source, seen, "http_status")
    legacy_status = _take(source, seen, "status")
    if status["present"]:
        raw_status = status["value"]
    elif legacy_status["present"]:
        raw_status = legacy_status["value"]
    else:
        raw_status = None
    raw_present = status["present"] or legacy_status["present"]
    if legacy_status["present"]:
        _strip_key(state, "status")
    code = None if raw_status is None else _http_status(raw_status)
    if raw_present and raw_status is not None and code is None:
        _reject_field(state, "http_status")
        if _string_secret(raw_status):
            _mark_privacy(state)
    if code is not None:
        state.http_status = code
        _put(state, record, "http_status", code, "accepted" if raw_status == code else "normalized")
    derived_app = None if code is None else _application_status_from_http(code)
    app = _take(source, seen, "application_status")
    legacy_app = _take(source, seen, "applicationStatus")
    if legacy_app["present"]:
        _strip_key(state, "applicationStatus")
    coverage = _take(source, seen, "coverage_gap")
    if coverage["present"]:
        _strip_key(state, "coverage_gap")
        if coverage["value"] == "EVIDENCED":
            state.coverage_evidenced = True
        else:
            state.coverage_unevidenced = True
    if derived_app:
        app_value = derived_app
    elif app["present"] and app["value"] == "NOT_OBSERVED":
        app_value = "NOT_OBSERVED"
    elif legacy_app["present"] and legacy_app["value"] == "NOT_OBSERVED":
        app_value = "NOT_OBSERVED"
    else:
        app_value = "UNAVAILABLE"
    if app["present"] or legacy_app["present"] or code is not None:
        same = (app["present"] and app["value"] == app_value) or (
            not app["present"] and legacy_app["present"] and legacy_app["value"] == app_value
        )
        _put(state, record, "application_status", app_value, "accepted" if same else "normalized")
    failure = _take(source, seen, "failure_kind")
    if failure["present"] and failure["value"] in FAILURES:
        _put(state, record, "failure_kind", failure["value"], "accepted")
        if failure["value"] in NETWORK_KINDS and code is None:
            state.network_no_http = True
        if failure["value"] == "wrapped" and code is None:
            state.customer_exception = True
        if failure["value"] != "none":
            state.failure_identified = True
    elif failure["present"] and failure["value"] is not None:
        _reject_field(state, "failure_kind")
        if _string_secret(failure["value"]):
            _mark_privacy(state)
    error_class = _take(source, seen, "error_class")
    if error_class["present"] and error_class["value"] is not None:
        token = error_class["value"]
        if isinstance(token, str) and _TOKEN64.match(token) and not privacy.contains_prohibited(token):
            _put(state, record, "error_class", token, "accepted")
            if code is None and (not failure["present"] or failure["value"] == "wrapped" or failure["value"] is None):
                state.customer_exception = True
        else:
            _reject_field(state, "error_class")
            _mark_privacy(state)
    action = _take(source, seen, "action")
    if action["present"] and action["value"] != "OBSERVED":
        if _string_secret(action["value"]):
            _mark_privacy(state)
        _drop_record(state, "ENFORCEMENT_ACTION_EXCLUDED")
        _reject_field(state, "action")
    elif action["present"]:
        _put(state, record, "action", "OBSERVED", "accepted")
    else:
        _put(state, record, "action", "OBSERVED", "normalized")
    method = _take(source, seen, "method")
    if method["present"] and method["value"] is not None:
        upper = method["value"].upper() if isinstance(method["value"], str) else ""
        if upper in METHODS:
            _put(state, record, "method", upper, "accepted" if upper == method["value"] else "normalized")
        elif _string_secret(method["value"]):
            _reject_field(state, "method")
            _mark_privacy(state)
        else:
            _put(state, record, "method", "unknown", "normalized")
    bytes_in = _take(source, seen, "request_bytes")
    if bytes_in["present"] and bytes_in["value"] is not None:
        number = _non_negative_int(bytes_in["value"])
        if number is None:
            _reject_field(state, "request_bytes")
        else:
            _put(state, record, "request_bytes", number, "accepted")
    response = _take(source, seen, "response_bytes")
    legacy_bytes = _take(source, seen, "bytes")
    if legacy_bytes["present"]:
        _strip_key(state, "bytes")
    if response["present"]:
        if response["value"] is None:
            _put(state, record, "response_bytes", None, "accepted")
        else:
            number = _non_negative_int(response["value"])
            if number is None:
                _reject_field(state, "response_bytes")
            else:
                _put(state, record, "response_bytes", number, "accepted")
    elif legacy_bytes["present"]:
        if legacy_bytes["value"] == 0 or legacy_bytes["value"] is None:
            _put(state, record, "response_bytes", None, "normalized")
        else:
            number = _non_negative_int(legacy_bytes["value"])
            if number is None:
                _reject_field(state, "response_bytes")
            else:
                _put(state, record, "response_bytes", number, "normalized")
    media = _take(source, seen, "content_type")
    if media["present"] and media["value"] is not None:
        parsed = _content_type(media["value"])
        if not parsed["ok"]:
            _reject_field(state, "content_type")
            if parsed.get("prohibited"):
                _mark_privacy(state)
        else:
            _put(state, record, "content_type", parsed["value"], "normalized" if parsed["changed"] else "accepted")
    mediation = _take(source, seen, "mediation")
    if mediation["present"] and mediation["value"] is not None:
        if isinstance(mediation["value"], str) and mediation["value"] in MEDIATION:
            _put(state, record, "mediation", mediation["value"], "accepted")
        elif _string_secret(mediation["value"]):
            _reject_field(state, "mediation")
            _mark_privacy(state)
        else:
            _put(state, record, "mediation", "unknown", "normalized")
    sampling = _take(source, seen, "sampling")
    if not sampling["present"] or sampling["value"] == "UNSAMPLED":
        _put(state, record, "sampling", "UNSAMPLED", "accepted" if sampling["present"] else "normalized")
    else:
        _put(state, record, "sampling", "UNSAMPLED", "normalized")
        if _string_secret(sampling["value"]):
            _mark_privacy(state)
    duplicate = _take(source, seen, "duplicate_of")
    if duplicate["present"]:
        token = duplicate["value"]
        if token is None:
            _put(state, record, "duplicate_of", None, "accepted")
        elif isinstance(token, str) and len(token) <= bounds["event_id_max_chars"] and not privacy.contains_prohibited(token):
            _put(state, record, "duplicate_of", token, "accepted")
        else:
            _reject_field(state, "duplicate_of")
            if _string_secret(token):
                _mark_privacy(state)
    provider = _take(source, seen, "provider_id")
    confidence = _take(source, seen, "provider_confidence")
    legacy_provider = _take(source, seen, "provider")
    if legacy_provider["present"]:
        _strip_key(state, "provider")
        if _string_secret(legacy_provider["value"]):
            _mark_privacy(state)
    provider_value = "unknown"
    confidence_value = "NONE"
    provider_kind = "normalized"
    if provider["present"] and isinstance(provider["value"], str) and _PROVIDER.match(provider["value"]):
        provider_value = provider["value"]
        provider_kind = "accepted"
    elif provider["present"] and provider["value"] is not None and provider["value"] != "unknown":
        _reject_field(state, "provider_id")
        if _string_secret(provider["value"]):
            _mark_privacy(state)
    if confidence["present"] and confidence["value"] in CONFIDENCE:
        confidence_value = confidence["value"]
    if confidence_value == "LOCAL_OLLAMA":
        host = record.get("destination_host")
        port = record.get("destination_port")
        local = host in ("localhost", "127.0.0.1", "::1")
        if not (local and port == 11434):
            provider_value = "unknown"
            confidence_value = "NONE"
            provider_kind = "normalized"
    if confidence_value == "NONE":
        provider_value = "unknown"
    if provider["present"] or confidence["present"] or legacy_provider["present"]:
        kind = provider_kind if provider["present"] and provider_value == provider["value"] else "normalized"
        _put(state, record, "provider_id", provider_value, kind)
        same_confidence = confidence["present"] and confidence["value"] == confidence_value
        _put(state, record, "provider_confidence", confidence_value, "accepted" if same_confidence else "normalized")
    optics = _take(source, seen, "optics_status")
    legacy_optics = _take(source, seen, "opticsStatus")
    if legacy_optics["present"]:
        _strip_key(state, "opticsStatus")
    if optics["present"]:
        optics_value = optics["value"]
    elif legacy_optics["present"]:
        optics_value = legacy_optics["value"]
    else:
        optics_value = None
    if state.drop_record:
        return
    if optics_value in OPTICS_STATUS:
        _put(state, record, "optics_status", optics_value, "accepted")
    else:
        _put(state, record, "optics_status", "SUCCESS", "normalized")
    internal = _take(source, seen, "optics_internal_failure")
    if internal["present"]:
        _strip_key(state, "optics_internal_failure")
        if internal["value"] is True:
            state.optics_internal = True
            _drop_record(state, "OPTICS_WRITE_FAILURE")
    environment = _take(source, seen, "environment_condition")
    if environment["present"]:
        _strip_key(state, "environment_condition")
        if environment["value"] is True:
            state.environment_fault = True
    parent_conflict = _take(source, seen, "parent_conflict")
    if parent_conflict["present"]:
        _strip_key(state, "parent_conflict")
        if parent_conflict["value"] is True and record.get("identity_conflict") != "PRODUCER_SEQUENCE":
            _put(state, record, "identity_conflict", "PARENT", "normalized")


def _build_observation(source):
    state = State()
    seen = set()
    record = {}
    _apply_schema(state, record, source, seen, "observation_event")
    who = _common_identity(source, seen, state, record, "observation")
    _apply_session(source, seen, state, record, bool(who["producer"] and who["version"]))
    _apply_trace(source, seen, state, record)
    _apply_clock_and_status(source, seen, state, record, "observation")
    destination = _collect_destination(source, seen, state)
    if not state.drop_record:
        _store_destination(state, record, destination)
    _apply_observation_fields(source, seen, state, record)
    demo = record.get("destination_host") == meta["demo_host"]
    requested = source["evidence_origin"] if "evidence_origin" in source else None
    seen.add("evidence_origin")
    _apply_origin(state, record, requested, who["producer"], who["version"], demo)
    location = _issue_location(state)
    _put(
        state,
        record,
        "issue_location",
        location,
        "accepted" if source.get("issue_location") == location else "normalized",
    )
    seen.add("issue_location")
    if source.get("issue_location") == "Provider fault":
        _mark_privacy(state)
    _sweep_leftovers(source, seen, state)
    if state.drop_record:
        state.accepted.clear()
        state.normalized.clear()
        record.pop("optics_status", None)
    return {"state": state, "record": None if state.drop_record else record}


def _build_envelope(source):
    state = State()
    seen = set()
    record = {}
    _apply_schema(state, record, source, seen, "run_envelope")
    who = _common_identity(source, seen, state, record, "envelope")
    _apply_session(source, seen, state, record, bool(who["producer"] and who["version"]))
    _apply_trace(source, seen, state, record)
    _apply_clock_and_status(source, seen, state, record, "envelope")
    state.accepted.discard("span_id")
    state.normalized.discard("span_id")
    state.accepted.discard("parent_span_id")
    state.normalized.discard("parent_span_id")
    span_kind = "accepted" if "span_id" in source and source.get("span_id") is None else "normalized"
    parent_kind = "accepted" if "parent_span_id" in source and source.get("parent_span_id") is None else "normalized"
    _put(state, record, "span_id", None, span_kind)
    _put(state, record, "parent_span_id", None, parent_kind)
    seen.add("span_id")
    seen.add("parent_span_id")
    coverage = _take(source, seen, "coverage_note")
    if coverage["present"] and coverage["value"] in COVERAGE:
        _put(state, record, "coverage_note", coverage["value"], "accepted")
    elif coverage["present"] and coverage["value"] is not None:
        _reject_field(state, "coverage_note")
        if _string_secret(coverage["value"]):
            _mark_privacy(state)
    declared_calls = _take(source, seen, "call_count")
    if declared_calls["present"] and declared_calls["value"] is not None:
        number = _non_negative_int(declared_calls["value"])
        if number is None:
            _reject_field(state, "call_count")
        else:
            _put(state, record, "call_count", number, "accepted")
    declared_drops = _take(source, seen, "dropped_count")
    if declared_drops["present"] and declared_drops["value"] is not None:
        number = _non_negative_int(declared_drops["value"])
        if number is None:
            _reject_field(state, "dropped_count")
        else:
            _put(state, record, "dropped_count", number, "accepted")
    calls = _take(source, seen, "calls")
    call_count = None
    if calls["present"] and isinstance(calls["value"], list):
        call_count = len(calls["value"])
        if call_count > bounds["calls_max"]:
            _drop_record(state, "INPUT_BOUND")
    if call_count is not None and not state.drop_record:
        _put(state, record, "call_count", call_count, "normalized")
    requested = source["evidence_origin"] if "evidence_origin" in source else None
    seen.add("evidence_origin")
    _apply_origin(state, record, requested, who["producer"], who["version"], False)
    _sweep_leftovers(source, seen, state)
    return {
        "state": state,
        "record": None if state.drop_record else record,
        "calls": calls["value"] if calls["present"] else None,
    }


def _build_derived(source):
    state = State()
    seen = set()
    record = {}
    _apply_schema(state, record, source, seen, "derived_diagnostic")
    _put(
        state,
        record,
        "evidence_origin",
        "DERIVED_DIAGNOSTIC",
        "accepted" if source.get("evidence_origin") == "DERIVED_DIAGNOSTIC" else "normalized",
    )
    seen.add("evidence_origin")
    state.reader_origin = "DERIVED_DIAGNOSTIC"
    state.provenance = "NOT_APPLICABLE"
    for key, limit in (("subject_event_id", 160), ("subject_run_id", 80)):
        item = _take(source, seen, key)
        if not item["present"] or item["value"] is None:
            continue
        token = _id_token(item["value"], limit)
        if isinstance(token, str):
            _put(state, record, key, token, "accepted")
        else:
            _reject_field(state, key)
            if isinstance(token, dict) and token.get("prohibited"):
                _mark_privacy(state)
    outcome = _take(source, seen, "application_outcome_label")
    if outcome["present"]:
        if outcome["value"] in OUTCOME_LABELS:
            _put(state, record, "application_outcome_label", outcome["value"], "accepted")
        else:
            _reject_field(state, "application_outcome_label")
            if _string_secret(outcome["value"]):
                _mark_privacy(state)
    phrase = _take(source, seen, "provider_response_phrase")
    if phrase["present"]:
        if phrase["value"] in PROVIDER_PHRASES:
            _put(state, record, "provider_response_phrase", phrase["value"], "accepted")
        else:
            _reject_field(state, "provider_response_phrase")
            if _string_secret(phrase["value"]):
                _mark_privacy(state)
    nxt = _take(source, seen, "next_action_category")
    if nxt["present"] and nxt["value"] in NEXT_ACTION:
        _put(state, record, "next_action_category", nxt["value"], "accepted")
    elif nxt["present"]:
        _reject_field(state, "next_action_category")
    location = _take(source, seen, "issue_location")
    if location["present"] and location["value"] in enums["issue_location"]:
        _put(state, record, "issue_location", location["value"], "accepted")
    elif location["present"]:
        _reject_field(state, "issue_location")
        if location["value"] == "Provider fault" or _string_secret(location["value"]):
            _mark_privacy(state)
    _sweep_leftovers(source, seen, state)
    return {"state": state, "record": None if state.drop_record else record}


def _build_annotation(source):
    state = State()
    seen = set()
    record = {}
    _apply_schema(state, record, source, seen, "annotation")
    if "evidence_origin" in source:
        seen.add("evidence_origin")
        _strip_key(state, "evidence_origin")
        _add_reason(state, "ANNOTATION_ORIGIN_REFUSED")
        _add_disposition(state, "REPLACE_WITH_SAFE_CATEGORY")
        if source.get("evidence_origin") == "LOCAL_OBSERVATION":
            state.reader_origin = "LEGACY_UNMARKED"
    role = _take(source, seen, "annotation_role")
    if role["present"] and role["value"] == "CUSTOMER_ANNOTATION":
        _put(state, record, "annotation_role", "CUSTOMER_ANNOTATION", "accepted")
    else:
        _put(state, record, "annotation_role", "CUSTOMER_ANNOTATION", "normalized")
    for key in ("annotation_id", "subject_run_id"):
        item = _take(source, seen, key)
        if not item["present"]:
            continue
        token = _id_token(item["value"], 80)
        if isinstance(token, str):
            _put(state, record, key, token, "accepted")
        else:
            _reject_field(state, key)
            if isinstance(token, dict) and token.get("prohibited"):
                _mark_privacy(state)
    created = _take(source, seen, "created_at")
    if created["present"]:
        stamp = _canonical_time(created["value"])
        if not stamp:
            _reject_field(state, "created_at")
        else:
            _put(state, record, "created_at", stamp["value"], "normalized" if stamp["changed"] else "accepted")
    text = _take(source, seen, "text")
    if text["present"]:
        scanned = _consume_string_field(text["value"])
        too_long = isinstance(text["value"], str) and len(text["value"]) > bounds["annotation_text_max_chars"]
        if scanned.get("prohibited") or too_long or scanned.get("bad"):
            _reject_field(state, "text")
            _mark_privacy(state)
        else:
            _put(state, record, "text", scanned["value"], "accepted")
    _sweep_leftovers(source, seen, state)
    return {"state": state, "record": None if state.drop_record else record}


def _value_enum(name, value):
    if name == "integrity_state" and value in enums["integrity_state"]:
        return {"value": value, "changed": False}
    if name == "migration_state" and value in enums["migration_state"]:
        return {"value": value, "changed": False}
    if name == "telemetry_last_result" and value in enums["telemetry_last_result"]:
        return {"value": value, "changed": False}
    if name == "last_successful_write_at":
        stamp = _canonical_time(value)
        if stamp:
            return {"value": stamp["value"], "changed": stamp["changed"]}
    number = _non_negative_int(value)
    if number is not None and name not in ("integrity_state", "migration_state", "telemetry_last_result"):
        return {"value": number, "changed": False}
    return None


def _build_health(source):
    state = State()
    seen = set()
    record = {}
    _apply_schema(state, record, source, seen, "product_health")
    _put(
        state,
        record,
        "evidence_origin",
        "PRODUCT_HEALTH",
        "accepted" if source.get("evidence_origin") == "PRODUCT_HEALTH" else "normalized",
    )
    seen.add("evidence_origin")
    state.reader_origin = "PRODUCT_HEALTH"
    name = _take(source, seen, "name")
    if name["present"] and name["value"] in HEALTH_NAMES:
        _put(state, record, "name", name["value"], "accepted")
    else:
        _drop_record(state, "RECORD_TYPE_REJECTED")
        _reject_field(state, "name")
    value = _take(source, seen, "value")
    if value["present"] and record.get("name"):
        enum_value = _value_enum(record["name"], value["value"])
        if enum_value is None:
            _reject_field(state, "value")
            if _string_secret(value["value"]):
                _mark_privacy(state)
        else:
            _put(state, record, "value", enum_value["value"], "normalized" if enum_value["changed"] else "accepted")
    observed = _take(source, seen, "observed_at")
    if observed["present"]:
        stamp = _canonical_time(observed["value"])
        if not stamp:
            _reject_field(state, "observed_at")
        else:
            _put(state, record, "observed_at", stamp["value"], "normalized" if stamp["changed"] else "accepted")
    detail = _take(source, seen, "detail_code")
    if detail["present"] and detail["value"] is not None:
        if isinstance(detail["value"], str) and _TOKEN64.match(detail["value"]):
            _put(state, record, "detail_code", detail["value"], "accepted")
        else:
            _reject_field(state, "detail_code")
            _mark_privacy(state)
    _sweep_leftovers(source, seen, state)
    return {"state": state, "record": None if state.drop_record else record}


def _build_quarantine(source):
    state = State()
    seen = set()
    record = {}
    _apply_schema(state, record, source, seen, "import_quarantine")
    requested = source.get("evidence_origin")
    seen.add("evidence_origin")
    _put(state, record, "evidence_origin", "IMPORTED", "accepted" if requested == "IMPORTED" else "normalized")
    if requested and requested != "IMPORTED":
        _add_reason(state, "ORIGIN_NOT_PROMOTED")
        _add_disposition(state, "REPLACE_WITH_SAFE_CATEGORY")
    state.reader_origin = "IMPORTED"
    state.provenance = "INSUFFICIENT"
    original = _take(source, seen, "original_evidence_origin")
    if original["present"] and original["value"] in ORIGINAL_ORIGIN:
        _put(state, record, "original_evidence_origin", original["value"], "accepted")
    else:
        _put(state, record, "original_evidence_origin", "LEGACY_UNMARKED", "normalized")
    label = _take(source, seen, "source_label")
    if label["present"]:
        text = label["value"]
        clean = (
            isinstance(text, str)
            and len(text) <= bounds["source_label_max_chars"]
            and not privacy.has_username_path(text)
            and not privacy.contains_prohibited(text)
            and "\\" not in text
        )
        if clean:
            _put(state, record, "source_label", text, "accepted")
        else:
            _reject_field(state, "source_label")
            _mark_privacy(state)
    digest = _take(source, seen, "content_sha256")
    if digest["present"] and digest["value"] is not None:
        if isinstance(digest["value"], str) and _SHA.match(digest["value"]):
            lower = digest["value"].lower()
            _put(state, record, "content_sha256", lower, "accepted" if lower == digest["value"] else "normalized")
        else:
            _reject_field(state, "content_sha256")
            if _string_secret(digest["value"]):
                _mark_privacy(state)
    seen_status = _take(source, seen, "schema_status_seen")
    if seen_status["present"] and isinstance(seen_status["value"], str) and _SEEN_STATUS.match(seen_status["value"]):
        _put(state, record, "schema_status_seen", seen_status["value"], "accepted")
    elif seen_status["present"]:
        _reject_field(state, "schema_status_seen")
    imported_at = _take(source, seen, "imported_at")
    if imported_at["present"]:
        stamp = _canonical_time(imported_at["value"])
        if not stamp:
            _reject_field(state, "imported_at")
        else:
            _put(state, record, "imported_at", stamp["value"], "normalized" if stamp["changed"] else "accepted")
    accepted = _take(source, seen, "accepted")
    if accepted["present"] and isinstance(accepted["value"], bool):
        _put(state, record, "accepted", accepted["value"], "accepted")
    else:
        _put(state, record, "accepted", False, "normalized")
    reason = _take(source, seen, "reason_code")
    if reason["present"] and isinstance(reason["value"], str) and _TOKEN64.match(reason["value"]):
        _put(state, record, "reason_code", reason["value"], "accepted")
    elif reason["present"] and reason["value"] is not None:
        _reject_field(state, "reason_code")
        if _string_secret(reason["value"]):
            _mark_privacy(state)
    _sweep_leftovers(source, seen, state)
    return {"state": state, "record": None if state.drop_record else record}


def _source_shape(source):
    if not isinstance(source, dict):
        return "unknown"
    if source.get("vantio_run_log") == "1" and isinstance(source.get("calls"), list):
        if source.get("runtime") == "python" or source.get("workflow") == "sight_loop":
            return "python_run_log"
        return "node_run_log"
    if isinstance(source.get("record_type"), str):
        return "contract_record"
    if "hostname" in source:
        return "legacy_call"
    return "unknown"


def _legacy_call_to_contract(call):
    out = {"record_type": "observation_event"}
    mapping = {
        "hostname": "destination_host",
        "method": "method",
        "path": "path",
        "scheme": "scheme",
        "request_bytes": "request_bytes",
        "status": "http_status",
        "content_type": "content_type",
        "duration_ms": "duration_ms",
        "action": "action",
        "ts": "started_at",
        "error_class": "error_class",
        "failure_kind": "failure_kind",
        "mediation": "mediation",
        "opticsStatus": "optics_status",
        "applicationStatus": "application_status",
    }
    if isinstance(call, dict):
        for src, dst in mapping.items():
            if src in call and call[src] is not None:
                out[dst] = call[src]
        if "bytes" in call:
            out["bytes"] = call["bytes"]
        for key in call.keys():
            if key == "bytes" or key in mapping:
                continue
            out[key] = call[key]
    return out


def _legacy_envelope_to_contract(source):
    out = {"record_type": "run_envelope"}
    if isinstance(source.get("trace_id"), str):
        out["run_id"] = source["trace_id"]
    if "pid" in source:
        out["process_id"] = source["pid"]
    if "ppid" in source:
        out["parent_process_id"] = source["ppid"]
    if isinstance(source.get("node_version"), str):
        out["runtime"] = "node"
        out["runtime_version"] = source["node_version"]
    if source.get("runtime") in ("python", "node"):
        out["runtime"] = source["runtime"]
    if isinstance(source.get("platform"), str):
        out["platform"] = source["platform"]
    if isinstance(source.get("arch"), str):
        out["arch"] = source["arch"]
    if isinstance(source.get("started_at"), str):
        out["started_at"] = source["started_at"]
    if isinstance(source.get("generated_at"), str):
        out["ended_at"] = source["generated_at"]
    if "duration_ms" in source:
        out["duration_ms"] = source["duration_ms"]
    if isinstance(source.get("cli_version"), str):
        out["cli_or_sdk_version"] = source["cli_version"]
    for key in ("schema_status", "schema_version", "evidence_origin", "producer", "session_id", "session_id_basis"):
        if key in source:
            out[key] = source[key]
    skip = {"pid", "ppid", "node_version", "generated_at", "cli_version"}
    for key in source.keys():
        if key in ("calls", "trace_id", "vantio_run_log"):
            continue
        mapped = "process_id" if key == "pid" else key
        if mapped in out:
            continue
        if key in skip:
            continue
        out[key] = source[key]
    return out


def _finalize(state, record, events, application_result, compatibility):
    disposition = _highest(DISPOSITION_RANK, state.dispositions, "ACCEPT")
    reason = _highest(REASON_RANK, state.reasons, "OK")
    if state.drop_record and state.optics_internal:
        location = "OPTICS"
    elif record is not None and "issue_location" in record:
        location = record["issue_location"]
    else:
        location = _issue_location(state)
    health = {
        "events_rejected": state.health["events_rejected"],
        "redaction_failures": state.health["redaction_failures"],
        "rejected_context": state.health["rejected_context"],
        "session_id_rejected": state.health["session_id_rejected"],
    }
    emitted = record is not None
    return {
        "schema_status": "unstable-pre-1.0",
        "schema_version": 0,
        "disposition": disposition,
        "reason_code": reason,
        "remediation_code": enums["remediation_by_reason"].get(reason, "VALIDATOR_INTERNAL"),
        "reader_origin_label": state.reader_origin,
        "issue_location": location,
        "issue_location_label": ISSUE_LABELS.get(location, "Unknown"),
        "completeness_impact": _completeness_list(state),
        "health_impact": health,
        "optics_health_impact": _health_label(health),
        "fields": {
            "accepted": _sorted(state.accepted),
            "normalized": _sorted(state.normalized),
            "rejected": _sorted(state.rejected),
            "stripped": _sorted(state.stripped),
        },
        "record": record if emitted else None,
        "events": events,
        "record_emitted": emitted,
        "diagnostics": {
            "destination_class": state.destination_class,
            "destination_ip_class": state.destination_ip_class,
            "privacy_event": "REDACTION_DROP" if state.privacy else None,
            "provenance": state.provenance,
            "scope_complete": False,
            "trace_basis_meaning": state.trace_meaning,
        },
        "completeness_inputs": {
            "accept_reject": "ACCEPT" if emitted else "REJECT",
            "drop_state": "DROPS_IN_SCOPE"
            if "EVENT_DROPPED" in state.completeness or "REDACTION_DROP" in state.completeness
            else "NONE",
            "evidence_origin_label": state.reader_origin,
            "integrity_state": "UNKNOWN",
            "interrupted": state.interrupted,
            "privacy_invariant": "VIOLATED" if state.privacy else "HELD",
            "sampling": "UNSAMPLED",
            "scope_complete": False,
            "stripped_fields": _sorted(state.stripped),
            "validation_result": "EMITTED" if emitted else "REJECTED",
        },
        "compatibility": compatibility,
        "application_result": application_result,
    }


def _empty_compatibility(shape, legacy_marker, legacy_version):
    return {
        "legacy_marker": legacy_marker,
        "legacy_schema_version": legacy_version,
        "live_writer_modified": False,
        "source_shape": shape,
    }


def _terminal(reason, application_result, shape):
    state = State()
    _drop_record(state, reason)
    if reason in (
        "MALFORMED_UTF8",
        "HOSTILE_INPUT",
        "CYCLE_REJECTED",
        "EXCESSIVE_NESTING",
        "INPUT_BOUND",
        "VALIDATOR_FAULT",
        "MALFORMED_JSON",
    ):
        state.optics_internal = True
    state.provenance = "NOT_APPLICABLE"
    return _finalize(state, None, [], application_result, _empty_compatibility(shape or "unavailable", False, None))


def _merge_state(parent, child):
    parent.dispositions.update(child.dispositions)
    parent.reasons.update(child.reasons)
    parent.completeness.update(child.completeness)
    parent.health["events_rejected"] += child.health["events_rejected"]
    parent.health["redaction_failures"] += child.health["redaction_failures"]
    parent.health["rejected_context"] += child.health["rejected_context"]
    parent.health["session_id_rejected"] += child.health["session_id_rejected"]
    if child.privacy:
        parent.privacy = True
    if not parent.reader_origin and child.reader_origin:
        parent.reader_origin = child.reader_origin


def _validate_plain(source, application_result):
    shape = _source_shape(source)
    if shape in ("node_run_log", "python_run_log"):
        mapped = _legacy_envelope_to_contract(source)
        built = _build_envelope(mapped)
        events = []
        dropped = 0
        calls = source["calls"] if isinstance(source.get("calls"), list) else []
        if len(calls) > bounds["calls_max"]:
            _drop_record(built["state"], "INPUT_BOUND")
        else:
            for call in calls:
                call_input = _legacy_call_to_contract(call if isinstance(call, dict) else {})
                child = _build_observation(call_input)
                if not child["record"]:
                    dropped += 1
                events.append(
                    _finalize(
                        child["state"],
                        child["record"],
                        [],
                        None,
                        _empty_compatibility("legacy_call", False, None),
                    )
                )
                _merge_state(built["state"], child["state"])
        if built["record"] is not None and not built["state"].drop_record:
            _put(built["state"], built["record"], "call_count", len(calls), "normalized")
            _put(built["state"], built["record"], "dropped_count", dropped, "normalized")
        legacy_version = source["schema_version"] if _is_integer(source.get("schema_version")) else None
        return _finalize(
            built["state"],
            None if built["state"].drop_record else built["record"],
            events,
            application_result,
            _empty_compatibility(shape, True, legacy_version),
        )
    if shape == "legacy_call":
        child = _build_observation(_legacy_call_to_contract(source))
        return _finalize(child["state"], child["record"], [], application_result, _empty_compatibility(shape, False, None))
    record_type = source.get("record_type") if "record_type" in source else None
    if record_type == "observation_event" or record_type is None:
        if record_type is None and shape == "unknown":
            state = State()
            _drop_record(state, "RECORD_TYPE_REJECTED")
            _sweep_leftovers(source, set(), state)
            return _finalize(state, None, [], application_result, _empty_compatibility(shape, False, None))
        cloned = dict(source)
        if record_type is None:
            cloned["record_type"] = "observation_event"
        built = _build_observation(cloned)
    elif record_type == "run_envelope":
        built = _build_envelope(source)
    elif record_type == "derived_diagnostic":
        built = _build_derived(source)
    elif record_type == "annotation":
        built = _build_annotation(source)
    elif record_type == "product_health":
        built = _build_health(source)
    elif record_type == "import_quarantine":
        built = _build_quarantine(source)
    else:
        state = State()
        _drop_record(state, "RECORD_TYPE_REJECTED")
        return _finalize(state, None, [], application_result, _empty_compatibility(shape, False, None))
    legacy_version = source["schema_version"] if _is_integer(source.get("schema_version")) else None
    marker = source.get("vantio_run_log") == "1"
    return _finalize(
        built["state"],
        built["record"],
        [],
        application_result,
        _empty_compatibility(shape, marker, legacy_version if marker else None),
    )


def _application_of(options):
    if not isinstance(options, dict):
        return None
    if "applicationResult" in options:
        return options["applicationResult"]
    return None


def validate_evidence(value, options=None):
    application_result = _application_of(options)
    try:
        if isinstance(options, dict) and options.get("injectFault") is True:
            raise RuntimeError("injected")
        if isinstance(value, str):
            if len(value) > bounds["max_input_chars"]:
                return _terminal("INPUT_BOUND", application_result, "bytes")
            if privacy.contains_prohibited(value) and not value.startswith("{") and not value.startswith("["):
                state = State()
                _mark_privacy(state)
                _drop_record(state, "REDACTION_DROP")
                return _finalize(state, None, [], application_result, _empty_compatibility("unknown", False, None))
            if value.startswith("{") or value.startswith("["):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    return _terminal("MALFORMED_JSON", application_result, "bytes")
            else:
                return _terminal("RECORD_TYPE_REJECTED", application_result, "unknown")
        if not isinstance(value, (dict, list)):
            return _terminal("RECORD_TYPE_REJECTED", application_result, "unknown")
        copied = walk.plain_copy(value)
        if not copied["ok"]:
            return _terminal(copied["reason"], application_result, "unknown")
        if isinstance(copied["value"], list):
            state = State()
            _mark_privacy(state)
            _drop_record(state, "PROMPT_COMPLETION_EXCLUDED")
            return _finalize(state, None, [], application_result, _empty_compatibility("unknown", False, None))
        return _validate_plain(copied["value"], application_result)
    except Exception:
        return _terminal("VALIDATOR_FAULT", application_result, "unavailable")


def validate_bytes(buffer, options=None):
    application_result = _application_of(options)
    try:
        if isinstance(options, dict) and options.get("injectFault") is True:
            raise RuntimeError("injected")
        if isinstance(buffer, str):
            raw = buffer.encode("utf-8")
        elif isinstance(buffer, bytearray):
            raw = bytes(buffer)
        elif isinstance(buffer, bytes):
            raw = buffer
        else:
            return _terminal("HOSTILE_INPUT", application_result, "bytes")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return _terminal("MALFORMED_UTF8", application_result, "bytes")
        if len(text) > bounds["max_input_chars"]:
            return _terminal("INPUT_BOUND", application_result, "bytes")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return _terminal("MALFORMED_JSON", application_result, "bytes")
        return validate_evidence(parsed, options)
    except Exception:
        return _terminal("VALIDATOR_FAULT", application_result, "bytes")


def canonical_json(value):
    return canonical.canonical_json(value)


contract_meta = meta
