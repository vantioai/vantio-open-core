/**
 * Structural inbound checks. These match fixed shapes and fixed tokens.
 * They do not score the meaning of prose.
 */

import { MAX_NESTED_BYTES, MAX_NESTED_OBJECTS } from "./bounds.js";

const CONTROL_TOKENS = [
  "<|im_start|>",
  "<|im_end|>",
  "<|system|>",
  "<|user|>",
  "<|assistant|>",
  "<<SYS>>",
  "<</SYS>>",
  "[INST]",
  "[/INST]",
  "<system>",
  "</system>",
];

const ROLES = new Set(["system", "developer", "user", "assistant", "tool"]);

const HIDDEN =
  /[\u202A-\u202E\u2066-\u2069\u200B-\u200D\uFEFF]|\u{E0001}|[\u{E0020}-\u{E007F}]/u;

export function hiddenChannel(text) {
  return typeof text === "string" && HIDDEN.test(text);
}

export function controlToken(text) {
  if (typeof text !== "string" || text.length === 0) return false;
  for (const token of CONTROL_TOKENS) {
    if (text.includes(token)) return true;
  }
  return false;
}

function walkObjects(node, visit, budget) {
  if (!node || budget.objects > MAX_NESTED_OBJECTS) return;
  if (node.t === "object") {
    budget.objects += 1;
    visit(node);
    if (budget.objects > MAX_NESTED_OBJECTS) return;
    const keys = node.order || [];
    for (let i = 0; i < keys.length; i += 1) {
      walkObjects(node.map[keys[i]], visit, budget);
      if (budget.objects > MAX_NESTED_OBJECTS) return;
    }
    return;
  }
  if (node.t === "array") {
    const items = node.items || [];
    for (let i = 0; i < items.length; i += 1) {
      walkObjects(items[i], visit, budget);
      if (budget.objects > MAX_NESTED_OBJECTS) return;
    }
  }
}

function objectHas(node, key) {
  return node && node.t === "object" && Object.prototype.hasOwnProperty.call(node.map, key);
}

function stringValue(node) {
  return node && node.t === "string" ? node.v : undefined;
}

function classifyObject(node, findings) {
  if (!node || node.t !== "object") return;
  const rpc = stringValue(node.map.jsonrpc);
  const method = stringValue(node.map.method);
  if (rpc === "2.0" && typeof method === "string") {
    findings.add("embedded_jsonrpc");
  }
  if (objectHas(node, "tools") && node.map.tools && node.map.tools.t === "array") {
    const items = node.map.tools.items || [];
    for (let i = 0; i < items.length; i += 1) {
      const tool = items[i];
      if (
        tool &&
        tool.t === "object" &&
        objectHas(tool, "name") &&
        objectHas(tool, "inputSchema")
      ) {
        findings.add("embedded_tool_catalog");
        break;
      }
    }
  }
  if (objectHas(node, "role") && objectHas(node, "content")) {
    const role = stringValue(node.map.role);
    if (ROLES.has(role)) findings.add("chat_role_frame");
  }
}

/**
 * Scan one content string. `parse` is the bounded JSON parser.
 * Returns a list of finding kinds. Does not return the text.
 */
export function scanText(text, parse) {
  const findings = new Set();
  if (typeof text !== "string" || text.length === 0) return [];
  const slice = text.length > MAX_NESTED_BYTES ? text.slice(0, MAX_NESTED_BYTES) : text;
  if (text.length > MAX_NESTED_BYTES) findings.add("truncated_shape");
  if (hiddenChannel(slice)) findings.add("hidden_unicode_channel");
  if (controlToken(slice)) findings.add("control_token");

  const whole = parse(slice);
  const budget = { objects: 0 };
  if (whole && whole.ok) {
    walkObjects(whole.value, (node) => classifyObject(node, findings), budget);
  } else {
    collectBalanced(slice, parse, findings);
  }
  return [...findings];
}

function collectBalanced(text, parse, findings) {
  let found = 0;
  let i = 0;
  while (i < text.length && found < MAX_NESTED_OBJECTS) {
    const start = text.indexOf("{", i);
    if (start < 0) break;
    const end = balancedEnd(text, start);
    if (end < 0) break;
    const piece = text.slice(start, end + 1);
    if (piece.length <= MAX_NESTED_BYTES) {
      const parsed = parse(piece);
      if (parsed && parsed.ok && parsed.value && parsed.value.t === "object") {
        classifyObject(parsed.value, findings);
        found += 1;
      }
    }
    i = end + 1;
  }
}

function balancedEnd(text, start) {
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < text.length; i += 1) {
    const ch = text[i];
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (ch === "\\") {
        escape = true;
        continue;
      }
      if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') {
      inString = true;
      continue;
    }
    if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
}
