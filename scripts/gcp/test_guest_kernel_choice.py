#!/usr/bin/env python3
"""7.0 and 6.12 stop before a VM. Ubuntu 24.04 stays the image."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import enforcement_proof as ep
import offline_deliver as od


def _env(**extra: str) -> dict[str, str]:
    env = {
        "PE_GIT_SHA": ep.PE_GIT_SHA,
        "PROOF_SLICE": "full",
        "PROOF_RUN_GO": "zach-run-go-placeholder",
        "PROOF_HOST_NAME": "proof81",
        "PROOF_UNINSTALL_APPROVAL": "",
        "STOP_AFTER_MINUTES": "120",
        "INSTANCE_NAME": "",
        "GCP_LAB_PROJECT": "vantio-lab-oct08",
        "GITHUB_RUN_ID": "12",
        "GCP_LAB_NOW_EPOCH": "1800000000",
    }
    env.update(extra)
    return env


class GuestKernelChoiceTests(unittest.TestCase):
    def test_ubuntu_2404_is_created_and_the_other_kernels_are_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = str(Path(tmp) / "startup.sh")
            Path(script).write_text("#!/bin/bash\n", encoding="utf-8")
            argv = ep.instance_create_argv(_env(PROOF_GUEST_KERNEL="ubuntu-24.04"), script)
            self.assertIn("--image-family=ubuntu-2404-lts-amd64", " ".join(argv))
            self.assertEqual(ep.precheck(_env()), 0)
            for kernel in ("7.0", "6.12", "ubuntu-2604"):
                self.assertEqual(ep.precheck(_env(PROOF_GUEST_KERNEL=kernel)), 1)
                with self.assertRaises(SystemExit) as caught:
                    ep.instance_create_argv(_env(PROOF_GUEST_KERNEL=kernel), script)
                self.assertEqual(caught.exception.code, "guest_kernel")
        workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "gcp-lab-enforcement-proof.yml"
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("merge-base --is-ancestor", text)
        self.assertNotIn("ubuntu-2604", text)
        self.assertNotIn("debian-13", text)
        self.assertIn("pe-git-sha-allowlist.txt", text)
        self.assertNotIn("google-github-actions/auth@", text)

    def test_create_policy_refuses_2604_and_debian_13(self) -> None:
        base = {
            "project_id": "vantio-lab-oct08",
            "name": "vantio-gcp-lab-12",
            "public_ip": False,
            "service_account": None,
            "network": od.NETWORK,
            "subnet": od.SUBNET,
            "labels": od.offline_labels(1_800_000_000, 120),
        }
        for family, project in (
            ("ubuntu-2604-lts-amd64", "ubuntu-os-cloud"),
            ("debian-13", "debian-cloud"),
        ):
            plan = dict(base)
            plan["image_family"] = family
            plan["image_project"] = project
            with self.assertRaises(SystemExit) as caught:
                od.offline_create_argv(plan, "/tmp/startup.sh")
            self.assertEqual(caught.exception.code, "image")


if __name__ == "__main__":
    unittest.main()
