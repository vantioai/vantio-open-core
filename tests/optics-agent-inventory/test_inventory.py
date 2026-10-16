"""Inventory accuracy on fixture proc trees."""

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import support
from support import CANARY, ProcTree, enrollment, ipv4, tcp_row, write_json

from optics_agent_inventory.catalog import LLM_HOSTS
from optics_agent_inventory.inventory import ScanConfig, scan

CID = "a" * 64
OTHER = "b" * 64
PF_KTHREAD = 0x00200000


def _scan(tree: ProcTree, enrollment_path: Path | None, **kwargs):
    config = ScanConfig(
        proc_root=tree.proc,
        host_id=kwargs.pop("host_id", "lab-runner"),
        euid=kwargs.pop("euid", 1000),
        enrollment_path=enrollment_path,
        mountinfo_path=tree.mountinfo,
        endpoint_map_path=kwargs.pop("endpoint_map_path", None),
        runs_dir=kwargs.pop("runs_dir", None),
        extra_hosts=kwargs.pop("extra_hosts", ()),
    )
    return scan(config)


class InventoryFixtureTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.tree = ProcTree(self.root)
        self.enroll = self.root / "enrollment.json"

    def tearDown(self):
        subprocess.run(["sudo", "-n", "rm", "-rf", str(self.root)], check=False)
        try:
            self._tmp.cleanup()
        except OSError:
            pass

    def _enroll(self, containers, host_processes=False):
        write_json(self.enroll, enrollment(containers=containers, host_processes=host_processes))

    def test_catalog_matches_llm_hosts(self):
        text = (support.ROOT / "packages" / "vantio-cli" / "bin" / "llm-hosts.cjs").read_text(encoding="utf-8")
        start = text.index("const LLM_HOSTS = [")
        end = text.index("];", start)
        hosts = re.findall(r'"([^"]+)"', text[start:end])
        self.assertEqual(tuple(hosts), LLM_HOSTS)

    def test_covered_partial_unenrolled_unknown_and_decoys(self):
        url = f"https://user:{CANARY}@api.openai.com/v1/{CANARY}?q={CANARY}"
        self.tree.add(
            10,
            comm="python3",
            exe="python3",
            argv=["python3", url],
            cgroup=f"0::/docker-{CID}.scope\n",
            environ={"OPENAI_API_KEY": CANARY},
            hostname="vantio-t3-agent",
            sockets=["10"],
            tcp=tcp_row(ipv4("10.88.0.2", 40000), ipv4("10.88.0.2", 443), "01", "10"),
            hosts="10.88.0.2 api.openai.com\n",
        )
        self.tree.add(11, comm="sleep", exe="sleep", cgroup=f"0::/docker-{CID}.scope\n", ppid=1)
        self.tree.add(
            12,
            comm="claude",
            exe="claude",
            cgroup=f"0::/docker-{OTHER}.scope\n",
            omit_exe=True,
        )
        self.tree.deny(self.tree.proc / "12" / "fd")
        self.tree.add(13, comm="python3", exe="python3", cgroup="0::/user.slice/session.scope\n", environ={"OPENAI_API_KEY": CANARY})
        self.tree.add(14, comm="sleep", exe="sleep", argv=["sleep", CANARY, "api.openai.com-not-a-token"])
        write_json(self.enroll, enrollment(containers=[CID, OTHER], host_processes=True))
        # pid 13 is a host process and host_processes is true, so it is enrolled and unknown.
        # Make its fd readable (default) so the host cap comes from the unknown workload
        # and from pid 12's denied fd.
        report, code = _scan(self.tree, self.enroll)
        self.assertEqual(code, 0)
        self.assertFalse(report["content_stored"])
        self.assertNotIn(CANARY, json.dumps(report))
        by_role = {row["role"]: row for row in report["workloads"]}
        self.assertEqual(by_role["api_client"]["coverage"], "covered")
        self.assertEqual(by_role["api_client"]["where"]["container_name"], "vantio-t3-agent")
        self.assertEqual(by_role["api_client"]["observed_reach"][0]["host"], "api.openai.com")
        self.assertNotIn("path", json.dumps(by_role["api_client"]["observed_reach"]))
        self.assertIn("hold_provider_credential_name", by_role["api_client"]["can_do"])
        self.assertEqual(by_role["agent_runtime"]["coverage"], "partial")
        self.assertEqual(by_role["credential_only"]["coverage"], "unknown")
        self.assertNotIn("sleep", [row["role"] for row in report["workloads"]])
        self.assertEqual(report["host"]["coverage"], "unknown")
        self.assertIn("enrolled_workload_unknown", report["host"]["reasons"])

    def test_unenrolled_container_and_decoy_mcp_config(self):
        self.tree.add(20, comm="claude", exe="claude", cgroup=f"0::/docker-{OTHER}.scope\n")
        self.tree.add(
            21,
            comm="sleep",
            exe="sleep",
            cgroup=f"0::/docker-{CID}.scope\n",
            mcp_rel=".cursor/mcp.json",
            mcp_body={"mcpServers": {"files": {"command": "mcp-server-filesystem", "description": CANARY}}},
        )
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(len(report["workloads"]), 1)
        self.assertEqual(report["workloads"][0]["coverage"], "unenrolled")
        self.assertEqual(report["workloads"][0]["where"]["container_id"], OTHER)
        self.assertNotIn(CANARY, json.dumps(report))
        self.assertEqual(report["host"]["coverage"], "covered")
        self.assertNotIn("enrolled_workload_unknown", report["host"]["reasons"])

    def test_lineage_absorbs_child_and_socket_without_argv_host(self):
        self.tree.add(30, comm="claude", exe="claude", cgroup=f"0::/docker-{CID}.scope\n", ppid=1)
        self.tree.add(
            31,
            comm="python3",
            exe="python3",
            ppid=30,
            argv=["python3", "worker.py"],
            cgroup=f"0::/docker-{CID}.scope\n",
            sockets=["31"],
            tcp=tcp_row(ipv4("10.88.0.8", 40000), ipv4("10.88.0.8", 443), "01", "31"),
            hosts="10.88.0.8 api.anthropic.com\n",
        )
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(len(report["workloads"]), 1)
        row = report["workloads"][0]
        self.assertEqual(row["role"], "agent_runtime")
        self.assertEqual(row["coverage"], "covered")
        self.assertEqual(row["where"]["pids"], [30, 31])
        self.assertEqual(row["observed_reach"], [{"host": "api.anthropic.com", "port": 443, "provider": "anthropic", "source": "socket"}])
        self.assertIn("call_model_api", row["can_do"])

    def test_sibling_claude_rows_merge(self):
        self.tree.add(40, comm="claude", exe="claude", cgroup=f"0::/docker-{CID}.scope\n", ppid=1)
        self.tree.add(41, comm="claude", exe="claude", cgroup=f"0::/docker-{CID}.scope\n", ppid=1)
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(len(report["workloads"]), 1)
        self.assertEqual(report["workloads"][0]["where"]["pids"], [40, 41])

    def test_ambiguous_map_and_non_catalog_socket_are_dropped(self):
        self.tree.add(
            50,
            comm="python3",
            exe="python3",
            argv=["python3"],
            cgroup=f"0::/docker-{CID}.scope\n",
            sockets=["1", "2"],
            tcp=(
                tcp_row(ipv4("10.1.0.1", 1), ipv4("10.1.0.9", 443), "01", "1")
                + tcp_row(ipv4("10.1.0.1", 2), ipv4("10.9.9.9", 443), "01", "2")
            ),
            hosts="10.1.0.9 api.openai.com api.anthropic.com\n10.9.9.9 example.com\n",
        )
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(report["workloads"], [])
        self.assertNotIn("10.9.9.9", json.dumps(report))
        self.assertNotIn("example.com", json.dumps(report))

    def test_endpoint_map_disagreement_emits_nothing(self):
        self.tree.add(
            51,
            comm="python3",
            exe="python3",
            cgroup=f"0::/docker-{CID}.scope\n",
            sockets=["3"],
            tcp=tcp_row(ipv4("10.2.0.1", 1), ipv4("10.2.0.2", 443), "01", "3"),
            hosts="10.2.0.2 api.openai.com\n",
        )
        path = self.root / "map.json"
        write_json(
            path,
            {"schema": "vantio.optics.endpoint_map.v1", "map": [{"ip": "10.2.0.2", "host": "api.anthropic.com", "port": 443}]},
        )
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll, endpoint_map_path=path)
        self.assertEqual(report["workloads"], [])

    def test_run_log_does_not_create_identity_and_strips_path(self):
        self.tree.add(60, comm="sleep", exe="sleep", cgroup=f"0::/docker-{CID}.scope\n", start=5000)
        runs = self.root / "runs"
        runs.mkdir()
        write_json(
            runs / "old.json",
            {
                "vantio_run_log": "1",
                "pid": 60,
                "started_at": "2023-01-01T00:00:00Z",
                "generated_at": "2023-01-01T00:01:00Z",
                "path": CANARY,
                "error": CANARY,
                "calls": [{"hostname": "api.openai.com", "path": CANARY, "error": CANARY}],
            },
        )
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll, runs_dir=runs)
        self.assertEqual(report["workloads"], [])
        self.assertNotIn(CANARY, json.dumps(report))

    def test_run_log_annotates_a_live_recognized_pid(self):
        self.tree.add(
            61,
            comm="python3",
            exe="python3",
            argv=["python3", "https://api.openai.com/v1/models"],
            cgroup=f"0::/docker-{CID}.scope\n",
            start=100,
        )
        runs = self.root / "runs"
        runs.mkdir()
        # btime 1700000000 + 100/clk. Use a started_at comfortably after boot+start.
        write_json(
            runs / "live.json",
            {
                "vantio_run_log": "1",
                "pid": 61,
                "ppid": 999,
                "started_at": "2023-11-14T22:13:21Z",
                "generated_at": "2023-11-14T22:13:30Z",
                "path": f"/{CANARY}",
                "error": CANARY,
                "calls": [{"hostname": "api.anthropic.com", "path": CANARY}],
            },
        )
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll, runs_dir=runs)
        self.assertEqual(len(report["workloads"]), 1)
        sources = {item["source"] for item in report["workloads"][0]["observed_reach"]}
        self.assertIn("argv", sources)
        self.assertIn("run_log", sources)
        hosts = {item["host"] for item in report["workloads"][0]["observed_reach"]}
        self.assertIn("api.anthropic.com", hosts)
        self.assertNotIn(CANARY, json.dumps(report))
        self.assertNotIn("999", json.dumps(report["workloads"][0]["observed_reach"]))

    def test_hidepid_values_restrict_non_root(self):
        self.tree.add(70, comm="claude", exe="claude", cgroup=f"0::/docker-{CID}.scope\n")
        self._enroll([CID])
        for option in ("hidepid=invisible", "hidepid=ptraceable", "hidepid=2", "hidepid=4", "hidepid=noaccess"):
            self.tree.mountinfo.write_text(f"36 35 0:1 / /proc rw,{option} - proc proc rw\n", encoding="utf-8")
            report, _code = _scan(self.tree, self.enroll, euid=1000)
            self.assertEqual(report["host"]["coverage"], "unknown", option)
            self.assertIn("proc_restricted", report["host"]["reasons"])
        self.tree.mountinfo.write_text("36 35 0:1 / /proc rw,hidepid=1 - proc proc rw\n", encoding="utf-8")
        report, _code = _scan(self.tree, self.enroll, euid=1000)
        self.assertNotIn("proc_restricted", report["host"]["reasons"])
        report, _code = _scan(self.tree, self.enroll, euid=0)
        self.tree.mountinfo.write_text("36 35 0:1 / /proc rw,hidepid=ptraceable - proc proc rw\n", encoding="utf-8")
        report, _code = _scan(self.tree, self.enroll, euid=0)
        self.assertNotIn("proc_restricted", report["host"]["reasons"])

    def test_enrolled_unreadable_fd_caps_host_without_a_workload(self):
        proc = self.tree.add(80, comm="python3", exe="python3", cgroup=f"0::/docker-{CID}.scope\n")
        self.tree.deny(proc / "fd")
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(report["workloads"], [])
        self.assertEqual(report["host"]["coverage"], "partial")
        self.assertIn("enrolled_scope_unreadable", report["host"]["reasons"])

    def test_host_processes_and_kernel_thread(self):
        hidden = self.tree.add(81, comm="python3", exe="python3", cgroup="0::/user.slice/session.scope\n")
        self.tree.deny(hidden / "fd")
        kernel = self.tree.add(82, comm="ksoftirqd", exe="ksoftirqd", ppid=2, flags=PF_KTHREAD, cgroup="0::/user.slice/session.scope\n")
        self.tree.deny(kernel / "fd")
        self.tree.add(2, comm="kthreadd", exe="kthreadd", ppid=0, flags=PF_KTHREAD, cgroup="0::/user.slice/session.scope\n")
        self._enroll([], host_processes=True)
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(report["host"]["coverage"], "partial")
        self.assertIn("enrolled_scope_unreadable", report["host"]["reasons"])
        self.assertEqual(report["workloads"], [])

    def test_kernel_thread_alone_does_not_cap_host(self):
        self.tree.add(2, comm="kthreadd", exe="kthreadd", ppid=0, flags=PF_KTHREAD, cgroup="0::/user.slice/session.scope\n")
        child = self.tree.add(83, comm="kworker", exe="kworker", ppid=2, cgroup="0::/user.slice/session.scope\n")
        self.tree.deny(child / "fd")
        self._enroll([], host_processes=True)
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(report["host"]["coverage"], "covered")
        self.assertNotIn("enrolled_scope_unreadable", report["host"]["reasons"])

    def test_truncated_comm_matches(self):
        self.tree.add(90, comm="text-generation", exe="python3", cgroup=f"0::/docker-{CID}.scope\n")
        self.tree.add(91, comm="mcp-server-file", exe="node", cgroup=f"0::/docker-{CID}.scope\n")
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll)
        roles = sorted(row["role"] for row in report["workloads"])
        self.assertEqual(roles, ["local_model_server", "mcp_server"])
        self.assertTrue(all(row["coverage"] == "covered" for row in report["workloads"]))

    def test_short_container_id_is_rejected(self):
        self.tree.add(92, comm="claude", exe="claude")
        write_json(self.enroll, enrollment(containers=["a" * 12]))
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(report["host"]["coverage"], "unknown")
        self.assertIn("enrollment_schema", report["host"]["reasons"])

    def test_symlink_enrollment_is_refused(self):
        target = self.root / "real.json"
        write_json(target, enrollment(containers=[CID]))
        link = self.root / "link.json"
        link.symlink_to(target)
        self.tree.add(93, comm="claude", exe="claude", cgroup=f"0::/docker-{CID}.scope\n")
        report, _code = _scan(self.tree, link)
        self.assertEqual(report["host"]["coverage"], "unknown")
        self.assertIn("enrollment_symlink", report["host"]["reasons"])
        self.assertNotIn(CANARY, json.dumps(report))

    def test_mcp_env_and_headers_are_dropped(self):
        self.tree.add(
            94,
            comm="mcp-server-file",
            exe="mcp-server-filesystem",
            cgroup=f"0::/docker-{CID}.scope\n",
            mcp_rel="mcp.json",
            mcp_body={
                "mcpServers": {
                    "files": {
                        "command": "/usr/bin/mcp-server-filesystem",
                        "args": ["--readonly", CANARY, "/tmp/secret"],
                        "env": {"SECRET": CANARY},
                        "headers": {"Authorization": CANARY},
                        "description": CANARY,
                        "url": f"https://user:{CANARY}@api.openai.com/v1/{CANARY}?q={CANARY}",
                    }
                }
            },
        )
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll)
        blob = json.dumps(report)
        self.assertNotIn(CANARY, blob)
        self.assertNotIn("/tmp/secret", blob)
        row = report["workloads"][0]
        config = [item for item in row["mcp_servers"] if item["basis"] == "config"][0]
        self.assertEqual(config["command_basename"], "mcp-server-filesystem")
        self.assertEqual(config["args"], ["--readonly"])
        self.assertEqual(config["url_host"], "api.openai.com")
        self.assertNotIn("env", config)

    def test_interactive_client_is_unknown(self):
        self.tree.add(
            95,
            comm="curl",
            exe="curl",
            argv=["curl", "https://api.openai.com/v1/models"],
            cgroup=f"0::/docker-{CID}.scope\n",
        )
        self._enroll([CID])
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(report["workloads"][0]["coverage"], "unknown")
        self.assertEqual(report["workloads"][0]["role"], "api_client")

    def test_missing_container_marker_is_unenrolled(self):
        self.tree.add(96, comm="claude", exe="claude", cgroup="0::/kubepods/burstable/podx/crio-not64\n")
        self._enroll([], host_processes=True)
        report, _code = _scan(self.tree, self.enroll)
        self.assertEqual(report["workloads"][0]["coverage"], "unenrolled")
        self.assertEqual(report["workloads"][0]["signals"]["container"], "missing")
        self.assertEqual(report["host"]["coverage"], "covered")


if __name__ == "__main__":
    unittest.main()
