#!/usr/bin/env python3
"""Offline tests for the H2 host checks and the F0-a public-pin fetch.

Stubs only. Nothing here runs docker, systemctl, iptables, gh, npm or any
network call.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lab"))
sys.path.insert(0, str(ROOT / "scripts" / "aws" / "lab-guests"))
import hostcheck_rows as hc  # noqa: E402
import self_service as ss  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "gcp"))
import offline_deliver_1 as od1  # noqa: E402

LAB_ENV = {
    "VANTIO_LAB_EXPECTED_HOST": "vantio-gcp-lab-12",
    "VANTIO_LAB_EXPECTED_PROJECT": "vantio-lab-oct08",
    "VANTIO_LAB_EXPECTED_ZONE": "us-central1-a",
}


class LabEnvCase(unittest.TestCase):
    """F3: the expected-host env is set per test (patch.dict), never at import."""

    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ, LAB_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)

# Pinned sha256 of the fixed argv artifact. A change to any argv, the env,
# the E4-3 pattern, the placeholder or the timeout changes this value and
# needs a fresh independent re-hash at P3.
PINNED_ARGV_SHA256 = "d52b5c4f145742b2f2be509a2176fdd7aacab5f01ac7cecb9300a3cc869cea2e"

PE = "vantio-pe-abc123def456"
FAKE_SECRET = "sk-test-not-a-real-value-123"

HEALTHY = {
    "S0-a": (0, "Tue Nov  3 19:40:00 UTC 2026\n", ""),
    "S0-b": (0, "vantio-gcp-lab-12\n", ""),
    "S0-c": (0, "2026-11-03 19:30:00\n", ""),
    "S0-d": (0, "iptables v1.8.10 (nf_tables)\n", ""),
    "S0-e": (0, "ip6tables v1.8.10 (nf_tables)\n", ""),
    "E4-1": (0, f"{PE} vantio-phantom-engine:egress-2e6ab54 Up 3 minutes\n", ""),
    "E4-2": (0, "PATH\nVANTIO_TELEMETRY_DISABLED\nDO_NOT_TRACK\nVANTIO_CLOUD_INGEST_URL\nVANTIO_API_KEY\n\n", ""),
    "E4-3": (0, "PATH=/usr/bin\nVANTIO_TELEMETRY_DISABLED=1\nDO_NOT_TRACK=1\nVANTIO_CLOUD_INGEST_URL=\nVANTIO_API_KEY=  \n", ""),
    "E5-1": (0, (
        "-rw-r--r-- 1 root root 400 Nov  3 19:30 /etc/systemd/system/vantio-boot-hold.service\n"
        "lrwxrwxrwx 1 root root 45 Nov  3 19:30 /etc/systemd/system/sysinit.target.wants/vantio-boot-hold.service -> /etc/systemd/system/vantio-boot-hold.service\n"
        "-rwxr-xr-x 1 root root 900 Nov  3 19:30 /usr/local/bin/vantio-boot-hold\n"
        "-rw-r--r-- 1 root root 300 Nov  3 19:30 /etc/vantio/boot-hold.json\n"
    ), ""),
    "E5-2": (0, (
        "total 0\n"
        "lrwxrwxrwx 1 root root 40 Nov  3 19:30 vantio-pe-loader.service -> /etc/systemd/system/vantio-pe-loader.service\n"
        "lrwxrwxrwx 1 root root 40 Nov  3 19:30 vantio-pe-enforce-ready.service -> /etc/systemd/system/vantio-pe-enforce-ready.service\n"
        "lrwxrwxrwx 1 root root 40 Nov  3 19:30 vantio-enrolled-network.service -> /etc/systemd/system/vantio-enrolled-network.service\n"
    ), ""),
    "E5-3": (0, "LoadState=loaded\nUnitFileState=enabled\nActiveState=inactive\nSubState=dead\nResult=success\n", ""),
    "E5-4": (0, "-N VANTIO_BOOT_HOLD\n-A VANTIO_BOOT_HOLD -j DROP\n", ""),
    "E5-5": (0, "-P OUTPUT ACCEPT\n-A OUTPUT -m cgroup --path system.slice/docker.service -j VANTIO_BOOT_HOLD\n", ""),
    "E5-6": (0, "-P FORWARD DROP\n-A FORWARD -s 10.250.250.0/24 -j VANTIO_BOOT_HOLD\n", ""),
    "E5-7": (0, "-N VANTIO_BOOT_HOLD\n-A VANTIO_BOOT_HOLD -j DROP\n", ""),
    "E5-8": (0, "-P OUTPUT ACCEPT\n-A OUTPUT -m cgroup --path system.slice/docker.service -j VANTIO_BOOT_HOLD\n", ""),
    "E5-9": (0, "-P FORWARD DROP\n-A FORWARD -s fd76:616e:7469::/64 -j VANTIO_BOOT_HOLD\n", ""),
    "E5-10": (0, '{"network_hold": true, "released": false, "last_reason": "boot-hold", "at": "2026-11-03T19:30:01Z"}', ""),
    "E5-11": (0, '{"state": "HELD", "health": "DEGRADED", "detail": "free text not kept"}', ""),
    "E5-12": (0, '{"enabled": true, "hold": true, "ordering": true, "signature": "c2lnbmF0dXJlLXZhbHVl"}', ""),
    "E5-13": (0, '{"command": "apply-boot", "result": "HELD", "at": "2026-11-03T19:30:01Z"}\n', ""),
}

IPV6_TABLE_ERROR = "ip6tables v1.8.7 (legacy): can't initialize ip6tables table `filter': Table does not exist (do you need to insmod?)"
IPV6_AF_ERROR = "ip6tables v1.8.10 (nf_tables): Could not fetch rule set generation id: Address family not supported by protocol"


class Stub:
    """Answers each fixed argv from a table keyed by row id. Records every call."""

    def __init__(self, overrides: dict | None = None) -> None:
        self.table = {**HEALTHY, **(overrides or {})}
        self.calls: list[tuple[str, list[str], dict]] = []

    def __call__(self, argv: list[str], env: dict):
        for row, fixed in hc.HOSTCHECK_ARGV:
            want = [PE if part == hc.PLACEHOLDER else part for part in fixed]
            if argv == want:
                self.calls.append((row, argv, env))
                return self.table[row]
        raise AssertionError(f"argv not in the fixed list: {argv}")


def by_row(result: dict) -> dict:
    return {row["row"]: row for row in result["rows"]}


class ArgvListTests(LabEnvCase):
    def test_argv_sha_is_pinned_and_printed(self) -> None:
        sha = hc.argv_sha256()
        print(f"\nHOSTCHECK-ARGV-SHA256 {sha}")
        self.assertEqual(sha, PINNED_ARGV_SHA256)
        self.assertEqual(hashlib.sha256(hc.argv_artifact_bytes()).hexdigest(), sha)
        self.assertEqual(hc.main(["--argv-sha256"]), 0)

    def test_argv_list_is_fixed_and_has_no_shell(self) -> None:
        self.assertEqual(len(hc.HOSTCHECK_ARGV), 21)
        self.assertEqual(len(set(hc.ROW_IDS)), 21)
        self.assertEqual(hc.ROW_IDS[0], "S0-a")
        self.assertEqual(hc.ROW_IDS[-1], "E5-13")
        for row, argv in hc.HOSTCHECK_ARGV:
            with self.subTest(row=row):
                self.assertIsInstance(argv, tuple)
                self.assertNotIn(argv[0], {"sh", "bash", "sudo", "env", "eval"})
                self.assertNotIn("-c", argv[:2])
                for part in argv:
                    self.assertNotIn("|", part.replace("{{", "").replace("}}", "") if row.startswith("E4") else part)
                    self.assertNotIn("$(", part)
                    self.assertNotIn(";", part)
        self.assertEqual(dict(hc.HOSTCHECK_ARGV)["E4-2"][-1], hc.PLACEHOLDER)

    def test_placeholder_only_takes_a_validated_name(self) -> None:
        self.assertEqual(hc._argv_for("E4-3", PE)[-1], PE)
        for bad in (None, "", "vantio-pe-", "vantio-pe-abc;rm", "other-name", "vantio-pe-abc def"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                hc._argv_for("E4-2", bad)

    def test_run_argv_uses_no_shell_no_stdin_and_the_fixed_env(self) -> None:
        with mock.patch.object(hc.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="x", stderr="")
            self.assertEqual(hc.run_argv(["date"], dict(hc.HOSTCHECK_ENV)), (0, "x", ""))
        kwargs = run.call_args.kwargs
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["stdin"], hc.subprocess.DEVNULL)
        self.assertEqual(kwargs["env"], hc.HOSTCHECK_ENV)
        self.assertEqual(kwargs["timeout"], hc.TIMEOUT_SECONDS)
        with mock.patch.object(hc.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(hc.run_argv(["ip6tables", "--version"], {}), (None, "", ""))


class HealthyRunTests(LabEnvCase):
    def test_all_rows_recorded_and_no_values_kept(self) -> None:
        stub = Stub()
        result = hc.run_hostcheck(stub)
        rows = by_row(result)
        self.assertEqual([row["row"] for row in result["rows"]], list(hc.ROW_IDS))
        self.assertTrue(all(row["outcome"] == hc.RECORDED for row in result["rows"]), result)
        self.assertEqual(result["summary"]["e5d_outcome"], hc.E5D_RECORDED)
        self.assertEqual(result["summary"]["ipv6"], "READ")
        self.assertEqual(result["summary"]["argv_sha256"], PINNED_ARGV_SHA256)
        self.assertEqual(rows["E4-3"]["facts"], {"checkin_nonempty_count": 0})
        self.assertTrue(rows["E4-2"]["facts"]["telemetry_disabled_name"])
        self.assertTrue(rows["E5-1"]["facts"]["wants_is_symlink"])
        self.assertEqual(rows["E5-3"]["facts"]["ActiveState"], "inactive")
        self.assertTrue(rows["E5-10"]["facts"]["bool_network_hold"])
        self.assertEqual(rows["E5-11"]["facts"]["word_state"], "HELD")
        self.assertTrue(rows["E5-12"]["facts"]["signature_field_present"])
        self.assertTrue(rows["E5-13"]["facts"]["apply_boot_held_seen"])
        text = json.dumps(result)
        for value in ("c2lnbmF0dXJlLXZhbHVl", "free text not kept", "2026-11-03T19:30:01Z", "/usr/bin", "egress-2e6ab54", "vantio-gcp-lab-12"):
            self.assertNotIn(value, text)
        for _, _, env in stub.calls:
            self.assertEqual(env, hc.HOSTCHECK_ENV)

    def test_e5_1_does_not_count_the_symlink_target_as_the_unit(self) -> None:
        out = HEALTHY["E5-1"][1].splitlines()
        missing_unit = "\n".join(out[1:]) + "\n"
        result = hc.run_hostcheck(Stub({"E5-1": (2, missing_unit, "ls: cannot access '/etc/systemd/system/vantio-boot-hold.service': No such file or directory\n")}))
        row = by_row(result)["E5-1"]
        self.assertEqual(row["outcome"], hc.STOP)
        self.assertFalse(row["facts"]["unit_present"])


class Q8Tests(LabEnvCase):
    def assert_not_present(self, error: str) -> None:
        result = hc.run_hostcheck(Stub({"E5-7": (1, "", error + "\n")}))
        rows = by_row(result)
        self.assertEqual(rows["E5-7"]["outcome"], hc.IPV6_NOT_PRESENT)
        self.assertEqual(rows["E5-7"]["reason"], "RECORD_AND_CONTINUE")
        self.assertEqual(rows["E5-7"]["facts"]["ipv6_error_verbatim"], error)
        for row in ("E5-8", "E5-9"):
            self.assertEqual(rows[row]["outcome"], hc.NOT_RUN)
            self.assertEqual(rows[row]["reason"], "IPV6_NOT_PRESENT")
        for row in ("E5-10", "E5-11", "E5-12", "E5-13"):
            self.assertEqual(rows[row]["outcome"], hc.RECORDED, "record and continue, never a neutral skip")
        summary = result["summary"]
        self.assertEqual(summary["e5d_outcome"], "NOT_PASS_IPV6_NOT_PRESENT")
        self.assertEqual(summary["e5d_note"], "IPv6 half not read; E5 (d) cannot be recorded as active")
        self.assertEqual(summary["ipv6_error_verbatim"], error)

    def test_table_initialise_error_is_ipv6_not_present(self) -> None:
        self.assert_not_present(IPV6_TABLE_ERROR)

    def test_address_family_error_is_ipv6_not_present(self) -> None:
        self.assert_not_present(IPV6_AF_ERROR)

    def assert_missing(self, version: tuple) -> None:
        result = hc.run_hostcheck(Stub({"S0-e": version}))
        rows = by_row(result)
        self.assertEqual(rows["S0-e"]["outcome"], hc.IP6TABLES_MISSING)
        self.assertEqual(rows["S0-e"]["reason"], "IP6TABLES_MISSING")
        later = [row for row in result["rows"] if hc.ROW_IDS.index(row["row"]) > hc.ROW_IDS.index("S0-e")]
        self.assertTrue(later and all(row["outcome"] == hc.NOT_RUN for row in later))
        self.assertEqual(result["summary"]["e5d_outcome"], hc.E5D_STOPPED)
        self.assertEqual(result["summary"]["stopped_at"], "S0-e")

    def test_missing_ip6tables_is_a_stop(self) -> None:
        self.assert_missing((None, "", ""))

    def test_failing_version_command_is_a_stop(self) -> None:
        self.assert_missing((1, "", "ip6tables: error\n"))

    def test_af_error_without_a_good_version_is_missing_not_absent(self) -> None:
        self.assertEqual(hc.classify_ipv6(1, 1, IPV6_AF_ERROR), (hc.IP6TABLES_MISSING, ""))
        self.assertEqual(hc.classify_ipv6(None, 1, IPV6_TABLE_ERROR), (hc.IP6TABLES_MISSING, ""))

    def test_any_other_ip6tables_error_is_a_stop(self) -> None:
        for err in ("ip6tables: No chain/target/match by that name.", "Permission denied (you must be root)", ""):
            with self.subTest(err=err):
                result = hc.run_hostcheck(Stub({"E5-7": (1, "", err + "\n")}))
                rows = by_row(result)
                self.assertEqual(rows["E5-7"]["outcome"], hc.IPV6_OTHER_ERROR)
                self.assertEqual(rows["E5-7"]["facts"], {})
                self.assertTrue(all(rows[r]["outcome"] == hc.NOT_RUN for r in ("E5-8", "E5-9", "E5-10", "E5-13")))
                self.assertEqual(result["summary"]["e5d_outcome"], hc.E5D_STOPPED)
                self.assertNotIn("e5d_note", result["summary"])
        self.assertEqual(hc.classify_ipv6(0, None, IPV6_AF_ERROR), (hc.IPV6_OTHER_ERROR, ""))

    def test_af_error_after_ipv6_was_read_is_a_stop(self) -> None:
        result = hc.run_hostcheck(Stub({"E5-8": (1, "", IPV6_AF_ERROR + "\n")}))
        rows = by_row(result)
        self.assertEqual(rows["E5-7"]["outcome"], hc.RECORDED)
        self.assertEqual(rows["E5-8"]["outcome"], hc.IPV6_OTHER_ERROR)
        self.assertEqual(rows["E5-9"]["outcome"], hc.NOT_RUN)


class GateTests(LabEnvCase):
    def assert_stop(self, overrides: dict, row: str, reason: str) -> dict:
        result = hc.run_hostcheck(Stub(overrides))
        rows = by_row(result)
        self.assertEqual(rows[row]["outcome"], hc.STOP, rows[row])
        self.assertEqual(rows[row]["reason"], reason)
        index = hc.ROW_IDS.index(row)
        for later in hc.ROW_IDS[index + 1:]:
            self.assertEqual(rows[later]["outcome"], hc.NOT_RUN)
            self.assertEqual(rows[later]["rc"], None)
        self.assertEqual(result["summary"]["stopped_at"], row)
        return result

    def test_e4_1_gate(self) -> None:
        two = HEALTHY["E4-1"][1] + "vantio-pe-ffff img Up 1 minute\n"
        for out in (two, "", f"{PE} img Exited (0) 1 minute ago\n", "evil-name img Up 1 minute\n"):
            with self.subTest(out=out):
                stub = Stub({"E4-1": (0, out, "")})
                hc.run_hostcheck(stub)
                self.assertNotIn("E4-2", [row for row, _, _ in stub.calls])
                self.assert_stop({"E4-1": (0, out, "")}, "E4-1", "E4_1_GATE")
        self.assert_stop({"E4-1": (1, HEALTHY["E4-1"][1], "")}, "E4-1", "E4_1_GATE")

    def test_e4_2_non_name_line_copies_nothing(self) -> None:
        result = self.assert_stop({"E4-2": (0, f"PATH\nVANTIO_API_KEY={FAKE_SECRET}\n", "")}, "E4-2", "NON_NAME_LINE_NOT_COPIED")
        self.assertNotIn(FAKE_SECRET, json.dumps(result))
        self.assertEqual(by_row(result)["E4-2"]["facts"], {})

    def test_e4_2_needs_both_opt_out_names(self) -> None:
        self.assert_stop({"E4-2": (0, "PATH\nVANTIO_TELEMETRY_DISABLED\n", "")}, "E4-2", "E4_2_REQUIRED_NAME_MISSING")
        self.assert_stop({"E4-2": (1, "", "template: split rejected")}, "E4-2", "NONZERO_RC_OR_SPLIT_REJECT")

    def test_e4_3_keeps_only_the_count(self) -> None:
        out = f"PATH=/usr/bin\nVANTIO_API_KEY={FAKE_SECRET}\nVANTIO_CLOUD_INGEST_URL=https://ingest.invalid\n"
        result = self.assert_stop({"E4-3": (0, out, "")}, "E4-3", "E4_3_COUNT_NOT_ZERO")
        self.assertEqual(by_row(result)["E4-3"]["facts"], {"checkin_nonempty_count": 2})
        text = json.dumps(result)
        self.assertNotIn(FAKE_SECRET, text)
        self.assertNotIn("ingest.invalid", text)
        self.assert_stop({"E4-3": (1, "", "")}, "E4-3", "NONZERO_RC")

    def test_e5_rows_stop_on_unexpected_state(self) -> None:
        self.assert_stop({"E5-3": (0, HEALTHY["E5-3"][1].replace("inactive", "active"), "")}, "E5-3", "E5_3_NOT_FRESH_OR_FAILED")
        self.assert_stop({"E5-3": (0, "LoadState=loaded\nWeird line\n", "")}, "E5-3", "E5_3_UNEXPECTED_LINE")
        self.assert_stop({"E5-4": (1, "", "iptables: No chain/target/match by that name.")}, "E5-4", "IPV4_HOLD_NOT_AS_EXPECTED")
        self.assert_stop({"E5-6": (0, "-P FORWARD DROP\n", "")}, "E5-6", "IPV4_HOLD_NOT_AS_EXPECTED")
        self.assert_stop({"E5-10": (0, '{"network_hold": true, "released": true}', "")}, "E5-10", "E5_10_ALREADY_RELEASED")
        self.assert_stop({"E5-11": (0, '{"state": "OPTED_OUT"}', "")}, "E5-11", "E5_11_HOLD_OFF_BY_POLICY")
        self.assert_stop({"E5-12": (0, "not json", "")}, "E5-12", "NOT_JSON_OR_NONZERO_RC")
        self.assert_stop({"E5-2": (0, "total 0\n", "")}, "E5-2", "E5_2_NOT_ALL_PRESENT")


class PassTwoHarnessTests(LabEnvCase):
    """Quinn V4 notes B-2, B-3 and B-7 on the harness side."""

    def test_bare_table_does_not_exist_is_not_ipv6_absent(self) -> None:
        # B-3: only the address-family or table-initialise wording counts.
        self.assertIsNone(hc.IPV6_ABSENT_RE.search("ip6tables: Table does not exist (do you need to insmod?)"))
        self.assertIsNotNone(hc.IPV6_ABSENT_RE.search(IPV6_TABLE_ERROR))
        self.assertIsNotNone(hc.IPV6_ABSENT_RE.search(IPV6_AF_ERROR))
        result = hc.run_hostcheck(Stub({"E5-7": (1, "", "ip6tables: Table does not exist (do you need to insmod?)")}))
        rows = by_row(result)
        self.assertEqual(rows["E5-7"]["outcome"], hc.IPV6_OTHER_ERROR)
        self.assertEqual(result["summary"]["stopped_at"], "E5-7")
        self.assertNotIn("ipv6_error_verbatim", json.dumps(result))

    def test_od1_regex_matches_the_harness_regex(self) -> None:
        self.assertEqual(od1.HOSTCHECK_IPV6_ABSENT.pattern, hc.IPV6_ABSENT_RE.pattern)
        self.assertEqual(od1.HOSTCHECK_IPV6_ABSENT.flags, hc.IPV6_ABSENT_RE.flags)

    def test_s0_b_not_a_lab_host_name_is_a_stop(self) -> None:
        # B-7: a host name that is not vantio-gcp-lab-<digits> stops before E4-1.
        for name in ("prod-db-1\n", "vantio-gcp-lab-\n", "vantio-gcp-lab-12x\n", "\n"):
            result = hc.run_hostcheck(Stub({"S0-b": (0, name, "")}))
            rows = by_row(result)
            self.assertEqual(rows["S0-b"]["outcome"], hc.STOP, name)
            self.assertEqual(rows["S0-b"]["reason"], "NOT_A_LAB_HOST_NAME")
            self.assertFalse(rows["S0-b"]["facts"]["host_name_match"])
            self.assertEqual(rows["E4-1"]["outcome"], hc.NOT_RUN)
            self.assertEqual(result["summary"]["stopped_at"], "S0-b")
            self.assertNotIn("prod-db", json.dumps(result))

    def test_e5_3_value_outside_the_systemd_set_is_a_stop(self) -> None:
        result = hc.run_hostcheck(Stub({"E5-3": (0, HEALTHY["E5-3"][1].replace("Result=success", "Result=tok3n"), "")}))
        rows = by_row(result)
        self.assertEqual(rows["E5-3"]["outcome"], hc.STOP)
        self.assertNotIn("tok3n", json.dumps(result))

    def test_e5_3_sets_match_od1(self) -> None:
        self.assertEqual(set(hc.E5_3_VALUES), set(od1.HOSTCHECK_FACTS["E5-3"]))
        for key, values in hc.E5_3_VALUES.items():
            self.assertEqual(values, od1.HOSTCHECK_FACTS["E5-3"][key], key)

    def test_json_word_with_a_digit_is_kept_as_has_only(self) -> None:
        result = hc.run_hostcheck(Stub({"E5-11": (0, '{"state": "HELD", "health": "abc123secret"}', "")}))
        facts = by_row(result)["E5-11"]["facts"]
        self.assertEqual(facts.get("word_state"), "HELD")
        self.assertNotIn("word_health", facts)
        self.assertIs(facts.get("has_health"), True)
        self.assertNotIn("abc123secret", json.dumps(result))


class PassTwoAllowlistTests(LabEnvCase):
    """B-2: the evidence allowlist keeps per-row keys and enum values only."""

    def assert_round_trip(self, result: dict) -> None:
        kept = od1.allow_hostcheck(result)
        self.assertEqual([r["row"] for r in kept["rows"]], [r["row"] for r in result["rows"]])
        for before, after in zip(result["rows"], kept["rows"]):
            self.assertEqual(after["facts"], before["facts"], before["row"])
            self.assertEqual(after["outcome"], before["outcome"])

    def test_every_fact_the_harness_emits_survives_the_allowlist(self) -> None:
        self.assert_round_trip(hc.run_hostcheck(Stub()))
        self.assert_round_trip(hc.run_hostcheck(Stub({"E5-7": (1, "", IPV6_TABLE_ERROR)})))
        self.assert_round_trip(hc.run_hostcheck(Stub({"E5-7": (1, "", IPV6_AF_ERROR)})))
        self.assert_round_trip(hc.run_hostcheck(Stub({"S0-b": (0, "elsewhere\n", "")})))

    def test_allowlist_has_a_schema_for_every_row(self) -> None:
        self.assertEqual(set(od1.HOSTCHECK_FACTS), set(hc.ROW_IDS))
        self.assertEqual(tuple(od1.HOSTCHECK_ROW_IDS), tuple(hc.ROW_IDS))

    def test_wrong_key_wrong_row_or_wrong_type_is_dropped(self) -> None:
        def kept(row: str, facts: dict) -> dict:
            out = od1.allow_hostcheck({"rows": [{"row": row, "outcome": "RECORDED", "rc": 0, "reason": "", "facts": facts}]})
            return out["rows"][0]["facts"]

        self.assertEqual(kept("E4-1", {"line_count": 1, "token": "abc"}), {"line_count": 1})
        self.assertEqual(kept("E4-1", {"backend": "nf_tables"}), {})
        self.assertEqual(kept("S0-d", {"backend": "nf_tables"}), {"backend": "nf_tables"})
        self.assertEqual(kept("S0-d", {"backend": "sk-abc"}), {})
        self.assertEqual(kept("E5-3", {"Result": "success", "ActiveState": "zz9"}), {"Result": "success"})
        self.assertEqual(kept("E4-3", {"checkin_nonempty_count": "1"}), {})
        self.assertEqual(kept("E4-3", {"checkin_nonempty_count": True}), {})
        self.assertEqual(kept("E5-11", {"word_state": "HELD", "word_detail": "x", "word_health": "a1"}), {"word_state": "HELD"})
        # N4: only listed boot-hold key names; has_ is true-only.
        self.assertEqual(
            kept("E5-11", {"has_message": True, "has_ready": False, "bool_host_wide_default_route_hold": False, "has_x": True, "bool_z": False}),
            {"has_message": True, "bool_host_wide_default_route_hold": False},
        )
        self.assertEqual(kept("E5-12", {"bool_signature": True, "signature_field_present": True}), {"signature_field_present": True})
        self.assertEqual(kept("E5-13", {"has_x": True}), {})
        self.assertEqual(kept("E5-7", {"ipv6_error_verbatim": IPV6_TABLE_ERROR}), {})


def _sparse_lists(text: str) -> dict[str, list[str]]:
    """Map each job in a workflow to its sparse-checkout list (text parse, no yaml)."""
    jobs: dict[str, list[str]] = {}
    job = None
    lines = text.splitlines()
    in_jobs = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip() == "jobs:":
            in_jobs = True
        elif in_jobs and len(line) > 2 and line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            job = line.strip()[:-1]
        elif job and line.strip() == "sparse-checkout: |":
            indent = len(line) - len(line.lstrip()) + 2
            entries = []
            i += 1
            while i < len(lines) and (len(lines[i]) - len(lines[i].lstrip())) >= indent and lines[i].strip():
                entries.append(lines[i].strip())
                i += 1
            jobs[job] = entries
            continue
        i += 1
    return jobs


def _job_text(text: str, job: str) -> str:
    out, keep = [], False
    for line in text.splitlines():
        if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            keep = line.strip()[:-1] == job
        if keep:
            out.append(line)
    return "\n".join(out)


def _covered(path: str, sparse: list[str]) -> bool:
    path = path.rstrip("/")
    for entry in sparse:
        e = entry.rstrip("/")
        # N7: exact entry, or an ancestor directory entry. A sparse entry BELOW
        # the path does not check the path out, so it does not count.
        if path == e or (entry.endswith("/") and path.startswith(e + "/")):
            return True
    return False


# F2: each exclusion strips ONLY its own token; the rest of the line is still scanned.
# - a PYTHONPATH value (an import root; the import test covers it)
# - the one path after an exact `test ! -e ` (asserts the path is absent)
# - the value of a `uses:` key (a third-party action ref), on `uses:` lines only
_EXCLUDED_TOKENS = (
    re.compile(r"PYTHONPATH(?::[ \t]*|=)[^\s\"';]+"),
    re.compile(r"\btest ! -e [^\s;&|]+"),
    re.compile(r"^(\s*-?\s*uses:[ \t]*)[^\s#]+(?:[ \t]+#.*)?$"),
)


def _strip_excluded_tokens(line: str) -> str:
    line = _EXCLUDED_TOKENS[0].sub("PYTHONPATH=", line)
    line = _EXCLUDED_TOKENS[1].sub("test ! -e", line)
    return _EXCLUDED_TOKENS[2].sub(r"\1", line)


REPO_PATH = __import__("re").compile(r"(?<![\w/.$@-])((?:scripts|packages|release)/[A-Za-z0-9_./-]+)")


class SparseCheckoutTests(LabEnvCase):
    """B-1: every repo file a sparse job copies, runs or sources is checked out."""

    WF = ROOT / ".github" / "workflows" / "gcp-lab-provision.yml"

    def test_staging_step_files_are_in_the_deliver_sparse_list(self) -> None:
        import re

        text = self.WF.read_text(encoding="utf-8")
        sparse = _sparse_lists(text)["deliver"]
        job = _job_text(text, "deliver")
        start = job.index("stage_lab_trust.py stage")
        block_start = job.rindex("run: |", 0, start)
        block_end = job.find("\n      - name:", start)
        block = job[block_start:block_end]
        wanted = set()
        for line in block.splitlines():
            line = line.strip()
            for pattern in (r"^cp (?:-a )?(\S+)", r"python3 (\S+\.py)", r"^(?:source|\.) (\S+)"):
                match = re.search(pattern, line)
                if match and REPO_PATH.fullmatch(match.group(1)):
                    wanted.add(match.group(1))
        self.assertIn("scripts/lab/hostcheck_rows.py", wanted)
        self.assertIn("scripts/lab/stage_lab_trust.py", wanted)
        self.assertIn("scripts/aws/lab-guests/self_service.py", wanted)
        self.assertIn("packages/vantio-install/vantio_install", wanted)
        for path in sorted(wanted):
            self.assertTrue(_covered(path, sparse), f"{path} missing from the deliver sparse list")

    def test_every_repo_path_in_every_sparse_job_is_checked_out(self) -> None:
        # N7: every workflow that has a sparse list, not just this one.
        wfs = sorted(p for p in (ROOT / ".github" / "workflows").glob("*.yml") if "sparse-checkout: |" in p.read_text(encoding="utf-8"))
        self.assertIn(self.WF, wfs)
        for wf in wfs:
            text = wf.read_text(encoding="utf-8")
            for job, sparse in _sparse_lists(text).items():
                body = _job_text(text, job)
                listed = set(sparse)
                scan_lines = [_strip_excluded_tokens(line) for line in body.splitlines()]
                for path in sorted(set(REPO_PATH.findall("\n".join(scan_lines)))):
                    if path in listed:
                        continue
                    self.assertTrue(_covered(path, sparse), f"{wf.name} {job}: {path} not in the sparse list")

    def test_runtime_imports_of_the_new_files_are_checked_out(self) -> None:
        import ast

        sparse = _sparse_lists(self.WF.read_text(encoding="utf-8"))["deliver"]
        local = {
            "hostcheck_rows": "scripts/lab/hostcheck_rows.py",
            "vantio_install": "packages/vantio-install/vantio_install/",
        }
        for path in ("scripts/lab/stage_lab_trust.py", "scripts/aws/lab-guests/self_service.py", "scripts/lab/hostcheck_rows.py"):
            tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names = [node.module.split(".")[0]]
                for name in names:
                    if name in local:
                        self.assertTrue(_covered(local[name], sparse), f"{path} imports {name}")
                    elif (ROOT / "scripts" / "lab" / f"{name}.py").exists() or (ROOT / "scripts" / "aws" / "lab-guests" / f"{name}.py").exists():
                        self.fail(f"{path} imports repo module {name}; add it to this test and the sparse list")


class SelfServiceHookTests(LabEnvCase):
    def test_hostcheck_runs_once_after_install_observe_and_before_later_phases(self) -> None:
        order: list[str] = []

        def invoke(argv, env):
            phase = argv[argv.index("--phase") + 1]
            order.append(f"invoke:{phase}:{'PROTECTED' if 'PROTECTED' in argv else 'OBSERVE'}")
            return {"state": "DEGRADED", "transaction_id": "tx-1", "reason": "OK"}

        def after(row):
            order.append(f"hostcheck:{row['phase']}:{row['protection']}")

        ss.run_installer(invoke, bundle="b", policy="p", signature="s", state_dir="d", config="c", after_install=after)
        hooks = [item for item in order if item.startswith("hostcheck")]
        self.assertEqual(hooks, ["hostcheck:install:OBSERVE"])
        self.assertEqual(order.index(hooks[0]), 1)
        self.assertEqual(len([item for item in order if item.startswith("invoke")]), 5)

    def test_no_hook_means_the_aws_path_is_unchanged(self) -> None:
        calls: list = []
        rows = ss.run_installer(lambda a, e: calls.append(a) or {"state": "FAILED_SAFE"}, bundle="b", policy="p", signature="s", state_dir="d", config="c")
        self.assertEqual(len(calls), 2)
        self.assertEqual([row["state"] for row in rows][2:], ["NOT_RUN"] * 3)
        with mock.patch.dict(ss.os.environ, {}, clear=True):
            self.assertFalse(ss.hostcheck_requested())
        with mock.patch.dict(ss.os.environ, {"VANTIO_LAB_HOSTCHECK": "1"}):
            self.assertTrue(ss.hostcheck_requested())

    def test_main_keeps_running_later_phases_when_the_host_check_faults(self) -> None:
        phases: list[str] = []

        def invoke(argv, env):
            phases.append(argv[argv.index("--phase") + 1])
            return {"state": "DEGRADED", "transaction_id": "tx-1"}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            ss.os.environ,
            {"VANTIO_LAB_HOSTCHECK": "1", "VANTIO_LAB_ROOT": tmp, "VANTIO_SELF_SERVICE_OUT": str(Path(tmp) / "rows.json")},
        ), mock.patch.object(ss, "_invoke_cli", invoke), mock.patch.object(ss, "install_offline_debs"), mock.patch.object(
            ss, "install_ca_bundle"
        ), mock.patch.object(ss, "write_observe_config"), mock.patch.object(ss, "enrollment_row", return_value={}), mock.patch.object(
            ss.subprocess, "run", side_effect=AssertionError("no host commands in tests")
        ), mock.patch.object(ss, "capture_hostcheck", side_effect=RuntimeError("boom")), mock.patch("builtins.print"):
            self.assertEqual(ss.main(), 0)
            record = json.loads((Path(tmp) / "rows.json").read_text(encoding="utf-8"))
        self.assertEqual(phases, ["install", "install", "rollback", "uninstall", "verify-removal"])
        self.assertEqual(record["hostcheck"]["summary"]["stopped_at"], "HOSTCHECK_ERROR")

    def test_s4_install_observe_must_be_healthy_or_degraded(self) -> None:
        ran: list = []
        for state in ("FAILED_SAFE", "BYTES_ABSENT", "", None):
            with self.subTest(state=state):
                got = ss.capture_hostcheck({"protection": "OBSERVE", "state": state}, run_checks=lambda: ran.append(1))
                self.assertEqual(got["summary"]["stopped_at"], "S4_INSTALL_NOT_OBSERVE_HEALTHY")
        self.assertEqual(ran, [])
        got = ss.capture_hostcheck({"protection": "PROTECTED", "state": "HEALTHY"}, run_checks=lambda: ran.append(1))
        self.assertEqual(got["summary"]["stopped_at"], "S4_INSTALL_NOT_OBSERVE_HEALTHY")
        for state in ("HEALTHY", "DEGRADED"):
            self.assertEqual(ss.capture_hostcheck({"protection": "OBSERVE", "state": state}, run_checks=lambda: {"rows": [], "summary": {}}), {"rows": [], "summary": {}})


def _slt_importable() -> bool:
    return importlib.util.find_spec("cryptography") is not None


@unittest.skipUnless(_slt_importable(), "cryptography not installed")
class StageLabTrustPinTests(LabEnvCase):
    def setUp(self) -> None:
        super().setUp()
        sys.path.insert(0, str(ROOT / "packages" / "vantio-install"))
        import stage_lab_trust

        self.slt = stage_lab_trust

    def test_public_pin_is_kept_under_the_pinned_name_only_when_the_hash_matches(self) -> None:
        pins = dict(self.slt.constants.FROZEN_PINS)
        payload = b"stand-in archive bytes for an offline test"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self.slt, "_run") as run:
            base = Path(tmp)
            source = base / "public-pin.oci.tar"
            source.write_bytes(payload)
            kept = self.slt.fetch_pinned(base / "wrong", source)
            self.assertEqual(kept, [])
            pins["pe_archive_sha256"] = hashlib.sha256(payload).hexdigest()
            with mock.patch.object(self.slt.constants, "FROZEN_PINS", pins):
                kept = self.slt.fetch_pinned(base / "right", source)
            self.assertEqual(kept, [pins["pe_archive_name"]])
            self.assertEqual((base / "right" / pins["pe_archive_name"]).read_bytes(), payload)
            self.assertEqual(list((base / "right" / ".fetch").iterdir()), [])
            self.assertEqual(self.slt.fetch_pinned(base / "none"), [])
            for call in run.call_args_list:
                self.assertIn(call.args[0][0], {"gh", "npm"})

    def test_cli_accepts_an_optional_public_pin(self) -> None:
        with mock.patch.object(self.slt, "fetch_pinned", return_value=[]) as fetch:
            self.assertEqual(self.slt.main(["fetch", "/tmp/x", "/tmp/pin.tar"]), 0)
            fetch.assert_called_with(Path("/tmp/x"), Path("/tmp/pin.tar"))
            self.assertEqual(self.slt.main(["fetch", "/tmp/x"]), 0)
            fetch.assert_called_with(Path("/tmp/x"), None)

    def test_check_archive_needs_the_pinned_archive_and_a_matching_signature(self) -> None:
        # B-8: positive check that archive_pin_match is True after stage.
        pins = dict(self.slt.constants.FROZEN_PINS)
        payload = b"stand-in archive bytes for check-archive"
        pins["pe_archive_sha256"] = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self.slt.constants, "FROZEN_PINS", pins):
            base = Path(tmp)
            empty = base / "empty"
            empty.mkdir()
            result = self.slt.stage(base / "absent", empty)
            self.assertIs(result["archive_pin_match"], False)
            with self.assertRaises(SystemExit):
                self.slt.check_archive(base / "absent")
            pinned = base / "pinned"
            pinned.mkdir()
            (pinned / pins["pe_archive_name"]).write_bytes(payload)
            result = self.slt.stage(base / "good", pinned)
            self.assertIs(result["archive_pin_match"], True)
            self.slt.pack(base / "good", base / "good" / "self-service.tar")
            self.assertEqual(self.slt.check_archive(base / "good"), {"archive_pin_match": True, "tar_member_pin_match": True})
            self.assertEqual(self.slt.main(["check-archive", str(base / "good")]), 0)
            signature = base / "good" / "signature.json"
            record = json.loads(signature.read_text())
            record["document"]["sha256"] = "0" * 64
            signature.write_text(json.dumps(record))
            with self.assertRaises(SystemExit):
                self.slt.check_archive(base / "good")



class PassThreeTests(LabEnvCase):
    """V5 notes N1..N7."""

    def run_s0b(self, printed: str, expected: object) -> dict:
        result = hc.run_hostcheck(Stub({"S0-b": (0, printed, "")}), expected_host=expected)
        return result

    def test_n2_exact_and_fqdn_match_pass(self) -> None:
        for printed in ("vantio-gcp-lab-12\n", "vantio-gcp-lab-12.us-central1-a.c.vantio-lab-oct08.internal\n", "vantio-gcp-lab-12.c.vantio-lab-oct08.internal"):
            result = self.run_s0b(printed, "vantio-gcp-lab-12")
            row = by_row(result)["S0-b"]
            self.assertEqual(row["outcome"], hc.RECORDED, printed)
            self.assertTrue(row["facts"]["host_name_match"])
            self.assertNotIn("internal", json.dumps(result))

    def test_n2_wrong_or_injectionish_names_stop(self) -> None:
        for printed in (
            "vantio-gcp-lab-13\n", "vantio-gcp-lab-123\n", "vantio-gcp-lab-12x\n", "xvantio-gcp-lab-12\n",
            "vantio-gcp-lab-12.\n", "vantio-gcp-lab-12..internal\n", "vantio-gcp-lab-12.Internal\n",
            "vantio-gcp-lab-12.a b\n", "vantio-gcp-lab-12.x;rm -rf /\n", "vantio-gcp-lab-12\nvantio-gcp-lab-12\n",
            "vantio-gcp-lab-12.*\n", "", "VANTIO-GCP-LAB-12\n",
        ):
            result = self.run_s0b(printed, "vantio-gcp-lab-12")
            row = by_row(result)["S0-b"]
            self.assertEqual((row["outcome"], row["reason"]), (hc.STOP, "NOT_A_LAB_HOST_NAME"), printed)
            self.assertEqual(result["summary"]["e5d_outcome"], hc.E5D_STOPPED)
            self.assertTrue(all(isinstance(v, bool) for v in row["facts"].values()))

    def test_n2_missing_or_malformed_expected_name_stops(self) -> None:
        for expected in ("", "vantio-gcp-lab-", "vantio-gcp-lab-12;id", "vantio-gcp-lab-12.internal", "other-12", "vantio-gcp-lab-*", 12):
            result = self.run_s0b("vantio-gcp-lab-12\n", expected)
            row = by_row(result)["S0-b"]
            self.assertEqual(row["reason"], "NOT_A_LAB_HOST_NAME", expected)
            self.assertFalse(row["facts"]["expected_name_valid"])
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(hc.EXPECTED_HOST_ENV, None)
            row = by_row(hc.run_hostcheck(Stub()))["S0-b"]
        self.assertEqual(row["reason"], "NOT_A_LAB_HOST_NAME")

    def test_f3_domain_is_pinned_to_the_lab_project_and_zone(self) -> None:
        ok = ("vantio-gcp-lab-12", "vantio-gcp-lab-12.us-central1-a.c.vantio-lab-oct08.internal", "vantio-gcp-lab-12.c.vantio-lab-oct08.internal")
        for printed in ok:
            row = by_row(hc.run_hostcheck(Stub({"S0-b": (0, printed + "\n", "")})))["S0-b"]
            self.assertEqual(row["outcome"], hc.RECORDED, printed)
        for printed in (
            "vantio-gcp-lab-12.internal", "vantio-gcp-lab-12.example.com",
            "vantio-gcp-lab-12.us-central1-b.c.vantio-lab-oct08.internal",
            "vantio-gcp-lab-12.c.vantio-lab-other.internal", "vantio-gcp-lab-12.c.vantio-lab-oct08.internal.evil",
        ):
            row = by_row(hc.run_hostcheck(Stub({"S0-b": (0, printed + "\n", "")})))["S0-b"]
            self.assertEqual((row["outcome"], row["reason"]), (hc.STOP, "NOT_A_LAB_HOST_NAME"), printed)
        for project, zone in (("", "us-central1-a"), ("vantio-lab-oct08", ""), ("evil.com", "us-central1-a"), ("vantio-lab-oct08", "a.b")):
            fqdn = by_row(hc.run_hostcheck(Stub({"S0-b": (0, f"vantio-gcp-lab-12.{zone}.c.{project}.internal\n", "")}), project=project, zone=zone))["S0-b"]
            self.assertEqual(fqdn["reason"], "NOT_A_LAB_HOST_NAME", (project, zone))
            self.assertFalse(fqdn["facts"]["expected_domain_valid"])
            short = by_row(hc.run_hostcheck(Stub(), project=project, zone=zone))["S0-b"]
            self.assertEqual(short["outcome"], hc.RECORDED)

    def test_f3_env_is_not_set_at_import(self) -> None:
        text = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?m)^os\.environ\[")
        offline = (ROOT / "scripts" / "gcp" / "offline_deliver_3.py").read_text(encoding="utf-8")
        self.assertIn('f"VANTIO_LAB_EXPECTED_PROJECT={project} "', offline)
        self.assertIn('f"VANTIO_LAB_EXPECTED_ZONE={ZONE} "', offline)
        self.assertEqual(od1.ZONE, "us-central1-a")
        self.assertIsNotNone(hc.LAB_PROJECT_RE.fullmatch(od1.LAB_PROJECT))

    def test_f2_exclusions_strip_only_their_token(self) -> None:
        cases = {
            "          PYTHONPATH=packages/vantio-install python3 scripts/x/run.py": ["scripts/x/run.py"],
            "          PYTHONPATH: packages/vantio-install": [],
            "          test ! -e packages/gone && cp scripts/y/keep.sh /tmp": ["scripts/y/keep.sh"],
            "          test -e packages/present": ["packages/present"],
            "          test !-e packages/loose": ["packages/loose"],
            "      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1": [],
            "          upload=scripts/z/up.py owner/name@dc37677b2e1c63e2034f94d8a5b11f265b73ba33": ["scripts/z/up.py"],
            "          echo gh-action-like scripts/w/also.py": ["scripts/w/also.py"],
        }
        for line, want in cases.items():
            self.assertEqual(REPO_PATH.findall(_strip_excluded_tokens(line)), want, line)

    def test_n2_offline_deliver_passes_the_instance_name(self) -> None:
        text = (ROOT / "scripts" / "gcp" / "offline_deliver_3.py").read_text(encoding="utf-8")
        self.assertIn('f"VANTIO_LAB_EXPECTED_HOST={name} "', text)
        self.assertIn('name = instance_name(env.get("GITHUB_RUN_ID", ""))', text)
        self.assertEqual(hc.EXPECTED_HOST_ENV, "VANTIO_LAB_EXPECTED_HOST")

    def test_n3_all_five_e5_3_keys_required(self) -> None:
        full = HEALTHY["E5-3"][1].splitlines()
        for drop in range(5):
            out = "\n".join(full[:drop] + full[drop + 1:]) + "\n"
            row = by_row(hc.run_hostcheck(Stub({"E5-3": (0, out, "")})))["E5-3"]
            self.assertEqual((row["outcome"], row["reason"]), (hc.STOP, "E5_3_KEYS_MISSING"))

    def test_n4_key_lists_and_reasons_match_the_allowlist_exactly(self) -> None:
        self.assertEqual({k: tuple(v) for k, v in hc.JSON_KEYS.items()}, od1.HOSTCHECK_JSON_KEYS)
        self.assertEqual(set(hc.JSON_WORD_KEYS), set(od1.HOSTCHECK_JSON_WORD_KEYS))
        self.assertEqual(hc.REASONS, od1.HOSTCHECK_REASONS)
        self.assertEqual(hc.E5D_OUTCOMES, od1.HOSTCHECK_E5D_OUTCOMES)
        self.assertEqual(hc.IPV6_STATES, od1.HOSTCHECK_IPV6_STATES)
        self.assertEqual(hc.argv_sha256(), od1.HOSTCHECK_ARGV_SHA256)
        self.assertTrue(set(hc.ROW_IDS) <= od1.HOSTCHECK_STOPPED_AT)

    def test_n4_key_lists_match_what_the_boot_hold_code_writes(self) -> None:
        sys.path.insert(0, str(ROOT / "packages" / "vantio-install"))
        from vantio_install.boot_hold import policy, service

        written = set(service.envelope("c", "s", "m"))
        self.assertTrue(written <= set(hc.JSON_KEYS["E5-11"]))
        self.assertTrue(set(policy.default_policy()) <= set(hc.JSON_KEYS["E5-12"]))

    def test_n4_unlisted_keys_counted_not_named(self) -> None:
        out = '{"network_hold": true, "released": false, "secret_name_x": 1, "other": "y"}'
        facts = by_row(hc.run_hostcheck(Stub({"E5-10": (0, out, "")})))["E5-10"]["facts"]
        self.assertEqual(facts["unlisted_key_count"], 2)
        self.assertNotIn("secret_name_x", json.dumps(facts))

    def test_n4_every_reason_the_harness_emits_is_allowed(self) -> None:
        cases = [{}, {"S0-b": (0, "elsewhere\n", "")}, {"E5-7": (3, "", IPV6_TABLE_ERROR)}, {"E5-10": (0, '{"released": true}', "")}]
        for case in cases:
            for row in hc.run_hostcheck(Stub(case))["rows"]:
                self.assertIn(row["reason"], hc.REASONS, row)
        kept = od1.allow_hostcheck({"rows": [{"row": "E4-1", "outcome": "STOP", "rc": 1, "reason": "MADE_UP", "facts": {}}]})
        self.assertNotIn("MADE_UP", json.dumps(kept))

    def test_n4_summary_values_exact(self) -> None:
        out = od1.allow_hostcheck({"rows": [], "summary": {"argv_sha256": "0" * 64, "e5d_outcome": "RECORDED", "ipv6": "READ", "stopped_at": "E9-9"}})
        self.assertEqual(out["summary"].get("ipv6"), "READ")
        for key in ("argv_sha256", "e5d_outcome", "stopped_at"):
            self.assertNotIn(key, out["summary"])

    def test_n6_stop_beats_ipv6_not_present(self) -> None:
        result = hc.run_hostcheck(Stub({"E5-7": (3, "", IPV6_TABLE_ERROR), "E5-10": (0, '{"released": true}', "")}))
        self.assertEqual(result["summary"]["ipv6"], "NOT_PRESENT")
        self.assertEqual(result["summary"]["e5d_outcome"], hc.E5D_STOPPED)

    def test_n1_staging_and_t5_compile_run_before_the_vm(self) -> None:
        text = (ROOT / ".github" / "workflows" / "gcp-lab-provision.yml").read_text(encoding="utf-8")
        job = _job_text(text, "deliver")
        vm = job.index("- name: Create the offline VM")
        for name in ("Stage the lab installer and a non-production trust key", "Compile the T5 loader"):
            self.assertLess(job.index(f"- name: {name}"), vm, name)
        self.assertLess(job.index("- name: Download the bundle, re-verify it, and delete it"), job.index("- name: Stage the lab installer"))
        for name in ("Copy the bundle over IAP", "Run the self-service installer", "Run the kernel red-team campaign", "Run the batteries", "Run t5-egress"):
            self.assertGreater(job.index(f"- name: {name}"), vm, name)



class TarMemberTests(LabEnvCase):
    """F1: every member the guest's `tar -xf` would write is checked."""

    PAYLOAD = b"stand-in archive bytes for the tar member tests"

    def setUp(self) -> None:
        super().setUp()
        sys.path.insert(0, str(ROOT / "packages" / "vantio-install"))
        import stage_lab_trust

        self.slt = stage_lab_trust
        self.pins = dict(stage_lab_trust.constants.FROZEN_PINS)
        self.pins["pe_archive_sha256"] = hashlib.sha256(self.PAYLOAD).hexdigest()
        self.record = {"document": {"sha256": self.pins["pe_archive_sha256"], "filename": self.pins["pe_archive_name"]}}
        self.member = f"bundle/artifacts/phantom-engine/{self.pins['pe_archive_name']}"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)

    def build(self, extra=(), member=None, payload=None) -> Path:
        import io
        import tarfile

        path = self.base / "t.tar"
        sig = json.dumps(self.record).encode()
        with tarfile.open(path, "w") as tar:
            def add(name, data=None, kind=tarfile.REGTYPE, link=""):
                info = tarfile.TarInfo(name)
                info.type = kind
                info.linkname = link
                if data is not None:
                    info.size = len(data)
                tar.addfile(info, io.BytesIO(data) if data is not None else None)
            add(member or self.member, self.PAYLOAD if payload is None else payload)
            add("signature.json", sig)
            for item in extra:
                add(*item)
        return path

    def check(self, path: Path) -> None:
        self.slt._check_tar_member(path, self.pins, self.record)

    def assert_rejected(self, path: Path) -> None:
        with self.assertRaises(SystemExit):
            self.check(path)

    def test_clean_tar_passes_and_member_spellings_normalise(self) -> None:
        self.check(self.build())
        self.check(self.build(member="./" + self.member))
        self.check(self.build(extra=[("bundle/", None, tarfile_type("DIRTYPE"))]))

    def test_alias_spellings_are_duplicates(self) -> None:
        m = self.member
        for alias in (m.replace("/", "//", 1), "./" + m, m.replace("artifacts/", "artifacts/./"), "./" + m.replace("/", "//"), m + "/"):
            self.assert_rejected(self.build(extra=[(alias, b"other bytes")]))
        self.assert_rejected(self.build(extra=[("./signature.json", b"{}")]))

    def test_exact_duplicate_overwriting_the_archive_path_is_rejected(self) -> None:
        self.assert_rejected(self.build(extra=[(self.member, b"later bytes win in tar -x")]))

    def test_symlink_hardlink_device_fifo_are_rejected(self) -> None:
        for kind in ("SYMTYPE", "LNKTYPE", "CHRTYPE", "BLKTYPE", "FIFOTYPE"):
            self.assert_rejected(self.build(extra=[("bundle/odd", None, tarfile_type(kind), "/etc/passwd")]))
            self.assert_rejected(self.build(member="other/x", extra=[(self.member, None, tarfile_type(kind), "other/x")]))

    def test_symlinked_or_file_parent_is_rejected(self) -> None:
        self.assert_rejected(self.build(extra=[("bundle/artifacts", None, tarfile_type("SYMTYPE"), "/tmp")]))
        self.assert_rejected(self.build(extra=[("bundle/artifacts", b"a file where a folder is")]))

    def test_absolute_dotdot_backslash_nul_empty_are_rejected(self) -> None:
        for name in ("/etc/x", "bundle/../../x", "..", "bundle\\x", ".", "./", "//"):
            self.assert_rejected(self.build(extra=[(name, b"x")]))
        # tar headers end a name at NUL (tarfile and GNU tar both truncate),
        # so a NUL cannot reach a member name; the normaliser still refuses one.
        for name in ("bundle/x\x00y", "", "a//", "a/./b"):
            if name in {"a//", "a/./b"}:
                self.assertEqual(self.slt._normal_member_name(name), name.replace("/./", "/").rstrip("/"))
            else:
                with self.assertRaises(SystemExit):
                    self.slt._normal_member_name(name)

    def test_wrong_bytes_or_missing_member_are_rejected(self) -> None:
        self.assert_rejected(self.build(payload=b"tampered"))
        self.assert_rejected(self.build(member="bundle/artifacts/phantom-engine/other.tar"))

    def test_pack_refuses_symlinks(self) -> None:
        tree = self.base / "tree"
        (tree / "real").mkdir(parents=True)
        (tree / "real" / "f.txt").write_text("x")
        (tree / "link").symlink_to(tree / "real")
        with self.assertRaises(SystemExit):
            self.slt.pack(tree, tree / "self-service.tar")


def tarfile_type(name: str) -> bytes:
    import tarfile

    return getattr(tarfile, name)


if __name__ == "__main__":
    unittest.main()
