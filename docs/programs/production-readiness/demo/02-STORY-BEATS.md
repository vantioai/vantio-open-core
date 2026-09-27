# Story beats B01–B18

Audience: INTERNAL_RESTRICTED

`founder_text` is `ABSENT` on every beat. The Founder Master Program text that would number beats 1–18 is not in this repository. These ids are the design sequence. Replace the titles when founder text lands. Keep the simulation-label rule and the command list.

Each beat has one room purpose. The operator does not skip ahead and does not add a command outside the list below. B15 runs `discover` and then the F1 checklist, in that order.

| Beat | Room action | Label | Command or speech |
| --- | --- | --- | --- |
| B01 | State the room contract | `NARRATED_BOUNDARY` | Speech. No event file |
| B02 | State the three-product lineup | `NARRATED_BOUNDARY` | Speech from the lineup docs |
| B03 | Show the binary version | `NARRATED_BOUNDARY` | `node packages/vantio-cli/bin/vantio.js --version` |
| B04 | Show local status on an empty demo home | `NARRATED_BOUNDARY` | `status` with telemetry disabled and no registry check |
| B05 | State the observe mechanism | `NARRATED_BOUNDARY` | Speech. No live patch in this beat |
| B06 | State coverage and the unobserved gap | `NARRATED_BOUNDARY` | Speech from the supported-paths docs |
| B07 | Run the in-process demo | `SIMULATED_DEMO` | `demo` after the banner |
| B08 | Open the run file and name the missing origin | `SIMULATED_DEMO` | Read the JSON. Do not edit it |
| B09 | Render proof for that trace | `SIMULATED_DEMO` | `prove --run=<trace> --format=md` |
| B10 | Say what the file contains and what it omits | `SIMULATED_DEMO` | Speech tied to the open file |
| B11 | Separate Optics status from application outcome | `NARRATED_BOUNDARY` | Speech from the status-token docs |
| B12 | State what free Optics leaves to other products | `NARRATED_BOUNDARY` | Speech. No enforce event |
| B13 | State the Phantom Engine boundary without running it | `NARRATED_BOUNDARY` | Speech. No host enrollment |
| B14 | Read the claim rows the room must not improvise | `NARRATED_BOUNDARY` | Speech from `08-CLAIM-LEDGER.json` |
| B15 | Run `discover` under the `SIMULATED_DEMO` banner, then inject one unlabeled synthetic and apply the stop rule | `INJECTED_UNLABELED_SYNTHETIC` | `discover`, then the F1 checklist in `07-FAILURE-INJECTION-OUTLINE.md` |
| B16 | Refuse a narrated block | `NARRATED_BOUNDARY` | Speech. No block token is created |
| B17 | Reset the demo home | `NARRATED_BOUNDARY` | Outline in `05-RESET-OUTLINE.md` |
| B18 | Close on the limitation ledger | `NARRATED_BOUNDARY` | Speech from `09-LIMITATION-LEDGER.json` |

## Grounding

| Beat | Source read for this design |
| --- | --- |
| B01, B07, B08, B09, B10 | `packages/vantio-cli/bin/vantio.js` `demoCommand`; design-host transcript in `06-EXPECTED-OUTPUTS.md` |
| B02, B12, B13 | `docs/PRODUCT_LINEUP.md`, `docs/governance/canonical/product-boundary.md`, `docs/observe-only.md` |
| B03, B04 | `packages/vantio-cli/package.json` version `0.3.24`; `statusCommand` |
| B05 | `README.md` and `docs/governance/canonical/product-boundary.md`: `NODE_OPTIONS --require` |
| B06 | `docs/products/optics/SUPPORTED-PATHS.md`, `docs/governance/canonical/supported-paths.md`, `docs/governance/canonical/known-limitations.md` |
| B11 | `docs/governance/canonical/status-tokens.md`, `docs/products/optics/STATUS-AND-OUTCOMES.md` |
| B14 | `08-CLAIM-LEDGER.json` |
| B15 | `07-FAILURE-INJECTION-OUTLINE.md`; `06-EXPECTED-OUTPUTS.md` discover invariants; `docs/products/optics/KNOWN-LIMITATIONS.md` (demo files look like other runs; evidence origin is absent on current files) |
| B16 | `docs/governance/STATUS-TOKENS.json` action tokens exist in the SDK type. Free Optics display copy does not use them as the Observe outcome |
| B17 | `05-RESET-OUTLINE.md` |
| B18 | `09-LIMITATION-LEDGER.json` |

## Commands the script may run

Only these, in this order, against the isolated demo home:

1. `--version`
2. `status`
3. `demo`
4. A file read of the new run JSON
5. `prove --list`
6. `prove --run=<that trace> --format=md`
7. `discover`

`discover` is step 7. The room runs it once at B15, under the `SIMULATED_DEMO` banner, before F1 is planted. The spoken observed-locally line refers to that output. The room does not run `discover` on the planted file.

`demo --json` is the expected-output reference. The spoken script uses human `demo` once so the room hears the stub sentence. The spoken script does not run JSON mode. A second `demo` would add a second run file. The script runs `demo` once.

Forbidden in the room: `vantio run` against a live model, `--check-registry`, `prove` with default HTML, `prove --from` on an unlabeled file, `logout`, any Phantom Engine binary, and any command that is not in the list above.
