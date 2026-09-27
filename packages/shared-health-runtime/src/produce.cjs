"use strict";

const contract = require("../contract.json");
const { evaluateFact, isPlainObject, loadCatalog } = require("./catalog.cjs");

const HEALTHY = new Set(contract.healthy_tokens);
const STATES = new Set(contract.states);
const CLASSIFICATIONS = new Set(contract.failure_classifications);
const COMPONENTS = new Set(contract.components);
const LIFECYCLES = new Set(contract.lifecycles);
const OPTIMISTIC_SOURCES = new Set(contract.optimistic_evidence_sources);
const TOKEN_CLASSIFICATION = contract.token_failure_classification;
const NONBLOCKING = new Set(contract.nonblocking_errors);

function healthyBlocked(errors) {
  return errors.some((code) => !NONBLOCKING.has(code));
}
const LIFECYCLE_STATE = Object.freeze({
  intentionally_disabled: "INTENTIONALLY_DISABLED",
  unsupported: "UNSUPPORTED",
  partial_coverage: "PARTIAL_COVERAGE",
  disconnected: "DISCONNECTED",
  evidence_unavailable: "EVIDENCE_UNAVAILABLE",
  rollback_incomplete: "ROLLBACK_INCOMPLETE",
  uninstall_incomplete: "UNINSTALL_INCOMPLETE",
});
const GREEN_SENTENCE = "This record is not a green light from process health or HTTP status.";
const TOKEN_MEANING_SENTENCE = "Failure classification records the token meaning, not a latch measured by this runtime.";

function isIsoTimestamp(value) {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)
    && !Number.isNaN(Date.parse(value));
}

function isOptimisticSource(value) {
  return typeof value === "string" && OPTIMISTIC_SOURCES.has(value.trim().toLowerCase());
}

function takeClock(options, errors) {
  const now = options.now;
  const value = typeof now === "function" ? now() : now;
  if (value === undefined) return new Date().toISOString();
  if (isIsoTimestamp(value)) return value;
  errors.push("CLOCK_INVALID");
  return null;
}

function hasForbiddenKey(value) {
  if (!isPlainObject(value)) return [];
  const errors = [];
  if (Object.prototype.hasOwnProperty.call(value, "coverage_percent")) errors.push("COVERAGE_PERCENT_FORBIDDEN");
  if (Object.prototype.hasOwnProperty.call(value, "customer_validation")) errors.push("CUSTOMER_VALIDATION_FORBIDDEN");
  if (Object.prototype.hasOwnProperty.call(value, "worm") || value.worm === "WORM") errors.push("WORM_FORBIDDEN");
  if (value.proved === true || value.platform_status === "proved") errors.push("PROVED_TOKEN_FORBIDDEN");
  return errors;
}

function pushUnique(list, code) {
  if (code && !list.includes(code)) list.push(code);
}

function blankDecision() {
  return {
    state: "EVIDENCE_UNAVAILABLE",
    component: contract.unspecified_component,
    scope: null,
    scopeDefaulted: false,
    evidence_source: "ABSENT",
    evidence_basis: "ABSENT",
    evidence_class: "NOT_INDEPENDENTLY_VERIFIED",
    catalog_protection_state: null,
    platform_status: null,
    named_gaps: [],
    failure_classification: "unsupported",
    failure_classification_basis: "NOT_EVIDENCED",
    derived_from_process_up: false,
    derived_from_http_success: false,
    http_status_ignored: false,
    process_up_ignored: false,
    limitationParts: [],
    callerClaimedExecution: false,
  };
}

function normalize(input, errors) {
  const source = isPlainObject(input) ? input : {};
  if (!isPlainObject(input)) pushUnique(errors, "INPUT_SHAPE");
  for (const code of hasForbiddenKey(source)) pushUnique(errors, code);
  if (source.green === true) pushUnique(errors, "OPTIMISTIC_GREEN_REFUSED");
  if (source.freshness !== undefined && source.freshness !== "UNKNOWN") {
    pushUnique(errors, "FRESHNESS_WINDOW_NOT_SET");
    if (source.freshness === "STALE" || source.freshness === "CURRENT" || source.freshness === "HISTORICAL") {
      pushUnique(errors, "FRESHNESS_STALE_IS_NOT_A_STATE");
    }
  }
  if (source.independent_verification_status !== undefined
    && source.independent_verification_status !== "NOT_INDEPENDENTLY_VERIFIED") {
    pushUnique(errors, "INDEPENDENT_VERIFICATION_NOT_MINTED");
  }
  if (source.recovery_verification !== undefined && source.recovery_verification !== "NOT_VERIFIED") {
    pushUnique(errors, "RECOVERY_VERIFICATION");
  }

  const signals = isPlainObject(source.signals) ? source.signals : {};
  if (source.signals !== undefined && !isPlainObject(source.signals)) pushUnique(errors, "SIGNALS_SHAPE");
  const facts = [];
  if (source.facts !== undefined && !Array.isArray(source.facts)) pushUnique(errors, "FACTS_SHAPE");
  else if (Array.isArray(source.facts)) {
    for (const fact of source.facts) facts.push(fact);
  }

  let lifecycle = null;
  if (source.lifecycle !== undefined && source.lifecycle !== null) {
    if (LIFECYCLES.has(source.lifecycle)) lifecycle = source.lifecycle;
    else pushUnique(errors, "LIFECYCLE_ENUM");
  }
  let requestedState = null;
  if (source.requested_state !== undefined && source.requested_state !== null) {
    if (STATES.has(source.requested_state)) requestedState = source.requested_state;
    else pushUnique(errors, "REQUESTED_STATE_ENUM");
  }
  let failureClassification = null;
  if (source.failure_classification !== undefined && source.failure_classification !== null) {
    if (CLASSIFICATIONS.has(source.failure_classification)) failureClassification = source.failure_classification;
    else pushUnique(errors, "FAILURE_CLASSIFICATION_ENUM");
  }

  const namedGaps = [];
  if (source.named_gaps !== undefined) {
    if (!Array.isArray(source.named_gaps)) pushUnique(errors, "NAMED_GAP_REQUIRED");
    else {
      for (const gap of source.named_gaps) {
        if (typeof gap !== "string" || !/^[a-z0-9_:-]{1,80}$/.test(gap) || /^\d+(\.\d+)?%?$/.test(gap)) {
          pushUnique(errors, "NAMED_GAP_REQUIRED");
        } else if (!namedGaps.includes(gap)) namedGaps.push(gap);
      }
    }
  }

  const component = COMPONENTS.has(source.component) ? source.component : null;
  if (source.component !== undefined && component === null) pushUnique(errors, "COMPONENT_ENUM");
  const timestamp = isIsoTimestamp(source.timestamp) ? source.timestamp : null;
  if (source.timestamp !== undefined && timestamp === null) pushUnique(errors, "TIMESTAMP_INVALID");
  const producer = typeof source.producer === "string" && /^[A-Za-z0-9._:@/-]{1,120}$/.test(source.producer)
    ? source.producer
    : null;
  const sourceVersion = typeof source.source_version === "string" && source.source_version.trim() !== ""
    && !/[\r\n]/.test(source.source_version)
    ? source.source_version.trim()
    : null;

  return {
    component,
    componentSupplied: component !== null,
    scopeSupplied: typeof source.scope === "string" ? source.scope : null,
    timestamp,
    producer,
    sourceVersion,
    lifecycle,
    requestedState,
    failureClassification,
    failureModeEvidenced: source.failure_mode_evidenced === true,
    namedGaps,
    facts,
    signals,
    lastKnownGood: source.last_known_good,
    greenClaim: source.green === true,
  };
}

function httpSuccess(signals, facts) {
  const status = signals.http_status;
  if (typeof status === "number" && status >= 200 && status <= 399) return true;
  return facts.some((fact) => isPlainObject(fact)
    && fact.fact_kind === "APPLICATION_STATUS"
    && fact.application_status === "SUCCESS");
}

function processSignal(signals, facts) {
  if (signals.process_up === true) return true;
  if (typeof signals.heartbeat_age_s === "number") return true;
  return facts.some((fact) => isPlainObject(fact) && fact.fact_kind === "LOADER_LIVENESS");
}

function mapProtection(protectionState, errors) {
  switch (protectionState) {
    case "protected":
      return "HEALTHY_ENFORCING";
    case "observing":
      return "HEALTHY_OBSERVING";
    case "not_enrolled":
      pushUnique(errors, "NOT_ENROLLED_IS_NOT_DISABLED");
      return "ENFORCEMENT_UNKNOWN";
    case "protection_stale":
    case "policy_stale":
      return "STALE";
    case "degraded":
      return "DEGRADED";
    case "quarantined":
      pushUnique(errors, "QUARANTINE_IS_NOT_A_SEPARATE_RUNTIME_STATE");
      return "DEGRADED";
    case "recovery_required":
      pushUnique(errors, "RECOVERY_REQUIRED_IS_NOT_ROLLBACK");
      return "ENFORCEMENT_UNKNOWN";
    case "coverage_unknown":
      pushUnique(errors, "COVERAGE_UNKNOWN_IS_NOT_HEALTHY");
      return "ENFORCEMENT_UNKNOWN";
    default:
      pushUnique(errors, "UNHANDLED_STATE");
      return "ENFORCEMENT_UNKNOWN";
  }
}

function applyClassification(decision, input, errors) {
  const fixed = TOKEN_CLASSIFICATION[decision.state];
  if (fixed) {
    if (input.failureClassification && input.failureClassification !== fixed) {
      pushUnique(errors, "FAILURE_CLASSIFICATION_CONTRADICTION");
      if (HEALTHY.has(decision.state)) {
        decision.state = "ENFORCEMENT_UNKNOWN";
        decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
        decision.evidence_source = "PROTECTION_EVALUATION";
        decision.failure_classification = "unsupported";
        decision.failure_classification_basis = "NOT_EVIDENCED";
        decision.limitationParts.push("The caller failure classification contradicted the healthy token.");
        return;
      }
    }
    decision.failure_classification = fixed;
    decision.failure_classification_basis = "TOKEN_MEANING";
    decision.limitationParts.push(TOKEN_MEANING_SENTENCE);
    return;
  }
  if (input.failureModeEvidenced && input.failureClassification) {
    decision.failure_classification = input.failureClassification;
    decision.failure_classification_basis = "CALLER_EVIDENCED";
    decision.limitationParts.push("Failure classification was supplied by the caller and was not measured by this runtime.");
    return;
  }
  if (input.failureClassification && !input.failureModeEvidenced) {
    pushUnique(errors, "FAILURE_MODE_NOT_EVIDENCED");
  }
  decision.failure_classification = "unsupported";
  decision.failure_classification_basis = "NOT_EVIDENCED";
}

function noteNonProtection(facts, decision, errors) {
  for (const fact of facts) {
    if (fact.fact_kind === "OPTICS_DISPLAY_READING") {
      pushUnique(errors, "OPTICS_DISPLAY_IS_NOT_PROTECTION");
      decision.limitationParts.push("An Optics display token is not a protection state.");
    }
    if (fact.fact_kind === "APPLICATION_STATUS" && fact.application_status === "SUCCESS") {
      pushUnique(errors, "APPLICATION_SUCCESS_IS_NOT_ENFORCEMENT");
      decision.limitationParts.push("Application SUCCESS, including HTTP 200, is not enforcement health.");
    }
    if (fact.fact_kind === "VERIFIER_RUN" && fact.verifier_result === "PASS") {
      pushUnique(errors, "VERIFIER_PASS_IS_NOT_ENFORCEMENT");
    }
    if (fact.fact_kind === "VERIFIER_RUN" && fact.verifier_result === "OPTIONAL_COMPONENT_ABSENT") {
      pushUnique(errors, "OPTIONAL_COMPONENT_ABSENT_IS_NOT_PASS");
    }
    if (fact.fact_kind === "VERIFIER_RUN" && fact.verifier_result === "BLOCKED") {
      pushUnique(errors, "VERIFIER_BLOCKED_IS_NOT_LEDGER_BLOCKED");
    }
    if (fact.fact_kind === "LEDGER_ACTION" && fact.ledger_action_taken === "OBSERVED") {
      pushUnique(errors, "LEDGER_OBSERVED_IS_NOT_PROTECTED");
    }
    if (fact.fact_kind === "LEDGER_ACTION" && fact.ledger_action_taken === "BLOCKED") {
      pushUnique(errors, "VERIFIER_BLOCKED_IS_NOT_LEDGER_BLOCKED");
    }
    if (fact.fact_kind === "LOADER_LIVENESS") {
      pushUnique(errors, "HEARTBEAT_IS_NOT_FRESHNESS");
      decision.limitationParts.push("Loader liveness is not freshness CURRENT and is not enforcement health.");
    }
    if (fact.fact_kind === "CONTROL_PLANE_HEARTBEAT") {
      decision.limitationParts.push("A control-plane heartbeat fact does not set connected or disconnected.");
    }
  }
}

function sameProtection(facts) {
  const first = facts[0];
  return facts.every((fact) => fact.protection_state === first.protection_state
    && fact.evidence_class === first.evidence_class
    && fact.platform_status === first.platform_status
    && fact.platform_scope === first.platform_scope
    && fact.subject === first.subject);
}

function componentForFacts(facts, input) {
  if (input.componentSupplied) return input.component;
  const protection = facts.filter((fact) => fact.fact_kind === "PROTECTION_EVALUATION");
  const protectionSubjects = [...new Set(protection.map((fact) => fact.subject))];
  if (protectionSubjects.length === 1 && COMPONENTS.has(protectionSubjects[0])) return protectionSubjects[0];
  if (facts.length === 1 && facts[0].fact_kind === "OPTICS_DISPLAY_READING") return "OPTICS";
  if (facts.length === 1 && facts[0].fact_kind === "SDK_ACTION") return "SDK";
  const subjects = [...new Set(facts.map((fact) => fact.subject))];
  if (subjects.length === 1 && COMPONENTS.has(subjects[0])) return subjects[0];
  return null;
}

function healthyGates(decision, fact, input, catalog, errors) {
  const scopes = catalog.fields.platform_scope.values;
  if (!input.componentSupplied) {
    decision.component = fact.subject;
  }
  if (decision.component !== fact.subject) {
    pushUnique(errors, "COMPONENT_SUBJECT_MISMATCH");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (fact.platform_scope && input.scopeSupplied && fact.platform_scope !== input.scopeSupplied) {
    pushUnique(errors, "SCOPE_MISMATCH");
    if (fact.platform_scope === "KIND_LOCAL" && input.scopeSupplied === "MANAGED_CLOUD") {
      pushUnique(errors, "KIND_LOCAL_IS_NOT_MANAGED_CLOUD");
    }
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (!scopes.includes(decision.scope) || decision.scopeDefaulted) {
    pushUnique(errors, "SCOPE_REQUIRED");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (contract.blocked_healthy_scopes.includes(decision.scope)) {
    pushUnique(errors, decision.scope === "STRANGER_HOST" ? "STRANGER_HOST_SCOPE_IS_NOT_PROOF" : "SCOPE_BLOCKS_HEALTHY_TOKEN");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (!contract.healthy_evidence_classes.includes(fact.evidence_class)) {
    pushUnique(errors, "EVIDENCE_CLASS_BLOCKS_HEALTHY_TOKEN");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (!contract.healthy_platform_statuses.includes(fact.platform_status)) {
    pushUnique(errors, "PLATFORM_STATUS_BLOCKS_HEALTHY_TOKEN");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (fact.compatibility_status === "internally_proven" && decision.scope === "STRANGER_HOST") {
    pushUnique(errors, "STRANGER_HOST_SCOPE_IS_NOT_PROOF");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (!input.timestamp) {
    pushUnique(errors, "TIMESTAMP_REQUIRED");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (!input.producer) {
    pushUnique(errors, "EVIDENCE_PRODUCER_UNSPECIFIED");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (!input.sourceVersion) {
    pushUnique(errors, "SOURCE_VERSION_REQUIRED");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
  }
  if (HEALTHY.has(decision.state)) {
    decision.evidence_source = "PROTECTION_EVALUATION";
    decision.evidence_basis = "PROTECTION_EVALUATION";
    decision.evidence_class = fact.evidence_class;
    decision.platform_status = fact.platform_status;
    decision.catalog_protection_state = fact.protection_state;
    decision.callerClaimedExecution = fact.evidence_class === "EXECUTED_IN_THIS_REMEDIATION";
    decision.limitationParts.push(
      decision.callerClaimedExecution
        ? "Caller claimed EXECUTED_IN_THIS_REMEDIATION. This runtime executed nothing."
        : "Protection token is caller-supplied repository evidence. This runtime did not execute enforcement.",
    );
  }
}

function decide(input, catalog, errors) {
  const decision = blankDecision();
  const validFacts = [];
  for (const fact of input.facts) {
    for (const code of hasForbiddenKey(fact)) pushUnique(errors, code);
    const factErrors = evaluateFact(fact, catalog);
    if (factErrors.length > 0) {
      pushUnique(errors, "FACT_REJECTED");
      for (const code of factErrors) pushUnique(errors, code);
    } else validFacts.push(fact);
  }

  const sawHttp = httpSuccess(input.signals, validFacts);
  const sawProcess = processSignal(input.signals, validFacts);
  if (typeof input.signals.heartbeat_age_s === "number") pushUnique(errors, "HEARTBEAT_IS_NOT_FRESHNESS");

  const scopes = catalog.fields.platform_scope.values;
  if (input.scopeSupplied && scopes.includes(input.scopeSupplied)) decision.scope = input.scopeSupplied;
  else if (input.scopeSupplied) {
    pushUnique(errors, "SCOPE_ENUM");
    decision.scope = "REPOSITORY_ONLY";
    decision.scopeDefaulted = true;
  } else {
    decision.scope = "REPOSITORY_ONLY";
    decision.scopeDefaulted = true;
    pushUnique(errors, "SCOPE_DEFAULTED_REPOSITORY_ONLY");
  }

  const inferredComponent = componentForFacts(validFacts, input);
  decision.component = input.componentSupplied ? input.component : (inferredComponent || contract.unspecified_component);
  if (!input.componentSupplied && !inferredComponent) pushUnique(errors, "COMPONENT_REQUIRED");

  noteNonProtection(validFacts, decision, errors);

  const protection = validFacts.filter((fact) => fact.fact_kind === "PROTECTION_EVALUATION");

  if (input.lifecycle === "rollback_incomplete" || input.lifecycle === "uninstall_incomplete" || input.lifecycle === "intentionally_disabled") {
    decision.state = LIFECYCLE_STATE[input.lifecycle];
    decision.evidence_source = "EXPLICIT_LIFECYCLE";
    decision.evidence_basis = "EXPLICIT_LIFECYCLE";
    decision.evidence_class = "NOT_INDEPENDENTLY_VERIFIED";
    decision.limitationParts.push(`Explicit lifecycle ${input.lifecycle} was supplied.`);
    if (input.lifecycle === "intentionally_disabled") {
      decision.limitationParts.push("Intentional disablement is not loader not_enrolled and is not process health.");
    }
    if (protection.length > 0) {
      decision.limitationParts.push("A protection fact was present and was not emitted over the explicit lifecycle.");
    }
  } else if (input.lifecycle === "disconnected") {
    decision.state = "DISCONNECTED";
    decision.evidence_source = "EXPLICIT_LIFECYCLE";
    decision.evidence_basis = "EXPLICIT_LIFECYCLE";
    decision.limitationParts.push("Disconnected was explicit. A heartbeat file was not read.");
  } else if (protection.length > 1 && !sameProtection(protection)) {
    pushUnique(errors, "PROTECTION_FACTS_CONTRADICT");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_source = "PROTECTION_EVALUATION";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
    decision.limitationParts.push("Protection facts disagreed. The healthier token was not selected.");
  } else if (protection.length >= 1) {
    const fact = protection[0];
    decision.catalog_protection_state = fact.protection_state;
    decision.evidence_class = fact.evidence_class;
    decision.platform_status = fact.platform_status;
    decision.state = mapProtection(fact.protection_state, errors);
    decision.evidence_source = "PROTECTION_EVALUATION";
    decision.evidence_basis = "PROTECTION_EVALUATION";
    if (fact.protection_state === "quarantined") {
      decision.limitationParts.push("Quarantine stays inside DEGRADED. dual_control_executor_wired is not a runtime state.");
    }
    if (input.lifecycle === "partial_coverage") {
      if (input.namedGaps.length === 0) {
        pushUnique(errors, "NAMED_GAP_REQUIRED");
        decision.state = "EVIDENCE_UNAVAILABLE";
        decision.evidence_basis = "EXPLICIT_LIFECYCLE";
        decision.evidence_source = "EXPLICIT_LIFECYCLE";
      } else if (HEALTHY.has(decision.state)) {
        decision.state = "PARTIAL_COVERAGE";
        decision.named_gaps = input.namedGaps.slice();
        decision.evidence_basis = "EXPLICIT_LIFECYCLE";
        decision.evidence_source = "EXPLICIT_LIFECYCLE";
        decision.limitationParts.push(`Named coverage gaps: ${input.namedGaps.join(", ")}.`);
      }
    }
    if (HEALTHY.has(decision.state)) healthyGates(decision, fact, input, catalog, errors);
  } else if (input.lifecycle === "partial_coverage") {
    decision.evidence_source = "EXPLICIT_LIFECYCLE";
    decision.evidence_basis = "EXPLICIT_LIFECYCLE";
    if (input.namedGaps.length === 0) {
      pushUnique(errors, "NAMED_GAP_REQUIRED");
      decision.state = "EVIDENCE_UNAVAILABLE";
      decision.limitationParts.push("Partial coverage requires named gaps. A percentage is not a gap.");
    } else {
      decision.state = "PARTIAL_COVERAGE";
      decision.named_gaps = input.namedGaps.slice();
      decision.limitationParts.push(`Named coverage gaps: ${input.namedGaps.join(", ")}.`);
    }
  } else if (input.lifecycle === "unsupported" || input.lifecycle === "evidence_unavailable") {
    decision.state = LIFECYCLE_STATE[input.lifecycle];
    decision.evidence_source = "EXPLICIT_LIFECYCLE";
    decision.evidence_basis = "EXPLICIT_LIFECYCLE";
    decision.limitationParts.push(`Explicit lifecycle ${input.lifecycle} was supplied.`);
  } else if (validFacts.length > 0 || sawHttp || sawProcess || input.greenClaim || input.requestedState) {
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = sawHttp || sawProcess || input.greenClaim ? "REFUSED_OPTIMISTIC_SIGNAL" : "NON_PROTECTION_FACT";
    decision.evidence_source = sawHttp || sawProcess || input.greenClaim
      ? "REFUSED_OPTIMISTIC_SIGNAL"
      : (validFacts[0] ? validFacts[0].fact_kind : "ABSENT");
    if (HEALTHY.has(input.requestedState) || input.greenClaim || sawHttp || sawProcess) {
      pushUnique(errors, "OPTIMISTIC_GREEN_REFUSED");
    }
    decision.limitationParts.push("No protection evaluation supported a healthy token.");
  } else {
    decision.state = "EVIDENCE_UNAVAILABLE";
    decision.evidence_source = "ABSENT";
    decision.evidence_basis = "ABSENT";
    decision.limitationParts.push("No evidence was supplied.");
  }

  if (input.requestedState && input.requestedState !== decision.state) {
    decision.limitationParts.push(`Requested state ${input.requestedState} was not emitted.`);
    if (HEALTHY.has(input.requestedState) && !HEALTHY.has(decision.state)) {
      pushUnique(errors, "OPTIMISTIC_GREEN_REFUSED");
    }
  }

  if (
    decision.component === contract.unspecified_component
    && decision.state !== "EVIDENCE_UNAVAILABLE"
    && decision.state !== "ENFORCEMENT_UNKNOWN"
  ) {
    pushUnique(errors, "COMPONENT_REQUIRED");
    decision.limitationParts.push("The state was withheld because component was absent.");
    decision.state = "EVIDENCE_UNAVAILABLE";
    decision.evidence_basis = "ABSENT";
    decision.evidence_source = "ABSENT";
  }

  applyClassification(decision, input, errors);

  if (HEALTHY.has(decision.state) && (decision.scopeDefaulted || !input.timestamp || !input.producer || !input.sourceVersion)) {
    if (decision.scopeDefaulted) pushUnique(errors, "SCOPE_REQUIRED");
    if (!input.timestamp) pushUnique(errors, "TIMESTAMP_REQUIRED");
    if (!input.producer) pushUnique(errors, "EVIDENCE_PRODUCER_UNSPECIFIED");
    if (!input.sourceVersion) pushUnique(errors, "SOURCE_VERSION_REQUIRED");
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
    decision.failure_classification = "unsupported";
    decision.failure_classification_basis = "NOT_EVIDENCED";
  }

  if (decision.state !== "EVIDENCE_UNAVAILABLE" && decision.state !== "ENFORCEMENT_UNKNOWN" && !input.timestamp) {
    pushUnique(errors, "TIMESTAMP_REQUIRED");
    decision.limitationParts.push(`State ${decision.state} was withheld because no evidence timestamp was supplied.`);
    decision.state = "EVIDENCE_UNAVAILABLE";
    decision.evidence_basis = "ABSENT";
    decision.evidence_source = "ABSENT";
    decision.failure_classification = "unsupported";
    decision.failure_classification_basis = "NOT_EVIDENCED";
  }

  if (HEALTHY.has(decision.state) && healthyBlocked(errors)) {
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
    decision.failure_classification = "unsupported";
    decision.failure_classification_basis = "NOT_EVIDENCED";
    decision.limitationParts.push("The healthy token was withheld because the evidence record has errors.");
  }

  if (HEALTHY.has(decision.state)) {
    decision.derived_from_http_success = false;
    decision.derived_from_process_up = false;
    decision.http_status_ignored = sawHttp;
    decision.process_up_ignored = sawProcess;
  } else if (decision.evidence_basis === "REFUSED_OPTIMISTIC_SIGNAL") {
    decision.derived_from_http_success = sawHttp;
    decision.derived_from_process_up = sawProcess;
    decision.http_status_ignored = false;
    decision.process_up_ignored = false;
  } else {
    decision.derived_from_http_success = false;
    decision.derived_from_process_up = false;
    decision.http_status_ignored = sawHttp;
    decision.process_up_ignored = sawProcess;
  }
  if (decision.http_status_ignored) {
    decision.limitationParts.push("HTTP status was present and was not used to choose this state.");
  }
  if (decision.process_up_ignored) {
    decision.limitationParts.push("Process or heartbeat evidence was present and was not used to choose this state.");
  }

  return decision;
}

function normalizeLastKnownGood(value, errors) {
  if (value === undefined || value === null) return null;
  if (!isPlainObject(value)) {
    pushUnique(errors, "LAST_KNOWN_GOOD_REJECTED");
    return null;
  }
  const sourceOk = typeof value.evidence_source === "string"
    && value.evidence_source.trim() !== ""
    && !isOptimisticSource(value.evidence_source);
  if (!STATES.has(value.state) || value.freshness !== "UNKNOWN" || !isIsoTimestamp(value.timestamp) || !sourceOk) {
    pushUnique(errors, "LAST_KNOWN_GOOD_REJECTED");
    return null;
  }
  if (value.green === true || value.proved === true) {
    pushUnique(errors, "LAST_KNOWN_GOOD_REJECTED");
    return null;
  }
  return Object.freeze({
    state: value.state,
    timestamp: value.timestamp,
    evidence_source: value.evidence_source,
    freshness: "UNKNOWN",
  });
}

function limitationText(parts) {
  const cleaned = [];
  for (const part of parts) {
    if (typeof part === "string" && part.trim() && !cleaned.includes(part.trim())) cleaned.push(part.trim());
  }
  if (!cleaned.includes(GREEN_SENTENCE)) cleaned.push(GREEN_SENTENCE);
  return cleaned.join(" ");
}

function seal(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const key of Object.keys(value)) seal(value[key]);
    Object.freeze(value);
  }
  return value;
}

function toRecord(decision, input, emittedAt, errors, lastKnownGood) {
  const sourceVersion = input.sourceVersion || contract.catalog_commit;
  const producer = input.producer || contract.runtime_name;
  if (!input.sourceVersion) pushUnique(errors, "SOURCE_VERSION_DEFAULTED");
  if (!input.producer) pushUnique(errors, "EVIDENCE_PRODUCER_UNSPECIFIED");
  const audit = {
    caller_claimed_execution: decision.callerClaimedExecution,
    catalog_commit: contract.catalog_commit,
    catalog_protection_state: decision.catalog_protection_state,
    council_status: contract.council_status,
    derived_from_http_success: decision.derived_from_http_success,
    derived_from_process_up: decision.derived_from_process_up,
    emitted_at: emittedAt,
    errors: errors.slice(),
    evidence_basis: decision.evidence_basis,
    evidence_class: decision.evidence_class,
    failure_classification_basis: decision.failure_classification_basis,
    green: false,
    http_status_ignored: decision.http_status_ignored,
    live_phantom_enforcement_changed: false,
    named_gaps: decision.named_gaps.slice(),
    platform_status: decision.platform_status,
    process_up_ignored: decision.process_up_ignored,
    producer_classification: contract.producer_classification,
    proved: false,
    runtime_name: contract.runtime_name,
    runtime_version: contract.runtime_version,
    schema_status: contract.schema_status,
    source_version_kind: input.sourceVersion ? "CALLER_SUPPLIED" : "CATALOG_COMMIT",
    stable_schema: false,
    this_runtime_executed: false,
  };
  return {
    record_type: contract.record_type,
    state: decision.state,
    component: decision.component,
    scope: decision.scope,
    evidence_source: decision.evidence_source,
    timestamp: input.timestamp,
    freshness: "UNKNOWN",
    source_version: sourceVersion,
    producer,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
    limitation: limitationText(decision.limitationParts),
    failure_classification: decision.failure_classification,
    last_known_good: lastKnownGood,
    safe_corrective_action: contract.safe_corrective_action[decision.state],
    recovery_verification: "NOT_VERIFIED",
    audit,
  };
}

function catalogFailureRecord(loaded, emittedAt, errors) {
  return seal({
    record_type: contract.record_type,
    state: "EVIDENCE_UNAVAILABLE",
    component: contract.unspecified_component,
    scope: "REPOSITORY_ONLY",
    evidence_source: "CATALOG_UNREADABLE",
    timestamp: null,
    freshness: "UNKNOWN",
    source_version: contract.catalog_commit,
    producer: contract.runtime_name,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
    limitation: limitationText([loaded.limitation]),
    failure_classification: "unsupported",
    last_known_good: null,
    safe_corrective_action: contract.safe_corrective_action.EVIDENCE_UNAVAILABLE,
    recovery_verification: "NOT_VERIFIED",
    audit: {
      caller_claimed_execution: false,
      catalog_commit: contract.catalog_commit,
      catalog_protection_state: null,
      council_status: contract.council_status,
      derived_from_http_success: false,
      derived_from_process_up: false,
      emitted_at: emittedAt,
      errors: errors.concat(loaded.errors),
      evidence_basis: "CATALOG_UNREADABLE",
      evidence_class: "NOT_INDEPENDENTLY_VERIFIED",
      failure_classification_basis: "NOT_EVIDENCED",
      green: false,
      http_status_ignored: false,
      live_phantom_enforcement_changed: false,
      named_gaps: [],
      platform_status: null,
      process_up_ignored: false,
      producer_classification: contract.producer_classification,
      proved: false,
      runtime_name: contract.runtime_name,
      runtime_version: contract.runtime_version,
      schema_status: contract.schema_status,
      source_version_kind: "CATALOG_COMMIT",
      stable_schema: false,
      this_runtime_executed: false,
    },
  });
}

function produce(input = {}, options = {}) {
  const errors = [];
  const emittedAt = takeClock(options, errors);
  const loaded = loadCatalog(options);
  if (!loaded.ok || !emittedAt) return catalogFailureRecord(loaded.ok ? {
    errors: ["CLOCK_INVALID"],
    limitation: "The runtime clock did not return an ISO timestamp. No health token was inferred.",
  } : loaded, emittedAt, errors);
  const normalized = normalize(input, errors);
  const decision = decide(normalized, loaded.catalog, errors);
  const lastKnownGood = normalizeLastKnownGood(normalized.lastKnownGood, errors);
  if (HEALTHY.has(decision.state) && healthyBlocked(errors)) {
    decision.state = "ENFORCEMENT_UNKNOWN";
    decision.evidence_basis = "PROTECTION_EVALUATION_WITHHELD";
    decision.failure_classification = "unsupported";
    decision.failure_classification_basis = "NOT_EVIDENCED";
    decision.limitationParts.push("The healthy token was withheld because the evidence record has errors.");
  }
  return seal(toRecord(decision, normalized, emittedAt, errors, lastKnownGood));
}

module.exports = {
  produce,
};
