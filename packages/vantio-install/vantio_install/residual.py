"""Residual inspection. EMPTY is the only clean removal result."""

from __future__ import annotations

from pathlib import Path

from vantio_install import constants


def inspect(snapshot: dict, *, scope: str, prefix: Path, stage: Path, iface: str) -> dict:
    probes = list(snapshot.get("probe_errors") or [])
    if probes:
        return {
            "result": "UNKNOWN",
            "scope": scope,
            "items": [],
            "probe_errors": probes,
        }
    items: list[dict] = []
    if scope in {"pe", "all"}:
        for row in snapshot.get("containers") or []:
            if row.get("role") == "phantom_engine":
                items.append({"kind": "container", "name": row.get("name"), "status": row.get("status")})
        for row in snapshot.get("images") or []:
            if row.get("role") == "phantom_engine":
                items.append({"kind": "image", "tag": row.get("tag"), "digest": row.get("digest")})
        if stage.is_dir() and any(stage.iterdir()):
            items.append({"kind": "stage_dir", "path": stage.name})
        for pin in snapshot.get("bpf_pins") or []:
            if pin in constants.BPF_PINS:
                items.append({"kind": "bpf_pin", "name": pin})
        if iface and iface in (snapshot.get("clsact_ifaces") or []):
            items.append({"kind": "clsact", "iface": iface})
        if "vantio-loader" in (snapshot.get("processes") or []):
            items.append({"kind": "process", "name": "vantio-loader"})
    if scope in {"optics", "all"}:
        for name in ("optics-cli-receipt.json", "agent-sdk-receipt.json"):
            path = prefix / name
            if path.is_file():
                items.append({"kind": "optics_receipt", "name": name})
        if snapshot.get("optics_cli_version"):
            items.append({"kind": "optics_cli", "version": snapshot.get("optics_cli_version")})
    result = "EMPTY" if not items else "RESIDUAL_PRESENT"
    return {"result": result, "scope": scope, "items": items, "probe_errors": []}
