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
- [x] Readable table: padded timestamp column, full action label (`DRY_RUN_BLOCKED_SPEND` no longer truncates to the same text as `DRY_RUN_BLOCKED_SIZE`), and the full trace ID so a row can be pasted into `vantio prove --run=` or `vantio diff`
- [x] Tests + offline fixture run (no Gate / Phantom Engine drill)
- [x] Public docs written (open-core README, Sight Loop, `@vantio/cli` README, vantio.ai/docs, `llms.txt`)
- [ ] Publish `@vantio/cli` 0.3.17, push the branch to GitHub — this host has no npm, GitHub, or Vercel credentials, so both steps need a machine that does

## Open honesty gap (needs Zachary)

vantio.ai/docs and `llms.txt` are already live with `vantio search`, `vantio tail`, and
`vantio diff`, but the published `@vantio/cli` on npm is still 0.3.16, which does not
have these commands. A reader who follows the live page today gets "unknown command".
Two ways to close it: publish 0.3.17 from a machine with an npm token, or soften the
live copy until the publish happens. Publishing is the smaller change and keeps the
page accurate.

## Out of scope

- Mission Control inspect chrome / wrap-library pills
- Gate enforce / Phantom Engine
- Browsers · Stripe · stranger-host theater
- Renaming `vantio prove` (existing export command stays)
