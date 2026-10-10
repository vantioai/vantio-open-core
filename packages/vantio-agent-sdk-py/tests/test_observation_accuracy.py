"""Observation-accuracy locks for the Python 3.1.1 candidate."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import vantio._http_observe as observe


class ObservationAccuracyTests(unittest.TestCase):
    def test_new_run_log_omits_the_leftover_workflow_field(self) -> None:
        home = tempfile.mkdtemp()
        previous = os.environ.get("VANTIO_HOME")
        os.environ["VANTIO_HOME"] = home
        saved_calls = list(observe._calls)
        saved_trace = observe._trace_id
        saved_started = observe._started_ms
        try:
            observe._calls.clear()
            observe._record("api.openai.com", "OBSERVED", "python_urllib", status=204, ok=True)
            observe._trace_id = "py-accuracy"
            observe._started_ms = 1
            observe._write_run_log()
            log = json.loads((Path(home) / "runs" / "py-accuracy.json").read_text(encoding="utf-8"))
        finally:
            observe._calls[:] = saved_calls
            observe._trace_id = saved_trace
            observe._started_ms = saved_started
            if previous is None:
                os.environ.pop("VANTIO_HOME", None)
            else:
                os.environ["VANTIO_HOME"] = previous
        self.assertNotIn("workflow", log)
        self.assertEqual(log["producer"], "python_observe")
        self.assertEqual(log["runtime"], "python")
        self.assertEqual(log["calls"][0]["status"], 204)

    def test_shipped_sources_omit_the_retired_product_name_and_prices(self) -> None:
        root = Path(__file__).resolve().parents[1] / "vantio"
        for path in root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("Gate", text, path.name)
            for price in ("$499", "$799", "$600", "14-day"):
                self.assertNotIn(price, text, path.name)


if __name__ == "__main__":
    unittest.main()
