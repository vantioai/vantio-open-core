"""Canonical JSON for the Unit A neutrality check.

UTF-8, sorted keys, no insignificant whitespace.
Controls use the same short escapes as the Node encoder.
Non-ASCII is left unescaped. Integers outside -9007199254740991
through 9007199254740991 are rejected. This file does not import a Vantio product.
"""

import json
import sys

MAX_DEPTH = 32
MAX_SAFE_INTEGER = 9007199254740991


class CanonicalError(Exception):
    pass


def canonical(value):
    return _stringify(value, 0, set())


def _stringify(value, depth, seen):
    if depth > MAX_DEPTH:
        raise CanonicalError("MAX_DEPTH_EXCEEDED")
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        if value > MAX_SAFE_INTEGER or value < -MAX_SAFE_INTEGER:
            raise CanonicalError("UNSAFE_INTEGER_REJECTED")
        if value == 0:
            return "0"
        return str(value)
    if isinstance(value, float):
        raise CanonicalError("NON_INTEGER_REJECTED")
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, list):
        if id(value) in seen:
            raise CanonicalError("CYCLE_REJECTED")
        seen.add(id(value))
        out = "[" + ",".join(_stringify(item, depth + 1, seen) for item in value) + "]"
        seen.remove(id(value))
        return out
    if isinstance(value, dict):
        if id(value) in seen:
            raise CanonicalError("CYCLE_REJECTED")
        seen.add(id(value))
        parts = []
        for key in sorted(value):
            if not isinstance(key, str):
                raise CanonicalError("UNSUPPORTED_VALUE")
            parts.append(_quote(key) + ":" + _stringify(value[key], depth + 1, seen))
        out = "{" + ",".join(parts) + "}"
        seen.remove(id(value))
        return out
    raise CanonicalError("UNSUPPORTED_VALUE")


def _quote(text):
    out = ['"']
    for char in text:
        code = ord(char)
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
            out.append(char)
    out.append('"')
    return "".join(out)


def main():
    try:
        documents = json.load(sys.stdin)
        for document in documents:
            sys.stdout.write(canonical(document) + "\n")
    except CanonicalError as error:
        sys.stderr.write(str(error) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
