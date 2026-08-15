# Spec — Optics CLI inspect (search, tail, diff)

**Brand:** Vantio Optics  
**Workflow:** Sight Loop  
**Tier fence:** P1 · Free observe  
**Customer surface:** CLI (`@vantio/cli`) · vantio.ai/docs · GitHub README  
**Gap id:** `optics_cli_inspect`

## Goal

A builder who already wrapped an agent can inspect a captured run from the terminal — search calls, tail the latest events, and diff two runs — without opening Mission Control.

## Dependencies

- Local run logs at `~/.vantio/runs/` (written by `vantio run` / interceptor)
- Existing `vantio prove` / `vantio discover --local` helpers for listing and resolving runs
- No Gate key, no Phantom Engine path

## Checklist

- [x] `vantio search` — find calls across local runs by host, provider, path, action, or free text
- [x] `vantio tail` — show the last N calls from a run (optional `--follow`)
- [x] `vantio diff` — compare two runs (hosts, call counts, bytes)
- [x] CLI `--help` for each command; top-level usage lists them
- [x] Tests + offline fixture prove (no Gate / Phantom Engine drill)
- [ ] Public docs: open-core README, Sight Loop, `@vantio/cli` README, vantio.ai/docs, `llms.txt` if CLI surface is named
- [ ] Publish `@vantio/cli` patch (version bump to 0.3.17)

## Out of scope

- Mission Control inspect chrome / wrap-library pills
- Gate enforce / Phantom Engine
- Browsers · Stripe · stranger-host theater
- Renaming `vantio prove` (existing export command stays)
