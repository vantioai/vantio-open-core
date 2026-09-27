/**
 * Documented cell notes for the comparator. Stage status is assigned in framework-lib.mjs.
 */

const ARCH_GATE = "docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md";
const ARCH_COUNCIL = "docs/architecture/optics-foundation/10-INDEPENDENT-COUNCIL-REPORT.md";
const KNOWN = "docs/products/optics/KNOWN-LIMITATIONS.md";
const PATHS = "docs/products/optics/SUPPORTED-PATHS.md";
const BOUNDARY = "docs/governance/canonical/product-boundary.md";
export const LINEUP = "docs/PRODUCT_LINEUP.md";
const A5 = "docs/architecture/optics-foundation/06-SELF-OBSERVABILITY-AND-RELIABILITY.md";
const P24 = "docs/planning/phantom-engine-production/04-P24-HEALTH-AND-COVERAGE.md";
export const COVERAGE = "docs/planning/phantom-engine-production/COVERAGE-MATRIX.json";
const EG = "docs/planning/enterprise-governance/00-PROGRAM-BOUNDARY.md";
const E2 = "docs/planning/enterprise-governance/02-E2-DELEGATED-AUTHORITY.md";

export const STAGE1_COMMON = [
  `${ARCH_COUNCIL} classification OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED accepts the named gate as an architecture document.`,
  `${ARCH_GATE} states Gate 8 is closed and that a document gate assigns none of UNIT_PROVED, INTEGRATION_PROVED, STRANGER_HOST_PROVED, PROVED_EXTERNAL, or CUSTOMER_VALIDATED.`,
  "Numeric targets in the architecture budget table stay NOT_SET. This pack does not estimate a replacement number.",
];

const INTERNAL_CANDIDATE_ABSENT =
  "internal_candidate_record is NOT_PRESENT. This force executed no internal production-candidate run.";

export const OPTICS_DESIGN = {
  egress: {
    current:
      "Wrapped in-scope egress is recorded as OBSERVED. A process that is not wrapped, a grandchild that does not inherit the wrapper, and a host outside the catalog produce no row.",
    sources: [BOUNDARY, PATHS, "docs/observe-only.md", "docs/architecture/optics-foundation/05-CORRELATION-AND-QUERY-CONTRACT.md", A5],
    design: [
      "Behavior: observe in-scope wrapped egress metadata. Prompts and completions stay off the record.",
      "Non-goals: Optics does not block, redact, or cap spend. Browser paths stay outside the wrap.",
      "Advance evidence named by the gate document: an implementation force after Gate 8, then the proof tiers. Gate 8 is closed.",
    ],
    stage2: [
      "Gate 8 is closed. The shipping CLI records wrapped calls and is not the architecture store, proof profile, or correlation contract.",
      `${KNOWN} states repository tests are unit and integration tests. They are not a customer deployment, a stranger-host proof, or a certificate.`,
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  descendant_lineage: {
    current:
      "A child that starts without the injected NODE_OPTIONS or PYTHONPATH is an unwrapped process. Writers do not set per-call span id, session id, or machine.",
    sources: [PATHS, KNOWN, "docs/architecture/optics-foundation/05-CORRELATION-AND-QUERY-CONTRACT.md"],
    design: [
      "A4 requires process_id, parent_process_id, run_id, and parent_run_id. A field that was not observed is stored null. Parenthood is not inferred from timestamps.",
      "The child-process test plan is specified and not executed. No evidence tier is assigned.",
      "A detached child gets no synthetic LOCAL_OBSERVATION row.",
    ],
    stage2: [
      "A4 section 1.1 says the child-process cases are specified, not executed.",
      `${KNOWN} states writers do not set per-call span id or session id.`,
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  aggregate_limits: {
    current: "No retention, prune, or max-size command exists. Run files stay until a person deletes them. Disk use is unbounded.",
    sources: [KNOWN, "docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md", A5],
    design: [
      "A5: with no customer limit the store grows and product health exposes database_size_bytes. With a customer limit the writer stops accepting rows and does not delete old rows to make room.",
      "NFR-DATABASE-SIZE current target is NOT_SET.",
      "Silent deletion to free space is outside the design.",
    ],
    stage2: [
      "The current JSON files have no configured limit and no stop record. That behavior is the known limitation, not an internal candidate of the A5 store rule.",
      INTERNAL_CANDIDATE_ABSENT,
    ],
    not_accepted: [
      {
        id: "lineup-spend-caps",
        source: LINEUP,
        effect: "DOES_NOT_SATISFY_ANY_STAGE",
        note: "The lineup marks spend and size caps on the Phantom Engine and Enterprise columns.",
      },
    ],
  },
  simulation: {
    current:
      "CLI 0.3.24 run files have no evidence_origin field. Demo files can look like other runs. The investor-demo rule is an operator banner, and the shipped reader does not apply it.",
    sources: [
      "docs/architecture/optics-foundation/02-EVIDENCE-AND-PRIVACY-CONTRACT.md",
      "docs/programs/production-readiness/demo/01-SIMULATION-LABEL-RULE.md",
      KNOWN,
    ],
    design: [
      "Writer origins include SIMULATED_DEMO. Demo and fixture evidence are excluded from operational trends.",
      "A legacy file whose destination is optics-demo.invalid is SIMULATED_DEMO on the architecture reader. The shipped CLI reader does not apply that rule.",
      "Stored action OBSERVED is not a simulation label.",
    ],
    stage2: [
      `${KNOWN} states evidence origin is absent and demo files look like other runs.`,
      "docs/programs/production-readiness/demo/01-SIMULATION-LABEL-RULE.md states CLI 0.3.24 does not enforce the simulation-label rule.",
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  rollback: {
    current:
      "Reinstalling the published CLI or Python package does not rewrite run files. There is no downgrade migration. Old and new files remain side by side until deleted.",
    sources: [
      "docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md",
      "docs/architecture/optics-foundation/04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md",
    ],
    design: [
      "A3: a corrupt or newer store is not replaced with an empty store. Original bytes stay. Newer-schema refusal uses recovery_state RECOVERY_REQUIRED.",
      "Interrupted migration resumes from the last committed version or stops. It does not delete the file and start over.",
      "Pre-migration backup failure aborts migration. The backup is not a proof.",
    ],
    stage2: [
      "No migrator exists. Gate 4 was accepted as architecture. The public reinstall procedure is the current package rollback and does not implement A3.",
      "The rollback performance metric is NOT_MEASURED.",
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  evidence: {
    current:
      "One JSON file per trace id. No content hash, signature, or evidence origin. prove --from can render JSON that Optics did not write. A crash during the single write can leave a partial file.",
    sources: [KNOWN, "docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md", ARCH_GATE],
    design: [
      "Option C is FOUNDER_RATIFIED_ARCHITECTURE_ONLY. SQLite is the future operational index. JSON proof stays portable.",
      "proof_sha256 is the SHA-256 of the stored proof.json bytes. The hash is not an attestation.",
      "No database exists in this repository.",
    ],
    stage2: [
      `${ARCH_GATE} records Gate 3 accepted as architecture and states no database exists.`,
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  independent_verification: {
    current:
      "vantio prove renders a local file. The known-limitations page states repository tests are not an external proof tier. No independent verifier is named.",
    sources: [KNOWN, "docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md", ARCH_COUNCIL, ARCH_GATE],
    design: [
      "Verification hashes the stored proof.json bytes and does not reserialize before the byte check.",
      "The council seat for evidence and independent verification accepted that design as architecture.",
      `${ARCH_GATE} leaves PROVED_EXTERNAL unset.`,
    ],
    stage2: [
      "Local prove output is a render. It is not an independent verifier.",
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  health: {
    current:
      "vantio status reports local run logs and whether seven Node provider packages resolve. UNSUPPORTED there means the package did not resolve. It does not mean the host catalog excluded the provider.",
    sources: [PATHS, A5, "docs/planning/shared-health-vocabulary/00-BOUNDARY.md"],
    design: [
      "A5 separates product health from provider outcome. A provider 500 is not an Optics failure.",
      "Freshness CURRENT stays unemitted while its window is NOT_SET. The honest value is UNKNOWN.",
      "Diagnostic counters are named. Measurement methods for write_latency_ms and query_latency_ms are NOT_SET.",
    ],
    stage2: [
      "Today's writers do not emit the A5 lifecycle or health record.",
      "docs/planning/shared-health-vocabulary/00-BOUNDARY.md is a catalog whose council is PENDING_INDEPENDENT_COUNCIL. The catalog is not a runtime health proof.",
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  coverage_truth: {
    current:
      "A supported path is one a wrapped process records. No row means not observed. Unsupported paths are not described as protected.",
    sources: [PATHS, KNOWN, A5],
    design: [
      "Completeness is not a percentage. Sampled evidence must not be displayed as complete. This pack does not introduce sampling.",
      "Issue location COVERAGE is for an evidenced gap. An unobserved child is NOT_OBSERVED.",
      "Roadmap item vantio status --coverage remains future work in docs/internal/optics-best-in-class-roadmap.md and is not a current command.",
    ],
    stage2: [
      "The supported-path manual is the current honesty page. It is not an implementation of the architecture coverage record.",
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  performance: {
    current: "No performance measurement record exists in this pack. Architecture budget targets are NOT_SET.",
    sources: [A5, "docs/internal/optics-best-in-class-roadmap.md"],
    design: [
      "A5 lists startup, interceptor init, per-call overhead, memory, write latency, queue, database size, query latency, export, and shutdown flush.",
      "Every current target is NOT_SET. The roadmap example under 5 milliseconds p99 is not adopted.",
      "An indicator is not an SLO. An SLO exists only after a customer sets a target and a window.",
    ],
    stage2: [
      "measurement_blocks_from_order is 2. Every required metric in PERFORMANCE-SCAFFOLD.json is NOT_MEASURED.",
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
  operational_overhead: {
    current: "Per-call overhead has no measurement record. NFR-PER-CALL-OVERHEAD is NOT_SET.",
    sources: [A5, "docs/internal/optics-best-in-class-roadmap.md"],
    design: [
      "The design question is time and resources added by observation, measured without reading body content.",
      "Failure behavior: an observation failure leaves application output unchanged.",
      "The numeric target is NOT_SET.",
    ],
    stage2: [
      "measurement_blocks_from_order is 2. cpu, memory, disk, evidence_growth, and startup are NOT_MEASURED.",
      INTERNAL_CANDIDATE_ABSENT,
    ],
  },
};

export const OPTICS_UNMET = {
  ingress: {
    statement_class: "NOT_DOCUMENTED",
    current: "The product boundary describes egress observation. This source set does not specify an Optics ingress capability.",
    sources: [BOUNDARY, "docs/observe-only.md"],
    why: [
      "No open-core document in the source set names Optics ingress behavior, ingress non-goals, and the evidence required to leave a design target.",
      "A missing capability stays at current_stage NONE.",
    ],
  },
  host: {
    statement_class: "DOCUMENTED_NON_CLAIM",
    current: "Host enforcement on enrolled Linux is outside free Optics. The supported-path page does not describe Phantom Engine coverage.",
    sources: [BOUNDARY, PATHS, KNOWN, LINEUP],
    why: [
      "The canonical boundary assigns host enforcement to Phantom Engine on enrolled Linux hosts.",
      "A documented non-claim is not a satisfied design-target stage and is not EVIDENCE_BACKED_BEST_IN_CLASS.",
    ],
  },
  workload_identity_integrity: {
    statement_class: "NOT_DOCUMENTED",
    current: "Wrapped runs record a process id. Writers do not set machine. Process id is not a workload identity.",
    sources: [KNOWN, PATHS, E2],
    why: [
      "No Optics design target in the accepted architecture pack defines workload identity or workload integrity.",
      `${E2} is an Enterprise planning packet. Its council is pending, and it says Identity, Delegation, and Duration objects for agent-to-agent grants are absent.`,
    ],
  },
  sequential: {
    statement_class: "DOCUMENTED_NON_CLAIM",
    current: "Free Optics does not apply a per-call size cap or a per-decision spend cap. producer_sequence in A4 is an event order, not a limit.",
    sources: [KNOWN, "docs/observe-only.md", "docs/architecture/optics-foundation/05-CORRELATION-AND-QUERY-CONTRACT.md"],
    why: [
      "The current boundary places spend and size caps on Phantom Engine.",
      "docs/specs/WRAP_UNDICI_WS_FRAMES_2026-08-15.md is a historical spec about Gate caps on an older CLI wrap. The current product boundary does not adopt it, so it satisfies no stage.",
    ],
    not_accepted: [
      {
        id: "historical-wrap-spec",
        source: "docs/specs/WRAP_UNDICI_WS_FRAMES_2026-08-15.md",
        effect: "DOES_NOT_SATISFY_ANY_STAGE",
      },
    ],
  },
  canary: {
    statement_class: "NOT_DOCUMENTED",
    current: "No staged policy or release canary is specified for Optics.",
    sources: ["docs/internal/optics-best-in-class-roadmap.md"],
    why: [
      "This dimension is a subset rollout of a policy or release.",
      "Privacy-canary fixtures, which assert that a marker string is absent from stored bytes, are excluded_practices. They do not satisfy canary.",
    ],
  },
  revocation: {
    statement_class: "NOT_DOCUMENTED",
    current: "Optics has no grant object to revoke. Free Optics requires no account.",
    sources: [BOUNDARY, E2],
    why: [
      `${E2} requirement EG-E2-8 is UNSATISFIED: expiry and revocation leaving no expanded authority is not shown by current sources.`,
      "That unsatisfied Enterprise plan does not satisfy an Optics stage, and it does not satisfy an Enterprise stage in this pack.",
    ],
  },
  deployment: {
    statement_class: "DOCUMENTED_CURRENT_BEHAVIOR",
    current: "The public manual names npm install of @vantio/cli and pip install of vantio-agent-sdk. This force did not deploy a host.",
    sources: [BOUNDARY, "docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md"],
    why: [
      "Install commands are an operator procedure.",
      "They do not state the evidence that would make a deployment a PRODUCTION_GRADE_INTERNAL_CANDIDATE, and this force recorded no deployment run.",
    ],
  },
  removal: {
    statement_class: "DOCUMENTED_CURRENT_BEHAVIOR",
    current:
      "npm uninstall and pip uninstall remove the packages and leave ~/.vantio in place, including run logs. The manual states that uninstall does not unenroll a Phantom Engine host.",
    sources: ["docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md"],
    why: [
      "The uninstall procedure is documented and was not timed.",
      "The uninstall metric is NOT_MEASURED. A procedure page does not meet the design-target checklist for this ladder.",
    ],
  },
};

export const PHANTOM_NOTE = {
  ingress: {
    statement_class: "NOT_DOCUMENTED",
    current: "Open-core sources name host and egress controls on enrolled Linux. They do not name a separate ingress capability.",
    sources: [LINEUP, P24],
    why: [
      "No ingress design target is present in the open-core source set.",
      "Private product-spec bodies are not copied into this pack.",
    ],
  },
  egress: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup marks observe, hostname block, redaction, and spend caps for Phantom Engine. This pack did not re-execute a host.",
    sources: [LINEUP, COVERAGE, "docs/programs/production-readiness/diligence/09-CAPABILITIES.md"],
    why: [
      "A lineup checkmark satisfies no stage.",
      `${COVERAGE} rows uprobe-e2e-wsl2 and scoped-tc-drop-wsl2 are OBSERVED_FROM_REPOSITORY_EVIDENCE with this_force NOT_EXECUTED. Repository sentences are not re-executed here and satisfy no stage.`,
      "docs/programs/production-readiness/diligence/09-CAPABILITIES.md sets the evidence tier of every lineup cell to UNSET and records Phantom Engine implementation as NOT_VERIFIED_IN_THIS_REPO.",
    ],
    not_accepted: [
      { id: "uprobe-e2e-wsl2", source: COVERAGE, effect: "DOES_NOT_SATISFY_ANY_STAGE" },
      { id: "scoped-tc-drop-wsl2", source: COVERAGE, effect: "DOES_NOT_SATISFY_ANY_STAGE" },
    ],
  },
  host: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup marks host enforcement on enrolled Linux. P24 is a plan. No loader was started in that plan or in this force.",
    sources: [LINEUP, P24, COVERAGE, EG],
    why: [
      `${P24} status is PLAN_ONLY. Its council file is PENDING_INDEPENDENT_COUNCIL. A pending plan is not accepted as BEST_IN_CLASS_DESIGN_TARGET.`,
      `${EG} records the product-spec verification label as a privileged Linux host and a local kind cluster, and records managed-cloud Kubernetes and a live Spanner write as TARGET_DESIGN. This force did not re-read the private spec and does not treat kind as a production-cluster proof.`,
      "Privileged disable of the loader remains a named residual in that planning boundary. This pack keeps that residual.",
    ],
    not_accepted: [
      { id: "kernel-verifier-wsl2", source: COVERAGE, effect: "DOES_NOT_SATISFY_ANY_STAGE" },
      { id: "host-crates-compile", source: COVERAGE, effect: "DOES_NOT_SATISFY_ANY_STAGE" },
    ],
  },
  descendant_lineage: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup marks fork inheritance on enrolled hosts. The coverage row says the WSL2 evidence was not an isolated fork-only test and was not re-executed.",
    sources: [LINEUP, COVERAGE, E2],
    why: [
      `${COVERAGE} id fork-inheritance-wsl2 is OBSERVED_FROM_REPOSITORY_EVIDENCE, platform_scope WSL2_PRIVILEGED, this_force NOT_EXECUTED.`,
      `${E2} says a trace id inherited across sched_process_fork is correlation, not a delegation record, and enrolled cgroup children are not a wider grant.`,
    ],
    not_accepted: [
      { id: "fork-inheritance-wsl2", source: COVERAGE, effect: "DOES_NOT_SATISFY_ANY_STAGE" },
    ],
  },
  workload_identity_integrity: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "The Enterprise planning boundary says Phantom Engine consumes identity and does not become the identity provider. The objects are not claimed to exist.",
    sources: [EG, E2],
    why: [
      `${EG} council status for that packet is PENDING_INDEPENDENT_COUNCIL.`,
      "A pending plan does not satisfy BEST_IN_CLASS_DESIGN_TARGET in this ladder.",
    ],
  },
  sequential: {
    statement_class: "NOT_DOCUMENTED",
    current: "The lineup has a spend and size cap cell. It does not split a per-decision limit from an aggregate limit.",
    sources: [LINEUP],
    why: [
      "The spend and size lineup cell is scored only on aggregate_limits. It is not reused here.",
      "No open-core design target defines a Phantom Engine sequential limit with advance evidence.",
    ],
  },
  aggregate_limits: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup marks spend and size caps on the wrapped path for Phantom Engine. No cap value was measured.",
    sources: [LINEUP, "docs/programs/production-readiness/diligence/09-CAPABILITIES.md"],
    why: [
      "The diligence skeleton leaves the lineup cell at evidence tier UNSET.",
      "No numeric cap, window, or measurement is recorded in this pack.",
    ],
  },
  simulation: {
    statement_class: "NOT_DOCUMENTED",
    current: "No Phantom Engine simulation-label design is stated in the open-core source set used here.",
    sources: [P24],
    why: ["P24 does not define simulation origins. The Optics simulation design is not a Phantom Engine stage."],
  },
  canary: {
    statement_class: "NOT_DOCUMENTED",
    current: "No staged Phantom Engine rollout canary is specified in the open-core source set.",
    sources: [P24],
    why: ["P24 names health and coverage planning. It does not specify a canary cohort."],
  },
  rollback: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "Enterprise planning cites a customer-pack sequence of export, hash, rollback, and uninstall as doctrine text, not as a run this force executed.",
    sources: [EG, "docs/planning/enterprise-governance/01-E1-OWNERSHIP.md"],
    why: [
      "docs/planning/enterprise-governance/01-E1-OWNERSHIP.md says those scripts are present in the doctrine and are not a stranger-host pass and not E1 implemented.",
      "The packet council is pending. The rollback metric is NOT_MEASURED.",
    ],
  },
  revocation: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "EG-E2-7 is PLANNED. EG-E2-8 is UNSATISFIED.",
    sources: [E2],
    why: [
      "Current sources do not show that expiry and revocation leave no expanded authority.",
      "An unsatisfied requirement is not a satisfied design-target stage.",
    ],
  },
  evidence: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup marks durable ledger and dual-control as partial for Phantom Engine. Local NDJSON is described as append-oriented in the P24 summary of an enterprise inventory. Spanner insert remains TARGET.",
    sources: [LINEUP, P24, EG],
    why: [
      "Partial in a lineup cell is still a lineup statement.",
      `${P24} says a live commit timestamp is UNVERIFIED and that the local file must not be called WORM.`,
    ],
  },
  independent_verification: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "P24 says an internal test is not stranger-host proof. compatibility_status on the company-host name set is internally_proven in the cited module, and not_stranger_proven otherwise.",
    sources: [P24, "docs/planning/stranger-host-gate/00-PACKET-BOUNDARY.md"],
    why: [
      "docs/planning/stranger-host-gate/00-PACKET-BOUNDARY.md keeps execution NOT_AUTHORIZED.",
      "Company-host text in a private module, as summarized by P24, is not an independent verifier and was not re-executed.",
    ],
  },
  health: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "P24 separates node liveness, protection state, and optional control-plane heartbeat. No probe was curled.",
    sources: [P24, "docs/planning/phantom-engine-production/06-INDEPENDENT-COUNCIL.md"],
    why: [
      "docs/planning/phantom-engine-production/06-INDEPENDENT-COUNCIL.md is PENDING_INDEPENDENT_COUNCIL.",
      "A green liveness file does not mean workloads are enrolled. This framework does not collapse those channels.",
    ],
  },
  coverage_truth: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "P24 requires a not_covered list: unenrolled workloads, Windows and macOS, a privileged operator who can stop the loader, shapes that were not stranger-proved, and calls already sent.",
    sources: [P24, COVERAGE],
    why: [
      "The plan says spoken output that contains a banned claim forces coverage_unknown. Banned tokens include universal coverage and a stranger-host pass.",
      "Every coverage row this force could cite is this_force NOT_EXECUTED. The plan's own council is pending, so the row is not a satisfied design-target stage.",
    ],
  },
  deployment: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "Phantom packaging and prerequisites are a planning packet. This force did not build an image, load a program, or enroll a host.",
    sources: ["docs/planning/phantom-engine-production/00-PLANNING-BOUNDARY.md", "docs/planning/phantom-engine-production/02-P1-PACKAGE-ARTIFACT-PROVENANCE.md"],
    why: [
      "docs/planning/phantom-engine-production/00-PLANNING-BOUNDARY.md keeps live eBPF load, kind, Helm install, and customer deploy closed.",
      "That packet's council is PENDING_INDEPENDENT_COUNCIL.",
    ],
  },
  removal: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "The Optics uninstall page states that it does not unenroll a Phantom Engine host. Doctrine uninstall is cited as not implemented E1.",
    sources: ["docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md", "docs/planning/enterprise-governance/01-E1-OWNERSHIP.md"],
    why: [
      "No removal run was executed. The uninstall metric is NOT_MEASURED.",
      "A citation of doctrine scripts is not a satisfied design-target stage while that plan's council is pending.",
    ],
  },
  performance: {
    statement_class: "NOT_DOCUMENTED",
    current: "No Phantom Engine performance measurement was taken. This pack does not estimate one.",
    sources: [P24, COVERAGE],
    why: [
      "Coverage-matrix rows are repository evidence of functional checks, not CPU, latency, or throughput measurements.",
      "Every performance metric in this scaffold is NOT_MEASURED.",
    ],
  },
  operational_overhead: {
    statement_class: "NOT_DOCUMENTED",
    current: "No host overhead measurement for Phantom Engine is recorded in the open-core source set.",
    sources: [P24],
    why: ["cpu, memory, disk, evidence_growth, and startup are NOT_MEASURED. No estimate is filled in."],
  },
};

export const ENTERPRISE_NOTE = {
  ingress: {
    statement_class: "NOT_DOCUMENTED",
    current: "Enterprise is governance on Phantom Engine protection. No separate ingress capability is documented here.",
    sources: [LINEUP, EG],
    why: ["The lineup does not add an ingress row. No design target for Enterprise ingress is in this source set."],
  },
  egress: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup repeats Phantom Engine egress marks on the Enterprise column. Enterprise does not add a second egress mechanism in that matrix.",
    sources: [LINEUP, EG],
    why: [
      `${EG} says a capability matrix cell is a lineup statement and is not an implementation record.`,
      "Enterprise status in the cited product-spec cross-product table is Internal dogfood. This pack does not reclassify Enterprise as shipped.",
    ],
  },
  host: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup marks host enforcement for Enterprise. The planning boundary keeps the same host scope and states certifications are not held.",
    sources: [LINEUP, EG],
    why: ["Certifications held: none, in the cited doctrine summary. A lineup check does not satisfy a stage."],
  },
  descendant_lineage: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "Child and cross-agent delegation is Partial or Roadmap in the cited doctrine. E2 defines a grant and does not claim the runtime object exists.",
    sources: [EG, E2],
    why: ["No first-class child-agent delegation object is claimed. The plan council is pending."],
  },
  workload_identity_integrity: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "E2: a workload identity is never the independent approver of a grant that affects that workload. Vantio consumes identity and does not become the identity provider.",
    sources: [EG, E2, "docs/planning/enterprise-governance/03-E3-APPROVAL-CLASSES.md"],
    why: [
      "Requirements EG-E2-1 through EG-E2-7 are PLANNED. EG-E2-8 is UNSATISFIED.",
      "Pending plan text is not BEST_IN_CLASS_DESIGN_TARGET on this ladder.",
    ],
  },
  sequential: {
    statement_class: "NOT_DOCUMENTED",
    current: "No Enterprise sequential-limit design is in the E1–E3 packet.",
    sources: [EG],
    why: ["The packet covers ownership, delegation, and approval classes. It does not define a per-decision limit."],
  },
  aggregate_limits: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup marks spend and size caps for Enterprise because it includes Phantom Engine. No Enterprise cap measurement exists here.",
    sources: [LINEUP, EG],
    why: ["Lineup inclusion is not a measured aggregate limit. evidence_growth is NOT_MEASURED."],
  },
  simulation: {
    statement_class: "NOT_DOCUMENTED",
    current: "The simulation-label rule in the investor demo is an Optics demo rule. It is not an Enterprise product capability.",
    sources: ["docs/programs/production-readiness/demo/01-SIMULATION-LABEL-RULE.md"],
    why: ["The demo document says CLI 0.3.24 does not enforce the rule. That rule does not satisfy an Enterprise stage."],
  },
  canary: {
    statement_class: "NOT_DOCUMENTED",
    current: "No Enterprise canary cohort is specified.",
    sources: [EG],
    why: ["E3 approval classes are not a staged canary."],
  },
  rollback: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "E1 keeps export, hash, rollback, and uninstall as a customer-owned sequence. The requirement status is PLANNED.",
    sources: ["docs/planning/enterprise-governance/01-E1-OWNERSHIP.md", "docs/planning/enterprise-governance/04-SUBORDINATION-AND-CUSTOMER-SUFFICIENCY.md"],
    why: [
      "EG-E1-4 is PLANNED. The doctrine row is not a stranger-host pass.",
      "The rollback metric is NOT_MEASURED.",
    ],
  },
  revocation: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "EG-E2-7 says revocation returns exercise and leaves title with the customer root. Status PLANNED. EG-E2-8 is UNSATISFIED.",
    sources: [E2],
    why: ["The property this dimension asks for is the one the plan marks UNSATISFIED. That is current_stage NONE."],
  },
  evidence: {
    statement_class: "LINEUP_ONLY",
    current: "The lineup marks durable ledger and dual-control for Enterprise. E3 does not treat unwired dual-control hooks as shipped approval classes.",
    sources: [LINEUP, EG, "docs/planning/enterprise-governance/03-E3-APPROVAL-CLASSES.md"],
    why: [
      `${EG} records dual-control as described in the doctrine file, with the live executor for one kind unwired, and two-of-two described as proved only for a non-destructive test kind.`,
      "This pack does not promote that sentence to a satisfied stage.",
    ],
  },
  independent_verification: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "No external verifier is named. The E1–E3 council file is pending.",
    sources: ["docs/planning/enterprise-governance/06-INDEPENDENT-COUNCIL.md", ARCH_GATE],
    why: ["A future council on the governance plan would still be a document result. independent_verifier is NOT_PRESENT."],
  },
  health: {
    statement_class: "NOT_DOCUMENTED",
    current: "Enterprise does not define a third health channel in the E1–E3 packet. P24's channels stay Phantom Engine planning.",
    sources: [EG, P24],
    why: ["Copying the Phantom health plan onto the Enterprise row would skip the product boundary. The Enterprise cell stays NOT_DOCUMENTED."],
  },
  coverage_truth: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "The planning boundary says certifications are not held and the reference-monitor doctrine is SCOPED.",
    sources: [EG, LINEUP],
    why: ["Honest gaps in the lineup are lineup text. They do not satisfy BEST_IN_CLASS_DESIGN_TARGET while the governance council is pending."],
  },
  deployment: {
    statement_class: "NOT_DOCUMENTED",
    current: "No Enterprise deployment procedure was run. Customer deploy is closed for this force.",
    sources: [EG],
    why: ["Internal dogfood, as cited from the product-spec table, is not a deployment record in this pack."],
  },
  removal: {
    statement_class: "PLAN_PENDING_COUNCIL",
    current: "EG-SP-5 says leave is export, hash, rollback, and uninstall with Vantio absent. Status is planning.",
    sources: ["docs/planning/enterprise-governance/04-SUBORDINATION-AND-CUSTOMER-SUFFICIENCY.md"],
    why: ["The leave property is planned. uninstall is NOT_MEASURED. No removal run exists."],
  },
  performance: {
    statement_class: "NOT_DOCUMENTED",
    current: "No Enterprise performance measurement exists in this pack.",
    sources: [EG],
    why: ["Every performance metric is NOT_MEASURED."],
  },
  operational_overhead: {
    statement_class: "NOT_DOCUMENTED",
    current: "No Enterprise overhead measurement exists in this pack.",
    sources: [EG],
    why: ["cpu, memory, disk, evidence_growth, and startup are NOT_MEASURED."],
  },
};
