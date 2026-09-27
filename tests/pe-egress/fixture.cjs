"use strict";

function policy(extra) {
  return Object.assign({
    enforce: true,
    dry_run: false,
    scope: "llm_and_named",
  }, extra || {});
}

function attempt(extra) {
  return Object.assign({
    policy_loaded: true,
    destination: {
      hostname: "api.openai.com",
      port: "443",
      protocol: "https",
      in_product_scope: true,
    },
  }, extra || {});
}

function hostObservation(extra) {
  return Object.assign({
    supplied: true,
    evidence: "supplied",
    enrolled: true,
    attach: "tc",
    saw: ["destination_ip", "port", "protocol"],
    dropped: false,
    contained: false,
    forwarded_cgroup0: false,
  }, extra || {});
}

function decide(evaluate, fields) {
  return evaluate({
    policy: policy(fields && fields.policy),
    path: { id: (fields && fields.path) || "app_fetch" },
    attempt: attempt(fields && fields.attempt),
  });
}

module.exports = {
  attempt,
  decide,
  hostObservation,
  policy,
};
