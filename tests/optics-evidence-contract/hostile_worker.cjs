"use strict";

const { validateEvidence, canonicalJson } = require("../../packages/optics-evidence-contract/src/validate.cjs");

const mode = process.argv[2];

function hangingInput() {
  const input = { record_type: "observation_event" };
  Object.defineProperty(input, "boom", {
    enumerable: true,
    get() {
      hangingInput.calls += 1;
      while (true) {
        // External timeout owns this process. The validator must not reach this getter.
      }
    },
  });
  return input;
}

hangingInput.calls = 0;

if (mode === "hang") {
  const input = hangingInput();
  input.boom;
} else if (mode === "validate") {
  const input = hangingInput();
  const result = validateEvidence(input);
  process.stdout.write("CALLS " + String(hangingInput.calls) + "\n");
  process.stdout.write(canonicalJson(result));
} else {
  process.stderr.write("usage: hostile_worker.cjs validate|hang\n");
  process.exit(2);
}
