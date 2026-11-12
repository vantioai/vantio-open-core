"""Plan tests for the stage 4 lab workflow. They do not call gcloud."""

from __future__ import annotations

import inspect
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[2]
GCP_DIR = ROOT / "scripts" / "gcp"
if str(GCP_DIR) not in sys.path:
    sys.path.insert(0, str(GCP_DIR))

import enforcement_proof
import lab_auto
import stage4_drive
import stage4_plan


WORKFLOW = ROOT / ".github" / "workflows" / "gcp-stage4-lab.yml"
COST_GATE = ROOT / ".github" / "workflows" / "gcp-lab-cost-gate.yml"
FULL = (
    "compare",
    "root-detach",
    "signals",
    "file-deny",
    "fork-inherit",
    "unix-socket",
    "ptrace-deny",
    "inbound",
    "bpffs-overmount",
    "af-packet",
    "stop-token",
    "pin-absent",
    "missing-path",
    "host-wide",
    "hard-link",
    "enrolled-root",
    "nonce-truncate",
    "ledger-forgery",
    "ptrace-task",
    "host-enroll",
    "same-boundary",
    "oom",
    "escapes",
    "clock",
    "k8s",
    "vlan",
    "reboot-pre",
    "reboot",
    "reboot-post",
    "compare",
    "expired-key",
    "uninstall",
)


class Harness:
    REBOOT_COMMAND = "reboot-cmd"
    ARCHIVE_COMMAND = "archive-cmd"

    def __init__(self, phases: tuple[str, ...]) -> None:
        self.phases = phases

    def phases_for(self, name: str) -> tuple[str, ...]:
        if name != "full":
            raise AssertionError(name)
        return self.phases

    def ssh_phase_command(self, phase: str) -> str:
        if phase == "missing":
            raise SystemExit("phase")
        return f"phase:{phase}"


class Stage4PlanTests(unittest.TestCase):
    def test_project_must_match_exactly(self) -> None:
        stage4_plan.require_project("vantio-lab-oct08")
        mutated = "vantio-lab-oct08".replace("8", "9")
        self.assertNotEqual(mutated, "vantio-lab-oct08")
        for project in (
            "other-project",
            "vantio-lab-oct08-extra",
            "prefix-vantio-lab-oct08",
            "",
            "Navera",
            "navera",
            "vantio-lab-navera",
            mutated,
        ):
            with self.assertRaises(stage4_plan.PlanError) as caught:
                stage4_plan.require_project(project)
            self.assertEqual(caught.exception.reason, "project")

    def test_soak_bounds(self) -> None:
        self.assertEqual(stage4_plan.parse_soak_minutes(""), 60)
        self.assertEqual(stage4_plan.parse_soak_minutes(None), 60)
        self.assertEqual(stage4_plan.parse_soak_minutes("60"), 60)
        self.assertEqual(stage4_plan.parse_soak_minutes("240"), 240)
        for value in ("241", "0", "60m", "-1", "1.5"):
            with self.assertRaises(stage4_plan.PlanError) as caught:
                stage4_plan.parse_soak_minutes(value)
            self.assertEqual(caught.exception.reason, "soak_minutes")

    def test_bpf_token_is_not_a_substring(self) -> None:
        self.assertTrue(stage4_plan.bpf_lsm_active("lockdown,capability,bpf"))
        self.assertTrue(stage4_plan.bpf_lsm_active(" bpf "))
        self.assertFalse(stage4_plan.bpf_lsm_active("lockdown,capability,apparmor"))
        self.assertFalse(stage4_plan.bpf_lsm_active("bpf_foo,ebpf"))

    def test_image_and_uname_are_exact(self) -> None:
        image = "projects/debian-cloud/global/images/debian-13-trixie-v20261102"
        self.assertTrue(stage4_plan.image_matches(image, stage4_plan.DEBIAN_IMAGE))
        self.assertFalse(stage4_plan.image_matches(image, stage4_plan.UBUNTU_IMAGE))
        self.assertTrue(stage4_plan.uname_matches(stage4_plan.DEBIAN_UNAME, stage4_plan.DEBIAN_UNAME))
        self.assertFalse(
            stage4_plan.uname_matches("6.12.107+deb13-cloud-amd64", stage4_plan.DEBIAN_UNAME)
        )
        self.assertFalse(stage4_plan.uname_matches("7.0.0-38-generic", stage4_plan.UBUNTU_UNAME))
        self.assertEqual(stage4_plan.DEBIAN_IMAGE, "debian-13-trixie-v20261102")
        self.assertEqual(stage4_plan.DEBIAN_UNAME, "6.12.116+deb13-cloud-amd64")
        self.assertEqual(stage4_plan.UBUNTU_IMAGE, "ubuntu-2604-resolute-amd64-v20261107")
        self.assertEqual(stage4_plan.UBUNTU_UNAME, "7.0.0-1016-gcp")

    def test_refusal_needs_a_failed_loader_and_whole_fields(self) -> None:
        text = "INSTALL_ENFORCEMENT_READINESS_BLOCKED bpf_lsm_inactive NOT ENFORCING"
        self.assertTrue(stage4_plan.refusal_holds(text, 1, [], []))
        self.assertFalse(stage4_plan.refusal_holds("", 1, [], []))
        self.assertFalse(stage4_plan.refusal_holds(text, 0, [], []))
        glued = "xINSTALL_ENFORCEMENT_READINESS_BLOCKED bpf_lsm_inactive_extra NOTX ENFORCING"
        self.assertFalse(stage4_plan.refusal_holds(glued, 1, [], []))
        mutated = text.replace("bpf_lsm_inactive", "bpf_lsm_inactivx", 1)
        self.assertNotEqual(mutated, text)
        self.assertFalse(stage4_plan.refusal_holds(mutated, 1, [], []))
        fresh = stage4_plan.new_vantio_programs([], ["id 1 name vantio_prog"])
        self.assertFalse(stage4_plan.refusal_holds(text, 1, [], fresh))
        self.assertTrue(stage4_plan.refusal_holds(text, 1, ["id 9 name other"], ["id 9 name other"]))
        self.assertFalse(stage4_plan.refusal_holds(text, 1, ["listing=unavailable"], []))
        self.assertEqual(stage4_plan.enforcement_claim(), "NOT_PROVEN")

    def test_create_argv_is_on_demand_and_labelled(self) -> None:
        startup = "/tmp/stage4-startup.sh"
        for role, image in (
            ("debian", stage4_plan.DEBIAN_IMAGE),
            ("ubuntu", stage4_plan.UBUNTU_IMAGE),
            ("refuse", stage4_plan.DEBIAN_IMAGE),
        ):
            argv = stage4_plan.create_argv("123", role, startup)
            flat = " ".join(argv)
            self.assertIn("--no-address", argv)
            self.assertIn("--boot-disk-type=pd-standard", argv)
            self.assertIn("--boot-disk-size=10GB", argv)
            self.assertIn(f"--boot-disk-name={stage4_plan.instance_name('123', role)}", argv)
            self.assertIn("--boot-disk-labels=vantio-lab=stage4,run-id=123", argv)
            self.assertIn("--machine-type=e2-standard-2", argv)
            self.assertIn(f"--image={image}", argv)
            self.assertNotIn("--image-family", flat)
            self.assertIn("--project=vantio-lab-oct08", argv)
            self.assertIn("--labels=vantio-lab=stage4,run-id=123", argv)
            self.assertIn("--tags=vantio-gcp-lab", argv)
            self.assertIn(f"--metadata-from-file=startup-script={startup}", argv)
            self.assertNotIn("preemptible", flat.lower())
            self.assertNotIn("spot", flat.lower())
            self.assertNotIn("accelerator", flat.lower())
        self.assertEqual(stage4_plan.instance_name("123", "refuse"), "s4-123-off")

    def test_dispatch_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        stage4_plan.require_dispatch_only(text)
        self.assertEqual(stage4_plan.workflow_on_keys(text), {"workflow_dispatch"})
        pushed = "on:\n  workflow_dispatch:\n  push:\n    branches: [main]\n"
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_dispatch_only(pushed)
        self.assertEqual(caught.exception.reason, "workflow_trigger")
        scheduled = "on:\n  schedule:\n    - cron: '0 0 * * *'\n"
        with self.assertRaises(stage4_plan.PlanError):
            stage4_plan.require_dispatch_only(scheduled)

    def test_wif_reuse_rejects_a_direct_auth_step(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        stage4_plan.require_wif_reuse(text)
        self.assertNotIn(stage4_plan.AUTH_ACTION, text)
        self.assertIn(stage4_plan.WIF_REUSE, text)
        self.assertNotIn("environment:", text)
        authed = text.replace(
            "permissions:",
            "uses: google-github-actions/auth@ba79af03959ebeac9769e648f473a284504d9193\npermissions:",
            1,
        )
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_wif_reuse(authed)
        self.assertEqual(caught.exception.reason, "wif_auth")
        mutated = text.replace("# oidc-trust", "# oidc-trusx", 1)
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_wif_reuse(mutated)
        self.assertEqual(caught.exception.reason, "wif_reuse")

    def test_cost_gate_keeps_the_stage4_jobs_on_the_existing_environment(self) -> None:
        text = COST_GATE.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        self.assertEqual(doc["env"]["GCP_LAB_PROJECT"], "vantio-lab-oct08")
        self.assertEqual(
            doc["env"]["GCP_LAB_WIF_PROVIDER"],
            "projects/910881070503/locations/global/workloadIdentityPools/github-actions/providers/github",
        )
        self.assertEqual(
            doc["env"]["GCP_LAB_SERVICE_ACCOUNT"],
            "vantio-lab-gha@vantio-lab-oct08.iam.gserviceaccount.com",
        )
        enrolled = (
            "${{ fromJSON(vars.VANTIO_ENROLLED_RUNNER == 'true' && "
            "'[\"self-hosted\", \"vantio-enrolled\"]' || '\"ubuntu-latest\"') }}"
        )
        for job_id in ("stage4-target", "stage4-teardown", "stage4-verify"):
            job = doc["jobs"][job_id]
            self.assertEqual(job["runs-on"], enrolled)
            self.assertEqual(job["steps"][-1]["name"], "Upload Optics observation log")
        self.assertEqual(doc["jobs"]["stage4-target"]["environment"], "gcp-lab")
        self.assertEqual(doc["jobs"]["stage4-target"]["timeout-minutes"], 360)
        self.assertEqual(doc["jobs"]["stage4-teardown"]["timeout-minutes"], 20)
        self.assertEqual(doc["jobs"]["stage4-verify"]["timeout-minutes"], 15)
        self.assertIn("always()", doc["jobs"]["stage4-teardown"]["if"])
        self.assertIn("always()", doc["jobs"]["stage4-verify"]["if"])
        self.assertEqual(
            doc["jobs"]["stage4-target"]["strategy"]["matrix"]["role"],
            ["debian", "ubuntu", "refuse"],
        )
        self.assertIn("inputs.stage4 == '1'", doc["jobs"]["stage4-target"]["if"])
        self.assertIn("stage4_drive.py summary", text)
        self.assertIn("GITHUB_STEP_SUMMARY", text)
        caller_text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(caller_text.count("secrets.W3_LAB_PRIVATE_BUNDLE_TOKEN"), 1)
        self.assertIn("DRAFT ONLY", caller_text)
        self.assertIn("slated for revocation", caller_text)
        caller = yaml.safe_load(caller_text)
        self.assertEqual(
            caller["jobs"]["lab"]["uses"],
            "vantioai/vantio-open-core/.github/workflows/gcp-lab-cost-gate.yml@main",
        )
        self.assertEqual(caller["jobs"]["lab"]["with"]["stage4"], "1")
        self.assertEqual(caller["concurrency"]["group"], "vantio-gce-slot")
        self.assertLess(
            caller_text.index("gcp-stage4-lab.yml@refs/heads/main"),
            caller_text.index("secrets.W3_LAB_PRIVATE_BUNDLE_TOKEN"),
        )
        fetch_steps = caller["jobs"]["fetch-pe"]["steps"]
        self.assertEqual(fetch_steps[0]["name"], "Require main on vantio-open-core")
        self.assertLess(
            caller_text.index("Require main on vantio-open-core"),
            caller_text.index("repository: vantioai/vantio-phantom-engine"),
        )
        for job_id in ("stage4-teardown", "stage4-verify"):
            step_names = [step.get("name") for step in doc["jobs"][job_id]["steps"]]
            self.assertEqual(step_names[0], "Require main on vantio-open-core")
            self.assertLess(step_names.index("Require main on vantio-open-core"), step_names.index("Checkout"))
            self.assertLess(
                step_names.index("Require main on vantio-open-core"),
                step_names.index("Authenticate with workload identity"),
            )
        self.assertEqual(
            doc["jobs"]["stage4-target"]["outputs"]["overall"],
            "${{ steps.ds.outputs.overall }}",
        )
        self.assertEqual(
            doc["jobs"]["stage4-target"]["outputs"]["ds_hold"],
            "${{ steps.ds.outputs.ds_hold }}",
        )
        self.assertNotIn("harness_ref:", caller_text)
        self.assertIn("build_pe_loader.sh", caller_text)
        self.assertIn('STAGE4_AFTER_AUTH: "1"', text)
        self.assertNotIn("gcp-stage4-lab.yml", lab_auto.WORKFLOWS)
        self.assertNotIn("gcp-stage4-lab.yml", lab_auto.attribute_condition())
        stage4_jobs = text.split("  stage4-target:", 1)[1]
        for line in _run_bodies(stage4_jobs):
            self.assertNotIn("${{", line)
        for line in _run_bodies(caller_text):
            self.assertNotIn("${{", line)
        target = doc["jobs"]["stage4-target"]
        names = [step.get("name") for step in target["steps"]]
        self.assertEqual(names[0], "Require main on vantio-open-core")
        self.assertLess(names.index("Require main on vantio-open-core"), names.index("Checkout"))
        self.assertLess(names.index("Require main on vantio-open-core"), names.index("Authenticate with workload identity"))
        allow = target["steps"][0]["run"]
        self.assertIn("gcp-stage4-lab.yml@refs/heads/main", allow)
        self.assertNotIn("gcp-lab-provision.yml", allow)
        self.assertNotIn("gcp-lab-cost-gate.yml", allow)
        gate_run = doc["jobs"]["gate"]["steps"][0]["run"]
        for caller in (
            "gcp-lab-cost-gate.yml@refs/heads/main",
            "gcp-lab-enforcement-proof.yml@refs/heads/main",
            "gcp-lab-provision.yml@refs/heads/main",
            "gcp-stage4-lab.yml@refs/heads/main",
        ):
            self.assertIn(caller, gate_run)
        narrowed = gate_run.replace("gcp-stage4-lab.yml@refs/heads/main", "gcp-stage4-lab.yml@refs/heads/other", 1)
        self.assertNotIn("gcp-stage4-lab.yml@refs/heads/main", narrowed)
        self.assertLess(names.index("Refuse static GCP keys"), names.index("Authenticate with workload identity"))
        self.assertLess(names.index("Authenticate with workload identity"), names.index("Run the lab role"))
        self.assertNotIn("apt-get", (ROOT / "scripts" / "lab" / "stage4_guest.sh").read_text(encoding="utf-8"))
        self.assertNotIn("rustup", (ROOT / "scripts" / "lab" / "stage4_guest.sh").read_text(encoding="utf-8"))

    def test_ds_hold_is_not_a_pass_and_not_exit_2(self) -> None:
        self.assertEqual(stage4_plan.DS_HOLD, "DS NOT WIRED — waiting on #85 run 26")
        text = stage4_plan.ds_hold_text("cursor/redteam-holds-8374")
        self.assertTrue(stage4_plan.ds_is_hold(0, text))
        self.assertFalse(stage4_plan.ds_is_hold(2, text))
        self.assertFalse(stage4_plan.ds_is_hold(0, "PASS"))
        mutated = text.replace("WIRED", "WIRFD", 1)
        self.assertNotEqual(mutated, text)
        self.assertFalse(stage4_plan.ds_is_hold(0, mutated))
        hidden = stage4_plan.ds_hold_text("run-go-ok", "run-go-ok")
        self.assertNotIn("run-go-ok", hidden)
        self.assertIn("ds_ref=rejected", hidden)
        self.assertTrue(stage4_plan.ds_is_hold(0, hidden))

    def test_ds_hold_cli_exits_zero(self) -> None:
        env = os.environ.copy()
        env["DS_REF"] = "7fd76a673d4ad06b9c74e8257585d716ea7305ea"
        env["RUN_GO"] = "run-go-ok"
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_plan.py"), "ds-hold"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(stage4_plan.ds_is_hold(completed.returncode, completed.stdout))
        self.assertNotIn("PASS", completed.stdout)
        self.assertIn("7fd76a673d4ad06b9c74e8257585d716ea7305ea", completed.stdout)

    def test_green_run_with_the_ds_hold_is_not_pass(self) -> None:
        rows = enforcement_proof.green_full_rows()
        self.assertGreaterEqual(len(rows), 6)
        for phase, lines, returncode in rows:
            self.assertTrue(enforcement_proof.phase_accepted(phase, lines, returncode))
        hold = stage4_plan.ds_hold_text("cursor/redteam-holds-8374")
        self.assertTrue(stage4_plan.ds_is_hold(0, hold))
        grade = enforcement_proof.overall_grade(rows, ds_wired=False)
        self.assertIn(grade, {"NOT_PROVEN", "INCOMPLETE"})
        self.assertNotEqual(grade, "PASS")
        self.assertEqual(grade, "INCOMPLETE")
        refused = [
            (phase, ["compare=REFUSED_LSM"] if phase == "compare" else list(lines), returncode)
            for phase, lines, returncode in rows
        ]
        self.assertFalse(enforcement_proof.phase_accepted("compare", ["compare=REFUSED_LSM"], 0))
        self.assertNotEqual(enforcement_proof.overall_grade(refused, ds_wired=False), "PASS")
        self.assertNotEqual(enforcement_proof.overall_grade(rows, ds_wired=True), "PASS")
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "DS_REF": "cursor/redteam-holds-8374",
                    "RUN_GO": "run-go-ok",
                    "HARNESS_CANDIDATES": str(ROOT),
                    "STAGE4_LOG_DIR": tmp,
                }
            )
            env.pop("GCP_LAB_EXECUTE", None)
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "summary"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(stage4_plan.DS_HOLD, completed.stdout)
            self.assertIn("OVERALL INCOMPLETE", completed.stdout)
            self.assertNotIn("OVERALL PASS", completed.stdout)
            self.assertNotIn("compare=PASS", completed.stdout)
            self.assertNotRegex(completed.stdout, r"(?m)^OVERALL PASS$")
            self.assertIn("live_enforcement=NOT_PROVEN", completed.stdout)
            self.assertIn("observed_phases=0", completed.stdout)
            self.assertNotIn("green_full_rows", inspect.getsource(stage4_drive._summary_rows))
            output = Path(tmp) / "github-output.txt"
            env["GITHUB_OUTPUT"] = str(output)
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "summary"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            recorded = output.read_text(encoding="utf-8")
        self.assertIn("overall=INCOMPLETE", recorded)
        self.assertIn(stage4_plan.DS_HOLD, recorded)
        self.assertNotIn("overall=PASS", recorded)

    def test_summary_grades_the_observed_log_not_the_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "DS_REF": "cursor/redteam-holds-8374",
                    "RUN_GO": "run-go-ok",
                    "HARNESS_CANDIDATES": str(ROOT),
                    "STAGE4_LOG_DIR": tmp,
                }
            )
            env.pop("GCP_LAB_EXECUTE", None)
            log = Path(tmp) / "phase-rows.txt"
            log.write_text(
                "phase=compare rc=0\ncompare=PASS\n.\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "summary"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("observed_phases=1", completed.stdout)
            self.assertIn("OVERALL INCOMPLETE", completed.stdout)
            self.assertNotIn("compare=PASS", completed.stdout)
            self.assertNotIn("OVERALL PASS", completed.stdout)
            mutated = log.read_text(encoding="utf-8").replace("compare=PASS", "compare=REFUSED_LSM", 1)
            self.assertNotEqual(mutated, log.read_text(encoding="utf-8"))
            log.write_text(mutated, encoding="utf-8")
            mutated_run = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "summary"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(mutated_run.returncode, 0, mutated_run.stderr)
            self.assertIn("observed_phases=1", mutated_run.stdout)
            self.assertIn("OVERALL INCOMPLETE", mutated_run.stdout)
            broken = Path(tmp) / "phase-rows.txt"
            broken.write_text("phase=compare rc=0\ncompare=PASS\n", encoding="utf-8")
            refused = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "summary"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        self.assertEqual(refused.returncode, 2)
        self.assertIn("phase_log", refused.stderr)
        self.assertNotIn("OVERALL", refused.stdout)

    def test_unbooted_debs_do_not_create_a_vm(self) -> None:
        self.assertFalse(stage4_plan.deb_boot_observed(None))
        self.assertFalse(stage4_plan.deb_boot_observed("debian13-and-ubuntu2605"))
        self.assertTrue(stage4_plan.deb_boot_observed(stage4_plan.DEB_BOOT_TOKEN))
        env = {
            "GCP_LAB_PROJECT": "vantio-lab-oct08",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "SOAK_MINUTES": "60",
            "RUN_GO": "run-go-ok",
            "HOST_NAME": "labhost",
            "HARNESS_CANDIDATES": str(ROOT),
            "ROLE": "debian",
            "GCP_LAB_EXECUTE": "1",
            "PATH": os.environ.get("PATH", ""),
        }
        for role in ("debian", "refuse"):
            env["ROLE"] = role
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "target"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(completed.returncode, 2, role)
            self.assertIn("deb_boot", completed.stderr)
            self.assertNotIn("instances", completed.stdout)
            self.assertNotIn("gcloud", completed.stdout)

    def test_uname_failure_deletes_the_instance(self) -> None:
        with (
            mock.patch.object(stage4_drive, "_open_vm", return_value="s4-7-deb"),
            mock.patch.object(stage4_drive, "_wait_ssh", return_value="boot"),
            mock.patch.object(stage4_drive, "_copy_guest_scripts"),
            mock.patch.object(stage4_drive, "_preflight", side_effect=stage4_plan.PlanError("preflight")),
            mock.patch.object(stage4_drive, "_delete_instance") as delete,
        ):
            with self.assertRaises(stage4_plan.PlanError) as caught:
                stage4_drive._prepare_guest("debian")
        self.assertEqual(caught.exception.reason, "preflight")
        delete.assert_called_once_with("s4-7-deb")
        env = os.environ.copy()
        env.pop("GCP_LAB_EXECUTE", None)
        with mock.patch.dict(os.environ, env, clear=True):
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import stage4_drive; stage4_drive._delete_instance('s4-7-deb')",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT / "scripts" / "lab",
                env={**env, "PYTHONPATH": str(ROOT / "scripts" / "lab")},
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--delete-disks=all", completed.stdout)
        self.assertIn("instances", completed.stdout)

    def test_short_harness_is_rejected(self) -> None:
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_drive.phase_commands(Harness(FULL[:8]))
        self.assertEqual(caught.exception.reason, "harness_phase_count")

    def test_full_harness_archives_before_the_second_compare(self) -> None:
        commands = stage4_drive.phase_commands(Harness(FULL))
        names = [name for name, _command in commands]
        self.assertEqual(names.count("compare"), 2)
        second = len(names) - 1 - names[::-1].index("compare")
        self.assertEqual(names[second - 1], "archive")
        self.assertIn(("reboot", "reboot-cmd"), commands)
        joined = " ".join(command for _name, command in commands)
        self.assertNotIn("enforcement_proof.run", joined)
        self.assertNotIn("run_proof", joined)

    def test_open_core_harness_slice_is_accepted(self) -> None:
        commands = stage4_drive.phase_commands(enforcement_proof)
        names = [name for name, _command in commands]
        self.assertEqual(tuple(enforcement_proof.phases_for("full")).count("compare"), 2)
        self.assertEqual(names.count("compare"), 2)
        second = len(names) - 1 - names[::-1].index("compare")
        self.assertEqual(names[second - 1], "archive")
        self.assertIn(enforcement_proof.REBOOT_COMMAND, [command for _name, command in commands])

    def test_missing_phase_command_fails_closed(self) -> None:
        phases = tuple("missing" if phase == "file-deny" else phase for phase in FULL)
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_drive.phase_commands(Harness(phases))
        self.assertEqual(caught.exception.reason, "phase")

    def test_static_credentials_and_events(self) -> None:
        stage4_plan.require_event("workflow_dispatch")
        stage4_plan.require_event("workflow_call")
        for empty in (None, ""):
            with self.assertRaises(stage4_plan.PlanError) as caught:
                stage4_plan.require_event(empty)
            self.assertEqual(caught.exception.reason, "event")
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_event("schedule")
        self.assertEqual(caught.exception.reason, "event")
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_no_static_creds({"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/key.json"})
        self.assertEqual(caught.exception.reason, "static_credentials")
        stage4_plan.require_no_static_creds(
            {"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/wif.json"},
            after_auth=True,
        )
        stage4_plan.require_no_static_creds(
            {"CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE": "/tmp/wif.json"},
            after_auth=True,
        )
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_no_static_creds({"GCP_SA_KEY": "/tmp/key.json"}, after_auth=True)
        self.assertEqual(caught.exception.reason, "static_credentials")

    def test_remaining_names(self) -> None:
        self.assertEqual(stage4_plan.remaining_names(""), [])
        self.assertEqual(stage4_plan.remaining_names("\n"), [])
        self.assertEqual(stage4_plan.remaining_names("s4-1-deb us-central1-a\n"), ["s4-1-deb"])

    def test_stop_script_stays_inside_the_job_cap(self) -> None:
        self.assertIn("360min", stage4_plan.stop_script())
        with self.assertRaises(stage4_plan.PlanError):
            stage4_plan.stop_script(361)

    def test_guard_finds_the_local_harness_without_a_ds_failure(self) -> None:
        problems = stage4_plan.guard_problems(
            project="vantio-lab-oct08",
            event="workflow_dispatch",
            env={},
            soak="60",
            run_go="run-go-ok",
            host_name="labhost",
            harness_candidates=[ROOT],
        )
        self.assertEqual(problems, [])
        missing = stage4_plan.guard_problems(
            project="vantio-lab-oct08",
            event="workflow_dispatch",
            env={},
            soak="60",
            run_go="run-go-ok",
            host_name="labhost",
            harness_candidates=[Path("/tmp/stage4-no-harness")],
        )
        self.assertEqual(missing, ["harness_entrypoint_missing"])
        original = stage4_plan.HARNESS_FILES
        try:
            stage4_plan.HARNESS_FILES = ("scripts/gcp/enforcement_proof.pyX",)
            self.assertIsNone(stage4_plan.harness_root([ROOT]))
        finally:
            stage4_plan.HARNESS_FILES = original

    def test_guard_cli_rejects_a_foreign_project_without_gcloud(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "GCP_LAB_PROJECT": "other-project",
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                "SOAK_MINUTES": "241",
                "RUN_GO": "run-go-ok",
                "HOST_NAME": "labhost",
                "HARNESS_CANDIDATES": "/tmp/stage4-no-harness",
            }
        )
        env.pop("GCP_LAB_EXECUTE", None)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "guard"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("project", completed.stderr)
        self.assertIn("soak_minutes", completed.stderr)
        self.assertIn("harness_entrypoint_missing", completed.stderr)
        self.assertIn("NOT_PROVEN", completed.stdout)
        self.assertNotIn("gcloud", completed.stdout)
        self.assertNotIn("PASS", completed.stdout)

    def test_target_without_execute_records_the_ds_hold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "GCP_LAB_PROJECT": "vantio-lab-oct08",
                    "GITHUB_EVENT_NAME": "workflow_dispatch",
                    "SOAK_MINUTES": "60",
                    "RUN_GO": "run-go-ok",
                    "HOST_NAME": "labhost",
                    "DS_REF": "cursor/redteam-holds-8374",
                    "HARNESS_CANDIDATES": str(ROOT),
                    "ROLE": "debian",
                    "STAGE4_LOG_DIR": tmp,
                }
            )
            env.pop("GCP_LAB_EXECUTE", None)
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "target"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("execute=0", completed.stdout)
        self.assertIn("NOT_PROVEN", completed.stdout)
        self.assertIn(stage4_plan.DS_HOLD, completed.stdout)
        self.assertNotIn("PASS", completed.stdout)
        self.assertNotIn("gcloud", completed.stdout)
        self.assertNotIn("verified_removed=yes", completed.stdout)

    def test_verify_without_execute_does_not_claim_removed(self) -> None:
        env = os.environ.copy()
        env["GCP_LAB_PROJECT"] = "vantio-lab-oct08"
        env.pop("GCP_LAB_EXECUTE", None)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "verify"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("execute=0", completed.stdout)
        self.assertNotIn("verified_removed=yes", completed.stdout)

    def test_mask_rejects_a_newline_before_emitting_a_command(self) -> None:
        secret = "run-go-ok\n::set-env::oops"
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.mask_commands(secret, "labhost")
        self.assertEqual(caught.exception.reason, "mask_newline")
        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(
            stage4_plan.mask_commands("run%go-ok", ""),
            "::add-mask::run%25go-ok",
        )

    def test_grub_puts_lsm_last_on_the_default_token(self) -> None:
        desired = stage4_plan.desired_lsm("lockdown,capability,bpf", "require")
        self.assertEqual(desired, "lockdown,capability,bpf")
        dropin = stage4_plan.grub_dropin(desired)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lsm.cfg"
            path.write_text(dropin, encoding="utf-8")
            completed = subprocess.run(
                [
                    "bash",
                    "-c",
                    'GRUB_CMDLINE_LINUX="quiet lsm=lockdown,capability"; '
                    'GRUB_CMDLINE_LINUX_DEFAULT="console=ttyS0 lsm=stock"; '
                    f'. "{path}"; printf "%s\\n%s\\n" "$GRUB_CMDLINE_LINUX" "$GRUB_CMDLINE_LINUX_DEFAULT"',
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        linux, default = completed.stdout.splitlines()
        self.assertNotIn("lsm=", linux)
        self.assertTrue(default.endswith(f"lsm={desired}"))
        self.assertEqual(stage4_plan.last_lsm(f"quiet {default}"), desired)
        earlier = f"lsm={desired} lsm=stock"
        self.assertNotEqual(stage4_plan.last_lsm(earlier), desired)
        with self.assertRaises(stage4_plan.PlanError):
            stage4_plan.grub_dropin(desired + " ")
        image = "projects/debian-cloud/global/images/" + stage4_plan.DEBIAN_IMAGE
        code = stage4_plan.main(
            [
                "stage4_plan.py",
                "guest-preflight",
                image,
                stage4_plan.DEBIAN_UNAME,
                "lockdown,bpf",
                stage4_plan.DEBIAN_IMAGE,
                stage4_plan.DEBIAN_UNAME,
                "require",
                desired,
                f"quiet lsm={desired[:-1]}x",
            ]
        )
        self.assertEqual(code, 2)

    def test_image_describe_miss_does_not_create(self) -> None:
        calls: list[list[str]] = []

        def fake_run(argv: list[str], check: bool) -> subprocess.CompletedProcess[str]:
            calls.append(list(argv))
            if "images" in argv:
                return subprocess.CompletedProcess(argv, 1, "", "NOT_FOUND")
            return subprocess.CompletedProcess(argv, 0, "created\n", "")

        with mock.patch.object(stage4_drive, "_run", fake_run):
            with self.assertRaises(stage4_plan.PlanError) as caught:
                stage4_drive._open_vm("debian")
        self.assertEqual(caught.exception.reason, "image")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:4], ["compute", "images", "describe"])
        mutated = stage4_plan.DEBIAN_IMAGE[:-1] + ("x" if stage4_plan.DEBIAN_IMAGE[-1] != "x" else "y")

        def wrong_name(argv: list[str], check: bool) -> subprocess.CompletedProcess[str]:
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 0, mutated + "\n", "")

        calls.clear()
        with mock.patch.object(stage4_drive, "_run", wrong_name):
            with self.assertRaises(stage4_plan.PlanError) as caught:
                stage4_drive._open_vm("ubuntu")
        self.assertEqual(caught.exception.reason, "image")
        self.assertEqual(len(calls), 1)

    def test_unlabeled_disk_name_fails_verify(self) -> None:
        def fake_rows(kind: str, run_id: str) -> list[tuple[str, str]]:
            return []

        def fake_run(argv: list[str], check: bool) -> subprocess.CompletedProcess[str]:
            if any("name=s4-44-off" in part for part in argv):
                return subprocess.CompletedProcess(argv, 0, "s4-44-off\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        env = os.environ.copy()
        env.update({"GCP_LAB_PROJECT": "vantio-lab-oct08", "GCP_LAB_EXECUTE": "1", "GITHUB_RUN_ID": "44"})
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(stage4_drive, "_rows", fake_rows), mock.patch.object(stage4_drive, "_run", fake_run):
                code = stage4_drive._verify()
        self.assertEqual(code, 1)
        with self.assertRaises(stage4_plan.PlanError):
            stage4_plan.disk_by_name_argv("s4-44-ofx")

    def test_proof_env_uses_the_harness_pin(self) -> None:
        env = _proof_env_with_supplied("864289cb2c9c4135d74233c74c6655087de3f20e")
        self.assertIsNone(env)
        os.environ["PE_GIT_SHA"] = enforcement_proof.PE_GIT_SHA
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/wif.json"
        try:
            built = stage4_drive._proof_env(enforcement_proof, Path("loader"), Path("debs"))
        finally:
            os.environ.pop("PE_GIT_SHA", None)
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        self.assertEqual(built["PE_GIT_SHA"], enforcement_proof.PE_GIT_SHA)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", built)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SOURCE_SHA").write_text(enforcement_proof.PE_GIT_SHA + "\n", encoding="utf-8")
            stage4_drive.require_source_sha(root, enforcement_proof.PE_GIT_SHA)
            flipped = enforcement_proof.PE_GIT_SHA[:-1] + ("a" if enforcement_proof.PE_GIT_SHA[-1] != "a" else "b")
            (root / "SOURCE_SHA").write_text(flipped + "\n", encoding="utf-8")
            with self.assertRaises(stage4_plan.PlanError) as caught:
                stage4_drive.require_source_sha(root, enforcement_proof.PE_GIT_SHA)
            self.assertEqual(caught.exception.reason, "pe_git_sha")

    def test_harness_ref_allowlist_rejects_a_caller_ref(self) -> None:
        stage4_plan.require_harness_ref("")
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_harness_ref("main")
        self.assertEqual(caught.exception.reason, "harness_ref")
        self.assertEqual(stage4_plan.HARNESS_FILES, ("scripts/gcp/enforcement_proof.py",))
        self.assertNotIn("guest_phases.sh", stage4_plan.HARNESS_FILES)
        self.assertNotIn("proof_grade.py", stage4_plan.HARNESS_FILES)

    def test_empty_event_fails_the_guard_cli(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "GCP_LAB_PROJECT": "vantio-lab-oct08",
                "GITHUB_EVENT_NAME": "",
                "SOAK_MINUTES": "60",
                "RUN_GO": "run-go-ok",
                "HOST_NAME": "labhost",
                "HARNESS_CANDIDATES": str(ROOT),
            }
        )
        env.pop("GCP_LAB_EXECUTE", None)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "lab" / "stage4_drive.py"), "guard"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("event", completed.stderr)
        self.assertNotIn("gcloud", completed.stdout)


def _run_bodies(text: str) -> list[str]:
    bodies: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if re.match(r"\s*run:\s*\|\s*$", lines[index]):
            indent = len(lines[index]) - len(lines[index].lstrip(" "))
            index += 1
            while index < len(lines):
                blank = lines[index].strip() == ""
                here = len(lines[index]) - len(lines[index].lstrip(" "))
                if not blank and here <= indent:
                    break
                bodies.append(lines[index])
                index += 1
            continue
        index += 1
    return bodies


def _proof_env_with_supplied(supplied: str) -> dict[str, str] | None:
    os.environ["PE_GIT_SHA"] = supplied
    try:
        stage4_drive._proof_env(enforcement_proof, Path("loader"), Path("debs"))
    except stage4_plan.PlanError as exc:
        if exc.reason != "pe_git_sha":
            raise
        return None
    else:
        return {"unexpected": "accepted"}
    finally:
        os.environ.pop("PE_GIT_SHA", None)


if __name__ == "__main__":
    unittest.main()
