"""Pinned identities for the T1 stranger-host package.

The public installer pin and the working seal are recorded so a bundle can
refuse them. This module does not load a private key.
"""

from __future__ import annotations

import re

SCHEMA = "vantio.stranger-host-evidence/v1"
PROOF_SCHEMA = "vantio.t1-package-proof/v1"
TRUST_KEY_ID = "test-nonprod-ed25519-2026-10-02"
TRUST_SHA256 = "2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876"
TRUST_MEMBER = "vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json"
PUBLIC_PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
# Zachary, 2026-10-16. The comparison digest is the working seal.
# The previous working seal stays named so step 2 can show it is no longer current.
WORKING_SEAL = "6d3ce580ffb5d52fa0bfb70bdee28409fa6282f86737011e3d85c1093f5ea403"
PREVIOUS_WORKING_SEAL = "bbb1025d9303e0c43e435f416772614a04ac5cc0e7e31c30ad43d7a403b2085d"
PLUMBING_ONLY_SEAL = "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753"
TRACKING_SEAL = "16c9e5638c169e5fdd3fd7291b3225a809b18abfe464d717c2d31a398d5bda6a"
COMPARISON_SEAL = WORKING_SEAL
BASE_SHA = "69671e97fa359b685232ec7dd4e9fb4badc7be57"
CEILING_PATH = "/var/lib/vantio-pe-clean-host/d/secret"
ENROLLED_UID = 65534
IMAGE_FAMILY = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
IMAGE_FAMILY_BARE = "ubuntu-2404-lts-amd64"
MAX_BYTES = 2_000_000
LABEL = "Roadmap"
TIER = "UNSET"
CLAIM_FIXTURE = "FIXTURE_NOT_A_HOST_PROOF"
CLAIM_AWAITING = "AWAITING_OUTSIDE_REVIEW"
REFUSED_CLAIMS = frozenset(
    {
        "STRANGER_HOST_PROVED",
        "PROVED_EXTERNAL",
        "CUSTOMER_VALIDATED",
        "SHIPPED",
    }
)
DENY_CASES = (
    "moved",
    "clone3",
    "reparent",
    "double_fork",
    "setsid",
    "unshare",
    "setns",
    "vfork",
    "ancestor_8",
)
ALLOW_CASES = ("ancestor_9", "unenrolled")
LOCKDOWN_MODES = ("none", "integrity", "confidentiality")
FORBIDDEN_JSON_FIELDS = frozenset({"prompt", "messages", "completion"})
PRIVATE_KEY_RE = re.compile(br"-----BEGIN [A-Z ]*PRIVATE KEY-----")
TOKEN_PREFIXES = (b"AKIA", b"ghp_", b"xoxb-", b"sk_live_")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
AMI_RE = re.compile(r"^ami-[0-9a-f]{8,17}$")
DATED_IMAGE_RE = re.compile(r"-v20[0-9]{6}(?:$|[^0-9])")
ATTEST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{7,159}$")
BUNDLE_FILES = (
    "MANIFEST.json",
    "host-record.json",
    "seal.json",
    "rows-enterprise.json",
    "rows-descendant-pre.json",
    "boot-evidence.json",
    "serial.log",
    "rows-descendant-post.json",
    "uninstall.json",
    "teardown.json",
    "secret-scan.txt",
    "grade.json",
)
LAB_OWNED_PREFIXES = (
    ".github/workflows/",
    "scripts/gcp/",
    "scripts/aws/",
    "scripts/lab/",
    "docs/planning/stranger-host-gate/",
    "README.md",
)
PACKAGE_PREFIXES = (
    "docs/gap/t1-stranger-host/",
    "scripts/gap/t1-stranger-host/",
    "tests/gap/t1-stranger-host/",
    "evidence/gap/t1-stranger-host/",
)
