/**
 * Operator policy normalization and the allow/deny decision.
 * A mode other than "enforce" is observe. A dropped rule never becomes an allow.
 */

import { MAX_RETAIN_BYTES, MAX_RETAIN_KEYS } from "./bounds.js";
import { pathPrefixMatch } from "./path-prefix.js";
import {
  argumentShape,
  callParts,
  comparePin,
  contentStrings,
  descriptionPin,
  inspectName,
  instructionsText,
  listTools,
  methodLabel,
  propertyNamesFrom,
  readEnvelope,
  rememberTool,
  retainValues,
  samplingTexts,
  schemaPin,
  takePending,
  upsertPending,
} from "./catalog.js";
import { scanText } from "./injection.js";
import { parseJson } from "./parse.js";

const KEY_RE = /^[A-Za-z0-9_.-]{1,64}$/;
const OPS = new Set(["prefix", "suffix", "equals", "enum", "type", "exists", "absent", "len_lte", "len_gte"]);
const TYPES = new Set(["string", "number", "boolean", "object", "array", "null"]);

function blank() {
  return Object.create(null);
}

export function normalizePolicy(raw) {
  const root = raw && typeof raw === "object" ? raw : {};
  const mode = root.mode === "enforce" ? "enforce" : "observe";
  const injection = root.injection === "block" ? "block" : "log";
  const rug_pull = root.rug_pull === "block" ? "block" : "log";
  const servers = blank();
  const source = root.servers && typeof root.servers === "object" ? root.servers : {};
  for (const serverId of Object.keys(source)) {
    servers[serverId] = normalizeServer(source[serverId]);
  }
  return { schema: "vantio.mcp_policy.v1", mode, injection, rug_pull, servers };
}

function normalizeServer(raw) {
  const src = raw && typeof raw === "object" ? raw : {};
  const invalid = [];
  const tools = blank();
  const toolSrc = src.tools && typeof src.tools === "object" ? src.tools : {};
  for (const name of Object.keys(toolSrc)) {
    const row = toolSrc[name] && typeof toolSrc[name] === "object" ? toolSrc[name] : {};
    const tool = {};
    if (row.class === "read" || row.class === "write" || (typeof row.class === "string" && KEY_RE.test(row.class))) {
      tool.class = row.class;
    }
    if (row.effect === "allow" || row.effect === "deny") tool.effect = row.effect;
    else if (row.effect != null) invalid.push({ id: name, reason: "bad_effect" });
    tools[name] = tool;
  }
  const class_defaults = blank();
  const classSrc = src.class_defaults && typeof src.class_defaults === "object" ? src.class_defaults : {};
  for (const name of Object.keys(classSrc)) {
    if (classSrc[name] === "allow" || classSrc[name] === "deny") class_defaults[name] = classSrc[name];
  }
  const rules = [];
  const seenKeys = new Set();
  const ruleSrc = Array.isArray(src.argument_rules) ? src.argument_rules : [];
  for (const rule of ruleSrc) {
    const built = normalizeRule(rule, seenKeys);
    if (built.ok) rules.push(built.rule);
    else invalid.push(built.reason);
  }
  if (seenKeys.size > MAX_RETAIN_KEYS) {
    invalid.push({ reason: "retain_key_cap" });
  }
  const approved = blank();
  const approvedSrc = src.approved && typeof src.approved === "object" ? src.approved : {};
  for (const name of Object.keys(approvedSrc)) {
    const row = approvedSrc[name] && typeof approvedSrc[name] === "object" ? approvedSrc[name] : {};
    approved[name] = {
      description_sha256: hexOrNull(row.description_sha256),
      schema_sha256: hexOrNull(row.schema_sha256),
    };
  }
  let def = "deny";
  if (src.default === "allow" || src.default === "deny") def = src.default;
  return {
    default: def,
    class_defaults,
    tools,
    argument_rules: seenKeys.size > MAX_RETAIN_KEYS ? [] : rules,
    approved,
    approved_instructions_sha256: hexOrNull(src.approved_instructions_sha256),
    invalid_rules: invalid,
    policy_incomplete: invalid.length > 0 || seenKeys.size > MAX_RETAIN_KEYS,
    retain_keys: seenKeys.size > MAX_RETAIN_KEYS ? [] : [...seenKeys],
  };
}

function hexOrNull(value) {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value) ? value : null;
}

function normalizeRule(rule, seenKeys) {
  if (!rule || typeof rule !== "object") return { ok: false, reason: { reason: "rule_missing_tool" } };
  if (typeof rule.tool !== "string" || rule.tool.length === 0) {
    return { ok: false, reason: { id: rule.id, reason: "rule_missing_tool" } };
  }
  if (rule.effect !== "allow" && rule.effect !== "deny") {
    return { ok: false, reason: { id: rule.id, reason: "bad_effect" } };
  }
  if (!OPS.has(rule.op)) return { ok: false, reason: { id: rule.id, reason: "bad_op" } };
  if (rule.op !== "exists" && rule.op !== "absent") {
    if (typeof rule.key !== "string" || !KEY_RE.test(rule.key)) {
      return { ok: false, reason: { id: rule.id, reason: "bad_key" } };
    }
  } else if (rule.key != null && (typeof rule.key !== "string" || !KEY_RE.test(rule.key))) {
    return { ok: false, reason: { id: rule.id, reason: "bad_key" } };
  }
  if (rule.key) seenKeys.add(rule.key);
  let value = rule.value;
  if (rule.op === "enum") {
    if (!Array.isArray(value) || value.length > 16 || value.some((v) => typeof v !== "string" || Buffer.byteLength(v) > MAX_RETAIN_BYTES)) {
      return { ok: false, reason: { id: rule.id, reason: "bad_enum" } };
    }
    value = value.slice();
  } else if (rule.op === "prefix" || rule.op === "suffix" || rule.op === "equals") {
    if (typeof value !== "string" || Buffer.byteLength(value) > MAX_RETAIN_BYTES) {
      return { ok: false, reason: { id: rule.id, reason: "bad_value" } };
    }
  } else if (rule.op === "type") {
    if (!TYPES.has(value)) return { ok: false, reason: { id: rule.id, reason: "bad_type" } };
  } else if (rule.op === "len_lte" || rule.op === "len_gte") {
    if (!Number.isSafeInteger(value) || value < 0) return { ok: false, reason: { id: rule.id, reason: "bad_len" } };
  }
  return {
    ok: true,
    rule: { id: typeof rule.id === "string" ? rule.id : "rule", tool: rule.tool, key: rule.key, op: rule.op, value, effect: rule.effect },
  };
}

function finding(kind) {
  return { kind };
}

function posture(mode, deny, informational) {
  if (mode === "enforce") return deny ? "BLOCK" : informational ? "LOG" : "ALLOW";
  if (deny) return "WOULD_BLOCK";
  if (informational) return "LOG";
  return "ALLOW";
}

/**
 * Decide one parsed envelope. `hmacHex` closes over the process key.
 * The return value has no argument strings, descriptions, or raw string ids.
 */
export function decideEnvelope({ policy, session, direction, envelope, hmacHex }) {
  const mode = policy && policy.mode === "enforce" ? "enforce" : "observe";
  const findings = [];
  let next = session;
  const server = policy && policy.servers ? policy.servers[session.serverId] : undefined;

  if (!envelope || envelope.batch || envelope.malformed) {
    findings.push(finding(envelope && envelope.batch ? "batch_rejected" : "malformed_json"));
    return finish(mode, "GAP", findings, next, envelope, hmacHex, null);
  }
  if (envelope.dups) findings.push(finding("duplicate_key"));
  if (envelope.truncated) findings.push(finding("truncated_shape"));
  if (envelope.idType === "bad") findings.push(finding("bad_id"));

  const labeled = methodLabel(envelope.method);
  const idHmac = envelope.idType === "string" ? hmacHex(envelope.idString) : undefined;
  const pendingKey = envelope.idType === "number" ? `n:${envelope.idNumber}` : idHmac ? `h:${idHmac}` : undefined;

  if (!server) {
    findings.push(finding("server_unlisted"));
    return finish(mode === "enforce" ? "enforce" : "observe", mode === "enforce" ? "BLOCK" : "LOG", findings, next, envelope, hmacHex, {
      labeled,
      idHmac,
      deny: mode === "enforce",
    });
  }

  if (server.policy_incomplete) {
    findings.push(finding("policy_incomplete"));
    return finish(mode, mode === "enforce" ? "BLOCK" : "LOG", findings, next, envelope, hmacHex, { labeled, idHmac });
  }

  if (envelope.kind === "request" && pendingKey && labeled.method) {
    const pending = upsertPending(next, pendingKey, labeled.method);
    next = pending.session;
    if (pending.overflow) findings.push(finding("pending_overflow"));
  }

  let correlated;
  if (envelope.kind === "result" || envelope.kind === "error") {
    const taken = takePending(next, pendingKey);
    next = taken.session;
    correlated = taken.method;
    if (!correlated) findings.push(finding("unmatched_result"));
  }

  if (labeled.method === "notifications/tools/list_changed" && direction === "server_to_client") {
    next = { ...next, stale: true };
    findings.push(finding("stale_catalog"));
  }

  const operatorNames = Object.keys(server.tools);
  const call = labeled.method === "tools/call" ? callParts(envelope.map) : null;
  let nameInfo = null;
  let toolHmac;
  if (call) {
    const rawName = call.nameNode && call.nameNode.t === "string" ? call.nameNode.v : call.nameNode;
    nameInfo = inspectName(rawName, operatorNames);
    for (const kind of nameInfo.findings) findings.push(finding(kind));
    if (typeof rawName === "string") toolHmac = hmacHex(rawName);
    if (nameInfo.operatorExact !== true && typeof rawName === "string") {
      const row = lookupTool(next, rawName, false, toolHmac);
      if (next.sawList && !next.incomplete && !row) findings.push(finding("unadvertised_tool"));
      else if (!row) findings.push(finding("catalog_unknown"));
    }
  }

  if (correlated === "tools/list" && envelope.kind === "result") {
    next = applyList(next, envelope, server, operatorNames, hmacHex, findings, policy);
  } else if (envelope.kind === "result" && listTools(envelope.map) && correlated !== "tools/list") {
    findings.push(finding("unmatched_result"));
  }

  if (correlated === "initialize" && envelope.kind === "result") {
    const text = instructionsText(envelope.map);
    if (typeof text === "string") {
      for (const kind of scanText(text, parseJson)) findings.push(finding(kind));
      const pin = comparePin(descriptionPin(text), server.approved_instructions_sha256);
      if (pin === "mismatch" || pin === "unbounded") findings.push(finding(pin === "unbounded" ? "hash_unbounded" : "server_instructions_changed"));
    }
  }

  if (direction === "server_to_client" && (envelope.kind === "result" || labeled.method === "sampling/createMessage")) {
    const texts =
      labeled.method === "sampling/createMessage" || correlated === "sampling/createMessage"
        ? samplingTexts(envelope.map)
        : contentStrings(envelope.map);
    if (labeled.method === "sampling/createMessage" && direction === "server_to_client") {
      findings.push(finding("server_sampling_request"));
    }
    if (correlated !== "prompts/get") {
      for (const text of texts) {
        for (const kind of scanText(text, parseJson)) findings.push(finding(kind));
      }
    }
  }

  const security = securityDeny(findings, policy, mode, labeled.method, envelope.kind);
  if (security.blocked) {
    return finish(mode, posture(mode, true, false), findings, next, envelope, hmacHex, {
      labeled,
      idHmac,
      nameInfo,
      toolHmac,
      call,
      server,
      reason: security.reason,
    });
  }

  if (labeled.method === "tools/list" && envelope.kind === "request") {
    return finish(mode, findings.length ? "LOG" : "ALLOW", findings, next, envelope, hmacHex, {
      labeled,
      idHmac,
      reason: findings.length ? findings[0].kind : "allow",
    });
  }

  if (labeled.method === "tools/call" && envelope.kind === "request") {
    return decideCall(mode, policy, server, next, envelope, hmacHex, findings, nameInfo, toolHmac, call, labeled, idHmac);
  }

  if (findings.some((f) => f.kind === "unmatched_result")) {
    return finish(mode, mode === "enforce" ? "BLOCK" : findings.length > 1 ? "LOG" : "ALLOW", findings, next, envelope, hmacHex, {
      labeled,
      idHmac,
      reason: "unmatched_result",
    });
  }

  if (envelope.kind === "request" && !PASSTHROUGH_REQUESTS.has(labeled.method)) {
    const deny = server.default !== "allow";
    return finish(mode, posture(mode, deny, findings.length > 0 && !deny), findings, next, envelope, hmacHex, {
      labeled,
      idHmac,
      reason: findings[0] ? findings[0].kind : "default_effect",
    });
  }

  if (findings.length) {
    const deny = findings.some((f) => f.kind === "duplicate_key" || f.kind === "truncated_shape" || f.kind === "hash_unbounded");
    return finish(mode, posture(mode, deny, !deny), findings, next, envelope, hmacHex, {
      labeled,
      idHmac,
      nameInfo,
      toolHmac,
      reason: findings[0].kind,
    });
  }
  return finish(mode, "ALLOW", findings, next, envelope, hmacHex, { labeled, idHmac, reason: "allow" });
}

const PASSTHROUGH_REQUESTS = new Set(["tools/list", "initialize", "ping"]);

function decideCall(mode, policy, server, session, envelope, hmacHex, findings, nameInfo, toolHmac, call, labeled, idHmac) {
  const toolName = nameInfo && nameInfo.operatorExact ? call.nameNode.v : undefined;
  if (session.stale) findings.push(finding("stale_catalog"));
  const row = toolName ? session.tools[toolName] : undefined;
  if (row && (row.descriptionPin === "mismatch" || row.schemaPin === "mismatch")) {
    findings.push(finding(row.descriptionPin === "mismatch" ? "rug_pull_description" : "rug_pull_schema"));
  }
  if (row && (row.descriptionPin === "unbounded" || row.schemaPin === "unbounded")) {
    findings.push(finding("hash_unbounded"));
  }

  const allow = new Set(server.retain_keys);
  if (row && row.schemaPin === "match") for (const name of row.propertyNames) allow.add(name);
  const retained = retainValues(call.args, [...allow]);
  if (retained.truncated) findings.push(finding("retain_truncated"));
  const shape = argumentShape(call.args || { t: "null" }, allow, hmacHex);

  const spoof = findings.some((f) =>
    ["hidden_chars_in_name", "nfkc_mismatch", "mixed_script_name", "confusable_name", "tool_name_type", "duplicate_key", "duplicate_tool_name"].includes(f.kind),
  );
  let effect = server.default;
  let reason = "default_effect";
  const staleOrUnknown = session.stale || findings.some((f) => f.kind === "catalog_unknown" || f.kind === "stale_catalog");
  const rule = !spoof && !retained.truncated && toolName ? firstRule(server, toolName, call.args, retained.retained) : null;
  if (retained.truncated || findings.some((f) => f.kind === "truncated_shape" || f.kind === "hash_unbounded")) {
    effect = "deny";
    reason = retained.truncated ? "retain_truncated" : "truncated_shape";
  } else if (spoof || findings.some((f) => f.kind === "unadvertised_tool")) {
    effect = "deny";
    reason = nameInfo && nameInfo.findings[0] ? nameInfo.findings[0] : "unadvertised_tool";
  } else if (staleOrUnknown && mode === "enforce") {
    effect = "deny";
    reason = session.stale ? "stale_catalog" : "catalog_unknown";
  } else if (rule) {
    effect = rule.effect;
    reason = rule.reject ? "path_rejected" : "argument_rule";
    if (rule.reject) findings.push(finding("path_rejected"));
  } else if (toolName && server.tools[toolName] && server.tools[toolName].effect) {
    effect = server.tools[toolName].effect;
    reason = "tool_effect";
  } else if (toolName && server.tools[toolName] && server.tools[toolName].class && server.class_defaults[server.tools[toolName].class]) {
    effect = server.class_defaults[server.tools[toolName].class];
    reason = "class_effect";
  }

  if (findings.some((f) => f.kind === "rug_pull_description" || f.kind === "rug_pull_schema") && policy.rug_pull === "block") {
    effect = "deny";
    reason = findings.find((f) => f.kind.startsWith("rug_pull")).kind;
  }
  if (findings.some((f) => f.kind === "pending_overflow")) {
    effect = "deny";
    reason = "pending_overflow";
  }

  const deny = effect === "deny";
  return finish(mode, posture(mode, deny, findings.length > 0 && !deny), findings, session, envelope, hmacHex, {
    labeled,
    idHmac,
    nameInfo,
    toolHmac,
    shape,
    reason,
    tool_name: toolName,
  });
}

function firstRule(server, toolName, args, retained) {
  for (const rule of server.argument_rules) {
    if (rule.tool !== toolName) continue;
    const matched = ruleMatches(rule, args, retained);
    if (matched === "reject") return { id: rule.id, effect: "deny", reject: true };
    if (matched === true) return rule;
  }
  return null;
}

function ruleMatches(rule, args, retained) {
  const present = args && args.t === "object" && rule.key && Object.prototype.hasOwnProperty.call(args.map, rule.key);
  if (rule.op === "exists") return present === true;
  if (rule.op === "absent") return present !== true;
  if (!present) return false;
  const node = args.map[rule.key];
  if (rule.op === "type") return nodeType(node) === rule.value;
  if (rule.op === "len_lte" || rule.op === "len_gte") {
    const n = node.t === "string" ? node.bytes : node.t === "array" ? node.total : node.t === "object" ? node.order.length : null;
    if (n == null) return false;
    return rule.op === "len_lte" ? n <= rule.value : n >= rule.value;
  }
  if (node.t !== "string") return false;
  const value = retained[rule.key];
  if (typeof value !== "string") return false;
  if (rule.op === "prefix") {
    const matched = pathPrefixMatch(value, rule.value);
    if (matched === "reject") return "reject";
    return matched === "match";
  }
  if (rule.op === "suffix") return value.endsWith(rule.value);
  if (rule.op === "equals") return value === rule.value;
  if (rule.op === "enum") return rule.value.includes(value);
  return false;
}

function nodeType(node) {
  if (!node) return "null";
  if (node.t === "bool") return "boolean";
  return node.t;
}

const SPOOF_KINDS = [
  "duplicate_key",
  "duplicate_tool_name",
  "hidden_chars_in_name",
  "nfkc_mismatch",
  "mixed_script_name",
  "confusable_name",
  "tool_name_type",
];
const INJECTION_KINDS = [
  "embedded_jsonrpc",
  "embedded_tool_catalog",
  "chat_role_frame",
  "control_token",
  "hidden_unicode_channel",
  "server_sampling_request",
];

function securityDeny(findings, policy, mode, method, kind) {
  const kinds = new Set(findings.map((f) => f.kind));
  const spoof = SPOOF_KINDS.find((item) => kinds.has(item));
  if (spoof) return { blocked: true, reason: spoof };
  if (kinds.has("pending_overflow") && kind === "request") return { blocked: true, reason: "pending_overflow" };
  const injectionHit = INJECTION_KINDS.find((item) => kinds.has(item));
  if (injectionHit && policy.injection === "block") return { blocked: true, reason: injectionHit };
  if (method === "sampling/createMessage" && policy.injection === "block") {
    return { blocked: true, reason: "server_sampling_request" };
  }
  const rug = ["server_instructions_changed", "rug_pull_description", "rug_pull_schema"].find((item) => kinds.has(item));
  if (rug && policy.rug_pull === "block") return { blocked: true, reason: rug };
  if (kinds.has("hash_unbounded") && mode === "enforce") return { blocked: true, reason: "hash_unbounded" };
  return { blocked: false, reason: injectionHit || "" };
}

function applyList(session, envelope, server, operatorNames, hmacHex, findings, policy) {
  const page = listTools(envelope.map);
  const next = {
    ...session,
    tools: copyTools(session.tools),
    draft: copyTools(session.draft),
    pending: copyPending(session.pending),
  };
  if (!page) {
    findings.push(finding("malformed_json"));
    return next;
  }
  let bucket;
  if (page.nextCursor) {
    if (!next.draftOpen) next.draft = Object.create(null);
    bucket = next.draft;
    next.draftOpen = true;
  } else if (next.draftOpen) {
    bucket = next.draft;
  } else {
    bucket = Object.create(null);
  }
  const skeletons = [];
  for (const tool of page.tools) {
    const name = tool.map.name && tool.map.name.t === "string" ? tool.map.name.v : undefined;
    const info = inspectName(name, operatorNames);
    for (const kind of info.findings) findings.push(finding(kind));
    const desc = tool.map.description && tool.map.description.t === "string" ? tool.map.description.v : "";
    for (const kind of scanText(desc, parseJson)) findings.push(finding(kind));
    const dPin = comparePin(
      descriptionPin(desc),
      info.operatorExact ? server.approved[name] && server.approved[name].description_sha256 : null,
    );
    const schema = schemaPin(tool, envelope.truncated);
    const sPin = comparePin(schema, info.operatorExact ? server.approved[name] && server.approved[name].schema_sha256 : null);
    if (dPin === "mismatch") findings.push(finding("rug_pull_description"));
    if (sPin === "mismatch") findings.push(finding("rug_pull_schema"));
    if (dPin === "unbounded" || sPin === "unbounded") findings.push(finding("hash_unbounded"));
    const sk = info.skeleton;
    if (sk && skeletons.includes(sk)) findings.push(finding("duplicate_tool_name"));
    if (sk) skeletons.push(sk);
    const hmacName = typeof name === "string" ? hmacHex(name) : hmacHex("");
    if (page.truncated) findings.push(finding("truncated_shape"));
    const previous = info.operatorExact ? next.tools[name] : undefined;
    const schemaMatched = sPin === "match";
    const names = schemaMatched ? propertyNamesFrom(tool, true) : previous && previous.schemaPin === "match" ? previous.propertyNames : [];
    const stored = rememberTool(
      bucket,
      {
        operatorName: info.operatorExact ? name : null,
        descriptionPin: dPin,
        schemaPin: sPin,
        propertyNames: names,
      },
      hmacName,
    );
    if (!stored) findings.push(finding("truncated_shape"));
  }
  next.sawList = true;
  next.stale = false;
  next.restarted = false;
  if (page.nextCursor) {
    next.incomplete = true;
    findings.push(finding("catalog_incomplete"));
  } else {
    next.tools = copyTools(bucket);
    next.draft = Object.create(null);
    next.draftOpen = false;
    next.incomplete = page.truncated === true;
  }
  return next;
}

function copyTools(tools) {
  const out = Object.create(null);
  for (const key of Object.keys(tools || {})) {
    const row = tools[key];
    out[key] = { ...row, propertyNames: row.propertyNames.slice() };
  }
  return out;
}

function copyPending(pending) {
  const out = Object.create(null);
  for (const key of Object.keys(pending || {})) out[key] = pending[key];
  return out;
}

function lookupTool(session, rawName, operatorExact, toolHmac) {
  if (operatorExact) return session.tools[rawName];
  return session.tools[`h:${toolHmac}`];
}

function finish(mode, action, findings, session, envelope, hmacHex, extra) {
  const info = extra || {};
  const labeled = info.labeled || { method_class: "other" };
  const recordBase = {
    schema: "vantio.mcp_observation.v1",
    direction_action: action,
    findings: dedupe(findings),
    decision: { action, reason: info.reason || (findings[0] && findings[0].kind) || "allow" },
    method_class: labeled.method_class,
    id_type: envelope && envelope.idType ? envelope.idType : "absent",
    retention: { payload: false, values: false },
  };
  if (labeled.method_class === "known") recordBase.method = labeled.method;
  else if (envelope && typeof envelope.method === "string") recordBase.method_hmac = hmacHex(envelope.method);
  if (envelope && envelope.idType === "number") recordBase.id_number = envelope.idNumber;
  if (info.idHmac) recordBase.id_hmac = info.idHmac;
  if (typeof info.tool_name === "string") recordBase.tool_name = info.tool_name;
  if (info.toolHmac && !(info.nameInfo && info.nameInfo.operatorExact)) recordBase.tool_hmac = info.toolHmac;
  if (info.shape) recordBase.argument_shape = info.shape;
  const cleanSession = stripSession(session);
  return { action, reason: recordBase.decision.reason, findings: recordBase.findings, session: cleanSession, partial: recordBase };
}

function dedupe(findings) {
  const seen = new Set();
  const out = [];
  for (const row of findings) {
    if (seen.has(row.kind)) continue;
    seen.add(row.kind);
    out.push({ kind: row.kind });
  }
  return out;
}

function stripSession(session) {
  if (!session) return session;
  const tools = Object.create(null);
  for (const key of Object.keys(session.tools || {})) {
    const row = session.tools[key];
    tools[key] = {
      operatorName: row.operatorName,
      descriptionPin: row.descriptionPin,
      schemaPin: row.schemaPin,
      propertyNames: row.propertyNames.slice(),
    };
  }
  const draft = Object.create(null);
  for (const key of Object.keys(session.draft || {})) {
    const row = session.draft[key];
    draft[key] = {
      operatorName: row.operatorName,
      descriptionPin: row.descriptionPin,
      schemaPin: row.schemaPin,
      propertyNames: row.propertyNames.slice(),
    };
  }
  const pending = Object.create(null);
  for (const key of Object.keys(session.pending || {})) pending[key] = session.pending[key];
  return {
    serverId: session.serverId,
    stale: session.stale === true,
    incomplete: session.incomplete === true,
    sawList: session.sawList === true,
    restarted: session.restarted === true,
    tools,
    draftOpen: session.draftOpen === true,
    draft,
    pending,
    pendingCount: session.pendingCount || 0,
  };
}

export function gapDecision(reason) {
  return {
    action: "GAP",
    reason,
    findings: [{ kind: reason }],
    session: null,
    partial: {
      schema: "vantio.mcp_observation.v1",
      decision: { action: "GAP", reason },
      findings: [{ kind: reason }],
      retention: { payload: false, values: false },
    },
  };
}
