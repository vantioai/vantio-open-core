# PKG-01 conformance

Audience: INTERNAL_RESTRICTED

Node and Python validators are hand-written. Both read the same files in `packages/optics-evidence-contract/contract/`. Neither imports `@vantio/cli` or `vantio-agent-sdk`.

The shared corpus is `tests/optics-evidence-contract/corpus.json`. Each case has an input (or a base plus patch), one disposition, one reason, completeness impact, Optics-health impact, a remediation code, and the canary strings that must be absent from canonical output.

Canonical JSON is sorted keys, no insignificant whitespace, integers only, and the same short control escapes in both languages. The conformance test compares those strings byte for byte.

Run from the repository root, offline, with no package install:

```bash
node --test tests/optics-evidence-contract/node.test.cjs
python3 tests/optics-evidence-contract/python_test.py
```

Node engine for this package is `>=18.3.0`, matching the frozen CLI. Python uses the stdlib only. The private package has no dependencies.

`schema_status` on every result is `unstable-pre-1.0`. `schema_version` is `0`. `diagnostics.scope_complete` is false. `completeness_inputs.integrity_state` is `UNKNOWN`. `completeness_inputs.sampling` is `UNSAMPLED`. `compatibility.live_writer_modified` is false.

This corpus is an internal conformance fixture. It is not a portable customer proof and it is not shipped.
