# Getting Started with Vantio Optics
### Open Core · Free · Observe only

**Time to first event: under 60 seconds.**  
Workflow: **[Sight Loop](./sight-loop.md)** (wrap → capture → inspect → residual)

---

## Step 1 — Install

Node:

```bash
npm install -g @vantio/cli
```

If that command fails with `EACCES`, the global npm prefix is not writable. Install into a directory you own and put its `bin` directory on `PATH`:

```bash
npm install -g @vantio/cli --prefix "$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"
```

Python needs a second package. The CLI install does not install it. Without this package, `vantio run python` and `vantio run python3` do not intercept:

```bash
pip install vantio-agent-sdk
```

If the system site-packages directory is not writable, `pip` installs into your user site. That is still this install.

These commands work on macOS, Linux, and Windows (WSL).

---

## Step 2 — Run your agent

Instead of running your Node agent directly, prefix it with `vantio run`:

```bash
# Before
node agent.js

# After
vantio run node agent.js
```

Python, after the pip install above:

```bash
vantio run python3 agent.py
```

Use `vantio run python agent.py` on a machine where the `python` command exists. `vantio run` accepts `python`, `python3`, and `python3.N`. It does not start a shell, so a glob in that command is not expanded. Prefixing `vantio run` does not intercept a Python process until `vantio-agent-sdk` is installed.

---

## Step 3 — See what's happening

The first time you run it, you'll see every outbound AI call intercepted in real time:

```
[ ∅ VANTIO ] Outbound LLM call intercepted
  host:    api.openai.com
  pid:     12345
  bytes:   237
  time:    2026-05-28T22:30:00.000Z
  → Optics observes only. Upgrade to Vantio Phantom Engine to enforce policy.
```

A summary prints when the run recorded at least one supported call. You can also request it explicitly. An empty run does not get a summary:

```bash
vantio run --summary node agent.js
```

```
[ ∅ VANTIO ] Run Summary
  LLM calls:    7
  Hosts:        api.openai.com, api.anthropic.com
  Total bytes:  94,201
  Duration:     12.4s
```

---

## Step 4 — Local commands

Free Optics needs **no account and no API key**.

Run logs are files under `~/.vantio/runs/`. `VANTIO_HOME` changes the parent directory. The default parent is `~/.vantio`, so the log directory is `$VANTIO_HOME/runs` when that variable is set, and `~/.vantio/runs` when it is not. The files are not written into the project directory. A tool that does not expand `~` needs the absolute path, such as `$HOME/.vantio/runs`.

A Node run (`node`, `npx`, `tsx`, or `ts-node`) writes one JSON file there when the process exits, including a run that made no LLM call. The terminal always prints a trace line. The summary prints only when at least one supported call was recorded.

A Python run writes a file there only after `vantio-agent-sdk` recorded at least one supported call. A Python process that exits with no such call leaves no file. `vantio prove` then says there is no local run log.

`vantio run pnpm …` and `vantio run bash …` start those programs and do not write a run log. The Node interceptor is applied to `node`, `npx`, `tsx`, and `ts-node`. The Python wrap is applied to `python`, `python3`, and `python3.N` after the SDK install.

When a log file exists, `vantio prove`, `vantio search`, `vantio tail`, `vantio diff`, and `vantio discover --local` read it on this machine.

---

## Step 4b — Generate a proof artifact (Free)

After a run, you have local evidence you can share with an auditor:

```bash
vantio prove              # HTML report for the most recent run
vantio prove --list       # list all locally stored runs
vantio prove --format=md  # Markdown instead of HTML
vantio search openai      # search captured calls
vantio tail               # latest calls from the most recent run
vantio diff <a> <b>       # compare two local runs
```

The proof artifact includes: trace ID, machine/PID, timestamp, byte counts per
LLM host, action labels (OBSERVED / ALLOWED / REDACTED / BLOCKED), and summary
counts. **No prompts or completions are included** — the report is safe to share
with auditors, security teams, or compliance reviewers.

```
✓ Proof artifact written to: vantio-proof-0x1a2b3c4d.html
```

---

## Step 5 — Phantom Engine / Enterprise connected discover

Connected `vantio discover` is a Phantom Engine / Enterprise capability. It is not part of free Optics. Free Optics stays on this machine (`vantio discover --local`). The commands below are that upgrade path:

```bash
vantio discover
vantio discover --since=7d
vantio discover --host=api.openai.com
vantio discover --since=30d --json
```

```
Shadow AI Attack Surface — last 24h
--------------------------------------------------------------------------------
TARGET HOST                       CALLS    ALLOWED   REDACTED  BLOCKED   OBSERVED  SHADOW?   LAST SEEN
--------------------------------------------------------------------------------
api.openai.com                       42         38          4        0         0   no        2026-05-28 22:30:00 UTC
--------------------------------------------------------------------------------
1 host(s) shown  |  No Shadow AI indicators detected.
```

That reading belongs to Phantom Engine / Enterprise connected discover. It is not a free Optics workspace.

---

## Supported frameworks

Works with any framework that makes HTTP calls:

LangChain · AutoGen · CrewAI · OpenAI SDK · Anthropic SDK · AWS Bedrock · Google Vertex · Cohere · Groq · Together AI · Perplexity · any `fetch`-based agent

**Python agents:** `pip install vantio-agent-sdk`, then `vantio run python3 agent.py` (or `vantio run python agent.py` where `python` exists) or `@shield`. The prefix does not intercept until the SDK is installed. See [vantio.ai/optics](https://vantio.ai/optics).

---

## What Vantio never captures

- The content of your prompts
- Model completions or responses
- Any personally identifiable information

Vantio records *that* a call was made, *when*, *to which provider*, and *how many bytes* — nothing more.

---

## Free Observe is bypassable by design — and that's the point

`vantio run` intercepts LLM calls by patching `globalThis.fetch` in the Node.js
runtime (via `NODE_OPTIONS --require`). This covers the vast majority of real agents
— every OpenAI SDK call, every LangChain.js call, every Vercel AI SDK call — without
any code changes.

**It can be bypassed.** A process can:
- Call an LLM endpoint directly through a native socket without using `fetch`
- Spawn a subprocess that isn't started with `vantio run`
- Use a language runtime other than Node without installing the Python SDK

**This is intentional, not a bug.** Vantio Optics surfaces your governance gap honestly. The gap itself is what motivates upgrading:

| Tier | What's bypassable |
|------|-------------------|
| **Free · Vantio Optics (this tier)** | Any process not started with `vantio run` / `shield()`; Python without `vantio-agent-sdk`; native socket calls the interceptor does not mediate |
| **Vantio Phantom Engine** (Contact Vantio) | Raw sockets and unenrolled processes not on an enrolled Linux host |
| **Vantio Enterprise** | Same host scope; adds ledger, dual-control, and certifications |

Run `vantio discover --local` to see what Optics can observe on your machine. Residual risk closes with **Vantio Phantom Engine** — see [observe-only.md](./observe-only.md).

> **Why honesty sells:** an audit team asking "can your agent bypass this?" gets a
> straight answer from Free: yes, intentionally, and here is the upgrade path that
> closes it. That transparency builds trust far faster than overclaiming.

---

## Common questions

**My agent uses Python, not Node.js.**
Install `vantio-agent-sdk` on that interpreter, then `vantio run python3 agent.py` or use the `@shield` decorator. Use `python` instead of `python3` only when that command exists. The prefix does not intercept until the SDK is installed. `vantio run` injects the Node interceptor (`NODE_OPTIONS --require`) for `node`, `npx`, `tsx`, and `ts-node`.

**Nothing is appearing in my terminal.**
For Node, use `node`, `npx`, `tsx`, or `ts-node` under `vantio run`. A Node run with no supported call still writes `~/.vantio/runs/` and prints a trace line, and it does not print a summary. For Python, install `vantio-agent-sdk` first, then `vantio run python3 agent.py` or `@shield`. Without the SDK, the prefix prints a one-line notice and does not intercept. A Python run with no supported call does not write a run log.

**`npm install -g` says EACCES.**
The global prefix is not writable. Repeat the install with `--prefix "$HOME/.local"` and add `$HOME/.local/bin` to `PATH`, as in Step 1.

---

*Questions? [security@vantio.ai](mailto:security@vantio.ai) · [vantio.ai](https://vantio.ai)*
