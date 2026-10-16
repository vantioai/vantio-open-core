"""DNS name compare. Suffix rule matches hostListed, with the T5 deltas."""

from __future__ import annotations

_ASCII_SPACE = " \t\r\n\f\v"
_LABEL_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


class NameRejected(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


def _fold(text: str) -> str:
    return "".join(ch.lower() if "A" <= ch <= "Z" else ch for ch in text)


def prepare_listed_name(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str) or raw == "":
        raise NameRejected("policy_malformed")
    text = raw.strip(_ASCII_SPACE)
    if any(ch in _ASCII_SPACE or ord(ch) > 127 for ch in text):
        raise NameRejected("policy_malformed")
    if text.endswith("."):
        text = text[:-1]
    if text == "" or ".." in text or text.startswith(".") or text.endswith("."):
        raise NameRejected("policy_malformed")
    labels = tuple(_fold(text).split("."))
    for label in labels:
        if not label or any(ch not in _LABEL_OK for ch in label) or len(label) > 63:
            raise NameRejected("policy_malformed")
    return labels


def prepare_candidate_name(raw: object) -> tuple[str, ...] | NameRejected:
    if not isinstance(raw, str) or raw == "":
        return NameRejected("dns_label_not_ldh")
    text = raw[:-1] if raw.endswith(".") else raw
    if text == "" or any(ord(ch) > 127 for ch in text):
        return NameRejected("dns_label_not_ldh")
    if ".." in text or text.startswith(".") or text.endswith("."):
        return NameRejected("dns_label_not_ldh")
    labels = tuple(_fold(text).split("."))
    for label in labels:
        if not label or len(label) > 63 or any(ch not in _LABEL_OK for ch in label):
            return NameRejected("dns_label_not_ldh")
    return labels


def longest_match(
    candidate: tuple[str, ...],
    listed: tuple[tuple[str, ...], ...],
) -> tuple[str, ...] | None:
    best: tuple[str, ...] | None = None
    for item in listed:
        exact = candidate == item
        suffix = (
            len(item) >= 2
            and len(item) < len(candidate)
            and candidate[-len(item) :] == item
        )
        if exact or suffix:
            if best is None or len(item) > len(best):
                best = item
    return best
