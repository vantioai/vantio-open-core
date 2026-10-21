import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from vantio import _http_observe


class LiveDestinationTest(unittest.TestCase):
    def test_first_connection_is_flagged_with_a_clock_time(self) -> None:
        home = tempfile.mkdtemp()
        previous = os.environ.get("VANTIO_HOME")
        os.environ["VANTIO_HOME"] = home
        _http_observe._trace_id = "py-live"
        try:
            _http_observe._note_live({
                "hostname": "billing.internal.example",
                "path": "/v1/tools?token=secret-canary",
                "method": "POST",
                "bytes": 10,
                "ts": "2026-10-21T18:02:07+00:00",
                "prompt": "PROMPT-CANARY",
            })
            _http_observe._note_live({
                "hostname": "billing.internal.example",
                "path": "/v1/tools",
                "method": "POST",
                "bytes": 10,
                "ts": "2026-10-21T18:03:07+00:00",
            })
            lines = Path(home, "live.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["flag"], "new_destination")
            first_clock = datetime.fromisoformat("2026-10-21T18:02:07+00:00").astimezone().strftime("%H:%M:%S")
            second_clock = datetime.fromisoformat("2026-10-21T18:03:07+00:00").astimezone().strftime("%H:%M:%S")
            self.assertEqual(first["clock"], first_clock)
            self.assertEqual(second["clock"], second_clock)
            self.assertEqual(first["time"], "2026-10-21T18:02:07+00:00")
            self.assertEqual(first["path"], "/v1/tools")
            self.assertEqual(second["flag"], None)
            self.assertNotIn("PROMPT-CANARY", "\n".join(lines))
            self.assertNotIn("secret-canary", "\n".join(lines))
        finally:
            if previous is None:
                os.environ.pop("VANTIO_HOME", None)
            else:
                os.environ["VANTIO_HOME"] = previous


if __name__ == "__main__":
    unittest.main()
