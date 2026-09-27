"use strict";

const {
  DECISION_CLASSES,
  EFFECTS,
  EVIDENCE_KINDS,
  POSTURE,
  PRODUCER_CLASSIFICATION,
  ROLLOUT_STEPS,
  STAGES,
} = require("./boundary.cjs");
const { replayHistory } = require("./replay.cjs");
const engine = require("./engine.cjs");

module.exports = {
  DECISION_CLASSES,
  EFFECTS,
  EVIDENCE_KINDS,
  POSTURE,
  PRODUCER_CLASSIFICATION,
  ROLLOUT_STEPS,
  STAGES,
  activeEnforcement: engine.activeEnforcement,
  advanceRollout: engine.advanceRollout,
  canary: engine.canary,
  createEngine: engine.createEngine,
  decide: engine.decide,
  discover: engine.discover,
  expireDueExceptions: engine.expireDueExceptions,
  freeze: engine.freeze,
  grantException: engine.grantException,
  ingest: engine.ingest,
  listEvidence: engine.listEvidence,
  observe: engine.observe,
  promote: engine.promote,
  propose: engine.propose,
  replayHistory,
  review: engine.review,
  revokeOrRollback: engine.revokeOrRollback,
  simulate: engine.simulate,
  thaw: engine.thaw,
  retire: engine.retire,
  verifyRemoval: engine.verifyRemoval,
};
