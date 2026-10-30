#!/usr/bin/env python3
"""Guards for the GCP lab. These tests do not call GCP."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest import mock

import yaml

import lab_auto as lab

ROOT = Path(__file__).resolve().parents[2]


def _passing_gate() -> dict:
    return lab.evaluate_cost_gate(
        {
            "lab_project_id": "vantio-lab-oct08",
            "billing_account_open": True,
            "partner_identity_present": False,
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
        self.assertFalse(lab.names_partner(text))

    def test_cost_gate_passes_only_under_the_ceiling(self) -> None:
        decision = _passing_gate()
        self.assertEqual(decision["expected_oop_usd"], "0")
        self.assertFalse(decision["abort"])
        self.assertFalse(decision["pe_installed"])

    def test_cost_gate_refuses_partner_identity_and_missing_credit(self) -> None:
        payload = {
            "lab_project_id": "vantio-lab-oct08",
            "billing_account_open": True,
            "partner_identity_present": True,
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
        self.assertIn("partner_identity", decision["reasons"])
        self.assertIn("credits_unreadable", decision["reasons"])

    def test_budget_must_be_the_lab_project_only(self) -> None:
        payload = {
            "lab_project_id": "vantio-lab-oct08",
            "billing_account_open": True,
            "partner_identity_present": False,
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
            "partner_identity_present": False,
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

    def test_switches_ship_false(self) -> None:
        capabilities = lab.load_capabilities()
        self.assertIs(capabilities["launch_enabled"], False)
        self.assertIs(capabilities["sweeper_enabled"], False)
        self.assertFalse(lab.flag_enabled(capabilities, "launch_enabled"))

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
        self.assertFalse(lab.names_partner(joined))
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
        foreign = {"name": "partner-vm", "labels": {"vantio-lab": "gcp", "vantio-owner": "gha"}}
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
        partner_policy = {"bindings": [{"role": "roles/owner", "members": ["user:support@partner-x.example"]}]}
        with mock.patch.dict(os.environ, {"VANTIO_PARTNER_MARKERS": "partner-x.example"}):
            self.assertTrue(lab.iam_has_partner_identity(partner_policy))
            self.assertFalse(lab.valid_lab_project("vantio-lab-partner-x.example"))
            self.assertFalse(
                lab.iam_has_partner_identity({"bindings": [{"role": "roles/owner", "members": ["user:a@vantio.ai"]}]})
            )
        with mock.patch.dict(os.environ, {"VANTIO_PARTNER_MARKERS": ""}):
            self.assertFalse(lab.iam_has_partner_identity(partner_policy))
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
        self.assertIs(payload["partner_identity_present"], False)
        decision = lab.evaluate_cost_gate(payload)
        self.assertEqual(decision["expected_oop_usd"], "0")

    def test_capabilities_file_is_json(self) -> None:
        raw = json.loads((lab.HERE / "lab_capabilities.json").read_text(encoding="utf-8"))
        self.assertIs(raw["launch_enabled"], False)
        self.assertIs(raw["sweeper_enabled"], False)
        self.assertIs(raw["offline_delivery_enabled"], True)

    def _sweep_env(self) -> dict[str, str]:
        return {
            "GCP_LAB_EXECUTE": "1",
            "GCP_LAB_PROJECT": "vantio-lab-oct08",
            "GCP_LAB_NOW_EPOCH": "1800000001",
        }

    def _gcloud(self, stdout: str, code: int = 0):
        def run(argv, **_kwargs):
            return subprocess.CompletedProcess(argv, code, stdout, "")

        return run

    def _refuse_delete(self, argv: list[str]):
        raise AssertionError(argv)

    def test_sweeper_empty_list_records_list_ok(self) -> None:
        buf = io.StringIO()
        with mock.patch.object(lab.subprocess, "run", self._gcloud("[]")), redirect_stdout(buf):
            code = lab.execute_sweep(self._sweep_env(), runner=self._refuse_delete)
        text = buf.getvalue().strip()
        self.assertEqual(code, 0)
        self.assertEqual(
            text,
            json.dumps(
                {"actions": [], "cloud": "gcp", "deleted": False, "list_ok": True, "instances_seen": 0}
            ),
        )
        parsed = json.loads(text)
        self.assertEqual(list(parsed), ["actions", "cloud", "deleted", "list_ok", "instances_seen"])

    def test_sweeper_list_failure_fails_closed(self) -> None:
        cases = [
            ("called", subprocess.CompletedProcess(["gcloud"], 1, "", "")),
            ("object", subprocess.CompletedProcess(["gcloud"], 0, "{}", "")),
            ("empty", subprocess.CompletedProcess(["gcloud"], 0, "", "")),
            ("text", subprocess.CompletedProcess(["gcloud"], 0, "not-json", "")),
        ]
        for name, completed in cases:
            with self.subTest(name=name):
                def run(argv, _completed=completed, **_kwargs):
                    return _completed

                buf = io.StringIO()
                with mock.patch.object(lab.subprocess, "run", run), redirect_stdout(buf):
                    code = lab.execute_sweep(self._sweep_env())
                text = buf.getvalue().strip()
                parsed = json.loads(text)
                self.assertEqual(code, 2)
                self.assertIs(parsed["list_ok"], False)
                self.assertEqual(parsed["reason"], "instances_list_failed")
                self.assertNotIn("actions", parsed)
                self.assertNotIn("deleted", parsed)
                self.assertEqual(list(parsed), ["cloud", "list_ok", "reason"])

    def test_sweeper_owned_expired_instance_is_would_delete(self) -> None:
        body = json.dumps(
            [
                {
                    "name": "vantio-gcp-lab-1",
                    "zone": "https://www.googleapis.com/compute/v1/projects/vantio-lab-oct08/zones/us-central1-a",
                    "labels": {
                        "vantio-lab": "gcp",
                        "vantio-owner": "gha",
                        "vantio-expires-epoch": "1800000000",
                    },
                }
            ]
        )
        buf = io.StringIO()
        with mock.patch.object(lab.subprocess, "run", self._gcloud(body)), redirect_stdout(buf):
            code = lab.execute_sweep(self._sweep_env(), runner=self._refuse_delete)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(code, 0)
        self.assertIs(parsed["list_ok"], True)
        self.assertEqual(parsed["instances_seen"], 1)
        self.assertIs(parsed["deleted"], False)
        self.assertEqual(parsed["actions"], [{"name": "vantio-gcp-lab-1", "action": "would_delete"}])
        self.assertEqual(list(parsed), ["actions", "cloud", "deleted", "list_ok", "instances_seen"])

    def _verify_env(self) -> dict[str, str]:
        return {
            "GCP_LAB_EXECUTE": "1",
            "GCP_LAB_PROJECT": "vantio-lab-oct08",
            "INSTANCE_NAME": "vantio-gcp-lab-12",
        }

    def test_verify_removed_empty_lists_are_list_ok(self) -> None:
        buf = io.StringIO()
        with mock.patch.object(lab.subprocess, "run", self._gcloud("[]")), redirect_stdout(buf):
            code = lab.execute_verify(self._verify_env())
        text = buf.getvalue().strip()
        parsed = json.loads(text)
        self.assertEqual(code, 0)
        self.assertEqual(parsed["status"], "VERIFIED_REMOVED")
        self.assertEqual(parsed["name"], "vantio-gcp-lab-12")
        self.assertEqual(parsed["cloud"], "gcp")
        self.assertIs(parsed["list_ok"], True)
        self.assertIs(parsed["checked_disks"], True)
        self.assertEqual(parsed["instances_seen"], 0)
        self.assertEqual(parsed["disks_seen"], 0)
        self.assertEqual(
            list(parsed),
            ["status", "name", "cloud", "list_ok", "checked_disks", "instances_seen", "disks_seen"],
        )

    def test_verify_removed_list_failure_is_unknown(self) -> None:
        def disks_fail(argv, **_kwargs):
            if "disks" in argv:
                return subprocess.CompletedProcess(argv, 1, "", "")
            return subprocess.CompletedProcess(argv, 0, "[]", "")

        buf = io.StringIO()
        with mock.patch.object(lab.subprocess, "run", disks_fail), redirect_stdout(buf):
            code = lab.execute_verify(self._verify_env())
        parsed = json.loads(buf.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(parsed["status"], "UNKNOWN")
        self.assertIs(parsed["list_ok"], False)
        self.assertIs(parsed["checked_disks"], False)
        self.assertNotIn("VERIFIED_REMOVED", buf.getvalue())

        def instances_object(argv, **_kwargs):
            if "instances" in argv:
                return subprocess.CompletedProcess(argv, 0, "{}", "")
            return subprocess.CompletedProcess(argv, 0, "[]", "")

        buf = io.StringIO()
        with mock.patch.object(lab.subprocess, "run", instances_object), redirect_stdout(buf):
            code = lab.execute_verify(self._verify_env())
        parsed = json.loads(buf.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(parsed["status"], "UNKNOWN")
        self.assertIs(parsed["list_ok"], False)
        self.assertIs(parsed["checked_disks"], True)

        def empty_stdout(argv, **_kwargs):
            return subprocess.CompletedProcess(argv, 0, "", "")

        buf = io.StringIO()
        with mock.patch.object(lab.subprocess, "run", empty_stdout), redirect_stdout(buf):
            code = lab.execute_verify(self._verify_env())
        parsed = json.loads(buf.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(parsed["status"], "UNKNOWN")
        self.assertIs(parsed["list_ok"], False)
        self.assertNotEqual(parsed["status"], "VERIFIED_REMOVED")

    def test_verify_removed_non_json_stdout_and_list_rc_are_unknown(self) -> None:
        # Council N3. checked_disks is whatever this call's disk list returned.
        cases = (
            ("non_json_rc_0", lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 0, "not-json", ""), False),
            (
                "instances_rc",
                lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 1, "", "")
                if "instances" in argv
                else subprocess.CompletedProcess(argv, 0, "[]", ""),
                True,
            ),
            (
                "disks_rc",
                lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 1, "", "")
                if "disks" in argv
                else subprocess.CompletedProcess(argv, 0, "[]", ""),
                False,
            ),
        )
        for name, run, checked_disks in cases:
            with self.subTest(name=name):
                buf = io.StringIO()
                err = io.StringIO()
                with (
                    mock.patch.object(lab.subprocess, "run", run),
                    redirect_stdout(buf),
                    redirect_stderr(err),
                ):
                    code = lab.execute_verify(self._verify_env())
                text = buf.getvalue()
                parsed = json.loads(text)
                self.assertEqual(code, 2)
                self.assertEqual(parsed["status"], "UNKNOWN")
                self.assertIs(parsed["list_ok"], False)
                self.assertIs(parsed["checked_disks"], checked_disks)
                self.assertNotEqual(parsed["status"], "VERIFIED_REMOVED")
                self.assertNotIn("VERIFIED_REMOVED", text)


def _workflow(name: str) -> tuple[str, dict]:
    path = ROOT / ".github" / "workflows" / name
    raw = path.read_text(encoding="utf-8")
    return raw, yaml.safe_load(raw)


def _on(document: dict) -> dict:
    if True in document:
        return document[True]
    return document["on"]


class SweepSidecarTests(unittest.TestCase):
    def test_sweep_and_verify_removed_write_sha256_sidecars(self) -> None:
        for name, json_name, step_name in (
            ("gcp-lab-sweeper.yml", "gcp-lab-sweep.json", "Hash sweep evidence"),
            ("gcp-lab-verify-removed.yml", "gcp-lab-verify-removed.json", "Hash removal evidence"),
        ):
            with self.subTest(workflow=name):
                raw, doc = _workflow(name)
                steps = doc["jobs"][next(iter(doc["jobs"]))]["steps"]
                hashed = next(step for step in steps if step.get("name") == step_name)
                upload = next(step for step in steps if json_name in str(step.get("with", {}).get("path", "")))
                self.assertLess(steps.index(hashed), steps.index(upload))
                self.assertIn("always()", hashed["if"])
                self.assertIn("sha256sum", hashed["run"])
                self.assertIn(json_name, hashed["run"])
                path = upload["with"]["path"]
                self.assertIn(json_name, path)
                self.assertIn(json_name + ".sha256", path)
                self.assertNotIn("gh workflow run", raw)
                self.assertNotIn("gh run rerun", raw)
        sweep_raw, sweep = _workflow("gcp-lab-sweeper.yml")
        self.assertEqual(_on(sweep)["schedule"][0]["cron"], "*/30 * * * *")
        self.assertEqual(sweep["concurrency"]["group"], "vantio-gce-slot")
        self.assertIs(sweep["concurrency"]["cancel-in-progress"], False)
        self.assertNotIn("gh workflow run", sweep_raw)

    def test_sidecar_script_matches_sha256sum(self) -> None:
        _raw, doc = _workflow("gcp-lab-sweeper.yml")
        steps = doc["jobs"]["sweep"]["steps"]
        script = next(step for step in steps if step.get("name") == "Hash sweep evidence")["run"]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "gcp-lab-sweep.json"
            target.write_text('{"actions": [], "cloud": "gcp", "deleted": false}\n', encoding="utf-8")
            env = os.environ.copy()
            env["RUNNER_TEMP"] = tmp
            completed = subprocess.run(
                ["bash", "-c", script],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            sidecar = Path(tmp) / "gcp-lab-sweep.json.sha256"
            self.assertTrue(sidecar.is_file())
            checked = subprocess.run(
                ["sha256sum", "-c", sidecar.name],
                cwd=tmp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("gcp-lab-sweep.json", sidecar.read_text(encoding="utf-8"))
            empty = Path(tmp) / "gcp-lab-sweep.json"
            empty.write_text("", encoding="utf-8")
            sidecar.unlink()
            again = subprocess.run(
                ["bash", "-c", script],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertFalse(sidecar.exists())


if __name__ == "__main__":
    unittest.main()
