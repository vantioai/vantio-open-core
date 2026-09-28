"""Command lines the live executor would run. Tests inspect these and do not execute them."""

from __future__ import annotations

from vantio_install import constants


def observe_apparmor_opt() -> str:
    return "apparmor=" + constants.PE_OBSERVE_APPARMOR_PROFILE


# Read-write binds. No :ro suffix. AppArmor still denies writes under /sys/kernel.
OBSERVE_BPFFS_BIND = "/sys/fs/bpf:/sys/fs/bpf"
OBSERVE_TRACEFS_BIND = "/sys/kernel/tracing:/sys/kernel/tracing"


def observe_binds() -> list[str]:
    """Host paths the observe container must see. bpffs, then tracefs."""
    return [OBSERVE_BPFFS_BIND, OBSERVE_TRACEFS_BIND]


def observe_container_argv(*, tag: str, iface: str, name: str) -> list[str]:
    """Observe-only container. Named AppArmor profile, three caps, bpffs and tracefs binds."""
    argv = [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "--network",
        "host",
        "--cap-add",
        "NET_ADMIN",
        "--cap-add",
        "BPF",
        "--cap-add",
        "SYS_ADMIN",
        "--security-opt",
        observe_apparmor_opt(),
    ]
    for bind in observe_binds():
        argv.extend(["-v", bind])
    argv.extend(
        [
            "-e",
            "VANTIO_TELEMETRY_DISABLED=1",
            "-e",
            "DO_NOT_TRACK=1",
            tag,
            "--iface",
            iface,
        ]
    )
    return argv


def apparmor_parser_load_argv(profile_path: str) -> list[str]:
    # -K skips the cache write. -r replaces the kernel profile. Same flags dockerd uses.
    return ["apparmor_parser", "-Kr", profile_path]


def apparmor_parser_remove_argv(profile_path: str) -> list[str]:
    return ["apparmor_parser", "-KR", profile_path]


def docker_load_argv(archive: str) -> list[str]:
    return ["docker", "load", "-i", archive]


def docker_tag_argv(digest: str, tag: str) -> list[str]:
    return ["docker", "tag", digest, tag]


def docker_stop_rm_argv(name: str) -> list[list[str]]:
    return [["docker", "stop", name], ["docker", "rm", name]]


def docker_rmi_argv(tag: str) -> list[str]:
    return ["docker", "rmi", tag]


def npm_install_argv(tarball: str, prefix: str) -> list[str]:
    return ["npm", "install", "--global", "--prefix", prefix, tarball]


def pip_wheel_argv(wheel: str, prefix: str) -> list[str]:
    return [
        "python3",
        "-m",
        "pip",
        "install",
        "--no-index",
        "--disable-pip-version-check",
        "--prefix",
        prefix,
        wheel,
    ]


def mkdir_argv(path: str) -> list[str]:
    return ["mkdir", "-p", "--", path]


def tc_clsact_argv(iface: str) -> list[str]:
    return ["tc", "qdisc", "replace", "dev", iface, "clsact"]


def tc_clsact_del_argv(iface: str) -> list[str]:
    return ["tc", "qdisc", "del", "dev", iface, "clsact"]


def docker_start_argv(name: str) -> list[str]:
    return ["docker", "start", name]


def observe_env() -> dict[str, str]:
    return {
        "VANTIO_TELEMETRY_DISABLED": "1",
        "DO_NOT_TRACK": "1",
    }
