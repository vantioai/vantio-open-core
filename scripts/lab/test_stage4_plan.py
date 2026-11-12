"""Plan tests for the stage 4 lab workflow. They do not call gcloud."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
GCP_DIR = ROOT / "scripts" / "gcp"
if str(GCP_DIR) not in sys.path:
    sys.path.insert(0, str(GCP_DIR))

import enforcement_proof
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

    def test_refusal_needs_every_line_and_no_new_pin(self) -> None:
        text = "\n".join(stage4_plan.REFUSAL_LINES)
        self.assertTrue(stage4_plan.refusal_holds(text, False))
        self.assertFalse(stage4_plan.refusal_holds(text, True))
        self.assertFalse(stage4_plan.refusal_holds("NOT ENFORCING\n", False))
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
            self.assertIn("--machine-type=e2-standard-2", argv)
            self.assertIn(f"--image={image}", argv)
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
        self.assertIn("stage4_plan.py ds-hold", text)
        caller = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        self.assertEqual(
            caller["jobs"]["lab"]["uses"],
            "vantioai/vantio-open-core/.github/workflows/gcp-lab-cost-gate.yml@main",
        )
        self.assertEqual(caller["jobs"]["lab"]["with"]["stage4"], "1")

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
        stage4_plan.require_event(None)
        stage4_plan.require_event("workflow_dispatch")
        stage4_plan.require_event("workflow_call")
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_event("schedule")
        self.assertEqual(caught.exception.reason, "event")
        with self.assertRaises(stage4_plan.PlanError) as caught:
            stage4_plan.require_no_static_creds({"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/key.json"})
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


if __name__ == "__main__":
    unittest.main()
