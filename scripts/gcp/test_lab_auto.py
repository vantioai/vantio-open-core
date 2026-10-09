#!/usr/bin/env python3
"""Guards for the GCP lab. These tests do not call GCP."""

from __future__ import annotations

import json
import unittest
from decimal import Decimal

import lab_auto as lab


def _passing_gate() -> dict:
    return lab.evaluate_cost_gate(
        {
            "lab_project_id": "vantio-lab-oct08",
            "billing_account_open": True,
            "navera_identity_present": False,
            "credit_remaining_usd": "100.00",
            "budget_present": True,
            "budget_project_ids": ["vantio-lab-oct08"],
            "budget_amount_usd": "5.00",
            "cap_armed": True,
            "spend_month_usd": "0.00",
            "instance_count": 0,
            "disk_count": 0,
        }
    )


class LabAutoTest(unittest.TestCase):
    def test_attribute_condition_pins_repo_ref_and_workflows(self) -> None:
        text = lab.attribute_condition()
        self.assertIn("assertion.repository=='vantioai/vantio-open-core'", text)
        self.assertIn("assertion.ref=='refs/heads/main'", text)
        for name in lab.WORKFLOWS:
            self.assertIn(lab.workflow_ref(name), text)
        self.assertNotIn("*", text)
        self.assertNotIn("navera", text)

    def test_cost_gate_passes_only_under_the_ceiling(self) -> None:
        decision = _passing_gate()
        self.assertEqual(decision["expected_oop_usd"], "0")
        self.assertFalse(decision["abort"])
        self.assertFalse(decision["pe_installed"])

    def test_cost_gate_refuses_navera_and_missing_credit(self) -> None:
        payload = {
            "lab_project_id": "vantio-lab-oct08",
            "billing_account_open": True,
            "navera_identity_present": True,
            "credit_remaining_usd": None,
            "budget_present": True,
            "budget_project_ids": ["vantio-lab-oct08"],
            "budget_amount_usd": "5.00",
            "cap_armed": True,
            "spend_month_usd": "0",
            "instance_count": 0,
            "disk_count": 0,
        }
        decision = lab.evaluate_cost_gate(payload)
        self.assertEqual(decision["expected_oop_usd"], "UNKNOWN")
        self.assertIn("navera_identity", decision["reasons"])
        self.assertIn("credits_unreadable", decision["reasons"])

    def test_budget_must_be_the_lab_project_only(self) -> None:
        payload = {
            "lab_project_id": "vantio-lab-oct08",
            "billing_account_open": True,
            "navera_identity_present": False,
            "credit_remaining_usd": "100",
            "budget_present": True,
            "budget_project_ids": ["vantio-lab-oct08", "other-project"],
            "budget_amount_usd": "5",
            "cap_armed": True,
            "spend_month_usd": "0",
            "instance_count": 0,
            "disk_count": 0,
        }
        decision = lab.evaluate_cost_gate(payload)
        self.assertIn("budget_scope", decision["reasons"])
        self.assertEqual(decision["expected_oop_usd"], "UNKNOWN")

    def test_empty_project_can_stand_in_for_unreadable_spend(self) -> None:
        payload = {
            "lab_project_id": "vantio-lab-oct08",
            "billing_account_open": True,
            "navera_identity_present": False,
            "credit_remaining_usd": "100",
            "budget_present": True,
            "budget_project_ids": ["vantio-lab-oct08"],
            "budget_amount_usd": "5",
            "cap_armed": True,
            "spend_month_usd": None,
            "instance_count": 0,
            "disk_count": 0,
        }
        decision = lab.evaluate_cost_gate(payload)
        self.assertEqual(decision["expected_oop_usd"], "0")
        self.assertEqual(decision["spend_source"], "empty_project_no_vms_or_disks")

    def test_launch_armed_sweeper_off(self) -> None:
        capabilities = lab.load_capabilities()
        self.assertIs(capabilities["launch_enabled"], True)
        self.assertIs(capabilities["sweeper_enabled"], False)
        self.assertTrue(lab.flag_enabled(capabilities, "launch_enabled"))
        self.assertFalse(lab.flag_enabled(capabilities, "sweeper_enabled"))

    def test_provision_stays_off_without_calling_gcp(self) -> None:
        self.assertEqual(lab.execute_provision({}), 2)

    def test_one_instance_and_owned_labels(self) -> None:
        self.assertTrue(lab.slot_occupied([{"status": "RUNNING"}]))
        self.assertTrue(lab.slot_occupied([{"status": "TERMINATED"}, {"status": "STOPPED"}]))
        self.assertFalse(lab.slot_occupied([{"status": "TERMINATED"}]))
        self.assertEqual(
            lab.provision_decision(
                {"launch_enabled": True},
                {"expected_oop_usd": "0", "abort": False},
                [{"status": "RUNNING"}],
            ),
            "slot_occupied",
        )
        self.assertEqual(
            lab.provision_decision(
                {"launch_enabled": False},
                {"expected_oop_usd": "0", "abort": False},
                [],
            ),
            "launch_disabled",
        )

    def test_create_argv_has_no_public_ip_and_no_key(self) -> None:
        plan = lab.plan_launch(
            {"project_id": "vantio-lab-oct08", "name": "vantio-gcp-lab-1"},
            1_800_000_000,
        )
        argv = lab.provision_argv(plan, "/tmp/startup.sh")
        self.assertIn("--no-address", argv)
        self.assertIn("--no-service-account", argv)
        self.assertIn("--no-scopes", argv)
        self.assertIn("--shielded-secure-boot", argv)
        joined = " ".join(argv)
        self.assertNotIn("navera", joined)
        self.assertNotIn("private_key", joined)
        script = lab.startup_script(30)
        self.assertIn("PE_INSTALLED=false", script)
        self.assertNotIn("apt-get", script)
        self.assertNotIn("docker pull", script)

    def test_sweeper_deletes_only_expired_owned_instances(self) -> None:
        owned = {
            "name": "vantio-gcp-lab-1",
            "labels": {
                "vantio-lab": "gcp",
                "vantio-owner": "gha",
                "vantio-expires-epoch": "1800000000",
            },
        }
        self.assertEqual(lab.sweeper_action(owned, 1800000000), "delete")
        self.assertEqual(lab.sweeper_action(owned, 1799999999), "keep")
        foreign = {"name": "navera-vm", "labels": {"vantio-lab": "gcp", "vantio-owner": "gha"}}
        self.assertEqual(lab.sweeper_action(foreign, 1900000000), "skip_not_owned")
        self.assertEqual(lab.apply_sweeper("delete", {"sweeper_enabled": False}), "would_delete")
        self.assertEqual(lab.apply_sweeper("delete", {"sweeper_enabled": True}), "delete")

    def test_probe_and_removal_stay_gcp_local(self) -> None:
        text = "\n".join(
            [
                "VANTIO_GCP_LAB_PROBE_BEGIN",
                "KERNEL=6.8.0-1007-gcp",
                "CGROUP=cgroup2fs",
                "BTF=present",
                "BPFFS=present",
                "DOCKER=absent",
                "PE_INSTALLED=false",
                "VANTIO_GCP_LAB_PROBE_END",
            ]
        )
        probe = lab.probe_from_serial(text)
        self.assertTrue(probe["markers_complete"])
        self.assertEqual(probe["docker"], "absent")
        self.assertFalse(probe["pe_installed"])
        self.assertEqual(
            lab.removal_status([{"name": "vantio-gcp-lab-1", "status": "TERMINATED"}], [], "vantio-gcp-lab-1"),
            "VERIFIED_REMOVED",
        )
        self.assertEqual(
            lab.removal_status([], [{"name": "vantio-gcp-lab-1"}], "vantio-gcp-lab-1"),
            "NOT_REMOVED",
        )

    def test_iam_and_budget_parsers(self) -> None:
        self.assertTrue(
            lab.iam_has_navera(
                {"bindings": [{"role": "roles/owner", "members": ["user:support@navera.io"]}]}
            )
        )
        self.assertFalse(lab.iam_has_navera({"bindings": [{"role": "roles/owner", "members": ["user:a@vantio.ai"]}]}))
        amount = lab.budget_amount_usd(
            {"amount": {"specifiedAmount": {"units": "5", "nanos": 0}}, "budgetFilter": {"projects": ["projects/vantio-lab-oct08"]}}
        )
        self.assertEqual(amount, Decimal("5"))
        self.assertEqual(
            lab.budget_project_ids({"budgetFilter": {"projects": ["projects/vantio-lab-oct08"]}}),
            ["vantio-lab-oct08"],
        )
        self.assertEqual(lab.credit_usd_from_labels({"vantio-credit-cents": "30000"}), Decimal("300"))

    def test_gate_reads_only_the_lab_project(self) -> None:
        payload = lab.payload_from_project_reads(
            {
                "projectId": "vantio-lab-oct08",
                "labels": {
                    "vantio-credit-cents": "10000",
                    "vantio-budget-cents": "500",
                    "vantio-cap": "alerts-only",
                },
            },
            {"billingEnabled": True, "billingAccountName": "billingAccounts/012345-6789AB-CDEF01"},
            {"bindings": [{"role": "roles/owner", "members": ["user:zachary@vantio.ai"]}]},
            [],
            [],
        )
        self.assertEqual(payload["budget_project_ids"], ["vantio-lab-oct08"])
        self.assertTrue(payload["cap_armed"])
        self.assertIs(payload["navera_identity_present"], False)
        decision = lab.evaluate_cost_gate(payload)
        self.assertEqual(decision["expected_oop_usd"], "0")

    def test_capabilities_file_is_json(self) -> None:
        raw = json.loads((lab.HERE / "lab_capabilities.json").read_text(encoding="utf-8"))
        self.assertIs(raw["launch_enabled"], True)
        self.assertIs(raw["sweeper_enabled"], False)


if __name__ == "__main__":
    unittest.main()
