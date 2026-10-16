"""The R15 note is design only and does not claim a loader change."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "planning" / "cgroup-skb-lifecycle" / "00-OPTIONS.md"


class R15DesignTests(unittest.TestCase):
    def test_options_and_labels(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("cgroup_skb_egress_enforce", text)
        self.assertIn("Option A — keep enforcing", text)
        self.assertIn("Option B — detach when the container exits", text)
        self.assertIn("bc-8b310b16", text)
        self.assertIn("**Roadmap**", text)
        self.assertIn("**Lab-only**", text)
        self.assertIn("does not choose an option", text)
        self.assertIn("The loader is not modified", text)
        self.assertNotIn("$", text)
        for banned in ("unbreakable", "audited", "Navera", "navera"):
            self.assertNotIn(banned, text)

    def test_no_loader_edit_in_this_commit_tree(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("Not in this commit. Not Verified", text)
        self.assertIn("scripts/aws", text)
        self.assertIn("scripts/gcp", text)


if __name__ == "__main__":
    unittest.main()
