"""License fetch, host-prep, enroll, and enforce-mode refusals."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import stat
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tests.test_stage_a import Harness
from vantio_install import constants
from vantio_install.artifact_verify import artifact_trust_override, packaged_artifact_path_override
from vantio_install.bundle_fetch import classify_endpoint, fetch_bundle, redirect_refusal, verify_unpacked
from vantio_install.cli import main
from vantio_install.commands import enforce_container_argv
from vantio_install.enroll import refusal_reason
from vantio_install.gates import require_live_gates
from vantio_install.health import derive
from vantio_install.host_prep import dropin_text, prepare, remove_grub_dropin
from vantio_install.license_token import (
    issue_token,
    license_trust_override,
    packaged_license_keys,
    store_license,
    verify_token,
)
from vantio_install.observe_health import SCOPED_BANNER, enforce_proof, readiness_gaps
from vantio_install.signed_policy import DevPublicKey, dev_trust, sign_policy
from vantio_install.util import redact_text
from vantio_install.verifier import _recompute_health

PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"


def _public(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _license_key(private: Ed25519PrivateKey, *, kid: str = "lic-test", mode: str = "test") -> dict:
    return {"kid": kid, "alg": "Ed25519", "public_key_b64": _b64(_public(private)), "mode": mode}


def _payload(**overrides: object) -> dict:
    body = {
        "v": 1,
        "kid": "lic-test",
        "sku": "phantom-engine",
        "cus": "cus_lab",
        "sub": "sub_lab",
        "qty": 1,
        "interval": "month",
        "iat": 1_700_000_000,
        "exp": 4_000_000_000,
        "mode": "test",
    }
    body.update(overrides)
    return body


def _tar_bytes(files: dict[str, bytes], private: Ed25519PrivateKey, record: dict) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        lines = []
        for rel, data in sorted(files.items()):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            lines.append(f"{hashlib.sha256(data).hexdigest()}  {rel}")
        sums = ("\n".join(lines) + "\n").encode("utf-8")
        (root / "SHA256SUMS").write_bytes(sums)
        signed = dict(record)
        signed["algorithm"] = "Ed25519"
        signed["signature_b64"] = _b64(private.sign(sums))
        signed["public_key_b64"] = _b64(_public(private))
        (root / "SHA256SUMS.sig").write_text(json.dumps(signed), encoding="utf-8")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(root).as_posix())
        return buffer.getvalue()


def _transport(script: list[tuple[int, dict, bytes]]):
    calls: list[tuple[str, dict]] = []

    def transport(url: str, headers: dict, _timeout: float):
        calls.append((url, dict(headers)))
        status, resp_headers, body = script.pop(0)
        return status, resp_headers, [body]

    return transport, calls


class TokenTests(unittest.TestCase):
    def test_packaged_license_trust_is_empty(self) -> None:
        self.assertEqual(packaged_license_keys(), ())
        self.assertEqual(constants.FROZEN_PINS["pe_archive_sha256"], PIN)

    def test_round_trip_and_refusals(self) -> None:
        private = Ed25519PrivateKey.generate()
        key = _license_key(private)
        token = issue_token(_payload(), private)
        with license_trust_override((key,)):
            ok = verify_token(token, now=1_800_000_000)
            self.assertTrue(ok["ok"], ok)
            self.assertEqual(set(ok["license"]), {"sub", "qty", "interval", "exp", "kid"})
            self.assertNotIn("cus", ok["license"])
            tampered = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
            self.assertEqual(verify_token(tampered, now=1_800_000_000)["reason"], "BAD_SIGNATURE")
            self.assertEqual(verify_token(issue_token(_payload(kid="missing"), private), now=1)["reason"], "UNKNOWN_KID")
            self.assertEqual(verify_token(issue_token(_payload(sku="other"), private), now=1)["reason"], "SKU_MISMATCH")
            expired = verify_token(issue_token(_payload(exp=10), private), now=10)
            self.assertEqual(expired["reason"], "EXPIRED")
            self.assertEqual(expired["exp"], 10)
            live_key = _license_key(private, mode="live")
            with license_trust_override((live_key,)):
                self.assertEqual(verify_token(token, now=1)["reason"], "MODE_MISMATCH")
            self.assertEqual(verify_token(issue_token(_payload(qty=True), private), now=1)["reason"], "MALFORMED")
            self.assertEqual(verify_token("nope", now=1)["reason"], "MALFORMED")

    def test_store_is_mode_0600_and_redacted(self) -> None:
        private = Ed25519PrivateKey.generate()
        token = issue_token(_payload(), private)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "etc" / "vantio" / "license"
            store_license(token, path)
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(mode, 0o600)
            self.assertNotIn(token, redact_text("prefix " + token + " suffix"))


class FetchTests(unittest.TestCase):
    def test_endpoint_and_redirect_rules(self) -> None:
        self.assertEqual(classify_endpoint("http://127.0.0.1:9/bundle"), "lab")
        self.assertEqual(classify_endpoint("http://localhost/bundle"), "lab")
        self.assertEqual(classify_endpoint("https://127.0.0.1/bundle"), "SCHEME_REFUSED")
        self.assertEqual(classify_endpoint("http://vantio.ai/api/pe/download"), "SCHEME_REFUSED")
        self.assertEqual(classify_endpoint("https://vantio.ai/api/pe/download"), "production")
        self.assertEqual(classify_endpoint("https://www.vantio.ai/api/pe/download"), "production")
        self.assertEqual(classify_endpoint("https://evil.example/bundle"), "ENDPOINT_REFUSED")
        self.assertEqual(classify_endpoint("https://user:pw@vantio.ai/x"), "ENDPOINT_REFUSED")
        self.assertEqual(
            redirect_refusal("https://objects.githubusercontent.com/a", 1, "production", "https://vantio.ai/x"),
            None,
        )
        self.assertEqual(
            redirect_refusal("https://release-assets.githubusercontent.com/a", 1, "production", "https://vantio.ai/x"),
            None,
        )
        self.assertEqual(
            redirect_refusal("https://evil.example/a", 1, "production", "https://vantio.ai/x"),
            "REDIRECT_HOST_REFUSED",
        )
        self.assertEqual(
            redirect_refusal("http://objects.githubusercontent.com/a", 1, "production", "https://vantio.ai/x"),
            "REDIRECT_SCHEME_REFUSED",
        )
        self.assertEqual(
            redirect_refusal("https://objects.githubusercontent.com/a", 2, "production", "https://vantio.ai/x"),
            "REDIRECT_LIMIT",
        )
        self.assertEqual(redirect_refusal("https://objects.githubusercontent.com/a", 1, "lab", "http://127.0.0.1/x"), "REDIRECT_REFUSED")

    def _bundle(self, private: Ed25519PrivateKey, record: dict, *, body: bytes | None = None) -> bytes:
        files = {"artifacts/phantom-engine/PHANTOM-ARTIFACT-MANIFEST.json": body or b'{"capabilities":[]}\n'}
        return _tar_bytes(files, private, record)

    def test_lab_path_verifies_and_prod_refuses_test_key(self) -> None:
        private = Ed25519PrivateKey.generate()
        record = {
            "key_id": "test-nonprod-artifact-lab-test",
            "key_class": "test_non_production",
            "not_a_production_root": True,
        }
        blob = self._bundle(private, record)
        transport, calls = _transport([(200, {}, blob)])
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "bundle"
            with artifact_trust_override({"test-nonprod-artifact-lab-test": _public(private)}):
                result = fetch_bundle("http://127.0.0.1:9/bundle", dest, token="vl1.lab.token", transport=transport)
            self.assertTrue(result["ok"], result)
            self.assertTrue((dest / "artifacts/phantom-engine/PHANTOM-ARTIFACT-MANIFEST.json").is_file())
            self.assertFalse((Path(tmp) / "bundle.partial").exists())
            self.assertEqual(calls[0][1]["Authorization"], "Bearer vl1.lab.token")
        transport, _calls = _transport([(200, {}, blob)])
        with tempfile.TemporaryDirectory() as tmp:
            result = fetch_bundle(
                "https://vantio.ai/api/pe/download?asset=bundle",
                Path(tmp) / "bundle",
                token="vl1.lab.token",
                transport=transport,
            )
        self.assertEqual(result["reason"], "TEST_KEY_ON_PRODUCTION_PATH")
        self.assertEqual(result["exit_code"], constants.EXIT_BLOCKED)

    def test_production_key_comes_only_from_the_packaged_file(self) -> None:
        private = Ed25519PrivateKey.generate()
        record = {"key_id": "prod-artifact-lab", "key_class": "production"}
        blob = self._bundle(private, record)
        trust = {
            "keys": [
                {
                    "key_id": "prod-artifact-lab",
                    "key_class": "production",
                    "alg": "Ed25519",
                    "public_key_b64": _b64(_public(private)),
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            trust_path = Path(tmp) / "trust.json"
            trust_path.write_text(json.dumps(trust), encoding="utf-8")
            transport, calls = _transport(
                [
                    (302, {"Location": "https://objects.githubusercontent.com/bundle.tar"}, b""),
                    (200, {}, blob),
                ]
            )
            with packaged_artifact_path_override(trust_path):
                result = fetch_bundle(
                    "https://vantio.ai/api/pe/download",
                    Path(tmp) / "bundle",
                    token="secret-token",
                    transport=transport,
                )
            self.assertTrue(result["ok"], result)
            self.assertNotIn("secret-token", json.dumps(result))
            self.assertNotIn("objects.githubusercontent.com", json.dumps(result))
            self.assertEqual(calls[0][1]["Authorization"], "Bearer secret-token")
            self.assertNotIn("Authorization", calls[1][1])
            transport, _calls = _transport([(200, {}, blob)])
            with artifact_trust_override({"prod-artifact-lab": _public(private)}):
                refused = fetch_bundle(
                    "https://www.vantio.ai/api/pe/download?asset=bundle",
                    Path(tmp) / "other",
                    token="secret-token",
                    transport=transport,
                )
            self.assertEqual(refused["reason"], "UNTRUSTED_KEY")

    def test_sha_sig_size_and_http_status(self) -> None:
        private = Ed25519PrivateKey.generate()
        record = {
            "key_id": "test-nonprod-artifact-lab-test",
            "key_class": "test_non_production",
            "not_a_production_root": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / "artifact.bin").write_bytes(b"changed\n")
            lines = f"{hashlib.sha256(b'intact\n').hexdigest()}  artifact.bin\n"
            (tree / "SHA256SUMS").write_text(lines, encoding="utf-8")
            sums = lines.encode("utf-8")
            (tree / "SHA256SUMS.sig").write_text(
                json.dumps(
                    {
                        "algorithm": "Ed25519",
                        "key_id": "test-nonprod-artifact-lab-test",
                        "key_class": "test_non_production",
                        "not_a_production_root": True,
                        "signature_b64": _b64(private.sign(sums)),
                        "public_key_b64": _b64(_public(private)),
                    }
                ),
                encoding="utf-8",
            )
            with artifact_trust_override({"test-nonprod-artifact-lab-test": _public(private)}):
                mismatched = verify_unpacked(tree, production=False)
        self.assertEqual(mismatched["reason"], "SHA_MISMATCH")
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / "artifact.bin").write_bytes(b"intact\n")
            lines = f"{hashlib.sha256(b'intact\n').hexdigest()}  artifact.bin\n"
            sums = lines.encode("utf-8")
            (tree / "SHA256SUMS").write_bytes(sums)
            (tree / "SHA256SUMS.sig").write_text(
                json.dumps(
                    {
                        "algorithm": "Ed25519",
                        "key_id": "test-nonprod-artifact-lab-test",
                        "key_class": "test_non_production",
                        "not_a_production_root": True,
                        "signature_b64": _b64(private.sign(b"not-the-checksum-file")),
                        "public_key_b64": _b64(_public(private)),
                    }
                ),
                encoding="utf-8",
            )
            with artifact_trust_override({"test-nonprod-artifact-lab-test": _public(private)}):
                signed = verify_unpacked(tree, production=False)
        self.assertEqual(signed["reason"], "SIGNATURE_INVALID")
        transport, _calls = _transport([(200, {}, b"0123456789")])
        with tempfile.TemporaryDirectory() as tmp:
            sized = fetch_bundle("http://127.0.0.1/x", Path(tmp) / "bundle", token="t", transport=transport, max_bytes=4)
            self.assertEqual(sized["reason"], "TOO_LARGE")
            self.assertFalse((Path(tmp) / "bundle.partial").exists())
        for status, reason, code, message in (
            (401, "LICENSE_UNAUTHORIZED", constants.EXIT_LICENSE_UNAUTHORIZED, "The license was not accepted."),
            (403, "LICENSE_CANCELED_OR_EXPIRED", constants.EXIT_LICENSE_FORBIDDEN, "license canceled or expired"),
            (410, "DOWNLOAD_GONE", constants.EXIT_DOWNLOAD_GONE, "The sealed bundle is no longer available."),
            (429, "RATE_LIMITED", constants.EXIT_RATE_LIMITED, "Too many download attempts for this license."),
        ):
            transport, _calls = _transport([(status, {}, b"")])
            with tempfile.TemporaryDirectory() as tmp:
                result = fetch_bundle("http://127.0.0.1/x", Path(tmp) / "bundle", token="t", transport=transport)
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["exit_code"], code)
            self.assertEqual(result["message"], message)

    def test_fsync_and_second_redirect(self) -> None:
        private = Ed25519PrivateKey.generate()
        record = {
            "key_id": "test-nonprod-artifact-lab-test",
            "key_class": "test_non_production",
            "not_a_production_root": True,
        }
        blob = self._bundle(private, record)
        transport, _calls = _transport([(200, {}, blob)])
        with tempfile.TemporaryDirectory() as tmp, artifact_trust_override({"test-nonprod-artifact-lab-test": _public(private)}):
            with mock.patch("vantio_install.bundle_fetch.os.fsync", wraps=os.fsync) as synced:
                result = fetch_bundle("http://127.0.0.1/x", Path(tmp) / "bundle", token="t", transport=transport)
            self.assertTrue(result["ok"], result)
            self.assertGreaterEqual(synced.call_count, 1)
        transport, _calls = _transport(
            [
                (302, {"Location": "https://objects.githubusercontent.com/a"}, b""),
                (302, {"Location": "https://objects.githubusercontent.com/b"}, b""),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            limited = fetch_bundle("https://vantio.ai/api/pe/download", Path(tmp) / "bundle", token="t", transport=transport)
        self.assertEqual(limited["reason"], "REDIRECT_LIMIT")


class HostPrepTests(unittest.TestCase):
    def test_write_and_remove_dropin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lsm = root / "sys/kernel/security/lsm"
            lsm.parent.mkdir(parents=True)
            lsm.write_text("lockdown,capability,apparmor\n", encoding="utf-8")
            (root / "proc/sys/kernel/random").mkdir(parents=True)
            (root / "proc/sys/kernel/random/boot_id").write_text("boot-1\n", encoding="utf-8")
            calls: list[list[str]] = []

            def updater(argv: list[str]) -> int:
                calls.append(list(argv))
                return 0

            prepared = prepare(root, updater)
            self.assertEqual(prepared["result"], "REBOOT_REQUIRED")
            self.assertEqual(prepared["message"], "reboot required")
            self.assertEqual(prepared["boot_id"], "boot-1")
            text = (root / constants.GRUB_DROPIN_RELATIVE).read_text(encoding="utf-8")
            self.assertEqual(text, dropin_text("lockdown,capability,apparmor"))
            self.assertIn('lsm=lockdown,capability,apparmor,bpf', text)
            self.assertEqual(calls, [["update-grub"]])
            self.assertNotIn("reboot", json.dumps(calls))
            lsm.write_text("lockdown,capability,apparmor,bpf\n", encoding="utf-8")
            again = prepare(root, updater)
            self.assertEqual(again["result"], "NO_CHANGE_NEEDED")
            self.assertEqual(calls, [["update-grub"]])
            removed = remove_grub_dropin(root, updater)
            self.assertTrue(removed["ok"], removed)
            self.assertFalse((root / constants.GRUB_DROPIN_RELATIVE).exists())

    def test_refuses_shell_metacharacters_and_restores_when_grub_keeps_the_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lsm = root / "sys/kernel/security/lsm"
            lsm.parent.mkdir(parents=True)
            lsm.write_text("apparmor;rm -rf /\n", encoding="utf-8")
            refused = prepare(root, lambda _argv: 0)
            self.assertEqual(refused["result"], "LSM_UNREADABLE")
            self.assertFalse((root / constants.GRUB_DROPIN_RELATIVE).exists())
            lsm.write_text("apparmor\n", encoding="utf-8")
            prepare(root, lambda _argv: 0)
            token = "apparmor,bpf"
            cfg = root / "boot/grub/grub.cfg"
            cfg.parent.mkdir(parents=True)
            cfg.write_text(f"linux /vmlinuz ro lsm={token}\n", encoding="utf-8")
            failed = remove_grub_dropin(root, lambda _argv: 0)
            self.assertFalse(failed["ok"])
            self.assertEqual(failed["error"], "grub_cfg_still_has_lsm")
            self.assertTrue((root / constants.GRUB_DROPIN_RELATIVE).is_file())


class EnforceFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.get("VANTIO_INSTALL_ALLOW_LIVE")
        os.environ["VANTIO_INSTALL_ALLOW_LIVE"] = "1"

    def tearDown(self) -> None:
        if self._env is None:
            os.environ.pop("VANTIO_INSTALL_ALLOW_LIVE", None)
        else:
            os.environ["VANTIO_INSTALL_ALLOW_LIVE"] = self._env

    def _run(self, harness: Harness, command: str, extra: list[str], *, yes: bool = False, live: bool = True) -> tuple[int, dict]:
        harness.flush()
        flags = ["--i-accept-live-mutations"] if live else []
        argv = harness.argv(command, yes=yes) + flags + extra
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = main(argv)
        return code, json.loads(buf.getvalue())

    def _materials(self, harness: Harness):
        lic_private = Ed25519PrivateKey.generate()
        dev_private = Ed25519PrivateKey.generate()
        dev_public = _public(dev_private)
        policy = sign_policy(
            {"allow_enforcement": True, "enforcement": "ENROLLED"},
            key_id="dev-nonprod-lab-enforce",
            public_key=dev_public,
            sign=dev_private.sign,
        )
        policy_path = harness.root / "policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        token = issue_token(_payload(), lic_private)
        key = _license_key(lic_private)
        root = harness.state / "server-root"
        lsm = root / "sys/kernel/security/lsm"
        lsm.parent.mkdir(parents=True, exist_ok=True)
        lsm.write_text("lockdown,capability,apparmor,bpf\n", encoding="utf-8")
        return token, key, policy_path, dev_public, root

    def test_refusals_then_protected_and_removal(self) -> None:
        harness = self.make()
        self.assertEqual(harness.run("plan")[0], 0)
        self.assertEqual(harness.run("apply", yes=True)[0], 0)
        root = harness.state / "server-root"
        lsm = root / "sys/kernel/security/lsm"
        lsm.parent.mkdir(parents=True)
        lsm.write_text("lockdown,capability,apparmor\n", encoding="utf-8")
        code, body = self._run(harness, "host-prep", ["--write-lsm", "--i-accept-reboot"])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["message"], "reboot required")
        self.assertNotIn("reboot", json.dumps(body["commands"]))
        dropin = root / constants.GRUB_DROPIN_RELATIVE
        self.assertTrue(dropin.is_file())
        lsm.write_text("lockdown,capability,apparmor,bpf\n", encoding="utf-8")
        token, key, policy_path, dev_public, root = self._materials(harness)
        # _materials rewrites lsm; the drop-in from host-prep remains.
        with license_trust_override((key,)), dev_trust((DevPublicKey("dev-nonprod-lab-enforce", dev_public),)):
            missing, missing_body = self._run(
                harness,
                "apply",
                ["--enforce-enrolled", "--policy-file", str(policy_path)],
                yes=True,
            )
            self.assertEqual(missing_body["reason"], "LICENSE_MISSING", missing_body)
            store_license(token, root / constants.LICENSE_RELATIVE)
            degraded, degraded_body = self._run(
                harness,
                "apply",
                ["--enforce-enrolled", "--policy-file", str(policy_path)],
                yes=True,
            )
            self.assertEqual(degraded, 0, degraded_body)
            self.assertEqual(degraded_body["protection_state"], "DEGRADED")
            self.assertEqual(degraded_body["state"], "DEGRADED")
            self.assertIn("loader_missing_scoped_banner", degraded_body.get("degraded_reason", ""))
            log = root / "var/lib/vantio/enforce-loader.out"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("ready\n" + SCOPED_BANNER + "\n", encoding="utf-8")
            (root / "var/lib/vantio/bpf-programs.txt").write_text("cgroup_skb_egress_enforce\n", encoding="utf-8")
            denied, denied_body = self._run(
                harness,
                "apply",
                ["--enforce-enrolled", "--exec-preset", "web-server", "--policy-file", str(policy_path)],
                yes=True,
            )
            self.assertEqual(denied_body["reason"], "EXEC_DENY_NOT_IN_SEAL", denied_body)
            manifest = harness.bundle / "artifacts" / "phantom-engine" / "PHANTOM-ARTIFACT-MANIFEST.json"
            document = json.loads(manifest.read_text(encoding="utf-8"))
            document["capabilities"] = ["exec_deny"]
            manifest.write_text(json.dumps(document), encoding="utf-8")
            protected, protected_body = self._run(
                harness,
                "apply",
                ["--enforce-enrolled", "--exec-preset", "web-server", "--policy-file", str(policy_path)],
                yes=True,
            )
            self.assertEqual(protected, 0, protected_body)
            self.assertEqual(protected_body["protection_state"], "PROTECTED")
            self.assertEqual(protected_body["state"], "HEALTHY")
            self.assertNotIn(token, json.dumps(protected_body))
            joined = " ".join(" ".join(argv) for argv in harness.snapshot()["recorded_argv"])
            self.assertIn("--enforce", joined)
            self.assertIn("--exec-preset web-server", joined)
            self.assertIn("--cgroup-skb-enforce", joined)
            health = json.loads(harness.tx_file("HEALTH.json").read_text(encoding="utf-8"))
            self.assertEqual(health["protection_state"], "PROTECTED")
            self.assertEqual(set(health["license"]), {"sub", "qty", "interval", "exp", "kid"})
            self.assertEqual(health["overall"], _recompute_health(harness.snapshot(), json.loads(harness.tx_file("CONFIG.json").read_text(encoding="utf-8")), []))
            for unit in ("vantio-pe", "docker", "containerd", "sshd", "systemd-logind"):
                refused, refused_body = self._run(harness, "enroll", ["--unit", unit])
                self.assertEqual(refused_body["reason"], "UNIT_REFUSED", unit)
            enrolled, enrolled_body = self._run(harness, "enroll", ["--unit", "lab-workload"])
            self.assertEqual(enrolled, 0, enrolled_body)
            drop = root / "etc/systemd/system/lab-workload.service.d" / constants.ENROLL_DROPIN_NAME
            self.assertEqual(drop.read_text(encoding="utf-8"), "[Service]\nSlice=vantio-enrolled.slice\n")
            removed, removed_body = self._run(harness, "uninstall", ["--scope", "all"], yes=True)
            self.assertEqual(removed, 0, removed_body)
            self.assertFalse(dropin_exists(root))
            self.assertFalse((root / constants.LICENSE_RELATIVE).exists())
            self.assertFalse(drop.exists())
            verified, verified_body = self._run(harness, "verify-removal", ["--scope", "all"], live=False)
            self.assertEqual(verified_body["state"], "VERIFIED_REMOVED", verified_body)
            dropin = root / constants.GRUB_DROPIN_RELATIVE
            dropin.parent.mkdir(parents=True, exist_ok=True)
            dropin.write_text('GRUB_CMDLINE_LINUX="$GRUB_CMDLINE_LINUX lsm=apparmor,bpf"\n', encoding="utf-8")
            again, again_body = self._run(harness, "verify-removal", ["--scope", "all"], live=False)
            self.assertNotEqual(again_body["state"], "VERIFIED_REMOVED", again_body)
            self.assertTrue(any(item.get("kind") == "grub_dropin" for item in again_body.get("residual_items") or []))

    def test_policy_lsm_and_preset_refusals(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        token, key, policy_path, dev_public, root = self._materials(harness)
        store_license(token, root / constants.LICENSE_RELATIVE)
        (root / "sys/kernel/security/lsm").write_text("apparmor\n", encoding="utf-8")
        with license_trust_override((key,)), dev_trust((DevPublicKey("dev-nonprod-lab-enforce", dev_public),)):
            code, body = self._run(
                harness,
                "apply",
                ["--enforce-enrolled", "--policy-file", str(policy_path)],
                yes=True,
            )
        self.assertEqual(code, constants.EXIT_BLOCKED)
        self.assertEqual(body["reason"], "LSM_BPF_MISSING", body)
        preset, preset_body = self._run(harness, "apply", ["--exec-preset", "web-server"])
        self.assertEqual(preset_body["reason"], "EXEC_PRESET_REQUIRES_ENFORCE")
        self.assertIsNone(refusal_reason("nginx"))
        self.assertEqual(refusal_reason("vantio-loader"), "UNIT_REFUSED")

    def test_policy_that_does_not_allow_enforcement_is_refused(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        dev_private = Ed25519PrivateKey.generate()
        dev_public = _public(dev_private)
        policy = sign_policy(
            {"enforcement": "NOT_ENABLED"},
            key_id="dev-nonprod-lab-enforce",
            public_key=dev_public,
            sign=dev_private.sign,
        )
        policy_path = harness.root / "observe-policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        lic_private = Ed25519PrivateKey.generate()
        root = harness.state / "server-root"
        lsm = root / "sys/kernel/security/lsm"
        lsm.parent.mkdir(parents=True)
        lsm.write_text("apparmor,bpf\n", encoding="utf-8")
        store_license(issue_token(_payload(), lic_private), root / constants.LICENSE_RELATIVE)
        with license_trust_override((_license_key(lic_private),)), dev_trust((DevPublicKey("dev-nonprod-lab-enforce", dev_public),)):
            _code, body = self._run(
                harness,
                "apply",
                ["--enforce-enrolled", "--policy-file", str(policy_path)],
                yes=True,
            )
        self.assertEqual(body["reason"], "POLICY_DOES_NOT_ALLOW_ENFORCEMENT", body)

    def make(self) -> Harness:
        harness = Harness()
        self.addCleanup(harness.close)
        return harness


def dropin_exists(root: Path) -> bool:
    return (root / constants.GRUB_DROPIN_RELATIVE).exists()


class HealthAgreementTests(unittest.TestCase):
    def test_protected_and_degraded_match(self) -> None:
        config = {"enforcement": "NOT_ENABLED", "path_deny": "disabled", "otlp": "DISABLED", "iface": "ens5", "install_mode": "observe-only"}
        snapshot = {
            "optics_cli_version": constants.FROZEN_PINS["optics_cli_version"],
            "containers": [
                {
                    "role": "phantom_engine",
                    "status": "running",
                    "cmd": ["--iface", "ens5", "--enforce"],
                    "enforce": True,
                }
            ],
            "processes": ["vantio-loader"],
            "bpf_pins": list(constants.BPF_PINS),
            "clsact_ifaces": ["ens5"],
            "active_lsm": "lockdown,capability,apparmor,bpf",
            "enforce_enrollment": {
                "requested": True,
                "loader_output": "SCOPED (drop enrolled)\n",
                "bpf_programs": ["cgroup_skb_egress_enforce"],
            },
        }
        health = derive(snapshot, config)
        self.assertEqual(health["protection_state"], "PROTECTED")
        self.assertEqual(health["overall"], "PASS")
        self.assertEqual(health["components"]["enforcement"], "PASS")
        self.assertEqual(_recompute_health(snapshot, config, []), "PASS")
        snapshot["enforce_enrollment"]["loader_output"] = "not yet"
        degraded = derive(snapshot, config)
        self.assertEqual(degraded["protection_state"], "DEGRADED")
        self.assertEqual(degraded["overall"], "DEGRADED")
        self.assertEqual(_recompute_health(snapshot, config, []), "DEGRADED")
        self.assertFalse(enforce_proof("nope", [])[0])
        gaps = readiness_gaps(
            {
                "mode": "enforce-enrolled",
                "lifecycle": "detached",
                "loader_output": SCOPED_BANNER,
                "bpf_programs": ["cgroup_skb_egress_enforce"],
            }
        )
        self.assertEqual(gaps, [])

    def test_enforce_argv_preset_is_opt_in(self) -> None:
        plain = enforce_container_argv(tag="tag", iface="ens5", name="vantio-pe")
        self.assertNotIn("--exec-preset", plain)
        preset = enforce_container_argv(tag="tag", iface="ens5", name="vantio-pe", exec_preset="web-server")
        self.assertIn("--exec-preset", preset)
        self.assertIn("web-server", preset)

    def test_gates_reject_a_single_flag(self) -> None:
        previous = os.environ.pop("VANTIO_INSTALL_ALLOW_LIVE", None)
        try:
            with self.assertRaises(Exception):
                require_live_gates({"accept_live_mutations": True, "fixture_host": "x"})
        finally:
            if previous is not None:
                os.environ["VANTIO_INSTALL_ALLOW_LIVE"] = previous


def _battery():
    import importlib.util

    path = Path(__file__).resolve().parents[3] / "scripts" / "aws" / "lab-guests" / "self_service_enforce.py"
    spec = importlib.util.spec_from_file_location("self_service_enforce", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BatteryTests(unittest.TestCase):
    def test_grade_pass_and_each_failure(self) -> None:
        battery = _battery()
        document = {
            "enterprise_rows": False,
            "redteam_brain": False,
            "pre": {"reboot_requested": True, "boot_id": "boot-a", "observe_done": True},
            "post": {
                "boot_id": "boot-b",
                "verify_state": "VERIFIED_REMOVED",
                "grub_dropin": False,
                "probes": {
                    "enrolled_egress_errno": 1,
                    "enrolled_file_errno": 13,
                    "unenrolled_egress_errno": 110,
                    "unenrolled_file_errno": 0,
                },
            },
        }
        self.assertEqual(battery.grade(document)["result"], "PASS")
        for key, value, reason in (
            ("enterprise_rows", True, "enterprise_rows"),
            ("redteam_brain", True, "redteam_brain"),
        ):
            broken = json.loads(json.dumps(document))
            broken[key] = value
            self.assertIn(reason, battery.grade(broken)["reasons"])
        broken = json.loads(json.dumps(document))
        broken["pre"]["reboot_requested"] = False
        self.assertIn("reboot_not_requested", battery.grade(broken)["reasons"])
        broken = json.loads(json.dumps(document))
        broken["post"]["probes"]["enrolled_egress_errno"] = 0
        self.assertIn("enrolled_egress", battery.grade(broken)["reasons"])
        broken = json.loads(json.dumps(document))
        broken["post"]["probes"]["enrolled_file_errno"] = 0
        self.assertIn("enrolled_file", battery.grade(broken)["reasons"])
        broken = json.loads(json.dumps(document))
        broken["post"]["probes"]["unenrolled_egress_errno"] = 1
        self.assertIn("unenrolled_affected", battery.grade(broken)["reasons"])
        broken = json.loads(json.dumps(document))
        broken["post"]["verify_state"] = "RESIDUAL_PRESENT"
        self.assertIn("verify_removal", battery.grade(broken)["reasons"])
        broken = json.loads(json.dumps(document))
        broken["post"]["grub_dropin"] = True
        self.assertIn("grub_dropin", battery.grade(broken)["reasons"])
        broken = json.loads(json.dumps(document))
        broken["post"]["boot_id"] = "boot-a"
        self.assertIn("boot_unchanged", battery.grade(broken)["reasons"])

    def test_argv_has_no_caller_trust_and_mint_keeps_the_private_key(self) -> None:
        battery = _battery()
        for phase in ("plan", "apply-observe", "host-prep", "apply-enforce", "enroll", "uninstall", "verify-removal"):
            argv = battery._argv(phase)
            self.assertNotIn("--fixture-host", argv)
            self.assertNotIn("--artifact-trust", argv)
        calls = []

        def invoke(argv):
            calls.append(argv)
            return 0, {"state": "HEALTHY"}

        pre = battery.run_pre(invoke, lsm_has_bpf=True, schedule_reboot=lambda: True)
        self.assertEqual([item[0] for item in calls], ["plan", "apply", "host-prep"])
        self.assertNotIn("--enforce-enrolled", calls[1])
        self.assertTrue(pre["reboot_requested"])
        post = battery.run_post(
            invoke,
            observe_done=True,
            probe=lambda: {
                "enrolled_egress_errno": 1,
                "enrolled_file_errno": 13,
                "unenrolled_egress_errno": 0,
                "unenrolled_file_errno": 0,
            },
            grub_dropin_present=lambda: False,
        )
        self.assertEqual(post["verify_state"], "HEALTHY")
        with tempfile.TemporaryDirectory() as tmp:
            summary = battery.mint(Path(tmp))
            text = json.dumps(summary)
            token = (Path(tmp) / "license.token").read_text(encoding="ascii").strip()
            self.assertNotIn(token, text)
            self.assertNotIn("PRIVATE KEY", text)
            blob = b"".join(path.read_bytes() for path in Path(tmp).rglob("*") if path.is_file())
            self.assertNotIn(b"PRIVATE KEY", blob)
            self.assertEqual(stat.S_IMODE((Path(tmp) / "license.token").stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
