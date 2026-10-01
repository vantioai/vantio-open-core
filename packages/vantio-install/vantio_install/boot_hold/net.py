"""Enrolled-only packet hold. No default-route change and no host-wide policy drop."""

from __future__ import annotations

from collections.abc import Callable

from vantio_install.boot_hold.constants import CHAIN
from vantio_install.boot_hold.errors import BootHoldError

Runner = Callable[[list[str]], int]

_FORBIDDEN = (
    "route",
    "blackhole",
    "0.0.0.0/0",
    "::/0",
    "-P",
    "iptables-restore",
    "ip6tables-restore",
)


def families(policy: dict) -> tuple[tuple[str, str], ...]:
    return (
        ("iptables", str(policy["enrolled_subnet_v4"])),
        ("ip6tables", str(policy["enrolled_subnet_v6"])),
    )


def commands_are_scoped(calls: list[list[str]]) -> list[str]:
    """Return problems if a command would hold the whole host."""

    problems: list[str] = []
    for argv in calls:
        blob = " ".join(argv)
        for token in _FORBIDDEN:
            if token in blob:
                problems.append(f"command contains {token!r}: {blob}")
        if "FORWARD" in argv or "OUTPUT" in argv:
            scoped = "cgroup" in argv or "-s" in argv
            if not scoped and "-D" not in argv and "-F" not in argv and "-X" not in argv and "-N" not in argv:
                problems.append(f"filter jump is not scoped to a cgroup or enrolled subnet: {blob}")
    return problems


def _required(runner: Runner, argv: list[str]) -> None:
    if runner(argv) != 0:
        raise BootHoldError(f"Host command failed: {' '.join(argv)}")


def install_hold(runner: Runner, policy: dict) -> list[list[str]]:
    issued: list[list[str]] = []

    def run(argv: list[str]) -> int:
        issued.append(list(argv))
        return runner(argv)

    slice_path = str(policy["cgroup_slice"])
    for binary, subnet in families(policy):
        run([binary, "-N", CHAIN])
        _required(run, [binary, "-F", CHAIN])
        _required(run, [binary, "-A", CHAIN, "-j", "DROP"])
        check_out = [binary, "-C", "OUTPUT", "-m", "cgroup", "--path", slice_path, "-j", CHAIN]
        if run(check_out) != 0:
            _required(run, [binary, "-I", "OUTPUT", "1", "-m", "cgroup", "--path", slice_path, "-j", CHAIN])
        check_fwd = [binary, "-C", "FORWARD", "-s", subnet, "-j", CHAIN]
        if run(check_fwd) != 0:
            _required(run, [binary, "-I", "FORWARD", "1", "-s", subnet, "-j", CHAIN])
    problems = commands_are_scoped(issued)
    if problems:
        raise BootHoldError("Refusing a host-wide hold. " + problems[0])
    return issued


def remove_hold(runner: Runner, policy: dict) -> list[list[str]]:
    issued: list[list[str]] = []

    def run(argv: list[str]) -> int:
        issued.append(list(argv))
        return runner(argv)

    slice_path = str(policy["cgroup_slice"])
    for binary, subnet in families(policy):
        for _ in range(8):
            if run([binary, "-D", "OUTPUT", "-m", "cgroup", "--path", slice_path, "-j", CHAIN]) != 0:
                break
        for _ in range(8):
            if run([binary, "-D", "FORWARD", "-s", subnet, "-j", CHAIN]) != 0:
                break
        run([binary, "-F", CHAIN])
        run([binary, "-X", CHAIN])
    problems = commands_are_scoped(issued)
    if problems:
        raise BootHoldError("Refusing a host-wide hold change. " + problems[0])
    return issued
