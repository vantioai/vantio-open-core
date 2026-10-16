"""Secure Boot and kernel lockdown facts for installer preflight.

The bracketed lockdown file is the mode. Secure Boot is the EFI variable
only. This module does not open a TPM and does not read a measured-boot log.
"""

from __future__ import annotations

from pathlib import Path

LOCKDOWN_MODES = ("none", "integrity", "confidentiality")
SECURE_BOOT_NAME = "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
MEASURED_BOOT = "not_checked"
TPM_ATTESTATION = "roadmap"

REFUSAL = {
    "lockdown_confidentiality": (
        "Kernel lockdown is confidentiality. The installer refuses this host. "
        "Measured boot and TPM attestation were not checked."
    ),
    "secure_boot_lockdown_mismatch": (
        "Secure Boot is on and kernel lockdown is none. The installer refuses this pair. "
        "The two facts disagree."
    ),
    "lockdown_unreadable": (
        "Read /sys/kernel/security/lockdown. It must list none, integrity, and "
        "confidentiality with exactly one mode in brackets."
    ),
    "secure_boot_unreadable": (
        "The Secure Boot EFI variable is present but not one byte of 0 or 1 "
        "after the four attribute bytes. The installer does not guess."
    ),
}

CONTINUATION = (
    "Measured boot and TPM attestation are Roadmap. This check did not read them."
)


def parse_lockdown(text: str) -> str:
    """Return the single bracketed mode. The shape matches the stranger-host parser."""
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


def read_secure_boot(root: Path) -> str:
    """Return on, off, absent, or unreadable. Absent means the EFI variable is not there."""
    path = root / "sys/firmware/efi/efivars" / SECURE_BOOT_NAME
    if not path.exists():
        return "absent"
    if not path.is_file():
        return "unreadable"
    try:
        blob = path.read_bytes()
    except OSError:
        return "unreadable"
    if len(blob) != 5:
        return "unreadable"
    value = blob[4]
    if value == 1:
        return "on"
    if value == 0:
        return "off"
    return "unreadable"


def read_lockdown(root: Path) -> tuple[str, str]:
    """Return (raw, mode). Mode is UNREADABLE when the file is missing or not the three-mode line."""
    path = root / "sys/kernel/security/lockdown"
    if not path.is_file():
        return "ABSENT", "UNREADABLE"
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return "ABSENT", "UNREADABLE"
    try:
        return raw[:120], parse_lockdown(raw)
    except ValueError:
        return raw[:120], "UNREADABLE"


def read_facts(root: Path) -> dict[str, str]:
    raw, mode = read_lockdown(root)
    return {
        "lockdown_raw": raw,
        "lockdown_mode": mode,
        "secure_boot": read_secure_boot(root),
        "measured_boot": MEASURED_BOOT,
        "tpm_attestation": TPM_ATTESTATION,
    }


def grade(lockdown_mode: object, secure_boot: object) -> tuple[str, str]:
    """Return PASS or BLOCKED and a reason token.

    Confidentiality is refused for every Secure Boot state, including on.
    Secure Boot on with lockdown none is a mismatch and is refused.
    Secure Boot absent is not a refusal by itself.
    """
    mode = lockdown_mode if isinstance(lockdown_mode, str) else "UNREADABLE"
    boot = secure_boot if isinstance(secure_boot, str) else "unreadable"
    if mode == "confidentiality":
        return "BLOCKED", "lockdown_confidentiality"
    if mode not in {"none", "integrity"}:
        return "BLOCKED", "lockdown_unreadable"
    if boot not in {"on", "off", "absent"}:
        return "BLOCKED", "secure_boot_unreadable"
    if boot == "on" and mode == "none":
        return "BLOCKED", "secure_boot_lockdown_mismatch"
    return "PASS", "continue"


def check_fields(host: dict) -> dict:
    """One preflight row. Missing facts are unreadable, not a pass."""
    result, reason = grade(host.get("lockdown_mode"), host.get("secure_boot"))
    raw = host.get("lockdown_raw")
    observed = {
        "secure_boot": host.get("secure_boot") if isinstance(host.get("secure_boot"), str) else "unreadable",
        "lockdown_mode": host.get("lockdown_mode") if isinstance(host.get("lockdown_mode"), str) else "UNREADABLE",
        "lockdown_raw": raw[:120] if isinstance(raw, str) else "ABSENT",
        "measured_boot": MEASURED_BOOT,
        "tpm_attestation": TPM_ATTESTATION,
        "reason": reason,
    }
    if result != "PASS":
        observed["refusal"] = REFUSAL[reason]
    remediation = REFUSAL.get(reason, CONTINUATION)
    return {
        "id": "PF-KERNEL-LOCKDOWN",
        "title": "Secure Boot and kernel lockdown",
        "result": result,
        "observed": observed,
        "expected": {
            "lockdown_mode": ["none", "integrity"],
            "secure_boot": ["on", "off", "absent"],
            "refused": ["confidentiality", "secure_boot_on_with_lockdown_none"],
            "measured_boot": MEASURED_BOOT,
            "tpm_attestation": TPM_ATTESTATION,
        },
        "remediation": remediation,
    }
