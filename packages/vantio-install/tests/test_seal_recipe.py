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
        self.assertIn("floating `main`", quick)
        self.assertIn("Phantom Box", quick)
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


if __name__ == "__main__":
    unittest.main()
