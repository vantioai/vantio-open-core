"""CLI for the enrolled boot hold. Stdout is one JSON object."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from vantio_install.boot_hold.errors import BootHoldError
from vantio_install.boot_hold.graph import graph_errors
from vantio_install.boot_hold.identity import read_host_caller
from vantio_install.boot_hold.policy import default_policy
from vantio_install.boot_hold.policy import load_policy
from vantio_install.boot_hold.readiness import assemble_host_facts, default_bpftool, probe_host
from vantio_install.boot_hold.service import (
    apply_boot,
    configure,
    enroll_compose,
    enroll_docker,
    enroll_systemd,
    ensure_network,
    envelope,
    install,
    loader_argv,
    observe_unenrolled,
    opt_in,
    opt_out,
    release,
    start_loader,
    status_body,
    live_boot_hold_runner,
)
from vantio_install.boot_hold.units import static_units
from vantio_install import constants as install_constants


class RecordingRunner:
    """Runs host commands only when the live gate is set. Otherwise it records them."""

    def __init__(self, live: bool) -> None:
        self.live = live
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        if self.live:
            completed = subprocess.run(argv, check=False)
            return int(completed.returncode)
        if len(argv) >= 2 and argv[1] in {"-C", "-N", "-D", "-X"}:
            return 1
        if argv and argv[0] == "docker":
            return 1
        if "inspect" in argv:
            return 1
        if argv[:2] == ["/usr/sbin/apparmor_parser", "-V"]:
            return 1
        if argv[:2] == ["apparmor_parser", "-V"]:
            return 0 if shutil.which("apparmor_parser") else 1
        return 0


def _live(root: Path) -> bool:
    return root == Path("/") and os.geteuid() == 0 and os.environ.get("VANTIO_BOOT_HOLD_LIVE") == "1"


def _capture(argv: list[str]) -> str:
    try:
        completed = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout or ""


def _facts_probe(root: Path, facts_path: str | None):
    def probe() -> dict:
        if facts_path and os.environ.get("VANTIO_BOOT_HOLD_ALLOW_FACTS") == "1":
            data = json.loads(Path(facts_path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            return data
        if not _live(root):
            return probe_host(root, bpftool=default_bpftool)
        policy, _notes = load_policy(root)
        return assemble_host_facts(
            root,
            prog_show=_capture(["bpftool", "prog", "show"]),
            cgroup_show=_capture(["bpftool", "cgroup", "show", "/sys/fs/cgroup/vantio-enrolled.slice"]),
            map_show=_capture(["bpftool", "map", "show"]),
            runner=live_boot_hold_runner,
            deny_probe=policy.get("deny_probe") if isinstance(policy.get("deny_probe"), dict) else None,
        )

    return probe


def _parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--root", default="/")
    parent.add_argument("--json", action="store_true")
    parser = argparse.ArgumentParser(prog="vantio-boot-hold")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("install", "apply-boot", "start-loader", "ensure-network", "opt-in", "graph-check"):
        sub.add_parser(name, parents=[parent])

    status = sub.add_parser("status", parents=[parent])
    status.add_argument("--lookup", default="")

    release_cmd = sub.add_parser("release", parents=[parent])
    release_cmd.add_argument("--require-enforce-ready", action="store_true")
    release_cmd.add_argument("--break-glass", action="store_true")
    release_cmd.add_argument("--i-am-root-operator", action="store_true")
    release_cmd.add_argument("--wait-seconds", type=int, default=0)
    release_cmd.add_argument("--facts", default="")

    enroll_unit = sub.add_parser("enroll-systemd", parents=[parent])
    enroll_unit.add_argument("--unit", required=True)
    enroll_unit.add_argument("--protected-path", action="append", default=[])

    enroll_d = sub.add_parser("enroll-docker", parents=[parent])
    enroll_d.add_argument("--name", required=True)
    enroll_d.add_argument("--restart-policy", default="no")
    enroll_d.add_argument("--cgroup-parent", default="")
    enroll_d.add_argument("--protected-path", action="append", default=[])
    enroll_d.add_argument("--set-restart-no", action="store_true")

    enroll_c = sub.add_parser("enroll-compose", parents=[parent])
    enroll_c.add_argument("--project-dir", required=True)
    enroll_c.add_argument("--compose-file", required=True)

    observe = sub.add_parser("observe-unenrolled", parents=[parent])
    observe.add_argument("--id", required=True)
    observe.add_argument("--kind", required=True)

    opt = sub.add_parser("opt-out", parents=[parent])
    opt.add_argument("--reason", required=True)

    config = sub.add_parser("configure", parents=[parent])
    config.add_argument("--hold", required=True, choices=["on", "off"])
    config.add_argument("--ordering", required=True, choices=["on", "off"])
    return parser


def _dump(payload: dict) -> int:
    if payload.get("proof_state") in install_constants.FORBIDDEN_PROOF_STATES:
        payload["proof_state"] = install_constants.PROOF_STATE
        payload["state"] = "FAILED_SAFE"
        payload["reboot_row"] = "NOT_PROVED"
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if payload.get("state") in {"FAILED_SAFE", "UNKNOWN"}:
        return 4
    if payload.get("state") == "HELD" and payload.get("command") == "release":
        return 4
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 10
    root = Path(args.root)
    caller = read_host_caller()
    runner = RecordingRunner(_live(root))
    python = sys.executable or "/usr/bin/python3"
    command = args.command
    try:
        if command == "graph-check":
            units = static_units(python, default_policy())
            errors = graph_errors(units, ordering=True, hold=True)
            payload = envelope(
                "graph-check",
                "FAILED_SAFE" if errors else "OK",
                "Dependency graph check failed." if errors else "Boot hold ordering keeps SSH, Docker, and enrolled workloads in the required order.",
                errors=errors,
            )
            return _dump(payload) if not errors else (_dump(payload) or 1)
        if command == "status":
            payload = status_body(root, lookup=args.lookup or None)
        elif command == "install":
            payload = install(root, caller, python)
        elif command == "apply-boot":
            payload = apply_boot(root, caller, runner, python)
        elif command == "start-loader":
            payload = start_loader(root, caller)
            if _live(root):
                argv_exec = loader_argv(root)
                os.execv(argv_exec[0], argv_exec)
        elif command == "ensure-network":
            payload = ensure_network(root, caller, runner)
        elif command == "release":
            payload = release(
                root,
                caller,
                runner,
                require_ready=bool(args.require_enforce_ready),
                break_glass=bool(args.break_glass),
                operator_flag=bool(args.i_am_root_operator),
                facts_probe=_facts_probe(root, args.facts or None),
                wait_seconds=int(args.wait_seconds),
                python=python,
            )
        elif command == "enroll-systemd":
            payload = enroll_systemd(root, caller, args.unit, list(args.protected_path), python)
        elif command == "enroll-docker":
            payload = enroll_docker(
                root,
                caller,
                args.name,
                args.restart_policy,
                args.cgroup_parent,
                list(args.protected_path),
                python,
                set_restart_no=bool(args.set_restart_no),
                runner=runner,
            )
        elif command == "enroll-compose":
            text = Path(args.compose_file).read_text(encoding="utf-8")
            payload = enroll_compose(root, caller, args.project_dir, text, python)
        elif command == "observe-unenrolled":
            payload = observe_unenrolled(root, caller, args.id, args.kind)
        elif command == "opt-out":
            payload = opt_out(root, caller, runner, args.reason, python)
        elif command == "opt-in":
            payload = opt_in(root, caller, runner, python)
        elif command == "configure":
            payload = configure(
                root,
                caller,
                runner,
                hold=args.hold == "on",
                ordering=args.ordering == "on",
                python=python,
            )
        else:
            payload = envelope(command, "FAILED_SAFE", "Unknown command.")
            return _dump(payload) or 10
    except BootHoldError as exc:
        payload = envelope(command, exc.state, str(exc))
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 — last-resort crash envelope
        payload = envelope(command, "FAILED_SAFE", exc.__class__.__name__)
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return install_constants.EXIT_CRASH
    return _dump(payload)
