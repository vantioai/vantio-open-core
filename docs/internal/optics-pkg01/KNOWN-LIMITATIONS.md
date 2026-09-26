# PKG-01 known limitations

Audience: INTERNAL_RESTRICTED

- Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` still says closed. This Force opens Gate 8 only for this private package. That architecture file was not edited.
- Founder decisions 2–13 stay unresolved. Safe defaults are recorded in `contract/contract-metadata.json`: no usage or cost, no alerting, no numeric performance target, no at-rest encryption choice, no promotion of `LEGACY_UNMARKED`, no seventh annotation origin, no Windows ACL claim, no SQLite binding, no `CURRENT` freshness, no machine hostname, no OTLP or SIEM export, no UI.
- No host catalog. A legacy provider string is omitted rather than guessed. `LOCAL_OLLAMA` is kept only when the normalized host is `localhost`, `127.0.0.1`, or `::1` and the port is `11434`. Otherwise provider id becomes `unknown` and confidence `NONE`.
- `CATALOG` and `REGIONAL_PATTERN` are accepted only when the caller sends those tokens and a provider id that matches the id charset. They are not inferred from the host.
- Detection folds confusables and applies one percent-decode and one base64 pass. It does not store the folded or decoded text. A long base64-alphabet string can be treated as a secret even when the decoded bytes are not a credential. The oversize-path fixture uses `!` so the path rule is the one under test.
- Phone detection requires a separator or parentheses, so a hex trace is not classified as a phone. Card detection does not treat a digit run bounded by letters as a card.
- Non-zero timestamp offsets are rejected, not converted. Only `Z`, `+00:00`, and `-00:00` are accepted, and the stored form is `YYYY-MM-DDTHH:MM:SS.mmmZ`.
- Duplicate JSON object keys are not visible. Parsers keep the last key.
- Integers above `9007199254740991` are not a conformance claim. Fixtures stay inside that range.
- Python string length is Unicode code points. Node string length for some host and version checks is UTF-16 code units. The corpus is BMP text, where those lengths match.
- There is no importer and no annotation store. Import and annotation objects are contract fixtures only. An import does not receive a fresh observation basis in this slice.
- `scope_complete` is always false. Record acceptance is not a scope-wide completeness claim.
- Python 3.10 and 3.11 were not installed here. Windows, macOS, and WSL were not run. Those are `NOT_TESTED`.
- The package is private, unversioned for release, and not loaded by the live CLI or Python runtime.
