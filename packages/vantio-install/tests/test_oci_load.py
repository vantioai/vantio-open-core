"""OCI load correction for containerd's snapshotter. No Docker daemon required."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from vantio_install.oci_load import (
    LOAD_ARCHIVE_NAME,
    describe_archive,
    load_output_rejected,
    materialize,
    plan_load,
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _gzip(payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as handle:
        handle.write(payload)
    return buffer.getvalue()


def _layer_tar() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        payload = b"hello"
        info = tarfile.TarInfo("hello.txt")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _pack(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, payload in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _oci_tar(*, media_type: str, gzip_layer: bool) -> bytes:
    layer = _layer_tar()
    blob = _gzip(layer) if gzip_layer else layer
    blob_digest = _sha256(blob)
    config = b'{"architecture":"amd64","os":"linux"}'
    config_digest = _sha256(config)
    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": "sha256:" + config_digest,
            "size": len(config),
        },
        "layers": [
            {
                "mediaType": media_type,
                "digest": "sha256:" + blob_digest,
                "size": len(blob),
            }
        ],
    }
    manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    manifest_digest = _sha256(manifest_bytes)
    index = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": "sha256:" + manifest_digest,
                "size": len(manifest_bytes),
                "annotations": {
                    "org.opencontainers.image.ref.name": "example",
                    "io.containerd.image.name": "docker.io/library/example:example",
                },
            }
        ],
    }
    index_bytes = json.dumps(index, separators=(",", ":")).encode("utf-8")
    return _pack(
        {
            "oci-layout": b'{"imageLayoutVersion":"1.0.0"}',
            "index.json": index_bytes,
            f"blobs/sha256/{config_digest}": config,
            f"blobs/sha256/{manifest_digest}": manifest_bytes,
            f"blobs/sha256/{blob_digest}": blob,
        }
    )


def _media_type(path: Path) -> str:
    with tarfile.open(path, "r") as archive:
        index = json.loads(archive.extractfile("index.json").read())
        digest = index["manifests"][0]["digest"].split(":", 1)[1]
        manifest = json.loads(archive.extractfile(f"blobs/sha256/{digest}").read())
    return manifest["layers"][0]["mediaType"]


class OciLoadTest(unittest.TestCase):
    def test_gzip_bytes_labeled_uncompressed_are_corrected(self) -> None:
        raw = _oci_tar(media_type="application/vnd.oci.image.layer.v1.tar", gzip_layer=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sealed.oci.tar"
            stage = root / "stage"
            stage.mkdir()
            source.write_bytes(raw)
            before = hashlib.sha256(raw).hexdigest()
            plan = plan_load(
                source,
                stage,
                fallback_digest="sha256:" + "a" * 64,
                image_tag="vantio-phantom-engine:example",
            )
            self.assertTrue(plan.rewrite)
            self.assertEqual(plan.load_path.name, LOAD_ARCHIVE_NAME)
            self.assertNotEqual(plan.image_digest, "sha256:" + "a" * 64)
            materialize(plan)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            self.assertEqual(
                _media_type(plan.load_path),
                "application/vnd.oci.image.layer.v1.tar+gzip",
            )
            with tarfile.open(plan.load_path, "r") as archive:
                index = json.loads(archive.extractfile("index.json").read())
            self.assertEqual(index["manifests"][0]["digest"], plan.image_digest)
            self.assertEqual(
                index["manifests"][0]["annotations"]["org.opencontainers.image.ref.name"],
                "example",
            )
            facts = describe_archive(source)
            self.assertTrue(facts["rewrite"])
            self.assertFalse(facts["blocked"])
            self.assertFalse(facts["storage_driver_change"])

    def test_matching_gzip_media_type_is_loaded_as_sealed(self) -> None:
        raw = _oci_tar(media_type="application/vnd.oci.image.layer.v1.tar+gzip", gzip_layer=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sealed.oci.tar"
            source.write_bytes(raw)
            plan = plan_load(source, root, fallback_digest="sha256:" + "b" * 64)
            self.assertFalse(plan.rewrite)
            self.assertEqual(plan.image_digest, "sha256:" + "b" * 64)
            self.assertEqual(plan.load_path, root / "sealed.oci.tar")
            facts = describe_archive(source)
            self.assertFalse(facts["rewrite"])
            self.assertEqual(facts["layout"], "oci")

    def test_unrecognized_file_stays_on_the_sealed_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "notes.txt"
            source.write_text("not an archive", encoding="utf-8")
            plan = plan_load(source, root, fallback_digest="sha256:" + "c" * 64)
            self.assertFalse(plan.rewrite)
            self.assertEqual(plan.layout, "unrecognized")
            facts = describe_archive(source)
            self.assertFalse(facts["blocked"])

    def test_unpack_error_text_is_rejected_even_with_loaded_image(self) -> None:
        text = (
            "Loaded image: vantio-phantom-engine:pe-residuals-06696d5\n"
            "Error unpacking image: failed to extract layer sha256:34467cc9: "
            "archive/tar: invalid tar header\n"
        )
        self.assertTrue(load_output_rejected(text, ""))
        self.assertFalse(load_output_rejected("Loaded image: vantio-phantom-engine:example\n", ""))


if __name__ == "__main__":
    unittest.main()
