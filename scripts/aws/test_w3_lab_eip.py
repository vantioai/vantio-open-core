#!/usr/bin/env python3
"""Decisions for the one authorized Elastic IP. No AWS calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import w3_lab_auto as lab  # noqa: E402
import w3_lab_eip as eip  # noqa: E402


def completed(payload: dict | None = None, *, code: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    stdout = "" if payload is None else json.dumps(payload)
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


def address(**extra: object) -> dict:
    body = {
        "AllocationId": "eipalloc-06d71714cf284f9d5",
        "Domain": "vpc",
        "PublicIp": eip.PUBLIC_IP,
        "Tags": [{"Key": "Name", "Value": "vantio-w3-c8-fixture-20260929-04"}],
    }
    body.update(extra)
    return body


class DecideTests(unittest.TestCase):
    def test_clear_address_may_be_released(self) -> None:
        decision = eip.decide(address())
        self.assertTrue(decision["release"])
        self.assertEqual(decision["status"], "UNATTACHED_NOT_LAB")

    def test_association_blocks_release(self) -> None:
        decision = eip.decide(address(AssociationId="eipassoc-0123456789abcdef0", InstanceId="i-0123456789abcdef0"))
        self.assertFalse(decision["release"])
        self.assertEqual(decision["status"], "ATTACHED")

    def test_lab_tag_blocks_release(self) -> None:
        tagged = address()
        tagged["Tags"].append({"Key": "vantio:lifecycle", "Value": "lab"})
        decision = eip.decide(tagged)
        self.assertFalse(decision["release"])
        self.assertEqual(decision["status"], "LAB_TAGGED")

    def test_wrong_ip_is_refused(self) -> None:
        decision = eip.decide(address(PublicIp="1.2.3.4"))
        self.assertFalse(decision["release"])
        self.assertEqual(decision["status"], "WRONG_ADDRESS")


class ExecuteTests(unittest.TestCase):
    def test_denied_release_does_not_claim_success(self) -> None:
        calls: list[list[str]] = []

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "describe-addresses" in text:
                return completed({"Addresses": [address()]})
            if "release-address" in text:
                return completed(code=254, stderr="An error occurred (AccessDenied) when calling the ReleaseAddress operation: explicit deny")
            raise AssertionError(text)

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "eip.json")
            try:
                with self.assertRaises(lab.GuardAbort) as caught:
                    eip.execute(runner)
            finally:
                os.environ.pop("EVIDENCE_PATH", None)
            body = json.loads(Path(tmp, "eip.json").read_text())
        self.assertEqual(caught.exception.reason, "release_denied")
        self.assertFalse(body["released"])
        self.assertEqual(body["before"]["public_ip"], eip.PUBLIC_IP)
        self.assertTrue(any("release-address" in " ".join(call) for call in calls))


if __name__ == "__main__":
    unittest.main()
