"""Health derivation used by the installer. The independent verifier does not import this module."""

from __future__ import annotations

from vantio_install import constants


def component_template(status: str) -> dict[str, str]:
    return {
        "optics_cli": status,
        "pe_container": status,
        "pe_loader_process": status,
        "bpf_maps_present": status,
        "tc_clsact_iface": status,
        "path_deny": "NOT_ENABLED",
        "enforcement": "NOT_ENABLED",
        "otlp": "NOT_ENABLED",
    }


def derive(snapshot: dict, config: dict, *, limitations: list | None = None) -> dict:
    components = component_template("NOT_TESTED")
    version = snapshot.get("optics_cli_version")
    if version == constants.FROZEN_PINS["optics_cli_version"]:
        components["optics_cli"] = "PASS"
    elif version in (None, "ABSENT"):
        components["optics_cli"] = "NOT_INSTALLED"
    else:
        components["optics_cli"] = "FAIL"

    enforcement = str(config.get("enforcement", "NOT_ENABLED"))
    components["enforcement"] = "NOT_ENABLED" if enforcement == "NOT_ENABLED" else "FAIL"
    path_deny = str(config.get("path_deny", "disabled"))
    components["path_deny"] = "NOT_ENABLED" if path_deny == "disabled" else "FAIL"
    otlp = str(config.get("otlp", "DISABLED"))
    components["otlp"] = "NOT_ENABLED" if otlp == "DISABLED" else "FAIL"

    probes = set(snapshot.get("probe_errors") or [])
    containers = [
        row
        for row in snapshot.get("containers") or []
        if row.get("role") == "phantom_engine"
    ]
    running = [row for row in containers if row.get("status") == "running"]
    if probes.intersection({"container"}):
        components["pe_container"] = "UNKNOWN"
    elif not containers:
        components["pe_container"] = "NOT_INSTALLED"
    elif not running:
        components["pe_container"] = "FAIL"
    else:
        cmd = running[0].get("cmd") or []
        enforced = "--enforce" in cmd or snapshot.get("enforce_flag") is True or running[0].get("enforce") is True
        components["pe_container"] = "FAIL" if enforced else "PASS"

    if "process" in probes:
        components["pe_loader_process"] = "UNKNOWN"
    elif "vantio-loader" in (snapshot.get("processes") or []):
        components["pe_loader_process"] = "PASS"
    elif components["pe_container"] == "NOT_INSTALLED":
        components["pe_loader_process"] = "NOT_INSTALLED"
    else:
        components["pe_loader_process"] = "FAIL"

    if "bpf" in probes:
        components["bpf_maps_present"] = "UNKNOWN"
    elif all(name in (snapshot.get("bpf_pins") or []) for name in constants.BPF_PINS):
        components["bpf_maps_present"] = "PASS"
    elif components["pe_container"] == "NOT_INSTALLED":
        components["bpf_maps_present"] = "NOT_INSTALLED"
    else:
        components["bpf_maps_present"] = "FAIL"

    iface = str(config.get("iface", ""))
    if "tc" in probes:
        components["tc_clsact_iface"] = "UNKNOWN"
    elif iface and iface in (snapshot.get("clsact_ifaces") or []):
        components["tc_clsact_iface"] = "PASS"
    elif components["pe_container"] == "NOT_INSTALLED":
        components["tc_clsact_iface"] = "NOT_INSTALLED"
    else:
        components["tc_clsact_iface"] = "FAIL"

    required = [
        components["optics_cli"],
        components["pe_container"],
        components["pe_loader_process"],
        components["bpf_maps_present"],
        components["tc_clsact_iface"],
    ]
    if any(value == "UNKNOWN" for value in components.values()):
        overall = "UNKNOWN"
    elif any(value == "FAIL" for value in components.values()):
        overall = "FAIL"
    elif any(value in {"NOT_INSTALLED", "NOT_TESTED"} for value in required):
        overall = "FAIL"
    else:
        overall = "PASS"
        if limitations:
            overall = "PASS_WITH_LIMITATIONS"

    return {
        "install_mode": config.get("install_mode", "observe-only"),
        "enforcement": enforcement,
        "components": components,
        "overall": overall,
    }
