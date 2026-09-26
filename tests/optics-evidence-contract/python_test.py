"""PKG-01 Python validator tests. Stdlib only."""

import copy
import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "packages" / "optics-evidence-contract" / "src"
sys.path.insert(0, str(SRC))

import validate  # noqa: E402

CORPUS = json.loads((pathlib.Path(__file__).parent / "corpus.json").read_text(encoding="utf-8"))
REMEDIATION = {
    "NONE",
    "REVIEW_DESTINATION_SHAPE",
    "REVIEW_SESSION_ID",
    "REVIEW_TRACE_CONTEXT",
    "REMOVE_PROHIBITED_CONTENT",
    "ORIGIN_UNMARKED",
    "DEMO_NOT_OPERATIONAL",
    "ENFORCEMENT_NOT_OPTICS",
    "VALIDATOR_INTERNAL",
}


def materialize(item):
    if "input" in item:
        return copy.deepcopy(item["input"])
    data = copy.deepcopy(CORPUS["bases"][item["base"]])
    for key in item.get("omit", []):
        data.pop(key, None)
    for key, value in (item.get("patch") or {}).items():
        data[key] = copy.deepcopy(value)
    return data


def dump_canonical():
    out = {}
    for item in CORPUS["cases"]:
        out[item["id"]] = validate.canonical_json(validate.validate_evidence(materialize(item)))
    return out


class ContractTests(unittest.TestCase):
    def test_corpus(self):
        self.assertGreaterEqual(len(CORPUS["cases"]), 70)
        for item in CORPUS["cases"]:
            self._assert_result(item, validate.validate_evidence(materialize(item)))

    def test_cross_language(self):
        dump_path = "/tmp/pkg01-node-dump.json"
        env = dict(os.environ)
        env["PKG01_DUMP_PATH"] = dump_path
        proc = subprocess.run(
            ["node", str(pathlib.Path(__file__).parent / "node.test.cjs"), "--dump"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        theirs = json.loads(pathlib.Path(dump_path).read_text(encoding="utf-8"))
        ours = dump_canonical()
        for key, value in ours.items():
            self.assertEqual(theirs[key], value, key)

    def test_fail_open(self):
        app = {"ok": True, "token": "APP_RESULT"}
        secret = validate.validate_evidence(
            {"record_type": "observation_event", "path": "/sk-CANARYOPENAI0001"},
            {"applicationResult": app},
        )
        self.assertIs(secret["application_result"], app)
        self.assertNotIn("CANARYOPENAI", validate.canonical_json(secret))
        dropped = validate.validate_evidence(
            {"record_type": "observation_event", "prompt": "sk-CANARYPROMPT0001"},
            {"applicationResult": app},
        )
        self.assertIs(dropped["application_result"], app)
        self.assertIsNone(dropped["record"])
        fault = validate.validate_evidence(
            {"record_type": "observation_event"},
            {"applicationResult": app, "injectFault": True},
        )
        self.assertEqual(fault["reason_code"], "VALIDATOR_FAULT")
        self.assertIs(fault["application_result"], app)
        self.assertNotIn("injected", validate.canonical_json(fault))
        bad = validate.validate_bytes(bytes([0xFF, 0xFE, 0xFD]), {"applicationResult": app})
        self.assertEqual(bad["reason_code"], "MALFORMED_UTF8")
        self.assertIs(bad["application_result"], app)
        huge = "x" * 2000000
        bounded = validate.validate_evidence(huge, {"applicationResult": app})
        self.assertEqual(bounded["reason_code"], "INPUT_BOUND")
        self.assertIs(bounded["application_result"], app)
        self.assertNotIn("xxxx", validate.canonical_json(bounded))

    def test_hostile_cycle_nesting(self):
        class Hostile(dict):
            def keys(self):
                return list(dict.keys(self)) + ["boom"]

            def __getitem__(self, key):
                if key == "boom":
                    raise RuntimeError("getter-secret")
                return dict.__getitem__(self, key)

        hostile = Hostile(record_type="observation_event")
        result = validate.validate_evidence(hostile)
        self.assertEqual(result["reason_code"], "HOSTILE_INPUT")
        self.assertNotIn("getter-secret", validate.canonical_json(result))
        cycle = {}
        cycle["self"] = cycle
        self.assertEqual(validate.validate_evidence(cycle)["reason_code"], "CYCLE_REJECTED")
        nested = {"leaf": True}
        for _ in range(20):
            nested = {"child": nested}
        self.assertEqual(validate.validate_evidence(nested)["reason_code"], "EXCESSIVE_NESTING")
        lone = validate.validate_evidence({
            "record_type": "observation_event",
            "schema_status": "unstable-pre-1.0",
            "schema_version": 0,
            "session_id": "\ud800",
            "session_id_basis": "APPLICATION_SUPPLIED",
        })
        self.assertEqual(lone["reason_code"], "SESSION_ID_REJECTED")
        record = lone["record"] or {}
        self.assertNotIn("session_id", record)

    def test_array_drop(self):
        result = validate.validate_evidence(["sk-CANARYARRAY0001"])
        self.assertEqual(result["reason_code"], "PROMPT_COMPLETION_EXCLUDED")
        self.assertIsNone(result["record"])
        self.assertNotIn("CANARYARRAY", validate.canonical_json(result))

    def test_scope(self):
        cli = json.loads((ROOT / "packages" / "vantio-cli" / "package.json").read_text(encoding="utf-8"))
        pyproject = (ROOT / "packages" / "vantio-agent-sdk-py" / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(cli["version"], "0.3.24")
        self.assertIn('version = "3.1.0"', pyproject)
        pkg = json.loads((ROOT / "packages" / "optics-evidence-contract" / "package.json").read_text(encoding="utf-8"))
        self.assertTrue(pkg["private"])
        self.assertNotIn("dependencies", pkg)
        meta = json.loads(
            (ROOT / "packages" / "optics-evidence-contract" / "contract" / "contract-metadata.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(meta["stable_schema"])
        self.assertEqual(meta["schema_version"], 0)
        outcome = (ROOT / "packages" / "vantio-agent-sdk-py" / "vantio" / "_outcome.py").read_text(encoding="utf-8")
        self.assertIn('SCHEMA_STATUS = "unstable-pre-1.0"', outcome)
        for base in (ROOT / "packages" / "vantio-cli", ROOT / "packages" / "vantio-agent-sdk-py"):
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {".py", ".js", ".cjs", ".mjs", ".toml", ".json", ".md"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                self.assertNotIn("optics-evidence-contract", text, str(path))

    def _assert_result(self, item, result):
        expect = item["expect"]
        canon = validate.canonical_json(result)
        ident = item["id"]
        self.assertEqual(result["schema_status"], "unstable-pre-1.0", ident)
        self.assertEqual(result["schema_version"], 0, ident)
        self.assertFalse(result["diagnostics"]["scope_complete"], ident)
        self.assertFalse(result["completeness_inputs"]["scope_complete"], ident)
        self.assertEqual(result["completeness_inputs"]["integrity_state"], "UNKNOWN", ident)
        self.assertEqual(result["completeness_inputs"]["sampling"], "UNSAMPLED", ident)
        self.assertFalse(result["compatibility"]["live_writer_modified"], ident)
        self.assertEqual(result["disposition"], expect["disposition"], ident)
        self.assertEqual(result["reason_code"], expect["reason_code"], ident)
        self.assertEqual(result["issue_location"], expect["issue_location"], ident)
        self.assertEqual(result["optics_health_impact"], expect["optics_health_impact"], ident)
        self.assertEqual(result["completeness_impact"], expect["completeness_impact"], ident)
        self.assertEqual(result["remediation_code"], expect["remediation_code"], ident)
        self.assertIn(result["remediation_code"], REMEDIATION, ident)
        self.assertEqual(result["record_emitted"], expect["record_emitted"], ident)
        self.assertNotEqual(result["issue_location_label"], "Provider fault", ident)
        if "reader_origin_label" in expect:
            self.assertEqual(result["reader_origin_label"], expect["reader_origin_label"], ident)
        if "issue_location_label" in expect:
            self.assertEqual(result["issue_location_label"], expect["issue_location_label"], ident)
        if "health_impact" in expect:
            self.assertEqual(result["health_impact"], expect["health_impact"], ident)
        if "stripped" in expect:
            self.assertEqual(result["fields"]["stripped"], expect["stripped"], ident)
        if "rejected" in expect:
            self.assertEqual(result["fields"]["rejected"], expect["rejected"], ident)
        if "compatibility" in expect:
            self.assertEqual(result["compatibility"], expect["compatibility"], ident)
        for key, value in (expect.get("diagnostics") or {}).items():
            self.assertEqual(result["diagnostics"][key], value, ident + " " + key)
        if expect["record_emitted"]:
            for key, value in (expect.get("record") or {}).items():
                self.assertEqual(result["record"].get(key), value, ident + " " + key)
            for key in expect.get("record_absent") or []:
                self.assertNotIn(key, result["record"], ident + " absent " + key)
        else:
            self.assertIsNone(result["record"], ident)
        if "event0" in expect:
            child = result["events"][0]
            event = expect["event0"]
            if "disposition" in event:
                self.assertEqual(child["disposition"], event["disposition"], ident)
            if "reason_code" in event:
                self.assertEqual(child["reason_code"], event["reason_code"], ident)
            if "reader_origin_label" in event:
                self.assertEqual(child["reader_origin_label"], event["reader_origin_label"], ident)
            for key, value in (event.get("record") or {}).items():
                self.assertEqual(child["record"][key], value, ident + " event " + key)
        for token in expect.get("forbidden") or []:
            self.assertNotIn(token, canon, ident + " leaked " + token)


if __name__ == "__main__":
    if "--dump" in sys.argv:
        payload = json.dumps(dump_canonical())
        target = os.environ.get("PKG01_DUMP_PATH")
        if target:
            pathlib.Path(target).write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
            sys.stdout.flush()
        sys.exit(0)
    unittest.main()
