#!/usr/bin/env python3
"""GCP enterprise battery: product uninstall plus a polled removal census.

Run 6 (provision 39875015455) failed enterprise-2 with programs_not_removed.
guest_rows read bpftool right after the container exited, and the root cgroup
programs outlive the container until vantio-loader --uninstall. AWS already
runs that uninstall and then reads the census. GCP now does the same, and the
census polls until it is clean or times out. These tests do not call GCP.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
GUESTS = ROOT / "scripts/aws/lab-guests"
GCP_SHELL = ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh"
sys.path.insert(0, str(GUESTS))
import phase2_grade as grade  # noqa: E402
import product_uninstall_census as census  # noqa: E402

PID = 3363
ANCHOR = 6946
SHORT_DENY = "/opt/vantio-lab/ceiling/deny.txt"


def _census(clean: bool, programs: list[str] | None = None) -> dict[str, object]:
    listed = [] if clean else (programs or ["cgroup_skb_egress_enforce"])
    return census.removal_census(listed, [], "", 0)


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class PollCensusTest(unittest.TestCase):
    def test_a_clean_first_read_does_not_sleep(self) -> None:
        clock = _Clock()
        got = census.poll_census(lambda: _census(True), clock=clock.clock, sleep=clock.sleep)
        self.assertIs(got["verified_removed"], True)
        self.assertEqual(got["census_polls"], 1)
        self.assertEqual(got["census_waited_s"], 0.0)
        self.assertEqual(clock.sleeps, [])

    def test_it_reads_again_until_the_census_is_clean(self) -> None:
        clock = _Clock()
        reads = iter([_census(False), _census(False), _census(True)])
        got = census.poll_census(lambda: next(reads), clock=clock.clock, sleep=clock.sleep)
        self.assertIs(got["verified_removed"], True)
        self.assertEqual(got["loader_programs"], [])
        self.assertEqual(got["census_polls"], 3)
        self.assertEqual(clock.sleeps, [census.CENSUS_POLL_INTERVAL_S] * 2)

    def test_a_census_still_listed_at_the_timeout_is_not_removed(self) -> None:
        clock = _Clock()
        calls: list[int] = []

        def read() -> dict[str, object]:
            calls.append(1)
            return _census(False, ["kprobe_open_deny"])

        got = census.poll_census(read, timeout_s=3.5, interval_s=1.0, clock=clock.clock, sleep=clock.sleep)
        self.assertIs(got["verified_removed"], False)
        self.assertEqual(got["loader_programs"], ["kprobe_open_deny"])
        self.assertEqual(len(calls), got["census_polls"])
        self.assertEqual(got["census_polls"], 5)
        self.assertLessEqual(sum(clock.sleeps), 3.5)
        self.assertEqual(got["census_waited_s"], 3.5)

    def test_a_failed_bpftool_is_never_clean(self) -> None:
        clock = _Clock()
        got = census.poll_census(
            lambda: census.removal_census([], [], "", 2),
            timeout_s=2.0,
            clock=clock.clock,
            sleep=clock.sleep,
        )
        self.assertIs(got["verified_removed"], False)
        self.assertEqual(got["bpftool_rc"], 2)

    def test_the_default_read_is_the_real_census(self) -> None:
        clock = _Clock()
        with mock.patch.object(census, "read_census", return_value=_census(True)) as read:
            got = census.poll_census(clock=clock.clock, sleep=clock.sleep)
        read.assert_called_once_with()
        self.assertIs(got["verified_removed"], True)

    def test_the_bound_is_20_seconds_one_second_apart(self) -> None:
        self.assertEqual((census.CENSUS_POLL_TIMEOUT_S, census.CENSUS_POLL_INTERVAL_S), (20.0, 1.0))

    def test_the_default_timeout_stops_an_always_dirty_read_at_20_seconds(self) -> None:
        clock = _Clock()
        got = census.poll_census(lambda: _census(False), clock=clock.clock, sleep=clock.sleep)
        self.assertIs(got["verified_removed"], False)
        self.assertEqual(got["census_polls"], 21)
        self.assertEqual(got["census_waited_s"], 20.0)

    def test_main_records_the_polled_census_and_keeps_the_guest_read(self) -> None:
        reads = iter([_census(False), _census(True)])
        with tempfile.TemporaryDirectory() as tmp:
            rows = Path(tmp) / "rows.json"
            rows.write_text(json.dumps({"removal": _census(False)}), encoding="utf-8")
            with mock.patch.object(census, "read_census", side_effect=lambda: next(reads)), mock.patch.object(
                census.time, "sleep", lambda _s: None
            ):
                code = census.main(["census", "--record", str(rows), "--guest-rc", "0"])
            body = json.loads(rows.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertIs(body["removal"]["verified_removed"], True)
        self.assertEqual(body["removal"]["census_polls"], 2)
        self.assertIs(body["after_container_exit"]["verified_removed"], False)
        self.assertTrue(grade.census_fully_clean(body["removal"]))

    def test_main_fails_when_the_last_read_still_lists_a_program(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = Path(tmp) / "rows.json"
            rows.write_text("{}", encoding="utf-8")
            err = io.StringIO()
            with mock.patch.object(census, "poll_census", return_value=_census(False)), mock.patch.object(
                sys, "stderr", err
            ):
                code = census.main(["census", "--record", str(rows), "--guest-rc", "0"])
        self.assertEqual(code, 1)
        self.assertIn("programs_not_removed cgroup_skb_egress_enforce", err.getvalue())

    def test_main_polls_and_the_census_only_reads(self) -> None:
        source = (GUESTS / "product_uninstall_census.py").read_text(encoding="utf-8")
        main = source[source.index("def main(") :]
        self.assertIn("census = poll_census()", main)
        self.assertNotIn("read_census()", main)
        self.assertNotIn("cgroup detach", source)
        self.assertNotIn("PROG_DETACH", source)
        self.assertNotIn(".unlink(", source)


class GcpEnterpriseUninstallTest(unittest.TestCase):
    def _final(self) -> str:
        text = GCP_SHELL.read_text(encoding="utf-8")
        return text[text.rindex("# A user-owned file in /tmp makes root's recreate return EACCES.") :]

    def test_enterprise_runs_the_product_uninstall_then_the_polled_census(self) -> None:
        final = self._final()
        rows = final.index('python3 "$stage/guest_rows.py" "$stage"')
        uninstall = final.index('if ! authorized_uninstall "$image" no 0; then')
        read = final.index(
            'python3 "$here/product_uninstall_census.py" --record /tmp/enterprise-pe-rows.json --guest-rc "$rc"'
        )
        stamp = final.index("stamp_host_evidence")
        durable = final.index("sudo cp -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json")
        self.assertLess(rows, uninstall)
        self.assertLess(uninstall, read)
        self.assertLess(read, stamp)
        self.assertLess(read, durable)
        self.assertEqual(final.count("authorized_uninstall"), 1)
        self.assertNotIn("bpftool cgroup detach", GCP_SHELL.read_text(encoding="utf-8"))

    def test_the_census_reaches_the_gcp_guest(self) -> None:
        stage = (ROOT / "scripts/gcp/offline_deliver_2.py").read_text(encoding="utf-8")
        self.assertIn('shutil.copy2(guest_dir / "product_uninstall_census.py", dest / "product_uninstall_census.py")', stage)
        self.assertIn('shutil.copy2(guest_dir / "sticky_write.py", dest / "sticky_write.py")', stage)
        deliver = (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8")
        self.assertIn('payload_dir / "product_uninstall_census.py",', deliver)

    def _decide(self, uninstall_rc: int, census_rc: int, guest_rc: int) -> tuple[int, list[str]]:
        final = self._final()
        start = final.index("set -e\n# AWS parity:")
        block = final[start + len("set -e\n") : final.index("sudo chmod a+r /tmp/enterprise-pe-rows.json")]
        script = (
            "set -u\n"
            f"rc={guest_rc}\nimage=img\nhere=/h\n"
            f'authorized_uninstall() {{ echo "uninstall $*" >>"$LOG"; return {uninstall_rc}; }}\n'
            f'sudo() {{ echo "sudo $*" >>"$LOG"; return {census_rc}; }}\n'
            + block
            + 'echo "rc=$rc"\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log"
            log.write_text("", encoding="utf-8")
            done = subprocess.run(
                ["bash", "-c", script], capture_output=True, text=True, env={**os.environ, "LOG": str(log)}, check=True
            )
            calls = log.read_text(encoding="utf-8").splitlines()
        return int(done.stdout.strip().rsplit("rc=", 1)[1]), calls

    def test_the_battery_code_is_the_census_code(self) -> None:
        rc, calls = self._decide(0, 0, 1)
        self.assertEqual(rc, 0)
        self.assertEqual(calls[0], "uninstall img no 0")
        self.assertIn("--guest-rc 1", calls[1])
        rc, _ = self._decide(0, 1, 0)
        self.assertEqual(rc, 1)

    def test_a_failed_uninstall_skips_the_census_and_fails(self) -> None:
        rc, calls = self._decide(1, 0, 0)
        self.assertEqual(rc, 1)
        self.assertEqual(calls, ["uninstall img no 0"])

    def _post_kill(
        self,
        ledger: bytes,
        before: int | str,
        want: int,
        events_data: bytes = b"",
        events_before: int | str = 0,
    ) -> subprocess.CompletedProcess[str]:
        text = GCP_SHELL.read_text(encoding="utf-8")
        body = text[text.index("authorized_uninstall() {") :]
        start = body.index("<<'PY'\n", body.index('if [ "$require_row" = "yes" ]; then')) + len("<<'PY'\n")
        program = body[start : body.index("\nPY\n", start)]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "uninstall.out"
            out.write_text("UNINSTALL_VERIFIED\n", encoding="utf-8")
            led = Path(tmp) / "uninstall.ndjson"
            led.write_bytes(ledger)
            events = Path(tmp) / "events.ndjson"
            events.write_bytes(events_data)
            return subprocess.run(
                [
                    sys.executable,
                    "-c",
                    program,
                    str(want),
                    str(before),
                    str(events_before),
                    str(out),
                    str(led),
                    str(events),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_post_kill_check_reads_only_this_uninstalls_ledger_rows(self) -> None:
        row = {"source": "deny_attr_post_kill", "ActionTaken": "DENIED", "Pid": PID, "lineage_anchor": ANCHOR}
        old = (json.dumps(row) + "\n").encode()
        stale = self._post_kill(old, len(old), PID)
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("post_kill_row_missing", stale.stderr)
        fresh = self._post_kill(old + old, len(old), PID)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertIn(f"deny_attr_post_kill pid {PID} anchor {ANCHOR}", fresh.stdout)
        # A ledger shorter than the recorded size was replaced; read all of it.
        shrunk = self._post_kill(old, len(old) + 50, PID)
        self.assertEqual(shrunk.returncode, 0, shrunk.stderr)

    def test_post_kill_check_reads_only_this_uninstalls_event_rows(self) -> None:
        row = {"source": "deny_attr_post_kill", "ActionTaken": "DENIED", "Pid": PID, "lineage_anchor": ANCHOR}
        old = (json.dumps(row) + "\n").encode()
        stale = self._post_kill(b"", 0, PID, old, len(old))
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("post_kill_row_missing", stale.stderr)
        fresh = self._post_kill(b"", 0, PID, old + old, len(old))
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertIn(f"deny_attr_post_kill pid {PID} anchor {ANCHOR}", fresh.stdout)
        shrunk = self._post_kill(b"", 0, PID, old, len(old) + 50)
        self.assertEqual(shrunk.returncode, 0, shrunk.stderr)

    def test_post_kill_check_refuses_a_missing_probe_pid(self) -> None:
        row = {"source": "deny_attr_post_kill", "ActionTaken": "DENIED", "Pid": PID, "lineage_anchor": ANCHOR}
        line = (json.dumps(row) + "\n").encode()
        for want in (0, -1):
            done = self._post_kill(line, 0, want, line, 0)
            self.assertNotEqual(done.returncode, 0, want)
            self.assertIn("post_kill_probe_pid_missing", done.stderr)
            self.assertNotIn("deny_attr_post_kill pid", done.stdout)

    def test_2d_marks_find_a_row_written_before_the_uninstall(self) -> None:
        # PR 368 council D1: the 2C cycle drains the probe's row into events.ndjson
        # (loader start) or uninstall.ndjson (2C uninstall) before the final
        # uninstall. With the pre-kill mark passed, that row is read.
        row = {"source": "deny_attr_post_kill", "ActionTaken": "DENIED", "Pid": PID, "lineage_anchor": ANCHOR}
        line = (json.dumps(row) + "\n").encode()
        other = (json.dumps(dict(row, Pid=PID + 1)) + "\n").encode()
        before_kill = other
        after_2c = before_kill + line + other
        # In events.ndjson: mark before the kill finds it; the uninstall-time size would not.
        marked = self._post_kill(b"", 0, PID, after_2c, len(before_kill))
        self.assertEqual(marked.returncode, 0, marked.stderr)
        self.assertIn(f"deny_attr_post_kill pid {PID} anchor {ANCHOR}", marked.stdout)
        late = self._post_kill(b"", 0, PID, after_2c, len(after_2c))
        self.assertNotEqual(late.returncode, 0)
        # Same in the uninstall ledger.
        marked = self._post_kill(after_2c, len(before_kill), PID)
        self.assertEqual(marked.returncode, 0, marked.stderr)
        # A row for this pid from before the mark is still excluded.
        stale = self._post_kill(b"", 0, PID, line + other, len(line))
        self.assertNotEqual(stale.returncode, 0)

    def test_2d_marks_replace_the_uninstall_time_sizes_only_when_numeric(self) -> None:
        text = GCP_SHELL.read_text(encoding="utf-8")
        body = text[text.index("authorized_uninstall() {") : text.index("normalize_loaded_image() {")]
        self.assertIn('local events_mark="${4:-}" ledger_mark="${5:-}"', body)
        events_case = "case \"$events_mark\" in ''|*[!0-9]*) ;; *) events_before=$events_mark ;; esac"
        ledger_case = "case \"$ledger_mark\" in ''|*[!0-9]*) ;; *) ledger_before=$ledger_mark ;; esac"
        self.assertIn(events_case, body)
        self.assertIn(ledger_case, body)
        stat = body.index("events_before=$(sudo stat -c %s /var/lib/vantio-pe-clean-host/evidence/events.ndjson")
        self.assertLess(body.index("ledger_before=$(sudo stat"), body.index(ledger_case))
        self.assertLess(stat, body.index(events_case))
        self.assertLess(body.index(ledger_case), body.index('python3 - "$probe_pid" "$ledger_before" "$events_before"'))
        self.assertIn(
            'authorized_uninstall "$image" "${VANTIO_REQUIRE_POST_KILL:-yes}" "${VANTIO_PROBE_PID:-0}" '
            '"${VANTIO_EVENTS_BEFORE:-}" "${VANTIO_LEDGER_BEFORE:-}"',
            text,
        )
        # The enterprise battery passes no marks and keeps the uninstall-time sizes.
        self.assertIn('if ! authorized_uninstall "$image" no 0; then', text)
        for mark, expect in (("", "77"), ("12", "12"), ("1x", "77"), ("-3", "77")):
            done = subprocess.run(
                ["bash", "-c", 'events_before=77; events_mark="$1"; ' + events_case + '; printf %s "$events_before"', "_", mark],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(done.stdout, expect, mark)

    def test_the_events_size_is_taken_before_the_loader_uninstall(self) -> None:
        text = GCP_SHELL.read_text(encoding="utf-8")
        body = text[text.index("authorized_uninstall() {") : text.index("normalize_loaded_image() {")]
        self.assertLess(
            body.index("events_before=$(sudo stat -c %s /var/lib/vantio-pe-clean-host/evidence/events.ndjson"),
            body.index("/var/lib/vantio/vantio-loader --uninstall"),
        )

    def test_a_failed_loader_create_or_copy_stops_the_uninstall(self) -> None:
        text = GCP_SHELL.read_text(encoding="utf-8")
        body = text[text.index("authorized_uninstall() {") : text.index("normalize_loaded_image() {")]
        self.assertIn(
            'cid=$(sudo docker create "$image") || { echo "UNINSTALL_NOT_VERIFIED loader_create" | '
            "tee -a /var/lib/vantio-lab/vantio-uninstall.out >&2; return 1; }",
            body,
        )
        self.assertIn(
            '/var/lib/vantio/vantio-loader || { echo "UNINSTALL_NOT_VERIFIED loader_copy" | '
            'tee -a /var/lib/vantio-lab/vantio-uninstall.out >&2; sudo docker rm "$cid" >/dev/null 2>&1; return 1; }',
            body,
        )
        self.assertLess(body.index("loader_copy"), body.index("/var/lib/vantio/vantio-loader --uninstall"))

    def test_the_ledger_size_is_taken_before_the_loader_uninstall(self) -> None:
        text = GCP_SHELL.read_text(encoding="utf-8")
        body = text[text.index("authorized_uninstall() {") : text.index("normalize_loaded_image() {")]
        self.assertLess(
            body.index("ledger_before=$(sudo stat -c %s /var/log/vantio/uninstall.ndjson"),
            body.index("/var/lib/vantio/vantio-loader --uninstall"),
        )
        self.assertIn(
            'python3 - "$probe_pid" "$ledger_before" "$events_before" /var/lib/vantio-lab/vantio-uninstall.out '
            "/var/log/vantio/uninstall.ndjson /var/lib/vantio-pe-clean-host/evidence/events.ndjson",
            body,
        )

    def _size_reads(
        self, exists: set, stat_rc: int = 0, sudo_rc: int = 0, sudo_fail: str = ""
    ) -> tuple[str, str]:
        """Run the real uninstall-time size reads under a fake sudo; return (ledger, events).

        A non-zero sudo_rc breaks every sudo call; sudo_fail breaks only calls naming that path.
        """
        text = GCP_SHELL.read_text(encoding="utf-8")
        body = text[text.index("authorized_uninstall() {") : text.index("normalize_loaded_image() {")]
        lines = [
            line.strip()
            for line in body.splitlines()
            if line.strip().startswith(("ledger_before=$(sudo stat", "events_before=$(sudo stat"))
        ]
        self.assertEqual(len(lines), 2)
        with tempfile.TemporaryDirectory() as tmp:
            sudo = Path(tmp) / "sudo"
            sudo.write_text(
                "#!/bin/bash\n"
                '[ "$SUDO_RC" = 0 ] || { echo "sudo: failed" >&2; exit "$SUDO_RC"; }\n'
                'if [ -n "$SUDO_FAIL" ]; then case " $* " in *" $SUDO_FAIL "*) exit 1 ;; esac; fi\n'
                'if [ "$1" = test ]; then\n'
                '  neg=0; [ "$2" = "!" ] && { neg=1; shift; }\n'
                '  [ "$2" = -e ] || exit 98\n'
                '  case " $EXISTS " in *" $3 "*) hit=1 ;; *) hit=0 ;; esac\n'
                '  [ "$hit" != "$neg" ] && exit 0; exit 1\n'
                "fi\n"
                'if [ "$1" = stat ]; then\n'
                '  case " $EXISTS " in *" $4 "*) ;; *) echo "stat: no such file" >&2; exit 1 ;; esac\n'
                '  [ "$STAT_RC" = 0 ] && { echo 123; exit 0; }; echo "stat: failed" >&2; exit "$STAT_RC"\n'
                "fi\n"
                "exit 99\n",
                encoding="utf-8",
            )
            sudo.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{tmp}:{os.environ['PATH']}",
                "STAT_RC": str(stat_rc),
                "SUDO_RC": str(sudo_rc),
                "SUDO_FAIL": sudo_fail,
                "EXISTS": " ".join(sorted(exists)),
            }
            done = subprocess.run(
                ["bash", "-c", "\n".join(lines) + '\nprintf "%s|%s" "$ledger_before" "$events_before"'],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
        ledger, events = done.stdout.split("|")
        return ledger, events

    def test_the_uninstall_time_size_reads_print_0_only_for_a_missing_file(self) -> None:
        # PR 368 council delta-4 N1: a failed stat or sudo is empty, never 0.
        ledger = "/var/log/vantio/uninstall.ndjson"
        events = "/var/lib/vantio-pe-clean-host/evidence/events.ndjson"
        self.assertEqual(self._size_reads({ledger, events}), ("123", "123"))
        self.assertEqual(self._size_reads({ledger}), ("123", "0"))
        self.assertEqual(self._size_reads(set()), ("0", "0"))
        self.assertEqual(self._size_reads({ledger, events}, stat_rc=1), ("", ""))
        self.assertEqual(self._size_reads({events}, stat_rc=1), ("0", ""))
        for exists in ({ledger, events}, {ledger}, set()):
            self.assertEqual(self._size_reads(exists, sudo_rc=1), ("", ""), sorted(exists))

    def test_post_kill_check_refuses_unreadable_offsets(self) -> None:
        row = {"source": "deny_attr_post_kill", "ActionTaken": "DENIED", "Pid": PID, "lineage_anchor": ANCHOR}
        old = (json.dumps(row) + "\n").encode()
        for before, events_before in (("", len(old)), (len(old), ""), ("", ""), ("x1", len(old))):
            done = self._post_kill(old, before, PID, old, events_before)
            self.assertNotEqual(done.returncode, 0, (before, events_before))
            self.assertIn("post_kill_offsets_unreadable", done.stderr, (before, events_before))
            self.assertNotIn("deny_attr_post_kill pid", done.stdout, (before, events_before))

    def test_a_sudo_failure_fails_the_2f_post_kill_check_closed(self) -> None:
        # 2F passes no marks, so the uninstall-time sizes are the offsets.
        ledger = "/var/log/vantio/uninstall.ndjson"
        events = "/var/lib/vantio-pe-clean-host/evidence/events.ndjson"
        row = {"source": "deny_attr_post_kill", "ActionTaken": "DENIED", "Pid": PID, "lineage_anchor": ANCHOR}
        stale = (json.dumps(row) + "\n").encode()
        for exists in ({ledger, events}, {ledger}, {events}, set()):
            before, events_before = self._size_reads(exists, sudo_rc=1)
            done = self._post_kill(stale, before, PID, stale, events_before)
            self.assertNotEqual(done.returncode, 0, sorted(exists))
            self.assertIn("post_kill_offsets_unreadable", done.stderr, sorted(exists))
            self.assertNotIn("deny_attr_post_kill pid", done.stdout, sorted(exists))
        # sudo fails only on one file's reads; the stale row sits in that file.
        for broken in (ledger, events):
            before, events_before = self._size_reads({ledger, events}, sudo_fail=broken)
            done = self._post_kill(
                stale if broken == ledger else b"", before, PID, stale if broken == events else b"", events_before
            )
            self.assertNotEqual(done.returncode, 0, broken)
            self.assertIn("post_kill_offsets_unreadable", done.stderr, broken)
            self.assertNotIn("deny_attr_post_kill pid", done.stdout, broken)
        # With sudo working and both files absent, every byte is new: the row counts.
        before, events_before = self._size_reads(set())
        fresh = self._post_kill(stale, before, PID, b"", events_before)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertIn(f"deny_attr_post_kill pid {PID} anchor {ANCHOR}", fresh.stdout)


class DenyRowsSkipPostKillTest(unittest.TestCase):
    """Ruling 3: a post-kill drain row is not a live deny row, even on a short path."""

    def _ns(self, found: list, deny: str) -> dict:
        text = (GUESTS / "phase2_host.py").read_text(encoding="utf-8")
        source = text[text.index("def _deny_rows") : text.index("def deny_event_for")]
        ns = {
            "events": lambda: [dict(item) for item in found],
            "rows": types.SimpleNamespace(DENY=Path(deny)),
            "EVENT_TIME_KEYS": ("Timestamp",),
        }
        exec(compile("from __future__ import annotations\n" + source, str(GUESTS / "phase2_host.py"), "exec"), ns)
        return ns

    def test_post_kill_rows_are_skipped(self) -> None:
        self.assertLessEqual(len(SHORT_DENY.encode()), grade.DENY_PATH_KEY_LEN)
        base = {"Pid": PID, "ActionTaken": "DENIED", "lineage_anchor": ANCHOR, "Payload": SHORT_DENY}
        found = [
            dict(base, Timestamp="2026-10-22T01:00:00.000Z"),
            dict(base, source="deny_attr_post_kill", Timestamp="2026-10-22T01:00:05.000Z"),
            dict(base, source="deny_attr_flush"),
        ]
        ns = self._ns(found, SHORT_DENY)
        got = ns["_deny_rows"](PID, with_time=True)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["ledger_ts"], "2026-10-22T01:00:00.000Z")
        self.assertNotIn("2026-10-22T01:00:05.000Z", [row.get("ledger_ts") for row in got])

    def test_only_post_kill_rows_are_skipped(self) -> None:
        base = {"Pid": PID, "ActionTaken": "DENIED", "lineage_anchor": ANCHOR, "PathAttempted": SHORT_DENY}
        ns = self._ns([dict(base, source="deny_attr_post_kill")], SHORT_DENY)
        self.assertEqual(ns["_deny_rows"](PID), [])
        ns = self._ns([dict(base, source="ledger")], SHORT_DENY)
        self.assertEqual(len(ns["_deny_rows"](PID)), 1)


class StopAfterMinutesGuardTest(unittest.TestCase):
    """PR 367 council: batteries with stop_after_minutes under 90 are refused before any spend."""

    WORKFLOW = ROOT / ".github/workflows/gcp-lab-provision.yml"

    def _guards(self) -> list[str]:
        text = self.WORKFLOW.read_text(encoding="utf-8")
        out = []
        start = 0
        while True:
            at = text.find("          # The phases after the batteries", start)
            if at < 0:
                return out
            end = text.index("\n          fi\n", text.index("-lt 90", at)) + len("\n          fi\n")
            out.append(text[at:end])
            start = end

    def test_both_validation_steps_refuse_and_read_the_input_from_env(self) -> None:
        text = self.WORKFLOW.read_text(encoding="utf-8")
        guards = self._guards()
        self.assertEqual(len(guards), 2)
        self.assertEqual(guards[0], guards[1])
        for guard in guards:
            self.assertNotIn("inputs.stop_after_minutes", guard)
        steps = text.split("      - name: Require main on vantio-open-core\n")
        guarded = [step for step in steps[1:] if "-lt 90" in step.split("\n      - name:", 1)[0]]
        self.assertEqual(len(guarded), 2)
        for step in guarded:
            self.assertTrue(step.startswith("        env:\n          STOP_AFTER_MINUTES: ${{ inputs.stop_after_minutes }}\n"))
        # The first guard is in the fetch job, before any bucket or VM step.
        fetch = text.index("  fetch:\n")
        self.assertLess(fetch, text.index(guards[0]))
        self.assertLess(text.index(guards[0]), text.index("\n  gate:\n"))
        self.assertLess(text.index("\n  deliver:\n"), text.rindex(guards[1]))

    def _run(self, batteries: str, minutes: str) -> int:
        guard = self._guards()[0].replace("${{ inputs.run_batteries }}", batteries)
        done = subprocess.run(
            ["bash", "-c", "set -euo pipefail\n" + guard],
            capture_output=True,
            text=True,
            env={**os.environ, "STOP_AFTER_MINUTES": minutes},
            check=False,
        )
        return done.returncode

    def test_the_guard(self) -> None:
        for minutes, code in (("105", 0), ("90", 0), ("100", 0), ("089", 1), ("89", 1), ("60", 1), ("", 1), ("9x", 1), ("-5", 1), ("08", 1), ("0100", 0), ("0090", 0)):
            self.assertEqual(self._run("true", minutes), code, minutes)
        for minutes in ("60", "", "abc"):
            self.assertEqual(self._run("false", minutes), 0, minutes)


class PhaseRemovalCensusPollTest(unittest.TestCase):
    """PR 368 council N2: the phase-level census polls like the battery census."""

    def test_phase_census_polls_the_single_read(self) -> None:
        text = (GUESTS / "phase2_host.py").read_text(encoding="utf-8")
        wrapper = text[text.index("def _removal_census() -> dict:") : text.index("def _removal_census_once() -> dict:")]
        self.assertIn("return census.poll_census(_removal_census_once)", wrapper)
        once = text[text.index("def _removal_census_once() -> dict:") :]
        once = once[: once.index("\ndef ")]
        self.assertNotIn("poll_census", once)
        self.assertNotIn("cgroup detach", once)
        self.assertEqual(text.count("removed = _removal_census()"), 2)


class RunnerSideTest(unittest.TestCase):
    """Council notes on PR 368: runner-side checks that need no GCP."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT / "scripts/gcp"))
        import offline_deliver as od  # noqa: E402

        cls.od = od

    def test_guest_json_missing_when_guest_rows_wrote_nothing(self) -> None:
        reasons = self.od._enterprise_fail_reasons
        self.assertEqual(reasons(None), ["guest_json_missing"])
        self.assertEqual(reasons({}), ["guest_json_missing"])
        self.assertEqual(reasons({"uninstall_tail": "x", "removal": _census(True)}), ["guest_json_missing"])
        self.assertNotIn("guest_json_missing", reasons({"grant_loader": {"rc": 1}}))

    def test_run_batteries_lets_90_and_120_past_the_floor(self) -> None:
        class Reached(Exception):
            pass

        for minutes in ("90", "120", "105"):
            with mock.patch.object(self.od, "_enabled", side_effect=Reached):
                with self.assertRaises(Reached):
                    self.od.run_batteries({"STOP_AFTER_MINUTES": minutes})

    def test_run_batteries_refuses_less_than_90_minutes(self) -> None:
        for minutes in ("", "60", "89", "abc", "0"):
            with mock.patch.object(self.od, "_enabled", side_effect=AssertionError("floor not first")):
                with self.assertRaises(SystemExit) as caught:
                    self.od.run_batteries({"STOP_AFTER_MINUTES": minutes})
            self.assertEqual(str(caught.exception), "stop_after_minutes", minutes)

    def test_2d_asks_for_a_post_kill_row_only_with_a_probe_pid(self) -> None:
        source = (ROOT / "scripts/gcp/offline_deliver_3.py").read_text(encoding="utf-8")
        self.assertIn('require_post_kill = "yes" if probe_pid > 0 and post_kill_marks is not None else "no"', source)
        self.assertIn('f"VANTIO_REQUIRE_POST_KILL={require_post_kill} VANTIO_PROBE_PID={probe_pid} "', source)
        self.assertNotIn('"VANTIO_REQUIRE_POST_KILL=yes VANTIO_PROBE_PID={probe_pid} "', source)
        self.assertIn(
            'post_kill_row = probe_pid > 0 and post_kill_marks is not None and "deny_attr_post_kill pid " in uninstall_text',
            source,
        )
        self.assertLess(source.index("post_kill_marks = ("), source.index('kill = _loader_case(project, name, seal, "2d-crash-recovery")'))


if __name__ == "__main__":
    unittest.main()
