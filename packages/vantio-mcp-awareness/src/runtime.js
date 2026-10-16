/**
 * Runtime closed over a process-local HMAC key.
 * Production code reaches this only through createRuntime(), which generates the key.
 */

import { createHmac, randomBytes } from "node:crypto";
import { MAX_GATES, MAX_SESSIONS, MAX_TAPS, MAX_TOMBSTONES } from "./bounds.js";
import { createSession, readEnvelope } from "./catalog.js";
import { createFramer, parseJson } from "./parse.js";
import { decideEnvelope, gapDecision, normalizePolicy } from "./policy.js";
import { createInProcessGate, createStdioPairGate, tapReadable } from "./observe.js";

export function assemble(key) {
  const store = createStore();
  let taps = 0;
  let gates = 0;

  function hmacHex(text) {
    return createHmac("sha256", key).update(String(text), "utf8").digest("hex");
  }

  function evaluateFrame(meta, fr) {
    const policy = meta.policyObject;
    const session = store.get(meta.serverId);
    if (fr.kind === "ignore") {
      return {
        forward: true,
        replacement: null,
        record: recordOf(meta, {
          action: "ALLOW",
          reason: fr.reason || "ignored_non_json",
          findings: [{ kind: fr.reason || "ignored_non_json" }],
          partial: {
            decision: { action: "ALLOW", reason: fr.reason || "ignored_non_json" },
            findings: [{ kind: fr.reason || "ignored_non_json" }],
            id_type: "absent",
            method_class: "other",
          },
          session,
        }),
        session,
      };
    }
    if (fr.kind !== "json") {
      const reason = fr.reason || fr.kind || "malformed_frame";
      const gap = gapDecision(reason === "oversize" ? "oversize" : reason);
      const action = policy.mode === "enforce" ? "GAP" : "GAP";
      const forward = policy.mode !== "enforce";
      return {
        forward,
        replacement: null,
        record: recordOf(meta, { ...gap, action, session }),
        session,
      };
    }
    let tree;
    try {
      tree = parseJson(fr.text);
    } catch {
      tree = { ok: false, reason: "malformed_json" };
    }
    if (!tree.ok) {
      const gap = gapDecision(tree.reason || "malformed_json");
      return {
        forward: policy.mode !== "enforce",
        replacement: forwardReplacement(policy, meta, fr, gap),
        record: recordOf(meta, { ...gap, session }),
        session,
      };
    }
    const envelope = readEnvelope(tree.value, { dups: tree.dups, truncated: tree.truncated });
    let decided;
    try {
      decided = decideEnvelope({
        policy,
        session,
        direction: meta.direction,
        envelope,
        hmacHex,
      });
    } catch {
      const gap = gapDecision("malformed_json");
      return {
        forward: policy.mode !== "enforce",
        replacement: null,
        record: recordOf(meta, { ...gap, session }),
        session,
      };
    }
    if (decided.session) store.commit(meta.serverId, decided.session);
    const forward = shouldForward(policy.mode, decided.action);
    const withheld = !forward;
    const replacement =
      meta.pair === true && withheld ? errorFrame(envelope, decided.reason) : null;
    return {
      forward,
      replacement,
      withheld,
      record: recordOf(meta, decided),
      session: decided.session,
    };
  }

  function runBuffer(buffer, meta) {
    const framer = createFramer(meta.transport || "stdio");
    const frames = [...framer.push(buffer), ...framer.finish()];
    const records = [];
    let session = store.get(meta.serverId);
    for (const fr of frames) {
      const out = evaluateFrame(meta, fr);
      records.push(out.record);
      session = out.session || session;
    }
    return { records, session };
  }

  return {
    normalizePolicy,
    createSession,
    hmacHex,
    observeBuffer(buffer, meta) {
      return runBuffer(buffer, { ...meta, policyObject: normalizePolicy(meta.policy) });
    },
    inspectExchange(input) {
      const policyObject = normalizePolicy(input.policy);
      const records = [];
      let session = store.get(input.serverId);
      const sides = [
        ["client_to_server", input.requestBody, input.requestType],
        ["server_to_client", input.responseBody, input.responseType],
      ];
      for (const [direction, body, type] of sides) {
        if (body == null) continue;
        const transport = String(type || "").includes("text/event-stream") ? "sse" : "json-body";
        const out = runBuffer(body, {
          transport,
          direction,
          serverId: input.serverId,
          policyObject,
        });
        records.push(...out.records);
        session = out.session || session;
      }
      return { records, session };
    },
    tapReadable(readable, meta) {
      if (taps >= MAX_TAPS) return { ok: false, reason: "cap" };
      const policyObject = normalizePolicy(meta.policy);
      const framer = createFramer(meta.transport || "stdio");
      const tap = tapReadable(readable, (chunk) => {
        if (!chunk) return;
        const frames = framer.push(chunk);
        for (const fr of frames) {
          const out = evaluateFrame({ ...meta, policyObject, direction: meta.direction || "server_to_client" }, fr);
          if (meta.onRecord) meta.onRecord(out.record);
        }
      });
      if (tap.ok) taps += 1;
      return tap;
    },
    createInProcessGate(meta) {
      if (gates >= MAX_GATES) return { ok: false, reason: "cap" };
      const policyObject = normalizePolicy(meta.policy);
      gates += 1;
      const stream = createInProcessGate(meta.transport || "stdio", (fr) => {
        const out = evaluateFrame(
          { ...meta, policyObject, direction: meta.direction || "client_to_server", pair: false },
          fr,
        );
        if (meta.onRecord) meta.onRecord(out.record);
        if (out.withheld && meta.onWithheld) meta.onWithheld(out.record);
        return { forward: out.forward, replacement: null };
      });
      return { ok: true, stream };
    },
    createStdioPairGate(meta) {
      if (gates >= MAX_GATES) return { ok: false, reason: "cap" };
      const policyObject = normalizePolicy(meta.policy);
      gates += 1;
      const gate = createStdioPairGate({
        fromChild: meta.fromChild,
        toChild: meta.toChild,
        onClientFrame: (fr) => {
          const out = evaluateFrame(
            { ...meta, policyObject, direction: "client_to_server", pair: true },
            fr,
          );
          if (meta.onRecord) meta.onRecord(out.record);
          return { forward: out.forward, replacement: out.replacement };
        },
        onServerFrame: (fr) => {
          const out = evaluateFrame(
            { ...meta, policyObject, direction: "server_to_client", pair: true },
            fr,
          );
          if (meta.onRecord) meta.onRecord(out.record);
          return { forward: out.forward, replacement: out.replacement };
        },
      });
      return { ok: true, ...gate };
    },
  };
}

function shouldForward(mode, action) {
  if (action === "BLOCK") return false;
  if (action === "GAP") return mode !== "enforce";
  return true;
}

function recordOf(meta, decided) {
  const partial = decided.partial || {};
  const record = {
    schema: "vantio.mcp_observation.v1",
    at: new Date().toISOString(),
    transport: meta.transport || "stdio",
    direction: meta.direction,
    server_id: meta.serverId,
    findings: partial.findings || decided.findings || [],
    decision: partial.decision || { action: decided.action, reason: decided.reason },
    retention: { payload: false, values: false },
  };
  if (partial.method) record.method = partial.method;
  if (partial.method_class) record.method_class = partial.method_class;
  if (partial.method_hmac) record.method_hmac = partial.method_hmac;
  if (partial.id_type) record.id_type = partial.id_type;
  if (typeof partial.id_number === "number") record.id_number = partial.id_number;
  if (partial.id_hmac) record.id_hmac = partial.id_hmac;
  if (typeof partial.tool_name === "string") record.tool_name = partial.tool_name;
  if (partial.tool_hmac) record.tool_hmac = partial.tool_hmac;
  if (partial.argument_shape) record.argument_shape = partial.argument_shape;
  return record;
}

function errorFrame(envelope, reason) {
  if (!envelope || envelope.idType !== "number" || typeof envelope.idNumber !== "number") {
    const body = `{"jsonrpc":"2.0","id":null,"error":{"code":-32001,"message":"vantio_mcp_policy_block","data":{"finding":${JSON.stringify(reason || "policy")}}}}\n`;
    return Buffer.from(body);
  }
  const body = `{"jsonrpc":"2.0","id":${envelope.idNumber},"error":{"code":-32001,"message":"vantio_mcp_policy_block","data":{"finding":${JSON.stringify(reason || "policy")}}}}\n`;
  return Buffer.from(body);
}

function forwardReplacement(policy, meta, fr, gap) {
  if (meta.pair !== true || policy.mode !== "enforce") return null;
  return Buffer.from(
    `{"jsonrpc":"2.0","id":null,"error":{"code":-32001,"message":"vantio_mcp_policy_block","data":{"finding":${JSON.stringify(gap.reason)}}}}\n`,
  );
}

function createStore() {
  const order = [];
  const map = new Map();
  const tombs = new Map();
  let overflow = false;
  return {
    get(serverId) {
      if (map.has(serverId)) {
        const at = order.indexOf(serverId);
        if (at >= 0) order.splice(at, 1);
        order.push(serverId);
        return map.get(serverId);
      }
      const restarted = overflow || tombs.has(serverId);
      const session = createSession(serverId, { stale: restarted, restarted });
      map.set(serverId, session);
      order.push(serverId);
      while (order.length > MAX_SESSIONS) {
        const old = order.shift();
        map.delete(old);
        if (tombs.size >= MAX_TOMBSTONES) overflow = true;
        else tombs.set(old, true);
      }
      return session;
    },
    commit(serverId, session) {
      map.set(serverId, session);
      if (session.sawList && session.stale !== true) tombs.delete(serverId);
    },
  };
}

export function productionKey() {
  return randomBytes(32);
}
