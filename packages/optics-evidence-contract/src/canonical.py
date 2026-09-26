"""Canonical JSON shared with canonical.cjs."""


def canonical_json(value):
    return _stringify(value)


def _stringify(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, list):
        return "[" + ",".join(_stringify(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        return "{" + ",".join(_quote(key) + ":" + _stringify(value[key]) for key in keys) + "}"
    raise TypeError("unsupported canonical value")


def _quote(text):
    out = ['"']
    for ch in text:
        code = ord(ch)
        if code == 0x22:
            out.append('\\"')
        elif code == 0x5C:
            out.append("\\\\")
        elif code == 0x08:
            out.append("\\b")
        elif code == 0x09:
            out.append("\\t")
        elif code == 0x0A:
            out.append("\\n")
        elif code == 0x0C:
            out.append("\\f")
        elif code == 0x0D:
            out.append("\\r")
        elif code < 0x20:
            out.append("\\u" + format(code, "04x"))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)
