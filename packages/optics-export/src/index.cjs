"use strict";

const { loadConfig } = require("./config.cjs");
const { attestObservation, createExporter } = require("./exporter.cjs");
const { SCHEMA_ID, SCHEMA_VERSION, acceptsVersion } = require("./schema.cjs");

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
  if (!config.enabled) {
    return {
      offer() {
        return { accepted: false, reason: config.reason || "DISABLED" };
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
  producerClaimed = true;
  const exporter = createExporter(config);
  return {
    offer(event) {
      const attested = attestObservation(event);
      if (!attested.ok) return { accepted: false, reason: attested.reason || "UNATTESTED" };
      return exporter.offer(event, exporter.token);
    },
    status: exporter.status,
    flush: exporter.flush,
    stop: exporter.stop,
  };
}

module.exports = {
  SCHEMA_ID,
  SCHEMA_VERSION,
  acceptsVersion,
  createExporter,
  loadConfig,
  startFromConfig,
};
