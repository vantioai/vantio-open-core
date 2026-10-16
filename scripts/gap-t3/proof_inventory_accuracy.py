"""Seed Linux containers and score Optics agent-inventory precision and recall.

Label: lab-only. The population is the seeded containers. Runtime preference
is docker, then podman, then a private namespace plus a docker-shaped cgroup.
This runner uses the namespace runtime when no daemon is installed.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "packages" / "optics-agent-inventory" / "src"
PAYLOAD = Path(__file__).resolve().parent / "payload.py"
EVIDENCE = ROOT / "docs" / "planning" / "gap-t3-optics-inventory" / "evidence" / "inventory-accuracy.json"
CANARY = "CANARYPROMPTT39F3C2A"
HOST_ID = "lab-runner"
SCANNER_UID = 1000
CLONE_NEWNS = 0x00020000
CLONE_NEWUTS = 0x04000000
CLONE_NEWIPC = 0x08000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
MS_REC = 16384
MS_PRIVATE = 262144
MS_BIND = 4096

LIBC = ctypes.CDLL(None, use_errno=True)


def _mount(source: str, target: str, fstype: str, flags: int) -> None:
    LIBC.mount.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.c_char_p,
    ]
    LIBC.mount.restype = ctypes.c_int
    source_b = None if source == "" else source.encode()
    fstype_b = None if fstype == "" else fstype.encode()
    if LIBC.mount(source_b, target.encode(), fstype_b, flags, None) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), target)


def _unshare(flags: int) -> None:
    LIBC.unshare.argtypes = [ctypes.c_int]
    LIBC.unshare.restype = ctypes.c_int
    if LIBC.unshare(flags) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), "unshare")


def _sethostname(name: str) -> None:
    raw = name.encode()
    if LIBC.sethostname(raw, len(raw)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), name)


class Container:
    def __init__(self, name: str, role: str, uid: int, argv_extra: list[str], env: dict[str, str], hosts: str, cwd_files: dict[str, str]) -> None:
        self.name = name
        self.role = role
        self.uid = uid
        self.argv_extra = argv_extra
        self.env = env
        self.hosts = hosts
        self.cwd_files = cwd_files
        self.container_id = os.urandom(32).hex()
        self.helper_pid = 0
        self.inner_pid = 0
        self.cgroup = Path(f"/sys/fs/cgroup/docker-{self.container_id}.scope")
        self.workdir = Path(f"/tmp/vantio-t3-{name}")
        self.ready = self.workdir / "ready"


def _prepare(container: Container) -> None:
    if container.workdir.exists():
        shutil.rmtree(container.workdir)
    container.workdir.mkdir(mode=0o755)
    for relative, body in container.cwd_files.items():
        target = container.workdir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        os.chmod(target, 0o644)
    os.chmod(container.workdir, 0o755)
    if container.uid != 0:
        os.chown(container.workdir, container.uid, container.uid)
        for path in container.workdir.rglob("*"):
            os.chown(path, container.uid, container.uid)
    hosts = container.workdir / "hosts"
    hosts.write_text(container.hosts, encoding="utf-8")
    hostname = container.workdir / "hostname"
    hostname.write_text(container.name + "\n", encoding="utf-8")
    container.cgroup.mkdir(mode=0o755)


def _container_main(container: Container, writer: int) -> None:
    try:
        os.setsid()
        _mount("", "/", "", MS_REC | MS_PRIVATE)
        _mount("proc", "/proc", "proc", 0)
        _sethostname(container.name)
        _mount(str(container.workdir / "hosts"), "/etc/hosts", "", MS_BIND)
        _mount(str(container.workdir / "hostname"), "/etc/hostname", "", MS_BIND)
        subprocess.check_call(["/usr/sbin/ip", "link", "set", "lo", "up"])
        for address in ("10.88.0.2/32", "10.88.0.8/32", "10.88.0.9/32", "10.88.1.1/32"):
            subprocess.check_call(["/usr/sbin/ip", "addr", "add", address, "dev", "lo"])
        (container.cgroup / "cgroup.procs").write_text(str(os.getpid()), encoding="utf-8")
        os.chdir(container.workdir)
        env = os.environ.copy()
        env.update(container.env)
        env["VANTIO_LAB_UID"] = str(container.uid)
        argv = [sys.executable, str(PAYLOAD), container.role, str(container.ready), *container.argv_extra]
        os.write(writer, b"OK\n")
        os.close(writer)
        os.execve(sys.executable, argv, env)
    except Exception as exc:
        try:
            os.write(writer, f"ERR {exc}\n".encode())
            os.close(writer)
        except OSError:
            pass
        os._exit(1)


def start(container: Container) -> None:
    _prepare(container)
    reader, writer = os.pipe()
    helper = os.fork()
    if helper == 0:
        os.close(reader)
        try:
            _unshare(CLONE_NEWNS | CLONE_NEWUTS | CLONE_NEWIPC | CLONE_NEWPID | CLONE_NEWNET)
            inner = os.fork()
        except Exception as exc:
            os.write(writer, f"ERR {exc}\n".encode())
            os.close(writer)
            os._exit(1)
        if inner == 0:
            _container_main(container, writer)
            os._exit(1)
        os.close(writer)
        os.waitpid(inner, 0)
        os._exit(0)
    os.close(writer)
    container.helper_pid = helper
    message = os.read(reader, 512).decode()
    os.close(reader)
    if not message.startswith("OK"):
        raise RuntimeError(f"{container.name} failed to start: {message!r}")
    deadline = time.time() + 10
    while time.time() < deadline:
        if container.ready.exists():
            break
        time.sleep(0.05)
    else:
        raise RuntimeError(f"{container.name} did not become ready")
    text = (container.cgroup / "cgroup.procs").read_text(encoding="utf-8")
    pids = [int(line) for line in text.split() if line.strip().isdigit()]
    if not pids:
        raise RuntimeError(f"{container.name} cgroup is empty")
    container.inner_pid = pids[0]


def stop(container: Container) -> None:
    if container.helper_pid:
        try:
            os.kill(container.helper_pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            os.waitpid(container.helper_pid, 0)
        except OSError:
            pass
    shutil.rmtree(container.workdir, ignore_errors=True)
    if container.cgroup.exists():
        procs = container.cgroup / "cgroup.procs"
        try:
            for line in procs.read_text(encoding="utf-8").split():
                if line.isdigit():
                    os.kill(int(line), signal.SIGKILL)
        except OSError:
            pass
        time.sleep(0.1)
        try:
            container.cgroup.rmdir()
        except OSError:
            subprocess.run(["rmdir", str(container.cgroup)], check=False)


def hosts_digest() -> str:
    return hashlib.sha256(Path("/etc/hosts").read_bytes()).hexdigest()


def build_world() -> list[Container]:
    url = f"https://user:{CANARY}@api.openai.com/v1/{CANARY}?q={CANARY}"
    mcp = {
        "mcpServers": {
            "files": {
                "command": "/usr/bin/mcp-server-filesystem",
                "args": ["--readonly", CANARY],
                "env": {"TOKEN": CANARY},
                "headers": {"Authorization": CANARY},
                "description": CANARY,
            }
        }
    }
    decoy_mcp = {"mcpServers": {"files": {"command": "sleep", "description": CANARY, "url": "https://api.openai.com/v1"}}}
    agent_hosts = "10.88.0.2 api.openai.com\n10.88.0.9 api.openai.com api.anthropic.com\n10.88.1.1 example.test\n"
    return [
        Container("vantio-t3-agent", "agent", SCANNER_UID, [url, CANARY], {"OPENAI_API_KEY": CANARY}, agent_hosts, {}),
        Container("vantio-t3-ollama", "ollama", SCANNER_UID, [], {}, "127.0.0.1 localhost\n", {}),
        Container("vantio-t3-mcp", "mcp", SCANNER_UID, [], {}, "127.0.0.1 localhost\n", {"mcp.json": json.dumps(mcp)}),
        Container("vantio-t3-lineage", "lineage", SCANNER_UID, [], {}, "10.88.0.8 api.anthropic.com\n", {}),
        Container("vantio-t3-unenrolled", "agent", SCANNER_UID, [url], {"OPENAI_API_KEY": CANARY}, "10.88.0.2 api.openai.com\n", {}),
        Container("vantio-t3-unknown", "unknown", SCANNER_UID, [], {"OPENAI_API_KEY": CANARY}, "127.0.0.1 localhost\n", {}),
        Container("vantio-t3-partial", "partial", 0, [], {}, "127.0.0.1 localhost\n", {}),
        Container("vantio-t3-decoy-web", "decoy-web", SCANNER_UID, [], {}, "127.0.0.1 localhost\n", {}),
        Container(
            "vantio-t3-decoy-file",
            "decoy-file",
            SCANNER_UID,
            [],
            {},
            "127.0.0.1 localhost\n",
            {"note.txt": f"{CANARY}\napi.openai.com\n"},
        ),
        Container("vantio-t3-decoy-curl", "decoy-curl", SCANNER_UID, ["https://example.com/index"], {}, "127.0.0.1 localhost\n", {}),
        Container(
            "vantio-t3-decoy-mcpconfig",
            "decoy-mcp",
            SCANNER_UID,
            [],
            {},
            "127.0.0.1 localhost\n",
            {".cursor/mcp.json": json.dumps(decoy_mcp)},
        ),
    ]


def enrollment(names: set[str], containers: list[Container]) -> dict:
    return {
        "schema": "vantio.optics.enrollment.v1",
        "host_id": HOST_ID,
        "host_processes": False,
        "containers": [item.container_id for item in containers if item.name in names],
    }


def run_scan(enrollment_path: Path, runs: Path, endpoint_map: Path, out: Path) -> tuple[dict, str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env.pop("VANTIO_EXTRA_LLM_HOSTS", None)
    cmd = [
        "sudo",
        "-n",
        "-u",
        "ubuntu",
        "env",
        f"PYTHONPATH={SRC}",
        sys.executable,
        "-m",
        "optics_agent_inventory",
        "--host-id",
        HOST_ID,
        "--enrollment",
        str(enrollment_path),
        "--endpoint-map",
        str(endpoint_map),
        "--runs-dir",
        str(runs),
        "--out",
        str(out),
    ]
    completed = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, check=False)
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(f"scan exit {completed.returncode}\n{stderr}\n{stdout[:500]}")
    return json.loads(stdout), stdout, stderr


def ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator


def score(report: dict, expected: Counter, population: set[str]) -> dict:
    predicted = Counter()
    outside = []
    for row in report["workloads"]:
        cid = row["where"]["container_id"]
        key = (cid, row["role"], row["coverage"])
        if cid in population:
            predicted[key] += 1
        else:
            outside.append({"container_id": cid, "role": row["role"], "coverage": row["coverage"]})
    keys = set(expected) | set(predicted)
    strict_tp = sum(min(expected[key], predicted[key]) for key in keys)
    strict_fp = sum(predicted.values()) - strict_tp
    strict_fn = sum(expected.values()) - strict_tp
    discovery_expected: Counter = Counter()
    discovery_predicted: Counter = Counter()
    for (cid, role, _coverage), count in expected.items():
        discovery_expected[(cid, role)] += count
    for (cid, role, _coverage), count in predicted.items():
        discovery_predicted[(cid, role)] += count
    dkeys = set(discovery_expected) | set(discovery_predicted)
    discovery_tp = sum(min(discovery_expected[key], discovery_predicted[key]) for key in dkeys)
    discovery_fp = sum(discovery_predicted.values()) - discovery_tp
    discovery_fn = sum(discovery_expected.values()) - discovery_tp
    return {
        "strict_precision": ratio(strict_tp, strict_tp + strict_fp),
        "strict_recall": ratio(strict_tp, strict_tp + strict_fn),
        "discovery_precision": ratio(discovery_tp, discovery_tp + discovery_fp),
        "discovery_recall": ratio(discovery_tp, discovery_tp + discovery_fn),
        "strict_tp": strict_tp,
        "strict_fp": strict_fp,
        "strict_fn": strict_fn,
        "discovery_tp": discovery_tp,
        "discovery_fp": discovery_fp,
        "discovery_fn": discovery_fn,
        "false_positives": [list(key) for key, count in predicted.items() for _ in range(count) if predicted[key] > expected[key]],
        "false_negatives": [list(key) for key, count in expected.items() for _ in range(max(0, count - predicted[key]))],
        "outside_seed": outside,
    }


def expect_primary(containers: list[Container]) -> Counter:
    wanted = {
        "vantio-t3-agent": ("api_client", "covered"),
        "vantio-t3-ollama": ("local_model_server", "covered"),
        "vantio-t3-mcp": ("mcp_server", "covered"),
        "vantio-t3-lineage": ("agent_runtime", "covered"),
        "vantio-t3-unenrolled": ("api_client", "unenrolled"),
        "vantio-t3-unknown": ("credential_only", "unknown"),
        "vantio-t3-partial": ("agent_runtime", "partial"),
    }
    by_name = {item.name: item.container_id for item in containers}
    return Counter({(by_name[name], role, coverage): 1 for name, (role, coverage) in wanted.items()})


def main() -> int:
    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo", "-n", sys.executable, *sys.argv])
    before = hosts_digest()
    containers = build_world()
    lab = Path("/tmp/vantio-t3-proof")
    if lab.exists():
        shutil.rmtree(lab)
    lab.mkdir(mode=0o755)
    os.chown(lab, SCANNER_UID, SCANNER_UID)
    os.chmod(lab, 0o755)
    runs = lab / "runs"
    runs.mkdir()
    (runs / "decoy.json").write_text(
        json.dumps(
            {
                "vantio_run_log": "1",
                "pid": 1,
                "started_at": "2020-01-01T00:00:00Z",
                "path": CANARY,
                "error": CANARY,
                "calls": [{"hostname": "api.openai.com", "path": CANARY, "error": CANARY}],
            }
        ),
        encoding="utf-8",
    )
    endpoint_map = {
        "schema": "vantio.optics.endpoint_map.v1",
        "map": [{"ip": "10.88.0.2", "host": "api.openai.com", "port": 8443}],
    }
    (lab / "map.json").write_text(json.dumps(endpoint_map), encoding="utf-8")
    try:
        for container in containers:
            start(container)
        population = {item.container_id for item in containers}
        primary_names = {item.name for item in containers if item.name != "vantio-t3-unenrolled"}
        (lab / "primary.json").write_text(json.dumps(enrollment(primary_names, containers)), encoding="utf-8")
        report, stdout, stderr = run_scan(lab / "primary.json", runs, lab / "map.json", lab / "primary-out.json")
        scored = score(report, expect_primary(containers), population)
        lineage = next(row for row in report["workloads"] if row["where"]["container_id"] == next(item.container_id for item in containers if item.name == "vantio-t3-lineage"))
        socket_hosts = [item for item in lineage["observed_reach"] if item["source"] == "socket"]
        pass_b_names = {
            "vantio-t3-agent",
            "vantio-t3-ollama",
            "vantio-t3-mcp",
            "vantio-t3-lineage",
            "vantio-t3-decoy-web",
            "vantio-t3-decoy-file",
            "vantio-t3-decoy-curl",
            "vantio-t3-decoy-mcpconfig",
        }
        (lab / "pass-b.json").write_text(json.dumps(enrollment(pass_b_names, containers)), encoding="utf-8")
        report_b, stdout_b, stderr_b = run_scan(lab / "pass-b.json", runs, lab / "map.json", lab / "pass-b-out.json")
        pass_c_names = pass_b_names | {"vantio-t3-partial"}
        (lab / "pass-c.json").write_text(json.dumps(enrollment(pass_c_names, containers)), encoding="utf-8")
        report_c, stdout_c, stderr_c = run_scan(lab / "pass-c.json", runs, lab / "map.json", lab / "pass-c-out.json")
        partial_id = next(item.container_id for item in containers if item.name == "vantio-t3-partial")
        partial_row = next(row for row in report_c["workloads"] if row["where"]["container_id"] == partial_id)
        after = hosts_digest()
        blobs = [stdout, stderr, stdout_b, stderr_b, stdout_c, stderr_c]
        for path in (lab / "primary-out.json", lab / "pass-b-out.json", lab / "pass-c-out.json"):
            blobs.append(path.read_text(encoding="utf-8"))
        evidence = {
            "schema": "vantio.optics.t3_inventory_proof.v1",
            "label": "lab-only",
            "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "runtime": "namespace",
            "scanner_euid": SCANNER_UID,
            "scored_population": "seeded_container_ids",
            "host_coverage": {
                "primary": report["host"]["coverage"],
                "pass_b": report_b["host"]["coverage"],
                "pass_c": report_c["host"]["coverage"],
            },
            "host_reasons": {
                "primary": report["host"]["reasons"],
                "pass_b": report_b["host"]["reasons"],
                "pass_c": report_c["host"]["reasons"],
            },
            "lineage_socket_name_source": "private_hosts",
            "endpoint_map_contains_lineage_ip": False,
            "lineage_socket_reach": socket_hosts,
            "partial_coverage_pass_c": partial_row["coverage"],
            "hosts_file_unchanged": before == after,
            "stand_ins": [
                {"container": item.name, "note": "Python interpreter started with a lab comm, not the upstream binary"}
                for item in containers
                if item.role in {"agent", "ollama", "mcp", "lineage", "partial", "decoy-curl"}
            ],
            "canary_sha256": hashlib.sha256(CANARY.encode()).hexdigest(),
            "canary_absent": all(CANARY not in blob for blob in blobs),
            "content_stored": report["content_stored"],
            "risks_open": [f"R{index}" for index in range(1, 17)],
            **scored,
        }
        checks = [
            scored["strict_precision"] == 1,
            scored["strict_recall"] == 1,
            scored["discovery_precision"] == 1,
            scored["discovery_recall"] == 1,
            report["host"]["coverage"] == "unknown",
            report_b["host"]["coverage"] == "covered",
            report_c["host"]["coverage"] == "partial",
            "enrolled_scope_unreadable" in report_c["host"]["reasons"],
            partial_row["coverage"] == "partial",
            any(item["host"] == "api.anthropic.com" and item["source"] == "socket" for item in socket_hosts),
            evidence["canary_absent"],
            report["content_stored"] is False,
            evidence["hosts_file_unchanged"],
            "10.88.1.1" not in stdout,
            "example.test" not in stdout,
            scored["outside_seed"] == [],
        ]
        evidence["failed_checks"] = [index for index, ok in enumerate(checks) if not ok]
        evidence["pass"] = not evidence["failed_checks"]
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(evidence, indent=2) + "\n"
        if CANARY in text:
            evidence["canary_absent"] = False
            evidence["pass"] = False
            text = json.dumps(evidence, indent=2) + "\n"
        EVIDENCE.write_text(text, encoding="utf-8")
        print(text)
        return 0 if evidence["pass"] else 1
    finally:
        for container in containers:
            stop(container)
        shutil.rmtree(lab, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"proof failed: {exc}\n")
        raise
