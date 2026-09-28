"""Sanitized support bundle. Secret-shaped bytes are redacted before they are packed."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from vantio_install.util import canonical_json, redact_text, sha256_bytes, write_json

_ALLOWLIST = (
    "TRANSACTION.json",
    "PREFLIGHT.json",
    "PLAN.json",
    "HEALTH.json",
    "ARTIFACT-VERIFICATION.json",
    "APPLY-EVENT-LOG.jsonl",
    "RESIDUAL.json",
    "HOST-SNAPSHOT.json",
    "CONFIG.json",
)

_SKIP_NAMES = ("id_rsa", "id_dsa", "credentials", "secret.token")


def _skip(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(".pem") or name.endswith(".key"):
        return True
    return name in _SKIP_NAMES


def build_support_bundle(evidence_dir: Path, transaction_id: str, host_facts: dict) -> dict:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    members: list[tuple[str, bytes, bool]] = []
    for name in _ALLOWLIST:
        path = evidence_dir / name
        if not path.is_file() or _skip(path):
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        redacted = redact_text(raw)
        members.append((name, redacted.encode("utf-8"), redacted != raw))
    facts = redact_text(
        "\n".join(
            [
                f"uname_m={host_facts.get('uname_m', 'UNKNOWN')}",
                f"os_pretty_name={host_facts.get('os_pretty_name', 'UNKNOWN')}",
                f"kernel={host_facts.get('kernel', 'UNKNOWN')}",
                f"btf={host_facts.get('btf_vmlinux_exists', 'UNKNOWN')}",
                f"cgroup={host_facts.get('cgroup_version', 'UNKNOWN')}",
                f"docker_images={_image_names(host_facts)}",
                f"bpf_pins={','.join(host_facts.get('bpf_pins') or [])}",
                f"clsact={','.join(host_facts.get('clsact_ifaces') or [])}",
            ]
        )
        + "\n"
    )
    members.append(("HOST-FACTS.txt", facts.encode("utf-8"), False))
    index_files = [
        {"name": name, "sha256": sha256_bytes(data), "redacted": redacted}
        for name, data, redacted in members
    ]
    index = {
        "transaction_id": transaction_id,
        "files": index_files,
        "excluded_kinds": [
            "pem",
            "private_keys",
            "aws_credentials",
            "registry_tokens",
            "phantom_box_scratch",
            "crm",
        ],
    }
    index_bytes = redact_text(canonical_json(index)).encode("utf-8")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data, _redacted in members:
            _add(archive, f"evidence/{name}", data)
        _add(archive, "SUPPORT-BUNDLE-INDEX.json", index_bytes)
    blob = buffer.getvalue()
    archive_name = f"vantio-support-{transaction_id}.tar.gz"
    archive_path = evidence_dir / archive_name
    archive_path.write_bytes(blob)
    digest = sha256_bytes(blob)
    sidecar = evidence_dir / f"{archive_name}.sha256"
    sidecar.write_text(f"{digest}  {archive_name}\n", encoding="utf-8")
    index["archive_name"] = archive_name
    index["archive_sha256"] = digest
    index_path = evidence_dir / "SUPPORT-BUNDLE-INDEX.json"
    write_json(index_path, index)
    return index


def _image_names(host_facts: dict) -> str:
    names = []
    for row in host_facts.get("images") or []:
        tag = str(row.get("tag", ""))
        if tag.startswith("vantio-phantom-engine"):
            names.append(tag)
    return ",".join(names)


def _add(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))
