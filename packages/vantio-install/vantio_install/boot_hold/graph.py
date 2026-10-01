"""Dependency checks for the boot-hold units."""

from __future__ import annotations

_RECOVERY = (
    "ssh.service",
    "sshd.service",
    "ssh.socket",
    "systemd-networkd.service",
    "systemd-resolved.service",
    "systemd-networkd-wait-online.service",
    "dhcpcd.service",
    "amazon-ssm-agent.service",
    "snap.amazon-ssm-agent.amazon-ssm-agent.service",
)

_HOST_WIDE = ("ip route", "route del", "blackhole", "-P OUTPUT DROP", "-P FORWARD DROP", "0.0.0.0/0", "::/0")


def parse_unit(text: str) -> dict[str, dict[str, list[str]]]:
    sections: dict[str, dict[str, list[str]]] = {}
    section: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            sections.setdefault(section, {})
            continue
        if section is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        bucket = sections[section].setdefault(key.strip(), [])
        bucket.extend(value.split())
    return sections


def _deps(parsed: dict[str, dict[str, list[str]]], key: str) -> list[str]:
    found: list[str] = []
    for section in parsed.values():
        found.extend(section.get(key, []))
    return found


def graph_errors(units: dict[str, str], *, ordering: bool = True, hold: bool = True) -> list[str]:
    errors: list[str] = []
    for name, text in units.items():
        for needle in _HOST_WIDE:
            if needle in text:
                errors.append(f"{name} contains {needle}")
    hold_text = units.get("etc/systemd/system/vantio-boot-hold.service", "")
    hold_parsed = parse_unit(hold_text)
    before = set(_deps(hold_parsed, "Before"))
    if hold and "docker.service" not in before:
        errors.append("boot hold is not Before=docker.service")
    if hold and "containerd.service" not in before:
        errors.append("boot hold is not Before=containerd.service")
    for key in ("Before", "Requires", "Wants", "After"):
        for dep in _deps(hold_parsed, key):
            if dep in _RECOVERY:
                errors.append(f"boot hold {key} includes {dep}")
    loader = parse_unit(units.get("etc/systemd/system/vantio-pe-loader.service", ""))
    if "vantio-boot-hold.service" not in _deps(loader, "After"):
        errors.append("Phantom Engine loader is not After=vantio-boot-hold.service")
    if "vantio-pe-enforce-ready.service" not in _deps(loader, "Before"):
        errors.append("Phantom Engine loader is not Before=vantio-pe-enforce-ready.service")
    ready = parse_unit(units.get("etc/systemd/system/vantio-pe-enforce-ready.service", ""))
    if "vantio-pe-loader.service" not in _deps(ready, "After"):
        errors.append("enforce-ready is not After= the loader")
    if "vantio-pe-loader.service" not in _deps(ready, "Requires"):
        errors.append("enforce-ready does not Requires= the loader")
    if "--require-enforce-ready" not in units.get("etc/systemd/system/vantio-pe-enforce-ready.service", ""):
        errors.append("enforce-ready unit does not require the enforce-ready probe")
    docker_unit = units.get("etc/systemd/system/vantio-enrolled-docker@.service", "")
    docker_parsed = parse_unit(docker_unit)
    if ordering and "vantio-pe-enforce-ready.service" not in _deps(docker_parsed, "Requires"):
        errors.append("enrolled docker unit does not Requires= enforce-ready")
    if not ordering and "vantio-pe-enforce-ready.service" in _deps(docker_parsed, "Requires"):
        errors.append("ordering-off docker unit still Requires= enforce-ready")
    if hold and "vantio-boot-hold.service" not in _deps(docker_parsed, "Requires"):
        errors.append("enrolled docker unit does not Requires= the boot hold")
    docker_dropin = units.get("etc/systemd/system/docker.service.d/vantio-boot-hold.conf", "")
    dropin_parsed = parse_unit(docker_dropin)
    if "vantio-boot-hold.service" not in _deps(dropin_parsed, "After"):
        errors.append("docker drop-in is not After= the boot hold")
    if _deps(dropin_parsed, "Requires"):
        errors.append("docker.service must not Requires= the boot hold")
    if SLICE_MISSING(units.get("etc/systemd/system/vantio-enrolled.slice", "")):
        errors.append("enrolled slice unit is missing")
    return errors


def SLICE_MISSING(text: str) -> bool:
    return "[Slice]" not in text
