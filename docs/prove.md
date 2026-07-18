# vantio prove — Auditor-Ready Proof Artifacts

Part of **Vantio Optics** · [**Sight Loop**](./sight-loop.md) step 3 (inspect / export).

`vantio prove` generates a self-contained proof artifact — HTML or Markdown — from
a `vantio run` log. The artifact is designed to be shared with auditors, security
reviewers, and compliance teams without any risk of leaking sensitive content.

**Reports contain zero prompts, completions, or content.** They record only:
host names, byte counts, process IDs, trace IDs, action labels, and timestamps.

---

## How it works

Every time `vantio run` intercepts at least one LLM call, it writes a compact JSON
run log to `~/.vantio/runs/<trace-id>.json` on exit (mode `0600`). `vantio prove`
reads those files and renders them as an auditor-ready document.

```
vantio run node agent.js          ← run your agent
   ↓ (on exit, writes ~/.vantio/runs/0x1a2b3c4d.json)
vantio prove                      ← generate proof from the most recent run
   ✓ Proof artifact written to: vantio-proof-0x1a2b3c4d.html
```

---

## Usage

```
vantio prove [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--list` | List available local run logs |
| `--run=<trace-id>` | Generate a report for a specific run (by trace ID or prefix) |
| `--from=<file>` | Generate a report from an explicit log file path |
| `--format=html\|md` | Output format (default: `html`) |
| `--out=<file>` | Write output to a named file |
| `-h, --help` | Show help |

---

## Examples

**Most recent run — HTML (default):**
```bash
vantio prove
# ✓ Proof artifact written to: vantio-proof-0x1a2b3c4d5e6f7a8b.html
```

**List available runs:**
```bash
vantio prove --list
# TRACE ID                                CALLS    TOTAL BYTES     DATE
# ─────────────────────────────────────────────────────────────────────────
# 0x1a2b3c4d5e6f7a8b                      3        15,425          2026-07-16 18:00:12 UTC
# 0x9f8e7d6c5b4a3210                      12       84,203          2026-07-15 09:22:55 UTC
```

**Specific run by trace ID:**
```bash
vantio prove --run=0x1a2b3c4d
```

**Markdown to stdout (pipe-friendly):**
```bash
vantio prove --format=md
vantio prove --format=md --out=audit-report.md
```

**Named output file:**
```bash
vantio prove --format=html --out=audit-2026-07-16.html
```

**From a specific log file:**
```bash
vantio prove --from=~/.vantio/runs/0x1a2b3c4d5e6f7a8b.json
```

---

## HTML report

The HTML report is a single self-contained file (no external dependencies) with:

- **Privacy banner** — explicit statement that no prompts or completions are present
- **Run identity** — trace ID, started/generated timestamps, duration, PID, machine, CLI version
- **Summary metrics** — total calls, bytes, unique hosts, PII-redacted count, blocked count
- **Call log table** — one row per intercepted call: host, action badge, bytes, timestamp

Action badges are colour-coded:
- `OBSERVED` — grey (**Vantio Optics** · Free · observe only — no enforce)
- `ALLOWED` — green (Vantio Gate / Enterprise · permitted by policy)
- `REDACTED` — amber (Vantio Gate / Enterprise · PII scrubbed)
- `BLOCKED` — red (Vantio Gate / Enterprise · denied by policy)

---

## Run log format

Run logs are stored at `~/.vantio/runs/<trace-id>.json` (mode `0600`):

```json
{
  "vantio_run_log": "1",
  "trace_id": "0x1a2b3c4d5e6f7a8b",
  "pid": 12345,
  "machine": "dev-laptop",
  "started_at": "2026-07-16T18:00:00.000Z",
  "generated_at": "2026-07-16T18:00:12.000Z",
  "duration_ms": 12000,
  "cli_version": "0.3.0",
  "calls": [
    { "hostname": "api.openai.com", "action": "OBSERVED", "bytes": 4821, "ts": "2026-07-16T18:00:01.100Z", "redactions": 0 }
  ],
  "summary": {
    "total_calls": 1,
    "total_bytes": 4821,
    "hosts": ["api.openai.com"],
    "redacted": 0,
    "blocked": 0,
    "est_spend_usd": null
  }
}
```

`est_spend_usd` is `null` on Free (no API key) and a float estimate on Pro/Enterprise.

---

## Availability

`vantio prove` is available on all tiers including Free — no API key required.
Run logs are written locally by the interceptor on exit whenever LLM calls were
observed. They never leave your machine unless you explicitly share the report.

---

## Audit use case

Share `vantio prove` output with:

- **Compliance reviewers** — confirms which LLM providers were called, when, and
  from which process, without exposing prompt content.
- **Security auditors** — shows byte counts and action labels that confirm governance
  controls (blocks, redactions) fired correctly.
- **Incident response** — a trace ID links the run log to any Vantio dashboard events
  (Pro/Enterprise), providing a full governance chain-of-custody.

> **Pro tip:** run with `vantio run --audit node agent.js` to flag all events from
> this run as audit-mode. Audit-mode events are labelled separately in the dashboard
> and in the proof artifact action column.

---

*[vantio.ai](https://vantio.ai) · [Pricing](https://vantio.ai/pricing) · [Dashboard](https://vantio.ai/dashboard)*
