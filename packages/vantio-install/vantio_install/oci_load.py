"""Load path for a sealed Phantom Engine OCI tar on stock Docker.

Ubuntu 24.04's default Docker uses the containerd image store. That unpacker
trusts the layer media type. A gzip blob labeled
``application/vnd.oci.image.layer.v1.tar`` fails with
``archive/tar: invalid tar header``. ``docker load`` can still exit 0.

This module writes a temporary archive whose media type matches the bytes.
It does not modify the sealed file, and it does not change Docker's storage
driver.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path

LOAD_ARCHIVE_NAME = "pe-containerd-load.oci.tar"

_GZIP_MAGIC = b"\x1f\x8b"
_OCI_TAR = "application/vnd.oci.image.layer.v1.tar"
_OCI_GZIP = "application/vnd.oci.image.layer.v1.tar+gzip"
_DOCKER_TAR = "application/vnd.docker.image.rootfs.diff.tar"
_DOCKER_GZIP = "application/vnd.docker.image.rootfs.diff.tar.gzip"
_GZIP_MEDIA = {
    _OCI_TAR: _OCI_GZIP,
    _DOCKER_TAR: _DOCKER_GZIP,
}
_TAR_MEDIA = {value: key for key, value in _GZIP_MEDIA.items()}
_UNPACK_MARKERS = (
    "invalid tar header",
    "Error unpacking",
    "apply layer error",
    "failed to extract layer",
)


class OciArchiveError(Exception):
    """The file is an OCI layout this loader cannot correct."""


@dataclass(frozen=True)
class OciLoadPlan:
    source: Path
    load_path: Path
    image_digest: str
    rewrite: bool
    layout: str
    corrections: tuple[str, ...]
    image_tag: str | None = None


def load_output_rejected(stdout: str, stderr: str) -> bool:
    """True when docker load reported an unpack failure, including exit 0."""
    text = f"{stdout}\n{stderr}"
    return any(marker in text for marker in _UNPACK_MARKERS)


def plan_load(
    source: Path,
    stage: Path,
    *,
    fallback_digest: str,
    image_tag: str | None = None,
) -> OciLoadPlan:
    """Choose the file ``docker load`` should read.

    ``fallback_digest`` is the sealed manifest digest. A corrected load uses
    the digest of the temporary manifest instead, because that is the image
    id Docker records. The sealed file is not the load path in that case.
    """
    passthrough = OciLoadPlan(
        source=source,
        load_path=stage / source.name,
        image_digest=fallback_digest,
        rewrite=False,
        layout="absent",
        corrections=(),
    )
    if not source.is_file():
        return passthrough
    try:
        prepared = _prepare(source)
    except OciArchiveError:
        raise
    except (OSError, tarfile.TarError, json.JSONDecodeError, ValueError):
        return OciLoadPlan(
            source=source,
            load_path=stage / source.name,
            image_digest=fallback_digest,
            rewrite=False,
            layout="unrecognized",
            corrections=(),
        )
    if prepared is None:
        return OciLoadPlan(
            source=source,
            load_path=stage / source.name,
            image_digest=fallback_digest,
            rewrite=False,
            layout="unrecognized",
            corrections=(),
        )
    corrections, new_digest = prepared
    if not corrections:
        return OciLoadPlan(
            source=source,
            load_path=stage / source.name,
            image_digest=fallback_digest,
            rewrite=False,
            layout="oci",
            corrections=(),
        )
    return OciLoadPlan(
        source=source,
        load_path=stage / LOAD_ARCHIVE_NAME,
        image_digest="sha256:" + new_digest,
        rewrite=True,
        layout="oci",
        corrections=tuple(corrections),
        image_tag=image_tag,
    )


def materialize(plan: OciLoadPlan) -> None:
    """Write the temporary load archive. The sealed file is only read."""
    if not plan.rewrite:
        return
    if not plan.source.is_file():
        raise OciArchiveError("The sealed archive is not on disk.")
    sealed_before = _sha256(plan.source)
    prepared = _prepare(plan.source)
    if prepared is None or not prepared[0]:
        raise OciArchiveError("The sealed archive no longer needs a load correction.")
    _corrections, new_digest = prepared
    if plan.image_digest != "sha256:" + new_digest:
        raise OciArchiveError("The corrected manifest digest changed while writing the load archive.")
    dest = plan.load_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    _write_corrected(plan.source, partial, new_digest, plan.image_tag)
    partial.replace(dest)
    if _sha256(plan.source) != sealed_before:
        raise OciArchiveError("The sealed archive changed while the load archive was written.")


def describe_archive(path: Path) -> dict:
    """Preflight facts. A correctable mismatch is not a block."""
    if not path.is_file():
        return {
            "layout": "absent",
            "rewrite": False,
            "blocked": False,
            "corrections": [],
            "storage_driver_change": False,
        }
    try:
        prepared = _prepare(path)
    except OciArchiveError as exc:
        return {
            "layout": "oci",
            "rewrite": False,
            "blocked": True,
            "reason": str(exc),
            "corrections": [],
            "storage_driver_change": False,
        }
    except (OSError, tarfile.TarError, json.JSONDecodeError, ValueError):
        return {
            "layout": "unrecognized",
            "rewrite": False,
            "blocked": False,
            "corrections": [],
            "storage_driver_change": False,
        }
    if prepared is None:
        return {
            "layout": "unrecognized",
            "rewrite": False,
            "blocked": False,
            "corrections": [],
            "storage_driver_change": False,
        }
    corrections, _digest = prepared
    return {
        "layout": "oci",
        "rewrite": bool(corrections),
        "blocked": False,
        "corrections": corrections,
        "storage_driver_change": False,
    }


def _prepare(source: Path) -> tuple[list[str], str] | None:
    """Return corrections and the manifest digest docker will record.

    ``None`` means the file is not an OCI layout. An empty correction list
    means the media types already match the bytes. The digest in that case
    is the sealed manifest digest.
    """
    with tarfile.open(source, "r") as archive:
        names = set(archive.getnames())
        if "oci-layout" not in names or "index.json" not in names:
            return None
        index = _read_json(archive, "index.json")
        manifests = index.get("manifests")
        if not isinstance(manifests, list) or not manifests:
            raise OciArchiveError("The OCI index has no manifest.")
        corrections: list[str] = []
        # One image. A multi-manifest index is refused rather than half-corrected.
        if len(manifests) != 1 or not isinstance(manifests[0], dict):
            raise OciArchiveError("The OCI index does not contain exactly one manifest.")
        entry = manifests[0]
        digest = _digest_hex(entry.get("digest"))
        manifest_name = f"blobs/sha256/{digest}"
        if manifest_name not in names:
            raise OciArchiveError("The OCI manifest blob is missing from the archive.")
        manifest = _read_json(archive, manifest_name)
        layers = manifest.get("layers")
        if not isinstance(layers, list) or not layers:
            raise OciArchiveError("The OCI manifest has no layers.")
        for layer in layers:
            if not isinstance(layer, dict):
                raise OciArchiveError("An OCI layer entry is not an object.")
            media = str(layer.get("mediaType") or "")
            layer_digest = _digest_hex(layer.get("digest"))
            blob_name = f"blobs/sha256/{layer_digest}"
            if blob_name not in names:
                raise OciArchiveError("An OCI layer blob is missing from the archive.")
            magic = _read_prefix(archive, blob_name, 2)
            replacement = _replacement_media(media, magic)
            if replacement is None:
                continue
            if replacement == media:
                continue
            layer["mediaType"] = replacement
            corrections.append(f"{layer_digest[:12]} {media} -> {replacement}")
        manifest_bytes = _canonical(manifest)
        new_digest = hashlib.sha256(manifest_bytes).hexdigest()
        entry["digest"] = "sha256:" + new_digest
        entry["size"] = len(manifest_bytes)
        # The returned digest is the sealed one when nothing changed, so callers
        # can keep the pin. The rewritten bytes are recomputed in _write_corrected.
        if not corrections:
            return [], digest
        return corrections, new_digest


def _write_corrected(source: Path, dest: Path, new_digest: str, image_tag: str | None) -> None:
    with tarfile.open(source, "r") as archive:
        index = _read_json(archive, "index.json")
        entry = index["manifests"][0]
        old_digest = _digest_hex(entry.get("digest"))
        manifest = _read_json(archive, f"blobs/sha256/{old_digest}")
        for layer in manifest["layers"]:
            media = str(layer.get("mediaType") or "")
            layer_digest = _digest_hex(layer.get("digest"))
            magic = _read_prefix(archive, f"blobs/sha256/{layer_digest}", 2)
            replacement = _replacement_media(media, magic)
            if replacement is not None:
                layer["mediaType"] = replacement
        manifest_bytes = _canonical(manifest)
        if hashlib.sha256(manifest_bytes).hexdigest() != new_digest:
            raise OciArchiveError("The corrected manifest does not match the planned digest.")
        entry["digest"] = "sha256:" + new_digest
        entry["size"] = len(manifest_bytes)
        if image_tag:
            entry["annotations"] = _annotations(image_tag)
        index_bytes = _canonical(index)
        with tarfile.open(dest, "w", format=tarfile.USTAR_FORMAT) as out:
            for member in archive.getmembers():
                name = member.name
                if name.startswith("/") or ".." in Path(name).parts:
                    raise OciArchiveError("An archive member is outside the tar.")
                if name == "index.json":
                    _add_bytes(out, "index.json", index_bytes)
                    continue
                if name == f"blobs/sha256/{old_digest}":
                    _add_bytes(out, f"blobs/sha256/{new_digest}", manifest_bytes)
                    continue
                if not member.isfile():
                    continue
                handle = archive.extractfile(member)
                if handle is None:
                    continue
                info = tarfile.TarInfo(name=name)
                info.size = member.size
                info.mode = 0o644
                info.mtime = 0
                out.addfile(info, handle)


def _replacement_media(media: str, magic: bytes) -> str | None:
    gzip = magic == _GZIP_MAGIC
    if media in _GZIP_MEDIA and gzip:
        return _GZIP_MEDIA[media]
    if media in _TAR_MEDIA and not gzip:
        return _TAR_MEDIA[media]
    return None


def _annotations(tag: str) -> dict[str, str]:
    repo, sep, name = tag.rpartition(":")
    ref = name if sep else tag
    if repo and "/" in repo:
        image_name = tag
    else:
        image_name = f"docker.io/library/{tag}"
    return {
        "io.containerd.image.name": image_name,
        "org.opencontainers.image.ref.name": ref,
    }


def _canonical(document: dict) -> bytes:
    return json.dumps(document, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _read_json(archive: tarfile.TarFile, name: str) -> dict:
    handle = archive.extractfile(name)
    if handle is None:
        raise OciArchiveError(f"Missing {name}.")
    document = json.loads(handle.read().decode("utf-8"))
    if not isinstance(document, dict):
        raise OciArchiveError(f"{name} is not a JSON object.")
    return document


def _read_prefix(archive: tarfile.TarFile, name: str, count: int) -> bytes:
    handle = archive.extractfile(name)
    if handle is None:
        raise OciArchiveError(f"Missing {name}.")
    return handle.read(count)


def _digest_hex(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise OciArchiveError("An OCI digest is missing.")
    hex_part = value.split(":", 1)[1]
    if len(hex_part) != 64 or any(char not in "0123456789abcdef" for char in hex_part):
        raise OciArchiveError("An OCI digest is not a sha256 hex string.")
    return hex_part


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = 0
    archive.addfile(info, io.BytesIO(payload))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
