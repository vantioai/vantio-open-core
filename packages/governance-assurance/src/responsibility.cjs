"use strict";

const { RACI, ROLES } = require("./constants.cjs");
const { CONTROLS } = require("./data/controls.cjs");

function blankRow() {
  const raci = {};
  for (const role of ROLES) raci[role] = "INFORMED";
  return raci;
}

function raciFor(control) {
  const raci = blankRow();
  raci.CUSTOMER_AI_OWNER = "ACCOUNTABLE";
  raci.CUSTOMER_SECURITY = "CONSULTED";
  raci.CUSTOMER_COMPLIANCE = "CONSULTED";
  raci.CUSTOMER_INFRASTRUCTURE_OPERATOR = "CONSULTED";
  raci.VANTIO = "CONSULTED";
  raci.INDEPENDENT_ASSESSOR = "CONSULTED";
  if (control.domain === "LEGAL") {
    raci.VANTIO = "NOT_APPLICABLE";
    raci.CUSTOMER_LEGAL = "ACCOUNTABLE";
    raci.CUSTOMER_AI_OWNER = "RESPONSIBLE";
    raci.CUSTOMER_COMPLIANCE = "CONSULTED";
    raci.MODEL_PROVIDER = control.primary_support === "THIRD_PARTY_REQUIRED" ? "RESPONSIBLE" : "CONSULTED";
  } else if (control.domain === "PRIVACY") {
    raci.VANTIO = "RESPONSIBLE";
    raci.CUSTOMER_PRIVACY = "ACCOUNTABLE";
    raci.CUSTOMER_AI_OWNER = "CONSULTED";
  } else if (control.domain === "PROCUREMENT") {
    raci.VANTIO = "RESPONSIBLE";
    raci.CUSTOMER_COMPLIANCE = "ACCOUNTABLE";
    raci.CUSTOMER_LEGAL = "CONSULTED";
  } else if (control.domain === "DISCLOSURE") {
    raci.VANTIO = "RESPONSIBLE";
    raci.CUSTOMER_AI_OWNER = "INFORMED";
    raci.CUSTOMER_COMPLIANCE = "CONSULTED";
  } else if (control.primary_support === "CUSTOMER_PROVIDES" || control.primary_support === "CUSTOMER_CONFIGURES") {
    raci.VANTIO = "CONSULTED";
    raci.CUSTOMER_AI_OWNER = "ACCOUNTABLE";
    raci.CUSTOMER_INFRASTRUCTURE_OPERATOR = "RESPONSIBLE";
  } else if (control.primary_support === "NOT_IMPLEMENTED" || control.primary_support === "UNVERIFIED") {
    raci.VANTIO = "INFORMED";
    raci.CUSTOMER_AI_OWNER = "ACCOUNTABLE";
    raci.CUSTOMER_SECURITY = "RESPONSIBLE";
  } else if (control.primary_support === "VANTIO_PROVIDES" || control.primary_support === "VANTIO_PARTIALLY_SUPPORTS") {
    raci.VANTIO = "RESPONSIBLE";
    raci.CUSTOMER_AI_OWNER = "ACCOUNTABLE";
  }
  return raci;
}

function buildMatrix(controls = CONTROLS) {
  return {
    schema: "vantio.governance-assurance.responsibility/v1",
    audience: "INTERNAL_RESTRICTED",
    customer_org_structure: "NOT_ASSERTED",
    template: true,
    roles: ROLES,
    raci_values: RACI,
    rows: controls.map((control) => ({
      control_id: control.control_id,
      domain: control.domain,
      primary_support: control.primary_support,
      raci: raciFor(control),
    })),
  };
}

function applyOverrides(matrix, overrides) {
  const next = {
    ...matrix,
    template: true,
    customer_org_structure: "NOT_ASSERTED",
    rows: matrix.rows.map((row) => ({ ...row, raci: { ...row.raci } })),
  };
  for (const [controlId, roleMap] of Object.entries(overrides || {})) {
    const row = next.rows.find((item) => item.control_id === controlId);
    if (!row) throw new Error(`unknown control ${controlId}`);
    for (const [role, value] of Object.entries(roleMap)) {
      if (!ROLES.includes(role)) throw new Error(`unknown role ${role}`);
      if (!RACI.includes(value)) throw new Error(`unknown raci ${value}`);
      row.raci[role] = value;
    }
  }
  return next;
}

function customerResponsibilityCount(matrix) {
  let count = 0;
  for (const row of matrix.rows) {
    for (const [role, value] of Object.entries(row.raci)) {
      if (role.startsWith("CUSTOMER_") && (value === "RESPONSIBLE" || value === "ACCOUNTABLE")) count += 1;
    }
  }
  return count;
}

module.exports = {
  applyOverrides,
  buildMatrix,
  customerResponsibilityCount,
  raciFor,
};
