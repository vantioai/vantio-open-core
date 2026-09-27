"use strict";

const { BANNER, CARD_IDS } = require("./constants.cjs");

function renderReport(doc) {
  const lines = [
    doc.audience,
    BANNER,
    `producer_classification=${doc.producer_classification}`,
    "external_proof=NOT_PROVED_EXTERNAL",
    "announcement=HOLD",
    "visual_completion_counts=false",
    `customer_activity_total=${doc.customer_activity_total}`,
  ];
  for (const id of CARD_IDS) {
    const card = (doc.cards || []).find((item) => item.id === id);
    if (!card) {
      lines.push(`[${id}] MISSING`);
      continue;
    }
    const label = card.simulation_label === null ? "NONE" : card.simulation_label;
    lines.push(`[${card.id}] proof_class=${card.proof_class} simulation_label=${label} external_proof=${card.external_proof}`);
  }
  return `${lines.join("\n")}\n`;
}

module.exports = { renderReport };
