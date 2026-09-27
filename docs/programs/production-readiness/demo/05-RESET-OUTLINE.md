# Reset outline

Audience: INTERNAL_RESTRICTED

This outline describes the reset. It is not a shipped script. Wave 2 may turn it into a program after a separate authorization. Do not point a deletion command at the operator's real home.

## State the script creates

Inside the demo home only:

- `$DEMO_HOME/.vantio/runs/<trace>.json` from the single `demo` invocation
- `$DEMO_HOME/.vantio/runs/<defect>.json` if injection F1 was planted
- Directory mode on `.vantio` and `runs` follows the CLI writer (`0700` when the CLI creates them)

Outside the demo home, only if the operator broke the prove rule:

- `vantio-proof-<trace>.html` in the working directory from a default HTML prove

The scripted prove path uses `--format=md` and writes to the terminal. A correct run creates no HTML file.

## Reset steps

1. Read `$DEMO_HOME` aloud. Confirm it is the temporary directory from the runbook, not `$HOME` of the logged-in operator after the demo shell has exited.
2. List `$DEMO_HOME/.vantio/runs`. Expect the demo trace file and, after B15, the planted defect file. Expect no other product data.
3. Remove the temporary directory and its contents.
4. If the working directory contains `vantio-proof-*.html` from this session, remove those files. Leave any proof file that was already there before the session.
5. Unset `HOME` override in the demo shell so later commands use the operator home again.
6. List the operator's real `~/.vantio/runs` only to confirm the demo trace id is absent. Do not delete files there as part of this outline.
7. Confirm `vantio status` is not required after reset. The next session starts from a new empty demo home.

## Pass condition

- The demo trace id is gone from the demo home because the demo home is gone.
- The planted defect is gone with it.
- The operator's real runs directory does not contain that trace id.
- No session HTML proof remains in the working directory.

## Fail condition

Stop and leave files in place if the path about to be removed is the operator's real home, a source checkout, or a path whose prefix was not recorded before B01. A failed reset is a stopped demo, not a reason to widen the deletion.
