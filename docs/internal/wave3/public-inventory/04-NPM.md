# npm

Audience: INTERNAL_RESTRICTED

Registry search for `vantio` returned five objects. Four are `@vantio` packages. The fifth, `lingual-lang`, is unrelated. Maintainer search for `vantioai` returned the same four packages. The publisher on the latest documents is npm user `vantioai`, email `zach@vantio.ai`.

No publish, deprecate, or yank was performed. `@vantio/cli@0.3.24` is frozen and was not reopened.

In-repo names that are not on the registry returned HTTP 404. That includes the internal Optics, Phantom Engine, and governance package names, plus unscoped `vantio` and `vantio-cli`.

Registry signatures are present on each latest version. The npm provenance attestation field was absent on each latest document.

| Package | Latest | Versions | Homepage | Description drift |
| --- | --- | --- | --- | --- |
| `@vantio/cli` | 0.3.24 | 0.1.0 and 0.3.0–0.3.24 (26) | `/optics` | Matches the free Optics observe sentence. Not deprecated. |
| `@vantio/agent-sdk` | 0.2.4 | 0.1.0, 0.2.0–0.2.4 | `/optics` | Description offers an upgrade path to Gate and Phantom Engine. README links `vantioai/vantio-pro`. |
| `@vantio/optics-mcp` | 0.1.2 | 0.1.0–0.1.2 | `/optics` | Description offers an upgrade path to Gate. README says upgrade to Vantio Gate to block, redact, or cap spend. |
| `@vantio/gate-mcp` | 0.1.0 | 0.1.0 only | `https://vantio.ai/pro` | Description is “Vantio Gate MCP — Policy Latch dry-run.” `/pro` redirects to `/phantom-engine#enforce`. README says live latch is `vantio run` plus Pro policy. |

None of the latest versions are deprecated. Engines are Node 18 or newer (`@vantio/agent-sdk` says `>=18.0.0`; the others say `>=18.3.0`). Licenses are MIT. Keywords and integrity strings are in the JSON register.

`@vantio/cli` bin is `vantio`. `@vantio/optics-mcp` bin is `vantio-optics-mcp`. `@vantio/gate-mcp` bin is `vantio-gate-mcp`. The Node SDK has no bin. It exports `.`.

Changing any of these registry texts requires the npm account. This track does not.
