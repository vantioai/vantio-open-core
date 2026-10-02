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


ENFORCE_CGROUP_BIND = "/sys/fs/cgroup:/sys/fs/cgroup"
ENFORCE_EVENTS_BIND = "/var/lib/vantio/pe-events:/var/lib/vantio/pe-events"
ENFORCE_EVENTS_FILE = "/var/lib/vantio/pe-events/events.ndjson"
ENFORCE_SLICE = "/sys/fs/cgroup/vantio-enrolled.slice"


def enforce_container_argv(*, tag: str, iface: str, name: str) -> list[str]:
    """Enforcement container. Same profile and caps as observe, with the slice visible.

    The container stays out of the enrolled slice. The loader enrolls that slice.
    """
    argv = [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "--restart",
        "no",
        "--network",
        "host",
        "--cgroupns",
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
    for bind in [*observe_binds(), ENFORCE_CGROUP_BIND, ENFORCE_EVENTS_BIND]:
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
            "--enforce",
            "--cgroup-skb-enforce",
            "--startup-enroll-cgroup",
            ENFORCE_SLICE,
            "--output-file",
            ENFORCE_EVENTS_FILE,
        ]
    )
    return argv


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


def npm_version_argv() -> list[str]:
    return ["npm", "--version"]


def apt_install_npm_argv() -> list[str]:
    """Ubuntu npm package only. The nodejs package does not ship the npm binary."""
    return ["apt-get", "install", "-y", "--no-install-recommends", "npm"]


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
