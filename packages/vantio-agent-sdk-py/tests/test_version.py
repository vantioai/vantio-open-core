"""Runtime version must match the project version."""
import pathlib
import unittest

import vantio


class VersionTests(unittest.TestCase):
    def test_runtime_version_matches_pyproject(self) -> None:
        project = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
        text = project.read_text(encoding="utf-8")
        self.assertIn('version = "3.0.15"', text)
        self.assertEqual(vantio.__version__, "3.0.15")


if __name__ == "__main__":
    unittest.main()
