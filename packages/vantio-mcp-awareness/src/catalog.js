/**
 * Tool-name checks, pin comparison, and session updates.
 * Skeletons of names the operator did not write are not stored.
 * Description and schema digests are compared and then dropped.
 */

import { createHash } from "node:crypto";
import {
  MAX_CANON,
  MAX_NAME,
  MAX_PROPERTY_NAMES,
  MAX_SHAPE_NODES,
  MAX_TOOLS,
  isKnownMethod,
} from "./bounds.js";

const HIDDEN =
  /[\u0000-\u001F\u007F\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069]|\u{E0001}|[\u{E0020}-\u{E007F}]/u;

const FOLD = new Map(
  Object.entries({
    А: "A",
    а: "a",
    В: "B",
    в: "b",
    Е: "E",
    е: "e",
    К: "K",
    к: "k",
    М: "M",
    м: "m",
    Н: "H",
    н: "h",
    О: "O",
    о: "o",
    Р: "P",
    р: "p",
    С: "C",
    с: "c",
    Т: "T",
    т: "t",
    У: "Y",
    у: "y",
    Х: "X",
    х: "x",
    І: "I",
    і: "i",
    Ј: "J",
    ј: "j",
    Α: "A",
    α: "a",
    Β: "B",
    Ε: "E",
    ε: "e",
    Ζ: "Z",
    ζ: "z",
    Η: "H",
    η: "h",
    Ι: "I",
    ι: "i",
    Κ: "K",
    κ: "k",
    Μ: "M",
    Ν: "N",
    Ο: "O",
    ο: "o",
    Ρ: "P",
    ρ: "p",
    Τ: "T",
    τ: "t",
    Υ: "Y",
    υ: "y",
    Χ: "X",
    χ: "x",
  }),
);

function has(node, key) {
  return node && node.t === "object" && Object.prototype.hasOwnProperty.call(node.map, key);
}

function str(node) {
  return node && node.t === "string" ? node.v : undefined;
}

export function sha256Text(text) {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

export function scriptBuckets(name) {
  const set = new Set();
  for (const ch of name) {
    const cp = ch.codePointAt(0);
    const bucket = bucketOf(cp);
    if (bucket === "Common" || bucket === "Inherited") continue;
    set.add(bucket);
  }
  return set;
}

function bucketOf(cp) {
  if ((cp >= 0x41 && cp <= 0x5a) || (cp >= 0x61 && cp <= 0x7a)) return "Latin";
  if (cp <= 0x7f) return "Common";
  if (cp >= 0xc0 && cp <= 0x24f) return "Latin";
  if (cp >= 0x1e00 && cp <= 0x1eff) return "Latin";
  if (cp >= 0x300 && cp <= 0x36f) return "Inherited";
  if (cp >= 0x370 && cp <= 0x3ff) return "Greek";
  if (cp >= 0x400 && cp <= 0x52f) return "Cyrillic";
  return "Other";
}

export function skeletonOf(name) {
  const folded = name.normalize("NFKC");
  let out = "";
  for (const ch of folded) {
    if (HIDDEN.test(ch)) continue;
    out += FOLD.get(ch) || ch;
  }
  return out;
}

export function inspectName(name, operatorNames) {
  const findings = [];
  if (typeof name !== "string") {
    findings.push("tool_name_type");
    return { findings, operatorExact: false, skeleton: "" };
  }
  if (HIDDEN.test(name)) findings.push("hidden_chars_in_name");
  const nfkc = name.normalize("NFKC");
  if (nfkc !== name) findings.push("nfkc_mismatch");
  if (scriptBuckets(name).size > 1) findings.push("mixed_script_name");
  const skeleton = skeletonOf(name);
  let operatorExact = false;
  for (const op of operatorNames) {
    if (op === name) operatorExact = true;
    else if (skeleton.length > 0 && skeleton === skeletonOf(op)) findings.push("confusable_name");
  }
  if (name.length > MAX_NAME) findings.push("truncated_shape");
  return { findings, operatorExact, skeleton };
}

function canonNode(node, parts, state) {
  if (!node || state.over) {
    state.over = true;
    return;
  }
  const push = (piece) => {
    state.len += piece.length;
    if (state.len > MAX_CANON) state.over = true;
    else parts.push(piece);
  };
  if (node.t === "string") push(JSON.stringify(node.v));
  else if (node.t === "number") push(node.lex);
  else if (node.t === "bool") push(node.v ? "true" : "false");
  else if (node.t === "null") push("null");
  else if (node.t === "array") {
    if (node.truncated) state.over = true;
    push("[");
    for (let i = 0; i < node.items.length && !state.over; i += 1) {
      if (i) push(",");
      canonNode(node.items[i], parts, state);
    }
    push("]");
  } else if (node.t === "object") {
    if (node.dup) state.over = true;
    push("{");
    const keys = node.order.slice().sort();
    for (let i = 0; i < keys.length && !state.over; i += 1) {
      if (i) push(",");
      push(JSON.stringify(keys[i]));
      push(":");
      canonNode(node.map[keys[i]], parts, state);
    }
    push("}");
  } else state.over = true;
}

export function schemaPin(toolNode, truncated) {
  if (!toolNode || toolNode.t !== "object" || truncated) return { state: "unbounded" };
  const picked = { t: "object", map: Object.create(null), order: [], dup: toolNode.dup };
  for (const key of ["inputSchema", "outputSchema", "annotations", "title", "_meta"]) {
    if (has(toolNode, key)) {
      picked.map[key] = toolNode.map[key];
      picked.order.push(key);
    }
  }
  const parts = [];
  const state = { len: 0, over: false };
  canonNode(picked, parts, state);
  if (state.over) return { state: "unbounded" };
  return { state: "hash", hex: sha256Text(parts.join("")) };
}

export function descriptionPin(text) {
  if (typeof text !== "string") return { state: "hash", hex: sha256Text("") };
  if (Buffer.byteLength(text) > MAX_CANON) return { state: "unbounded" };
  return { state: "hash", hex: sha256Text(text) };
}

export function comparePin(computed, pin) {
  if (computed.state === "unbounded") return "unbounded";
  if (typeof pin !== "string" || pin.length === 0) return "unpinned";
  return computed.hex === pin.toLowerCase() ? "match" : "mismatch";
}

export function propertyNamesFrom(toolNode, schemaMatched) {
  if (!schemaMatched || !toolNode || toolNode.t !== "object") return [];
  const schema = toolNode.map.inputSchema;
  if (!schema || schema.t !== "object" || !schema.map.properties || schema.map.properties.t !== "object") {
    return [];
  }
  const names = [];
  for (const name of schema.map.properties.order) {
    if (/^[A-Za-z0-9_.-]{1,64}$/.test(name)) names.push(name);
    if (names.length >= MAX_PROPERTY_NAMES) break;
  }
  return names;
}

export function argumentShape(node, allowRaw, hmacHex, budget = { n: MAX_SHAPE_NODES }) {
  if (!node || budget.n <= 0) return { t: "truncated" };
  budget.n -= 1;
  if (node.t === "string") return { t: "string", n: node.bytes };
  if (node.t === "number") return { t: "number" };
  if (node.t === "bool") return { t: "boolean" };
  if (node.t === "null") return { t: "null" };
  if (node.t === "truncated") return { t: "truncated" };
  if (node.t === "array") {
    const items = [];
    const cap = Math.min(node.items.length, 8);
    for (let i = 0; i < cap; i += 1) items.push(argumentShape(node.items[i], allowRaw, hmacHex, budget));
    return { t: "array", n: node.total, items, truncated: node.truncated === true };
  }
  if (node.t === "object") {
    const keys = [];
    for (const name of node.order) {
      const child = argumentShape(node.map[name], allowRaw, hmacHex, budget);
      if (allowRaw.has(name)) keys.push({ name, ...child });
      else keys.push({ key_hmac: hmacHex(name), ...child });
    }
    return { t: "object", n: node.order.length, keys, dup: node.dup === true };
  }
  return { t: "truncated" };
}

export function createSession(serverId, opts = {}) {
  return {
    serverId,
    stale: opts.stale === true,
    incomplete: false,
    sawList: false,
    restarted: opts.restarted === true,
    tools: Object.create(null),
    draftOpen: false,
    draft: Object.create(null),
    pending: Object.create(null),
    pendingCount: 0,
  };
}

export function cloneSession(session) {
  const tools = Object.create(null);
  for (const key of Object.keys(session.tools)) {
    const row = session.tools[key];
    tools[key] = {
      operatorName: row.operatorName,
      descriptionPin: row.descriptionPin,
      schemaPin: row.schemaPin,
      propertyNames: row.propertyNames.slice(),
    };
  }
  const draft = Object.create(null);
  for (const key of Object.keys(session.draft)) draft[key] = session.draft[key];
  const pending = Object.create(null);
  for (const key of Object.keys(session.pending)) pending[key] = session.pending[key];
  return {
    serverId: session.serverId,
    stale: session.stale,
    incomplete: session.incomplete,
    sawList: session.sawList,
    restarted: session.restarted,
    tools,
    draftOpen: session.draftOpen,
    draft,
    pending,
    pendingCount: session.pendingCount,
  };
}

export function readEnvelope(value, flags) {
  if (!value || value.t === "array") return { batch: true, dups: flags.dups === true, truncated: flags.truncated === true };
  if (value.t !== "object") return { malformed: true, dups: flags.dups === true, truncated: flags.truncated === true };
  const map = value.map;
  const rpc = str(map.jsonrpc);
  if (rpc != null && rpc !== "2.0") return { malformed: true, dups: flags.dups === true, truncated: flags.truncated === true };
  const method = str(map.method);
  const hasId = has(value, "id");
  let idType = "absent";
  let idNumber;
  let idString;
  if (hasId) {
    const idNode = map.id;
    if (idNode.t === "number" && /^-?(0|[1-9][0-9]*)$/.test(idNode.lex)) {
      const n = Number(idNode.lex);
      if (Number.isSafeInteger(n)) {
        idType = "number";
        idNumber = n;
      } else idType = "bad";
    } else if (idNode.t === "string") {
      idType = "string";
      idString = idNode.v;
    } else idType = "bad";
  }
  let kind = "malformed";
  if (has(value, "error")) kind = "error";
  else if (has(value, "result")) kind = "result";
  else if (typeof method === "string" && !hasId) kind = "notification";
  else if (typeof method === "string") kind = "request";
  return {
    batch: false,
    malformed: false,
    kind,
    method: typeof method === "string" ? method : undefined,
    idType,
    idNumber,
    idString,
    dups: flags.dups === true || value.dup === true,
    truncated: flags.truncated === true,
    map,
  };
}

export function methodLabel(method) {
  if (typeof method === "string" && isKnownMethod(method)) return { method_class: "known", method };
  return { method_class: "other" };
}

export function contentStrings(map) {
  const texts = [];
  const result = map && map.result && map.result.t === "object" ? map.result : null;
  if (!result) return texts;
  const content = result.map.content;
  if (content && content.t === "array") {
    for (const block of content.items) {
      if (!block || block.t !== "object") continue;
      if (block.map.text && block.map.text.t === "string") texts.push(block.map.text.v);
      const resource = block.map.resource;
      if (resource && resource.t === "object" && resource.map.text && resource.map.text.t === "string") {
        texts.push(resource.map.text.v);
      }
    }
  }
  if (result.map.structuredContent) texts.push(jsonish(result.map.structuredContent));
  return texts;
}

function jsonish(node) {
  if (!node) return "";
  if (node.t === "string") return node.v;
  const parts = [];
  const state = { len: 0, over: false };
  canonNode(node, parts, state);
  return parts.join("");
}

export function samplingTexts(map) {
  const params = map && map.params && map.params.t === "object" ? map.params : null;
  if (!params) return [];
  return [jsonish(params)];
}

export function listTools(map) {
  const result = map && map.result && map.result.t === "object" ? map.result : null;
  if (!result || !result.map.tools || result.map.tools.t !== "array") return null;
  const tools = [];
  for (const tool of result.map.tools.items) {
    if (!tool || tool.t !== "object") continue;
    tools.push(tool);
    if (tools.length >= MAX_TOOLS) break;
  }
  return {
    tools,
    truncated: result.map.tools.truncated === true || result.map.tools.total > tools.length,
    nextCursor: has(result, "nextCursor"),
  };
}

export function instructionsText(map) {
  const result = map && map.result && map.result.t === "object" ? map.result : null;
  if (!result || !result.map.instructions || result.map.instructions.t !== "string") return undefined;
  return result.map.instructions.v;
}

export function callParts(map) {
  const params = map && map.params && map.params.t === "object" ? map.params : null;
  if (!params) return { nameNode: undefined, args: undefined };
  return { nameNode: params.map.name, args: params.map.arguments };
}

export function retainValues(args, keys) {
  const retained = Object.create(null);
  let truncated = false;
  if (!args || args.t !== "object") return { retained, truncated, present: false };
  for (const key of keys) {
    if (!Object.prototype.hasOwnProperty.call(args.map, key)) continue;
    const node = args.map[key];
    if (node.t !== "string") continue;
    if (node.bytes > 512) {
      truncated = true;
      continue;
    }
    retained[key] = node.v;
  }
  return { retained, truncated, present: true };
}

export function upsertPending(session, key, method) {
  const next = cloneSession(session);
  if (!key) return { session: next, overflow: false };
  if (Object.prototype.hasOwnProperty.call(next.pending, key)) {
    next.pending[key] = method;
    return { session: next, overflow: false };
  }
  if (next.pendingCount >= 128) return { session: next, overflow: true };
  next.pending[key] = method;
  next.pendingCount += 1;
  return { session: next, overflow: false };
}

export function takePending(session, key) {
  const next = cloneSession(session);
  if (!key || !Object.prototype.hasOwnProperty.call(next.pending, key)) {
    return { session: next, method: undefined };
  }
  const method = next.pending[key];
  delete next.pending[key];
  next.pendingCount -= 1;
  return { session: next, method };
}

export function rememberTool(bucket, row, hmacName) {
  const key = row.operatorName || `h:${hmacName}`;
  if (Object.keys(bucket).length >= MAX_TOOLS && !Object.prototype.hasOwnProperty.call(bucket, key)) {
    return false;
  }
  bucket[key] = row;
  return true;
}
