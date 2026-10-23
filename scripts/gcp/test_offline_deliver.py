#!/usr/bin/env python3
"""Guards for offline GCP delivery. These tests do not call GCP."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from decimal import Decimal
from unittest import mock
from pathlib import Path

import lab_auto as lab
import offline_deliver as od

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "scripts" / "aws"))
import enterprise_bundle  # noqa: E402


def _trust_tar(directory: Path, body: bytes, *, extra: bytes | None = None, name: str = od.TRUST_MEMBER) -> Path:
    path = directory / "contract.tar"
    with tarfile.open(path, "w") as tar:
        guest = tarfile.TarInfo("guest_rows.py")
        guest.size = 1
        tar.addfile(guest, io.BytesIO(b"x"))
        info = tarfile.TarInfo(name)
        info.size = len(body)
        tar.addfile(info, io.BytesIO(body))
        if extra is not None:
            bad = tarfile.TarInfo("note.txt")
            bad.size = len(extra)
            tar.addfile(bad, io.BytesIO(extra))
    return path


class OfflineDeliverTest(unittest.TestCase):
    def test_redteam_rows_pull_names_a_refused_remote(self) -> None:
        self.assertIn("/tmp/redteam-rows.json", od.SCP_FROM_REMOTES)
        self.assertIn("/var/lib/vantio-lab/redteam-rows.json", od.SCP_FROM_REMOTES)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as caught:
                od._scp_from(od.LAB_PROJECT, "vantio-gcp-lab-1", "/tmp/not-a-lab-file.json", Path("/tmp/not-a-lab-file.json"))
        self.assertEqual(str(caught.exception), "scp")
        self.assertIn("scp_refused remote=/tmp/not-a-lab-file.json", err.getvalue())
        argv_err = io.StringIO()
        with contextlib.redirect_stderr(argv_err):
            with self.assertRaises(SystemExit):
                od.iap_scp_argv(od.LAB_PROJECT, [], "vantio-gcp-lab-1:/tmp/x")
        self.assertIn("scp_refused no_sources", argv_err.getvalue())

    def test_project_and_run_id_stay_on_the_lab(self) -> None:
        self.assertEqual(od.require_lab_project("vantio-lab-oct08"), "vantio-lab-oct08")
        with mock.patch.dict(os.environ, {"VANTIO_PARTNER_MARKERS": "partner-x"}):
            for project in ("vantio-lab-partner-x", "other-project", "vantio-lab-other"):
                with self.assertRaises(SystemExit):
                    od.require_lab_project(project)
        with self.assertRaises(SystemExit):
            od.object_names("../1")
        self.assertEqual(od.object_names("12"), ("12/seal.oci.tar", "12/contract.tar"))
        self.assertEqual(od.instance_name("12"), "vantio-gcp-lab-12")

    def test_public_pin_is_not_the_seal(self) -> None:
        with self.assertRaises(SystemExit):
            od.verify_seal_file(Path("/nope"), od.PUBLIC_INSTALLER_PIN)
        with self.assertRaises(SystemExit):
            od.guest_command(od.PUBLIC_INSTALLER_PIN, "enterprise")
        bundle = (ROOT / "scripts/aws/enterprise_bundle.py").read_text(encoding="utf-8")
        self.assertEqual(enterprise_bundle.PLUMBING_ONLY_SEAL, od.POLICY_ALLOW_SEAL)
        self.assertNotEqual(enterprise_bundle.POLICY_ALLOW_SEAL, od.PUBLIC_INSTALLER_PIN)
        self.assertNotIn(od.POLICY_ALLOW_SEAL, bundle)
        self.assertIn(od.TRUST_SHA256, bundle)

    def test_contract_trust_accepts_only_the_nonprod_key(self) -> None:
        body = json.dumps(
            {
                "keys": [
                    {
                        "not_a_production_root": True,
                        "environment": "NON-PRODUCTION",
                        "label": "TEST",
                        "key_id": od.TRUST_KEY_ID,
                    }
                ]
            }
        ).encode()
        with tempfile.TemporaryDirectory() as tmp:
            path = _trust_tar(Path(tmp), body)
            digest = hashlib.sha256(body).hexdigest()
            self.assertEqual(len(od.verify_contract_trust(path, digest)), 64)
            with self.assertRaises(SystemExit):
                od.verify_contract_trust(path, "a" * 64)
        private = b"-----BEGIN PRIVATE KEY-----\nYQ==\n-----END PRIVATE KEY-----\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = _trust_tar(Path(tmp), body, extra=private)
            with self.assertRaises(SystemExit):
                od.verify_contract_trust(path, hashlib.sha256(body).hexdigest())

    def test_create_argv_is_offline_and_keyless(self) -> None:
        name = "vantio-gcp-lab-12"
        plan = {
            "project_id": "vantio-lab-oct08",
            "name": name,
            "public_ip": False,
            "service_account": None,
            "network": od.NETWORK,
            "subnet": od.SUBNET,
            "image_family": od.IMAGE_FAMILY,
            "image_project": od.IMAGE_PROJECT,
            "labels": od.offline_labels(1_800_000_000, 120),
        }
        argv = od.offline_create_argv(plan, "/tmp/startup.sh")
        joined = " ".join(argv)
        self.assertIn("--no-address", argv)
        self.assertIn("--no-service-account", argv)
        self.assertIn("--no-scopes", argv)
        self.assertIn("--network=vantio-lab-offline", argv)
        self.assertIn("--subnet=vantio-lab-offline-usc1", argv)
        self.assertIn("--tags=vantio-gcp-lab", argv)
        self.assertIn("--metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE", argv)
        self.assertIn("--image-family=ubuntu-2404-lts-amd64", argv)
        self.assertIn("--image-project=ubuntu-os-cloud", argv)
        self.assertIn("--shielded-secure-boot", argv)
        self.assertNotIn("--address=", joined)
        self.assertNotIn("debian-cloud", joined)
        self.assertFalse(lab.names_partner(joined))
        startup = od.offline_startup(120)
        self.assertNotIn("apt-get", startup)
        self.assertIn("shutdown -h +120", startup)
        self.assertIn("--machine-type=e2-micro", argv)
        self.assertIn("--boot-disk-size=10GB", argv)
        brain_plan = dict(plan)
        brain_plan["machine_type"] = "e2-standard-4"
        brain_plan["boot_disk_gb"] = "30GB"
        brain_argv = od.offline_create_argv(brain_plan, "/tmp/startup.sh")
        brain_joined = " ".join(brain_argv)
        self.assertIn("--machine-type=e2-standard-4", brain_argv)
        self.assertIn("--boot-disk-size=30GB", brain_argv)
        self.assertIn("--no-address", brain_argv)
        self.assertNotIn("--address=", brain_joined)
        self.assertFalse(lab.names_partner(brain_joined))
        refused = dict(brain_plan)
        refused["machine_type"] = "n2-standard-4"
        with self.assertRaises(SystemExit):
            od.offline_create_argv(refused, "/tmp/startup.sh")

    def test_iap_commands_expire_and_stay_private(self) -> None:
        ssh = od.iap_ssh_argv("vantio-lab-oct08", "vantio-gcp-lab-12", "true")
        self.assertIn("--tunnel-through-iap", ssh)
        self.assertIn("--ssh-key-expire-after=1h", ssh)
        scp = od.iap_scp_argv(
            "vantio-lab-oct08",
            ["seal.oci.tar"],
            "vantio-gcp-lab-12:/tmp/vantio-lab/seal.oci.tar",
        )
        self.assertIn("--tunnel-through-iap", scp)
        self.assertIn("--ssh-key-expire-after=1h", scp)
        self.assertIn("--scp-flag=-oServerAliveInterval=30", scp)
        self.assertIn("--scp-flag=-oServerAliveCountMax=20", scp)
        self.assertNotIn("--ssh-flag=-oServerAliveInterval=30", scp)
        miss = "ERROR: (gcloud.compute.os-login.ssh-keys.remove) Cannot find requested SSH key."
        self.assertTrue(od.scp_remove_miss_is_ignorable(miss))
        self.assertFalse(od.scp_remove_miss_is_ignorable(miss + "\nPermission denied"))
        self.assertFalse(od.scp_remove_miss_is_ignorable(""))
        self.assertIn("--ssh-flag=-oServerAliveInterval=30", ssh)
        back = od.iap_scp_argv(
            "vantio-lab-oct08",
            ["vantio-gcp-lab-12:/tmp/enterprise-pe-rows.json"],
            "/tmp/rows.json",
        )
        self.assertEqual(back[-2], "vantio-gcp-lab-12:/tmp/enterprise-pe-rows.json")
        with self.assertRaises(SystemExit):
            od.iap_scp_argv("vantio-lab-oct08", ["a:b"], "c:d")
        self.assertEqual(
            od.guest_command(od.POLICY_ALLOW_SEAL, "descendant-b1", "post"),
            f"bash {od.GUEST_DIR}/enterprise-rows.sh {od.POLICY_ALLOW_SEAL} descendant-b1 post",
        )
        self.assertEqual(
            od.guest_command("ab" * 32, "plumb"),
            f"bash {od.GUEST_DIR}/enterprise-rows.sh {'ab' * 32} plumb",
        )
        self.assertTrue(od.reboot_ready("abc", "def"))
        self.assertFalse(od.reboot_ready("abc", "abc"))

    def test_upload_falls_back_when_get_is_denied(self) -> None:
        self.assertEqual(od.classify_gcloud_cp(0, ""), "uploaded")
        self.assertEqual(od.classify_gcloud_cp(1, "403 storage.objects.get denied"), "fallback_json")
        self.assertEqual(od.classify_gcloud_cp(1, "network down"), "fail")

    def test_two_hour_estimate_stays_under_a_dime(self) -> None:
        amount = od.estimate_gross_usd(Decimal("2"))
        self.assertGreater(amount, Decimal("0"))
        self.assertLess(amount, Decimal("0.10"))

    def test_evidence_allowlist_drops_unknown_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "row.json"
            od.write_evidence(
                path,
                {
                    "note": "ghp_" + "a" * 20,
                    "seal_sha256": od.POLICY_ALLOW_SEAL,
                    "claim_cap": od.CLAIM_CAP,
                    "guest": {"private": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"},
                },
            )
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("ghp_", text)
            self.assertNotIn("PRIVATE KEY", text)
            self.assertNotIn("note", text)
            self.assertIn(od.POLICY_ALLOW_SEAL, text)
            self.assertEqual(od.content_range(0, 4, 8), "bytes 0-3/8")
            with self.assertRaises(SystemExit):
                od.content_range(0, 9, 8)

    def _passing_repeat(self, repeat: int) -> dict:
        return {
            "repeat": repeat,
            "enterprise_rc": 0,
            "descendant_rc": 0,
            "b1_pass": True,
            "reboot_observed": True,
            "kernel_btf": True,
            "kernel_bpffs": True,
            "kernel_cgroup_v2": True,
            "kernel_lsm": "lockdown,capability,landlock",
            "seal_checked": True,
            "rows": {"grant": {"result": "pass"}, "revoke": {"probe": {"nobody_errno": 13}}},
        }

    def test_loader_hold_requires_the_measured_pid_and_anchor(self) -> None:
        def sample(pid: int) -> dict:
            return {
                "deny_event": {
                    "lineage_anchor": 9058,
                    "path": od.CEILING_PATH,
                    "pid": pid,
                },
                "file_errno": 13,
                "lineage_anchor": 9058,
                "path": od.CEILING_PATH,
                "pid": pid,
            }

        stale = {
            "enrolled_after": {"file_errno": 0, "path": od.CEILING_PATH, "pid": 6895},
            "ndjson_denied_pids": [6131, 6143],
            "unenrolled_after": {"file_errno": 0},
            "while_loader_up": {"file_errno": 0, "path": od.CEILING_PATH, "pid": 6863},
        }
        self.assertEqual(od._loader_word("2d-crash-recovery", stale), "setup_invalid")
        side = {"errno": 13, "pid": 6870, "row_pid": 6870, "anchor": 6599, "row_count": 1,
                "rows_before": 0, "row_seen": True, "wait_s": 0.25}
        held = {
            "enroll_restart": {
                "held": True,
                "restart_rows": {"before": side, "after": dict(side, expected_anchor=6599, rows_before=1, row_count=2)},
            },
            "enrolled_after": sample(6895),
            "unenrolled_after": {"file_errno": 0, "path": od.CEILING_PATH, "pid": 6896},
            "while_loader_up": sample(6863),
        }
        self.assertEqual(od._loader_word("2d-crash-recovery", held), "held")
        # GCP 2D requires the restart rows (restart_rows_missing).
        self.assertEqual(od._loader_word("2d-crash-recovery", {k: v for k, v in held.items() if k != "enroll_restart"}), "fail")
        restart = {"deny_after": sample(7653), "deny_before": sample(7548)}
        self.assertEqual(od._loader_word("2c-upgrade-rollback", restart), "held")
        dropped = dict(held)
        dropped["enrolled_after"] = {"file_errno": 0, "path": od.CEILING_PATH, "pid": 6895}
        self.assertEqual(od._loader_word("2d-crash-recovery", dropped), "fail")
        mapped = dict(held)
        mapped["enrolled_after"] = {
            "file_errno": 13,
            "map_named": True,
            "path": od.CEILING_PATH,
            "pid": 3501,
        }
        self.assertEqual(od._loader_word("2d-crash-recovery", mapped), "fail")
        drained = dict(held)
        drained["enrolled_after"] = {
            "deny_event": {
                "lineage_anchor": 6599,
                "path": od.CEILING_PATH,
                "pid": 3501,
                "source": "deny_attr",
            },
            "file_errno": 13,
            "lineage_anchor": 6599,
            "map_named": True,
            "path": od.CEILING_PATH,
            "pid": 3501,
        }
        self.assertEqual(od._loader_word("2d-crash-recovery", drained), "held")
        unnamed = dict(mapped)
        unnamed["enrolled_after"] = {
            "file_errno": 13,
            "map_named": False,
            "path": od.CEILING_PATH,
            "pid": 3501,
        }
        self.assertEqual(od._loader_word("2d-crash-recovery", unnamed), "fail")
        kept = od.allow_record(
            {
                "claim_cap": od.CLAIM_CAP,
                "cases": [
                    {"case": "enterprise", "result": "fail", "errno": 13, "deny_pid": 0, "denied_rows": 0},
                    {"case": "loader-kill", "result": "held", "errno": 13, "deny_pid": 4242, "denied_rows": 1},
                ],
            }
        )
        self.assertEqual(kept["cases"][1]["deny_pid"], 4242)
        self.assertEqual(kept["cases"][0]["errno"], 13)
        dead = subprocess.CompletedProcess(args=["ssh"], returncode=255, stdout="", stderr="4010 destination read failed")
        self.assertTrue(od._transport_failure(dead))
        real = subprocess.CompletedProcess(args=["ssh"], returncode=1, stdout="PY_RC=1\n", stderr="")
        self.assertFalse(od._transport_failure(real))
        infra = od.allow_record(
            {
                "claim_cap": od.CLAIM_CAP,
                "cases": [{"case": "loader-kill", "result": "infra_retry", "errno": -1, "path": od.CEILING_PATH}],
                "loader_kill": "infra_retry",
            }
        )
        self.assertEqual(infra["cases"][0]["result"], "infra_retry")
        self.assertNotIn("errno", infra["cases"][0])
        self.assertEqual(infra["loader_kill"], "infra_retry")
        invalid = od.allow_record(
            {
                "claim_cap": od.CLAIM_CAP,
                "cases": [
                    {
                        "case": "loader-kill",
                        "result": "setup_invalid",
                        "errno": 0,
                        "deny_pid": 1990,
                        "lineage_anchor": 0,
                        "path": od.CEILING_PATH,
                    }
                ],
                "loader_kill": "setup_invalid",
            }
        )
        self.assertEqual(invalid["cases"][0]["result"], "setup_invalid")
        self.assertNotIn("errno", invalid["cases"][0])
        self.assertEqual(invalid["cases"][0]["lineage_anchor"], 0)
        self.assertEqual(invalid["loader_kill"], "setup_invalid")
        self.assertFalse(od.boot_lockout("Started OpenBSD Secure Shell server."))
        self.assertTrue(od.boot_lockout("You are in emergency mode. After logging in, type journalctl -xb"))
        transcript = json.dumps(
            {
                "pre": {
                    "cases": [
                        {
                            "expect_deny": True,
                            "file_errno": 13,
                            "file_event": {"lineage_anchor": 7142, "path": od.CEILING_PATH},
                            "name": "moved",
                            "pass": True,
                            "pid": 3069,
                        }
                    ],
                    "failed_cases": [],
                    "not_run": [],
                }
            }
        )
        wrapped = json.dumps(
            {
                "pre": {
                    "cases": [
                        {
                            "name": "moved",
                            "pass": True,
                            "samples": [
                                {
                                    "expect_deny": True,
                                    "file_errno": 13,
                                    "file_event": {"lineage_anchor": 7142},
                                    "name": "moved",
                                    "pass": True,
                                    "pid": 3069,
                                }
                            ],
                        }
                    ]
                }
            }
        )
        nested = od._descendant_cases(od._guest_payload(wrapped))
        self.assertEqual(nested[0]["pid"], 3069)
        self.assertEqual(nested[0]["lineage_anchor"], 7142)
        self.assertTrue(nested[0]["expect_deny"])
        kept_cases = od._descendant_cases(od._guest_payload("noise\n" + transcript + "\nPY_RC=0\n"))
        self.assertEqual(kept_cases[0]["pid"], 3069)
        self.assertEqual(kept_cases[0]["lineage_anchor"], 7142)
        self.assertTrue(od._pre_held(kept_cases))

    def test_full_battery_is_two_complete_repeats(self) -> None:
        self.assertEqual(od.battery_schedule(), ["enterprise", "descendant-b1", "enterprise", "descendant-b1"])
        self.assertEqual(od.FULL_BATTERY, ("kernel", "seal", "enterprise", "descendant-b1"))
        repeats = [self._passing_repeat(1), self._passing_repeat(2)]
        self.assertTrue(od.full_set_passes(repeats))
        attributed = [self._passing_repeat(1), self._passing_repeat(2)]
        attributed[1] = dict(attributed[1])
        attributed[1]["enterprise_rc"] = 1
        attributed[1]["deny_hold"] = True
        self.assertTrue(od.full_set_passes(attributed))
        kept_capture = od.allow_record(
            {
                "captures": [
                    {
                        "errno": 13,
                        "fail_reasons": ["programs_not_removed"],
                        "guest_rc": 1,
                        "hold": True,
                        "lineage_anchor": 9058,
                        "name": "enterprise-2",
                        "path": od.CEILING_PATH,
                        "pid": 4968,
                        "uid": 65534,
                    }
                ],
                "claim_cap": od.CLAIM_CAP,
            }
        )
        self.assertTrue(kept_capture["captures"][0]["hold"])
        self.assertEqual(kept_capture["captures"][0]["lineage_anchor"], 9058)
        self.assertNotIn("hostname", json.dumps(kept_capture))
        short = [self._passing_repeat(1)]
        self.assertFalse(od.full_set_passes(short))
        missing_grant = [self._passing_repeat(1), self._passing_repeat(2)]
        missing_grant[1] = dict(missing_grant[1])
        missing_grant[1]["rows"] = {"revoke": {"probe": {"nobody_errno": 13}}}
        self.assertFalse(od.full_set_passes(missing_grant))
        kept = od.allow_record({"repeats": repeats, "full_set": True, "hostname": "secret-host"})
        self.assertNotIn("hostname", kept)
        self.assertEqual(len(kept["repeats"]), 2)
        self.assertIn("grant", kept["repeats"][0]["rows"])
        self.assertIn("revoke", kept["repeats"][0]["rows"])
        duplicated = [self._passing_repeat(1), self._passing_repeat(1)]
        self.assertFalse(od.full_set_passes(duplicated))

    def test_teardown_deletes_the_bucket_when_listing_fails(self) -> None:
        calls: list[tuple[str, ...]] = []
        original_list = od._list_instances
        original_delete = od.delete_objects
        original_created = od._creation_epoch
        original_write = od.write_evidence

        def boom(_project: str) -> list[dict]:
            raise SystemExit("instances")

        def record(names, *, missing_ok: bool) -> None:
            calls.append(tuple(names))
            self.assertTrue(missing_ok)

        od._list_instances = boom
        od.delete_objects = record
        od._creation_epoch = lambda _project, _name: None
        od.write_evidence = lambda *_args, **_kwargs: None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(SystemExit):
                    od.teardown_if_present(
                        {
                            "GCP_LAB_EXECUTE": "1",
                            "GCP_LAB_PROJECT": "vantio-lab-oct08",
                            "GITHUB_RUN_ID": "12",
                            "EVIDENCE_DIR": tmp,
                        }
                    )
        finally:
            od._list_instances = original_list
            od.delete_objects = original_delete
            od._creation_epoch = original_created
            od.write_evidence = original_write
        self.assertEqual(calls, [("12/seal.oci.tar", "12/contract.tar")])

    def test_teardown_runs_with_t5_disabled(self) -> None:
        deliver = (ROOT / "scripts/gcp/offline_deliver_1.py").read_text(encoding="utf-8")
        preamble = deliver.split("def ", 1)[0]
        self.assertNotIn("import t5_battery", preamble)
        start = deliver.index("def _load_t5_battery")
        chunk = deliver[start:deliver.index("\ndef ", start + 1)]
        self.assertLess(chunk.index("t5_requested"), chunk.index("import t5_battery"))
        teardown = (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8")
        body_start = teardown.index("def teardown_if_present")
        body_end = teardown.index("def _loader_libs")
        self.assertNotIn("import t5_battery", teardown[body_start:body_end])
        probe = r"""
import sys
from pathlib import Path

class _BlockT5:
    def find_spec(self, fullname, path, target=None):
        if fullname == "t5_battery" or fullname.startswith("t5_battery."):
            raise ModuleNotFoundError("No module named 't5_battery'", name=fullname)
        return None

sys.meta_path.insert(0, _BlockT5())
root = Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts" / "gcp"))
import offline_deliver as od

if "t5_battery" in sys.modules:
    raise SystemExit("t5 loaded at import")

calls = []

def boom(_project):
    raise SystemExit("instances")

def record(names, *, missing_ok):
    calls.append(tuple(names))
    if missing_ok is not True:
        raise SystemExit("missing_ok")

od._list_instances = boom
od.delete_objects = record
od._creation_epoch = lambda _project, _name: None
od.write_evidence = lambda *_args, **_kwargs: None
try:
    od.teardown_if_present(
        {
            "GCP_LAB_EXECUTE": "1",
            "GCP_LAB_PROJECT": "vantio-lab-oct08",
            "GITHUB_RUN_ID": "12",
            "EVIDENCE_DIR": sys.argv[2],
            "T5_EGRESS": "false",
            "REDTEAM_BRAIN": "false",
        }
    )
except SystemExit as exc:
    if exc.code != "instances":
        raise SystemExit(f"unexpected {exc.code!r}")
else:
    raise SystemExit("teardown returned")
if calls != [("12/seal.oci.tar", "12/contract.tar")]:
    raise SystemExit(f"calls {calls!r}")
if "t5_battery" in sys.modules:
    raise SystemExit("t5 loaded during teardown")
try:
    od._load_t5_battery({"T5_EGRESS": "false"})
except SystemExit as exc:
    if exc.code != "t5_egress":
        raise SystemExit(f"disabled load {exc.code!r}")
else:
    raise SystemExit("disabled load returned")
if "t5_battery" in sys.modules:
    raise SystemExit("t5 loaded while disabled")
try:
    od._load_t5_battery({"T5_EGRESS": "true"})
except ModuleNotFoundError as exc:
    if exc.name != "t5_battery":
        raise SystemExit(f"enabled load {exc!r}")
else:
    raise SystemExit("enabled load returned")
print("ok")
"""
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [sys.executable, "-c", probe, str(ROOT), tmp],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertEqual(completed.stdout.strip(), "ok")

    def test_a_run_id_containing_404_is_not_a_missing_object(self) -> None:
        quoted = "ERROR: 403 Permission denied gs://vantio-lab-oct08-handoff/14042/seal.oci.tar"
        self.assertFalse(od._missing_object(quoted))
        self.assertFalse(od._missing_object("gcloud: command not found"))
        self.assertTrue(od._missing_object("The following URLs matched no objects or files:\ngs://vantio-lab-oct08-handoff/14042/seal.oci.tar"))
        self.assertTrue(od._missing_object("NotFound: 404 gs://vantio-lab-oct08-handoff/12/seal.oci.tar"))

    def test_allowlist_rejects_secret_shaped_short_fields(self) -> None:
        kept = od.allow_record(
            {
                "account_id": "-----BEGINPRIVATEKEY-----",
                "step": "ghp_" + "a" * 20,
                "name": "not-a-lab-vm",
                "snapshot": "evil",
                "seal_sha256": od.POLICY_ALLOW_SEAL,
            }
        )
        self.assertEqual(kept, {"seal_sha256": od.POLICY_ALLOW_SEAL})

    def test_prune_does_not_republish_a_false_full_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            one = {"full_set": True, "repeats": [self._passing_repeat(1)], "hostname": "box"}
            (directory / "gcp-lab-rows.json").write_text(json.dumps(one), encoding="utf-8")
            od.prune_evidence(directory)
            body = json.loads((directory / "gcp-lab-rows.json").read_text(encoding="utf-8"))
            self.assertNotIn("full_set", body)
            self.assertNotIn("repeats", body)
            self.assertNotIn("hostname", body)

    def test_prune_drops_a_poisoned_hash_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "handoff.json").write_text("not-json", encoding="utf-8")
            (directory / "handoff.json.sha256").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
            (directory / "gcp-plumb.json").write_text("{}\n", encoding="utf-8")
            od.prune_evidence(directory)
            self.assertFalse((directory / "handoff.json").exists())
            self.assertFalse((directory / "handoff.json.sha256").exists())
            self.assertFalse((directory / "gcp-plumb.json").exists())
            (directory / "teardown.json.sha256").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
            nested = directory / "gcp-plumb.json"
            nested.mkdir()
            (nested / "enterprise-rows.json").write_text('{"token":"ghp_' + "a" * 20 + '"}\n', encoding="utf-8")
            od.prune_evidence(directory)
            self.assertFalse((directory / "teardown.json.sha256").exists())
            self.assertFalse(nested.exists())

    def test_prune_unlinks_guest_symlinks_and_survives_bad_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "evidence"
            directory.mkdir()
            outside = root / "outside"
            outside.mkdir()
            secret = outside / "secret.txt"
            secret.write_text("ghp_" + "a" * 20, encoding="utf-8")
            link = directory / "gcp-plumb.json"
            link.symlink_to(outside, target_is_directory=True)
            (directory / "debs.json").write_bytes(b"\xff\xfe")
            (directory / "handoff.json.sha256").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
            od.prune_evidence(directory)
            self.assertFalse(link.exists())
            self.assertTrue(secret.is_file())
            self.assertFalse((directory / "debs.json").exists())
            self.assertFalse((directory / "handoff.json.sha256").exists())
            self.assertEqual(list(directory.iterdir()), [])

    def test_prune_removes_a_directory_deeper_than_the_recursion_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "gcp-lab-rows.json").write_text(
                '{"hostname":"box","note":"ghp_' + "a" * 20 + '"}\n',
                encoding="utf-8",
            )
            (directory / "gcp-lab-rows.json.sha256").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
            nested = directory / "gcp-plumb.json"
            nested.mkdir()
            cursor = nested
            for _ in range(sys.getrecursionlimit() + 20):
                cursor = cursor / "d"
                cursor.mkdir()
            od.prune_evidence(directory)
            self.assertFalse(nested.exists())
            text = (directory / "gcp-lab-rows.json").read_text(encoding="utf-8")
            self.assertNotIn("ghp_", text)
            self.assertNotIn("PRIVATE KEY", (directory / "gcp-lab-rows.json.sha256").read_text(encoding="utf-8"))

    def test_evidence_sidecar_does_not_follow_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            outside = root / "secret.txt"
            outside.write_text("keep-me", encoding="utf-8")
            path = evidence / "handoff.json"
            path.write_text("{}\n", encoding="utf-8")
            sidecar = evidence / "handoff.json.sha256"
            sidecar.symlink_to(outside)
            od.write_evidence(path, {"seal_sha256": od.POLICY_ALLOW_SEAL})
            self.assertEqual(outside.read_text(encoding="utf-8"), "keep-me")
            self.assertFalse(sidecar.is_symlink())
            self.assertIn(od.POLICY_ALLOW_SEAL, path.read_text(encoding="utf-8"))

    def test_prune_deletes_the_file_when_allowlist_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "gcp-lab-rows.json").write_text(
                '{"hostname":"box","full_set":true,"note":"ghp_' + "a" * 20 + '"}\n',
                encoding="utf-8",
            )
            (directory / "gcp-lab-rows.json.sha256").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
            original = od.allow_record

            def boom(_payload: dict) -> dict:
                raise OverflowError("int too large")

            od.allow_record = boom
            try:
                od.prune_evidence(directory)
            finally:
                od.allow_record = original
            self.assertFalse((directory / "gcp-lab-rows.json").exists())
            self.assertFalse((directory / "gcp-lab-rows.json.sha256").exists())

    def test_huge_numbers_deep_nests_and_token_names_stay_out(self) -> None:
        digest = "a" * 64
        kept = od.allow_record(
            {
                "debs": [
                    {"name": "github_pat_" + "a" * 22, "sha256": digest},
                    {"name": "gho_" + "b" * 22, "sha256": digest},
                    {"name": "docker.io_1.deb", "sha256": digest},
                ],
                "repeats": [
                    {"repeat": 1, "convergence_ms": int("9" * 400), "rows": {"note": "ghp_" + "a" * 20}},
                    self._passing_repeat(2),
                ],
            }
        )
        self.assertEqual(kept["debs"], [{"name": "docker.io_1.deb", "sha256": digest}])
        self.assertFalse(kept["full_set"])
        self.assertNotIn("convergence_ms", json.dumps(kept))
        deep: dict = {"repeat": 1, "result": "pass"}
        cursor = deep
        for _ in range(40):
            cursor["rows"] = {}
            cursor = cursor["rows"]
        self.assertEqual(od.allow_battery(deep), {"repeat": 1, "result": "pass"})

    def test_raw_guest_copies_are_not_left_for_the_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in od.RAW_GUEST_NAMES:
                (directory / name).write_text('{"token": "ghp_' + "a" * 20 + '"}\n', encoding="utf-8")
            (directory / "gcp-lab-rows.json").write_text("{}\n", encoding="utf-8")
            od.drop_guest_copies(directory)
            self.assertTrue((directory / "gcp-lab-rows.json").is_file())
            for name in od.RAW_GUEST_NAMES:
                self.assertFalse((directory / name).exists())

    def test_deb_pack_is_flat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "docker.io_1.deb").write_bytes(b"deb")
            rows = od.pack_debs(directory, directory / "debs.tar")
            self.assertEqual(rows[0]["name"], "docker.io_1.deb")
            with tarfile.open(directory / "debs.tar") as tar:
                self.assertEqual(tar.getnames(), ["docker.io_1.deb"])

    def test_batteries_wait_for_a_new_seal(self) -> None:
        plumbing = {"EXPECTED_SEAL": od.POLICY_ALLOW_SEAL, "RUN_BATTERIES": "false"}
        self.assertEqual(od.refuse_batteries(plumbing), od.POLICY_ALLOW_SEAL)
        self.assertFalse(od.batteries_requested(plumbing))
        with self.assertRaises(SystemExit):
            od.refuse_batteries({"EXPECTED_SEAL": od.POLICY_ALLOW_SEAL, "RUN_BATTERIES": "true"})
        new_seal = "ab" * 32
        self.assertEqual(
            od.refuse_batteries({"EXPECTED_SEAL": new_seal, "RUN_BATTERIES": "true"}),
            new_seal,
        )
        with self.assertRaises(SystemExit):
            od.expected_seal({"EXPECTED_SEAL": od.PUBLIC_INSTALLER_PIN})

    def test_guest_script_is_offline(self) -> None:
        text = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertNotIn("apt-get update", text)
        self.assertNotIn("linux-tools", text)
        self.assertNotIn("ubuntu:ubuntu", text)
        self.assertIn("--no-download", text)
        self.assertIn('id -un', text)
        self.assertIn("debs/*.deb", text)
        self.assertIn('sha256sum -c -', text)
        self.assertIn(od.TRUST_SHA256, text)
        self.assertIn(od.IMAGE_NAME, text)
        self.assertIn("ca-certificates.crt", text)
        self.assertIn("mount -t bpf bpf /sys/fs/bpf", text)
        self.assertIn("systemctl reboot --force", text)
        self.assertIn("google-shutdown-scripts.service", text)
        self.assertNotIn("sudo reboot || true", text)
        self.assertIn("mount --make-rshared /sys/fs/bpf", text)
        self.assertIn("/sys/fs/bpf:/sys/fs/bpf:rshared", text)
        self.assertIn("INTERNAL_CLEAN_HOST_PROOF", text)
        self.assertLess(text.index('mode=${2:-plumb}'), text.index("apt-get install"))
        uninstall = text[text.index("authorized_uninstall()"): text.index("normalize_loaded_image")]
        self.assertIn('sudo python3 - "$here/sticky_write.py"', uninstall)
        self.assertLess(uninstall.index("sudo rm -f /var/lib/vantio-lab/vantio-uninstall.out"), uninstall.index("ensure_working_bpftool"))
        self.assertIn('echo "UNINSTALL_RESIDUAL bpftool missing" | tee -a /var/lib/vantio-lab/vantio-uninstall.out', uninstall)
        self.assertIn('echo "UNINSTALL_NOT_VERIFIED rc=$urc" | tee -a /var/lib/vantio-lab/vantio-uninstall.out', uninstall)
        self.assertIn('echo "UNINSTALL_RESIDUAL bpffs"', uninstall)
        self.assertIn("| tee -a /var/lib/vantio-lab/vantio-uninstall.out", uninstall)
        self.assertNotIn("sudo tee -a /var/lib/vantio-lab/vantio-uninstall.out", uninstall)
        self.assertNotIn("/tmp/vantio-uninstall.out", uninstall)
        self.assertIn("stamp_host_evidence", text)
        self.assertIn("baseline_diag.read_lockdown()", text)
        self.assertIn("baseline_diag.read_image_name()", text)
        self.assertIn("read_lockdown", od.LATER_BOOT_PROBE)
        self.assertIn("read_image_name", od.LATER_BOOT_PROBE)
        self.assertNotIn("\n", od.LATER_BOOT_PROBE)

    def test_evidence_keeps_live_lockdown_and_the_exact_image_name(self) -> None:
        lockdown = "none [integrity] confidentiality"
        image = "ubuntu-2404-noble-amd64-v20261014"
        kept = od.allow_record(
            {
                "lockdown": lockdown,
                "kernel_lockdown": "[none] integrity confidentiality",
                "image_name": image,
            }
        )
        self.assertEqual(kept["lockdown"], lockdown)
        self.assertEqual(kept["kernel_lockdown"], "[none] integrity confidentiality")
        self.assertEqual(kept["image_name"], image)
        dropped = od.allow_record(
            {
                "image_name": od.IMAGE_FAMILY,
                "lockdown": "lockdown,capability,bpf",
                "kernel_lockdown": "none [integrity] confidentiality extra",
            }
        )
        self.assertNotIn("image_name", dropped)
        self.assertNotIn("lockdown", dropped)
        self.assertNotIn("kernel_lockdown", dropped)
        flags = od._kernel_flags(
            {
                "btf": True,
                "lsm": "lockdown,capability,bpf",
                "lockdown": lockdown,
                "image_name": image,
            }
        )
        self.assertEqual(flags["kernel_lockdown"], lockdown)
        self.assertEqual(flags["image_name"], image)
        self.assertNotIn("image_name", od._kernel_flags({"image_name": "ubuntu-os-cloud/ubuntu-2404-lts-amd64"}))
        source = "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/" + image
        self.assertEqual(od.image_name_from_disk({"sourceImage": source}), image)
        self.assertEqual(
            od.image_name_from_disk(
                {"sourceImage": "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-2404-lts-amd64"}
            ),
            "",
        )
        argv = od.describe_boot_disk_argv("vantio-lab-oct08", "vantio-gcp-lab-12")
        self.assertIn("disks", argv)
        self.assertIn("describe", argv)
        self.assertIn("--format=json(sourceImage)", argv)
        fresh = "33333333-3333-3333-3333-333333333333"
        sealed = "BOOT_IMAGE=/vmlinuz ro lsm=lockdown,capability,landlock,yama,apparmor,ima,evm,bpf panic=-1"
        listed = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        adopted = od.live_lsm_from_probe(
            {
                "boot_id": fresh,
                "cmdline": sealed,
                "enabled_lsm": listed,
                "lockdown": lockdown,
                "image_name": image,
            },
            fresh,
        )
        self.assertIsNotNone(adopted)
        self.assertEqual(adopted["lockdown"], lockdown)
        self.assertEqual(adopted["image_name"], image)
        family = od.live_lsm_from_probe(
            {
                "boot_id": fresh,
                "cmdline": sealed,
                "enabled_lsm": listed,
                "image_name": od.IMAGE_FAMILY,
            },
            fresh,
        )
        self.assertIsNotNone(family)
        self.assertNotIn("image_name", family)

    def test_deb_fetch_uses_the_pinned_snapshot(self) -> None:
        text = (ROOT / "scripts/gcp/fetch_offline_debs.sh").read_text(encoding="utf-8")
        self.assertIn(od.PACKAGE_IMAGE, text)
        for line in od.SNAPSHOT_LINES:
            self.assertIn(line, text)
        self.assertIn("--download-only", text)
        self.assertIn("--no-install-recommends", text)
        self.assertIn("docker.io", text)
        self.assertIn("python3-cryptography", text)
        self.assertIn("ca-certificates", text)
        self.assertIn("linux-tools-common", text)
        self.assertIn("linux-tools-6.8.0-1070-gcp", text)
        self.assertIn("linux-gcp-tools-6.8.0-1070", text)
        self.assertIn("linux-tools-6.8.0-1069-gcp", text)
        self.assertIn("linux-gcp-tools-6.8.0-1069", text)
        self.assertLess(text.index("apt-get install -y --no-install-recommends ca-certificates"), text.index("snapshot.ubuntu.com"))
        self.assertLess(text.index("--download-only"), text.index("apt-get download \"ca-certificates="))
        # The live-installed ca-certificates can be newer than the snapshot (run 39818326180).
        self.assertIn("apt-cache madison ca-certificates", text)
        self.assertLess(text.index("apt-cache madison ca-certificates"), text.index("apt-get download \"ca-certificates="))
        self.assertNotIn("apt-get download ca-certificates )", text)
        self.assertIn("ca-certificates.crt", text)

    def test_confirm_rejects_the_pre_reboot_rows_file(self) -> None:
        stock = {"host_result": "GUARD_PROVED", "cmdline": "panic=-1", "reboot_requested": True}
        self.assertFalse(od.confirm_matches_boot(stock, "11111111-1111-1111-1111-111111111111"))
        fresh = "22222222-2222-2222-2222-222222222222"
        self.assertTrue(od.confirm_matches_boot({"boot_id": fresh}, fresh))
        self.assertFalse(od.confirm_matches_boot({"boot_id": "old"}, fresh))
        blob = "x" * 200001 + "Command line: sealed"
        self.assertEqual(od.serial_console_text(blob), blob)
        self.assertNotIn("[-200000:]", (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8"))
        script = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertIn(
            "sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json",
            script,
        )
        self.assertNotIn("\n", od.LATER_BOOT_PROBE)
        self.assertIn("grubenv", od.LATER_BOOT_PROBE)
        self.assertIn("enabled_lsm", od.LATER_BOOT_PROBE)
        self.assertIn("/sys/kernel/security/lsm", od.LATER_BOOT_PROBE)
        self.assertNotIn("reboot", od.LATER_BOOT_PROBE)
        self.assertLess(script.find("sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json"), script.find("write_lsm_status"))
        fresh_boot = "33333333-3333-3333-3333-333333333333"
        sealed = "BOOT_IMAGE=/vmlinuz ro lsm=lockdown,capability,landlock,yama,apparmor,ima,evm,bpf panic=-1"
        listed = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        adopted = od.live_lsm_from_probe(
            {"boot_id": fresh_boot, "cmdline": sealed, "enabled_lsm": listed},
            fresh_boot,
        )
        self.assertIsNotNone(adopted)
        self.assertTrue(od.lsm_confirm_ok(adopted))
        self.assertIsNone(od.live_lsm_from_probe({"boot_id": "old", "cmdline": sealed, "enabled_lsm": listed}, fresh_boot))
        self.assertIsNone(
            od.live_lsm_from_probe(
                {"boot_id": fresh_boot, "cmdline": "panic=-1", "enabled_lsm": "lockdown,capability,apparmor"},
                fresh_boot,
            )
        )
        stale = {"boot_id": "old", "host_result": "GUARD_PROVED", "reboot_requested": True}
        current = {"boot_id": fresh_boot, "host_result": "LSM_ENABLED", "reboot_requested": False}
        self.assertFalse(od.guard_ready(stale, fresh_boot))
        self.assertTrue(od.guard_ready({**stale, "boot_id": fresh_boot}, fresh_boot))
        self.assertFalse(od.guard_ready({**current, "host_result": "GUARD_PROVED"}, fresh_boot))
        self.assertEqual(od.choose_boot_rows(stale, current, fresh_boot)["boot_id"], fresh_boot)
        self.assertEqual(od.choose_boot_rows(current, stale, fresh_boot)["boot_id"], fresh_boot)
        self.assertEqual(od.choose_boot_rows(stale, None, fresh_boot)["boot_id"], "old")
        self.assertIsNone(od.choose_boot_rows(None, None, fresh_boot))
        deliver = (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8")
        self.assertIn("live_lsm_from_probe(probe_body, later)", deliver)
        self.assertNotIn('_wait_boot(project, name, "down"', deliver)
        self.assertIn("_wait_live_boot", deliver)
        published = script.find("cp /var/lib/vantio-lab/enterprise-pe-rows.json /tmp/enterprise-pe-rows.json")
        decision = script.find('json.load(open("/var/lib/vantio-lab/enterprise-pe-rows.json"))')
        self.assertGreaterEqual(published, 0)
        self.assertGreaterEqual(decision, 0)
        self.assertLess(published, decision)
        self.assertLess(decision, script.find("systemd-run --on-active=45s", decision))
        self.assertNotIn("cp /tmp/phase2-host.out /tmp/enterprise-pe-rows.json", script)
        pre_clear = script.find("sudo rm -f /var/lib/vantio-lab/b1-pre.json")
        pre_run = script.find('python3 "$here/descendant_b1.py"')
        self.assertGreaterEqual(pre_clear, 0)
        self.assertGreaterEqual(pre_run, 0)
        self.assertLess(pre_clear, pre_run)
        stock_boot = "44444444-4444-4444-4444-444444444444"
        self.assertTrue(
            od.stock_bpf_ready(
                {
                    "boot_id": stock_boot,
                    "host_result": "LSM_ALREADY_ACTIVE",
                    "stock_lsm": listed,
                    "cmdline": "BOOT_IMAGE=/vmlinuz ro panic=-1",
                },
                stock_boot,
            )
        )
        self.assertIsNotNone(
            od.live_stock_bpf(
                {"boot_id": stock_boot, "cmdline": "BOOT_IMAGE=/vmlinuz ro panic=-1", "enabled_lsm": listed},
                stock_boot,
            )
        )
        self.assertIn("lsm_enabled_follow_up", deliver)
        self.assertIn("boot_id_unread", deliver)
        hint = "Specify --start=552072 in the next get-serial-port-output command\n"
        self.assertEqual(od.next_serial_start("noise\n" + hint), 552072)
        self.assertIsNone(od.next_serial_start("kernel line only"))
        self.assertEqual(od.serial_console_text("boot line\n" + hint), "boot line\n")
        self.assertEqual(od.serial_port_argv("vantio-lab-oct08", "vantio-gcp-lab-1", 552072)[-1], "--start=552072")
        self.assertNotIn("The full serial log", deliver)

    def test_every_guest_helper_phase2_host_imports_reaches_the_guest(self) -> None:
        # 2c-upgrade-rollback imports product_uninstall_census on the guest.
        guest_dir = ROOT / "scripts/aws/lab-guests"
        host = (guest_dir / "phase2_host.py").read_text(encoding="utf-8")
        imported = set(re.findall(r"^\s*import ([a-z_0-9]+)", host, re.M))
        helpers = sorted(name for name in imported if (guest_dir / f"{name}.py").is_file())
        self.assertIn("product_uninstall_census", helpers)
        stage_src = (ROOT / "scripts/gcp/offline_deliver_2.py").read_text(encoding="utf-8")
        stage = stage_src[stage_src.index("def _stage_payload("):]
        stage = stage[: stage.index("    return rows")]
        deliver_src = (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8")
        upload = deliver_src[deliver_src.index("debs = _stage_payload(env, payload_dir)"):]
        upload = upload[: upload.index("lsm = _prepare_lab_lsm(")]
        workflow = (ROOT / ".github/workflows/gcp-lab-provision.yml").read_text(encoding="utf-8")
        deliver_job = workflow[workflow.index("- name: Checkout delivery scripts"):]
        deliver_job = deliver_job[: deliver_job.index("sparse-checkout-cone-mode")]
        for name in helpers:
            with self.subTest(helper=name):
                self.assertIn(f'dest / "{name}.py"', stage)
                self.assertIn(f'payload_dir / "{name}.py"', upload)
                self.assertIn(f"scripts/aws/lab-guests/{name}.py", deliver_job)

    def test_workflow_keeps_wif_and_hides_the_bundle(self) -> None:
        names = sorted(path.name for path in (ROOT / ".github/workflows").glob("gcp-lab-*.yml"))
        self.assertEqual(set(names), set(lab.WORKFLOWS))
        self.assertEqual(len(names), 6)
        text = (ROOT / ".github/workflows/gcp-lab-provision.yml").read_text(encoding="utf-8")
        self.assertIn("environment: w3-lab-auto", text)
        self.assertIn("environment: gcp-lab", text)
        self.assertIn(od.HANDOFF_SA, text)
        self.assertIn("upload-handoff", text)
        self.assertIn("download-handoff", text)
        self.assertIn("create-instance", text)
        self.assertIn("plumb-guest", text)
        self.assertIn("run-batteries", text)
        self.assertIn("serial-console", text)
        self.assertLess(text.find("run-batteries"), text.find("serial-console"))
        self.assertLess(text.find("serial-console"), text.find("delete-handoff"))
        self.assertIn("teardown-if-present", text)
        self.assertIn("vantio-gce-slot", text)
        self.assertIn("EXPECTED_SEAL: ${{ inputs.seal }}", text)
        self.assertIn("if: ${{ !inputs.run_batteries && !inputs.self_service && !inputs.t5_egress }}", text)
        self.assertIn("t5_egress:", text)
        self.assertIn("run-t5-egress", text)
        self.assertLess(text.find("run-t5-egress"), text.find("serial-console"))
        self.assertIn("self_service:", text)
        self.assertIn("run-self-service", text)
        self.assertNotIn("if: ${{ !inputs.run_batteries }}", text)
        self.assertNotIn("gcp-lab-one-vm", text)
        self.assertNotIn("default: f882dd81", text)
        self.assertIn(od.WIF_PROVIDER, text)
        self.assertNotIn("vars.GCP_LAB_WIF_PROVIDER", text)
        self.assertNotIn("vars.GCP_LAB_SERVICE_ACCOUNT", text)
        self.assertNotIn("uploadType=media", (ROOT / "scripts/gcp/offline_deliver.py").read_text(encoding="utf-8"))
        self.assertIn('test "$GCP_LAB_SERVICE_ACCOUNT" = "vantio-lab-gha@vantio-lab-oct08.iam.gserviceaccount.com"', text)
        self.assertIn("vantio-lab-handoff@vantio-lab-oct08.iam.gserviceaccount.com", text)
        for name in (
            "gcp-lab-teardown.yml",
            "gcp-lab-sweeper.yml",
            "gcp-lab-collect.yml",
            "gcp-lab-verify-removed.yml",
            "gcp-lab-cost-gate.yml",
        ):
            other = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn(od.WIF_PROVIDER, other)
            self.assertNotIn("vars.GCP_LAB_WIF_PROVIDER", other)
            self.assertNotIn("gcp-lab-one-vm", other)
        for name in (
            "gcp-lab-teardown.yml",
            "gcp-lab-sweeper.yml",
            "gcp-lab-collect.yml",
            "gcp-lab-verify-removed.yml",
        ):
            other = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("vantio-gce-slot", other)
        self.assertIn("fetch_offline_debs.sh", text)
        self.assertEqual(text.count("secrets.W3_LAB_PRIVATE_BUNDLE_TOKEN"), 1)
        self.assertNotIn("aws-actions", text)
        self.assertNotIn("ReleaseAddress", text)
        self.assertFalse(lab.names_partner(text))
        self.assertNotIn("contents: write", text)
        lines = text.splitlines()
        blocks = []
        for index, line in enumerate(lines):
            if "actions/upload-artifact@" in line:
                blocks.append("\n".join(lines[index : index + 12]))
        self.assertGreaterEqual(len(blocks), 3)
        optics_blocks = [block for block in blocks if "optics-observe" in block]
        evidence_blocks = [block for block in blocks if block not in optics_blocks]
        self.assertGreaterEqual(len(evidence_blocks), 3)
        self.assertGreaterEqual(len(optics_blocks), 3)
        for block in evidence_blocks:
            self.assertIn("gcp-lab-evidence", block)
        for block in blocks:
            self.assertNotIn("seal.oci.tar", block)
            self.assertNotIn("contract.tar", block)
            self.assertNotIn(".deb", block)
        for key in ("  fetch:", "  deliver:", "  teardown:"):
            self.assertIn(key, text)

    def test_self_service_rows_keep_states_and_drop_paths(self) -> None:
        kept = od.allow_record(
            {
                "cloud": "gcp",
                "mode": "self-service",
                "self_service": [
                    {"phase": "install", "protection": "OBSERVE", "reason": "HEALTHY", "state": "HEALTHY"},
                    {"phase": "install", "protection": "PROTECTED", "reason": "ENFORCEMENT_HELD", "state": "NOT_RUN"},
                    {"phase": "install", "protection": "OBSERVE", "reason": "/tmp/secret", "state": "HEALTHY"},
                ],
                "status": "SELF_SERVICE",
            }
        )
        self.assertEqual(kept["mode"], "self-service")
        self.assertEqual(kept["status"], "SELF_SERVICE")
        self.assertEqual(
            kept["self_service"],
            [
                {
                    "phase": "install",
                    "proof_state": "NOT_PROVED",
                    "protection": "OBSERVE",
                    "reason": "HEALTHY",
                    "state": "HEALTHY",
                },
                {
                    "phase": "install",
                    "proof_state": "NOT_PROVED",
                    "protection": "PROTECTED",
                    "reason": "ENFORCEMENT_HELD",
                    "state": "NOT_RUN",
                },
            ],
        )
        self.assertFalse(od.self_service_requested({}))
        self.assertTrue(od.self_service_requested({"SELF_SERVICE": "true"}))
        with self.assertRaises(SystemExit):
            od.self_service_requested({"SELF_SERVICE": "true", "RUN_BATTERIES": "true"})
            od.run_self_service({"GCP_LAB_EXECUTE": "1", "SELF_SERVICE": "true", "RUN_BATTERIES": "true"})

    def test_loaded_image_keeps_the_historical_tag_and_a_commit_tag(self) -> None:
        text = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertIn(od.IMAGE_NAME, text)
        self.assertIn("normalize_loaded_image", text)
        self.assertIn("loaded_image_refused", text)
        self.assertNotIn('test "$image" = "$image_name"', text)
        pattern = re.compile(r"^vantio-phantom-engine:(egress-2e6ab54|[0-9a-f]{7,40})$")
        self.assertIsNotNone(pattern.fullmatch("vantio-phantom-engine:e5e15ab"))
        self.assertIsNotNone(pattern.fullmatch("vantio-phantom-engine:egress-2e6ab54"))
        self.assertIsNone(pattern.fullmatch("ubuntu:24.04"))
        self.assertIsNone(pattern.fullmatch("vantio-phantom-engine:latest"))
        self.assertIsNone(pattern.fullmatch("vantio-phantom-engine:e5e15ab extra"))
        tail = od.missing_rows_tail(
            "Loaded image: vantio-phantom-engine:e5e15ab\nghp_" + "a" * 20,
            "sha256sum: FAILED",
        )
        self.assertIn("Loaded image: vantio-phantom-engine:e5e15ab", tail)
        self.assertIn("sha256sum: FAILED", tail)
        self.assertNotIn("ghp_", tail)
        self.assertIn("[redacted]", tail)

    def test_serial_port_reads_the_lab_instance(self) -> None:
        argv = od.serial_port_argv("vantio-lab-oct08", "vantio-gcp-lab-38793701944")
        self.assertEqual(
            argv,
            [
                "gcloud",
                "compute",
                "instances",
                "get-serial-port-output",
                "vantio-gcp-lab-38793701944",
                "--project=vantio-lab-oct08",
                "--zone=us-central1-a",
                "--port=1",
            ],
        )
        self.assertIn("serial-console", od.USAGE)

    def test_lsm_confirm_needs_bpf_in_the_live_list(self) -> None:
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        stock = "lockdown,capability,landlock,yama,apparmor,ima,evm"
        self.assertTrue(
            od.lsm_confirm_ok(
                {
                    "host_result": "LSM_ENABLED",
                    "stock_lsm": token,
                    "cmdline": f"root=PARTUUID ro lsm={token} panic=-1",
                }
            )
        )
        self.assertTrue(
            od.lsm_confirm_ok(
                {
                    "host_result": "LSM_ALREADY_ACTIVE",
                    "stock_lsm": token,
                    "cmdline": f"root=PARTUUID ro lsm={token} panic=-1",
                }
            )
        )
        self.assertFalse(
            od.lsm_confirm_ok(
                {
                    "host_result": "LSM_ALREADY_ACTIVE",
                    "stock_lsm": stock,
                    "cmdline": "root=PARTUUID ro console=ttyS0,115200 panic=-1",
                }
            )
        )
        self.assertFalse(
            od.lsm_confirm_ok(
                {
                    "host_result": "GUARD_PROVED",
                    "stock_lsm": stock,
                    "cmdline": "root=PARTUUID ro console=ttyS0,115200 panic=-1",
                }
            )
        )
        self.assertFalse(od.lsm_confirm_ok({"host_result": "LSM_ENABLED", "stock_lsm": "bpfextra", "cmdline": "lsm=bpfextra"}))

    def test_prune_keeps_the_lsm_guard_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "lsm-guard.json").write_text(
                json.dumps(
                    {
                        "host_result": "GUARD_PROVED",
                        "hostname": "box",
                        "lsm_guard": "stale_rows",
                        "note": "ghp_" + "a" * 20,
                        "stock_bpf_lsm": False,
                        "stock_lsm": "lockdown,capability,apparmor",
                    }
                ),
                encoding="utf-8",
            )
            (directory / "not-evidence.json").write_text("{}\n", encoding="utf-8")
            od.prune_evidence(directory)
            self.assertFalse((directory / "not-evidence.json").exists())
            body = json.loads((directory / "lsm-guard.json").read_text(encoding="utf-8"))
            self.assertEqual(body["host_result"], "GUARD_PROVED")
            self.assertEqual(body["lsm_guard"], "stale_rows")
            self.assertEqual(body["stock_lsm"], "lockdown,capability,apparmor")
            self.assertIs(body["stock_bpf_lsm"], False)
            self.assertNotIn("hostname", body)
            self.assertNotIn("note", body)
            self.assertNotIn("ghp_", (directory / "lsm-guard.json").read_text(encoding="utf-8"))
        dropped = od.allow_record({"host_result": "PASS", "lsm_guard": "lsm_enabled"})
        self.assertEqual(dropped, {"lsm_guard": "lsm_enabled"})
        self.assertEqual(od.allow_record({"host_result": ""})["host_result"], "")

    def test_serial_window_names_a_page_failure(self) -> None:
        calls = {"n": 0}

        def first_then_timeout(argv, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    stdout="first boot\n",
                    stderr="Specify --start=100 in the next get-serial-port-output command\n",
                )
            raise subprocess.TimeoutExpired(argv, 180)

        with mock.patch.object(od.subprocess, "run", first_then_timeout):
            rc, blob, pages, error, note = od.read_serial_log("vantio-lab-oct08", "vantio-gcp-lab-1")
        self.assertEqual(rc, 0)
        self.assertEqual(pages, 1)
        self.assertEqual(error, "")
        self.assertIn("first boot\n", blob)
        self.assertNotIn("Specify --start=", blob)
        self.assertIn("--start=100", note)
        buf = io.StringIO()
        calls["n"] = 0
        with mock.patch.object(od.subprocess, "run", first_then_timeout), contextlib.redirect_stdout(buf):
            self.assertEqual(od._log_serial("vantio-lab-oct08", "vantio-gcp-lab-1", "boot"), 0)
        self.assertNotIn("SERIAL_ERROR=", buf.getvalue())

        def empty(argv, **_kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        with mock.patch.object(od.subprocess, "run", empty):
            _rc, blob, _pages, error, _note = od.read_serial_log("vantio-lab-oct08", "vantio-gcp-lab-1")
        self.assertEqual(blob, "")
        self.assertEqual(error, "empty")

        def warning_only(argv, **_kwargs):
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="\n",
                stderr="WARNING: some serial port output was lost\nSpecify --start=12 in the next get-serial-port-output command\n",
            )

        with mock.patch.object(od.subprocess, "run", warning_only):
            _rc, blob, _pages, error, note = od.read_serial_log("vantio-lab-oct08", "vantio-gcp-lab-1")
        self.assertEqual(error, "empty")
        self.assertNotIn("WARNING", blob)
        self.assertIn("WARNING", note)
        buf = io.StringIO()
        with mock.patch.object(od.subprocess, "run", warning_only), contextlib.redirect_stdout(buf):
            self.assertEqual(od._log_serial("vantio-lab-oct08", "vantio-gcp-lab-1", "boot"), 1)
        logged = buf.getvalue()
        self.assertIn("SERIAL_ERROR=empty", logged)
        self.assertIn("SERIAL_STDERR=", logged)
        self.assertLess(logged.index("SERIAL_BYTES="), logged.index("WARNING"))

        def first_call_times_out(argv, **_kwargs):
            raise subprocess.TimeoutExpired(argv, 180)

        with mock.patch.object(od.subprocess, "run", first_call_times_out):
            _rc, blob, pages, error, _note = od.read_serial_log("vantio-lab-oct08", "vantio-gcp-lab-1")
        self.assertEqual(blob, "")
        self.assertEqual(pages, 0)
        self.assertEqual(error, "page_timeout")

        def advancing(argv, **_kwargs):
            start = 0
            for arg in argv:
                if str(arg).startswith("--start="):
                    start = int(str(arg).split("=", 1)[1])
            nxt = start + 10
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=f"page-{start}\n",
                stderr=f"Specify --start={nxt} in the next get-serial-port-output command\n",
            )

        with mock.patch.object(od.subprocess, "run", advancing):
            _rc, blob, pages, error, _note = od.read_serial_log("vantio-lab-oct08", "vantio-gcp-lab-1")
        self.assertEqual(pages, 4)
        self.assertEqual(error, "")
        self.assertIn("page-0\n", blob)
        self.assertIn("page-30\n", blob)
        buf = io.StringIO()
        with mock.patch.object(od.subprocess, "run", advancing), contextlib.redirect_stdout(buf):
            self.assertEqual(od._log_serial("vantio-lab-oct08", "vantio-gcp-lab-1", "boot"), 0)
        self.assertNotIn("SERIAL_ERROR=", buf.getvalue())

        buf = io.StringIO()
        with mock.patch.object(od.subprocess, "run", empty), contextlib.redirect_stdout(buf):
            status = od.capture_serial(
                {"GCP_LAB_EXECUTE": "1", "GCP_LAB_PROJECT": "vantio-lab-oct08", "GITHUB_RUN_ID": "1"}
            )
        self.assertEqual(status, 1)
        self.assertIn("SERIAL_ERROR=empty", buf.getvalue())

    def _drive_lsm(self, *, live, rows, boots, probe=None, ssh_stdout="", serial_status=None):
        calls = {"ssh_case": [], "wait_boot": [], "ssh": 0, "probe": 0, "log": []}
        statuses = list(serial_status) if serial_status is not None else []

        def wait_live(_project, _name, _timeout):
            return live

        def ssh_case(_project, _name, command):
            calls["ssh_case"].append(command)
            return subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def rows_for(_project, _name, boot_id, _transcript):
            return rows(boot_id)

        def wait_boot(_project, _name, previous, _timeout):
            calls["wait_boot"].append(previous)
            return boots(previous)

        def probe_live(_project, _name):
            calls["probe"] += 1
            return {} if probe is None else probe

        def ssh(_project, _name, _command, timeout_s=20):
            calls["ssh"] += 1
            return subprocess.CompletedProcess([], 0, stdout=ssh_stdout, stderr="")

        def log_serial(_project, _name, boot_id=""):
            calls["log"].append(boot_id)
            if statuses:
                return statuses.pop(0)
            return 0

        stack = contextlib.ExitStack()
        for name, fn in (
            ("_wait_live_boot", wait_live),
            ("_ssh_case", ssh_case),
            ("_rows_for_boot", rows_for),
            ("_wait_boot", wait_boot),
            ("_log_serial", log_serial),
            ("_probe_live", probe_live),
            ("_ssh", ssh),
            ("_print_saved_boot_evidence", lambda *_args, **_kwargs: None),
        ):
            stack.enter_context(mock.patch.object(od, name, fn))
        return stack, calls

    def test_prepare_lab_lsm_follows_the_boot_it_waited_for(self) -> None:
        seal = "ab" * 32
        before = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        after = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        later = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        listed = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        sealed = f"BOOT_IMAGE=/vmlinuz ro lsm={listed} panic=-1"
        proved = {
            "cmdline": "panic=-1",
            "host_result": "GUARD_PROVED",
            "reboot_requested": True,
            "stock_lsm": "lockdown,capability,apparmor",
        }

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            stack, calls = self._drive_lsm(live="", rows=lambda _boot: {}, boots=lambda _prev: "")
            with stack:
                with self.assertRaises(SystemExit) as unread:
                    od._prepare_lab_lsm("vantio-lab-oct08", "vantio-gcp-lab-1", seal, evidence)
            self.assertEqual(unread.exception.code, "lsm")
            self.assertEqual(calls["ssh_case"], [])
            unread_body = json.loads((evidence / "lsm-guard.json").read_text(encoding="utf-8"))
            self.assertEqual(unread_body["lsm_guard"], "boot_id_unread")
            self.assertEqual(unread_body["host_result"], "")

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            stack, calls = self._drive_lsm(
                live=before,
                rows=lambda _boot: {**proved, "boot_id": "old-boot"},
                boots=lambda _prev: after,
            )
            with stack:
                with self.assertRaises(SystemExit) as stale:
                    od._prepare_lab_lsm("vantio-lab-oct08", "vantio-gcp-lab-1", seal, evidence)
            self.assertEqual(stale.exception.code, "lsm")
            self.assertEqual(calls["wait_boot"], [])
            self.assertEqual(len(calls["ssh_case"]), 1)
            stale_body = json.loads((evidence / "lsm-guard.json").read_text(encoding="utf-8"))
            self.assertEqual(stale_body["lsm_guard"], "stale_rows")
            self.assertEqual(stale_body["host_result"], "GUARD_PROVED")

        def rows_for(boot_id: str) -> dict:
            if boot_id == before:
                return {**proved, "boot_id": before}
            if boot_id == after:
                return {**proved, "boot_id": after}
            return {}

        def boots(previous: str) -> str:
            if previous == before:
                return after
            if previous == after:
                return later
            return ""

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            stack, calls = self._drive_lsm(
                live=before,
                rows=rows_for,
                boots=boots,
                probe={"boot_id": later, "cmdline": sealed, "enabled_lsm": listed},
            )
            with stack:
                record = od._prepare_lab_lsm("vantio-lab-oct08", "vantio-gcp-lab-1", seal, evidence)
            self.assertEqual(record["lsm_guard"], "lsm_enabled_follow_up")
            self.assertEqual(record["host_result"], "LSM_ENABLED")
            self.assertEqual(record["stock_lsm"], listed)
            self.assertIs(record["stock_bpf_lsm"], True)
            self.assertEqual(calls["wait_boot"], [before, after])
            self.assertEqual(calls["probe"], 1)
            self.assertEqual(calls["ssh"], 0)

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            stack, calls = self._drive_lsm(
                live=before,
                rows=lambda boot_id: {**proved, "boot_id": before} if boot_id == before else {**proved, "boot_id": "old-boot"},
                boots=lambda previous: after if previous == before else "",
                ssh_stdout=json.dumps({"boot_id": after, "cmdline": sealed, "enabled_lsm": listed}),
            )
            with stack:
                record = od._prepare_lab_lsm("vantio-lab-oct08", "vantio-gcp-lab-1", seal, evidence)
            self.assertEqual(record["lsm_guard"], "lsm_enabled")
            self.assertEqual(record["host_result"], "LSM_ENABLED")
            self.assertEqual(calls["ssh"], 1)
            self.assertEqual(calls["probe"], 0)
            self.assertEqual(calls["wait_boot"], [before])

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            stack, calls = self._drive_lsm(
                live=before,
                rows=lambda boot_id: {**proved, "boot_id": before} if boot_id == before else {},
                boots=lambda previous: after if previous == before else "",
                serial_status=[1],
            )
            with stack:
                with self.assertRaises(SystemExit) as missing:
                    od._prepare_lab_lsm("vantio-lab-oct08", "vantio-gcp-lab-1", seal, evidence)
            self.assertEqual(missing.exception.code, "lsm")
            self.assertEqual(calls["log"], [after])
            self.assertEqual(len(calls["ssh_case"]), 1)
            self.assertEqual(calls["probe"], 0)
            missing_body = json.loads((evidence / "lsm-guard.json").read_text(encoding="utf-8"))
            self.assertEqual(missing_body["lsm_guard"], "serial_missing")

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            stack, calls = self._drive_lsm(
                live=before,
                rows=rows_for,
                boots=boots,
                probe={"boot_id": later, "cmdline": sealed, "enabled_lsm": listed},
                serial_status=[0, 1],
            )
            with stack:
                with self.assertRaises(SystemExit) as follow_missing:
                    od._prepare_lab_lsm("vantio-lab-oct08", "vantio-gcp-lab-1", seal, evidence)
            self.assertEqual(follow_missing.exception.code, "lsm")
            self.assertEqual(calls["log"], [after, later])
            self.assertEqual(calls["probe"], 0)
            follow_body = json.loads((evidence / "lsm-guard.json").read_text(encoding="utf-8"))
            self.assertEqual(follow_body["lsm_guard"], "serial_missing")

        active = {
            "boot_id": before,
            "cmdline": "BOOT_IMAGE=/vmlinuz ro panic=-1",
            "host_result": "LSM_ALREADY_ACTIVE",
            "reboot_requested": False,
            "stock_lsm": listed,
        }
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            stack, calls = self._drive_lsm(
                live=before,
                rows=lambda boot_id: active if boot_id == before else {},
                boots=lambda _previous: "",
                serial_status=[1],
            )
            with stack:
                with self.assertRaises(SystemExit) as active_missing:
                    od._prepare_lab_lsm("vantio-lab-oct08", "vantio-gcp-lab-1", seal, evidence)
            self.assertEqual(active_missing.exception.code, "lsm")
            self.assertEqual(calls["log"], [before])
            self.assertEqual(calls["wait_boot"], [])
            active_body = json.loads((evidence / "lsm-guard.json").read_text(encoding="utf-8"))
            self.assertEqual(active_body["lsm_guard"], "serial_missing")

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            stack, calls = self._drive_lsm(
                live=before,
                rows=lambda boot_id: active if boot_id == before else {},
                boots=lambda _previous: "",
            )
            with stack:
                record = od._prepare_lab_lsm("vantio-lab-oct08", "vantio-gcp-lab-1", seal, evidence)
            self.assertEqual(record["lsm_guard"], "already_active")
            self.assertIs(record["stock_bpf_lsm"], True)
            self.assertEqual(calls["log"], [before])
            self.assertEqual(calls["wait_boot"], [])


DOCKER_CLEAN_RM = "rm -f /etc/apt/apt.conf.d/docker-clean"
LIVE_PURGE_RM = "rm -f /var/cache/apt/archives/*.deb"

_CA_PIN_STUBS = {
    "apt-cache": 'echo "apt-cache $*" >> "$STUB_LOG"\nprintf "%s" "${STUB_MADISON:-}"\n',
    # download drops a fake .deb in the cwd (the archive). A real install runs dpkg,
    # so when STUB_HOOK names an existing file it models ubuntu's docker-clean
    # DPkg::Post-Invoke hook and empties STUB_ARCHIVES.
    "apt-get": (
        'echo "apt-get $*" >> "$STUB_LOG"\n'
        'if [ "${1:-}" = download ]; then v=${2#*=}; : > "ca-certificates_${v}_all.deb"; fi\n'
        'if [ "${1:-}" = install ] && [[ " $* " != *" --download-only "* ]] '
        '&& [ -n "${STUB_HOOK:-}" ] && [ -e "$STUB_HOOK" ] && [ -n "${STUB_ARCHIVES:-}" ]; then\n'
        '  rm -f "$STUB_ARCHIVES"/*.deb\n'
        'fi\n'
    ),
    "update-ca-certificates": 'echo "update-ca-certificates $*" >> "$STUB_LOG"\n',
    "dpkg-query": 'echo "dpkg-query $*" >> "$STUB_LOG"\nprintf "%s" "${STUB_INSTALLED:-}"\n',
}


class CaPinBehaviourTest(unittest.TestCase):
    """Run the fetch script's ca-certificates block with stubbed apt tools."""

    def _block(self) -> str:
        text = (ROOT / "scripts/gcp/fetch_offline_debs.sh").read_text(encoding="utf-8")
        start = text.index("# BEGIN ca-pin")
        end = text.index("# END ca-pin")
        return text[start:end]

    def _run(self, madison: str, installed: str) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stubs = base / "bin"
            stubs.mkdir()
            for name, body in _CA_PIN_STUBS.items():
                path = stubs / name
                path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
                path.chmod(0o755)
            archives = base / "archives"
            archives.mkdir()
            log = base / "log"
            log.write_text("", encoding="utf-8")
            env = dict(os.environ)
            env.update(
                {
                    "PATH": f"{stubs}{os.pathsep}{env.get('PATH', '')}",
                    "STUB_LOG": str(log),
                    "STUB_MADISON": madison,
                    "STUB_INSTALLED": installed,
                }
            )
            script = "set -euo pipefail\narchives=" + str(archives) + "\n" + self._block()
            result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30)
            calls = log.read_text(encoding="utf-8").splitlines()
        return result, calls

    def test_empty_madison_exits_non_zero_before_any_download(self) -> None:
        result, calls = self._run("", "20240203")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no ca-certificates version", result.stderr)
        self.assertEqual(calls, ["apt-cache madison ca-certificates"])

    def test_snapshot_version_is_downloaded_installed_and_asserted(self) -> None:
        madison = (
            "ca-certificates | 20240203 | https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble-updates/main amd64 Packages\n"
            "ca-certificates | 20230311ubuntu1 | https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble/main amd64 Packages\n"
        )
        result, calls = self._run(madison, "20240203")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            calls,
            [
                "apt-cache madison ca-certificates",
                "apt-get download ca-certificates=20240203",
                "apt-get install -y --allow-downgrades --no-install-recommends ca-certificates=20240203",
                "update-ca-certificates --fresh",
                "dpkg-query -W -f=${Version} ca-certificates",
            ],
        )

    def test_installed_version_mismatch_exits_non_zero(self) -> None:
        madison = "ca-certificates | 20240203 | https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble-updates/main amd64 Packages\n"
        result, _calls = self._run(madison, "20260816ubuntu0.24.04.1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is not the snapshot's 20240203", result.stderr)

    def test_bundle_is_copied_after_the_snapshot_install(self) -> None:
        text = (ROOT / "scripts/gcp/fetch_offline_debs.sh").read_text(encoding="utf-8")
        snapshot = text.index("snapshot.ubuntu.com")
        install = text.index("--allow-downgrades")
        self.assertLess(snapshot, install)
        self.assertLess(install, text.index("update-ca-certificates"))
        self.assertLess(text.index("# END ca-pin"), text.index("cp /etc/ssl/certs/ca-certificates.crt /out/ca-certificates.crt"))


    def test_docker_clean_is_removed_before_any_apt_install_or_dpkg_call(self) -> None:
        # ubuntu:24.04's docker-clean hook empties the apt archive after every dpkg
        # run and after apt-get update (provision 39857348011 lost every .deb).
        text = (ROOT / "scripts/gcp/fetch_offline_debs.sh").read_text(encoding="utf-8")
        body = text[text.index("script=$(cat <<'EOS'"):]
        lines = [line.strip() for line in body.splitlines()]
        self.assertIn(DOCKER_CLEAN_RM, lines, "fetch_offline_debs.sh must remove docker-clean in the container")
        hook = lines.index(DOCKER_CLEAN_RM)
        calls = [
            index
            for index, line in enumerate(lines)
            if not line.startswith("#")
            and re.search(r"\bapt-get (update|install|download)\b|\bdpkg\b(?!-query)|\bapt\b ", line)
        ]
        self.assertTrue(calls)
        self.assertLess(hook, min(calls))
        self.assertLess(text.index("--allow-downgrades"), text.index('cp "$archives"/*.deb /out/'))
        # Only inside the throwaway container script, never on the runner itself.
        self.assertEqual(text.count("docker-clean"), body.count("docker-clean"))

    def _run_with_hook(self, remove_hook: bool) -> list[str]:
        madison = "ca-certificates | 20240203 | https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble-updates/main amd64 Packages\n"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stubs = base / "bin"
            stubs.mkdir()
            for name, body in _CA_PIN_STUBS.items():
                path = stubs / name
                path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
                path.chmod(0o755)
            archives = base / "archives"
            archives.mkdir()
            (archives / "docker.io_24.0.7_amd64.deb").write_text("", encoding="utf-8")
            hook = base / "docker-clean"
            hook.write_text("DPkg::Post-Invoke {};\n", encoding="utf-8")
            log = base / "log"
            log.write_text("", encoding="utf-8")
            env = dict(os.environ)
            env.update(
                {
                    "PATH": f"{stubs}{os.pathsep}{env.get('PATH', '')}",
                    "STUB_LOG": str(log),
                    "STUB_MADISON": madison,
                    "STUB_INSTALLED": "20240203",
                    "STUB_HOOK": str(hook),
                    "STUB_ARCHIVES": str(archives),
                }
            )
            # The script's own removal line, pointed at the stand-in hook file.
            prelude = DOCKER_CLEAN_RM.replace("/etc/apt/apt.conf.d/docker-clean", str(hook)) if remove_hook else ":"
            script = "set -euo pipefail\narchives=" + str(archives) + "\n" + prelude + "\n" + self._block()
            result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return sorted(path.name for path in archives.glob("*.deb"))

    def test_archive_keeps_debs_through_the_ca_pin_install_once_hook_is_removed(self) -> None:
        self.assertIn(DOCKER_CLEAN_RM, (ROOT / "scripts/gcp/fetch_offline_debs.sh").read_text(encoding="utf-8").splitlines())
        self.assertEqual(
            self._run_with_hook(remove_hook=True),
            ["ca-certificates_20240203_all.deb", "docker.io_24.0.7_amd64.deb"],
        )

    def test_hook_left_in_place_empties_the_archive(self) -> None:
        # Control: the stub hook reproduces the 39857348011 failure.
        self.assertEqual(self._run_with_hook(remove_hook=False), [])

    def test_live_archive_debs_are_purged_before_the_snapshot_fetch(self) -> None:
        text = (ROOT / "scripts/gcp/fetch_offline_debs.sh").read_text(encoding="utf-8")
        lines = [line.strip() for line in text.splitlines()]
        live = "apt-get install -y --no-install-recommends ca-certificates"
        snapshot = "apt-get install -y --download-only --no-install-recommends \\"
        for needle in (live, snapshot, LIVE_PURGE_RM):
            self.assertIn(needle, lines, f"fetch_offline_debs.sh is missing: {needle}")
        self.assertLess(lines.index(live), lines.index(LIVE_PURGE_RM))
        self.assertLess(lines.index(LIVE_PURGE_RM), lines.index(snapshot))

    def _run_container_script(self, purge_live: bool) -> list[str]:
        """Run the whole container script with fake apt tools and temp paths.

        The fake live install leaves the debs it installed (openssl and the live
        ca-certificates) in the archive, as apt does once docker-clean is gone.
        Returns the .deb names that reach /out.
        """
        text = (ROOT / "scripts/gcp/fetch_offline_debs.sh").read_text(encoding="utf-8")
        start = text.index("script=$(cat <<'EOS'\n") + len("script=$(cat <<'EOS'\n")
        body = text[start : text.index("\nEOS\n", start)]
        if not purge_live:
            self.assertIn(LIVE_PURGE_RM + "\n", body)
            body = body.replace(LIVE_PURGE_RM + "\n", "", 1)
        madison = "ca-certificates | 20240203 | https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble-updates/main amd64 Packages\n"
        stubs_src = {
            "apt-cache": 'printf "%s" "$STUB_MADISON"\n',
            "update-ca-certificates": "exit 0\n",
            "dpkg-query": 'printf "%s" 20240203\n',
            "apt-get": (
                'case " $* " in\n'
                '  *" download "*) v=${2#*=}; : > "ca-certificates_${v}_all.deb" ;;\n'
                '  *" --download-only "*) for d in docker.io_24.0.7-0ubuntu4.1_amd64 python3-cryptography_41.0.7-4ubuntu0.4_amd64 '
                'strace_6.8-0ubuntu2_amd64 ca-certificates_20240203_all; do : > "$STUB_ARCHIVES/$d.deb"; done ;;\n'
                '  *" --allow-downgrades "*) : ;;\n'
                '  *" install "*) : > "$STUB_ARCHIVES/openssl_3.0.13-0ubuntu3.16_amd64.deb"; '
                ': > "$STUB_ARCHIVES/ca-certificates_20260816ubuntu0.24.04.1_all.deb" ;;\n'
                "esac\n"
            ),
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stubs = base / "bin"
            stubs.mkdir()
            for name, src in stubs_src.items():
                path = stubs / name
                path.write_text("#!/bin/bash\n" + src, encoding="utf-8")
                path.chmod(0o755)
            archives = base / "archives"
            archives.mkdir()
            out = base / "out"
            out.mkdir()
            etc = base / "etc"
            (etc / "apt/apt.conf.d").mkdir(parents=True)
            (etc / "apt/apt.conf.d/docker-clean").write_text("", encoding="utf-8")
            (etc / "ssl/certs").mkdir(parents=True)
            (etc / "ssl/certs/ca-certificates.crt").write_text("bundle\n", encoding="utf-8")
            script = (
                body.replace("/var/cache/apt/archives", str(archives))
                .replace("/etc/", f"{etc}/")
                .replace("/out/", f"{out}/")
            )
            # Never let the run touch the real /out, /etc or apt archive.
            live_lines = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
            for real in (" /out", " /etc/", " /var/"):
                self.assertFalse([line for line in live_lines if real in line], real)
            env = dict(os.environ)
            env.update(
                {
                    "PATH": f"{stubs}{os.pathsep}{env.get('PATH', '')}",
                    "STUB_MADISON": madison,
                    "STUB_ARCHIVES": str(archives),
                }
            )
            result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out / "ca-certificates.crt").is_file())
            return sorted(path.name for path in out.glob("*.deb"))

    def test_nothing_from_the_live_install_reaches_out(self) -> None:
        staged = self._run_container_script(purge_live=True)
        self.assertNotIn("openssl_3.0.13-0ubuntu3.16_amd64.deb", staged)
        self.assertNotIn("ca-certificates_20260816ubuntu0.24.04.1_all.deb", staged)
        self.assertEqual(
            staged,
            [
                "ca-certificates_20240203_all.deb",
                "docker.io_24.0.7-0ubuntu4.1_amd64.deb",
                "python3-cryptography_41.0.7-4ubuntu0.4_amd64.deb",
                "strace_6.8-0ubuntu2_amd64.deb",
            ],
        )

    def test_without_the_purge_live_openssl_reaches_out(self) -> None:
        # Control: this is the leak council flagged on a769757.
        self.assertIn("openssl_3.0.13-0ubuntu3.16_amd64.deb", self._run_container_script(purge_live=False))


class PublicPinHandoffTest(unittest.TestCase):
    """2c-upgrade-rollback needs public-pin.oci.tar beside seal.oci.tar on the GCP guest."""

    RUN = "39820831363"

    def _pin(self, directory: Path) -> tuple[Path, str]:
        path = directory / od.PUBLIC_PIN_FILE
        path.write_bytes(b"public-pin-bytes" * 64)
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_file_name_matches_the_guest_and_aws(self) -> None:
        host = (ROOT / "scripts/aws/lab-guests/phase2_host.py").read_text(encoding="utf-8")
        self.assertIn(f'HERE / "{od.PUBLIC_PIN_FILE}"', host)
        self.assertEqual(od.PUBLIC_PIN_FILE, enterprise_bundle.PUBLIC_PIN_FILE)
        self.assertEqual(od.PUBLIC_INSTALLER_PIN, enterprise_bundle.PUBLIC_INSTALLER_PIN)

    def test_handoff_objects_carry_the_pin_only_for_batteries(self) -> None:
        base = {"GITHUB_RUN_ID": self.RUN, "REDTEAM_BRAIN": "false"}
        pin = f"{self.RUN}/public-pin.oci.tar"
        self.assertNotIn(pin, od.handoff_objects({**base, "RUN_BATTERIES": "false"}))
        self.assertNotIn(pin, od.handoff_objects(base))
        self.assertIn(pin, od.handoff_objects({**base, "RUN_BATTERIES": "true"}))

    def test_verify_refuses_absent_and_wrong_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with self.assertRaises(SystemExit) as absent:
                od.verify_public_pin_file(directory / od.PUBLIC_PIN_FILE)
            self.assertEqual(absent.exception.code, "public_pin_absent")
            path, digest = self._pin(directory)
            with self.assertRaises(SystemExit) as wrong:
                od.verify_public_pin_file(path)
            self.assertEqual(wrong.exception.code, "public_pin_digest")
            with mock.patch.dict(od.__dict__, {"PUBLIC_INSTALLER_PIN": digest}):
                self.assertEqual(od.verify_public_pin_file(path), digest)

    def _upload(self, run_batteries: str, directory: Path) -> list[str]:
        uploaded: list[str] = []
        env = {
            "GCP_LAB_EXECUTE": "1",
            "GCP_LAB_PROJECT": "vantio-lab-oct08",
            "GITHUB_RUN_ID": self.RUN,
            "W3_BUNDLE_DIR": str(directory),
            "EVIDENCE_DIR": str(directory / "evidence"),
            "REDTEAM_BRAIN": "false",
            "RUN_BATTERIES": run_batteries,
        }
        checked = {"seal_sha256": "a" * 64, "contract_sha256": "b" * 64, "trust_sha256": "c" * 64}
        with mock.patch.dict(
            od.__dict__,
            {
                "assert_bundle_dir": lambda _d, _e: checked,
                "expected_seal": lambda _env: "a" * 64,
                "upload_one": lambda _b, name, _p, max_bytes: uploaded.append(name) or "uploaded",
                "github_output": lambda *_a: None,
            },
        ), contextlib.redirect_stdout(io.StringIO()):
            od.upload_handoff(env)
        return uploaded

    def test_upload_sends_the_verified_pin_with_batteries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.assertEqual(len(self._upload("false", directory)), 2)
            with self.assertRaises(SystemExit) as absent:
                self._upload("true", directory)
            self.assertEqual(absent.exception.code, "public_pin_absent")
            _path, digest = self._pin(directory)
            with mock.patch.dict(od.__dict__, {"PUBLIC_INSTALLER_PIN": digest}):
                names = self._upload("true", directory)
            self.assertEqual(names[-1], f"{self.RUN}/public-pin.oci.tar")

    def test_download_reverifies_the_pin_and_deletes_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "bundle"
            source = Path(tmp) / "src"
            source.mkdir()
            _path, digest = self._pin(source)
            deleted: list[tuple[str, ...]] = []

            def fake_download(_bucket: str, name: str, path: Path) -> None:
                if name.endswith(od.PUBLIC_PIN_FILE):
                    path.write_bytes((source / od.PUBLIC_PIN_FILE).read_bytes())
                else:
                    path.write_bytes(b"x")

            env = {
                "GCP_LAB_EXECUTE": "1",
                "GCP_LAB_PROJECT": "vantio-lab-oct08",
                "GITHUB_RUN_ID": self.RUN,
                "W3_BUNDLE_DIR": str(directory),
                "EVIDENCE_DIR": str(Path(tmp) / "evidence"),
                "EXPECTED_CONTRACT_SHA256": "b" * 64,
                "REDTEAM_BRAIN": "false",
                "RUN_BATTERIES": "true",
            }
            patches = {
                "download_one": fake_download,
                "verify_seal_file": lambda _p, _e: "a" * 64,
                "expected_seal": lambda _env: "a" * 64,
                "verify_contract_trust": lambda _p, _t: "b" * 64,
                "delete_objects": lambda names, missing_ok: deleted.append(tuple(names)),
                "PUBLIC_INSTALLER_PIN": digest,
            }
            with mock.patch.dict(od.__dict__, patches), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(od.download_handoff(env), 0)
            self.assertEqual(json.loads(out.getvalue())["public_pin_sha256"], digest)
            self.assertEqual(od.verify_public_pin_file.__name__, "verify_public_pin_file")
            self.assertTrue((directory / od.PUBLIC_PIN_FILE).is_file())
            self.assertIn(f"{self.RUN}/public-pin.oci.tar", deleted[-1])
            (source / od.PUBLIC_PIN_FILE).write_bytes(b"tampered")
            with mock.patch.dict(od.__dict__, patches), self.assertRaises(SystemExit) as bad:
                od.download_handoff(env)
            self.assertEqual(bad.exception.code, "public_pin_digest")
            self.assertIn(f"{self.RUN}/public-pin.oci.tar", deleted[-1])

    def test_pin_reaches_the_guest_and_stays_there(self) -> None:
        stage_src = (ROOT / "scripts/gcp/offline_deliver_2.py").read_text(encoding="utf-8")
        stage = stage_src[stage_src.index("def _stage_payload("):]
        stage = stage[: stage.index("    return rows")]
        self.assertIn("dest / PUBLIC_PIN_FILE", stage)
        self.assertIn("verify_public_pin_file(dest / PUBLIC_PIN_FILE)", stage)
        deliver_src = (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8")
        upload = deliver_src[deliver_src.index("debs = _stage_payload(env, payload_dir)"):]
        upload = upload[: upload.index("lsm = _prepare_lab_lsm(")]
        self.assertIn("payload_dir / PUBLIC_PIN_FILE", upload)
        unlinked = upload[upload.index("for local_name in"):]
        self.assertNotIn("public-pin", unlinked)
        self.assertNotIn("PUBLIC_PIN_FILE", unlinked)

    def test_workflow_stages_and_carries_the_pin_for_batteries(self) -> None:
        workflow = (ROOT / ".github/workflows/gcp-lab-provision.yml").read_text(encoding="utf-8")
        prepare = workflow[workflow.index("- name: Prepare and verify the private bundle"):]
        prepare = prepare[: prepare.index("assert-bundle")]
        self.assertIn("W3_BATTERY: ${{ inputs.run_batteries == true && '2c-upgrade-rollback' || '' }}", prepare)
        for command in ("upload-handoff", "download-handoff", "delete-handoff", "teardown-if-present"):
            with self.subTest(command=command):
                end = workflow.index(f"offline_deliver.py {command}")
                step = workflow[workflow.rindex("- name:", 0, end): end]
                self.assertIn("RUN_BATTERIES: ${{ inputs.run_batteries == true && 'true' || 'false' }}", step)


class DescendantStartFieldsTest(unittest.TestCase):
    """#357 descendant-b1 start fields, the loaded image tag, and the 2D row wait reach gcp-lab-rows.json."""

    BOOT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    LATER = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def _body(self, phase: str) -> dict:
        return {
            "phase": phase,
            "hostname": "vantio-gcp-lab-1",
            "image": "vantio-phantom-engine:da961aa9",
            "boot_id": self.BOOT if phase == "pre" else self.LATER,
            "boot_lsm": {
                "lsm": "lockdown,capability,landlock,yama,apparmor,bpf,ima,evm",
                "bpf_lsm_active": True,
                "cmdline_lsm": "lockdown,capability,landlock,yama,apparmor,bpf,ima,evm",
            },
            "cases": [
                {
                    "name": "moved",
                    "pass": False,
                    "samples": [{"name": "moved", "expect_deny": True, "pass": False, "file_errno": 13, "pid": 4100}],
                }
            ],
            "failed_cases": ["moved"],
            "scoped_banner": "scoped_banner_without_ledger_line",
            "start_timing": {
                "ledger_since": 120,
                "banner_wait_s": 4.012,
                "probe_done_after_banner_s": 0.21,
                "ledger_seen": False,
                "banner_to_ledger_s": None,
                "ledger_timeout_s": 30.1,
                "start_wait_s": 34.3,
                "hostname": "leak",
            },
            "start_probe": {
                "pid": 4099,
                "file_errno": 13,
                "lineage_anchor": 0,
                "took_s": 0.05,
                "file_event": None,
                "path": "/etc/shadow",
            },
            "start_window_rows": {
                "status": "delayed",
                "delayed": 1,
                "dropped": 0,
                "checked": [
                    {
                        "name": "start_probe",
                        "pid": 4099,
                        "file_errno": 13,
                        "row_index": 7,
                        "status": "recorded",
                        "after_ledger_line": False,
                        "row_time": "2026-10-22T17:30:01.5Z",
                    },
                    {"name": "moved", "pid": 4100, "row_index": 9, "status": "delayed", "after_ledger_line": True},
                    {"name": "Bad Name", "status": "dropped"},
                ],
                "ledger_line_index": 8,
                "ledger_line_time": 1792690201.5,
                "informational": True,
            },
            "warnings": ["scoped_banner=scoped_banner_without_ledger_line", "ghp_" + "a" * 30],
            "descendant_pass": False,
        }

    def test_allow_start_fields_keeps_typed_values_only(self) -> None:
        kept = od.allow_start_fields(self._body("pre"))
        self.assertEqual(
            set(kept), {"start_timing", "start_probe", "start_window_rows", "warnings", "boot_lsm"}
        )
        self.assertNotIn("hostname", kept["start_timing"])
        self.assertIsNone(kept["start_timing"]["banner_to_ledger_s"])
        self.assertIs(kept["start_timing"]["ledger_seen"], False)
        self.assertNotIn("path", kept["start_probe"])
        self.assertIs(kept["start_probe"]["file_event"], False)
        self.assertEqual([item["name"] for item in kept["start_window_rows"]["checked"]], ["start_probe", "moved"])
        self.assertEqual(kept["warnings"], ["scoped_banner=scoped_banner_without_ledger_line"])
        self.assertTrue(kept["boot_lsm"]["bpf_lsm_active"])
        self.assertEqual(od.allow_start_fields({"lab_lsm_reassert": None}), {"lab_lsm_reassert": None})
        reassert = od.allow_start_fields(
            {"lab_lsm_reassert": {"ok": True, "written": True, "reason": "guard_record", "lsm_value": "bpf", "boot_id": self.BOOT, "x": 1}}
        )["lab_lsm_reassert"]
        self.assertEqual(set(reassert), {"ok", "written", "reason", "lsm_value", "boot_id"})
        error = od.allow_start_fields({"start_probe": {"error": "OSError: /root/secret token=abc"}})
        self.assertEqual(error["start_probe"], {"error": "OSError"})

    def test_loaded_image_tag_replaces_the_lab_constant(self) -> None:
        text = "x\nLoaded image: vantio-phantom-engine:da961aa9\nIMAGE_LINE=vantio-phantom-engine:da961aa9\n"
        self.assertEqual(od.loaded_image_from_text(text), "vantio-phantom-engine:da961aa9")
        self.assertEqual(
            od.loaded_image_from_text("Loaded image: docker.io/library/vantio-phantom-engine:egress-2e6ab54\n"),
            od.IMAGE_NAME,
        )
        for bad in ("Loaded image: vantio-phantom-engine:latest", "Loaded image: evil:da961aa9", "Loaded image: vantio-phantom-engine:DA961AA9", ""):
            with self.subTest(bad=bad):
                self.assertEqual(od.loaded_image_from_text(bad), "")
        self.assertEqual(od.allow_record({"image": "vantio-phantom-engine:da961aa9"})["image"], "vantio-phantom-engine:da961aa9")
        self.assertNotIn("image", od.allow_record({"image": "vantio-phantom-engine:latest"}))
        self.assertEqual(od.allow_record({"image": f"{od.IMAGE_PROJECT}/{od.IMAGE_FAMILY}"})["image"], f"{od.IMAGE_PROJECT}/{od.IMAGE_FAMILY}")
        self.assertEqual(od.allow_battery({"image": "vantio-phantom-engine:" + "a" * 40}), {"image": "vantio-phantom-engine:" + "a" * 40})
        self.assertIsNone(od.allow_battery({"image": "vantio-phantom-engine:" + "a" * 41}))
        source = (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8")
        self.assertNotIn('"image": IMAGE_NAME', source)
        shell = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertIn("vantio-phantom-engine:(egress-2e6ab54|[0-9a-f]{7,40})", shell)

    def test_objects_keep_the_public_pin_handoff_name(self) -> None:
        kept = od.allow_record({"objects": ["1/seal.oci.tar", "1/public-pin.oci.tar", "1/other.tar"]})
        self.assertEqual(kept["objects"], ["1/seal.oci.tar", "1/public-pin.oci.tar"])

    def test_run_one_battery_carries_start_fields_and_image_into_rows(self) -> None:
        seal = "ab" * 32
        pre_guest = {"pre": self._body("pre"), "reboot_requested": True, "failed_cases": ["moved"]}
        post_guest = {
            "battery": "descendant-b1",
            "pre": self._body("pre"),
            "post": self._body("post"),
            "reboot_observed": True,
            "lab_lsm_reassert": None,
            "b1_pass": False,
            "descendant_pass": False,
        }
        pulls = [{"image": "vantio-phantom-engine:da961aa9"}, pre_guest, post_guest]
        loaded = "Loaded image: vantio-phantom-engine:da961aa9\nPY_RC=1\n"

        def ssh_case(_project, _name, _command):
            return subprocess.CompletedProcess([], 1, stdout=loaded, stderr="")

        captures: list[dict] = []
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            for name, fn in (
                ("_ssh_case", ssh_case),
                ("_pull_guest_json", lambda *_a: pulls.pop(0)),
                ("_scp_from", lambda *_a: False),
                ("_wait_ssh", lambda *_a: self.BOOT),
                ("_wait_boot", lambda *_a: self.LATER),
                ("_ssh_ready", lambda *_a, **_k: True),
            ):
                stack.enter_context(mock.patch.object(od, name, fn))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            summary = od._run_one_battery("vantio-lab-oct08", "vantio-gcp-lab-1", seal, Path(tmp), 1, captures)
            od.write_evidence(Path(tmp) / "gcp-lab-rows.json", {"captures": captures, "repeats": [summary, summary], "image": summary["image"]})
            rows = json.loads((Path(tmp) / "gcp-lab-rows.json").read_text(encoding="utf-8"))
        self.assertEqual(rows["image"], "vantio-phantom-engine:da961aa9")
        self.assertEqual(rows["repeats"][0]["rows"]["image"], "vantio-phantom-engine:da961aa9")
        by_name = {item["name"]: item for item in rows["captures"]}
        for name in ("descendant-pre-1", "descendant-post-1"):
            with self.subTest(capture=name):
                capture = by_name[name]
                for key in ("start_timing", "start_probe", "start_window_rows", "warnings", "boot_lsm"):
                    self.assertIn(key, capture)
                self.assertEqual(capture["image"], "vantio-phantom-engine:da961aa9")
                self.assertEqual(capture["start_window_rows"]["status"], "delayed")
                self.assertNotIn("hostname", json.dumps(capture))
        self.assertIn("lab_lsm_reassert", by_name["descendant-post-1"])
        self.assertIsNone(by_name["descendant-post-1"]["lab_lsm_reassert"])
        self.assertNotIn("lab_lsm_reassert", by_name["descendant-pre-1"])
        post = rows["repeats"][0]["post"]
        self.assertEqual(post["image"], "vantio-phantom-engine:da961aa9")
        self.assertEqual(post["start_timing"]["ledger_since"], 120)
        self.assertEqual(rows["repeats"][0]["pre"]["boot_lsm"]["cmdline_lsm"].split(",")[-1], "evm")

    def test_loader_kill_capture_names_the_missing_row_and_the_wait(self) -> None:
        body = {
            "enroll_restart": {
                "held": False,
                "reason": "deny_row_missing_before_restart",
                "pid": 3612,
                "before_errno": 13,
                "before_anchor": 0,
                "before_count": 0,
                "before_row_wait_s": 5.002,
                "before_row_seen": False,
            },
            "reason": "deny_row_missing_before_restart",
        }
        capture = od._loader_capture("loader-kill", {"body": body, "word": "fail", "rc": 1})
        kept = od._allow_capture(capture)
        self.assertIn("deny_row_missing_before_restart", kept["fail_reasons"])
        self.assertEqual(kept["before_row_wait_s"], 5.002)
        self.assertIs(kept["before_row_seen"], False)
        self.assertIs(kept["hold"], False)
        held = od._loader_capture("loader-kill", {"body": {"enroll_restart": {"held": True, "reason": "x"}}, "word": "held"})
        self.assertNotIn("x", held.get("fail_reasons", []))

    def test_loader_kill_capture_flags_a_late_row_before_and_after(self) -> None:
        restart = {
            "held": True,
            "reason": None,
            "before_row_wait_s": 1.25,
            "before_row_seen": True,
            "after_row_wait_s": 0.75,
            "after_row_seen": True,
            "warnings": ["late_deny_row_before_restart", "ghp_" + "a" * 30],
        }
        capture = od._loader_capture("loader-kill", {"body": {"enroll_restart": restart}, "word": "held"})
        kept = od._allow_capture(capture)
        self.assertEqual(kept["warnings"], ["late_deny_row_before_restart", "late_deny_row_after_restart"])
        self.assertEqual(kept["after_row_wait_s"], 0.75)
        self.assertIs(kept["after_row_seen"], True)
        # On time (<= 0.5s): recorded, not flagged.
        quick = dict(restart, before_row_wait_s=0.5, after_row_wait_s=0.25, warnings=[])
        kept = od._allow_capture(od._loader_capture("loader-kill", {"body": {"enroll_restart": quick}, "word": "held"}))
        self.assertNotIn("warnings", kept)
        self.assertEqual(kept["before_row_wait_s"], 0.5)
        # A row that never came is a fail, never a late-row warning.
        missing = {
            "held": False,
            "reason": "anchor_changed_or_missing",
            "before_row_wait_s": 0.25,
            "before_row_seen": True,
            "after_row_wait_s": 5.0,
            "after_row_seen": False,
        }
        kept = od._allow_capture(od._loader_capture("loader-kill", {"body": {"enroll_restart": missing}, "word": "fail"}))
        self.assertIs(kept["hold"], False)
        self.assertIn("anchor_changed_or_missing", kept["fail_reasons"])
        self.assertNotIn("warnings", kept)
        self.assertIs(kept["after_row_seen"], False)

    def test_allow_record_stores_the_normalised_image(self) -> None:
        kept = od.allow_record({"image": "docker.io/library/vantio-phantom-engine:da961aa9"})
        self.assertEqual(kept["image"], "vantio-phantom-engine:da961aa9")
        kept = od.allow_record({"image": " vantio-phantom-engine:da961aa9\n"})
        self.assertEqual(kept["image"], "vantio-phantom-engine:da961aa9")
        for bad in ("docker.io/library/evil:da961aa9", "ghcr.io/x/vantio-phantom-engine:da961aa9", 7, None, ["vantio-phantom-engine:da961aa9"]):
            with self.subTest(bad=bad):
                self.assertNotIn("image", od.allow_record({"image": bad}))

    def test_sanitizers_drop_forged_and_oversized_values(self) -> None:
        cases = {
            "start_probe": (
                {
                    "pid": 4099.0,
                    "file_errno": True,
                    "net_errno": 256,
                    "lineage_anchor": 2**33,
                    "took_s": 1e9,
                    "pass": "true",
                    "token": "ghp_" + "a" * 30,
                },
                {},
            ),
            "start_timing": (
                {
                    "ledger_since": -1,
                    "banner_wait_s": float("nan"),
                    "start_wait_s": "4",
                    "ledger_timeout_s": True,
                    "ledger_seen": 1,
                    "probe_done_after_banner_s": 3601,
                },
                {},
            ),
            "boot_lsm": ({"lsm": "bpf;rm -rf /", "cmdline_lsm": "x" * 121, "bpf_lsm_active": "yes"}, {}),
            "lab_lsm_reassert": (
                {"ok": "true", "reason": "R" * 5, "lsm_value": "BPF", "boot_id": "not-a-boot", "secret": "s"},
                {},
            ),
        }
        for key, (forged, expected) in cases.items():
            with self.subTest(field=key):
                self.assertEqual(od.allow_start_fields({key: forged})[key], expected)
        for key in ("start_probe", "start_timing", "boot_lsm", "lab_lsm_reassert", "start_window_rows", "warnings"):
            for wrong in ("x", 7, 1.5, True, ["x"] if key != "warnings" else {"a": "b"}):
                with self.subTest(field=key, wrong=wrong):
                    self.assertNotIn(key, od.allow_start_fields({key: wrong}))
        window = od.allow_start_fields(
            {
                "start_window_rows": {
                    "status": "all_good",
                    "delayed": 1001,
                    "dropped": -1,
                    "ledger_line_index": 2.5,
                    "ledger_line_time": "1; drop table",
                    "checked": [{"name": f"p{i}", "status": "recorded", "pid": i} for i in range(100)]
                    + [
                        {"name": "x", "status": "forged"},
                        {"name": "Bad Name", "status": "recorded"},
                        {"name": "y", "status": "delayed", "pid": 1.0, "file_errno": 999, "row_index": -3, "row_time": True},
                    ],
                    "error": "ValueError: /home/secret/path",
                }
            }
        )["start_window_rows"]
        self.assertNotIn("status", window)
        self.assertNotIn("delayed", window)
        self.assertNotIn("dropped", window)
        self.assertNotIn("ledger_line_index", window)
        self.assertNotIn("ledger_line_time", window)
        self.assertEqual(len(window["checked"]), 24)
        self.assertEqual(window["error"], "ValueError")
        tail = od._allow_start_window({"checked": [{"name": "y", "status": "delayed", "pid": 1.0, "file_errno": 999, "row_index": -3, "row_time": True}]})
        self.assertEqual(tail["checked"], [{"name": "y", "status": "delayed"}])
        self.assertEqual(od._allow_start_window({"checked": [{"name": "x", "status": "forged"}]})["checked"], [])
        warnings = od.allow_start_fields(
            {"warnings": ["scoped_banner=missing"] * 20 + ["late_deny_row_before_restart"]}
        )["warnings"]
        self.assertEqual(len(warnings), 8)
        bad = od.allow_start_fields(
            {
                "warnings": [
                    "ghp_" + "a" * 30,
                    "late_deny_row_during_restart",
                    "A=b",
                    "a=b",
                    "scoped_banner=scoped",
                    "scoped_banner=missing_x",
                    "mid_scoped_banner=missing",
                    "token=abc123",
                    "a=" + "b" * 61,
                    "k" * 41 + "=v",
                    7,
                    None,
                    "late_deny_row_after_restart",
                ]
            }
        )["warnings"]
        self.assertEqual(bad, ["late_deny_row_after_restart"])
        good = [
            "scoped_banner=missing",
            "pre_scoped_banner=not_checked",
            "post_scoped_banner=scoped_banner_without_ledger_line",
            "late_deny_row_before_restart",
        ]
        self.assertEqual(od.allow_start_fields({"warnings": good})["warnings"], good)
        # Capture- and battery-level copies use the same rules.
        capture = od._allow_capture(
            {"name": "loader-kill", "before_row_wait_s": True, "after_row_wait_s": 3601, "after_row_seen": "yes", "start_probe": {"pid": 1.5}}
        )
        for key in ("before_row_wait_s", "after_row_wait_s", "after_row_seen"):
            self.assertNotIn(key, capture)
        self.assertEqual(capture.get("start_probe"), {})
        self.assertIsNone(od.allow_battery({"start_probe": "x"}))

    def test_descendant_pre_clears_enterprise_rows_and_reassert_record(self) -> None:
        shell = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        branch = shell.split('if [ "$mode" = "descendant-b1" ]; then', 1)[1]
        pre_rm = branch.split('if [ "$phase" = "pre" ]; then', 1)[1].split("fi", 1)[0]
        for path in (
            "/var/lib/vantio-lab/b1-pre.json",
            "/var/lib/vantio-lab/enterprise-pe-rows.json",
            "/var/lib/vantio-lab/lsm-reassert.json",
        ):
            self.assertIn(path, pre_rm)
        run = branch.index('python3 "$here/descendant_b1.py"')
        self.assertLess(branch.index("/var/lib/vantio-lab/lsm-reassert.json"), run)
        # post must keep the re-assert record; it reads it after the reboot.
        self.assertEqual(branch[:run].count("lsm-reassert.json"), 1)


class ImageCycleWordTest(unittest.TestCase):
    """GCP must read phase2_grade.grade_image_cycle(), the body run_2c really returns.

    Provision 39859707484 graded 2C setup_invalid with anchor 0 although the
    host had run all four steps: the GCP mapper only knew deny_before/deny_after.
    """

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT / "scripts/aws/lab-guests"))
        import phase2_grade

        cls.grade = phase2_grade

    def _step(self, name: str, *, errno: int = 13, attributed: bool = True, removed: bool = True) -> dict:
        pin = name in {"baseline", "rollback"}
        archive = self.grade.PUBLIC_INSTALLER_PIN if pin else self.grade.WORKING_SEAL
        tail = self.grade.uninstall_attestation(name, {"contract": self.grade.PUBLIC_PIN_UNINSTALL if pin else "seal"})
        return {
            "archive_sha256": archive,
            "attributed": attributed,
            "file_errno": errno,
            "image_id": "sha256:" + ("a" if pin else "b") * 32,
            "name": name,
            "uninstall": {
                "bpffs_vantio": [],
                "bpftool_rc": 0,
                "contract": self.grade.PUBLIC_PIN_UNINSTALL if pin else "seal",
                "docker_containers": "",
                "docker_ps_failed": False,
                "loader_programs": [],
                "tail": tail,
                "verified_removed": removed,
            },
        }

    def _cycle(self, **broken: dict) -> dict:
        steps = [self._step(name, **broken.get(name, {})) for name in od.IMAGE_CYCLE_STEPS]
        return self.grade.grade_image_cycle(steps)

    def test_run4_shape_is_fail_not_setup_invalid(self) -> None:
        # Run 4: pin steps had no attributed deny and no pin uninstall attestation.
        body = self._cycle(
            baseline={"attributed": False, "removed": False},
            rollback={"attributed": False, "removed": False},
        )
        self.assertEqual(body["host_result"], "FAIL")
        self.assertEqual(body["reason"], "baseline_enforcement")
        self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "fail")
        kept = od._loader_capture("loader-restart", {"body": body, "rc": 1, "word": "fail"})
        self.assertEqual(kept["fail_reasons"][0], "baseline_enforcement")
        by_name = {row["name"]: row for row in kept["cases"]}
        self.assertEqual(list(by_name), list(od.IMAGE_CYCLE_STEPS))
        self.assertFalse(by_name["baseline"]["pass"])
        self.assertEqual(by_name["baseline"]["reason"], "baseline_enforcement")
        self.assertTrue(by_name["upgrade"]["pass"])
        self.assertTrue(by_name["reupgrade"]["pass"])
        allowed = od._allow_capture(kept)
        self.assertEqual(allowed["fail_reasons"], kept["fail_reasons"])
        self.assertEqual([row["name"] for row in allowed["cases"]], list(od.IMAGE_CYCLE_STEPS))

    def test_recorded_cycle_is_held(self) -> None:
        body = self._cycle()
        self.assertEqual(body["host_result"], "RECORDED", body.get("reasons"))
        self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "held")
        kept = od._loader_capture("loader-restart", {"body": body, "rc": 0, "word": "held"})
        self.assertTrue(kept["hold"])
        self.assertNotIn("fail_reasons", kept)

    def test_seal_step_enforcement_miss_is_fail(self) -> None:
        body = self._cycle(reupgrade={"errno": 0})
        self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "fail")

    def test_recorded_cycle_does_not_mark_upgrade_failed(self) -> None:
        # Run 6: RECORDED sets reason upgrade_rollback_reupgrade and no reasons
        # list. The capture read it as an upgrade_ fail and showed upgrade pass false.
        body = self._cycle()
        self.assertEqual(body["reason"], od.IMAGE_CYCLE_OK_REASON)
        self.assertNotIn("reasons", body)
        self.assertEqual(od._image_cycle_reasons(body), [])
        kept = od._allow_capture(od._loader_capture("loader-restart", {"body": body, "rc": 0, "word": "held"}))
        by_name = {row["name"]: row for row in kept["cases"]}
        self.assertEqual(list(by_name), list(od.IMAGE_CYCLE_STEPS))
        for name, row in by_name.items():
            with self.subTest(step=name):
                self.assertTrue(row["pass"])
                self.assertNotIn("reason", row)
        self.assertNotIn("fail_reasons", kept)

    def test_single_reason_fallback_is_only_for_a_fail(self) -> None:
        self.assertEqual(od._image_cycle_reasons({"reason": "upgrade_enforcement"}), ["upgrade_enforcement"])
        self.assertEqual(
            od._image_cycle_reasons({"host_result": "RECORDED", "reason": "upgrade_enforcement"}), []
        )
        # RECORDED means host_result only, as in _image_cycle_word. action is not read.
        self.assertEqual(
            od._image_cycle_reasons({"action": "RECORDED", "reason": "upgrade_enforcement"}), ["upgrade_enforcement"]
        )
        self.assertEqual(
            od._image_cycle_reasons({"host_result": "FAIL", "action": "RECORDED", "reason": "upgrade_enforcement"}),
            ["upgrade_enforcement"],
        )
        self.assertEqual(
            od._image_cycle_reasons({"host_result": "FAIL", "reason": od.IMAGE_CYCLE_OK_REASON}),
            [od.IMAGE_CYCLE_OK_REASON],
        )
        self.assertEqual(
            od._image_cycle_reasons({"reasons": [od.IMAGE_CYCLE_OK_REASON, "upgrade_uninstall"]}),
            [od.IMAGE_CYCLE_OK_REASON, "upgrade_uninstall"],
        )

    def test_a_fail_body_keeps_its_fail_reasons(self) -> None:
        cases = (
            {"host_result": "FAIL", "action": "RECORDED", "reason": "upgrade_enforcement"},
            {"host_result": "FAIL", "reason": od.IMAGE_CYCLE_OK_REASON},
        )
        for extra in cases:
            with self.subTest(body=extra):
                # A real FAIL cycle (upgrade not denied) with a single reason and no reasons list.
                body = self._cycle(upgrade={"errno": 0})
                body.pop("reasons", None)
                body.update(extra)
                self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "fail")
                kept = od._allow_capture(od._loader_capture("loader-restart", {"body": body, "rc": 1, "word": "fail"}))
                self.assertEqual(kept["fail_reasons"], [body["reason"]])
                by_name = {row["name"]: row for row in kept["cases"]}
                self.assertFalse(by_name["upgrade"]["pass"])
                self.assertEqual(by_name["upgrade"]["reason"], body["reason"])

    def test_a_real_upgrade_fail_still_marks_upgrade(self) -> None:
        body = self._cycle(upgrade={"errno": 0})
        self.assertEqual(body["host_result"], "FAIL")
        kept = od._loader_capture("loader-restart", {"body": body, "rc": 1, "word": "fail"})
        by_name = {row["name"]: row for row in kept["cases"]}
        self.assertFalse(by_name["upgrade"]["pass"])
        self.assertEqual(by_name["upgrade"]["reason"], "upgrade_enforcement")
        self.assertTrue(by_name["baseline"]["pass"])

    def test_missing_archives_stay_setup_invalid(self) -> None:
        for reason in ("public_pin_absent", "public_pin_digest", "seal_absent", "seal"):
            body = self.grade.grade_image_cycle([])
            body["reason"] = reason
            self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "setup_invalid", reason)
        self.assertEqual(od._loader_word("2c-upgrade-rollback", self.grade.grade_image_cycle([])), "setup_invalid")

    def test_legacy_deny_shape_unchanged(self) -> None:
        self.assertEqual(od._loader_word("2c-upgrade-rollback", {"deny_before": {}}), "setup_invalid")

    # #362 (open) grades pin residue as findings[] public_pin_leaves_bpf_residue
    # instead of a fail. GCP must keep that finding in the capture and the rows.
    RESIDUE = {
        "bpffs_vantio": ["/sys/fs/bpf/vantio", "/sys/fs/bpf/vantio/deny_map"],
        "bpftool_rc": 0,
        "docker_containers": "",
        "finding": "public_pin_leaves_bpf_residue",
        "loader_programs": ["vantio_file_open", "vantio_exec"],
        "step": "baseline",
    }

    def _residue_body(self) -> dict:
        """The #362 grader's body when the pin left programs and pins behind."""
        if hasattr(self.grade, "public_pin_residue"):
            steps = [self._step(name) for name in od.IMAGE_CYCLE_STEPS]
            for step in steps[0::2]:
                step["uninstall"].update(
                    {
                        "bpffs_vantio": list(self.RESIDUE["bpffs_vantio"]),
                        "loader_programs": list(self.RESIDUE["loader_programs"]),
                        "verified_removed": False,
                    }
                )
            return self.grade.grade_image_cycle(steps)
        body = self._cycle()
        body["findings"] = [dict(self.RESIDUE), dict(self.RESIDUE, step="rollback")]
        return body

    def test_362_residue_finding_reaches_capture_and_rows(self) -> None:
        body = self._residue_body()
        self.assertEqual(body["host_result"], "RECORDED", body.get("reasons"))
        self.assertEqual([item["step"] for item in body["findings"]], ["baseline", "rollback"])
        word = od._loader_word("2c-upgrade-rollback", body)
        self.assertEqual(word, "held")
        kept = od._allow_capture(od._loader_capture("loader-restart", {"body": body, "rc": 0, "word": word}))
        expected = [
            {
                "bpffs_vantio": self.RESIDUE["bpffs_vantio"],
                "bpftool_rc": 0,
                "finding": "public_pin_leaves_bpf_residue",
                "loader_programs": self.RESIDUE["loader_programs"],
                "step": step,
            }
            for step in ("baseline", "rollback")
        ]
        self.assertEqual(kept["findings"], expected)
        self.assertTrue(kept["hold"])
        rows = od.allow_record(
            {
                "loader_restart": word,
                "loader_restart_findings": od.allow_cycle_findings(body["findings"]),
            }
        )
        self.assertEqual(rows["loader_restart"], "held")
        self.assertEqual(rows["loader_restart_findings"], expected)

    def test_findings_kept_on_fail_and_filtered(self) -> None:
        body = self._cycle(reupgrade={"errno": 0})
        body["findings"] = [
            dict(self.RESIDUE),
            dict(self.RESIDUE, step="elsewhere"),
            dict(self.RESIDUE, finding="Bad Finding!"),
            dict(self.RESIDUE, finding="other_finding"),
            dict(
                self.RESIDUE,
                step="rollback",
                bpffs_vantio=["/sys/fs/bpf/vantio/../../etc", "/etc/passwd", "/sys/fs/bpf/vantio/ok"],
                loader_programs=["ok_prog", "bad prog;rm"],
                docker_containers="abc",
            ),
            "not-a-dict",
        ]
        self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "fail")
        kept = od._allow_capture(od._loader_capture("loader-restart", {"body": body, "rc": 1, "word": "fail"}))
        self.assertIn("reupgrade_enforcement", kept["fail_reasons"])
        self.assertEqual([item["step"] for item in kept["findings"]], ["baseline", "rollback"])
        rollback = kept["findings"][1]
        self.assertEqual(rollback["bpffs_vantio"], ["/sys/fs/bpf/vantio/ok"])
        self.assertEqual(rollback["loader_programs"], ["ok_prog"])
        self.assertNotIn("docker_containers", rollback)

    def _write_rows(self, restart_body: dict) -> dict:
        """Drive od.run_batteries with every cloud call stubbed and return the written gcp-lab-rows.json."""
        repeat = {"b1_pass": True, "deny_hold": True, "deny_pid": 41, "desc_deny_pid": 42, "lineage_anchor": 7}

        def loader_case(_project: str, _name: str, _seal: str, mode: str) -> dict:
            if mode == "2c-upgrade-rollback":
                return {"body": restart_body, "rc": 0, "word": "held"}
            return {"body": {}, "rc": 0, "word": "held"}

        ok = subprocess.CompletedProcess([], 0, stdout="UNINSTALL_VERIFIED\ndeny_attr_post_kill pid 9\n", stderr="")
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            stubs = {
                "_enabled": mock.DEFAULT,
                "require_lab_project": mock.Mock(return_value="vantio-lab-test"),
                "_gate_ok": mock.DEFAULT,
                "batteries_requested": mock.Mock(return_value=True),
                "instance_name": mock.Mock(return_value="vantio-gcp-lab-1"),
                "refuse_batteries": mock.Mock(return_value="a" * 64),
                "_evidence_dir": mock.Mock(return_value=evidence),
                "_stage_payload": mock.Mock(return_value=[]),
                "_wait_until_running": mock.DEFAULT,
                "_ssh": mock.Mock(return_value=ok),
                "_scp_to": mock.DEFAULT,
                "_prepare_lab_lsm": mock.Mock(return_value={}),
                "_wait_live_boot": mock.Mock(return_value="boot-2"),
                "_run_one_battery": mock.Mock(return_value=repeat),
                "full_set_passes": mock.Mock(return_value=True),
                "_loader_case": mock.Mock(side_effect=loader_case),
                # 2E-2G are test_gcp_phase_batteries.py. Stub them out here.
                "run_phase_batteries": mock.Mock(return_value=[]),
                "phases_pass": mock.Mock(return_value=True),
                "drop_guest_copies": mock.DEFAULT,
                "remove_os_login_key": mock.DEFAULT,
            }
            with mock.patch.multiple(od, **stubs), contextlib.redirect_stdout(io.StringIO()):
                rc = od.run_batteries({"RUNNER_TEMP": tmp})
            self.assertEqual(rc, 0)
            return json.loads((evidence / "gcp-lab-rows.json").read_text(encoding="utf-8"))

    def test_rows_writer_carries_findings(self) -> None:
        body = self._residue_body()
        rows = self._write_rows(body)
        self.assertEqual(rows["loader_restart"], "held")
        self.assertEqual(rows["loader_restart_findings"], od.allow_cycle_findings(body["findings"]))
        self.assertEqual([item["step"] for item in rows["loader_restart_findings"]], ["baseline", "rollback"])
        self.assertEqual(rows["loader_restart_findings"][0]["finding"], "public_pin_leaves_bpf_residue")
        self.assertEqual(rows["loader_restart_findings"][0]["loader_programs"], self.RESIDUE["loader_programs"])

    def test_rows_writer_without_findings(self) -> None:
        # Current behaviour: no host findings -> the key is written as [].
        for findings in (None, "junk"):
            body = self._cycle()
            body["findings"] = findings
            self.assertEqual(self._write_rows(body)["loader_restart_findings"], [])
        body = self._cycle()
        body.pop("findings", None)
        self.assertEqual(self._write_rows(body)["loader_restart_findings"], [])

    def test_recorded_without_upgrade_pass_is_fail(self) -> None:
        body = self._cycle()
        body["upgrade_pass"] = False
        self.assertEqual(body["host_result"], "RECORDED")
        self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "fail")

    def test_upgrade_pass_with_host_fail_is_fail(self) -> None:
        body = self._cycle()
        body["host_result"] = "FAIL"
        body["reason"] = "baseline_enforcement"
        self.assertIs(body["upgrade_pass"], True)
        self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "fail")

    def test_raw_findings_through_allow_record(self) -> None:
        raw = [
            None,
            "public_pin_leaves_bpf_residue",
            ["baseline"],
            {"finding": None, "step": "baseline"},
            {"finding": "public_pin_leaves_bpf_residue"},
            {"finding": "public_pin_leaves_bpf_residue", "step": None},
            {"finding": "public_pin_leaves_bpf_residue", "step": "BASELINE"},
            {"finding": "public_pin_leaves_bpf_residue", "step": "../baseline"},
            {"finding": "unknown_finding", "step": "baseline"},
            {"finding": "public_pin_leaves_bpf_residue\n", "step": "baseline"},
            {
                "finding": "public_pin_leaves_bpf_residue",
                "step": "rollback",
                "loader_programs": [None, 7, "", "x" * 65, "ok_prog", "a b", "../x"],
                "bpffs_vantio": [
                    None,
                    "/sys/fs/bpf/vantio",
                    "/sys/fs/bpf/vantio/../../../etc/shadow",
                    "/sys/fs/bpf/other",
                    "/sys/fs/bpf/vantio/m ap",
                    "relative/vantio",
                    "/sys/fs/bpf/vantio/" + "p" * 200,
                ],
                "bpftool_rc": True,
                "docker_containers": "deadbeef",
                "hostname": "vm-1",
                "token": "ghp_x",
            },
            {
                "finding": "public_pin_leaves_bpf_residue",
                "step": "baseline",
                "loader_programs": "vantio_exec",
                "bpffs_vantio": None,
                "bpftool_rc": 256,
            },
        ]
        rows = od.allow_record({"loader_restart_findings": raw})["loader_restart_findings"]
        self.assertEqual(
            rows,
            [
                {
                    "bpffs_vantio": ["/sys/fs/bpf/vantio"],
                    "finding": "public_pin_leaves_bpf_residue",
                    "loader_programs": ["ok_prog"],
                    "step": "rollback",
                },
                {"finding": "public_pin_leaves_bpf_residue", "step": "baseline"},
            ],
        )
        self.assertEqual(od.allow_record({"loader_restart_findings": None}), {})
        self.assertEqual(od.allow_record({"loader_restart_findings": "x"}), {})
        self.assertEqual(od.allow_record({"loader_restart_findings": []})["loader_restart_findings"], [])

    def test_finding_caps_and_rc_range(self) -> None:
        many = {
            "finding": "public_pin_leaves_bpf_residue",
            "step": "baseline",
            "loader_programs": [f"p{i}" for i in range(40)],
            "bpffs_vantio": [f"/sys/fs/bpf/vantio/m{i}" for i in range(40)],
            "bpftool_rc": 255,
        }
        rows = od.allow_cycle_findings([many] * 12)
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["loader_programs"], [f"p{i}" for i in range(32)])
        self.assertEqual(rows[0]["bpffs_vantio"], [f"/sys/fs/bpf/vantio/m{i}" for i in range(32)])
        self.assertEqual(rows[0]["bpftool_rc"], 255)
        for rc, kept in ((0, True), (255, True), (-1, False), (256, False), (False, False), ("0", False), (1.0, False)):
            row = od.allow_cycle_findings([dict(many, bpftool_rc=rc)])[0]
            self.assertEqual("bpftool_rc" in row, kept, rc)

    def test_finding_names_pinned_to_grader(self) -> None:
        # The full set: every named 2C finding the grader can emit, and nothing else.
        self.assertEqual(od.KNOWN_CYCLE_FINDINGS, self.grade.CYCLE_FINDINGS)
        self.assertEqual(
            self.grade.CYCLE_FINDINGS,
            frozenset({self.grade.PUBLIC_PIN_RESIDUE_FINDING, self.grade.PUBLIC_PIN_UNATTRIBUTED_FINDING}),
        )
        self.assertEqual(od.allow_cycle_findings([{"finding": "made_up", "step": "baseline"}]), [])

    def test_public_pin_unattributed_finding_reaches_capture_and_rows(self) -> None:
        steps = [self._step(name) for name in od.IMAGE_CYCLE_STEPS]
        for step in steps:
            step["setup_error"] = ""
        for step in steps[0::2]:
            step["attributed"] = False
        body = self.grade.grade_image_cycle(steps)
        self.assertEqual(body["host_result"], "RECORDED", body.get("reasons"))
        names = {item["finding"] for item in body["findings"]}
        self.assertLessEqual(names, self.grade.CYCLE_FINDINGS)
        word = od._loader_word("2c-upgrade-rollback", body)
        self.assertEqual(word, "held")
        kept = od._allow_capture(od._loader_capture("loader-restart", {"body": body, "rc": 0, "word": word}))
        expected = [
            {"file_errno": 13, "finding": "public_pin_unattributed_deny", "step": step}
            for step in ("baseline", "rollback")
        ]
        self.assertEqual(kept["findings"], expected)
        self.assertEqual(od.allow_cycle_findings([dict(expected[0])]), [expected[0]])

    def test_unattributed_finding_keeps_only_errno_13_on_a_pin_step(self) -> None:
        good = {"file_errno": 13, "finding": "public_pin_unattributed_deny", "step": "baseline"}
        self.assertEqual(od.allow_cycle_findings([dict(good, step="rollback")]), [dict(good, step="rollback")])
        for errno in (0, 1, 110, -1, True, "13", 13.0, None, 4096):
            with self.subTest(errno=errno):
                self.assertEqual(od.allow_cycle_findings([dict(good, file_errno=errno)]), [])
        missing = dict(good)
        del missing["file_errno"]
        self.assertEqual(od.allow_cycle_findings([missing]), [])
        for step in ("upgrade", "reupgrade"):
            self.assertEqual(od.allow_cycle_findings([dict(good, step=step)]), [], step)
        # The residue finding never carries an errno.
        residue = od.allow_cycle_findings([dict(self.RESIDUE, file_errno=13)])[0]
        self.assertNotIn("file_errno", residue)

    def test_unattributed_seal_step_still_fails_through_gcp(self) -> None:
        steps = [self._step(name) for name in od.IMAGE_CYCLE_STEPS]
        for step in steps:
            step["setup_error"] = ""
        steps[1]["attributed"] = False
        body = self.grade.grade_image_cycle(steps)
        self.assertEqual(body["host_result"], "FAIL")
        self.assertIn("upgrade_enforcement", body["reasons"])
        self.assertEqual(od._loader_word("2c-upgrade-rollback", body), "fail")


class MainBlockLastTest(unittest.TestCase):
    """CI runs these files as scripts. Anything after unittest.main() never runs (#363 council)."""

    def test_no_definitions_after_main_block(self) -> None:
        import ast

        late = []
        for path in sorted([*(ROOT / "scripts/aws").glob("test_*.py"), *(ROOT / "scripts/gcp").glob("test_*.py")]):
            body = ast.parse(path.read_text(encoding="utf-8")).body
            mains = [
                i
                for i, node in enumerate(body)
                if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'"
            ]
            if mains:
                # Anchor on the FIRST main block: unittest.main() exits there, so
                # anything after it, even another main block, never runs.
                late += [f"{path.name}:{node.lineno}" for node in body[mains[0] + 1 :]]
        self.assertEqual(late, [])


if __name__ == "__main__":
    unittest.main()
