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

function unionAdded(current, baseline, widened, revoked) {
  const blocked = new Set(revoked || []);
  const merged = current.slice();
  for (const item of widened) {
    if (baseline.includes(item) || merged.includes(item) || blocked.has(item)) continue;
    merged.push(item);
  }
  merged.sort();
  return merged;
}

function composePaths(current, baseline, widened) {
  const kept = [];
  for (const item of current) {
    if (baseline.includes(item) && !widened.includes(item)) continue;
    kept.push(item);
  }
  kept.sort();
  return kept;
}

function capIsNarrower(current, baseline) {
  if (current === null) return false;
  if (baseline === null) return true;
  return current < baseline;
}

function widerCap(current, widened) {
  if (current === null || widened === null) return null;
  return Math.max(current, widened);
}

function composeCap(current, baseline, widened, ceiling) {
  if (ceiling != null && capRaised(current, ceiling)) return current;
  const target = ceiling == null ? widened : tighterCap(widened, ceiling);
  if (capIsNarrower(current, baseline)) return current;
  if (ceiling != null && current !== baseline && capIsNarrower(current, widened)) return current;
  let raised = widerCap(current, target);
  if (ceiling != null && capRaised(raised, ceiling)) raised = ceiling;
  return raised;
}

function listRevoked(options, key) {
  if (!options || !options.revoked || !options.revoked[key]) return [];
  return options.revoked[key];
}

function composeWiden(current, baseline, widened, options) {
  return Object.freeze({
    hosts: Object.freeze(unionAdded(current.hosts, baseline.hosts, widened.hosts, listRevoked(options, "hosts"))),
    destinations: Object.freeze(unionAdded(
      current.destinations,
      baseline.destinations,
      widened.destinations,
      listRevoked(options, "destinations"),
    )),
    path_constraints: Object.freeze(composePaths(current.path_constraints, baseline.path_constraints, widened.path_constraints)),
    actions: Object.freeze(unionAdded(current.actions, baseline.actions, widened.actions, listRevoked(options, "actions"))),
    domains: Object.freeze(unionAdded(current.domains, baseline.domains, widened.domains, listRevoked(options, "domains"))),
    spend_cap: composeCap(current.spend_cap, baseline.spend_cap, widened.spend_cap, options && options.spendCeiling),
    size_cap: composeCap(current.size_cap, baseline.size_cap, widened.size_cap, options && options.sizeCeiling),
  });
}

const LIST_KEYS = ["hosts", "destinations", "actions", "domains"];

function ensureRevoked(open) {
  if (!open.revoked) {
    open.revoked = { hosts: [], destinations: [], actions: [], domains: [] };
  }
  return open.revoked;
}

function noteNarrow(openWidens, before, after) {
  const cuts = {
    hosts: removed(before.hosts, after.hosts),
    destinations: removed(before.destinations, after.destinations),
    actions: removed(before.actions, after.actions),
    domains: removed(before.domains, after.domains),
  };
  for (const open of openWidens) {
    const revoked = ensureRevoked(open);
    for (const key of LIST_KEYS) {
      for (const item of cuts[key]) {
        if (!revoked[key].includes(item)) revoked[key].push(item);
      }
    }
    if (capIsNarrower(after.spend_cap, before.spend_cap)) {
      open.spend_ceiling = open.spend_ceiling == null
        ? after.spend_cap
        : tighterCap(open.spend_ceiling, after.spend_cap);
    }
    if (capIsNarrower(after.size_cap, before.size_cap)) {
      open.size_ceiling = open.size_ceiling == null
        ? after.size_cap
        : tighterCap(open.size_ceiling, after.size_cap);
    }
  }
}

function addedBy(open, key) {
  const revoked = new Set(open.revoked && open.revoked[key] ? open.revoked[key] : []);
  const added = [];
  for (const item of open.next_policy[key]) {
    if (open.baseline[key].includes(item) || revoked.has(item)) continue;
    added.push(item);
  }
  return added;
}

function siblingAdditions(staying, key) {
  const extras = new Set();
  for (const open of staying) {
    for (const item of addedBy(open, key)) extras.add(item);
  }
  return extras;
}

function siblingCap(staying, field, ceilingField) {
  let chosen;
  for (const open of staying) {
    const target = open.next_policy[field];
    const base = open.baseline[field];
    if (!capRaised(target, base)) continue;
    const ceiling = open[ceilingField];
    const contribution = ceiling == null ? target : tighterCap(target, ceiling);
    chosen = chosen === undefined ? contribution : widerCap(chosen, contribution);
  }
  return chosen;
}

function capAfterRollback(current, boundCap, staying, field, ceilingField) {
  const sibling = siblingCap(staying, field, ceilingField);
  const tightened = tighterCap(current, boundCap);
  if (sibling === undefined) return tightened;
  if (capIsNarrower(current, boundCap) && capIsNarrower(current, sibling)) return current;
  return widerCap(tightened, sibling);
}

function keepListed(current, bound, extras) {
  const kept = current.filter((item) => bound.includes(item) || extras.has(item));
  kept.sort();
  return kept;
}

function rollbackPreserving(current, bound, staying) {
  const active = staying || [];
  const paths = new Set([...current.path_constraints, ...bound.path_constraints]);
  for (const open of active) {
    for (const item of open.baseline.path_constraints) {
      if (!open.next_policy.path_constraints.includes(item)) paths.delete(item);
    }
  }
  const constraints = [...paths];
  constraints.sort();
  return Object.freeze({
    hosts: Object.freeze(keepListed(current.hosts, bound.hosts, siblingAdditions(active, "hosts"))),
    destinations: Object.freeze(keepListed(
      current.destinations,
      bound.destinations,
      siblingAdditions(active, "destinations"),
    )),
    path_constraints: Object.freeze(constraints),
    actions: Object.freeze(keepListed(current.actions, bound.actions, siblingAdditions(active, "actions"))),
    domains: Object.freeze(keepListed(current.domains, bound.domains, siblingAdditions(active, "domains"))),
    spend_cap: capAfterRollback(current.spend_cap, bound.spend_cap, active, "spend_cap", "spend_ceiling"),
    size_cap: capAfterRollback(current.size_cap, bound.size_cap, active, "size_cap", "size_ceiling"),
  });
}

module.exports = {
  composeWiden,
  envelopesEqual,
  normalizeEnvelope,
  noteNarrow,
  removed,
  rollbackPreserving,
  subsetViolations,
  tightenTo,
};
