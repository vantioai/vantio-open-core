"use strict";

function comparisonDocument(fixture) {
  return {
    achievement: fixture.achievement,
    aliases_used: fixture.aliases_used,
    compatibility_classification: fixture.compatibility_classification,
    diagnostic_limitations: fixture.diagnostic_limitations,
    evidence_origin: fixture.evidence_origin,
    expected_canonical: fixture.expected_canonical,
    expected_events: fixture.expected_events,
    expected_unsupported_state: fixture.expected_unsupported_state,
    fields_not_promoted: fixture.fields_not_promoted,
    fixture_id: fixture.id,
    input_parse: fixture.input_parse,
    producer_surface: fixture.producer.surface,
    producer_version: fixture.producer.version,
    record_emitted: fixture.record_emitted,
    scenario: fixture.scenario,
    semantic_dimension_readings: fixture.semantic_dimension_readings,
  };
}

module.exports = { comparisonDocument };
