# AI guide

Use this guide when editing Vantio Optics documentation in this repository. Package versions below are the versions in `docs/governance/VERSION-METADATA.json`. Do not bump them from a documentation change.

```json
{
  "ai_guide_versions": {
    "@vantio/cli": "0.3.25",
    "@vantio/agent-sdk": "0.2.4",
    "vantio-agent-sdk": "3.1.1",
    "@vantio/optics-mcp": "0.1.2",
    "@vantio/gate-mcp": "0.1.1",
    "vantio-optics": "0.1.0",
    "@vantio/optics-evidence-contract": "0.0.0-unstable-pre-1.0"
  }
}
```

## Boundary

Vantio Optics is the free Observe tier: local metadata for supported wrapped calls. It does not retain prompts or completions. Phantom Engine is Enforce + Control on enrolled Linux hosts. Enterprise is the governance layer. Free Optics needs no account and no API key.

There is no OTLP exporter. Browser paths stay outside this wrap.

## What to treat as current

Current prose is the canonical list in `docs/governance/llms.txt`. A planning note, an internal roadmap item, or a retired name is not current. New public docs join that list only when the documentation release checks pass.

Enforcement helpers (`fetchPolicy`, `reportAnomaly`, `redactPII`, and the Python names) are control-plane APIs. Describe them as Phantom Engine / Enterprise, not as free Optics behavior.
