"""Host preflight. The first missing control stops the run."""

from __future__ import annotations

import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

from errors import PackageError
from facts import boot_id_ok, bpf_in_lsm_list, bpffs_mounted, image_is_exact, parse_lockdown


class PreflightFailure(PackageError):
    pass


def _text(path: Path, reason: str) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise PreflightFailure(reason) from exc


def _optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _maybe_text(path: Path) -> str | None:
    """Return file text, or None when the path is missing or unreadable.

    The caller still runs the earlier preflight stops before treating None
    as an unreadable lockdown file.
    """
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def read_link_local_image(opener: Callable[..., object], timeout: float = 2) -> str:
    """Read a GCP image name from link-local metadata. Empty when it is unreachable."""
    request = urllib.request.Request(
        "http://169.254.169.254/computeMetadata/v1/instance/image",
        headers={"Metadata-Flavor": "Google"},
    )
    try:
        response = opener(request, timeout=timeout)
    except (OSError, ValueError, TimeoutError):
        return ""
    read = getattr(response, "read", None)
    close = getattr(response, "close", None)
    try:
        if not callable(read):
            return ""
        blob = read(1024)
    except (OSError, ValueError, TimeoutError):
        return ""
    finally:
        if callable(close):
            close()
    if not isinstance(blob, (bytes, bytearray)):
        return ""
    return bytes(blob).decode("utf-8", errors="replace").strip()


def cgroup_fstype(path: Path) -> str:
    try:
        proc = subprocess.run(
            ["stat", "-fc", "%T", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def choose_image(*, attestation: str, source: str, metadata: str, supplemental: Mapping[str, str]) -> dict[str, object]:
    candidates: list[tuple[str, str]] = []
    if attestation:
        candidates.append((attestation, source or "operator-attestation"))
    if metadata:
        candidates.append((metadata.rsplit("/", 1)[-1], "metadata"))
    for name, origin in candidates:
        if image_is_exact(name, source=origin):
            return {"exact": name, "source": origin, "supplemental": dict(supplemental)}
    return {"exact": "", "source": "", "supplemental": dict(supplemental)}


def evaluate(
    *,
    enabled_lsm: str,
    btf_bytes: int,
    cgroup_fstype_name: str,
    lockdown_raw: str | None,
    mounts: str,
    boot_id: str,
    cmdline: str,
    uname_release: str,
    uname_version: str,
    image: Mapping[str, object],
) -> dict[str, object]:
    """Grade already-read bytes. Callers read each file once."""
    if not isinstance(enabled_lsm, str) or not bpf_in_lsm_list(enabled_lsm):
        raise PreflightFailure("bpf_lsm_inactive")
    if type(btf_bytes) is not int or btf_bytes <= 0:
        raise PreflightFailure("btf_missing")
    if cgroup_fstype_name != "cgroup2fs":
        raise PreflightFailure("cgroup_v2_missing")
    if not isinstance(lockdown_raw, str):
        raise PreflightFailure("lockdown_unreadable")
    try:
        mode = parse_lockdown(lockdown_raw)
    except ValueError as exc:
        raise PreflightFailure("lockdown_unreadable") from exc
    if mode == "confidentiality":
        raise PreflightFailure("lockdown_confidentiality")
    if not bpffs_mounted(mounts):
        raise PreflightFailure("bpffs_missing")
    exact = image.get("exact") if isinstance(image, Mapping) else ""
    source = image.get("source") if isinstance(image, Mapping) else ""
    if not image_is_exact(exact, source=source):
        raise PreflightFailure("image_exact_missing")
    recorded_boot = boot_id.strip() if isinstance(boot_id, str) else ""
    if not boot_id_ok(recorded_boot):
        raise PreflightFailure("boot_id")
    supplemental = image.get("supplemental") if isinstance(image, Mapping) else {}
    return {
        "boot_id": recorded_boot,
        "bpffs": True,
        "btf_bytes": btf_bytes,
        "cgroup_fstype": cgroup_fstype_name,
        "cmdline": cmdline.strip(),
        "enabled_lsm": enabled_lsm.strip(),
        "image": {
            "exact": exact,
            "source": source,
            "supplemental": dict(supplemental) if isinstance(supplemental, Mapping) else {},
        },
        "kernel_btf": True,
        "kernel_cgroup_v2": True,
        "lockdown_mode": mode,
        "lockdown_raw": lockdown_raw.strip(),
        "uname_release": uname_release,
        "uname_version": uname_version,
    }


def supplemental_from_root(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    os_release = root / "etc/os-release"
    if os_release.is_file():
        found["os_release"] = os_release.read_text(encoding="utf-8", errors="replace")[:2000]
    build = root / "etc/cloud/build.info"
    if build.is_file():
        found["cloud_build"] = build.read_text(encoding="utf-8", errors="replace")[:2000]
    return found


def collect_host(
    root: Path,
    *,
    attestation: str = "",
    source: str = "operator-attestation",
    metadata: str = "",
    cgroup_name: str | None = None,
    uname_release: str | None = None,
    uname_version: str | None = None,
) -> dict[str, object]:
    lsm_path = root / "sys/kernel/security/lsm"
    if not lsm_path.is_file():
        raise PreflightFailure("bpf_lsm_inactive")
    enabled = _text(lsm_path, "bpf_lsm_inactive")
    btf = root / "sys/kernel/btf/vmlinux"
    try:
        btf_bytes = btf.stat().st_size if btf.is_file() else 0
    except OSError:
        btf_bytes = 0
    if cgroup_name is None:
        cgroup_name = cgroup_fstype(root / "sys/fs/cgroup")
    lockdown_raw = _maybe_text(root / "sys/kernel/security/lockdown")
    mounts = _optional(root / "proc/mounts")
    boot_id = _optional(root / "proc/sys/kernel/random/boot_id")
    cmdline = _optional(root / "proc/cmdline")
    info = os.uname()
    image = choose_image(
        attestation=attestation,
        source=source,
        metadata=metadata,
        supplemental=supplemental_from_root(root),
    )
    return evaluate(
        enabled_lsm=enabled,
        btf_bytes=btf_bytes,
        cgroup_fstype_name=cgroup_name,
        lockdown_raw=lockdown_raw,
        mounts=mounts,
        boot_id=boot_id,
        cmdline=cmdline,
        uname_release=uname_release if uname_release is not None else info.release,
        uname_version=uname_version if uname_version is not None else info.version,
        image=image,
    )
