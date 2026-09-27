"use strict";

const runtime = require("./runtime.cjs");

module.exports = {
  evidenceRoot: runtime.evidenceRoot,
  getRecord: runtime.getRecord,
  openStore: runtime.openStore,
  put: runtime.put,
  query: runtime.query,
  salvage: runtime.salvage,
};
