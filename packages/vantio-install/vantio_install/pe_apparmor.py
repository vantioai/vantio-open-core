"""AppArmor profile for the observe-only Phantom Engine container.

docker-default denies writes under /sys/fs/bpf (`deny /sys/fs/[^c]*/** wklx`).
That denial returns EACCES from BPF_OBJ_PIN after the eBPF object has loaded.
This profile keeps the rest of that template and allows read, write, lock, and
link under /sys/fs/bpf only.

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


def inspect_is_observe_container(text: str) -> bool:
    """Docker inspect line: running, privileged, AppArmor profile, cmd JSON."""
    parts = text.split(" ", 3)
    if len(parts) != 4:
        return False
    running, privileged, profile, cmd = parts
    if running != "true" or privileged != "false":
        return False
    if profile != constants.PE_OBSERVE_APPARMOR_PROFILE:
        return False
    if "--enforce" in cmd or "--privileged" in cmd or "VANTIO_PHANTOM_DENY" in cmd:
        return False
    return True
