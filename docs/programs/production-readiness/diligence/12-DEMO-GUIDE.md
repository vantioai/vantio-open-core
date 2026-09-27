# Demo guide

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Reserve the slot for a later demo script. This file is not the script. It records what a demo is allowed to show and what it must label.

## Allowed subject

A local Optics observe path already described in the public manual:

- `docs/products/optics/QUICKSTART.md`
- `docs/products/optics/USER-MANUAL.md`

The script body stays `NOT_FILLED`. Do not paste command sequences into this room as a company operating procedure. Point at the public manual and re-read it on the day of the demo.

## Fixture behavior already documented

`docs/products/optics/STATUS-AND-OUTCOMES.md` records that `vantio demo` writes one stub HTTP 200 for host `optics-demo.invalid`, with duration 0 and no network. Discover, search, tail, diff, and prove include that file. There is no origin field that excludes fixtures.

A demo that uses this command labels the record as a fixture. It is not production traffic and not customer traffic.

## Required labels on any future script

| Label | Value |
| --- | --- |
| Product | Vantio Optics, free observe |
| Package versions | Taken from the machine that day, compared with [11-BUILD-STATUS.md](11-BUILD-STATUS.md) |
| Network | Stated. The stub demo has no network. |
| Customer data | Absent |
| Prompts | Absent |
| Enforcement result | Absent, unless the demo is an explicitly separate Phantom Engine session whose materials are not stored in this file |

## Prohibited demo content

- Kernel bypass and exploit demonstrations
- Credential entry, live keys, or customer tenants
- Private prompts or completions
- Phantom Engine customer materials
- A claim that the fixture record is `STRANGER_HOST_PROVED` or `CUSTOMER_VALIDATED`

## Sections still empty

| Section | Value |
| --- | --- |
| Spoken script | `NOT_FILLED` |
| Slides | `NOT_FILLED` |
| Phantom Engine demo | `NOT_IN_THIS_ROOM` |
