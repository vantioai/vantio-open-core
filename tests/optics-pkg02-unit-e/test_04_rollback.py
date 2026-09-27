"""Rollback keeps canonical files and restores the previous writer shape."""

import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path

from support import LoopbackServer

from vantio_future import force_reset, read_rolled_back, reset_writer_mode, set_writer_mode, shield
from vantio_future import writer as writer_module


class RollbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._saved = {
            key: os.environ.get(key)
            for key in ("VANTIO_HOME", "VANTIO_EXTRA_LLM_HOSTS", "VANTIO_PKG02_PYTHON_WRITER")
        }
        os.environ["VANTIO_HOME"] = self._home.name
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ.pop("VANTIO_PKG02_PYTHON_WRITER", None)
        reset_writer_mode()
        force_reset()

    def tearDown(self):
        force_reset()
        reset_writer_mode()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._home.cleanup()

    def _path(self, trace_id):
        return Path(self._home.name) / "runs" / f"{trace_id}.json"

    async def test_disable_writer_uses_previous_shape_and_keeps_canonical_file(self):
        with LoopbackServer(200) as base:
            async with shield(trace_id="unit-e-canonical"):
                response = urllib.request.urlopen(base + "/v1/chat", timeout=2)
                response.read()
                response.close()
            canonical_path = self._path("unit-e-canonical")
            before = canonical_path.read_bytes()
            canonical = json.loads(before.decode("utf-8"))
            self.assertEqual(canonical["schema_version"], 0)
            self.assertEqual(canonical["producer"], "python_observe")
            self.assertEqual(canonical["events"][0]["optics_status"], "OBSERVED")
            self.assertEqual(canonical["events"][0]["evidence_origin"], "LOCAL_OBSERVATION")
            set_writer_mode("legacy")
            async with shield(trace_id="unit-e-legacy"):
                response = urllib.request.urlopen(base + "/v1/chat", timeout=2)
                response.read()
                response.close()
            async with shield(trace_id="unit-e-legacy-empty"):
                pass
        self.assertEqual(canonical_path.read_bytes(), before)
        self.assertFalse(self._path("unit-e-legacy-empty").is_file())
        legacy = json.loads(self._path("unit-e-legacy").read_text(encoding="utf-8"))
        self.assertEqual(legacy["vantio_run_log"], "1")
        self.assertEqual(legacy["schema_version"], 2)
        self.assertEqual(legacy["workflow"], "sight_loop")
        self.assertEqual(legacy["runtime"], "python")
        self.assertNotIn("producer", legacy)
        self.assertEqual(legacy["calls"][0]["opticsStatus"], "SUCCESS")
        self.assertIn("+00:00", legacy["calls"][0]["ts"])
        self.assertNotIn("failure_kind", canonical["events"][0])
        reading = read_rolled_back(canonical_path)
        self.assertEqual(reading["optics_status"], "UNSUPPORTED")
        self.assertEqual(reading["schema_status"], "unstable-pre-1.0")
        self.assertEqual(reading["evidence_origin"], "LOCAL_OBSERVATION")
        self.assertFalse(reading["file_rewritten"])
        self.assertTrue(reading["bytes_unchanged"])
        self.assertEqual(canonical_path.read_bytes(), before)
        self.assertNotEqual(reading["optics_status"], "SUCCESS")

    async def test_validation_failure_keeps_the_return_value(self):
        sentinel = {"kept": True}

        async def work():
            async with shield(trace_id="unit-e-fail-open"):
                return sentinel

        original = writer_module.validate_evidence

        def explode(_value):
            raise RuntimeError("validator down")

        writer_module.validate_evidence = explode
        try:
            result = await work()
        finally:
            writer_module.validate_evidence = original
        self.assertIs(result, sentinel)
        self.assertFalse(self._path("unit-e-fail-open").exists())
        self.assertNotIn("validator down", json.dumps(sentinel))


if __name__ == "__main__":
    unittest.main()
