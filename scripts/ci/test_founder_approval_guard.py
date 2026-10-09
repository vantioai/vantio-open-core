import importlib.util, pathlib, unittest
spec = importlib.util.spec_from_file_location("g", pathlib.Path(__file__).with_name("founder_approval_guard.py"))
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
GLOBS = ["packages/vantio-install/vantio_install/constants.py", "packages/vantio-install/docs/*", "README.md"]
ADMIN_EV = {"event": "labeled", "label": {"name": "founder-approved"}, "actor": {"login": "zacharybalicki"}}

class T(unittest.TestCase):
    def test_unprotected_passes(self):
        self.assertTrue(g.decide(g.protected_hits([{"filename": "src/x.py"}], GLOBS), set(), None, None)[0])
    def test_pin_without_label_fails(self):
        hits = g.protected_hits([{"filename": "packages/vantio-install/vantio_install/constants.py"}], GLOBS)
        self.assertFalse(g.decide(hits, set(), None, None)[0])
    def test_rename_out_of_protected_counts(self):
        self.assertTrue(g.protected_hits([{"filename": "x.md", "previous_filename": "packages/vantio-install/docs/INSTALL.md"}], GLOBS))
    def test_label_by_non_admin_fails(self):
        hits = ["README.md"]
        self.assertFalse(g.decide(hits, {"founder-approved"}, ADMIN_EV, "write")[0])
    def test_label_by_admin_passes(self):
        self.assertTrue(g.decide(["README.md"], {"founder-approved"}, ADMIN_EV, "admin")[0])
    def test_latest_event_wins(self):
        evs = [ADMIN_EV, {"event": "unlabeled", "label": {"name": "founder-approved"}, "actor": {"login": "a"}}]
        self.assertEqual(g.latest_label_event(evs)["event"], "unlabeled")

if __name__ == "__main__":
    unittest.main()
