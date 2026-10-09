"""Frozen Stage A pins and installer policy constants.

Customer docs must not repeat company-host paths. This module is the
disclosure denylist the preflight gate compares artifacts against.
"""

from __future__ import annotations

INSTALLER_VERSION = "0.1.0-stage-a"
CONTRACT_VERSION = "1.0.0-stage-a"
MANIFEST_VERSION = "1.0.0-stage-a"
PROOF_CEILING = "INTERNAL_CLEAN_HOST_PROOF"
PROOF_STATE = "NOT_PROVED"

FORBIDDEN_PROOF_STATES = frozenset(
    {
        "CUSTOMER_VALIDATED",
        "PROVED_EXTERNAL",
        "SHIPPED",
        "DESIGN_PARTNER_VALIDATED",
    }
)

FORBIDDEN_CLAIMS = frozenset(
    {
        "customer_deployment",
        "stranger_host",
        "PE_enforce_mode",
        "OTLP_bounded_cycle",
        "formal_video_recordings_A_H",
        "ingress_egress_deny_matrix",
        "public_publication",
        "announcement",
        "Paid_plan",
        "certification_or_compliance",
        "FULL_resource_sufficiency",
        "GHCR_0.1.0_verified",
        "CUSTOMER_VALIDATED",
        "PROVED_EXTERNAL",
        "GA_0.2.0_internal_rebind_completed",
    }
)

# Strings that must not appear inside a sealed customer artifact.
DISCLOSURE_FORBIDDEN = (
    "/home/vantioai",
    "vantio-sandbox",
    "absolute_control/secret.token",
)

BPF_PINS = (
    "vantio_trace_map",
    "vantio_enrolled_cgroups",
    "vantio_debug_counters",
    "vantio_debug_last_comm",
    "vantio_tls_severed_pids",
)

# Below this, preflight records a bounded-memory limitation (~t3.small class).
MEM_BOUNDED_BELOW_KIB = 3 * 1024 * 1024

REQUIRED_MANIFEST_FIELDS = (
    "manifest_version",
    "bundle_id",
    "contract_version",
    "proof_ceiling",
    "products",
    "artifacts",
    "artifact_verification",
    "configuration",
    "filesystem_paths",
    "privileges",
    "kernel_capabilities",
    "network_requirements",
    "workload_roots",
    "health",
    "coverage",
    "policy",
    "evidence",
    "transaction",
    "rollback",
    "uninstall",
    "residual_inspection",
    "independent_verification",
    "support_bundle",
    "version_compatibility",
    "unsupported_environments",
    "exclusions",
)

APPLY_STEPS = (
    "verify_artifacts",
    "ensure_node",
    "install_optics_cli",
    "install_agent_sdks",
    "stage_pe_archive",
    "docker_load",
    "write_observe_config",
    "install_boot_hold",
    "start_pe_observe",
    "mark_applied",
    "collect_health",
    "write_support_index",
)

HOST_MUTATION_STEPS = frozenset(
    {
        "install_optics_cli",
        "install_agent_sdks",
        "stage_pe_archive",
        "docker_load",
        "write_observe_config",
        "install_boot_hold",
        "start_pe_observe",
    }
)

EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_UNSUPPORTED = 3
EXIT_FAILED_SAFE = 4
EXIT_INTERRUPTED = 5
EXIT_USAGE = 10
EXIT_CRASH = 20

FROZEN_PINS = {
    "optics_cli_package": "@vantio/cli",
    "optics_cli_version": "0.3.24",
    "optics_cli_filename": "cli-0.3.24.tgz",
    "optics_cli_sha256": "82fe13ad6fc916ac67a670bd95fbf18b24389ecb383d81246e1d52cb96712a1f",
    "agent_sdk_npm_package": "@vantio/agent-sdk",
    "agent_sdk_npm_version": "0.2.4",
    "agent_sdk_npm_filename": "agent-sdk-0.2.4.tgz",
    "agent_sdk_npm_sha256": "465eca5e0db9240530c15b6ab9725c5e302626cdbec541b31b4987d52d36c55c",
    "agent_sdk_py_package": "vantio-agent-sdk",
    "agent_sdk_py_version": "3.1.0",
    "agent_sdk_py_wheel": "vantio_agent_sdk-3.1.0-py3-none-any.whl",
    "agent_sdk_py_wheel_sha256": "dcf84cb3c4f144ece21032001657bfd9c91067faeffbefd0fb2ae19d6109dbeb",
    "agent_sdk_py_sdist": "vantio_agent_sdk-3.1.0.tar.gz",
    "agent_sdk_py_sdist_sha256": "9f991291d5e44a23e17a9b0d7db24f6e7048d4c76cf0a9c37e35ccbcfe999c4f",
    "pe_source_commit": "df61d976a81f44e6165b87d40c493a850a247891",
    "pe_prior_candidate_commit": "fab81efc08110506ff90847495197e7051a253b5",
    "pe_archive_name": "vantio-phantom-engine-policy-allow-df61d97-linux-amd64.oci.tar",
    "pe_archive_sha256": "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753",
    "pe_manifest_digest": "sha256:ef67950f2635f2d2a90fb9fdfc9213be56a118dc5b56af72dd95df8b8031154c",
    "pe_config_digest": "sha256:5210c0ef1f3763d3ac5536d34014169d14699c2a12e528bfc28ee5d7a1a6a34c",
    "pe_loader_sha256": "f49c5dc1b49a7ab758a26f1b9b5a06191516326db7d1ff60c72c01bdec5e3fc6",
    "pe_layer_digests": [
        "sha256:774043ccc8ccd0d0833a9ee0792142ab7ad93df971e59dd248fbf82db16d0150",
        "sha256:2bcb0f32a7bc4b8ae39a1f2f75f736b6505b08db616f8244cf1f92a0f0c56afc",
        "sha256:1ceab224f3c84826371072efd4b220d89d1080f6b0a2c0141eb082e1fb2ce9f4",
    ],
    "pe_local_tag": "vantio-phantom-engine:policy-allow-df61d97",
    "pe_platform": "linux/amd64",
}

# Sealed identity the live gate compares to the pin table at call time.
# Archive file bytes are compared to FROZEN_PINS["pe_archive_sha256"].
LIVE_CANONICAL_IDENTITY = {
    "pe_source_commit": "df61d976a81f44e6165b87d40c493a850a247891",
    "pe_archive_sha256": "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753",
    "pe_manifest_digest": "sha256:ef67950f2635f2d2a90fb9fdfc9213be56a118dc5b56af72dd95df8b8031154c",
}

# Observe-only PE container profile. docker-default denies /sys/fs/bpf pin writes.
PE_OBSERVE_APPARMOR_PROFILE = "vantio-pe-observe"

# Memory class is the only preflight limitation a live apply may carry.
APPROVED_LIVE_LIMITATIONS = frozenset({"PF-MEM"})

LIVE_MUTATING_COMMANDS = frozenset({"apply", "rollback", "uninstall"})

PREFLIGHT_ORDER = (
    "PF-ARCH",
    "PF-OS",
    "PF-BTF",
    "PF-CGROUP2",
    "PF-BPFFS",
    "PF-TRACEFS",
    "PF-DOCKER",
    "PF-APPARMOR",
    "PF-DOCKER-PERM",
    "PF-MEM",
    "PF-IFACE",
    "PF-ARTIFACT-OPTICS",
    "PF-ARTIFACT-SDK-NPM",
    "PF-ARTIFACT-SDK-PY",
    "PF-ARTIFACT-PE",
    "PF-OCI-LOAD",
    "PF-GHCR-DEFAULT",
    "PF-DISCLOSURE",
    "PF-TRANSFER-ALLOWLIST",
    "PF-ENFORCEMENT-DEFAULT",
    "PF-TX-ATTACH",
    "PF-NODE",
    "PF-NPM",
    "PF-ENTERPRISE-CLAIM",
    "PF-OPERATOR-SSH-ASSUMPTION",
)
