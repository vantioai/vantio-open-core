#!/usr/bin/env python3
"""Guards for offline GCP delivery. These tests do not call GCP."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
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
        for project in ("vantio-lab-navera", "other-project", "vantio-lab-other"):
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
        self.assertIn(od.POLICY_ALLOW_SEAL, bundle)
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
        self.assertNotIn("navera", joined.lower())
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
        self.assertNotIn("navera", brain_joined.lower())
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
        held = {
            "enrolled_after": sample(6895),
            "unenrolled_after": {"file_errno": 0, "path": od.CEILING_PATH, "pid": 6896},
            "while_loader_up": sample(6863),
        }
        self.assertEqual(od._loader_word("2d-crash-recovery", held), "held")
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
        self.assertLess(text.index("--download-only"), text.index("apt-get download ca-certificates"))
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
        self.assertNotIn("navera", text.lower())
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


if __name__ == "__main__":
    unittest.main()
