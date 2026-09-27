import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import {
  BASE_SHA,
  DIMENSIONS,
  METRIC_IDS,
  PRODUCER_CLASSIFICATION,
  PRODUCTS,
  STAGE_IDS,
  packJson,
} from "./framework-lib.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const SLOT_BLOCKS_FROM = {
  internal_candidate_record: 2,
  clean_host_record: 3,
  independent_verifier: 4,
  benchmark_record: 5,
  customer_window: 6,
};

export function loadPack(dir = ROOT) {
  return {
    ladder: JSON.parse(readFileSync(join(dir, "CLAIM-LADDER.json"), "utf8")),
    matrix: JSON.parse(readFileSync(join(dir, "COMPARATOR-MATRIX.json"), "utf8")),
    performance: JSON.parse(readFileSync(join(dir, "PERFORMANCE-SCAFFOLD.json"), "utf8")),
    score: readFileSync(join(dir, "03-SCORE.md"), "utf8"),
    manifest: JSON.parse(readFileSync(join(dir, "BENCHMARK-MANIFEST.json"), "utf8")),
  };
}

export function freshPack() {
  return packJson();
}

function stageIndex(id) {
  const index = STAGE_IDS.indexOf(id);
  if (index < 0) throw new Error(`unknown stage ${id}`);
  return index;
}

export function validateCells(cells, dimensions) {
  const errors = [];
  const seen = new Set();
  if (cells.length !== PRODUCTS.length * dimensions.length) {
    errors.push(`cell count ${cells.length}`);
  }
  for (const product of PRODUCTS) {
    for (const dimension of dimensions) {
      const matches = cells.filter((cell) => cell.product_id === product.id && cell.dimension_id === dimension.id);
      if (matches.length !== 1) {
        errors.push(`expected one cell for ${product.id}/${dimension.id}, found ${matches.length}`);
        continue;
      }
      seen.add(`${product.id}/${dimension.id}`);
      errors.push(...validateCell(matches[0], dimension));
    }
  }
  if (seen.size !== PRODUCTS.length * dimensions.length) errors.push("duplicate or missing cells");
  return errors;
}

function validateCell(cell, dimension) {
  const errors = [];
  const label = `${cell.product_id}/${cell.dimension_id}`;
  if (cell.lineup_claim_effect !== "DOES_NOT_SATISFY_ANY_STAGE") {
    errors.push(`${label} lineup effect`);
  }
  if (cell.producer_reexecution !== "NOT_EXECUTED") errors.push(`${label} reexecution`);
  if (!Array.isArray(cell.stages) || cell.stages.length !== STAGE_IDS.length) {
    errors.push(`${label} stage count`);
    return errors;
  }
  let highest = 0;
  let firstGap = null;
  cell.stages.forEach((stage, index) => {
    if (stage.order !== index + 1 || stage.id !== STAGE_IDS[index]) {
      errors.push(`${label} stage order ${stage.id}`);
    }
    if (stage.status === "SATISFIED") {
      if (firstGap !== null) errors.push(`${label} skipped to ${stage.id}`);
      if (stage.blocked_by !== null) errors.push(`${label} satisfied stage has a blocker`);
      if (!Array.isArray(stage.evidence) || stage.evidence.length === 0) errors.push(`${label} empty evidence`);
      highest = stage.order;
    } else if (stage.status === "NOT_REACHED") {
      if (firstGap === null) firstGap = stage.id;
      const expectedBlock = stage.id === firstGap ? null : firstGap;
      if (stage.blocked_by !== expectedBlock) {
        errors.push(`${label} ${stage.id} blocked_by ${stage.blocked_by}, expected ${expectedBlock}`);
      }
    } else {
      errors.push(`${label} bad status ${stage.status}`);
    }
  });
  const expectedCurrent = highest === 0 ? "NONE" : STAGE_IDS[highest - 1];
  if (cell.current_stage !== expectedCurrent) {
    errors.push(`${label} current_stage ${cell.current_stage}, expected ${expectedCurrent}`);
  }
  if (cell.current_stage === "EVIDENCE_BACKED_BEST_IN_CLASS") {
    errors.push(`${label} best-in-class is not populated`);
  }
  for (const [slot, fromOrder] of Object.entries(SLOT_BLOCKS_FROM)) {
    if (cell.evidence_slots[slot] === "NOT_PRESENT") {
      for (const stage of cell.stages) {
        if (stage.order >= fromOrder && stage.status === "SATISFIED") {
          errors.push(`${label} ${stage.id} satisfied while ${slot} is NOT_PRESENT`);
        }
      }
    }
  }
  if (cell.measurement_blocks_from_order !== dimension.measurement_blocks_from_order) {
    errors.push(`${label} measurement gate`);
  }
  if (cell.required_metrics.join(",") !== dimension.required_metrics.join(",")) {
    errors.push(`${label} required metrics`);
  }
  return errors;
}

export function validatePerformance(performance) {
  const errors = [];
  const ids = performance.metrics.map((metric) => metric.id);
  if (ids.join(",") !== METRIC_IDS.join(",")) errors.push("metric id order");
  for (const metric of performance.metrics) {
    if (metric.result !== "NOT_MEASURED") errors.push(`${metric.id} result ${metric.result}`);
    if (metric.result_value !== null) errors.push(`${metric.id} has a value`);
    if (metric.estimate !== "PROHIBITED") errors.push(`${metric.id} estimate`);
    if (metric.sample_count !== "NOT_MEASURED") errors.push(`${metric.id} sample_count`);
    if (metric.percentiles !== "NOT_MEASURED") errors.push(`${metric.id} percentiles`);
    if (metric.unit !== null) errors.push(`${metric.id} unit`);
    if (typeof metric.result_value === "number") errors.push(`${metric.id} numeric`);
  }
  const serialized = JSON.stringify(performance);
  if (serialized.includes("<5")) errors.push("example latency figure was copied into the scaffold");
  if (/"result"\s*:\s*"MEASURED"/.test(serialized)) errors.push("MEASURED present");
  return errors;
}

export function validateLadder(ladder) {
  const errors = [];
  if (ladder.stages.length !== 7) errors.push("ladder length");
  ladder.stages.forEach((stage, index) => {
    if (stage.order !== index + 1 || stage.id !== STAGE_IDS[index]) errors.push(`ladder stage ${stage.id}`);
    if (!Array.isArray(stage.entry) || stage.entry.length === 0) errors.push(`ladder entry ${stage.id}`);
  });
  return errors;
}

export function validateManifest(manifest, dir = ROOT) {
  const errors = [];
  if (manifest.producer_classification !== PRODUCER_CLASSIFICATION) errors.push("classification");
  if (manifest.base_sha !== BASE_SHA) errors.push("base sha");
  if (manifest.council_status !== "PENDING_INDEPENDENT_COUNCIL") errors.push("council");
  if (manifest.council_verdict !== null) errors.push("verdict");
  if (manifest.merge !== false) errors.push("merge");
  const closed = manifest.closed;
  for (const key of [
    "customer_deploy",
    "stranger_host_execution",
    "announcement",
    "credential_use",
    "money_movement",
    "cli_reopen",
    "python_byte_mutation",
    "pe_confidential_copied",
  ]) {
    if (closed[key] !== false) errors.push(`closed ${key}`);
  }
  for (const [rel, expected] of Object.entries(manifest.files_sha256)) {
    const body = readFileSync(join(dir, rel));
    const actual = createHash("sha256").update(body).digest("hex");
    if (actual !== expected) errors.push(`sha256 ${rel}`);
  }
  return errors;
}

export function checkPack(dir = ROOT) {
  const loaded = loadPack(dir);
  const fresh = freshPack();
  const errors = [];
  if (JSON.stringify(loaded.ladder) !== JSON.stringify(fresh["CLAIM-LADDER.json"])) errors.push("CLAIM-LADDER drift");
  if (JSON.stringify(loaded.matrix) !== JSON.stringify(fresh["COMPARATOR-MATRIX.json"])) errors.push("matrix drift");
  if (JSON.stringify(loaded.performance) !== JSON.stringify(fresh["PERFORMANCE-SCAFFOLD.json"])) {
    errors.push("performance drift");
  }
  if (loaded.score !== fresh["03-SCORE.md"]) errors.push("score drift");
  errors.push(...validateLadder(loaded.ladder));
  errors.push(...validateCells(loaded.matrix.cells, loaded.matrix.dimensions));
  errors.push(...validatePerformance(loaded.performance));
  errors.push(...validateManifest(loaded.manifest, dir));
  const measured = loaded.matrix.cells.filter((cell) => cell.current_stage !== "NONE" && cell.current_stage !== "BEST_IN_CLASS_DESIGN_TARGET");
  if (measured.length !== 0) errors.push("a cell is past the design-target stage");
  return errors;
}

function main() {
  const errors = checkPack();
  if (errors.length > 0) {
    for (const error of errors) console.error(error);
    process.exit(1);
  }
  console.log(PRODUCER_CLASSIFICATION);
  console.log("council PENDING_INDEPENDENT_COUNCIL");
  console.log("cells", PRODUCTS.length * DIMENSIONS.length);
  console.log("metrics NOT_MEASURED", METRIC_IDS.length);
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) main();
