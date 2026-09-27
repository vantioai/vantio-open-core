# Failure-injection outline

Audience: INTERNAL_RESTRICTED

Injections are operator checks. They are not a fuzzer and they do not ship as a command. Only F1 is performed in the room, at beat B15. F2 through F6 are rehearsals the operator runs before the room, or stops for if they appear by mistake.

The planted defect for F1 is created in the demo home during the beat. It is deleted by the reset. This repository does not contain a copy of that defect as a standalone run log.

## F1 — Unlabeled synthetic file (room)

When: B15, after `discover` has been run under the `SIMULATED_DEMO` banner, before reset.

Setup, inside `$DEMO_HOME/.vantio/runs/` only:

Write one JSON object whose top-level marker is `vantio_run_log` `"1"`, whose single call hostname is `api.openai.com`, whose action is `OBSERVED`, and whose bytes are a positive integer. Omit `evidence_origin`. Omit `producer`. Omit hostname `optics-demo.invalid`. Use trace id `0xinjectunlabeled01` so the reset can name it.

The wrapper below is the design record of that defect. The wrapper is labeled. The inner object is the defect. Do not show the inner object to the investor as an event. Show the stop.

```json
{
  "schema": "vantio.investor-demo.failure-injection/v0",
  "simulation_label": "INJECTED_UNLABELED_SYNTHETIC",
  "display_to_investor": false,
  "implementation_status": "OUTLINE_ONLY",
  "inner_defect_rule": "Create the inner object only in the demo home at beat B15. Delete it in the reset. It is unlabeled on purpose."
}
```

Expected operator result, same rule as `01-SIMULATION-LABEL-RULE.md` and `03-DEMO-SCRIPT.md`:

On F1, an unlabeled synthetic file is discarded. The operator does not prove it, does not add it to a total, and does not resume a success narration. The operator still speaks B16–B18 as the close, including `L-FOUNDER-BEATS-ABSENT`. The operator does not keep speaking as if the demo succeeded with the unlabeled file.

Checks:

1. The operator states the file has no simulation label.
2. The operator does not run `vantio prove` on `0xinjectunlabeled01`.
3. The operator does not add its call count to a customer total.
4. The operator does not resume a success narration. B16 through B18 are the close.
5. Do not delete the planted file before B17. Reset in B17 removes the file with the demo home. That removal completes the discard. Until then, discard is the disposition.

Fail if anyone calls the planted host a live provider call.

## F2 — Demo host narrated as production (rehearsal)

If a speaker calls `optics-demo.invalid` a customer OpenAI call, the operator repeats the banner and returns to B08. The file stays a stub.

## F3 — Narrated enforcement (rehearsal)

If a speaker says the room blocked, redacted, or capped spend, the operator stops that sentence. No file is created to illustrate the sentence. Beat B16 is the scripted form of this refusal.

## F4 — `prove --from` on bytes Optics did not write (rehearsal)

`docs/products/optics/KNOWN-LIMITATIONS.md` records that `prove --from` can render JSON that Optics did not write. The room does not use `--from`. If a rehearsal renders the F1 defect that way, the expected result is a proof with no simulation label. That result is a failed room, not a feature to show investors.

## F5 — Second demo changes the id (rehearsal)

A second `demo` writes a second trace id and a second timestamp. Expected outputs are invariants, not a frozen transcript. The room runs `demo` once so `prove --list` shows one run.

## F6 — Discover total (rehearsal)

`discover` after `demo` includes `optics-demo.invalid` in the observed-locally count. Expected. The operator does not subtract it in the CLI, because the CLI has no demo exclusion in 0.3.24. The operator excludes it in speech and on the banner. Automatic exclusion of demo files is listed as not a product guarantee in `docs/products/optics/KNOWN-LIMITATIONS.md`.

## Pass for the injection portion of the room

F1 was planted only in the demo home, was not proved, was not counted as customer activity, did not resume a success narration, and was removed by reset. B16 through B18 were spoken as the close. No enforcement token was written.
