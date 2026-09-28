"""Residual inspection. EMPTY is the only clean removal result.

When ``bpffs`` is set, known pin names are read from that directory.
A snapshot that lists no pins does not hide a name that is still there.
"""

from __future__ import annotations

from pathlib import Path

from vantio_install import bpf_pins, constants
from vantio_install.agent_sdk import agent_sdk_residual_items
from vantio_install.optics_cli import optics_cli_residual_items


def inspect(
    snapshot: dict,
    *,
    scope: str,
    prefix: Path,
    stage: Path,
    iface: str,
    bpffs: Path | None = None,
) -> dict:
    probes = list(snapshot.get("probe_errors") or [])
    if probes:
        return {
            "result": "UNKNOWN",
            "scope": scope,
            "items": [],
            "probe_errors": probes,
        }
    items: list[dict] = []
    pin_errors: list[str] = []
    if scope in {"pe", "all"}:
        for row in snapshot.get("containers") or []:
            if row.get("role") == "phantom_engine":
                items.append({"kind": "container", "name": row.get("name"), "status": row.get("status")})
        for row in snapshot.get("images") or []:
            if row.get("role") == "phantom_engine":
                items.append({"kind": "image", "tag": row.get("tag"), "digest": row.get("digest")})
        if stage.is_dir() and any(stage.iterdir()):
            items.append({"kind": "stage_dir", "path": stage.name})
        pin_items, pin_errors = _pin_items(snapshot, bpffs)
        if not pin_errors:
            items.extend(pin_items)
        if iface and iface in (snapshot.get("clsact_ifaces") or []):
            items.append({"kind": "clsact", "iface": iface})
        if "vantio-loader" in (snapshot.get("processes") or []):
            items.append({"kind": "process", "name": "vantio-loader"})
    if scope in {"optics", "all"}:
        receipt = prefix / "optics-cli-receipt.json"
        if receipt.is_file():
            items.append({"kind": "optics_receipt", "name": "optics-cli-receipt.json"})
        if snapshot.get("optics_cli_version"):
            items.append({"kind": "optics_cli", "version": snapshot.get("optics_cli_version")})
        items.extend(optics_cli_residual_items(prefix))
        if snapshot.get("agent_sdk_npm_version"):
            items.append({"kind": "agent_sdk_npm", "version": snapshot.get("agent_sdk_npm_version")})
        if snapshot.get("agent_sdk_py_version"):
            items.append({"kind": "agent_sdk_py", "version": snapshot.get("agent_sdk_py_version")})
        items.extend(agent_sdk_residual_items(prefix))
    if pin_errors:
        return {
            "result": "UNKNOWN",
            "scope": scope,
            "items": items,
            "probe_errors": pin_errors,
        }
    result = "EMPTY" if not items else "RESIDUAL_PRESENT"
    return {"result": result, "scope": scope, "items": items, "probe_errors": []}


def _pin_items(snapshot: dict, bpffs: Path | None) -> tuple[list[dict], list[str]]:
    recorded = {pin for pin in (snapshot.get("bpf_pins") or []) if pin in constants.BPF_PINS}
    if bpffs is not None:
        live, errors = bpf_pins.scan_known_pins(bpffs)
        if errors:
            return [], errors
        recorded.update(live)
    names = [name for name in constants.BPF_PINS if name in recorded]
    return [{"kind": "bpf_pin", "name": name} for name in names], []
