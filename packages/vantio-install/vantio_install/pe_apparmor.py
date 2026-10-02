"""AppArmor profile for the observe-only Phantom Engine container.

docker-default denies writes under /sys/fs/bpf (`deny /sys/fs/[^c]*/** wklx`).
That denial returns EACCES from BPF_OBJ_PIN after the eBPF object has loaded.
This profile keeps the rest of that template and allows read, write, lock, and
link under /sys/fs/bpf only.

The observe container bind-mounts host tracefs at /sys/kernel/tracing. Writes
under /sys/kernel/** stay denied. The loader's tracefs probe is a read of a
non-empty directory, and tracepoint id files are reads. uprobe_events writes
stay denied.

The text follows the moby docker-default template at v27.5.1 and v28.3.3
(`profiles/apparmor/template.go`). proof_state for this package stays
NOT_PROVED. A parsed profile is not a clean-host pin proof.
"""

from __future__ import annotations

from pathlib import Path

from vantio_install import constants

_PROFILE_NAME = "PROFILE_NAME"

# Literal braces are AppArmor alternation, not format placeholders.
_PROFILE = """#include <tunables/global>

# Observe-only Phantom Engine. Carves bpffs pin writes out of docker-default.
# Claim ceiling INTERNAL_CLEAN_HOST_PROOF. proof_state NOT_PROVED.
profile PROFILE_NAME flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  network,
  capability,
  file,
  umount,
  signal (receive) peer=unconfined,
  signal (receive) peer=runc,
  signal (receive) peer=crun,
  signal (receive) peer=docker-default,
  signal (send,receive) peer=PROFILE_NAME,

  deny @{PROC}/* w,
  deny @{PROC}/{[^1-9],[^1-9][^0-9],[^1-9s][^0-9y][^0-9s],[^1-9][^0-9][^0-9][^0-9/]*}/** w,
  deny @{PROC}/sys/[^k]** w,
  deny @{PROC}/sys/kernel/{?,??,[^s][^h][^m]**} w,
  deny @{PROC}/sysrq-trigger rwklx,
  deny @{PROC}/kcore rwklx,

  deny mount,

  # Host tracefs is bind-mounted at /sys/kernel/tracing. Writes stay denied.
  deny /sys/[^f]*/** wklx,
  deny /sys/f[^s]*/** wklx,
  deny /sys/fs/[^cb]*/** wklx,
  deny /sys/fs/b[^p]*/** wklx,
  deny /sys/fs/bp[^f]*/** wklx,
  deny /sys/fs/b wklx,
  deny /sys/fs/b/ wklx,
  deny /sys/fs/b/** wklx,
  deny /sys/fs/bp wklx,
  deny /sys/fs/bp/ wklx,
  deny /sys/fs/bp/** wklx,
  deny /sys/fs/bpf?* wklx,
  deny /sys/fs/bpf?*/** wklx,
  /sys/fs/bpf rwkl,
  /sys/fs/bpf/ rwkl,
  /sys/fs/bpf/** rwkl,
  deny /sys/fs/bpf x,
  deny /sys/fs/bpf/ x,
  deny /sys/fs/bpf/** x,
  deny /sys/fs/c[^g]*/** wklx,
  deny /sys/fs/cg[^r]*/** wklx,
  deny /sys/firmware/** rwklx,
  deny /sys/devices/virtual/powercap/** rwklx,
  deny /sys/kernel/security/** rwklx,

  ptrace (trace,read,tracedby,readby) peer=PROFILE_NAME,
}
"""


def profile_text() -> str:
    name = constants.PE_OBSERVE_APPARMOR_PROFILE
    if not name or any(char in name for char in " \t\n{}#"):
        raise ValueError("The observe AppArmor profile name is not a single token.")
    return _PROFILE.replace(_PROFILE_NAME, name)


def pe_apparmor_profile_path(stage: Path) -> Path:
    return stage / "apparmor" / constants.PE_OBSERVE_APPARMOR_PROFILE


def apparmor_profile_loaded(name: str, profiles_path: Path | None = None) -> bool | None:
    """True when the kernel lists the profile. False when it does not. None if unreadable."""
    path = profiles_path or Path("/sys/kernel/security/apparmor/profiles")
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    prefix = name + " "
    for line in text.splitlines():
        if line == name or line.startswith(prefix):
            return True
    return False


# Status, host pid, running, privileged, AppArmor profile, exit code,
# start time, finish time, container id, then the container cmd.
# docker run -d exits 0 for a detached container and for a process that has
# already exited. Status, pid, and exit code are what separate those two.
# A six-field line from older callers still parses. Exit code and times are
# then absent.
OBSERVE_INSPECT_FORMAT = (
    "{{.State.Status}} {{.State.Pid}} {{.State.Running}} "
    "{{.HostConfig.Privileged}} {{.AppArmorProfile}} "
    "{{.State.ExitCode}} {{.State.StartedAt}} {{.State.FinishedAt}} {{.Id}} "
    "{{json .Config.Cmd}}"
)

_OBSERVE_STATUSES = frozenset(
    {"created", "restarting", "running", "removing", "paused", "exited", "dead"}
)


def parse_observe_inspect(text: str) -> dict | None:
    """Parse one observe inspect line. None means the line is not that shape."""
    raw = text.strip()
    fields = raw.split(" ", 9)
    if len(fields) == 10:
        status, pid, running, privileged, profile, exit_text, started_at, finished_at, container_id, cmd = fields
        if not exit_text.isdigit():
            return None
        exit_code: int | None = int(exit_text)
    elif len(raw.split(" ", 5)) == 6:
        status, pid, running, privileged, profile, cmd = raw.split(" ", 5)
        exit_code = None
        started_at = ""
        finished_at = ""
        container_id = ""
    else:
        return None
    status = status.casefold()
    if status not in _OBSERVE_STATUSES or not pid.isdigit():
        return None
    if running not in {"true", "false"} or privileged not in {"true", "false"}:
        return None
    return {
        "status": status,
        "pid": int(pid),
        "running": running == "true",
        "privileged": privileged == "true",
        "profile": profile,
        "cmd": cmd,
        "exit_code": exit_code,
        "started_at": started_at,
        "finished_at": finished_at,
        "container_id": container_id,
    }


def inspect_is_observe_container(text: str) -> bool:
    """True when the container is running, unprivileged, and on the observe profile."""
    parsed = parse_observe_inspect(text)
    if parsed is None:
        return False
    if parsed["status"] != "running" or not parsed["running"] or parsed["pid"] <= 0:
        return False
    if parsed["privileged"]:
        return False
    if parsed["profile"] != constants.PE_OBSERVE_APPARMOR_PROFILE:
        return False
    cmd = parsed["cmd"]
    if "--enforce" in cmd or "--privileged" in cmd or "VANTIO_PHANTOM_DENY" in cmd:
        return False
    return True
