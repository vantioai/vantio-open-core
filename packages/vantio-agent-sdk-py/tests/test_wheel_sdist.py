"""Local wheel and sdist carry the same runtime sources.

This is a verification build in a temp directory. It does not seal a release
candidate and it does not upload anywhere.
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _runtime_from_wheel(path: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("vantio/") and name.endswith(".py"):
                found[name] = archive.read(name)
    return found


def _runtime_from_sdist(path: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = member.name
            marker = "/vantio/"
            if marker not in name or not name.endswith(".py"):
                continue
            rel = "vantio/" + name.split(marker, 1)[1]
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            found[rel] = extracted.read()
    return found


def _metadata_text(blob: bytes) -> str:
    return blob.decode("utf-8", "replace")


class WheelSdistEquivalenceTests(unittest.TestCase):
    def test_wheel_and_sdist_runtime_sources_match(self) -> None:
        if importlib.util.find_spec("build") is None:
            self.skipTest("build is not installed; local verification installs it and does not upload")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            subprocess.run(
                [sys.executable, "-m", "build", "--outdir", str(out), str(ROOT)],
                check=True,
                capture_output=True,
                text=True,
            )
            wheels = list(out.glob("*.whl"))
            sdists = list(out.glob("*.tar.gz"))
            self.assertEqual(len(wheels), 1)
            self.assertEqual(len(sdists), 1)
            wheel, sdist = wheels[0], sdists[0]
            self.assertIn("3.1.0", wheel.name)
            self.assertIn("3.1.0", sdist.name)
            wheel_src = _runtime_from_wheel(wheel)
            sdist_src = _runtime_from_sdist(sdist)
            self.assertTrue(wheel_src)
            self.assertEqual(set(wheel_src), set(sdist_src))
            for name, data in wheel_src.items():
                self.assertEqual(hashlib.sha256(data).hexdigest(), hashlib.sha256(sdist_src[name]).hexdigest(), name)
            with zipfile.ZipFile(wheel) as archive:
                metadata = _metadata_text(
                    next(archive.read(name) for name in archive.namelist() if name.endswith("METADATA"))
                )
            self.assertIn("Name: vantio-agent-sdk", metadata)
            self.assertIn("Version: 3.1.0", metadata)
            with tarfile.open(sdist, "r:gz") as archive:
                pkg_info = next(
                    member for member in archive.getmembers() if member.name.endswith("PKG-INFO")
                )
                extracted = archive.extractfile(pkg_info)
                self.assertIsNotNone(extracted)
                info = _metadata_text(extracted.read() if extracted is not None else b"")
                sdist_license = next(
                    member for member in archive.getmembers() if member.name.endswith("/LICENSE")
                )
                sdist_license_file = archive.extractfile(sdist_license)
                self.assertIsNotNone(sdist_license_file)
                sdist_license_bytes = sdist_license_file.read() if sdist_license_file is not None else b""
            self.assertIn("Version: 3.1.0", info)
            with zipfile.ZipFile(wheel) as archive:
                wheel_license_name = next(
                    name for name in archive.namelist() if name.endswith("/LICENSE")
                )
                wheel_license_bytes = archive.read(wheel_license_name)
            packed = (ROOT / "LICENSE").read_bytes()
            self.assertEqual(wheel_license_bytes, packed)
            self.assertEqual(sdist_license_bytes, packed)
            self.assertEqual(
                hashlib.sha256(wheel_license_bytes).hexdigest(),
                hashlib.sha256(sdist_license_bytes).hexdigest(),
            )
