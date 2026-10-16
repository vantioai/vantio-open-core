"""Digit-ratio stand-in for a future skb program. Not the enforce decision."""

from __future__ import annotations


def skb_label_signal(label: str) -> bool:
    """True when a bounded 63-step pass sees a long digit-heavy label."""
    sample = label[:63]
    digits = 0
    for index, ch in enumerate(sample):
        if index >= 63:
            break
        if "0" <= ch <= "9":
            digits += 1
    length = len(sample)
    return length >= 20 and digits * 2 > length
