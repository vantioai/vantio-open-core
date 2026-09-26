"""Bounded copy. Cycles and throwing getters become terminal reasons."""

import json
from pathlib import Path

_BOUNDS = json.loads(
    (Path(__file__).resolve().parent.parent / "contract" / "normalization.json").read_text(encoding="utf-8")
)["bounds"]

OVERSIZE = "OVERSIZE"
MALFORMED_TEXT = "MALFORMED_TEXT"
bounds = _BOUNDS


class BoundMarker(dict):
    def __init__(self, kind):
        super().__init__(__optics_bound=kind)


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


def _copy(value, state):
    if value is None:
        return {"ok": True, "value": None}
    if isinstance(value, str):
        if len(value) > _BOUNDS["max_string_chars"]:
            return {"ok": True, "value": BoundMarker(OVERSIZE)}
        if _lone_surrogate(value):
            return {"ok": True, "value": BoundMarker(MALFORMED_TEXT)}
        return {"ok": True, "value": value}
    if isinstance(value, bool):
        return {"ok": True, "value": value}
    if isinstance(value, int):
        return {"ok": True, "value": value}
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return {"ok": False, "reason": "HOSTILE_INPUT"}
        if value.is_integer() and abs(value) <= _BOUNDS["safe_integer_max"]:
            return {"ok": True, "value": int(value)}
        return {"ok": True, "value": value}
    if isinstance(value, (bytes, bytearray)):
        return {"ok": False, "reason": "HOSTILE_INPUT"}
    if isinstance(value, list):
        ident = id(value)
        if ident in state["seen"]:
            return {"ok": False, "reason": "CYCLE_REJECTED"}
        if state["depth"] >= _BOUNDS["max_depth"]:
            return {"ok": False, "reason": "EXCESSIVE_NESTING"}
        if state["nodes"] >= _BOUNDS["max_nodes"]:
            return {"ok": False, "reason": "INPUT_BOUND"}
        try:
            length = len(value)
        except Exception:
            return {"ok": False, "reason": "HOSTILE_INPUT"}
        if length > _BOUNDS["max_array"]:
            return {"ok": False, "reason": "INPUT_BOUND"}
        state["seen"].add(ident)
        state["nodes"] += 1
        state["depth"] += 1
        try:
            out = []
            for item in value:
                child = _copy(item, state)
                if not child["ok"]:
                    return child
                out.append(child["value"])
            return {"ok": True, "value": out}
        except Exception:
            return {"ok": False, "reason": "HOSTILE_INPUT"}
        finally:
            state["depth"] -= 1
            state["seen"].discard(ident)
    if isinstance(value, dict):
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
        try:
            try:
                keys = list(value.keys())
            except Exception:
                return {"ok": False, "reason": "HOSTILE_INPUT"}
            if len(keys) > _BOUNDS["max_keys"]:
                return {"ok": False, "reason": "INPUT_BOUND"}
            out = {}
            for key in keys:
                if not isinstance(key, str) or len(key) > 128:
                    return {"ok": False, "reason": "INPUT_BOUND"}
                try:
                    child_value = value[key]
                except Exception:
                    return {"ok": False, "reason": "HOSTILE_INPUT"}
                child = _copy(child_value, state)
                if not child["ok"]:
                    return child
                out[key] = child["value"]
            return {"ok": True, "value": out}
        finally:
            state["depth"] -= 1
            state["seen"].discard(ident)
    return {"ok": False, "reason": "HOSTILE_INPUT"}
