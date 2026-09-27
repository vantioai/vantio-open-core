"""Bounded copy. Plain dict, list, and tuple values only."""

import json
import types
from pathlib import Path

import privacy

_BOUNDS = json.loads(
    (Path(__file__).resolve().parent.parent / "contract" / "normalization.json").read_text(encoding="utf-8")
)["bounds"]

OVERSIZE = "OVERSIZE"
MALFORMED_TEXT = "MALFORMED_TEXT"
bounds = _BOUNDS


class BoundMarker(dict):
    def __init__(self, kind, scan=None):
        payload = {"__optics_bound": kind}
        if scan:
            payload["matched"] = scan.get("matched") is True
            payload["boundary"] = scan.get("boundary") is True and scan.get("matched") is not True
        super().__init__(payload)


def is_bound(value):
    return isinstance(value, dict) and value.get("__optics_bound") in (OVERSIZE, MALFORMED_TEXT)


def _lone_surrogate(text):
    i = 0
    while i < len(text):
        code = ord(text[i])
        if 0xD800 <= code <= 0xDBFF:
            if i + 1 >= len(text):
                return True
            nxt = ord(text[i + 1])
            if not (0xDC00 <= nxt <= 0xDFFF):
                return True
            i += 2
            continue
        if 0xDC00 <= code <= 0xDFFF:
            return True
        i += 1
    return False


def plain_copy(value):
    return _copy(value, {"nodes": 0, "depth": 0, "seen": set()})


_ACCESSOR_HOOKS = {
    "__getattribute__",
    "__getattr__",
    "__getitem__",
    "__iter__",
    "__str__",
    "__repr__",
    "keys",
    "items",
    "values",
}


def _exotic_reason(value):
    cls = type(value)
    for klass in cls.__mro__:
        if klass in (dict, list, tuple, object):
            continue
        for name, item in klass.__dict__.items():
            if isinstance(item, property):
                return "ACCESSOR_PROPERTY_FORBIDDEN"
            if name in _ACCESSOR_HOOKS:
                return "ACCESSOR_PROPERTY_FORBIDDEN"
    return "UNSUPPORTED_COMPLEX_VALUE"


def _enter(value, state):
    ident = id(value)
    if ident in state["seen"]:
        return {"ok": False, "reason": "CYCLE_REJECTED"}
    if state["depth"] >= _BOUNDS["max_depth"]:
        return {"ok": False, "reason": "EXCESSIVE_NESTING"}
    if state["nodes"] >= _BOUNDS["max_nodes"]:
        return {"ok": False, "reason": "INPUT_BOUND"}
    state["seen"].add(ident)
    state["nodes"] += 1
    state["depth"] += 1
    return None


def _leave(value, state):
    state["depth"] -= 1
    state["seen"].discard(id(value))


def _copy(value, state):
    if value is None:
        return {"ok": True, "value": None}
    if type(value) is str:
        if privacy.utf8_bytes(value) > _BOUNDS["max_string_chars"]:
            return {"ok": True, "value": BoundMarker(OVERSIZE, privacy.scan_bounded_prefix(value))}
        if _lone_surrogate(value):
            return {"ok": True, "value": BoundMarker(MALFORMED_TEXT)}
        return {"ok": True, "value": value}
    if type(value) is bool:
        return {"ok": True, "value": value}
    if type(value) is int:
        return {"ok": True, "value": value}
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            return {"ok": False, "reason": "HOSTILE_INPUT"}
        if value.is_integer() and abs(value) <= _BOUNDS["safe_integer_max"]:
            return {"ok": True, "value": int(value)}
        return {"ok": True, "value": value}
    if type(value) is bytes or type(value) is bytearray or type(value) is memoryview:
        return {"ok": False, "reason": "UNSUPPORTED_COMPLEX_VALUE", "disposition": "REJECT_FIELD"}
    if type(value) is list or type(value) is tuple:
        blocked = _enter(value, state)
        if blocked:
            return blocked
        try:
            length = list.__len__(value) if type(value) is list else tuple.__len__(value)
            if length > _BOUNDS["max_array"]:
                return {"ok": False, "reason": "INPUT_BOUND"}
            out = []
            for index in range(length):
                item = list.__getitem__(value, index) if type(value) is list else tuple.__getitem__(value, index)
                child = _copy(item, state)
                if not child["ok"]:
                    return child
                out.append(child["value"])
            return {"ok": True, "value": out}
        finally:
            _leave(value, state)
    if type(value) is dict:
        blocked = _enter(value, state)
        if blocked:
            return blocked
        try:
            keys = list(dict.keys(value))
            if len(keys) > _BOUNDS["max_keys"]:
                return {"ok": False, "reason": "INPUT_BOUND"}
            forms = set()
            for key in keys:
                if type(key) is not str:
                    return {"ok": False, "reason": "INVALID_FORMAT"}
                if privacy.utf8_bytes(key) > _BOUNDS["field_name_max_bytes"]:
                    return {"ok": False, "reason": "MAX_SIZE_EXCEEDED"}
                form = privacy.comparison_form(key)
                if form in forms:
                    return {"ok": False, "reason": "DUPLICATE_CANONICAL_FIELD"}
                forms.add(form)
            out = {}
            for key in keys:
                child = _copy(dict.__getitem__(value, key), state)
                if not child["ok"]:
                    return child
                out[key] = child["value"]
            return {"ok": True, "value": out}
        finally:
            _leave(value, state)
    if type(value) in (
        types.FunctionType,
        types.LambdaType,
        types.MethodType,
        types.BuiltinFunctionType,
        types.BuiltinMethodType,
    ):
        return {"ok": False, "reason": "UNSUPPORTED_COMPLEX_VALUE", "disposition": "REJECT_FIELD"}
    exotic = _exotic_reason(value)
    if exotic == "ACCESSOR_PROPERTY_FORBIDDEN":
        return {"ok": False, "reason": exotic}
    if callable(value):
        return {"ok": False, "reason": "UNSUPPORTED_COMPLEX_VALUE", "disposition": "REJECT_FIELD"}
    return {"ok": False, "reason": exotic}
