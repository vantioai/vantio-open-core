#!/usr/bin/env python3
"""Fixture proof for the T1 stranger-host package. No cloud calls."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "gap" / "t1-stranger-host"
sys.path.insert(0, str(SCRIPT))

import bundle  # noqa: E402
import capture  # noqa: E402
import constants  # noqa: E402
import facts  # noqa: E402
import grade  # noqa: E402
import preflight  # noqa: E402
from errors import PackageError  # noqa: E402

LSM = "lockdown,capability,landlock,yama,apparmor,bpf,ima,evm"
CMDLINE = "BOOT_IMAGE=/vmlinuz ro console=ttyS0 lsm=lockdown,capability,landlock,yama,apparmor,ima,evm,bpf panic=-1"
LSM_WORD = "lsm=lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
LOCKDOWN = "none [integrity] confidentiality"
BOOT1 = "11111111-1111-1111-1111-111111111111"
BOOT2 = "22222222-2222-2222-2222-222222222222"
IMAGE = "ubuntu-2404-noble-amd64-v20261009"
SERIAL = f"Linux version 7.0.0-1014-gcp\nKernel command line: {CMDLINE}\n"
OPERATOR = str(SCRIPT / "stranger_host.py")


def _pem(private: Ed25519PrivateKey) -> bytes:
    return private.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())


def _trust(private: Ed25519PrivateKey, **overrides: object) -> bytes:
    public = base64.b64encode(private.public_key().public_bytes_raw()).decode("ascii")
    key = {
        "algorithm": "ed25519",
        "environment": "NON-PRODUCTION",
        "key_id": constants.TRUST_KEY_ID,
        "label": "TEST",
        "not_a_production_root": True,
        "public_key_b64": public,
    }
    key.update(overrides)
    return json.dumps({"keys": [key]}).encode("utf-8")


def _cases() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in constants.DENY_CASES:
        rows.append({"expect_deny": True, "file_errno": 13, "name": name, "net_errno": 1, "pass": True})
    for name in constants.ALLOW_CASES:
        rows.append({"expect_deny": False, "file_errno": 0, "name": name, "net_errno": 0, "pass": True})
    return rows


def _measure(boot: str) -> dict[str, object]:
    return {"boot_id": boot, "cases": _cases(), "descendant_pass": True, "failed_cases": []}


def _host() -> dict[str, object]:
    return {
        "boot_id": BOOT1,
        "bpffs": True,
        "btf_bytes": 128,
        "cgroup_fstype": "cgroup2fs",
        "cmdline": CMDLINE,
        "enabled_lsm": LSM,
        "image": {"exact": IMAGE, "source": "operator-attestation", "supplemental": {"os_release": "Ubuntu 24.04"}},
        "kernel_btf": True,
        "kernel_cgroup_v2": True,
        "lockdown_mode": "integrity",
        "lockdown_raw": LOCKDOWN,
        "uname_release": "7.0.0-1014-gcp",
        "uname_version": "#14~24.04.1-Ubuntu",
    }


def _enterprise(**updates: object) -> dict[str, object]:
    body: dict[str, object] = {
        "deny_attr_post_kill": True,
        "fail_reasons": [],
        "freeze": {"widen_reason": "FROZEN"},
        "grant_loader": {"audit": True, "path_observe": True, "rc": 0},
        "grant_probe": {"nobody_errno": 0},
        "loader_kill": "held",
        "loader_restart": "held",
        "path": constants.CEILING_PATH,
        "revoke": {
            "block_event": {"ActionTaken": "DENIED", "Pid": 10, "lineage_anchor": 20},
            "probe": {"nobody_errno": 13, "path": constants.CEILING_PATH, "uid": 65534},
        },
        "uid": 65534,
        "unchanged": {
            "conflict_reason": "VERSION_CONFLICT",
            "generation": 3,
            "generation_before": 3,
            "probe": "open_ok",
        },
        "unreachable": {"reason": "ENTERPRISE_UNREACHABLE"},
    }
    body.update(updates)
    return body


def _boot() -> dict[str, object]:
    encoded = SERIAL.encode("utf-8")
    return {
        "boot_id": BOOT2,
        "cmdline": CMDLINE,
        "enabled_lsm": LSM,
        "serial_boot_id": BOOT2,
        "serial_bytes": len(encoded),
        "serial_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _seal(digest: str | None = None) -> dict[str, object]:
    chosen = digest or constants.COMPARISON_SEAL
    return {
        "digest": chosen,
        "file_sha256": chosen,
        "present": True,
        "sha256sum": "seal.oci.tar: OK",
    }


def _uninstall(**updates: object) -> dict[str, object]:
    body: dict[str, object] = {
        "bpftool_vantio_lines": [],
        "bpffs_vantio_names": [],
        "fail_reasons": [],
        "uninstall_verified_line": True,
    }
    body.update(updates)
    return body


def _teardown(**updates: object) -> dict[str, object]:
    body: dict[str, object] = {
        "actor": "outside_operator",
        "apt_sources_restored": False,
        "offline_conf_removed": False,
        "project_touched_by_vantio": False,
        "swapfile_removed": False,
        "vantio_ran_teardown": False,
        "vm_deleted": True,
    }
    body.update(updates)
    return body


def _grade(**overrides: object) -> dict[str, object]:
    parts = {
        "boot": _boot(),
        "descendant_post": {"post": _measure(BOOT2), "pre": _measure(BOOT1), "reboot_observed": True},
        "descendant_pre": {"pre": _measure(BOOT1)},
        "enterprise": _enterprise(),
        "host": _host(),
        "seal": _seal(),
        "serial_text": SERIAL,
        "teardown": _teardown(),
        "uninstall": _uninstall(),
    }
    parts.update(overrides)
    return grade.grade_evidence(
        host=parts["host"],
        seal=parts["seal"],
        enterprise=parts["enterprise"],
        descendant_pre=parts["descendant_pre"],
        boot=parts["boot"],
        descendant_post=parts["descendant_post"],
        uninstall=parts["uninstall"],
        teardown=parts["teardown"],
        serial_text=parts["serial_text"],  # type: ignore[arg-type]
    )


def _step(result: dict[str, object], number: int) -> dict[str, object]:
    steps = result["steps"]
    assert isinstance(steps, list)
    found = steps[number - 1]
    assert isinstance(found, dict)
    return found


def _write_root(root: Path, *, lsm: str = LSM, btf: bytes = b"btf", lockdown: str = LOCKDOWN, mounts: str = "bpf /sys/fs/bpf bpf rw 0 0\n") -> None:
    files = {
        "sys/kernel/security/lsm": lsm + "\n",
        "sys/kernel/security/lockdown": lockdown + "\n",
        "proc/mounts": mounts,
        "proc/cmdline": CMDLINE + "\n",
        "proc/sys/kernel/random/boot_id": BOOT1 + "\n",
        "etc/os-release": "PRETTY_NAME=\"Ubuntu 24.04 LTS\"\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    btf_path = root / "sys/kernel/btf/vmlinux"
    btf_path.parent.mkdir(parents=True, exist_ok=True)
    btf_path.write_bytes(btf)


def _run_operator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, OPERATOR, *args], capture_output=True, text=True, check=False)


class FactsTests(unittest.TestCase):
    def test_bpf_token_is_exact(self) -> None:
        self.assertTrue(facts.bpf_in_lsm_list(LSM))
        self.assertFalse(facts.bpf_in_lsm_list("lockdown,capability,bpfx"))
        self.assertTrue(facts.bpf_in_cmdline(CMDLINE))
        self.assertFalse(facts.bpf_in_cmdline("lsm=bpfx panic=-1"))
        self.assertEqual(facts.lsm_word(CMDLINE), LSM_WORD)

    def test_lockdown_modes(self) -> None:
        self.assertEqual(facts.parse_lockdown(LOCKDOWN), "integrity")
        self.assertEqual(facts.parse_lockdown("[none] integrity confidentiality"), "none")
        self.assertEqual(facts.parse_lockdown("none integrity [confidentiality]"), "confidentiality")
        with self.assertRaises(ValueError):
            facts.parse_lockdown("none integrity")
        with self.assertRaises(ValueError):
            facts.parse_lockdown("[none] [integrity] confidentiality")

    def test_exact_image_rejects_the_family(self) -> None:
        self.assertTrue(facts.image_is_exact(IMAGE, source="operator-attestation"))
        self.assertTrue(facts.image_is_exact("ami-0abc1234def56789", source="metadata"))
        self.assertFalse(facts.image_is_exact(constants.IMAGE_FAMILY, source="operator-attestation"))
        self.assertFalse(facts.image_is_exact(constants.IMAGE_FAMILY_BARE, source="operator-attestation"))
        self.assertFalse(facts.image_is_exact("Ubuntu 24.04", source="operator-attestation"))
        self.assertTrue(facts.image_is_exact("dedicated-test-build", source="operator-attestation"))
        self.assertFalse(facts.image_is_exact("dedicated-test-build", source="metadata"))


class PreflightTests(unittest.TestCase):
    def test_stops_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_root(root, lsm="lockdown,capability,apparmor", btf=b"")
            with self.assertRaises(preflight.PreflightFailure) as caught:
                preflight.collect_host(root, attestation=IMAGE, cgroup_name="cgroup2fs")
            self.assertEqual(caught.exception.reason, "bpf_lsm_inactive")

            _write_root(root, btf=b"")
            with self.assertRaises(preflight.PreflightFailure) as caught:
                preflight.collect_host(root, attestation=IMAGE, cgroup_name="cgroup2fs")
            self.assertEqual(caught.exception.reason, "btf_missing")

            _write_root(root)
            with self.assertRaises(preflight.PreflightFailure) as caught:
                preflight.collect_host(root, attestation=IMAGE, cgroup_name="tmpfs")
            self.assertEqual(caught.exception.reason, "cgroup_v2_missing")

            _write_root(root, lockdown="none integrity")
            with self.assertRaises(preflight.PreflightFailure) as caught:
                preflight.collect_host(root, attestation=IMAGE, cgroup_name="cgroup2fs")
            self.assertEqual(caught.exception.reason, "lockdown_unreadable")

            _write_root(root, lockdown="none integrity [confidentiality]")
            with self.assertRaises(preflight.PreflightFailure) as caught:
                preflight.collect_host(root, attestation=IMAGE, cgroup_name="cgroup2fs")
            self.assertEqual(caught.exception.reason, "lockdown_confidentiality")

            _write_root(root, mounts="ext4 / ext4 rw 0 0\n")
            with self.assertRaises(preflight.PreflightFailure) as caught:
                preflight.collect_host(root, attestation=IMAGE, cgroup_name="cgroup2fs")
            self.assertEqual(caught.exception.reason, "bpffs_missing")

            _write_root(root)
            with self.assertRaises(preflight.PreflightFailure) as caught:
                preflight.collect_host(root, attestation=constants.IMAGE_FAMILY, cgroup_name="cgroup2fs")
            self.assertEqual(caught.exception.reason, "image_exact_missing")

    def test_pass_records_lockdown_and_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_root(root)
            host = preflight.collect_host(root, attestation=IMAGE, cgroup_name="cgroup2fs")
        self.assertEqual(host["lockdown_mode"], "integrity")
        self.assertEqual(host["lockdown_raw"], LOCKDOWN)
        image = host["image"]
        assert isinstance(image, dict)
        self.assertEqual(image["exact"], IMAGE)
        self.assertEqual(image["source"], "operator-attestation")
        supplemental = image["supplemental"]
        assert isinstance(supplemental, dict)
        self.assertIn("Ubuntu 24.04", supplemental["os_release"])
        self.assertEqual(host["boot_id"], BOOT1)
        graded = grade.grade_preflight(host)
        self.assertEqual(graded["result"], "PASS")

    def test_metadata_image_uses_the_last_segment(self) -> None:
        chosen = preflight.choose_image(
            attestation="",
            source="operator-attestation",
            metadata="projects/ubuntu-os-cloud/global/images/" + IMAGE,
            supplemental={},
        )
        self.assertEqual(chosen["exact"], IMAGE)
        self.assertEqual(chosen["source"], "metadata")

    def test_shell_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_root(root)
            ok = subprocess.run(
                ["bash", str(SCRIPT / "preflight.sh"), "--root", str(root), "--image-name", IMAGE, "--cgroup-fstype", "cgroup2fs"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertIn("PREFLIGHT_OK", ok.stdout)
            _write_root(root, lsm="lockdown,apparmor")
            bad = subprocess.run(
                ["bash", str(SCRIPT / "preflight.sh"), "--root", str(root), "--image-name", IMAGE, "--cgroup-fstype", "cgroup2fs"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bad.returncode, 1)
            self.assertIn("PREFLIGHT_FAIL bpf_lsm_inactive", bad.stdout)


class GradeTests(unittest.TestCase):
    def test_all_nine_steps_pass(self) -> None:
        result = _grade()
        self.assertEqual(result["result"], "PASS")
        self.assertFalse(result["host_proof"])
        self.assertEqual(result["label"], "Roadmap")
        self.assertEqual(result["tier"], "UNSET")
        for number in range(1, 10):
            self.assertEqual(_step(result, number)["result"], "PASS", _step(result, number))
        self.assertEqual(_step(result, 2)["comparison_seal"], True)
        self.assertEqual(_step(result, 2)["working_seal"], False)
        self.assertEqual(_step(result, 8)["removal"], "VERIFIED_REMOVED")

    def test_working_seal_flag_and_refused_digests(self) -> None:
        working = _grade(seal=_seal(constants.WORKING_SEAL))
        self.assertEqual(_step(working, 2)["working_seal"], True)
        self.assertEqual(_step(working, 2)["result"], "PASS")
        for digest, reason in (
            (constants.PUBLIC_PIN, "seal_is_public_pin"),
            (constants.PLUMBING_ONLY_SEAL, "seal_is_plumbing_only"),
            (constants.TRACKING_SEAL, "seal_is_tracking"),
        ):
            refused = _grade(seal=_seal(digest))
            self.assertEqual(_step(refused, 2)["reasons"], [reason])
            self.assertNotEqual(refused["result"], "PASS")

    def test_programs_not_removed_is_a_harness_note(self) -> None:
        noted = _grade(enterprise=_enterprise(fail_reasons=["programs_not_removed"]))
        self.assertEqual(_step(noted, 3)["result"], "PASS")
        self.assertEqual(_step(noted, 3)["notes"], ["harness_fault_candidate"])
        removed = _grade(uninstall=_uninstall(fail_reasons=["programs_not_removed"]))
        self.assertEqual(_step(removed, 8)["removal"], "VERIFIED_REMOVED")
        self.assertEqual(_step(removed, 8)["notes"], ["harness_fault_candidate"])
        residual = _grade(uninstall=_uninstall(fail_reasons=["programs_not_removed"], bpffs_vantio_names=["vantio_persist"]))
        self.assertEqual(_step(residual, 8)["removal"], "NOT_REMOVED")
        self.assertIn("bpffs_vantio_present", _step(residual, 8)["reasons"])

    def test_missing_uninstall_lists_fail_closed(self) -> None:
        missing = _grade(uninstall={"uninstall_verified_line": True})
        reasons = _step(missing, 8)["reasons"]
        assert isinstance(reasons, list)
        self.assertIn("bpftool_missing", reasons)
        self.assertIn("bpffs_pins_missing", reasons)
        self.assertEqual(_step(missing, 8)["removal"], "NOT_REMOVED")

    def test_stale_boot_and_serial_binding(self) -> None:
        stale = _grade(descendant_post={"post": _measure(BOOT1), "pre": _measure(BOOT1), "reboot_observed": True})
        reasons = _step(stale, 7)["reasons"]
        assert isinstance(reasons, list)
        self.assertIn("stale_rows", reasons)
        self.assertIn("reboot_not_observed", reasons)
        same = _grade(boot={**_boot(), "boot_id": BOOT1, "serial_boot_id": BOOT1})
        self.assertIn("boot_id_unchanged", _step(same, 6)["reasons"])
        swapped = SERIAL.replace(LSM_WORD, "lsm=lockdown,capability")
        unbound = _grade(serial_text=swapped, boot={**_boot(), "serial_sha256": hashlib.sha256(swapped.encode()).hexdigest()})
        self.assertIn("serial_lsm_missing", _step(unbound, 6)["reasons"])
        self.assertIn("cmdline_bpf_missing", _step(_grade(boot={**_boot(), "cmdline": "panic=-1"}), 6)["reasons"])

    def test_descendant_skip_and_errno(self) -> None:
        measure = _measure(BOOT1)
        cases = measure["cases"]
        assert isinstance(cases, list)
        first = dict(cases[0])
        first["skipped"] = True
        cases[0] = first
        skipped = _grade(descendant_pre={"pre": measure})
        self.assertIn("case_skipped", _step(skipped, 5)["reasons"])
        first["skipped"] = False
        first["file_errno"] = True
        cases[0] = first
        boolean = _grade(descendant_pre={"pre": measure})
        self.assertIn("file_errno", _step(boolean, 5)["reasons"])
        first["file_errno"] = 13
        first["net_errno"] = 0
        cases[0] = first
        quiet_net = _grade(descendant_pre={"pre": measure})
        self.assertIn("net_errno", _step(quiet_net, 5)["reasons"])

    def test_loader_object_and_teardown(self) -> None:
        nested = _enterprise()
        for key in ("loader_kill", "loader_restart", "deny_attr_post_kill"):
            del nested[key]
        nested["loader"] = {"deny_attr_post_kill": True, "loader_kill": "held", "loader_restart": "held"}
        self.assertEqual(_step(_grade(enterprise=nested), 4)["result"], "PASS")
        restored = _teardown(vm_deleted=False, apt_sources_restored=True, offline_conf_removed=True, swapfile_removed=True)
        self.assertEqual(_step(_grade(teardown=restored), 9)["result"], "PASS")
        incomplete = _teardown(vm_deleted=False)
        self.assertIn("teardown_incomplete", _step(_grade(teardown=incomplete), 9)["reasons"])
        owned = _teardown(vantio_ran_teardown=True)
        self.assertIn("teardown_ran_by_vantio", _step(_grade(teardown=owned), 9)["reasons"])


class BundleTests(unittest.TestCase):
    def _material(self, directory: Path) -> tuple[Path, Path, Ed25519PrivateKey]:
        private = Ed25519PrivateKey.generate()
        key_path = directory / "operator-key.pem"
        trust_path = directory / "trust.json"
        key_path.write_bytes(_pem(private))
        trust_path.write_bytes(_trust(private))
        return key_path, trust_path, private

    def _write_inputs(self, directory: Path) -> dict[str, str]:
        directory.mkdir(parents=True, exist_ok=True)
        seal = directory / "seal.oci.tar"
        seal.write_bytes(b"sealed-bytes")
        digest = hashlib.sha256(b"sealed-bytes").hexdigest()
        names = {
            "host": _host(),
            "enterprise": _enterprise(),
            "pre": {"pre": _measure(BOOT1)},
            "boot": {**_boot(), "serial_log": SERIAL},
            "post": {"post": _measure(BOOT2), "pre": _measure(BOOT1), "reboot_observed": True},
            "uninstall": _uninstall(),
            "teardown": _teardown(),
        }
        paths: dict[str, str] = {}
        for name, body in names.items():
            path = directory / f"{name}.json"
            path.write_text(json.dumps(body), encoding="utf-8")
            paths[name] = str(path)
        paths["seal"] = str(seal)
        paths["digest"] = digest
        paths["serial"] = str(directory / "serial.txt")
        (directory / "serial.txt").write_text(SERIAL, encoding="utf-8")
        return paths

    def test_fixture_signature_is_not_a_host_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = self._write_inputs(root / "in")
            key_path, trust_path, _private = self._material(root)
            out = root / "bundle"
            assembled = _run_operator(
                "assemble",
                "--out",
                str(out),
                "--claim",
                constants.CLAIM_FIXTURE,
                "--created-utc",
                "2026-10-16T16:00:00Z",
                "--host-record",
                inputs["host"],
                "--enterprise",
                inputs["enterprise"],
                "--descendant-pre",
                inputs["pre"],
                "--boot",
                inputs["boot"],
                "--serial",
                inputs["serial"],
                "--descendant-post",
                inputs["post"],
                "--uninstall",
                inputs["uninstall"],
                "--teardown",
                inputs["teardown"],
                "--seal-file",
                inputs["seal"],
                "--seal-digest",
                inputs["digest"],
            )
            self.assertEqual(assembled.returncode, 0, assembled.stderr)
            signed = _run_operator(
                "sign",
                "--bundle",
                str(out),
                "--key",
                str(key_path),
                "--trust",
                str(trust_path),
                "--claim",
                constants.CLAIM_FIXTURE,
            )
            self.assertEqual(signed.returncode, 0, signed.stderr)
            verified = _run_operator("verify", "--bundle", str(out))
            self.assertEqual(verified.returncode, 0, verified.stderr)
            body = json.loads(verified.stdout)
            self.assertFalse(body["host_proof"])
            self.assertEqual(body["claim_cap"], constants.CLAIM_FIXTURE)
            self.assertNotIn(b"PRIVATE KEY", (out / "SIGNATURE.json").read_bytes())

    def test_awaiting_requires_the_pinned_trust_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = self._write_inputs(root / "in")
            key_path, trust_path, _private = self._material(root)
            out = root / "bundle"
            self.assertEqual(
                _run_operator(
                    "assemble",
                    "--out",
                    str(out),
                    "--claim",
                    constants.CLAIM_FIXTURE,
                    "--created-utc",
                    "2026-10-16T16:00:00Z",
                    "--host-record",
                    inputs["host"],
                    "--enterprise",
                    inputs["enterprise"],
                    "--descendant-pre",
                    inputs["pre"],
                    "--boot",
                    inputs["boot"],
                    "--serial",
                    inputs["serial"],
                    "--descendant-post",
                    inputs["post"],
                    "--uninstall",
                    inputs["uninstall"],
                    "--teardown",
                    inputs["teardown"],
                    "--seal-file",
                    inputs["seal"],
                    "--seal-digest",
                    inputs["digest"],
                ).returncode,
                0,
            )
            with self.assertRaises(PackageError) as caught:
                bundle.sign_bundle(out, key_path, trust_path, claim=constants.CLAIM_AWAITING)
            self.assertEqual(caught.exception.reason, "trust_hash")
            original = bundle.TRUST_SHA256
            bundle.TRUST_SHA256 = hashlib.sha256(trust_path.read_bytes()).hexdigest()
            try:
                bundle.sign_bundle(out, key_path, trust_path, claim=constants.CLAIM_AWAITING)
                verified = bundle.verify_bundle(out)
            finally:
                bundle.TRUST_SHA256 = original
            self.assertTrue(verified["host_proof"])
            self.assertEqual(verified["tier"], "UNSET")

    def test_rejects_other_keys_claims_and_secrets(self) -> None:
        private = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trust_path = root / "trust.json"
            key_path = root / "key.pem"
            key_path.write_bytes(_pem(private))
            inputs = self._write_inputs(root / "in")
            out = root / "bundle"

            def assemble() -> None:
                if out.exists():
                    for path in sorted(out.rglob("*"), reverse=True):
                        if path.is_file():
                            path.unlink()
                        elif path.is_dir():
                            path.rmdir()
                    out.rmdir()
                proc = _run_operator(
                    "assemble",
                    "--out",
                    str(out),
                    "--claim",
                    constants.CLAIM_FIXTURE,
                    "--created-utc",
                    "2026-10-16T16:00:00Z",
                    "--host-record",
                    inputs["host"],
                    "--enterprise",
                    inputs["enterprise"],
                    "--descendant-pre",
                    inputs["pre"],
                    "--boot",
                    inputs["boot"],
                    "--serial",
                    inputs["serial"],
                    "--descendant-post",
                    inputs["post"],
                    "--uninstall",
                    inputs["uninstall"],
                    "--teardown",
                    inputs["teardown"],
                    "--seal-file",
                    inputs["seal"],
                    "--seal-digest",
                    inputs["digest"],
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)

            trust_path.write_bytes(_trust(private, label="PRODUCTION"))
            assemble()
            with self.assertRaises(PackageError) as caught:
                bundle.sign_bundle(out, key_path, trust_path, claim=constants.CLAIM_FIXTURE)
            self.assertEqual(caught.exception.reason, "trust_not_test")

            trust_path.write_bytes(_trust(private, not_a_production_root=False))
            assemble()
            with self.assertRaises(PackageError) as caught:
                bundle.sign_bundle(out, key_path, trust_path, claim=constants.CLAIM_FIXTURE)
            self.assertEqual(caught.exception.reason, "trust_not_test")

            payload = json.loads(_trust(private))
            payload["keys"].append(dict(payload["keys"][0]))
            trust_path.write_bytes(json.dumps(payload).encode("utf-8"))
            assemble()
            with self.assertRaises(PackageError) as caught:
                bundle.sign_bundle(out, key_path, trust_path, claim=constants.CLAIM_FIXTURE)
            self.assertEqual(caught.exception.reason, "trust_not_test")

            trust_path.write_bytes(_trust(private))
            assemble()
            with self.assertRaises(PackageError) as caught:
                bundle.sign_bundle(out, key_path, trust_path, claim="STRANGER_HOST_PROVED")
            self.assertEqual(caught.exception.reason, "claim_refused")

            inside = out / "operator-key.pem"
            inside.write_bytes(_pem(private))
            with self.assertRaises(PackageError) as caught:
                bundle.sign_bundle(out, inside, trust_path, claim=constants.CLAIM_FIXTURE)
            self.assertEqual(caught.exception.reason, "private_key_in_bundle")
            inside.unlink()

            (out / "serial.log").write_text(SERIAL + "\n-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
            with self.assertRaises(PackageError) as caught:
                bundle.sign_bundle(out, key_path, trust_path, claim=constants.CLAIM_FIXTURE)
            self.assertEqual(caught.exception.reason, "private_key_in_bundle")

    def test_secret_scan_and_grade_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = self._write_inputs(root / "in")
            secret_serial = root / "in" / "serial.txt"
            secret_serial.write_text(SERIAL + "\nAKIAEXAMPLEKEY\n", encoding="utf-8")
            leaked = _run_operator(
                "assemble",
                "--out",
                str(root / "leaked"),
                "--claim",
                constants.CLAIM_FIXTURE,
                "--created-utc",
                "2026-10-16T16:00:00Z",
                "--host-record",
                inputs["host"],
                "--enterprise",
                inputs["enterprise"],
                "--descendant-pre",
                inputs["pre"],
                "--boot",
                inputs["boot"],
                "--serial",
                str(secret_serial),
                "--descendant-post",
                inputs["post"],
                "--uninstall",
                inputs["uninstall"],
                "--teardown",
                inputs["teardown"],
                "--seal-file",
                inputs["seal"],
                "--seal-digest",
                inputs["digest"],
            )
            self.assertEqual(leaked.returncode, 1)
            self.assertIn("secret_scan", leaked.stderr)

            secret_serial.write_text(SERIAL, encoding="utf-8")
            enterprise = json.loads(Path(inputs["enterprise"]).read_text(encoding="utf-8"))
            enterprise["prompt"] = "keep this out"
            Path(inputs["enterprise"]).write_text(json.dumps(enterprise), encoding="utf-8")
            prompted = _run_operator(
                "assemble",
                "--out",
                str(root / "prompted"),
                "--claim",
                constants.CLAIM_FIXTURE,
                "--created-utc",
                "2026-10-16T16:00:00Z",
                "--host-record",
                inputs["host"],
                "--enterprise",
                inputs["enterprise"],
                "--descendant-pre",
                inputs["pre"],
                "--boot",
                inputs["boot"],
                "--serial",
                str(root / "in" / "serial.txt"),
                "--descendant-post",
                inputs["post"],
                "--uninstall",
                inputs["uninstall"],
                "--teardown",
                inputs["teardown"],
                "--seal-file",
                inputs["seal"],
                "--seal-digest",
                inputs["digest"],
            )
            self.assertIn("secret_scan", prompted.stderr)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = self._write_inputs(root / "in")
            key_path, trust_path, _private = self._material(root)
            out = root / "bundle"
            self.assertEqual(
                _run_operator(
                    "assemble",
                    "--out",
                    str(out),
                    "--claim",
                    constants.CLAIM_FIXTURE,
                    "--created-utc",
                    "2026-10-16T16:00:00Z",
                    "--host-record",
                    inputs["host"],
                    "--enterprise",
                    inputs["enterprise"],
                    "--descendant-pre",
                    inputs["pre"],
                    "--boot",
                    inputs["boot"],
                    "--serial",
                    inputs["serial"],
                    "--descendant-post",
                    inputs["post"],
                    "--uninstall",
                    inputs["uninstall"],
                    "--teardown",
                    inputs["teardown"],
                    "--seal-file",
                    inputs["seal"],
                    "--seal-digest",
                    inputs["digest"],
                ).returncode,
                0,
            )
            host = json.loads((out / "host-record.json").read_text(encoding="utf-8"))
            host["enabled_lsm"] = "lockdown,apparmor"
            (out / "host-record.json").write_text(json.dumps(host), encoding="utf-8")
            bundle.sign_bundle(out, key_path, trust_path, claim=constants.CLAIM_FIXTURE)
            with self.assertRaises(PackageError) as caught:
                bundle.verify_bundle(out)
            self.assertEqual(caught.exception.reason, "grade_mismatch")

            host["enabled_lsm"] = LSM
            (out / "host-record.json").write_text(json.dumps(host) + " \n", encoding="utf-8")
            bundle.sign_bundle(out, key_path, trust_path, claim=constants.CLAIM_FIXTURE)
            (out / "host-record.json").write_text(json.dumps(host) + " \n ", encoding="utf-8")
            with self.assertRaises(PackageError) as caught:
                bundle.verify_bundle(out)
            self.assertEqual(caught.exception.reason, "signature_invalid")


class CaptureTests(unittest.TestCase):
    def test_capture_boot_and_pins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_root(root)
            serial = root / "serial.log"
            serial.write_text(SERIAL, encoding="utf-8")
            out = root / "boot.json"
            proc = _run_operator("capture-boot", "--root", str(root), "--serial-file", str(serial), "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            body = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(body["boot_id"], BOOT1)
            self.assertEqual(body["serial_boot_id"], BOOT1)
            self.assertIn(LSM_WORD, body["serial_log"])
            pins = root / "bpf"
            (pins / "vantio_persist").parent.mkdir(parents=True)
            (pins / "vantio_persist").write_text("x", encoding="utf-8")
            (pins / "other").mkdir()
            (pins / "other" / "vantio_trace_map").write_text("x", encoding="utf-8")
            (pins / "ignore").write_text("x", encoding="utf-8")
            found = capture.list_bpffs_pins(pins)
            self.assertEqual(sorted(found), ["vantio_persist", "vantio_trace_map"])
            original = capture.MAX_BYTES
            capture.MAX_BYTES = 4
            try:
                with self.assertRaises(PackageError) as caught:
                    capture.capture_boot(root, "12345")
            finally:
                capture.MAX_BYTES = original
            self.assertEqual(caught.exception.reason, "serial_too_large")


class PackageBoundaryTests(unittest.TestCase):
    def test_sources_do_not_import_lab_runners(self) -> None:
        for path in SCRIPT.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("scripts.gcp", text, path.name)
            self.assertNotIn("scripts.aws", text, path.name)
            self.assertNotIn("offline_deliver", text, path.name)
            self.assertNotIn("w3_lab", text, path.name)

    def test_no_prices_or_absolute_claims(self) -> None:
        roots = [SCRIPT, ROOT / "docs" / "gap" / "t1-stranger-host"]
        for folder in roots:
            for path in folder.rglob("*"):
                if not path.is_file() or path.suffix not in {".py", ".md", ".sh"}:
                    continue
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("$499", text, path.name)
                self.assertNotIn("$799", text, path.name)
                self.assertNotIn("unbreakable", text.casefold(), path.name)
                self.assertNotIn("audited", text.casefold(), path.name)

    def test_git_paths_stay_in_the_package(self) -> None:
        diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "-uall"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        paths: list[str] = [line for line in diff.stdout.splitlines() if line]
        for line in status.stdout.splitlines():
            if len(line) >= 4:
                paths.append(line[3:].strip())
        for path in paths:
            self.assertTrue(
                any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in constants.PACKAGE_PREFIXES),
                path,
            )


if __name__ == "__main__":
    unittest.main()
