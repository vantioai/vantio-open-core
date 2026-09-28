"""Preflight checks. UNKNOWN on a required hard check blocks. It never becomes READY."""

from __future__ import annotations

import json
from pathlib import Path

from vantio_install import constants
from vantio_install.manifest import (
    artifact_paths,
    hash_named,
    load_manifest,
    missing_manifest_fields,
    scan_disclosure,
    verify_sha256sums,
)

_FORBIDDEN_CIDRS = {"0.0.0.0/0", "::/0", "0.0.0.0", "*"}


def _check(check_id: str, title: str, result: str, observed: dict, expected: dict, remediation: str) -> dict:
    return {
        "id": check_id,
        "title": title,
        "result": result,
        "observed": observed,
        "expected": expected,
        "remediation": remediation,
    }


def _parse_node(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or not value or value in {"ABSENT", "UNKNOWN"}:
        return None
    raw = value[1:] if value.startswith("v") else value
    parts = raw.split(".")
    nums: list[int] = []
    for part in parts[:3]:
        if not part.isdigit():
            return None
        nums.append(int(part))
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def _tracefs_check(host: dict, *, allow_unrecorded: bool) -> dict:
    """New plans require a recorded mount. Recovery of an older snapshot does not invent one."""
    title = "tracefs mounted at /sys/kernel/tracing and non-empty"
    remediation = "Mount tracefs at /sys/kernel/tracing. An empty directory at that path is not tracefs."
    if "tracefs_mounted" not in host:
        if allow_unrecorded:
            return _check(
                "PF-TRACEFS",
                "tracefs fact unrecorded on this recovery snapshot",
                "PASS",
                {"tracefs_mounted": "UNRECORDED"},
                {"tracefs_mounted": "UNRECORDED"},
                "Recovery does not use tracefs. Apply re-probes the live host when the snapshot has no fact.",
            )
        return _check(
            "PF-TRACEFS",
            title,
            "BLOCKED",
            {"tracefs_mounted": "UNKNOWN"},
            {"tracefs_mounted": True},
            remediation,
        )
    tracefs = host.get("tracefs_mounted")
    return _check(
        "PF-TRACEFS",
        title,
        "PASS" if tracefs is True else "BLOCKED",
        {"tracefs_mounted": tracefs if isinstance(tracefs, bool) else "UNKNOWN"},
        {"tracefs_mounted": True},
        remediation,
    )


def _apparmor_observation(host: dict) -> tuple[str, dict]:
    enabled = host.get("apparmor_enabled", "UNKNOWN")
    parser = host.get("apparmor_parser", "UNKNOWN")
    observed = {
        "apparmor_enabled": enabled if isinstance(enabled, bool) else "UNKNOWN",
        "apparmor_parser": parser if isinstance(parser, bool) else "UNKNOWN",
    }
    if enabled is True and parser is True:
        return "PASS", observed
    if not isinstance(enabled, bool) or not isinstance(parser, bool):
        return "UNKNOWN", observed
    return "BLOCKED", observed


def _forbidden_cidr(value: str) -> bool:
    text = value.strip()
    if text in _FORBIDDEN_CIDRS or text.endswith("/0"):
        return True
    return False


def aggregate(checks: list[dict]) -> str:
    results = [row["result"] for row in checks]
    if any(item == "UNSUPPORTED" for item in results):
        return "UNSUPPORTED"
    if any(item in {"BLOCKED", "UNKNOWN"} for item in results):
        return "BLOCKED"
    if any(item == "LIMITATION" for item in results):
        return "READY_WITH_LIMITATIONS"
    return "READY"


def limitations_from(checks: list[dict]) -> list[dict]:
    rows = []
    for check in checks:
        if check["result"] != "LIMITATION":
            continue
        rows.append(
            {
                "id": check["id"],
                "description": check["title"],
                "claim_impact": check["observed"].get("claim_impact", "Recorded limitation."),
            }
        )
    return rows


def run_preflight(
    *,
    bundle: Path,
    config: dict,
    host: dict,
    resuming: bool,
    plan_present: bool,
    config_present: bool,
    bundle_digest_match: bool,
    allow_unrecorded_tracefs: bool = False,
) -> dict:
    pin = constants.FROZEN_PINS
    checks: list[dict] = []
    paths = artifact_paths(bundle, pin)
    manifest = {}
    manifest_error = None
    try:
        manifest = load_manifest(bundle)
    except Exception as exc:  # noqa: BLE001 — surfaced as a blocked check
        manifest_error = str(exc)

    arch = str(host.get("uname_m", "UNKNOWN"))
    arch_ok = arch in {"x86_64", "amd64"}
    checks.append(
        _check(
            "PF-ARCH",
            "CPU architecture x86_64/amd64",
            "PASS" if arch_ok else "UNSUPPORTED",
            {"uname_m": arch, "expected_arch": ["x86_64", "amd64"]},
            {"arch": ["x86_64", "amd64"]},
            "Use an x86_64 or amd64 Linux host.",
        )
    )

    os_id = str(host.get("os_id", "UNKNOWN"))
    os_ver = str(host.get("os_version_id", "UNKNOWN"))
    os_ok = os_id == "ubuntu" and os_ver.startswith("24.04")
    os_result = "PASS" if os_ok else ("BLOCKED" if "UNKNOWN" in {os_id, os_ver} else "UNSUPPORTED")
    checks.append(
        _check(
            "PF-OS",
            "OS is Ubuntu 24.04 LTS family",
            os_result,
            {
                "os_id": os_id,
                "os_version_id": os_ver,
                "os_pretty_name": host.get("os_pretty_name", "UNKNOWN"),
            },
            {"os_id": "ubuntu", "os_version_id": "24.04"},
            "Install on Ubuntu 24.04 LTS.",
        )
    )

    btf = host.get("btf_vmlinux_exists")
    checks.append(
        _check(
            "PF-BTF",
            "Kernel BTF present at /sys/kernel/btf/vmlinux",
            "PASS" if btf is True else ("UNSUPPORTED" if btf is False else "BLOCKED"),
            {"btf_vmlinux_exists": btf if isinstance(btf, bool) else "UNKNOWN"},
            {"btf_vmlinux_exists": True},
            "Boot a kernel that publishes BTF at /sys/kernel/btf/vmlinux.",
        )
    )

    cgroup = str(host.get("cgroup_version", "UNKNOWN"))
    checks.append(
        _check(
            "PF-CGROUP2",
            "cgroup v2 in use",
            "PASS" if cgroup == "cgroup2" else ("UNSUPPORTED" if cgroup == "cgroup1" else "BLOCKED"),
            {"cgroup_version": cgroup},
            {"cgroup_version": "cgroup2"},
            "Mount cgroup v2. cgroup v1-only hosts are unsupported.",
        )
    )

    mounted = host.get("bpffs_mounted")
    writable = host.get("bpffs_writable")
    bpf_ok = mounted is True and writable is True
    checks.append(
        _check(
            "PF-BPFFS",
            "/sys/fs/bpf mounted and writable by intended principal",
            "PASS" if bpf_ok else "BLOCKED",
            {
                "bpffs_mounted": mounted if isinstance(mounted, bool) else "UNKNOWN",
                "bpffs_writable": writable if isinstance(writable, bool) else "UNKNOWN",
            },
            {"bpffs_mounted": True, "bpffs_writable": True},
            "Mount bpffs at /sys/fs/bpf and grant the install principal write access.",
        )
    )

    checks.append(_tracefs_check(host, allow_unrecorded=allow_unrecorded_tracefs))

    docker_bin = host.get("docker_binary") is True
    docker_ver = host.get("docker_version") if host.get("docker_version") else "UNKNOWN"
    checks.append(
        _check(
            "PF-DOCKER",
            "Container runtime docker available",
            "PASS" if docker_bin else "BLOCKED",
            {"docker_binary": docker_bin, "docker_version_or_UNKNOWN": docker_ver},
            {"docker_binary": True},
            "Install Docker and confirm the docker CLI is on PATH.",
        )
    )

    apparmor_result, apparmor_observed = _apparmor_observation(host)
    checks.append(
        _check(
            "PF-APPARMOR",
            "AppArmor enabled and apparmor_parser available",
            apparmor_result,
            apparmor_observed,
            {"apparmor_enabled": True, "apparmor_parser": True},
            "Enable AppArmor and install apparmor_parser. The observe-only Phantom Engine container loads a named profile.",
        )
    )

    can = host.get("principal_can_talk_to_docker") is True
    mode = str(host.get("privilege_mode", "UNKNOWN"))
    sudo_ok = host.get("sudo_available") is True and mode == "sudo"
    perm_ok = (can and mode in {"docker_group", "sudo"}) or sudo_ok
    if can and mode == "UNKNOWN":
        perm_ok = True
    checks.append(
        _check(
            "PF-DOCKER-PERM",
            "docker.sock permissions / group / sudo path",
            "PASS" if perm_ok else "BLOCKED",
            {
                "docker_sock_path": host.get("docker_sock_path"),
                "principal_can_talk_to_docker": can,
                "privilege_mode": mode,
                "remediation": "docker group or sudo",
            },
            {"privilege_mode": "docker_group|sudo"},
            "Add the operator to the docker group or rerun with sudo. Group membership is not assumed.",
        )
    )

    mem = host.get("mem_total_kib")
    if not isinstance(mem, int):
        mem_result = "LIMITATION"
        resource = "UNKNOWN"
        impact = "Memory was not observed. Full resource sufficiency stays outside this result."
    elif mem < constants.MEM_BOUNDED_BELOW_KIB:
        mem_result = "LIMITATION"
        resource = "RESOURCE_SUFFICIENT_FOR_BOUNDED_TEST"
        impact = "Memory is in the bounded class. Full resource sufficiency stays outside this result."
    else:
        mem_result = "PASS"
        resource = "ABOVE_BOUNDED_CLASS"
        impact = ""
    gib = round(mem / (1024 * 1024), 3) if isinstance(mem, int) else "UNKNOWN"
    checks.append(
        _check(
            "PF-MEM",
            "Memory class for claim tier",
            mem_result,
            {"mem_total_gib": gib, "resource_class": resource, "claim_impact": impact},
            {"resource_class": "recorded"},
            "Treat hosts under 3 GiB as bounded-test class.",
        )
    )

    iface = str(config.get("iface", ""))
    ifaces = host.get("ifaces") if isinstance(host.get("ifaces"), dict) else {}
    iface_state = ifaces.get(iface, "ABSENT")
    iface_ok = iface_state == "up"
    checks.append(
        _check(
            "PF-IFACE",
            "Target network iface exists",
            "PASS" if iface_ok else "BLOCKED",
            {"iface": iface, "iface_state": iface_state, "discovered_or_configured": "configured"},
            {"iface_state": "up"},
            "Set iface to a host interface that is up. Do not hardcode a lab interface for every host.",
        )
    )

    artifact_rows = [
        ("PF-ARTIFACT-OPTICS", "Optics CLI artifact sha256 match", paths["optics_cli"], pin["optics_cli_sha256"]),
        (
            "PF-ARTIFACT-SDK-NPM",
            "agent-sdk npm artifact sha256 match",
            paths["agent_sdk_npm"],
            pin["agent_sdk_npm_sha256"],
        ),
        (
            "PF-ARTIFACT-SDK-PY",
            "agent-sdk py wheel sha256 match",
            paths["agent_sdk_py_wheel"],
            pin["agent_sdk_py_wheel_sha256"],
        ),
    ]
    for check_id, title, path, expected in artifact_rows:
        observed = hash_named(path)
        checks.append(
            _check(
                check_id,
                title,
                "PASS" if observed == expected else "BLOCKED",
                {
                    "path": path.name,
                    "expected_sha256": expected,
                    "observed_sha256": observed,
                    "match": observed == expected,
                },
                {"match": True},
                "Restore the frozen artifact bytes. A hash mismatch stops the install.",
            )
        )

    sdist = paths["agent_sdk_py_sdist"]
    if sdist.is_file():
        observed_sdist = hash_named(sdist)
        if observed_sdist != pin["agent_sdk_py_sdist_sha256"]:
            checks.append(
                _check(
                    "PF-ARTIFACT-SDK-PY-SDIST",
                    "agent-sdk py sdist sha256 match",
                    "BLOCKED",
                    {
                        "path": sdist.name,
                        "expected_sha256": pin["agent_sdk_py_sdist_sha256"],
                        "observed_sha256": observed_sdist,
                        "match": False,
                    },
                    {"match": True},
                    "Remove the sdist or restore the frozen bytes.",
                )
            )

    pe_obs = hash_named(paths["pe_archive"])
    pe_manifest_doc = None
    pe_match = pe_obs == pin["pe_archive_sha256"]
    commit_match = False
    digest_match = False
    if paths["pe_manifest"].is_file():
        try:
            pe_manifest_doc = json.loads(paths["pe_manifest"].read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pe_manifest_doc = None
    if isinstance(pe_manifest_doc, dict):
        commit_match = pe_manifest_doc.get("source_commit") == pin["pe_source_commit"]
        digest_match = pe_manifest_doc.get("manifest_digest") == pin["pe_manifest_digest"]
        pe_match = pe_match and commit_match and digest_match
        pe_match = pe_match and pe_manifest_doc.get("archive_sha256") == pin["pe_archive_sha256"]
        pe_match = pe_match and pe_manifest_doc.get("config_digest") == pin["pe_config_digest"]
        pe_match = pe_match and pe_manifest_doc.get("loader_sha256") == pin["pe_loader_sha256"]
        pe_match = pe_match and pe_manifest_doc.get("layer_digests") == pin["pe_layer_digests"]
    else:
        pe_match = False
    checks.append(
        _check(
            "PF-ARTIFACT-PE",
            "PE archive + manifest digest match sealed tip",
            "PASS" if pe_match else "BLOCKED",
            {
                "archive_path": paths["pe_archive"].name,
                "archive_sha256_expected": pin["pe_archive_sha256"],
                "archive_sha256_observed": pe_obs,
                "manifest_digest_expected": pin["pe_manifest_digest"],
                "match": pe_match,
                "source_commit": pin["pe_source_commit"],
                "commit_match": commit_match,
                "digest_match": digest_match,
            },
            {"match": True, "source_commit": pin["pe_source_commit"]},
            "Use the sealed archive for the frozen tip. Tip drift needs a new seal.",
        )
    )

    source = str(config.get("artifact_source", "sealed_archive"))
    ghcr = source == "ghcr" or "ghcr.io" in source or source.endswith(":0.1.0")
    manifest_source = ""
    if isinstance(manifest, dict):
        manifest_source = str(manifest.get("artifact_source", ""))
        if manifest_source == "ghcr" or "ghcr.io" in json.dumps(manifest.get("artifacts", {})):
            if ":0.1.0" in json.dumps(manifest.get("artifacts", {})) or manifest_source == "ghcr":
                ghcr = True
    checks.append(
        _check(
            "PF-GHCR-DEFAULT",
            "GHCR 0.1.0 is not selected as artifact source",
            "BLOCKED" if ghcr else "PASS",
            {"artifact_source": source, "ghcr_0_1_0_used": ghcr},
            {"ghcr_0_1_0_used": False},
            "Stage the sealed archive. GHCR 0.1.0 is not a default source.",
        )
    )

    disclosure = scan_disclosure(paths["pe_archive"])
    status = None if not isinstance(pe_manifest_doc, dict) else pe_manifest_doc.get("disclosure_status")
    scan_flag = None if not isinstance(pe_manifest_doc, dict) else pe_manifest_doc.get("forbidden_path_scan")
    disclosure_ok = disclosure["pass"] and status == "PASS" and scan_flag == "PASS"
    checks.append(
        _check(
            "PF-DISCLOSURE",
            "Sealed PE disclosure gate PASS recorded",
            "PASS" if disclosure_ok else "BLOCKED",
            {"disclosure_status": status or "ABSENT", "forbidden_path_scan": disclosure["forbidden_hits"] or scan_flag},
            {"disclosure_status": "PASS", "forbidden_path_scan": "PASS"},
            "Reseal the archive after the disclosure scan passes. There is no waiver for company-host paths.",
        )
    )

    transfer_required = bool(config.get("transfer_required"))
    cidrs = config.get("transfer_source_cidrs") if isinstance(config.get("transfer_source_cidrs"), list) else []
    bad_cidr = any(_forbidden_cidr(str(item)) for item in cidrs)
    if not transfer_required:
        transfer_result = "PASS" if not bad_cidr else "BLOCKED"
    else:
        transfer_result = "PASS" if cidrs and not bad_cidr else "BLOCKED"
    checks.append(
        _check(
            "PF-TRANSFER-ALLOWLIST",
            "Transfer source CIDRs allowlisted when remote transfer required",
            transfer_result,
            {
                "transfer_required": transfer_required,
                "source_cidrs": cidrs,
                "zero_zero_forbidden_confirmed": not bad_cidr,
            },
            {"zero_zero_forbidden_confirmed": True},
            "Provide operator allowlisted transfer CIDRs. 0.0.0.0/0 is refused.",
        )
    )

    mode = str(config.get("install_mode", ""))
    enforcement = str(config.get("enforcement", ""))
    enf_ok = mode == "observe-only" and enforcement == "NOT_ENABLED"
    checks.append(
        _check(
            "PF-ENFORCEMENT-DEFAULT",
            "enforcement is NOT_ENABLED / observe-only",
            "PASS" if enf_ok else "BLOCKED",
            {"install_mode": mode, "enforcement": enforcement},
            {"install_mode": "observe-only", "enforcement": "NOT_ENABLED"},
            "Keep install_mode observe-only and enforcement NOT_ENABLED.",
        )
    )

    if not resuming:
        attach_ok = True
    else:
        attach_ok = plan_present and config_present and bundle_digest_match
    checks.append(
        _check(
            "PF-TX-ATTACH",
            "Plan/apply artifacts and brief/config attached when resuming",
            "PASS" if attach_ok else "BLOCKED",
            {
                "transaction_id": config.get("transaction_id"),
                "plan_present": plan_present,
                "config_present": config_present,
                "bundle_digest_match": bundle_digest_match,
                "resuming": resuming,
            },
            {"bundle_digest_match": True},
            "Reattach the plan, config, and the same bundle digests before resume.",
        )
    )

    node = _parse_node(host.get("node_version"))
    node_ok = node is not None and node >= (18, 0, 0)
    checks.append(
        _check(
            "PF-NODE",
            "Node.js >=18 available or installable for Optics",
            "PASS" if node_ok else "BLOCKED",
            {"node_version_or_absent": host.get("node_version") or "ABSENT", "install_plan": "use host Node >=18"},
            {"node": ">=18"},
            "Install Node.js 18 or newer before apply.",
        )
    )

    enterprise = str(config.get("enterprise_inclusion", "OPTIONAL_SOURCE_ONLY_NOT_PACKAGED_AUTHORITY"))
    claims_packaged = "PACKAGED_AUTHORITY" in enterprise and "NOT_PACKAGED" not in enterprise
    checks.append(
        _check(
            "PF-ENTERPRISE-CLAIM",
            "Enterprise packaging authority not claimed",
            "LIMITATION" if claims_packaged else "PASS",
            {
                "enterprise_inclusion": enterprise,
                "claim_text": "packaged authority requested" if claims_packaged else "not claimed",
                "claim_impact": "Packaged enterprise authority stays outside this install.",
            },
            {"enterprise_inclusion": "OPTIONAL_SOURCE_ONLY_NOT_PACKAGED_AUTHORITY"},
            "Leave enterprise authority out of this bundle.",
        )
    )

    motion = str(config.get("install_motion", "UNKNOWN"))
    motion_limited = motion != "customer-local"
    checks.append(
        _check(
            "PF-OPERATOR-SSH-ASSUMPTION",
            "Installer path is customer-local (not operator-NAT SSH proof)",
            "LIMITATION" if motion_limited else "PASS",
            {
                "install_motion": motion,
                "operator_box_ssh_used": motion == "operator-remote-assist",
                "claim_impact": "Remote operator assist is recorded and is not a customer-path proof.",
            },
            {"install_motion": "customer-local"},
            "Run the installer on the host that will keep the node.",
        )
    )

    if manifest_error or missing_manifest_fields(manifest):
        missing = missing_manifest_fields(manifest) if manifest else ["MANIFEST.json"]
        checks.append(
            _check(
                "PF-MANIFEST",
                "Deployment manifest required sections",
                "BLOCKED",
                {"missing": missing, "error": manifest_error},
                {"missing": []},
                "Add the required manifest sections and validate the JSON.",
            )
        )

    sums_mismatch = False
    rows: list[dict] = []
    try:
        rows = verify_sha256sums(bundle)
        sums_mismatch = any(not row["match"] for row in rows)
    except Exception as exc:  # noqa: BLE001 — hash list errors block the plan
        sums_mismatch = True
        rows = [{"error": str(exc)}]
    if sums_mismatch:
        checks.append(
            _check(
                "PF-SHA256SUMS",
                "SHA256SUMS match bundle bytes",
                "BLOCKED",
                {"rows": rows},
                {"match": True},
                "Regenerate SHA256SUMS from the staged bytes.",
            )
        )

    overall = aggregate(checks)
    return {
        "overall": overall,
        "checks": checks,
        "limitations": limitations_from(checks),
        "failed_or_limiting_checks": [row for row in checks if row["result"] != "PASS"],
        "proof_ceiling": constants.PROOF_CEILING,
        "refuse_apply": overall in {"BLOCKED", "UNSUPPORTED"},
    }
