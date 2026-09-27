/**
 * Normative data for the benchmark and performance-qualification scaffold.
 * Edit this file, then run scripts/emit-pack.mjs. The checker compares
 * the emitted JSON to a fresh build so the two cannot drift.
 */

import {
  COVERAGE,
  ENTERPRISE_NOTE,
  LINEUP,
  OPTICS_DESIGN,
  OPTICS_UNMET,
  PHANTOM_NOTE,
  STAGE1_COMMON,
} from "./cell-notes.mjs";

export const SCHEMA = "vantio.planning.benchmark-framework/v1";
export const AUDIENCE = "INTERNAL_RESTRICTED";
export const PRODUCER_CLASSIFICATION = "BENCHMARK_FRAMEWORK_READY_FOR_COUNCIL";
export const BASE_SHA = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";

export const STAGE_IDS = [
  "BEST_IN_CLASS_DESIGN_TARGET",
  "PRODUCTION_GRADE_INTERNAL_CANDIDATE",
  "CLEAN_HOST_PROVED_CANDIDATE",
  "PROVED_EXTERNAL_CANDIDATE",
  "INDEPENDENTLY_BENCHMARKED_CANDIDATE",
  "CUSTOMER_VALIDATED_CANDIDATE",
  "EVIDENCE_BACKED_BEST_IN_CLASS",
];

export const PRODUCTS = [
  {
    id: "optics",
    name: "Vantio Optics",
    owning_repo: "vantioai/vantio-open-core",
  },
  {
    id: "phantom_engine",
    name: "Vantio Phantom Engine",
    owning_repo: "vantioai/vantio-phantom-engine",
  },
  {
    id: "enterprise",
    name: "Vantio Enterprise",
    owning_repo: "talk-to-sales",
  },
];

export const METRIC_IDS = [
  "cpu",
  "memory",
  "disk",
  "evidence_growth",
  "startup",
  "policy_load",
  "decision_latency",
  "connection_latency",
  "throughput",
  "event_loss",
  "backpressure",
  "reboot_recovery",
  "degradation_recovery",
  "rollback",
  "uninstall",
];

const METRIC_DIMENSIONS = {
  cpu: ["operational_overhead", "performance"],
  memory: ["operational_overhead", "performance"],
  disk: ["operational_overhead", "performance"],
  evidence_growth: ["aggregate_limits", "operational_overhead", "performance"],
  startup: ["operational_overhead", "performance"],
  policy_load: ["performance"],
  decision_latency: ["egress", "performance"],
  connection_latency: ["egress", "performance"],
  throughput: ["egress", "performance"],
  event_loss: ["egress", "evidence", "performance"],
  backpressure: ["performance"],
  reboot_recovery: ["health", "performance"],
  degradation_recovery: ["health", "performance"],
  rollback: ["performance", "rollback"],
  uninstall: ["performance", "removal"],
};

export const DIMENSIONS = [
  {
    id: "ingress",
    title: "Ingress",
    question: "Inbound traffic into the workload or the host is observed or controlled, and the coverage of that path is stated.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "egress",
    title: "Egress",
    question: "Outbound agent or workload traffic is observed or controlled on the paths the product names.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "host",
    title: "Host",
    question: "A host the customer enrolls carries the control even when the process skips the application wrap.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "descendant_lineage",
    title: "Descendant lineage",
    question: "A child or further descendant is covered by the same observation or enforcement as its parent, and the record shows lineage instead of inferring it.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "workload_identity_integrity",
    title: "Workload identity and integrity",
    question: "A workload identity, distinct from a process id, is consumed with an integrity statement. The product does not become the identity provider.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "sequential",
    title: "Sequential limits",
    question: "A limit applies to one call or one policy decision before the next decision.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "aggregate_limits",
    title: "Aggregate limits",
    question: "A limit sums bytes, calls, or spend across a window, and crossing it is explicit.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "simulation",
    title: "Simulation",
    question: "Synthetic or demo evidence is labeled and stays out of operational totals.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "canary",
    title: "Canary",
    question: "A policy or release is exposed to a subset of workloads before the rest.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "rollback",
    title: "Rollback",
    question: "A source, package, or schema rollback leaves already recorded evidence readable.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "revocation",
    title: "Revocation",
    question: "Expiry or revocation removes the granted authority and leaves no expanded remainder.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "evidence",
    title: "Evidence",
    question: "Observation or enforcement produces a durable record a later reader can scope.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "independent_verification",
    title: "Independent verification",
    question: "A verifier outside the producing team can check the record without asking the producer to restate it.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "health",
    title: "Health",
    question: "Product health is a separate channel from workload success, and a green value on one channel does not fill another.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "coverage_truth",
    title: "Coverage truth",
    question: "The product names what is covered and what is not, and partial coverage is not displayed as complete.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "deployment",
    title: "Deployment",
    question: "The product is placed on a host and brought to a stated health under a recorded procedure.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "removal",
    title: "Removal",
    question: "The product and its local evidence can leave the host under a recorded procedure.",
    measurement_blocks_from_order: 5,
  },
  {
    id: "performance",
    title: "Performance",
    question: "Startup, policy load, decision latency, connection latency, throughput, loss, backpressure, and recovery are measured on a named workload.",
    measurement_blocks_from_order: 2,
  },
  {
    id: "operational_overhead",
    title: "Operational overhead",
    question: "CPU, memory, disk, evidence growth, and startup cost added by the product are measured against the same workload without it.",
    measurement_blocks_from_order: 2,
  },
];

const SLOTS = {
  internal_candidate_record: "NOT_PRESENT",
  clean_host_record: "NOT_PRESENT",
  independent_verifier: "NOT_PRESENT",
  benchmark_record: "NOT_PRESENT",
  customer_window: "NOT_PRESENT",
};

const BLOCKED_FROM = {
  2: "internal_candidate_record is NOT_PRESENT. This force executed no internal production-candidate run.",
  3: "clean_host_record is NOT_PRESENT. docs/planning/clean-host-lifecycle/00-PROGRAM-BOUNDARY.md records evidence_tier UNSET and stranger_host NOT_RUN.",
  4: "independent_verifier is NOT_PRESENT. A document council pass remains a document result.",
  5: "benchmark_record is NOT_PRESENT. Required metrics that are NOT_MEASURED block this stage. Estimates are prohibited.",
  6: "customer_window is NOT_PRESENT.",
  7: "EVIDENCE_BACKED_BEST_IN_CLASS requires every earlier stage to be SATISFIED. No cell in this pack has that run of stages.",
};

function requiredMetrics(dimensionId) {
  return METRIC_IDS.filter((id) => METRIC_DIMENSIONS[id].includes(dimensionId));
}

function buildStages(highestSatisfiedOrder, stageEvidence) {
  return STAGE_IDS.map((id, index) => {
    const order = index + 1;
    if (order <= highestSatisfiedOrder) {
      return {
        order,
        id,
        status: "SATISFIED",
        blocked_by: null,
        evidence: stageEvidence[id],
      };
    }
    return {
      order,
      id,
      status: "NOT_REACHED",
      blocked_by: order === firstGapOrder(highestSatisfiedOrder) ? null : STAGE_IDS[highestSatisfiedOrder],
      evidence: stageEvidence[id],
    };
  });
}

function firstGapOrder(highestSatisfiedOrder) {
  return highestSatisfiedOrder + 1;
}

function currentStage(highestSatisfiedOrder) {
  if (highestSatisfiedOrder === 0) return "NONE";
  return STAGE_IDS[highestSatisfiedOrder - 1];
}

function laterEvidence(fromOrder) {
  const evidence = {};
  for (let order = fromOrder; order <= 7; order += 1) {
    evidence[STAGE_IDS[order - 1]] = [BLOCKED_FROM[order]];
  }
  return evidence;
}

function cell(spec) {
  const dimension = DIMENSIONS.find((item) => item.id === spec.dimension_id);
  const evidence = {
    ...laterEvidence(spec.highest + 1),
    ...spec.evidence,
  };
  for (const id of STAGE_IDS) {
    if (!evidence[id] || evidence[id].length === 0) {
      throw new Error(`missing evidence for ${spec.product_id}/${spec.dimension_id}/${id}`);
    }
  }
  return {
    product_id: spec.product_id,
    dimension_id: spec.dimension_id,
    statement_class: spec.statement_class,
    lineup_claim_effect: "DOES_NOT_SATISFY_ANY_STAGE",
    documented_current_behavior: spec.documented_current_behavior,
    sources: spec.sources,
    not_accepted: spec.not_accepted,
    required_metrics: requiredMetrics(spec.dimension_id),
    measurement_blocks_from_order: dimension.measurement_blocks_from_order,
    evidence_slots: { ...SLOTS },
    producer_reexecution: "NOT_EXECUTED",
    current_stage: currentStage(spec.highest),
    stages: buildStages(spec.highest, evidence),
  };
}


function opticsDesign(dimensionId, statement) {
  return {
    product_id: "optics",
    dimension_id: dimensionId,
    statement_class: "ARCHITECTURE_DESIGN_TARGET",
    highest: 1,
    documented_current_behavior: statement.current,
    sources: statement.sources,
    not_accepted: statement.not_accepted ?? [],
    evidence: {
      BEST_IN_CLASS_DESIGN_TARGET: [...statement.design, ...STAGE1_COMMON],
      ...laterEvidence(2),
      PRODUCTION_GRADE_INTERNAL_CANDIDATE: statement.stage2,
    },
  };
}

function unmet(productId, dimensionId, spec) {
  return {
    product_id: productId,
    dimension_id: dimensionId,
    statement_class: spec.statement_class,
    highest: 0,
    documented_current_behavior: spec.current,
    sources: spec.sources,
    not_accepted: spec.not_accepted ?? [],
    evidence: {
      BEST_IN_CLASS_DESIGN_TARGET: spec.why,
      ...laterEvidence(2),
    },
  };
}

function cellsForProduct(productId, table, designTable) {
  return DIMENSIONS.map((dimension) => {
    if (designTable && designTable[dimension.id]) {
      return cell(opticsDesign(dimension.id, designTable[dimension.id]));
    }
    const spec = table[dimension.id];
    if (!spec) throw new Error(`missing ${productId}/${dimension.id}`);
    return cell(unmet(productId, dimension.id, spec));
  });
}

export function buildCells() {
  return [
    ...cellsForProduct("optics", OPTICS_UNMET, OPTICS_DESIGN),
    ...cellsForProduct("phantom_engine", PHANTOM_NOTE, null),
    ...cellsForProduct("enterprise", ENTERPRISE_NOTE, null),
  ];
}

export function claimLadder() {
  return {
    schema: SCHEMA,
    audience: AUDIENCE,
    document: "CLAIM-LADDER",
    producer_classification: PRODUCER_CLASSIFICATION,
    base_sha: BASE_SHA,
    skip_rule: "A stage may be SATISFIED only when every lower order is SATISFIED. There is no skip status. NOT_REACHED is the status of every stage the evidence does not meet.",
    stages: [
      {
        order: 1,
        id: "BEST_IN_CLASS_DESIGN_TARGET",
        entry: [
          "The owning product is named.",
          "Behavior is stated in a source other than a lineup checkmark.",
          "Non-goals are stated.",
          "The evidence required to enter PRODUCTION_GRADE_INTERNAL_CANDIDATE is stated.",
          "Measurement posture is a founder-set target or an explicit NOT_SET or NOT_MEASURED. An example number is not a target.",
          "For this initial population, an Optics cell also requires OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED on the gate that contains the design. A planning packet whose council is PENDING_INDEPENDENT_COUNCIL is not accepted.",
        ],
      },
      {
        order: 2,
        id: "PRODUCTION_GRADE_INTERNAL_CANDIDATE",
        entry: [
          "Stage 1 is SATISFIED.",
          "internal_candidate_record is a run of the design's implementation, not NOT_PRESENT.",
          "Repository unit tests that the known-limitations page says are not a certificate do not fill the slot.",
          "When measurement_blocks_from_order is 2, every required metric is MEASURED.",
        ],
      },
      {
        order: 3,
        id: "CLEAN_HOST_PROVED_CANDIDATE",
        entry: [
          "Stage 2 is SATISFIED.",
          "clean_host_record is present. evidence_tier UNSET does not fill the slot.",
          "A company host, a developer machine, and local kind are not this stage.",
        ],
      },
      {
        order: 4,
        id: "PROVED_EXTERNAL_CANDIDATE",
        entry: [
          "Stage 3 is SATISFIED.",
          "independent_verifier names a verifier outside the producing team.",
          "A document council pass does not fill the slot.",
          "A local prove render does not fill the slot.",
        ],
      },
      {
        order: 5,
        id: "INDEPENDENTLY_BENCHMARKED_CANDIDATE",
        entry: [
          "Stage 4 is SATISFIED.",
          "benchmark_record is present.",
          "Every required metric for the dimension is MEASURED, with instrument, workload, and sample count.",
          "NOT_MEASURED blocks the stage. An estimate blocks the stage.",
        ],
      },
      {
        order: 6,
        id: "CUSTOMER_VALIDATED_CANDIDATE",
        entry: [
          "Stage 5 is SATISFIED.",
          "customer_window names a customer workload and a window.",
          "Internal proof and external lab proof do not fill the slot.",
        ],
      },
      {
        order: 7,
        id: "EVIDENCE_BACKED_BEST_IN_CLASS",
        entry: [
          "Stage 6 is SATISFIED.",
          "A comparator against documented peer capabilities, excluding marketing checkmarks, shows the measured result meets the design target.",
          "Limitations stay stated beside the result.",
        ],
      },
    ],
  };
}

export function lineupIgnored() {
  const rows = [
    ["observe_wrapped_calls", "stated", "stated", "stated"],
    ["block_by_hostname_wrapped", "absent", "stated", "stated"],
    ["pii_redaction_wrapped", "absent", "stated", "stated"],
    ["spend_size_caps_wrapped", "absent", "stated", "stated"],
    ["host_enforcement_enrolled_linux", "absent", "stated", "stated"],
    ["fork_inheritance_enrolled_hosts", "absent", "stated", "stated"],
    ["cidr_k8s_network_policy_enrolled", "absent", "stated", "stated"],
    ["durable_ledger_dual_control", "absent", "partial", "stated"],
  ];
  return rows.map(([id, optics, phantom_engine, enterprise]) => ({
    id,
    source: LINEUP,
    optics,
    phantom_engine,
    enterprise,
    claim_effect: "DOES_NOT_SATISFY_ANY_STAGE",
    diligence: "docs/programs/production-readiness/diligence/09-CAPABILITIES.md sets every cell's evidence tier to UNSET.",
  }));
}

export function excludedPractices() {
  return [
    {
      id: "privacy_canary_fixture",
      dimension_refused: "canary",
      note: "A marker string asserted absent from stored bytes is a privacy fixture. It is a different practice from a staged rollout canary.",
    },
    {
      id: "lineup_checkmark",
      dimension_refused: null,
      note: "A checkmark or the word partial in docs/PRODUCT_LINEUP.md satisfies no claim stage.",
    },
    {
      id: "roadmap_example_latency",
      dimension_refused: "performance",
      text: "less than 5 milliseconds at p99",
      source: "docs/internal/optics-best-in-class-roadmap.md section 6 item 14",
      disposition: "NOT_ADOPTED",
      note: "The architecture pack leaves NFR-PER-CALL-OVERHEAD at NOT_SET. This scaffold does not estimate.",
    },
    {
      id: "historical_gate_wrap_spec",
      dimension_refused: "sequential",
      source: "docs/specs/WRAP_UNDICI_WS_FRAMES_2026-08-15.md",
      note: "Historical spec. The current product boundary says Optics does not block, redact, or apply spend caps.",
    },
    {
      id: "wsl2_repository_sentence",
      dimension_refused: null,
      source: COVERAGE,
      note: "OBSERVED_FROM_REPOSITORY_EVIDENCE with this_force NOT_EXECUTED satisfies no stage. WSL2 is not a clean host and not a managed-cloud cluster.",
    },
  ];
}

export function comparatorMatrix() {
  const cells = buildCells();
  return {
    schema: SCHEMA,
    audience: AUDIENCE,
    document: "COMPARATOR-MATRIX",
    producer_classification: PRODUCER_CLASSIFICATION,
    base_sha: BASE_SHA,
    comparison_rule: "Compare documented behavior. Lineup checkmarks are listed and then ignored for stage status.",
    products: PRODUCTS,
    dimensions: DIMENSIONS.map((dimension) => ({
      ...dimension,
      required_metrics: requiredMetrics(dimension.id),
    })),
    lineup_ignored: lineupIgnored(),
    excluded_practices: excludedPractices(),
    cells,
  };
}

export function performanceScaffold() {
  return {
    schema: SCHEMA,
    audience: AUDIENCE,
    document: "PERFORMANCE-SCAFFOLD",
    producer_classification: PRODUCER_CLASSIFICATION,
    base_sha: BASE_SHA,
    rule: "A metric without a measurement record is NOT_MEASURED. This pack estimates nothing.",
    result_enum: ["NOT_MEASURED", "MEASURED"],
    measured_record_required_fields: ["instrument", "workload", "started_at_utc", "sample_count", "result_value"],
    metrics: METRIC_IDS.map((id) => ({
      id,
      result: "NOT_MEASURED",
      unit: null,
      workload: "NOT_DEFINED",
      instrument: "NOT_DEFINED",
      sample_count: "NOT_MEASURED",
      percentiles: "NOT_MEASURED",
      result_value: null,
      estimate: "PROHIBITED",
      dimensions: METRIC_DIMENSIONS[id],
      note: "No measurement was taken in this force.",
    })),
    rejected_examples: [
      {
        id: "roadmap-per-call-example",
        disposition: "NOT_ADOPTED",
        source: "docs/internal/optics-best-in-class-roadmap.md section 6 item 14",
        architecture_target: "NFR-PER-CALL-OVERHEAD NOT_SET",
        result: "NOT_MEASURED",
      },
    ],
  };
}

export function scoreMarkdown() {
  const cells = buildCells();
  const lines = [
    "# Comparator score",
    "",
    "Audience: INTERNAL_RESTRICTED",
    "",
    "Generated from `scripts/framework-lib.mjs`. The checker rebuilds this table.",
    "",
    `Producer classification: \`${PRODUCER_CLASSIFICATION}\``,
    "",
    "Current stage is the last consecutive SATISFIED stage. NONE means stage 1 is NOT_REACHED. `BEST_IN_CLASS_DESIGN_TARGET` is the name of stage 1, a written design. It is not a measured result and not a comparison against another product. Later stages are present in `COMPARATOR-MATRIX.json` and are NOT_REACHED.",
    "",
    "| Dimension | Optics | Phantom Engine | Enterprise |",
    "| --- | --- | --- | --- |",
  ];
  for (const dimension of DIMENSIONS) {
    const cols = PRODUCTS.map((product) => {
      const match = cells.find((item) => item.product_id === product.id && item.dimension_id === dimension.id);
      return `\`${match.current_stage}\``;
    });
    lines.push(`| ${dimension.title} | ${cols.join(" | ")} |`);
  }
  lines.push("");
  lines.push("No cell is `EVIDENCE_BACKED_BEST_IN_CLASS`. No performance metric is measured.");
  lines.push("");
  return `${lines.join("\n")}\n`;
}

export function packJson() {
  return {
    "CLAIM-LADDER.json": claimLadder(),
    "COMPARATOR-MATRIX.json": comparatorMatrix(),
    "PERFORMANCE-SCAFFOLD.json": performanceScaffold(),
    "03-SCORE.md": scoreMarkdown(),
  };
}
