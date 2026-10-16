"""Parsers shared by preflight and the nine-step grade.

BPF is its own comma token or its own lsm= word. A longer token that
contains those letters does not count.
"""

from __future__ import annotations

from constants import AMI_RE, ATTEST_RE, DATED_IMAGE_RE, IMAGE_FAMILY, IMAGE_FAMILY_BARE, LOCKDOWN_MODES


def boot_id_ok(value: object) -> bool:
    return isinstance(value, str) and value == value.strip() and 1 <= len(value) <= 80 and "\n" not in value


def bpf_in_lsm_list(text: str) -> bool:
    return any(part.strip() == "bpf" for part in text.split(","))


def lsm_word(cmdline: str) -> str | None:
    if not isinstance(cmdline, str):
        return None
    for token in cmdline.split():
        if token.startswith("lsm="):
            return token
    return None


def bpf_in_cmdline(cmdline: str) -> bool:
    word = lsm_word(cmdline)
    if word is None:
        return False
    return bpf_in_lsm_list(word.split("=", 1)[1])


def parse_lockdown(text: str) -> str:
    """Return the single bracketed lockdown mode."""
    if not isinstance(text, str):
        raise ValueError("lockdown_unreadable")
    tokens = text.strip().split()
    if len(tokens) != 3:
        raise ValueError("lockdown_unreadable")
    bracketed = [token for token in tokens if token.startswith("[") and token.endswith("]") and len(token) > 2]
    if len(bracketed) != 1:
        raise ValueError("lockdown_unreadable")
    mode = bracketed[0][1:-1]
    names = [token[1:-1] if token.startswith("[") and token.endswith("]") else token for token in tokens]
    if mode not in LOCKDOWN_MODES or set(names) != set(LOCKDOWN_MODES):
        raise ValueError("lockdown_unreadable")
    return mode


def bpffs_mounted(mounts_text: str) -> bool:
    if not isinstance(mounts_text, str):
        return False
    for line in mounts_text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "/sys/fs/bpf" and parts[2] == "bpf":
            return True
    return False


def image_is_exact(name: object, *, source: object) -> bool:
    if not isinstance(name, str) or not isinstance(source, str):
        return False
    if any(char.isspace() for char in name):
        return False
    if name in {IMAGE_FAMILY, IMAGE_FAMILY_BARE}:
        return False
    if AMI_RE.fullmatch(name):
        return True
    if DATED_IMAGE_RE.search(name) and ATTEST_RE.fullmatch(name):
        return True
    if source == "operator-attestation" and ATTEST_RE.fullmatch(name):
        return True
    return False


def exact_int(value: object, expected: int) -> bool:
    return type(value) is int and value == expected


def positive_int(value: object) -> bool:
    return type(value) is int and value > 0
