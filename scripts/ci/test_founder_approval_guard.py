import importlib.util, pathlib, unittest
spec = importlib.util.spec_from_file_location("g", pathlib.Path(__file__).with_name("founder_approval_guard.py"))
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
GLOBS = ["packages/vantio-install/vantio_install/constants.py", "packages/vantio-install/docs/*", "README.md"]
ADMIN_EV = {
    "event": "labeled",
    "label": {"name": "founder-approved"},
    "actor": {"login": "zacharybalicki"},
    "created_at": "2026-10-10T00:00:02Z",
}
HEAD_BEFORE_LABEL = "2026-10-10T00:00:01Z"
LABEL_TIME = "2026-10-10T00:00:02Z"

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
        self.assertFalse(g.decide(hits, {"founder-approved"}, ADMIN_EV, "write", HEAD_BEFORE_LABEL, "labeled")[0])
    def test_label_by_admin_passes(self):
        self.assertTrue(g.decide(["README.md"], {"founder-approved"}, ADMIN_EV, "admin", LABEL_TIME, "labeled")[0])
    def test_admin_label_older_than_update_fails(self):
        self.assertFalse(g.decide(["README.md"], {"founder-approved"}, ADMIN_EV, "admin", "2026-10-10T00:00:03Z", "edited")[0])
    def test_same_timestamp_is_fresh_only_on_the_label_action(self):
        self.assertTrue(g.decide(["README.md"], {"founder-approved"}, ADMIN_EV, "admin", LABEL_TIME, "labeled")[0])
        self.assertFalse(g.decide(["README.md"], {"founder-approved"}, ADMIN_EV, "admin", LABEL_TIME, "edited")[0])
    def test_admin_label_without_update_time_fails(self):
        self.assertFalse(g.decide(["README.md"], {"founder-approved"}, ADMIN_EV, "admin", None, "labeled")[0])
    def test_body_text_is_not_an_input(self):
        self.assertFalse(g.decide(["README.md"], set(), None, None, None, "edited")[0])
    def test_latest_event_wins(self):
        evs = [ADMIN_EV, {"event": "unlabeled", "label": {"name": "founder-approved"}, "actor": {"login": "a"}}]
        self.assertEqual(g.latest_label_event(evs)["event"], "unlabeled")

if __name__ == "__main__":
    unittest.main()
