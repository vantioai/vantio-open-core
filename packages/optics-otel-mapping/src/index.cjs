"use strict";

const { POSTURE } = require("./boundary.cjs");
const { exportRecords, listAdapters } = require("./adapters.cjs");
const { ALLOWED_MAP_TARGETS, PROHIBITED_TARGETS, loadMapping } = require("./load.cjs");
const { designPreview } = require("./preview.cjs");

const mapping = loadMapping();

function mappingDocument() {
  return mapping;
}

function adapters() {
  return listAdapters(mapping);
}

function exportOpticsRecords(records, options) {
  return exportRecords(mapping, records, options);
}

function preview(record) {
  return designPreview(mapping, record);
}

module.exports = {
  ALLOWED_MAP_TARGETS,
  POSTURE,
  PROHIBITED_TARGETS,
  adapters,
  exportOpticsRecords,
  mappingDocument,
  preview,
};
