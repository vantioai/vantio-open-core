# Quickstart

Optics is local. A fresh CLI install needs no account and no API key. The record is metadata: host, size, timing, and process. Prompts and completions are absent from the record.

Versions: install `@vantio/cli@0.3.24` and, for Python, `vantio-agent-sdk==3.0.14`. Python 3.1.0 in this git tree is unpublished. Details: [INSTALLATION.md](INSTALLATION.md).

## 1. Install the CLI

```bash
# Example status: illustrative
npm install -g @vantio/cli
vantio --version
```

`vantio --version` prints the installed CLI version. For this manual that version is `0.3.24`.

There is no `https://vantio.ai/install.sh` installer. Node.js 18.3 or newer is required by the CLI package.

## 2. See one local demo record

`vantio demo` writes one stub call and does not use the network. The stub host is `optics-demo.invalid`. Later `discover`, `search`, `tail`, `diff`, and `prove` treat that file like any other run. The file has no separate origin marker.

```bash
# Example status: illustrative
vantio demo
vantio status
```

`vantio status` reads this machine. It contacts the network only when you pass `--check-registry`.

## 3. Wrap a Node agent

```bash
# Example status: illustrative
vantio run node agent.js
vantio run --summary node agent.js
```

`vantio run` attaches the interceptor for `node`, `npx`, `tsx`, and `ts-node`. A Node process started without `vantio run` is not attached.

When the child exits, the CLI writes `~/.vantio/runs/<trace-id>.json`, including when no in-scope call happened. Commands that read logs use `~/.vantio/runs` from the home directory. They do not read `VANTIO_HOME`. If you set `VANTIO_HOME`, the writer and the reader can diverge. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 4. Wrap a Python agent

Install the published SDK on the same interpreter you run:

```bash
# Example status: illustrative
pip install 'vantio-agent-sdk==3.0.14'
vantio run python agent.py
```

`vantio run python` without that package prints a warning and does not intercept. Python 3.10 or newer is required by the published package.

`shield()` inside the process is the other entry point. On published 3.0.14, `shield()` sends the usage ping unless you opt out. Set `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` before you rely on silence. See [TELEMETRY.md](TELEMETRY.md).

A Python run log is written only when at least one in-scope call was recorded. A silent Python process can leave no file.

## 5. Read what was recorded

```bash
# Example status: illustrative
vantio discover --local
vantio prove
vantio search openai
vantio tail -n 20
vantio diff 0xabc 0xdef
```

`discover` looks back 24 hours unless you set `--since` to `7d` or `30d`. It lists this machine's run logs. It is not a fleet inventory.

`prove` writes an HTML file in the current directory by default (`vantio-proof-<id>.html`). `--format=md` writes Markdown to stdout unless you set `--out`.

Replace `0xabc` and `0xdef` with trace id prefixes from `vantio prove --list`.

## What you should see

A supported call shows action `OBSERVED` in a free Optics run. Display lines separate **Optics status** from **Application outcome**. Optics status `Successful` means the record exists. Application outcome comes from the HTTP status. See [STATUS-AND-OUTCOMES.md](STATUS-AND-OUTCOMES.md).

A call that never hit a wrapped library, or a host outside the catalog, produces no row. That absence is not protection. See [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md).

## Next

- Node details: [NODE-GUIDE.md](NODE-GUIDE.md)
- Python 3.0.14 versus unpublished 3.1.0: [PYTHON-GUIDE.md](PYTHON-GUIDE.md)
- Privacy: [PRIVACY-AND-SECURITY.md](PRIVACY-AND-SECURITY.md)
