#!/usr/bin/env python3
"""Guards for offline GCP delivery. These tests do not call GCP."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from decimal import Decimal
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
        self.assertIn("--image-family=debian-12", argv)
        self.assertIn("--image-project=debian-cloud", argv)
        self.assertIn("--shielded-secure-boot", argv)
        self.assertNotIn("--address=", joined)
        self.assertNotIn("ubuntu", joined)
        self.assertNotIn("navera", joined.lower())
        startup = od.offline_startup(120)
        self.assertNotIn("apt-get", startup)
        self.assertIn("shutdown -h +120", startup)

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
            f"bash /tmp/vantio-lab/enterprise-rows.sh {od.POLICY_ALLOW_SEAL} descendant-b1 post",
        )
        self.assertEqual(
            od.guest_command("ab" * 32, "plumb"),
            f"bash /tmp/vantio-lab/enterprise-rows.sh {'ab' * 32} plumb",
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

    def test_full_battery_is_two_complete_repeats(self) -> None:
        self.assertEqual(od.battery_schedule(), ["enterprise", "descendant-b1", "enterprise", "descendant-b1"])
        self.assertEqual(od.FULL_BATTERY, ("kernel", "seal", "enterprise", "descendant-b1"))
        repeats = [self._passing_repeat(1), self._passing_repeat(2)]
        self.assertTrue(od.full_set_passes(repeats))
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
        self.assertIn("INTERNAL_CLEAN_HOST_PROOF", text)
        self.assertLess(text.index('mode=${2:-plumb}'), text.index("apt-get install"))

    def test_deb_fetch_uses_the_pinned_snapshot(self) -> None:
        text = (ROOT / "scripts/gcp/fetch_offline_debs.sh").read_text(encoding="utf-8")
        self.assertIn(od.DEBIAN_IMAGE, text)
        for line in od.SNAPSHOT_LINES:
            self.assertIn(line, text)
        self.assertIn("--download-only", text)
        self.assertIn("--no-install-recommends", text)
        self.assertIn("docker.io", text)
        self.assertIn("python3-cryptography", text)

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
        self.assertIn("teardown-if-present", text)
        self.assertIn("vantio-gce-slot", text)
        self.assertIn("EXPECTED_SEAL: ${{ inputs.seal }}", text)
        self.assertIn("if: ${{ !inputs.run_batteries }}", text)
        self.assertNotIn("gcp-lab-one-vm", text)
        self.assertNotIn("default: f882dd81", text)
        self.assertNotIn("910881070503", text)
        self.assertNotIn("uploadType=media", (ROOT / "scripts/gcp/offline_deliver.py").read_text(encoding="utf-8"))
        self.assertIn('test "$GCP_LAB_SERVICE_ACCOUNT" = "vantio-lab-gha@vantio-lab-oct08.iam.gserviceaccount.com"', text)
        self.assertIn("vantio-lab-handoff@vantio-lab-oct08.iam.gserviceaccount.com", text)
        self.assertNotIn("projects/910881070503", text)
        for name in (
            "gcp-lab-teardown.yml",
            "gcp-lab-sweeper.yml",
            "gcp-lab-collect.yml",
            "gcp-lab-verify-removed.yml",
        ):
            other = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("vantio-gce-slot", other)
            self.assertNotIn("gcp-lab-one-vm", other)
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
        for block in blocks:
            self.assertIn("gcp-lab-evidence", block)
            self.assertNotIn("seal.oci.tar", block)
            self.assertNotIn("contract.tar", block)
            self.assertNotIn(".deb", block)
        for key in ("  fetch:", "  deliver:", "  teardown:"):
            self.assertIn(key, text)


if __name__ == "__main__":
    unittest.main()
