"""Runtime version must match the project version."""
import hashlib
import pathlib
import unittest

import vantio


class VersionTests(unittest.TestCase):
    def test_runtime_version_matches_pyproject(self) -> None:
        project = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
        text = project.read_text(encoding="utf-8")
        self.assertIn('version = "3.1.0"', text)
        self.assertEqual(vantio.__version__, "3.1.0")
        self.assertIn('license = "MIT"', text)
        self.assertIn('license-files = ["LICENSE"]', text)
        package = project.parent
        approved = package.parents[1] / "extensions" / "vantio-optics" / "LICENSE.txt"
        packed = package / "LICENSE"
        root = package.parents[1] / "LICENSE"
        self.assertFalse(root.exists())
        self.assertEqual(packed.read_bytes(), approved.read_bytes())
        self.assertEqual(hashlib.sha256(packed.read_bytes()).hexdigest(), "f41a838e502baec9034ac2011f6c8848be21ff18f2003fa22bc416a79df9bf11")
        self.assertNotIn("patent", packed.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
