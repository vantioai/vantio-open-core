"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const matrix = require("../../docs/planning/optics-pkg02/RECORD-COMPATIBILITY-MATRIX.json");

const PROVED = new Set([
  "cli_0_3_24",
  "future_cli",
  "missing_canonical",
  "mixed_versions",
  "unknown_fields_and_enums",
]);

test("Unit D flips only the future CLI cells it proved", () => {
  assert.equal(matrix.activates_unit_d, true);
  assert.equal(matrix.activates_unit_e, false);
  assert.equal(matrix.unit_d_shipped_product, false);
  assert.equal(matrix.unit_d_future_cli_version, "0.4.0-pkg02-unit-d");
  assert.equal(matrix.cell_count, 104);
  assert.equal(matrix.cells.length, 104);
  let proved = 0;
  for (const cell of matrix.cells) {
    const flipped = cell.writer === "future_cli" && PROVED.has(cell.reader);
    if (flipped) {
      proved += 1;
      assert.equal(cell.achievement, "UNIT_D_PROVED_NOT_SHIPPED");
      assert.equal(cell.activates_unit_d, true);
      assert.equal(cell.activates_unit_e, false);
      assert.equal(cell.shipped_product, false);
      assert.notEqual(cell.achievement, "SHIPPED");
    } else {
      assert.equal(cell.achievement, "NOT_SHIPPED", cell.writer + " " + cell.reader);
      assert.equal(cell.activates_unit_d, undefined);
    }
    if (cell.writer === "future_python" || cell.reader === "future_python" || cell.writer === "python_3_1_0") {
      assert.equal(cell.achievement, "NOT_SHIPPED");
    }
  }
  assert.equal(proved, 5);
});
