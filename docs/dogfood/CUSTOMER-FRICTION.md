# Customer friction — Lab-only

This file records what happened when the CI and release workflows tried to install and run Vantio the way the public docs tell a customer to. The checks below were run on this machine on 2026-10-17 against the packages the registries served that day. This is not a customer certification.

Public path used:

- `docs/getting-started-tier01.md`
- `packages/vantio-cli/README.md`
- `packages/vantio-agent-sdk-py/README.md`

Commands those pages give:

```bash
npm install -g @vantio/cli
pip install vantio-agent-sdk
vantio run node agent.js
vantio run python agent.py
```

The workflows do only that, plus a copy of `~/.vantio/runs` so the job can upload a log. They do not call repository scripts, and they do not run the CLI from a source checkout.

## Entries

### 1. `npm install -g` is not the whole install on Linux

What happened: `npm install -g @vantio/cli` failed with `EACCES` creating `/usr/lib/node_modules`. `npm prefix -g` was `/`. The same package installed when given a writable prefix. The getting-started page says the global install is the only install step and does not mention a prefix, a Node version manager, or a permissions failure.

Fix belongs in the docs. The page should say what to do when the global prefix is not writable. A product change is not required for a customer who already has a writable prefix.

### 2. The registries are behind this repository

What happened: `npm view @vantio/cli version` returned `0.3.24`. `packages/vantio-cli/package.json` in this tree is `0.3.25`. `https://pypi.org/pypi/vantio-agent-sdk/json` returned `3.1.0`. `packages/vantio-agent-sdk-py/pyproject.toml` in this tree is `3.1.1`. `npm view @vantio/agent-sdk version` returned `0.2.4`. A customer following the install page gets the registry builds, not the checkout.

Fix belongs in the product release process. The docs already point at the registries. They should not tell a customer to run a file from this repo.

### 3. The documented Python command is `python`

What happened: `vantio run python -c '...'` exited 1 with `spawn python ENOENT`. This machine has `python3` and no `python`. The published CLI does start `python3` (`vantio run python3 -c '...'` exited 0). Getting started and the CLI readme only show `python`.

Fix belongs in the docs. They should show `python3` for hosts that do not install the `python` name. The CLI already accepts that name.

### 4. Getting started says the CLI is the only install

What happened: the same page then says Python needs `pip install vantio-agent-sdk` before `vantio run python` will intercept. Both sentences are on `docs/getting-started-tier01.md`.

Fix belongs in the docs. The first install step should name both packages.

### 5. An empty run does not match the "you will see a summary" page

What happened: `vantio run node -e 'process.exit(0)'` with published CLI `0.3.24` exited 0, wrote `~/.vantio/runs/<trace>.json`, and printed only the trace line. It did not print the run summary the getting-started page shows. `vantio run python3 -c '...'` after `pip install vantio-agent-sdk` exited 0 and wrote no run file. `vantio prove` then printed "No local run logs found." The Python readme says a trace with no supported call does not write a run log. Getting started does not say that.

Fix belongs in the docs for the empty-run case. A product change would be needed only if an empty Python run should still leave a file a CI job can upload. This dogfood does not make that change.

### 6. `pnpm` and `bash` start, and they do not leave a run log

What happened: `vantio run pnpm --version` and `vantio run bash -lc 'echo bash-ok'` both exited 0 and printed the trace line. Neither created `~/.vantio/runs`. Getting started says the Node interceptor is `NODE_OPTIONS --require` for `node`, `npx`, `tsx`, and `ts-node`. Most commands in these workflows are `pnpm`, `python3`, or a shell script.

Fix belongs in the docs. They should say that prefixing `vantio run` to `pnpm` or `bash` does not record a run. Wrapping those tools would be a product change, and this dogfood does not do it from inside the repo.

### 7. `vantio run` does not expand a shell glob

What happened: the CLI spawns the program with no shell. A customer who writes `vantio run node --test packages/*.test.js` does not get the shell's glob. The docs only show `vantio run node agent.js`.

Fix belongs in the docs. An example should use a concrete file name. This dogfood does not pass globs to `vantio run`.

### 8. Run logs are outside the workspace

What happened: the published CLI writes `~/.vantio/runs`. The upload-artifact path is not a shell, so `~` is not expanded. The public pages do not say how to collect that directory in CI. The workflow copies `$HOME/.vantio/runs` into `optics-observe-log` and uploads that directory. The copy is not in the install docs.

Fix belongs in the docs. A short CI note should show the directory and a copy into the workspace. The product already documents the directory in the CLI readme.

### 9. Release jobs are not the documented `vantio run node agent.js`

What happened: the npm, PyPI, MCP registry, and provenance jobs run repository scripts and publish actions. Following the public pages means not executing those scripts under `vantio run`. The observe step installs the published packages and runs the documented `vantio run node` and `vantio run python` commands. It does not call `promote_npm.mjs`, `stage_sealed_pypi.py`, `fetch_custody_release.py`, `mcp-publisher`, `npm pack`, or the provenance `tar`.

Fix belongs in the docs if a release example is wanted. It does not belong in a workflow that shells out to those scripts under the customer install.

### 10. The install commands are unpinned

What happened: the pages do not name a version. These workflows use the same unpinned commands. On this date that resolved to CLI `0.3.24` and `vantio-agent-sdk` `3.1.0`.

Fix belongs in the docs if a customer CI job is expected to pin a version. The product pages currently describe a floating install, and the workflows follow that.

### 11. `pip install` may target the user site

What happened: `pip install vantio-agent-sdk` printed that it was defaulting to a user install because the system site-packages was not writable, then installed `3.1.0` under `~/.local`. The import succeeded afterward. The pages do not mention a user site.

Fix belongs in the docs. The install still succeeded with the documented command.

### 12. Nothing in the public pages shows a CI failure policy

What happened: `vantio run python` exits 1 when `python` is missing. A job that should stay green has to set `continue-on-error` on that step. The product pages do not mention GitHub Actions.

Fix belongs in the docs. The exit code is the wrapper reporting that it could not start the program.
