"""Protected-path hold for enrolled workloads.

Systemd units get InaccessiblePaths while the hold is up. Docker and systemd
both name the AppArmor profile vantio-boot-hold. Boot loads the deny profile.
Release replaces that same profile with an allow profile so a later start can
see the paths, and Phantom Engine policy is the control after enforce-ready.
"""

from __future__ import annotations

from vantio_install.boot_hold.constants import APPARMOR_PROFILE


def deny_profile(paths: list[str]) -> str:
    lines = [
        f"profile {APPARMOR_PROFILE} flags=(attach_disconnected) {{",
        "  file,",
        "  network,",
        "  capability,",
        "  signal,",
        "  unix,",
    ]
    for path in paths:
        lines.append(f"  deny {path} rwmlkx,")
        lines.append(f"  deny {path}/** rwmlkx,")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def allow_profile() -> str:
    return (
        f"profile {APPARMOR_PROFILE} flags=(attach_disconnected) {{\n"
        "  file,\n"
        "  network,\n"
        "  capability,\n"
        "  signal,\n"
        "  unix,\n"
        "}\n"
    )


def dropin_text(
    *,
    hold: bool,
    ordering: bool,
    protected_paths: list[str],
    apparmor: bool,
    hide_paths: bool,
    start_gate: bool = True,
) -> str:
    after: list[str] = []
    requires: list[str] = []
    if start_gate and hold:
        after.append("vantio-boot-hold.service")
        requires.append("vantio-boot-hold.service")
    if start_gate and ordering:
        after.append("vantio-pe-enforce-ready.service")
        requires.append("vantio-pe-enforce-ready.service")
    lines = ["[Unit]", "Description=Vantio enrolled workload gate"]
    if after:
        lines.append("After=" + " ".join(after))
    if requires:
        lines.append("Requires=" + " ".join(requires))
    lines.extend(["", "[Service]", "Slice=vantio-enrolled.slice"])
    if hide_paths:
        for path in protected_paths:
            lines.append(f"InaccessiblePaths={path}")
        if apparmor:
            lines.append(f"AppArmorProfile={APPARMOR_PROFILE}")
    lines.append("")
    return "\n".join(lines)
