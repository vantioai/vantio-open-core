"""Fixture host mutations and a live executor that stays disabled unless authorized."""

from __future__ import annotations

import shutil
from pathlib import Path

from vantio_install import constants
from vantio_install.live_executor import execute_step
from vantio_install.optics_cli import remove_optics_prefix
from vantio_install.commands import (
    docker_load_argv,
    docker_rmi_argv,
    docker_stop_rm_argv,
    npm_install_argv,
    observe_container_argv,
    observe_env,
)
from vantio_install.errors import InstallError
from vantio_install.util import sha256_file, write_json


class FixtureMutator:
    """Applies the transaction to an in-memory host snapshot and a temp prefix."""

    def __init__(self, snapshot: dict, prefix: Path, stage: Path) -> None:
        self.snapshot = snapshot
        self.prefix = prefix
        self.stage = stage
        self.mutation_count = 0
        self.recorded_argv: list[list[str]] = []

    def apply_step(self, step_id: str, ctx: dict) -> None:
        if step_id in constants.HOST_MUTATION_STEPS:
            self.mutation_count += 1
        handler = {
            "install_optics_cli": self._install_optics,
            "install_agent_sdks": self._install_sdks,
            "stage_pe_archive": self._stage_pe,
            "docker_load": self._docker_load,
            "write_observe_config": self._write_config,
            "start_pe_observe": self._start,
        }.get(step_id)
        if handler:
            handler(ctx)

    def rollback_step(self, step_id: str, ctx: dict) -> None:
        handler = {
            "install_optics_cli": self._remove_optics,
            "install_agent_sdks": self._remove_sdks,
            "stage_pe_archive": self._remove_stage,
            "docker_load": self._docker_rmi,
            "write_observe_config": self._remove_config,
            "start_pe_observe": self._stop,
        }.get(step_id)
        if handler:
            self.mutation_count += 1
            handler(ctx)

    def uninstall(self, scope: str, ctx: dict) -> None:
        leave = set(ctx.get("uninstall_leave") or [])
        if scope in {"pe", "all"}:
            if "container" not in leave:
                self._stop(ctx)
            if "image" not in leave:
                self._docker_rmi(ctx)
            if "stage" not in leave:
                self._remove_stage(ctx)
            if "bpf_pins" not in leave:
                self.snapshot["bpf_pins"] = []
            else:
                self.snapshot["bpf_pins"] = list(constants.BPF_PINS)
            if "clsact" not in leave:
                self.snapshot["clsact_ifaces"] = []
            if "loader" not in leave:
                self.snapshot["processes"] = [
                    name for name in self.snapshot.get("processes") or [] if name != "vantio-loader"
                ]
        if scope in {"optics", "all"} and "optics" not in leave:
            self._remove_optics(ctx)
            self._remove_sdks(ctx)
        self.mutation_count += 1

    def _mark_file(self, path: Path, payload: dict) -> None:
        write_json(path, payload)
        files = self.snapshot.setdefault("product_files", [])
        text = path.as_posix()
        if text not in files:
            files.append(text)

    def _drop_file(self, path: Path) -> None:
        if path.is_file() or path.is_symlink():
            path.unlink()
        files = self.snapshot.setdefault("product_files", [])
        text = path.as_posix()
        self.snapshot["product_files"] = [item for item in files if item != text]

    def _install_optics(self, ctx: dict) -> None:
        pin = constants.FROZEN_PINS
        argv = npm_install_argv(str(ctx["paths"]["optics_cli"]), str(self.prefix))
        self.recorded_argv.append(argv)
        self.snapshot.setdefault("recorded_argv", []).append(argv)
        self.prefix.mkdir(parents=True, exist_ok=True)
        self._mark_file(
            self.prefix / "optics-cli-receipt.json",
            {
                "marker": "vantio-install-receipt",
                "package": pin["optics_cli_package"],
                "version": pin["optics_cli_version"],
                "sha256": pin["optics_cli_sha256"],
            },
        )
        self.snapshot["optics_cli_version"] = pin["optics_cli_version"]

    def _install_sdks(self, ctx: dict) -> None:
        pin = constants.FROZEN_PINS
        self.prefix.mkdir(parents=True, exist_ok=True)
        self._mark_file(
            self.prefix / "agent-sdk-receipt.json",
            {
                "marker": "vantio-install-receipt",
                "npm": pin["agent_sdk_npm_version"],
                "python": pin["agent_sdk_py_version"],
            },
        )

    def _remove_optics(self, ctx: dict) -> None:
        remove_optics_prefix(self.prefix)
        self._drop_file(self.prefix / "optics-cli-receipt.json")
        self._drop_file(self.prefix / "bin" / "vantio")
        self.snapshot["optics_cli_version"] = None

    def _remove_sdks(self, ctx: dict) -> None:
        self._drop_file(self.prefix / "agent-sdk-receipt.json")

    def _stage_pe(self, ctx: dict) -> None:
        source = ctx["paths"]["pe_archive"]
        self.stage.mkdir(parents=True, exist_ok=True)
        target = self.stage / source.name
        shutil.copyfile(source, target)
        observed = sha256_file(target)
        expected = constants.FROZEN_PINS["pe_archive_sha256"]
        if observed != expected:
            raise InstallError(
                "Staged Phantom Engine archive hash does not match the frozen pin.",
                exit_code=4,
                state="FAILED_SAFE",
            )
        self._mark_file(self.stage / "STAGE.json", {"archive": target.name, "sha256": observed})

    def _remove_stage(self, ctx: dict) -> None:
        if self.stage.is_dir():
            shutil.rmtree(self.stage)
        prefix = self.stage.as_posix()
        files = self.snapshot.get("product_files") or []
        self.snapshot["product_files"] = [item for item in files if not item.startswith(prefix)]

    def _docker_load(self, ctx: dict) -> None:
        pin = constants.FROZEN_PINS
        archive = self.stage / pin["pe_archive_name"]
        load_argv = docker_load_argv(str(archive))
        self.recorded_argv.append(load_argv)
        self.snapshot.setdefault("recorded_argv", []).append(load_argv)
        images = self.snapshot.setdefault("images", [])
        if not any(row.get("tag") == pin["pe_local_tag"] for row in images):
            images.append(
                {
                    "tag": pin["pe_local_tag"],
                    "digest": pin["pe_manifest_digest"],
                    "role": "phantom_engine",
                }
            )

    def _docker_rmi(self, ctx: dict) -> None:
        tag = constants.FROZEN_PINS["pe_local_tag"]
        self.recorded_argv.append(docker_rmi_argv(tag))
        self.snapshot["images"] = [
            row for row in self.snapshot.get("images") or [] if row.get("tag") != tag
        ]

    def _write_config(self, ctx: dict) -> None:
        path = Path(ctx["observe_config_path"])
        payload = {
            "install_mode": "observe-only",
            "enforcement": "NOT_ENABLED",
            "otlp": "DISABLED",
            "path_deny": "disabled",
            "traffic_control": "audit-only",
            "iface": ctx["config"]["iface"],
            "env": observe_env(),
            "cmd": ["--iface", ctx["config"]["iface"]],
        }
        if "--enforce" in payload["cmd"] or "VANTIO_PHANTOM_DENY" in payload["env"]:
            raise InstallError("Refusing to write an enforcing config.", exit_code=4, state="FAILED_SAFE")
        self._mark_file(path, payload)

    def _remove_config(self, ctx: dict) -> None:
        self._drop_file(Path(ctx["observe_config_path"]))

    def _start(self, ctx: dict) -> None:
        pin = constants.FROZEN_PINS
        iface = ctx["config"]["iface"]
        name = f"vantio-pe-{ctx['transaction_id'][-12:]}"
        argv = observe_container_argv(tag=pin["pe_local_tag"], iface=iface, name=name)
        if "--enforce" in argv:
            raise InstallError("Observe start refused an enforce flag.", exit_code=4, state="FAILED_SAFE")
        self.recorded_argv.append(argv)
        self.snapshot.setdefault("recorded_argv", []).append(argv)
        containers = self.snapshot.setdefault("containers", [])
        if any(row.get("name") == name and row.get("status") == "running" for row in containers):
            return
        containers.append(
            {
                "name": name,
                "role": "phantom_engine",
                "status": "running",
                "image": pin["pe_local_tag"],
                "cmd": ["--iface", iface],
                "enforce": False,
            }
        )
        missing = set(ctx.get("simulate_missing") or [])
        if "bpf_pins" not in missing:
            self.snapshot["bpf_pins"] = list(constants.BPF_PINS)
        if "clsact" not in missing:
            clsact = self.snapshot.setdefault("clsact_ifaces", [])
            if iface not in clsact:
                clsact.append(iface)
        if "vantio-loader" not in missing:
            procs = self.snapshot.setdefault("processes", [])
            if "vantio-loader" not in procs:
                procs.append("vantio-loader")
        extra = ctx.get("simulate_probe_errors") or []
        if extra:
            current = set(self.snapshot.get("probe_errors") or [])
            current.update(extra)
            self.snapshot["probe_errors"] = sorted(current)

    def _stop(self, ctx: dict) -> None:
        name_suffix = ctx["transaction_id"][-12:]
        commands = docker_stop_rm_argv(f"vantio-pe-{name_suffix}")
        self.recorded_argv.extend(commands)
        self.snapshot["containers"] = [
            row
            for row in self.snapshot.get("containers") or []
            if not str(row.get("name", "")).endswith(name_suffix)
        ]
        self.snapshot["bpf_pins"] = []
        self.snapshot["clsact_ifaces"] = []
        self.snapshot["processes"] = [
            name for name in self.snapshot.get("processes") or [] if name != "vantio-loader"
        ]


class LiveMutator:
    """Runs allowlisted observe-only operations after authorize_live returns a grant."""

    def __init__(self, grant, runner, observer, snapshot: dict) -> None:
        if grant is None:
            raise InstallError(
                "Live host mutations need an authorization grant. The env var alone does not grant one.",
                exit_code=4,
                state="FAILED_SAFE",
                failure_class="FAILED_SAFE",
            )
        self.grant = grant
        self.prefix = grant.prefix
        self.runner = runner
        self.observer = observer
        self.snapshot = snapshot
        self.mutation_count = 0
        self.recorded_argv: list[list[str]] = []

    def apply_step(self, step_id: str, ctx: dict) -> None:
        self._run(step_id, "apply")

    def rollback_step(self, step_id: str, ctx: dict) -> None:
        self._run(step_id, "rollback")

    def uninstall(self, scope: str, ctx: dict) -> None:
        if scope in {"pe", "all"}:
            for step_id in ("start_pe_observe", "docker_load", "stage_pe_archive", "write_observe_config"):
                self._run(step_id, "rollback")
        if scope in {"optics", "all"}:
            for step_id in ("install_agent_sdks", "install_optics_cli"):
                self._run(step_id, "rollback")

    def _run(self, step_id: str, kind: str) -> None:
        if step_id not in constants.HOST_MUTATION_STEPS:
            return
        deltas, argv = execute_step(self.grant, step_id, kind, self.runner, self.observer)
        for delta in deltas:
            self._merge(delta)
        self.recorded_argv.extend(argv)
        self.snapshot.setdefault("recorded_argv", []).extend(argv)
        if argv or deltas:
            self.mutation_count += 1

    def _merge(self, delta: dict) -> None:
        for key in ("optics_cli_version",):
            if key in delta:
                self.snapshot[key] = delta[key]
        for key in ("images", "containers", "bpf_pins", "clsact_ifaces", "processes"):
            if key in delta:
                self.snapshot[key] = delta[key]
