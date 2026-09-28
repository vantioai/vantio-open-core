"""Independent verifier.

This module must not import the installer engine, health derivation, or CLI.
It re-reads the bundle and the evidence directory from disk. An installer
exit code of 0 is ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from vantio_install import constants

_REQUIRED = (
    "TRANSACTION.json",
    "PREFLIGHT.json",
    "PLAN.json",
    "HEALTH.json",
    "ARTIFACT-VERIFICATION.json",
    "RESIDUAL.json",
    "HOST-SNAPSHOT.json",
)


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _recompute_health(snapshot: dict, config: dict, limitations: list) -> str:
    probes = set(snapshot.get("probe_errors") or [])
    components: dict[str, str] = {}
    version = snapshot.get("optics_cli_version")
    if version == constants.FROZEN_PINS["optics_cli_version"]:
        components["optics_cli"] = "PASS"
    elif version in (None, "ABSENT"):
        components["optics_cli"] = "NOT_INSTALLED"
    else:
        components["optics_cli"] = "FAIL"
    components["enforcement"] = "NOT_ENABLED" if str(config.get("enforcement")) == "NOT_ENABLED" else "FAIL"
    components["path_deny"] = "NOT_ENABLED" if str(config.get("path_deny", "disabled")) == "disabled" else "FAIL"
    components["otlp"] = "NOT_ENABLED" if str(config.get("otlp", "DISABLED")) == "DISABLED" else "FAIL"
    containers = [row for row in snapshot.get("containers") or [] if row.get("role") == "phantom_engine"]
    running = [row for row in containers if row.get("status") == "running"]
    if "container" in probes:
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
        return "UNKNOWN"
    if any(value == "FAIL" for value in components.values()):
        return "FAIL"
    if any(value in {"NOT_INSTALLED", "NOT_TESTED"} for value in required):
        return "FAIL"
    if limitations:
        return "PASS_WITH_LIMITATIONS"
    return "PASS"


def _claim_hits(value: object, hits: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in constants.FORBIDDEN_CLAIMS and item in {"PASS", "PROVED", "SHIPPED", True}:
                hits.append(str(key))
            if key == "proof_state" and item in constants.FORBIDDEN_PROOF_STATES:
                hits.append(str(item))
            _claim_hits(item, hits)
    elif isinstance(value, list):
        for item in value:
            _claim_hits(item, hits)
    elif isinstance(value, str) and value in constants.FORBIDDEN_PROOF_STATES:
        hits.append(value)


def _residual_items(snapshot: dict, scope: str, iface: str) -> list[dict] | None:
    if snapshot.get("probe_errors"):
        return None
    items: list[dict] = []
    if scope in {"pe", "all", None}:
        for row in snapshot.get("containers") or []:
            if row.get("role") == "phantom_engine":
                items.append({"kind": "container"})
        for row in snapshot.get("images") or []:
            if row.get("role") == "phantom_engine":
                items.append({"kind": "image"})
        for pin in snapshot.get("bpf_pins") or []:
            if pin in constants.BPF_PINS:
                items.append({"kind": "bpf_pin", "name": pin})
        if iface and iface in (snapshot.get("clsact_ifaces") or []):
            items.append({"kind": "clsact"})
        if "vantio-loader" in (snapshot.get("processes") or []):
            items.append({"kind": "process"})
    return items


def verify(evidence_dir: Path, bundle_dir: Path) -> dict:
    checks: list[dict] = []
    missing = [name for name in _REQUIRED if not (evidence_dir / name).is_file()]
    checks.append({"id": "evidence-present", "result": "FAIL" if missing else "PASS", "missing": missing})
    tx = _load(evidence_dir / "TRANSACTION.json") or {}
    config = _load(evidence_dir / "CONFIG.json") or {}
    health = _load(evidence_dir / "HEALTH.json") or {}
    snapshot = _load(evidence_dir / "HOST-SNAPSHOT.json")
    residual = _load(evidence_dir / "RESIDUAL.json") or {}
    pin = constants.FROZEN_PINS
    archive = bundle_dir / "artifacts" / "phantom-engine" / pin["pe_archive_name"]
    cli = bundle_dir / "artifacts" / "optics" / pin["optics_cli_filename"]
    observed_archive = _sha256_file(archive)
    observed_cli = _sha256_file(cli)
    hash_ok = observed_archive == pin["pe_archive_sha256"] and observed_cli == pin["optics_cli_sha256"]
    checks.append(
        {
            "id": "rehash-artifacts",
            "result": "PASS" if hash_ok else "FAIL",
            "archive_match": observed_archive == pin["pe_archive_sha256"],
            "cli_match": observed_cli == pin["optics_cli_sha256"],
        }
    )
    exit_file = evidence_dir / "INSTALLER-EXIT.json"
    exit_doc = _load(exit_file) if exit_file.is_file() else None
    checks.append(
        {
            "id": "installer-exit-ignored",
            "result": "PASS",
            "exit_file_present": exit_file.is_file(),
            "recorded_exit_code": None if not exit_doc else exit_doc.get("exit_code"),
            "trusted": False,
        }
    )
    if snapshot is None:
        checks.append({"id": "recompute-health", "result": "UNKNOWN"})
    else:
        recomputed = _recompute_health(snapshot, config, list(tx.get("limitations") or []))
        stated = health.get("overall")
        match = stated == recomputed
        success_claim = stated in {"PASS", "PASS_WITH_LIMITATIONS"}
        result = "PASS" if match and (not success_claim or recomputed in {"PASS", "PASS_WITH_LIMITATIONS"}) else "FAIL"
        if recomputed == "UNKNOWN" and stated == "UNKNOWN":
            result = "UNKNOWN"
        checks.append({"id": "recompute-health", "result": result, "stated": stated, "recomputed": recomputed})
        scope = residual.get("scope") or "all"
        items = _residual_items(snapshot, str(scope), str(config.get("iface", "")))
        if items is None:
            checks.append({"id": "recompute-residual", "result": "UNKNOWN"})
        else:
            stated_result = residual.get("result")
            recomputed_result = "EMPTY" if not items else "RESIDUAL_PRESENT"
            residual_ok = stated_result == recomputed_result or stated_result == "UNKNOWN"
            if stated_result == "EMPTY" and items:
                residual_ok = False
            checks.append(
                {
                    "id": "recompute-residual",
                    "result": "PASS" if residual_ok else "FAIL",
                    "stated": stated_result,
                    "recomputed": recomputed_result,
                }
            )
    hits: list[str] = []
    for name in ("TRANSACTION.json", "HEALTH.json", "PLAN.json", "PREFLIGHT.json"):
        document = _load(evidence_dir / name)
        if document is not None:
            _claim_hits(document, hits)
    if tx.get("proof_state") not in {None, constants.PROOF_STATE, "UNKNOWN"}:
        if tx.get("proof_state") in constants.FORBIDDEN_PROOF_STATES or tx.get("proof_state") == "INTERNAL_CLEAN_HOST_PROOF":
            hits.append(str(tx.get("proof_state")))
    checks.append({"id": "claim-ceiling", "result": "FAIL" if hits else "PASS", "hits": hits})
    results = [row["result"] for row in checks]
    if any(item == "FAIL" for item in results):
        overall = "FAIL"
    elif any(item == "UNKNOWN" for item in results):
        overall = "UNKNOWN"
    else:
        overall = "PASS"
    return {
        "document": "INDEPENDENT-VERIFICATION",
        "result": overall,
        "proof_state": constants.PROOF_STATE,
        "proof_ceiling": constants.PROOF_CEILING,
        "trusted_installer_exit": False,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vantio-verify")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = verify(Path(args.evidence_dir), Path(args.bundle))
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if report["result"] == "PASS":
        return 0
    if report["result"] == "UNKNOWN":
        return 4
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
