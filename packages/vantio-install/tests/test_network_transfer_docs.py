"""GAP-CB-DEP-013 customer network-transfer allowlist regressions."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
DOC_PATH = PACKAGE / "docs" / "NETWORK-TRANSFER-ALLOWLIST.md"

BASENAME = "vantio-phantom-engine-pe-residuals-06696d5-linux-amd64.oci.tar"
RELATIVE = "artifacts/phantom-engine/" + BASENAME
SHA256 = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
SOURCE_COMMIT = "06696d5020700693b0154c59d0e072a24f648378"
MANIFEST_DIGEST = "sha256:8b40aec5c125043ec4278a14170677474c9ca31a7ae78e8496c40dffa69d0e19"
SUPERSEDED_BASENAME = "vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar"

_ABSOLUTE_PATH = re.compile(
    r"(?:^|[\s`'\"(])/(?:home|opt|var|usr|Users|root|tmp|mnt|srv|etc)(?:/|\b)"
)
_FORBIDDEN_TEXT = (
    "Phantom Box",
    "phantom-box",
    "w3-aws-internal",
    "VANTIO_SOAK_LOCAL",
    ":5001",
    "0.0.0.0/0",
    "0.0.0.0",
    "::/0",
    "GHCR",
    "ghcr.io",
    "github.com",
    "git clone",
)


def evaluate_handoff(
    *,
    media_present: bool,
    sums_present: bool,
    digest: str,
    version_ok: bool,
    arch_ok: bool,
    complete: bool,
    interrupted: bool,
    repaired: bool,
) -> dict:
    """Fail-closed stand-in for the documented allow, copy, verify, place, revoke path."""
    if not media_present or not sums_present:
        return {
            "steps": ["stop"],
            "placed": False,
            "revoked": True,
            "resumed_partial": False,
            "reason": "missing",
        }
    if digest != SHA256:
        return {
            "steps": ["stop"],
            "placed": False,
            "revoked": True,
            "resumed_partial": False,
            "reason": "hash-mismatch",
        }
    if not version_ok:
        return {
            "steps": ["stop"],
            "placed": False,
            "revoked": True,
            "resumed_partial": False,
            "reason": "wrong-version",
        }
    if not arch_ok:
        return {
            "steps": ["stop"],
            "placed": False,
            "revoked": True,
            "resumed_partial": False,
            "reason": "wrong-arch",
        }
    if interrupted or not complete:
        return {
            "steps": ["delete-partial", "stop"],
            "placed": False,
            "revoked": True,
            "resumed_partial": False,
            "reason": "incomplete",
        }
    if repaired:
        return {
            "steps": ["stop"],
            "placed": False,
            "revoked": True,
            "resumed_partial": False,
            "reason": "manual-repair",
        }
    return {
        "steps": ["allow", "copy", "verify", "place", "revoke"],
        "placed": True,
        "revoked": True,
        "resumed_partial": False,
        "evidence": ["transfer-verify.txt", "transfer-evidence.txt"],
        "reason": "ok",
    }


class NetworkTransferDocsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = DOC_PATH.read_text(encoding="utf-8")

    def test_pins_match_lock(self) -> None:
        self.assertIn(BASENAME, self.doc)
        self.assertIn(RELATIVE, self.doc)
        self.assertIn(SHA256, self.doc)
        self.assertIn(SOURCE_COMMIT, self.doc)
        self.assertIn(MANIFEST_DIGEST, self.doc)
        self.assertIn("`published` is false", self.doc)
        self.assertIn("INTERNAL_CLEAN_HOST_PROOF", self.doc)
        self.assertIn("GAP-CB-DEP-013", self.doc)
        self.assertIn("This note does not record a LIVE_TRANSFER PASS.", self.doc)
        self.assertNotIn(SUPERSEDED_BASENAME, self.doc)
        constants = (PACKAGE / "vantio_install" / "constants.py").read_text(encoding="utf-8")
        self.assertIn(SHA256, constants)
        self.assertIn(SOURCE_COMMIT, constants)
        self.assertIn(MANIFEST_DIGEST, constants)
        pyproject = (PACKAGE / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "0.1.0-stage-a"', pyproject)

    def test_01_correct_basename(self) -> None:
        self.assertEqual(self.doc.count(BASENAME) >= 1, True)
        self.assertIn(f"Basename: `{BASENAME}`", self.doc)
        self.assertIn("Do not shorten it", self.doc)
        self.assertNotIn(SUPERSEDED_BASENAME, self.doc)

    def test_02_missing_artifact_stops(self) -> None:
        self.assertIn("If the archive is missing, stop.", self.doc)
        self.assertIn("If `SHA256SUMS` is missing", self.doc)
        result = evaluate_handoff(
            media_present=False,
            sums_present=True,
            digest=SHA256,
            version_ok=True,
            arch_ok=True,
            complete=True,
            interrupted=False,
            repaired=False,
        )
        self.assertEqual(result["reason"], "missing")
        self.assertFalse(result["placed"])
        missing_sums = evaluate_handoff(
            media_present=True,
            sums_present=False,
            digest=SHA256,
            version_ok=True,
            arch_ok=True,
            complete=True,
            interrupted=False,
            repaired=False,
        )
        self.assertEqual(missing_sums["reason"], "missing")
        self.assertFalse(missing_sums["placed"])

    def test_03_hash_mismatch_stops(self) -> None:
        self.assertIn("hash mismatch", self.doc)
        self.assertIn("not the locked digest", self.doc)
        self.assertIn("Do not change the digest", self.doc)
        result = evaluate_handoff(
            media_present=True,
            sums_present=True,
            digest="0" * 64,
            version_ok=True,
            arch_ok=True,
            complete=True,
            interrupted=False,
            repaired=False,
        )
        self.assertEqual(result["reason"], "hash-mismatch")
        self.assertFalse(result["placed"])

    def test_04_wrong_version_language(self) -> None:
        self.assertIn("wrong version", self.doc)
        self.assertIn("0.3.24", self.doc)
        self.assertIn("0.2.4", self.doc)
        self.assertIn("3.1.0", self.doc)
        self.assertIn("does not change frozen versions", self.doc)
        constants = (PACKAGE / "vantio_install" / "constants.py").read_text(encoding="utf-8")
        self.assertIn('"optics_cli_version": "0.3.24"', constants)
        self.assertIn('"agent_sdk_npm_version": "0.2.4"', constants)
        self.assertIn('"agent_sdk_py_version": "3.1.0"', constants)
        result = evaluate_handoff(
            media_present=True,
            sums_present=True,
            digest=SHA256,
            version_ok=False,
            arch_ok=True,
            complete=True,
            interrupted=False,
            repaired=False,
        )
        self.assertEqual(result["reason"], "wrong-version")
        self.assertFalse(result["placed"])

    def test_05_wrong_arch_language(self) -> None:
        self.assertIn("wrong architecture", self.doc)
        self.assertIn("linux-amd64", self.doc)
        self.assertIn("x86_64", self.doc)
        result = evaluate_handoff(
            media_present=True,
            sums_present=True,
            digest=SHA256,
            version_ok=True,
            arch_ok=False,
            complete=True,
            interrupted=False,
            repaired=False,
        )
        self.assertEqual(result["reason"], "wrong-arch")
        self.assertFalse(result["placed"])

    def test_06_incomplete_transfer_stops(self) -> None:
        self.assertIn("The copy is incomplete.", self.doc)
        self.assertIn("Do not place an incomplete file.", self.doc)
        result = evaluate_handoff(
            media_present=True,
            sums_present=True,
            digest=SHA256,
            version_ok=True,
            arch_ok=True,
            complete=False,
            interrupted=False,
            repaired=False,
        )
        self.assertEqual(result["reason"], "incomplete")
        self.assertFalse(result["placed"])
        self.assertFalse(result["resumed_partial"])

    def test_07_zero_private_path(self) -> None:
        self.assertNotIn("private", self.doc.lower())
        self.assertNotIn("git clone", self.doc.lower())
        self.assertNotIn("github.com", self.doc.lower())
        self.assertNotIn("~/", self.doc)
        self.assertIsNone(_ABSOLUTE_PATH.search(self.doc))
        self.assertNotIn("http://", self.doc)
        self.assertNotIn("https://", self.doc)
        self.assertNotIn("file://", self.doc)

    def test_08_zero_phantom_box_and_forbidden_strings(self) -> None:
        self.assertIsNone(re.search(r"phantom[\s-]*box", self.doc, re.IGNORECASE))
        for needle in _FORBIDDEN_TEXT:
            self.assertNotIn(needle, self.doc)
        self.assertIn("container registry", self.doc)
        self.assertIn("repository checkout", self.doc)
        self.assertIn("every source address", self.doc)
        self.assertIn("is refused", self.doc)

    def test_09_no_manual_repair_happy_path(self) -> None:
        self.assertIn("Do not edit the archive", self.doc)
        self.assertIn("A hand-edited archive is not a successful handoff.", self.doc)
        self.assertIn("There is no repair that ends in a successful handoff.", self.doc)
        self.assertNotIn("repair the archive and continue", self.doc.lower())
        self.assertNotIn("fix the file and continue", self.doc.lower())
        result = evaluate_handoff(
            media_present=True,
            sums_present=True,
            digest=SHA256,
            version_ok=True,
            arch_ok=True,
            complete=True,
            interrupted=False,
            repaired=True,
        )
        self.assertEqual(result["reason"], "manual-repair")
        self.assertFalse(result["placed"])
        self.assertNotEqual(result["steps"], ["allow", "copy", "verify", "place", "revoke"])

    def test_10_successful_handoff_order(self) -> None:
        markers = ["# 1. ALLOW", "# 2. COPY", "# 3. VERIFY", "# 4. PLACE", "# 5. REVOKE"]
        indexes = [self.doc.index(marker) for marker in markers]
        self.assertEqual(indexes, sorted(indexes))
        allow, copy, verify, place, revoke = indexes
        self.assertIn("authorize-security-group-ingress", self.doc[allow:copy])
        self.assertIn("OPERATOR_PUBLIC_IP/32", self.doc[allow:copy])
        self.assertIn("scp -i SSH_IDENTITY", self.doc[copy:verify])
        self.assertIn(BASENAME, self.doc[copy:verify])
        self.assertIn("sha256sum -c - > ./transfer-verify.txt", self.doc[verify:place])
        self.assertIn(SHA256, self.doc[verify:place])
        self.assertIn("sha256sum -c SHA256SUMS >> ./transfer-verify.txt", self.doc[verify:place])
        self.assertNotIn("| tee", self.doc[verify:place])
        self.assertIn("mv ./vantio-sealed-media/" + BASENAME, self.doc[place:revoke])
        self.assertIn(RELATIVE, self.doc[place:revoke])
        self.assertIn("revoke-security-group-ingress", self.doc[revoke:])
        self.assertIn("allow, then copy, then verify, then place, then revoke", self.doc)
        result = evaluate_handoff(
            media_present=True,
            sums_present=True,
            digest=SHA256,
            version_ok=True,
            arch_ok=True,
            complete=True,
            interrupted=False,
            repaired=False,
        )
        self.assertEqual(result["steps"], ["allow", "copy", "verify", "place", "revoke"])
        self.assertTrue(result["placed"])
        self.assertTrue(result["revoked"])

    def test_11_evidence_export(self) -> None:
        self.assertIn("## Evidence export", self.doc)
        self.assertIn("transfer-verify.txt", self.doc)
        self.assertIn("transfer-evidence.txt", self.doc)
        self.assertIn("PLAN.json", self.doc)
        self.assertIn("PREFLIGHT.json", self.doc)
        self.assertIn("Do not upload either file.", self.doc)
        self.assertIn("live_transfer: none", self.doc)
        self.assertIn("published: false", self.doc)
        result = evaluate_handoff(
            media_present=True,
            sums_present=True,
            digest=SHA256,
            version_ok=True,
            arch_ok=True,
            complete=True,
            interrupted=False,
            repaired=False,
        )
        self.assertEqual(
            result["evidence"],
            ["transfer-verify.txt", "transfer-evidence.txt"],
        )

    def test_12_interrupted_transfer_recovery(self) -> None:
        self.assertIn("## Recovery", self.doc)
        self.assertIn("If the copy is interrupted", self.doc)
        self.assertIn("Delete that partial file", self.doc)
        self.assertIn("Do not resume an incomplete file", self.doc)
        self.assertIn("Copy the full sealed archive again", self.doc)
        self.assertIn("does not resume an installer transaction", self.doc)
        result = evaluate_handoff(
            media_present=True,
            sums_present=True,
            digest=SHA256,
            version_ok=True,
            arch_ok=True,
            complete=True,
            interrupted=True,
            repaired=False,
        )
        self.assertEqual(result["steps"][0], "delete-partial")
        self.assertFalse(result["placed"])
        self.assertFalse(result["resumed_partial"])
        self.assertTrue(result["revoked"])

    def test_required_sections_and_cross_link(self) -> None:
        for heading in (
            "## Origin",
            "## Identity",
            "## Hash verify",
            "## Transfer boundary",
            "## Destination",
            "## Failure behavior",
            "## Recovery",
            "## Evidence export",
        ):
            self.assertIn(heading, self.doc)
        install = (PACKAGE / "docs" / "INSTALL.md").read_text(encoding="utf-8")
        link = (
            "`NETWORK-TRANSFER-ALLOWLIST.md` describes the temporary copy of the "
            "sealed Phantom Engine archive onto that host."
        )
        self.assertEqual(install.count(link), 1)
        self.assertEqual(install.count("NETWORK-TRANSFER-ALLOWLIST.md"), 1)
        self.assertFalse(any(PACKAGE.rglob("*.oci.tar")))

    def test_no_media_upload_or_public_distribution(self) -> None:
        self.assertIn("Do not upload the archive", self.doc)
        self.assertIn("does not publish the archive", self.doc)
        self.assertIn("stays open", self.doc)
        self.assertNotIn("LIVE_TRANSFER PASS recorded", self.doc)
        self.assertNotRegex(self.doc, r"(?i)transfer rehearsal passed")


if __name__ == "__main__":
    unittest.main()
