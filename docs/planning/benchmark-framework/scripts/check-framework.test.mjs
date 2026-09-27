import assert from "node:assert/strict";
import test from "node:test";
import { checkPack, validateCells, validatePerformance } from "./check-framework.mjs";
import { STAGE_IDS, packJson } from "./framework-lib.mjs";

test("benchmark pack matches the library and the ladder rules", () => {
  const errors = checkPack();
  assert.deepEqual(errors, []);
});

test("a skipped stage is rejected", () => {
  const matrix = packJson()["COMPARATOR-MATRIX.json"];
  const cell = structuredClone(matrix.cells[0]);
  cell.stages[0].status = "NOT_REACHED";
  cell.stages[1].status = "SATISFIED";
  cell.stages[1].blocked_by = null;
  cell.current_stage = "PRODUCTION_GRADE_INTERNAL_CANDIDATE";
  const errors = validateCells([cell, ...matrix.cells.slice(1)], matrix.dimensions);
  assert.ok(errors.some((error) => error.includes("skipped")));
});

test("a measured value cannot be smuggled into an unmeasured metric", () => {
  const performance = packJson()["PERFORMANCE-SCAFFOLD.json"];
  performance.metrics[0].result = "NOT_MEASURED";
  performance.metrics[0].result_value = 1;
  const errors = validatePerformance(performance);
  assert.ok(errors.some((error) => error.includes("cpu")));
});

test("stage ids stay in ladder order", () => {
  assert.deepEqual(
    STAGE_IDS,
    [
      "BEST_IN_CLASS_DESIGN_TARGET",
      "PRODUCTION_GRADE_INTERNAL_CANDIDATE",
      "CLEAN_HOST_PROVED_CANDIDATE",
      "PROVED_EXTERNAL_CANDIDATE",
      "INDEPENDENTLY_BENCHMARKED_CANDIDATE",
      "CUSTOMER_VALIDATED_CANDIDATE",
      "EVIDENCE_BACKED_BEST_IN_CLASS",
    ],
  );
});
