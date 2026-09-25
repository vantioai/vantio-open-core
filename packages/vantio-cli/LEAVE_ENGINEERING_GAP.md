# LEAVE_ENGINEERING_GAP

**Status:** Customer-controlled removal is a required product invariant. No CLI command shipped. No public roadmap. No owner. No delivery date.

## What this gap is

A `vantio leave` command (or equivalent) would allow a customer to cleanly remove Vantio from a host or project — reversing all enrollment steps, removing stored credentials and run logs, and leaving the host in the state it was in before Vantio was installed.

## Current state

- **CLI command:** Not shipped. `vantio leave` is not in the command dispatch, not in the help text, and not in any public documentation.
- **Docs:** No customer-facing documentation claims `vantio leave` exists.
- **Implementation:** None. No code for this command exists in this package.

## Why it matters

The Founder instruction (Decision 3) declares customer-controlled removal a required invariant — a customer must be able to remove Vantio's local footprint without Vantio's assistance or a support ticket. This is a trust property, not a convenience feature.

## What remains unresolved

- **Ownership:** No assignee, no team, no charter to build this.
- **Scope:** What counts as "leave" is unspecified. Candidates include: remove `~/.vantio/`, uninstall the global npm package, unenroll from Phantom Engine, remove the interceptor from existing scripts, disable scheduled Optics MCP, revert any system-level changes.
- **Atomic vs. stepwise:** Whether leave is one command or a multi-step guided removal is unresolved.
- **Verification:** How to prove leave completed correctly is unresolved.

## What was done in this remediation

- Confirmed the command is absent from CLI dispatch, USAGE string, and README.
- This file documents the gap per the Founder instruction.
- No `vantio leave` command was implemented (per explicit instruction: "Do NOT implement ... leave").

## Instructions for whoever picks this up

1. Do not ship a `vantio leave` command until scope, behavior, and verification are defined and reviewed.
2. Any public documentation of `vantio leave` must be accurate at the time of writing — do not pre-announce.
3. Remove this file when the command ships and is verified.
