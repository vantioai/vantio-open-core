"""PKG-01 Python validator tests. Stdlib only."""

import copy
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "packages" / "optics-evidence-contract" / "src"
sys.path.insert(0, str(SRC))

import privacy  # noqa: E402
import unicode_profile  # noqa: E402
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


class _Accessor(object):
    calls = 0

    @property
    def boom(self):
        _Accessor.calls += 1
        return "getter-secret"


class _PlainBox(object):
    def __init__(self):
        self.record_type = "observation_event"


def _plain_fn():
    return "CANARYFUNC0001"


class _ProxyLike(dict):
    calls = 0

    def keys(self):
        _ProxyLike.calls += 1
        return list(dict.keys(self))

    def __getitem__(self, key):
        _ProxyLike.calls += 1
        if key == "boom":
            raise RuntimeError("getter-secret")
        return dict.__getitem__(self, key)


def materialize(item):
    if "input" in item:
        return copy.deepcopy(item["input"])
    data = copy.deepcopy(CORPUS["bases"][item["base"]])
    for key in item.get("omit", []):
        data.pop(key, None)
    for key, value in (item.get("patch") or {}).items():
        data[key] = copy.deepcopy(value)
    return data


def _worker_result():
    proc = subprocess.run(
        [sys.executable, str(pathlib.Path(__file__).parent / "hostile_worker.py"), "validate"],
        check=False,
        capture_output=True,
        text=True,
        timeout=2,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    line, _, body = proc.stdout.partition("\n")
    if line != "CALLS 0":
        raise AssertionError(line)
    return json.loads(body)


def run_case(item):
    harness = item.get("harness")
    if harness == "accessor":
        _Accessor.calls = 0
        result = validate.validate_evidence(_Accessor())
        if _Accessor.calls != 0:
            raise AssertionError(item["id"])
        return result
    if harness == "proxy":
        _ProxyLike.calls = 0
        result = validate.validate_evidence(_ProxyLike(record_type="observation_event"))
        if _ProxyLike.calls != 0:
            raise AssertionError(item["id"])
        return result
    if harness == "class":
        return validate.validate_evidence(_PlainBox())
    if harness == "function":
        return validate.validate_evidence(_plain_fn)
    if harness == "function-field":
        return validate.validate_evidence({"record_type": "observation_event", "note": _plain_fn})
    if harness == "nonreturning":
        return _worker_result()
    if harness == "binary-buffer":
        return validate.validate_evidence(bytes([9, 8, 7]))
    if harness == "binary-uint8array":
        return validate.validate_evidence(bytearray([9, 8, 7]))
    if harness == "binary-memoryview":
        return validate.validate_evidence(memoryview(bytes([9, 8, 7])))
    return validate.validate_evidence(materialize(item))


def dump_canonical():
    out = {}
    for item in CORPUS["cases"]:
        out[item["id"]] = validate.canonical_json(run_case(item))
    return out


class ContractTests(unittest.TestCase):
    def test_corpus(self):
        self.assertEqual(len(CORPUS["cases"]), 220)
        banned = ("CANARY", "sk-", "AKIA", "ghp_", "AIza", "BEGIN PRIVATE", "canary.person", "sk-CANARYKEYNAME0001")
        for item in CORPUS["cases"]:
            self._assert_result(item, run_case(item))
        for ident, canon in dump_canonical().items():
            for token in banned:
                self.assertNotIn(token, canon, ident + " " + token)

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
        app = {"ok": True, "token": "APP_RESULT", "nested": {"n": 1}}
        secret = validate.validate_evidence(
            {"record_type": "observation_event", "path": "/sk-CANARYOPENAI0001"},
            {"applicationResult": app},
        )
        self.assertEqual(secret["application_result"], app)
        self.assertIsNot(secret["application_result"], app)
        self.assertIsNot(secret["application_result"]["nested"], app["nested"])
        app["nested"]["n"] = 2
        self.assertEqual(secret["application_result"]["nested"]["n"], 1)
        secret["application_result"]["nested"]["n"] = 9
        self.assertEqual(app["nested"]["n"], 2)
        self.assertNotIn("CANARYOPENAI", validate.canonical_json(secret))
        dropped = validate.validate_evidence(
            {"record_type": "observation_event", "prompt": "sk-CANARYPROMPT0001"},
            {"applicationResult": app},
        )
        self.assertEqual(dropped["application_result"]["token"], "APP_RESULT")
        self.assertIsNot(dropped["application_result"], app)
        self.assertIsNone(dropped["record"])
        fault = validate.validate_evidence(
            {"record_type": "observation_event"},
            {"applicationResult": app, "injectFault": True},
        )
        self.assertEqual(fault["reason_code"], "VALIDATOR_FAULT")
        self.assertEqual(fault["application_result"]["token"], "APP_RESULT")
        self.assertIsNot(fault["application_result"], app)
        self.assertNotIn("injected", validate.canonical_json(fault))
        bad = validate.validate_bytes(bytes([0xFF, 0xFE, 0xFD]), {"applicationResult": app})
        self.assertEqual(bad["reason_code"], "MALFORMED_UTF8")
        self.assertEqual(bad["application_result"]["token"], "APP_RESULT")
        self.assertIsNot(bad["application_result"], app)
        huge = "x" * 2000000
        bounded = validate.validate_evidence(huge, {"applicationResult": app})
        self.assertEqual(bounded["reason_code"], "INPUT_BOUND")
        self.assertEqual(bounded["application_result"]["token"], "APP_RESULT")
        self.assertIsNot(bounded["application_result"], app)
        self.assertNotIn("xxxx", validate.canonical_json(bounded))

    def test_hostile_cycle_nesting(self):
        _ProxyLike.calls = 0
        hostile = _ProxyLike(record_type="observation_event")
        result = validate.validate_evidence(hostile)
        self.assertEqual(_ProxyLike.calls, 0)
        self.assertEqual(result["reason_code"], "ACCESSOR_PROPERTY_FORBIDDEN")
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

    def test_input_mutation(self):
        item = next(case for case in CORPUS["cases"] if case["id"] == "mutable-nested-input")
        source = materialize(item)
        source["nested"] = {"n": 1}
        snapshot = copy.deepcopy(source)
        result = validate.validate_evidence(source)
        self.assertEqual(source, snapshot)
        source["destination_host"] = "changed.example"
        source["nested"]["n"] = 4
        self.assertEqual(result["record"]["destination_host"], "api.example.com")
        canon = validate.canonical_json(result)
        self.assertNotIn("changed.example", canon)
        self.assertNotIn('"n"', canon)

    def test_isolated_getter(self):
        proc = subprocess.run(
            [sys.executable, str(pathlib.Path(__file__).parent / "hostile_worker.py"), "validate"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith("CALLS 0\n"))
        self.assertIn("ACCESSOR_PROPERTY_FORBIDDEN", proc.stdout)
        try:
            hang = subprocess.run(
                [sys.executable, str(pathlib.Path(__file__).parent / "hostile_worker.py"), "hang"],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.5,
            )
        except subprocess.TimeoutExpired:
            hang = None
        if hang is not None:
            self.assertNotEqual(hang.returncode, 0)

    def test_no_network_imports(self):
        root = ROOT / "packages" / "optics-evidence-contract" / "src"
        names = (
            "validate.py", "privacy.py", "walk.py", "canonical.py", "unicode_profile.py",
            "validate.cjs", "privacy.cjs", "walk.cjs", "canonical.cjs", "unicode_profile.cjs",
        )
        text = "\n".join((root / name).read_text(encoding="utf-8") for name in names)
        self.assertNotIn('require("http")', text)
        self.assertNotIn('require("net")', text)
        self.assertNotIn("import urllib", text)
        self.assertNotIn("import socket", text)
        self.assertNotIn("import requests", text)
        detectors = "\n".join(
            (root / name).read_text(encoding="utf-8")
            for name in ("privacy.py", "privacy.cjs", "unicode_profile.py", "unicode_profile.cjs")
        )
        for token in (
            "isalpha", "isalnum", "casefold", "toLowerCase", "toUpperCase", ".lower(", ".upper(", "toLocale",
            ".normalize(", "unicodedata", "\\p{L}", "\\p{N}", "Intl.",
        ):
            self.assertNotIn(token, detectors, token)
        generator = (ROOT / "packages" / "optics-evidence-contract" / "tools" / "generate_unicode_profile.py").read_text(
            encoding="utf-8"
        )
        for token in ("urllib", "import socket", "requests", "import unicodedata", "unicodedata."):
            self.assertNotIn(token, generator, token)
        classes = json.loads((ROOT / "packages" / "optics-evidence-contract" / "contract" / "detector-classes.json").read_text(encoding="utf-8"))
        bounds = json.loads((ROOT / "packages" / "optics-evidence-contract" / "contract" / "normalization.json").read_text(encoding="utf-8"))
        self.assertEqual(classes["length_unit"], "UTF-8_BYTES")
        self.assertEqual(bounds["length_unit"], "UTF-8_BYTES")
        self.assertEqual(classes["max_scan_bytes"], bounds["bounds"]["max_string_chars"])

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
        if "accepted" in expect:
            self.assertEqual(result["fields"]["accepted"], expect["accepted"], ident)
        if "normalized" in expect:
            self.assertEqual(result["fields"]["normalized"], expect["normalized"], ident)
        data = materialize(item) if item.get("utf8") else None
        for spec in item.get("utf8") or []:
            if "field" in spec:
                self.assertEqual(len(str(data[spec["field"]]).encode("utf-8")), spec["bytes"], ident + " " + spec["field"])
            if "field_name_bytes" in spec:
                self.assertTrue(any(len(key.encode("utf-8")) == spec["field_name_bytes"] for key in data), ident)
        if "compatibility" in expect:
            self.assertEqual(result["compatibility"], expect["compatibility"], ident)
        for key, value in (expect.get("diagnostics") or {}).items():
            self.assertEqual(result["diagnostics"][key], value, ident + " " + key)
        for key, value in (expect.get("completeness_inputs") or {}).items():
            self.assertEqual(result["completeness_inputs"][key], value, ident + " " + key)
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

    def test_pinned_unicode_tables(self):
        contract = ROOT / "packages" / "optics-evidence-contract" / "contract"
        meta = json.loads((contract / "unicode-profile-metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["profile_id"], "PKG01-UCD-16.0.0")
        self.assertEqual(meta["profile_version"], "16.0.0")
        self.assertEqual(unicode_profile.profile_id(), meta["profile_id"])
        self.assertEqual(unicode_profile.profile_version(), meta["profile_version"])
        for item in meta["outputs"]:
            data = (contract / item["name"]).read_bytes()
            self.assertGreater(len(data), 0)
            self.assertLessEqual(len(data), meta["max_file_bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"], item["name"])
        for item in meta["sources"]:
            data = (contract / "unicode-source" / item["name"]).read_bytes()
            self.assertGreater(len(data), 0)
            self.assertLessEqual(len(data), meta["max_file_bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"], item["name"])
        profile = json.loads((contract / "unicode-profile.json").read_text(encoding="utf-8"))
        for vector in profile["verification_vectors"]:
            normalized = unicode_profile.normalize_codes(vector["input"], vector["form"])
            self.assertTrue(normalized["ok"])
            self.assertEqual(normalized["codes"], vector["output"])
            if vector.get("category") and len(vector["input"]) == 1:
                self.assertEqual(unicode_profile.category_of(vector["input"][0]), vector["category"])
        raw = bytearray((contract / "unicode-profile.json").read_bytes())
        raw[0] ^= 0xFF
        corrupt = hashlib.sha256(raw).hexdigest()
        good = next(item["sha256"] for item in meta["outputs"] if item["name"] == "unicode-profile.json")
        self.assertNotEqual(corrupt, good)

    def test_unavailable_profile_fails_closed(self):
        privacy.set_profile_unavailable_for_test(True)
        try:
            source = materialize(next(item for item in CORPUS["cases"] if item["id"] == "clean-observation"))
            source["path"] = "/pay/4111111111111111"
            result = validate.validate_evidence(source)
            self.assertEqual(result["disposition"], "REJECT_RECORD")
            self.assertEqual(result["reason_code"], "VALIDATOR_FAULT")
            self.assertEqual(result["issue_location"], "CONFIGURATION")
            self.assertIsNone(result["record"])
            self.assertEqual(result["diagnostics"]["scan_state"], "UNAVAILABLE")
            self.assertIsNone(result["diagnostics"]["privacy_event"])
            self.assertIsNone(result["diagnostics"]["unicode_profile_id"])
            self.assertIsNone(result["diagnostics"]["unicode_profile_version"])
            self.assertEqual(result["completeness_inputs"]["privacy_invariant"], "UNKNOWN")
            self.assertNotIn("4111111111111111", validate.canonical_json(result))
        finally:
            privacy.set_profile_unavailable_for_test(False)
        self.assertTrue(privacy.profile_ready())

    def test_independent_probes(self):
        source = materialize(next(item for item in CORPUS["cases"] if item["id"] == "clean-observation"))
        source["path"] = "/pay/4111\u200e111111111111"
        pan = validate.validate_evidence(source)
        self.assertEqual(pan["disposition"], "REJECT_FIELD")
        self.assertEqual(pan["reason_code"], "REDACTION_DROP")
        self.assertEqual(pan["diagnostics"]["privacy_event"], "DESTINATION_COMPONENT_REDACTED")
        self.assertEqual(pan["diagnostics"]["scan_state"], "FULL")
        self.assertNotIn("path", pan["record"])
        canon = validate.canonical_json(pan)
        self.assertNotIn("4111111111111111", canon)
        self.assertNotIn("\u200e", canon)
        secret = validate.validate_evidence({
            "record_type": "import_quarantine",
            "schema_status": "unstable-pre-1.0",
            "schema_version": 0,
            "evidence_origin": "IMPORTED",
            "original_evidence_origin": "LOCAL_OBSERVATION",
            "accepted": False,
            "imported_at": "2026-07-01T00:00:00.000Z",
            "source_label": "s\u200b\u200bk-abcdefgh",
        })
        self.assertEqual(secret["disposition"], "REJECT_FIELD")
        self.assertEqual(secret["reason_code"], "DETECTOR_MATCH")
        self.assertEqual(secret["diagnostics"]["privacy_event"], "DETECTOR_MATCH")
        self.assertNotIn("source_label", secret["record"])
        self.assertNotIn("sk-", validate.canonical_json(secret))
        unknown_input = materialize(next(item for item in CORPUS["cases"] if item["id"] == "clean-observation"))
        unknown_input["path"] = "/a\u0379@b.co"
        unknown = validate.validate_evidence(unknown_input)
        self.assertEqual(unknown["disposition"], "REJECT_FIELD")
        self.assertEqual(unknown["reason_code"], "REDACTION_DROP")
        self.assertEqual(unknown["diagnostics"]["privacy_event"], "DESTINATION_COMPONENT_REDACTED")
        self.assertNotIn("path", unknown["record"])
        self.assertNotIn("\u0379", validate.canonical_json(unknown))
        nested = validate.validate_evidence({"record_type": "observation_event", "payload": bytes([9, 8, 7])})
        self.assertEqual(nested["disposition"], "REJECT_FIELD")
        self.assertEqual(nested["reason_code"], "UNSUPPORTED_COMPLEX_VALUE")
        self.assertIsNone(nested["record"])
        self.assertNotIn("bytearray", validate.canonical_json(nested))


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
