"""The seal recipe keeps the source pin and the frozen public versions."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def _load():
    path = PACKAGE / "packaging" / "seal_customer_artifact.py"
    spec = importlib.util.spec_from_file_location("seal_customer_artifact", path)
    if spec is None or spec.loader is None:
        raise AssertionError("seal recipe missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SealRecipeTest(unittest.TestCase):
    def test_source_pin_and_frozen_versions_stay(self) -> None:
        recipe = _load()
        recipe.source_pin_intact(PACKAGE)
        text = (PACKAGE / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "0.1.0-stage-a"', text)
        self.assertNotIn('version = "0.1.0+stage.a"', text)
        self.assertIn("vantio-install =", text)
        self.assertIn("vantio-verify =", text)
        sealed = recipe.seal_version_text(text)
        self.assertIn('version = "0.1.0+stage.a"', sealed)
        self.assertNotIn('version = "0.1.0-stage-a"', sealed)
        self.assertIn("vantio-install =", sealed)
        self.assertIn("vantio-verify =", sealed)
        recipe.source_pin_intact(PACKAGE)

    def test_customer_docs_name_the_three_gaps(self) -> None:
        docs = PACKAGE / "docs"
        quick = (docs / "QUICKSTART.md").read_text(encoding="utf-8")
        install = (docs / "INSTALL.md").read_text(encoding="utf-8")
        preflight = (docs / "PREFLIGHT.md").read_text(encoding="utf-8")
        limits = (docs / "LIMITATIONS.md").read_text(encoding="utf-8")
        self.assertIn("vantio_install-0.1.0+stage.a-py3-none-any.whl", quick)
        self.assertIn("SHA256SUMS", quick)
        self.assertIn("--no-index", quick)
        wheel = (
            "/var/lib/vantio/installer-venv/bin/python -m pip install "
            "--no-index --disable-pip-version-check --no-deps <sealed-wheel>"
        )
        sdist = (
            "/var/lib/vantio/installer-venv/bin/python -m pip install "
            "--no-index --disable-pip-version-check --no-deps --no-build-isolation <sealed-sdist>"
        )
        self.assertIn(wheel, quick)
        self.assertIn(sdist, quick)
        self.assertIn("--no-build-isolation", sdist)
        self.assertNotIn("--no-build-isolation", wheel)
        self.assertNotIn("installed the same way", quick)
        self.assertNotIn("the same `pip install --no-index --no-deps` command", quick)
        self.assertIn(
            'export PYTHONPATH="/var/lib/vantio/installer-prefix/local/lib/python3.X/dist-packages"',
            quick,
        )
        self.assertIn("ModuleNotFoundError: No module named 'vantio_install'", quick)
        self.assertIn("sys.path", quick)
        self.assertIn("floating `main`", quick)
        self.assertIn("company-host path", quick)
        self.assertNotIn("Phantom Box", quick)
        self.assertNotIn("w3-aws-internal", quick)
        self.assertIn("ARTIFACT-PATH.md", quick)
        self.assertIn("GHCR", quick)
        self.assertIn("INTERNAL_CLEAN_HOST_PROOF", quick)
        self.assertIn("0.3.24", quick)
        self.assertIn("0.2.4", quick)
        self.assertIn("3.1.0", quick)
        self.assertIn("--fixture-host", install)
        self.assertIn("privilege", install)
        self.assertNotIn("fixture or rehearsal", install)
        self.assertIn("privilege_mode", preflight)
        self.assertIn("docker_group", preflight)
        self.assertIn("PF-DOCKER-PERM", preflight)
        self.assertIn("Raw `docker`", preflight)
        self.assertIn("privilege_mode", limits)
        self.assertIn("--fixture-host", limits)
        self.assertIn("INTERNAL_CLEAN_HOST_PROOF", limits)
        self.assertIn("published", limits)
        self.assertIn("ARTIFACT-PATH.md", limits)

    def test_customer_docs_use_staging_basename_only(self) -> None:
        docs = PACKAGE / "docs"
        names = (
            "ARTIFACT-PATH.md",
            "STAGE-B-ARTIFACT-PATH.md",
            "QUICKSTART.md",
            "LIMITATIONS.md",
            "PACKAGING.md",
        )
        combined = "\n".join((docs / name).read_text(encoding="utf-8") for name in names)
        artifact = (docs / "ARTIFACT-PATH.md").read_text(encoding="utf-8")
        stage_b = (docs / "STAGE-B-ARTIFACT-PATH.md").read_text(encoding="utf-8")
        basename = "vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar"
        self.assertIn(basename, artifact)
        self.assertIn(basename, stage_b)
        self.assertIn(
            "72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128",
            artifact,
        )
        self.assertIn("fab81efc08110506ff90847495197e7051a253b5", artifact)
        self.assertIn(
            "sha256:4d932b93bf4c20983142d5f9bff1ea060d9407a19a5e8c9f59db29f7a4122553",
            artifact,
        )
        self.assertIn("INTERNAL_CLEAN_HOST_PROOF", artifact)
        self.assertIn("`published` remains **false**", artifact)
        for banned in (
            "Phantom Box",
            "phantom-box",
            "w3-aws-internal",
            "VANTIO_SOAK_LOCAL",
            ":5001",
        ):
            self.assertNotIn(banned, combined)


if __name__ == "__main__":
    unittest.main()
