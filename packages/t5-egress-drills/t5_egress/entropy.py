"""Shannon entropy in userspace. The skb program does not run this."""

from __future__ import annotations

import math


def shannon_bits(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    total = len(data)
    entropy = 0.0
    for count in counts:
        if count:
            prob = count / total
            entropy -= prob * math.log2(prob)
    return entropy
