"use strict";

const { loadConfig } = require("./config.cjs");
const { attestObservation, canonicalEventBytes, createExporter } = require("./exporter.cjs");
const { SCHEMA_ID, SCHEMA_VERSION, acceptsVersion } = require("./schema.cjs");
const {
  PRODUCT_OTLP_EXPORT_AUTHORIZED,
  verifyExternalSourceSignature,
} = require("./source-signature.cjs");

let producerClaimed = false;

function disabledExporter(reason) {
  return {
    offer() {
      return { accepted: false, reason };
    },
    status() {
      return { health: "disabled", queued: 0, dropped: 0, rejected: 0, sent: 0 };
    },
    flush() {
      return Promise.resolve();
    },
    stop() {},
  };
}

function startFromConfig(filePath) {
  if (producerClaimed) return disabledExporter("UNATTESTED");
  let config;
  try {
    config = loadConfig(filePath);
  } catch {
    config = { enabled: false, reason: "CONFIG_REFUSED" };
  }
  if (!config.enabled) return disabledExporter(config.reason || "DISABLED");
  producerClaimed = true;
  const exporter = createExporter(config);
  return {
    offer(event, externalSignature) {
      const attested = attestObservation(event);
      if (!attested.ok) return { accepted: false, reason: attested.reason || "UNATTESTED" };
      return exporter.offer(event, exporter.token, externalSignature);
    },
    status: exporter.status,
    flush: (options) => exporter.flush(options),
    stop: exporter.stop,
  };
}

module.exports = {
  PRODUCT_OTLP_EXPORT_AUTHORIZED,
  SCHEMA_ID,
  SCHEMA_VERSION,
  acceptsVersion,
  canonicalEventBytes,
  createExporter,
  loadConfig,
  startFromConfig,
  verifyExternalSourceSignature,
};
