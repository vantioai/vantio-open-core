#!/usr/bin/env python3
"""Offline tests for the H2 host checks and the F0-a public-pin fetch.

Stubs only. Nothing here runs docker, systemctl, iptables, gh, npm or any
network call.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
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


class ArgvListTests(unittest.TestCase):
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


class HealthyRunTests(unittest.TestCase):
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


class Q8Tests(unittest.TestCase):
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


class GateTests(unittest.TestCase):
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


class PassTwoHarnessTests(unittest.TestCase):
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
            self.assertEqual(rows["S0-b"]["facts"], {"lab_name_pattern": False})
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


class PassTwoAllowlistTests(unittest.TestCase):
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
        self.assertEqual(kept("E5-11", {"has_x": True, "has_y": False, "bool_z": False}), {"has_x": True, "bool_z": False})
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
        if path == e or (entry.endswith("/") and path.startswith(e + "/")) or e.startswith(path + "/"):
            return True
    return False


REPO_PATH = __import__("re").compile(r"(?<![\w/.$-])((?:scripts|packages|release)/[A-Za-z0-9_./-]+)")


class SparseCheckoutTests(unittest.TestCase):
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
        for wf in (self.WF,):
            text = wf.read_text(encoding="utf-8")
            for job, sparse in _sparse_lists(text).items():
                body = _job_text(text, job)
                listed = set(sparse)
                for path in sorted(set(REPO_PATH.findall(body))):
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


class SelfServiceHookTests(unittest.TestCase):
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
class StageLabTrustPinTests(unittest.TestCase):
    def setUp(self) -> None:
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
            self.assertEqual(self.slt.check_archive(base / "good"), {"archive_pin_match": True})
            self.assertEqual(self.slt.main(["check-archive", str(base / "good")]), 0)
            signature = base / "good" / "signature.json"
            record = json.loads(signature.read_text())
            record["document"]["sha256"] = "0" * 64
            signature.write_text(json.dumps(record))
            with self.assertRaises(SystemExit):
                self.slt.check_archive(base / "good")


if __name__ == "__main__":
    unittest.main()
