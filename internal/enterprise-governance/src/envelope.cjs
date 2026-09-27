"use strict";

const { DOMAINS } = require("./boundary.cjs");

const DOMAIN_SET = new Set(DOMAINS);
const TOKEN = /^[A-Za-z0-9._:/-]{1,200}$/;

function stringList(value) {
  if (!Array.isArray(value)) return null;
  const seen = new Set();
  const out = [];
  for (const item of value) {
    if (typeof item !== "string" || !TOKEN.test(item)) return null;
    if (seen.has(item)) continue;
    seen.add(item);
    out.push(item);
  }
  out.sort();
  return out;
}

function readCap(value, present) {
  if (!present) return { ok: false };
  if (value === null) return { ok: true, value: null };
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return { ok: false };
  return { ok: true, value };
}

function normalizeEnvelope(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { ok: false, reason: "ENVELOPE_REQUIRED" };
  }
  const hosts = stringList(value.hosts);
  const destinations = stringList(value.destinations);
  const pathConstraints = stringList(value.path_constraints);
  const actions = stringList(value.actions);
  const domains = stringList(value.domains);
  if (!hosts || !destinations || !pathConstraints || !actions || !domains) {
    return { ok: false, reason: "ENVELOPE_LIST_INVALID" };
  }
  for (const domain of domains) {
    if (!DOMAIN_SET.has(domain)) return { ok: false, reason: "UNKNOWN_DOMAIN" };
  }
  const hasSpend = Object.prototype.hasOwnProperty.call(value, "spend_cap");
  const hasSize = Object.prototype.hasOwnProperty.call(value, "size_cap");
  const spend = readCap(value.spend_cap, hasSpend);
  const size = readCap(value.size_cap, hasSize);
  if (!spend.ok || !size.ok) return { ok: false, reason: "CAP_INVALID" };
  return {
    ok: true,
    envelope: Object.freeze({
      hosts: Object.freeze(hosts),
      destinations: Object.freeze(destinations),
      path_constraints: Object.freeze(pathConstraints),
      actions: Object.freeze(actions),
      domains: Object.freeze(domains),
      spend_cap: spend.value,
      size_cap: size.value,
    }),
  };
}

function capRaised(childCap, parentCap) {
  if (parentCap === null) return false;
  if (childCap === null) return true;
  return childCap > parentCap;
}

function subsetViolations(child, parent) {
  const violations = [];
  for (const host of child.hosts) {
    if (!parent.hosts.includes(host)) violations.push(`host:${host}`);
  }
  for (const destination of child.destinations) {
    if (!parent.destinations.includes(destination)) violations.push(`destination:${destination}`);
  }
  for (const action of child.actions) {
    if (!parent.actions.includes(action)) violations.push(`action:${action}`);
  }
  for (const domain of child.domains) {
    if (!parent.domains.includes(domain)) violations.push(`domain:${domain}`);
  }
  for (const constraint of parent.path_constraints) {
    if (!child.path_constraints.includes(constraint)) violations.push(`path_constraint_removed:${constraint}`);
  }
  if (capRaised(child.spend_cap, parent.spend_cap)) violations.push("spend_cap_raised");
  if (capRaised(child.size_cap, parent.size_cap)) violations.push("size_cap_raised");
  return violations;
}

function envelopesEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function removed(before, after) {
  return before.filter((item) => !after.includes(item));
}

function tighterCap(left, right) {
  if (left === null) return right;
  if (right === null) return left;
  return Math.min(left, right);
}

function tightenTo(current, bound) {
  const constraints = [...new Set([...current.path_constraints, ...bound.path_constraints])].sort();
  return Object.freeze({
    hosts: Object.freeze(current.hosts.filter((item) => bound.hosts.includes(item))),
    destinations: Object.freeze(current.destinations.filter((item) => bound.destinations.includes(item))),
    actions: Object.freeze(current.actions.filter((item) => bound.actions.includes(item))),
    domains: Object.freeze(current.domains.filter((item) => bound.domains.includes(item))),
    path_constraints: Object.freeze(constraints),
    spend_cap: tighterCap(current.spend_cap, bound.spend_cap),
    size_cap: tighterCap(current.size_cap, bound.size_cap),
  });
}

module.exports = {
  envelopesEqual,
  normalizeEnvelope,
  removed,
  subsetViolations,
  tightenTo,
};
