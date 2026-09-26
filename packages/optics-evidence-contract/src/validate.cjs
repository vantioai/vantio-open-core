"use strict";

const { readFileSync } = require("fs");
const path = require("path");
const { canonicalJson } = require("./canonical.cjs");
const { plainCopy, isBound, OVERSIZE, MALFORMED_TEXT, bounds } = require("./walk.cjs");
const privacy = require("./privacy.cjs");

const CONTRACT_DIR = path.join(__dirname, "..", "contract");

function loadContract(name) {
  return JSON.parse(readFileSync(path.join(CONTRACT_DIR, name), "utf8"));
}

const enums = loadContract("enums.json");
const meta = loadContract("contract-metadata.json");

const DISPOSITION_RANK = new Map(enums.disposition_rank.map((name, index) => [name, index]));
const REASON_RANK = new Map(enums.reason_priority.map((name, index) => [name, index]));
const ISSUE_LABELS = enums.issue_location_labels;
const WRITER_ORIGINS = new Set(enums.evidence_origin_writer);
const SESSION_BASIS = new Set(enums.session_id_basis);
const TRACE_BASIS = new Set(enums.trace_id_basis);
const OPTICS_STATUS = new Set(enums.optics_status);
const METHODS = new Set(enums.method);
const SCHEMES = new Set(enums.scheme);
const FAILURES = new Set(enums.failure_kind);
const NETWORK_KINDS = new Set(enums.network_failure_kinds);
const CONFIDENCE = new Set(enums.provider_confidence);
const MEDIATION = new Set(enums.mediation);
const PLATFORMS = new Set(enums.platform);
const ARCHES = new Set(enums.arch);
const LIFECYCLE = new Set(enums.lifecycle);
const CLOCK = new Set(enums.clock_quality);
const CONFLICT = new Set(enums.identity_conflict);
const RUNTIMES = new Set(enums.runtime);
const COVERAGE = new Set(enums.coverage_note);
const PRODUCERS = new Set(meta.recognized_producers);
const HEALTH_NAMES = new Set(enums.product_health_name);
const OUTCOME_LABELS = new Set(enums.application_outcome_label);
const PROVIDER_PHRASES = new Set(enums.provider_response_phrase);
const NEXT_ACTION = new Set(enums.next_action_category);
const ORIGINAL_ORIGIN = new Set(enums.original_evidence_origin);
const APP_STATUS = new Set(enums.application_status);

const INPUT_ONLY = new Set([
  "vantio_trace_id",
  "traceparent",
  "requested_url",
  "requested_destination",
  "url",
  "destination",
  "connected_url",
  "connected_destination",
  "connected_host",
  "proxy",
  "proxy_url",
  "proxy_destination",
  "redirect_url",
  "redirect_destination",
  "coverage_gap",
  "optics_internal_failure",
  "parent_conflict",
  "environment_condition",
  "producer_version",
]);

function createState() {
  return {
    dispositions: new Set(),
    reasons: new Set(),
    completeness: new Set(),
    health: {
      events_rejected: 0,
      redaction_failures: 0,
      rejected_context: 0,
      session_id_rejected: 0,
    },
    accepted: new Set(),
    normalized: new Set(),
    stripped: new Set(),
    rejected: new Set(),
    privacy: false,
    sessionRejected: false,
    contextRejected: false,
    dropRecord: false,
    provenance: "NOT_APPLICABLE",
    destinationClass: null,
    destinationIpClass: null,
    traceMeaning: null,
    opticsInternal: false,
    networkNoHttp: false,
    customerException: false,
    coverageEvidenced: false,
    coverageUnevidenced: false,
    configurationFault: false,
    environmentFault: false,
    httpStatus: null,
    failureIdentified: false,
    readerOrigin: null,
    interrupted: false,
  };
}

function addDisposition(state, disposition) {
  state.dispositions.add(disposition);
}

function addReason(state, reason) {
  state.reasons.add(reason);
}

function markPrivacy(state) {
  if (state.privacy) return;
  state.privacy = true;
  state.completeness.add("REDACTION_DROP");
  state.health.redaction_failures = 1;
  addReason(state, "REDACTION_DROP");
}

function markSession(state) {
  if (state.sessionRejected) return;
  state.sessionRejected = true;
  state.completeness.add("SESSION_ID_REJECTED");
  state.health.session_id_rejected = 1;
  addReason(state, "SESSION_ID_REJECTED");
  addDisposition(state, "REJECT_FIELD");
}

function markContext(state) {
  if (state.contextRejected) return;
  state.contextRejected = true;
  state.completeness.add("CONTEXT_REJECTED");
  state.health.rejected_context = 1;
  addReason(state, "CONTEXT_REJECTED");
  addDisposition(state, "REJECT_FIELD");
}

function dropRecord(state, reason) {
  if (!state.dropRecord) {
    state.dropRecord = true;
    state.completeness.add("EVENT_DROPPED");
    state.health.events_rejected = 1;
  }
  addReason(state, reason);
  addDisposition(state, "REJECT_RECORD");
  state.opticsInternal = true;
}

function put(state, record, name, value, kind) {
  record[name] = value;
  if (kind === "accepted") {
    state.normalized.delete(name);
    state.accepted.add(name);
    addDisposition(state, "ACCEPT");
  } else {
    state.accepted.delete(name);
    state.normalized.add(name);
    addDisposition(state, "NORMALIZE");
    addReason(state, "NORMALIZED");
  }
}

function rejectField(state, name) {
  state.rejected.add(name);
  addDisposition(state, "REJECT_FIELD");
}

function stripKey(state, name) {
  state.stripped.add(name);
  addDisposition(state, "STRIP");
  addReason(state, "UNKNOWN_FIELD_OMITTED");
}

function highest(map, values, fallback) {
  let best = fallback;
  let rank = map.has(fallback) ? map.get(fallback) : -1;
  for (const value of values) {
    const next = map.has(value) ? map.get(value) : -1;
    if (next > rank) {
      rank = next;
      best = value;
    }
  }
  return best;
}

function sorted(set) {
  return Array.from(set).sort();
}

function completenessList(state) {
  const out = [];
  for (const token of enums.completeness_tokens) {
    if (state.completeness.has(token)) out.push(token);
  }
  return out.length ? out : ["NONE"];
}

function healthLabel(health) {
  if (health.redaction_failures > 0) return "INTERNAL_PRIVACY_FAILURE";
  if (health.events_rejected > 0) return "EVENT_REJECTED";
  if (health.session_id_rejected > 0) return "SESSION_REJECTED";
  if (health.rejected_context > 0) return "CONTEXT_REJECTED";
  return "NONE";
}

function issueLocation(state) {
  if (state.opticsInternal) return "OPTICS";
  if (state.networkNoHttp) return "NETWORK";
  if (state.httpStatus != null && state.httpStatus >= 400 && state.httpStatus <= 599) {
    return "PROVIDER_INTERACTION";
  }
  if (state.customerException && state.httpStatus == null) return "CUSTOMER_APPLICATION";
  if (state.coverageEvidenced) return "COVERAGE";
  if (state.coverageUnevidenced) return "UNKNOWN";
  if (state.configurationFault) return "CONFIGURATION";
  if (state.environmentFault) return "ENVIRONMENT";
  if (state.httpStatus != null && state.httpStatus >= 200 && state.httpStatus < 400) return "NONE";
  if (state.httpStatus != null && (state.httpStatus < 200 || state.httpStatus > 599)) return "UNKNOWN";
  if (state.failureIdentified) return "UNKNOWN";
  return "NONE";
}

function applicationStatusFromHttp(status) {
  if (status == null) return "UNAVAILABLE";
  if (status >= 200 && status < 400) return "SUCCESS";
  if (status >= 400 && status <= 599) return "APPLICATION_ERROR";
  return "UNAVAILABLE";
}

function codePoints(text) {
  return Array.from(text);
}

function isInteger(value) {
  return typeof value === "number" && Number.isInteger(value) && Math.abs(value) <= bounds.safe_integer_max;
}

function nonNegativeInt(value) {
  if (!isInteger(value) || value < 0) return null;
  return value;
}

function versionToken(value, max) {
  if (typeof value !== "string") return null;
  if (value.length < 1 || value.length > max) return null;
  if (!/^[A-Za-z0-9._+-]+$/.test(value)) return null;
  if (privacy.containsProhibited(value)) return { prohibited: true };
  return value;
}

function idToken(value, max) {
  if (typeof value !== "string") return null;
  if (value.length < 1 || value.length > max) return null;
  if (!/^[A-Za-z0-9_-]+$/.test(value)) return null;
  if (privacy.containsProhibited(value)) return { prohibited: true };
  return value;
}

function isLeap(year) {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function canonicalTime(value) {
  if (typeof value !== "string") return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.(\d{1,6}))?(Z|\+00:00|-00:00)$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  if (month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) return null;
  const days = [0, 31, isLeap(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (day < 1 || day > days[month]) return null;
  const fraction = (match[8] || "").padEnd(3, "0").slice(0, 3);
  const out = match[1] + "-" + match[2] + "-" + match[3] + "T"
    + match[4] + ":" + match[5] + ":" + match[6] + "." + fraction + "Z";
  return { value: out, changed: out !== value };
}

function hasControl(text) {
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (code <= 0x1f || code === 0x7f || code === 0x2028 || code === 0x2029) return true;
  }
  return false;
}

function isNoncharacter(code) {
  if (code >= 0xfdd0 && code <= 0xfdef) return true;
  return (code & 0xfffe) === 0xfffe;
}

function utf8Bytes(text) {
  return Buffer.byteLength(text, "utf8");
}

function hexNormalize(value, width) {
  if (typeof value !== "string") return null;
  if (width && value.length === width && /^[0-9a-fA-F]+$/.test(value)) {
    if (/^0+$/.test(value)) return null;
    const lower = value.toLowerCase();
    return { value: lower, changed: lower !== value };
  }
  return null;
}

function traceNormalize(value) {
  if (typeof value !== "string" || isBound(value)) return null;
  if (codePoints(value).length > bounds.trace_id_max_chars) return null;
  if (privacy.containsProhibited(value)) return { prohibited: true };
  const w3c = hexNormalize(value, 32);
  if (w3c) return w3c;
  if (/^0x[0-9a-fA-F]{1,126}$/.test(value) && value.length <= bounds.trace_id_max_chars) {
    const lower = "0x" + value.slice(2).toLowerCase();
    if (/^0x0+$/.test(lower)) return null;
    return { value: lower, changed: lower !== value };
  }
  return null;
}

function spanNormalize(value) {
  if (typeof value !== "string" || isBound(value)) return null;
  if (value.length > bounds.span_id_max_chars) return null;
  if (privacy.containsProhibited(value)) return { prohibited: true };
  const w3c = hexNormalize(value, 16);
  if (w3c && value.length <= bounds.span_id_max_chars) return w3c;
  if (/^0x[0-9a-fA-F]+$/.test(value) && value.length <= bounds.span_id_max_chars && value.length >= 3) {
    const lower = "0x" + value.slice(2).toLowerCase();
    if (/^0x0+$/.test(lower)) return null;
    return { value: lower, changed: lower !== value };
  }
  return null;
}

function parseTraceparent(value) {
  if (typeof value !== "string") return null;
  const match = /^00-([0-9a-fA-F]{32})-([0-9a-fA-F]{16})-[0-9a-fA-F]{2}$/.exec(value);
  if (!match) return null;
  const trace = traceNormalize(match[1]);
  const span = spanNormalize(match[2]);
  if (!trace || trace.prohibited || !span || span.prohibited) return null;
  return { trace: trace.value, span: span.value };
}

function isIpv4(text) {
  const parts = text.split(".");
  if (parts.length !== 4) return false;
  for (const part of parts) {
    if (!/^[0-9]{1,3}$/.test(part)) return false;
    if (part.length > 1 && part.startsWith("0")) return false;
    const n = Number(part);
    if (n > 255) return false;
  }
  return true;
}

function isIpv6(text) {
  if (text.includes("%")) return false;
  if (!/^[0-9a-fA-F:]+$/.test(text)) return false;
  if ((text.match(/::/g) || []).length > 1) return false;
  const halves = text.split("::");
  const check = (side) => {
    if (side === "") return true;
    const groups = side.split(":");
    if (groups.some((group) => group.length < 1 || group.length > 4)) return false;
    return true;
  };
  if (halves.length === 1) {
    const groups = text.split(":");
    return groups.length === 8 && check(text);
  }
  if (halves.length !== 2) return false;
  if (!check(halves[0]) || !check(halves[1])) return false;
  const left = halves[0] === "" ? 0 : halves[0].split(":").length;
  const right = halves[1] === "" ? 0 : halves[1].split(":").length;
  return left + right < 8;
}

function normalizeHost(value) {
  if (typeof value !== "string" || isBound(value)) return { ok: false, prohibited: isBound(value) };
  if (value.length < 1 || value.length > bounds.host_max_chars) return { ok: false, prohibited: value.length > bounds.host_max_chars };
  if (hasControl(value) || value.includes("/") || value.includes("?") || value.includes("#") || value.includes("@")) {
    return { ok: false, prohibited: privacy.containsProhibited(value) || true };
  }
  if (privacy.containsProhibited(value) || privacy.hasUsernamePath(value) || privacy.hasDbScheme(value)) {
    return { ok: false, prohibited: true };
  }
  if (value.startsWith("[") && value.endsWith("]")) {
    const inner = value.slice(1, -1);
    if (!isIpv6(inner)) return { ok: false, prohibited: false };
    return { ok: true, value: inner.toLowerCase(), ipClass: "ipv6", changed: true };
  }
  if (isIpv4(value)) return { ok: true, value, ipClass: "ipv4", changed: false };
  if (value.includes(":")) {
    if (!isIpv6(value)) return { ok: false, prohibited: false };
    const lower = value.toLowerCase();
    return { ok: true, value: lower, ipClass: "ipv6", changed: lower !== value };
  }
  const lower = value.toLowerCase();
  if (!/^[a-z0-9.-]+$/.test(lower)) return { ok: false, prohibited: false };
  if (lower.startsWith(".") || lower.endsWith(".") || lower.includes("..")) return { ok: false, prohibited: false };
  const labels = lower.split(".");
  if (labels.some((label) => label.length < 1 || label.length > bounds.label_max_chars)) {
    return { ok: false, prohibited: false };
  }
  return { ok: true, value: lower, ipClass: "dns", changed: lower !== value };
}

function normalizePath(value) {
  if (typeof value !== "string" || isBound(value)) {
    return { ok: false, oversize: isBound(value) && value.__optics_bound === OVERSIZE, prohibited: true };
  }
  if (codePoints(value).length > bounds.path_max_chars) {
    return { ok: false, oversize: true, prohibited: privacy.containsProhibited(value) };
  }
  if (hasControl(value) || value.includes("\\") || privacy.hasUsernamePath(value)) {
    return { ok: false, prohibited: true };
  }
  if (value.includes("://")) return { ok: false, prohibited: true };
  let path = value;
  let stripped = false;
  if (path.includes("#") || path.includes("?")) {
    path = path.split("#")[0].split("?")[0];
    stripped = true;
  }
  if (path.length === 0) return { ok: false, prohibited: privacy.containsProhibited(value) };
  if (privacy.containsProhibited(value) || privacy.containsProhibited(path)) {
    return { ok: false, prohibited: true };
  }
  return { ok: true, value: path, changed: stripped || path !== value };
}

function contentType(value) {
  if (typeof value !== "string" || isBound(value)) return { ok: false, prohibited: true };
  const base = value.split(";")[0].trim().toLowerCase();
  if (base.length < 3 || base.length > bounds.content_type_max_chars) return { ok: false, prohibited: privacy.containsProhibited(value) };
  if (!/^[a-z0-9][a-z0-9!#$&^_.+-]*\/[a-z0-9][a-z0-9!#$&^_.+-]*$/.test(base)) {
    return { ok: false, prohibited: privacy.containsProhibited(value) };
  }
  if (privacy.containsProhibited(base) || privacy.containsProhibited(value)) return { ok: false, prohibited: true };
  return { ok: true, value: base, changed: base !== value };
}

function httpStatus(value) {
  if (typeof value === "boolean" || !isInteger(value)) return null;
  if (value < 100 || value > 599) return null;
  return value;
}

function portNumber(value) {
  if (typeof value === "boolean") return null;
  if (typeof value === "string" && /^[0-9]{1,5}$/.test(value)) {
    const n = Number(value);
    if (n >= 1 && n <= 65535) return { value: n, changed: true };
    return null;
  }
  if (!isInteger(value) || value < 1 || value > 65535) return null;
  return { value, changed: false };
}

function parseAuthority(authority) {
  let hostText = authority;
  let port = null;
  if (authority.startsWith("[")) {
    const end = authority.indexOf("]");
    if (end === -1) return { ok: false };
    hostText = authority.slice(1, end);
    const rest = authority.slice(end + 1);
    if (rest.startsWith(":")) {
      const parsed = portNumber(rest.slice(1));
      if (!parsed || parsed.changed === false && String(parsed.value) !== rest.slice(1) && rest.slice(1) !== String(parsed.value)) {
        if (!parsed) return { ok: false };
      }
      if (!parsed) return { ok: false };
      port = parsed.value;
    } else if (rest.length !== 0) return { ok: false };
    const host = normalizeHost(hostText);
    if (!host.ok) return { ok: false, prohibited: host.prohibited };
    return { ok: true, host: host.value, ipClass: host.ipClass, port, hostChanged: true };
  }
  const colon = authority.lastIndexOf(":");
  if (colon !== -1 && authority.indexOf(":") === colon) {
    hostText = authority.slice(0, colon);
    const parsed = portNumber(authority.slice(colon + 1));
    if (!parsed) return { ok: false };
    port = parsed.value;
  }
  const host = normalizeHost(hostText);
  if (!host.ok) return { ok: false, prohibited: host.prohibited };
  return { ok: true, host: host.value, ipClass: host.ipClass, port, hostChanged: host.changed };
}

function parseDestination(raw, state) {
  if (typeof raw !== "string" || isBound(raw)) {
    return { ok: false, failClosed: true, privacy: true };
  }
  if (raw.length > bounds.destination_raw_max_chars || hasControl(raw)) {
    return { ok: false, failClosed: true, privacy: true };
  }
  if (privacy.hasDbScheme(raw)) return { ok: false, failClosed: true, privacy: true };
  let body = raw;
  const hash = body.indexOf("#");
  if (hash !== -1) {
    const fragment = body.slice(hash + 1);
    body = body.slice(0, hash);
    if (fragment && privacy.containsProhibited(fragment)) markPrivacy(state);
    addDisposition(state, "NORMALIZE");
  }
  const q = body.indexOf("?");
  if (q !== -1) {
    const query = body.slice(q + 1);
    body = body.slice(0, q);
    addDisposition(state, "STRIP");
    if (privacy.hasSensitiveQuery(raw) || privacy.containsProhibited(query)) markPrivacy(state);
    else addReason(state, "QUERY_STRIPPED");
  }
  const schemeMatch = /^([A-Za-z][A-Za-z0-9+.-]*):\/\//.exec(body);
  if (!schemeMatch) return { ok: false, failClosed: true, privacy: privacy.containsProhibited(raw) };
  const scheme = schemeMatch[1].toLowerCase();
  if (privacy.policy.db_schemes.includes(scheme)) return { ok: false, failClosed: true, privacy: true };
  if (!SCHEMES.has(scheme) || scheme === "unknown") {
    return { ok: false, failClosed: true, privacy: privacy.containsProhibited(raw) };
  }
  let rest = body.slice(schemeMatch[0].length);
  const slash = rest.indexOf("/");
  const authority = slash === -1 ? rest : rest.slice(0, slash);
  let path = slash === -1 ? null : rest.slice(slash);
  if (authority.includes("@")) {
    const at = authority.lastIndexOf("@");
    const userinfo = authority.slice(0, at);
    const hostport = authority.slice(at + 1);
    if (!userinfo || !hostport || hostport.includes("@")) {
      return { ok: false, failClosed: true, privacy: true };
    }
    addDisposition(state, "STRIP");
    markPrivacy(state);
    addReason(state, "USERINFO_STRIPPED");
    const parsed = parseAuthority(hostport);
    if (!parsed.ok) return { ok: false, failClosed: true, privacy: true };
    if (path) {
      const normalized = normalizePath(path);
      if (!normalized.ok) return { ok: false, failClosed: true, privacy: true };
      path = normalized.value;
    }
    return { ok: true, scheme, host: parsed.host, port: parsed.port, path, ipClass: parsed.ipClass };
  }
  const parsed = parseAuthority(authority);
  if (!parsed.ok) return { ok: false, failClosed: true, privacy: Boolean(parsed.prohibited) || privacy.containsProhibited(raw) };
  if (path) {
    const normalized = normalizePath(path);
    if (!normalized.ok) return { ok: false, failClosed: true, privacy: true };
    path = normalized.value;
  }
  return { ok: true, scheme, host: parsed.host, port: parsed.port, path, ipClass: parsed.ipClass };
}

function stringSecret(value) {
  if (isBound(value)) return true;
  return typeof value === "string" && privacy.containsProhibited(value);
}

function consumeStringField(value) {
  if (isBound(value)) return { prohibited: true, malformed: value.__optics_bound === MALFORMED_TEXT };
  if (typeof value !== "string") return { bad: true };
  if (privacy.containsProhibited(value)) return { prohibited: true };
  return { value };
}

function checkSession(value, basis, producerOk) {
  if (isBound(value)) {
    return { omit: true, session: true, privacy: value.__optics_bound !== MALFORMED_TEXT, malformed: value.__optics_bound === MALFORMED_TEXT };
  }
  if (typeof value !== "string" || typeof basis !== "string") return { omit: true, session: true };
  if (!SESSION_BASIS.has(basis)) return { omit: true, session: true };
  if (basis === "OPTICS_GENERATED" && !producerOk) return { omit: true, session: true };
  if (value.normalize("NFC") !== value) return { omit: true, session: true };
  if (utf8Bytes(value) > bounds.session_id_max_bytes) return { omit: true, session: true, privacy: privacy.containsProhibited(value) };
  if (value.startsWith(" ") || value.endsWith(" ")) return { omit: true, session: true };
  if (value.includes("/") || value.includes("\\") || value.includes("@")) return { omit: true, session: true, privacy: privacy.containsProhibited(value) };
  for (const ch of value) {
    const code = ch.codePointAt(0);
    if (code <= 0x1f || code === 0x7f || isNoncharacter(code)) return { omit: true, session: true };
  }
  if (privacy.containsProhibited(value)) return { omit: true, session: true, privacy: true };
  return { ok: true, value, basis };
}

function eventIdFor(producerId, sequence) {
  const len = utf8Bytes(producerId);
  return "e." + String(len) + "." + producerId + "." + String(sequence);
}

function recognizedProducer(producer, version, origin) {
  if (!PRODUCERS.has(producer)) return false;
  if (typeof version !== "string" || !/^[A-Za-z0-9._+-]{1,32}$/.test(version)) return false;
  if (!WRITER_ORIGINS.has(origin)) return false;
  return true;
}

function applyOrigin(state, record, requestedOrigin, producer, version, demoHost) {
  if (demoHost) {
    put(state, record, "evidence_origin", "SIMULATED_DEMO", requestedOrigin === "SIMULATED_DEMO" ? "accepted" : "normalized");
    state.readerOrigin = "SIMULATED_DEMO";
    addReason(state, "SIMULATED_DEMO");
    addDisposition(state, "REPLACE_WITH_SAFE_CATEGORY");
    state.provenance = producer === "demo_command" ? "SUFFICIENT" : "INSUFFICIENT";
    return;
  }
  const sufficient = recognizedProducer(producer, version, requestedOrigin);
  if (producer === "demo_command" && requestedOrigin === "LOCAL_OBSERVATION") {
    state.readerOrigin = "LEGACY_UNMARKED";
    state.provenance = "INSUFFICIENT";
    addReason(state, "LEGACY_UNMARKED");
    addDisposition(state, "REPLACE_WITH_SAFE_CATEGORY");
    return;
  }
  if (requestedOrigin && WRITER_ORIGINS.has(requestedOrigin) && sufficient) {
    put(state, record, "evidence_origin", requestedOrigin, "accepted");
    state.readerOrigin = requestedOrigin;
    state.provenance = "SUFFICIENT";
    return;
  }
  if (requestedOrigin === "LOCAL_OBSERVATION" || !requestedOrigin) {
    state.readerOrigin = "LEGACY_UNMARKED";
    state.provenance = "INSUFFICIENT";
    addReason(state, requestedOrigin ? "PROVENANCE_INSUFFICIENT" : "LEGACY_UNMARKED");
    addDisposition(state, "REPLACE_WITH_SAFE_CATEGORY");
    return;
  }
  if (WRITER_ORIGINS.has(requestedOrigin)) {
    state.readerOrigin = "LEGACY_UNMARKED";
    state.provenance = "INSUFFICIENT";
    addReason(state, "PROVENANCE_INSUFFICIENT");
    addDisposition(state, "REPLACE_WITH_SAFE_CATEGORY");
    return;
  }
  state.readerOrigin = "LEGACY_UNMARKED";
  state.provenance = "INSUFFICIENT";
  addReason(state, "LEGACY_UNMARKED");
  addDisposition(state, "REPLACE_WITH_SAFE_CATEGORY");
}

function take(input, seen, key) {
  if (Object.prototype.hasOwnProperty.call(input, key)) {
    seen.add(key);
    return { present: true, value: input[key] };
  }
  return { present: false, value: undefined };
}

function treeHasSecret(value, depth) {
  if (depth > 8) return true;
  if (typeof value === "string") return privacy.containsProhibited(value);
  if (isBound(value)) return true;
  if (Array.isArray(value)) return value.some((item) => treeHasSecret(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.keys(value).some((key) => {
      if (privacy.isPayloadName(key)) return true;
      if (privacy.isBaggageName(key)) return true;
      if (privacy.isProhibitedName(key) && !STRUCTURAL_EXCLUSIONS.has(privacy.normalizeName(key))) return true;
      return treeHasSecret(value[key], depth + 1);
    });
  }
  return false;
}

const STRUCTURAL_EXCLUSIONS = new Set([
  "workflow",
  "plane",
  "freemode",
  "estspendusd",
  "usage",
  "tokencount",
  "prompttokens",
  "completiontokens",
  "totaltokens",
  "cost",
  "costusd",
  "residual",
  "datanote",
  "statuslabels",
]);

function sweepLeftovers(input, seen, state) {
  const keys = Object.keys(input).sort();
  for (const key of keys) {
    if (seen.has(key)) continue;
    const value = input[key];
    const secret = stringSecret(value) || treeHasSecret(value, 0);
    if (privacy.isPayloadName(key)) {
      stripKey(state, key);
      markPrivacy(state);
      dropRecord(state, "PROMPT_COMPLETION_EXCLUDED");
      continue;
    }
    if (privacy.isBaggageName(key)) {
      stripKey(state, key);
      addReason(state, "BAGGAGE_OMITTED");
      if (secret) markPrivacy(state);
      continue;
    }
    stripKey(state, key);
    const structural = STRUCTURAL_EXCLUSIONS.has(privacy.normalizeName(key));
    if (secret || (privacy.isProhibitedName(key) && !structural)) markPrivacy(state);
  }
}

function assignDestination(state, record, parts, kind) {
  if (!parts) return;
  const hostKind = kind === "accepted" && !parts.hostChanged ? "accepted" : "normalized";
  put(state, record, "destination_host", parts.host, hostKind);
  if (parts.port == null) put(state, record, "destination_port", null, "normalized");
  else put(state, record, "destination_port", parts.port, parts.portChanged ? "normalized" : "accepted");
  put(state, record, "scheme", parts.scheme, "normalized");
  if (parts.path) put(state, record, "path", parts.path, "normalized");
  state.destinationIpClass = parts.ipClass || null;
}

function collectDestination(input, seen, state) {
  const proxyKeys = ["proxy", "proxy_url", "proxy_destination"];
  const redirectKeys = ["redirect_url", "redirect_destination"];
  const connectedKeys = ["connected_host", "connected_url", "connected_destination"];
  const requestedKeys = ["requested_url", "requested_destination", "url", "destination"];
  let proxy = false;
  let redirect = false;
  for (const key of proxyKeys) {
    const item = take(input, seen, key);
    if (!item.present) continue;
    proxy = true;
    stripKey(state, key);
    if (stringSecret(item.value)) markPrivacy(state);
  }
  for (const key of redirectKeys) {
    const item = take(input, seen, key);
    if (!item.present) continue;
    redirect = true;
    stripKey(state, key);
    if (stringSecret(item.value)) markPrivacy(state);
  }
  const explicit = take(input, seen, "destination_host");
  const explicitPort = take(input, seen, "destination_port");
  const explicitScheme = take(input, seen, "scheme");
  const explicitPath = take(input, seen, "path");
  let connected = null;
  let connectedFrom = null;
  for (const key of connectedKeys) {
    const item = take(input, seen, key);
    if (!item.present) continue;
    stripKey(state, key);
    if (!connectedFrom) connectedFrom = item;
  }
  let requested = null;
  for (const key of requestedKeys) {
    const item = take(input, seen, key);
    if (!item.present) continue;
    stripKey(state, key);
    if (!requested) requested = item;
  }
  if (proxy) state.destinationClass = "PROXY_OMITTED";
  else if (redirect && !explicit.present && !connectedFrom) state.destinationClass = "REDIRECT_OMITTED";

  const parsed = [];
  if (connectedFrom) {
    if (typeof connectedFrom.value === "string" && connectedFrom.value.includes("://")) {
      const got = parseDestination(connectedFrom.value, state);
      if (!got.ok) return { fail: true, privacy: got.privacy };
      parsed.push({ source: "connected", ...got });
    } else {
      const host = normalizeHost(connectedFrom.value);
      if (!host.ok) return { fail: true, privacy: host.prohibited };
      parsed.push({ source: "connected", ok: true, host: host.value, ipClass: host.ipClass, port: null, scheme: null, path: null, hostChanged: host.changed });
    }
  }
  if (requested) {
    const got = parseDestination(requested.value, state);
    if (!got.ok) return { fail: true, privacy: got.privacy };
    parsed.push({ source: "requested", ...got });
  }
  let chosen = null;
  if (explicit.present) {
    const host = normalizeHost(explicit.value);
    if (!host.ok) return { fail: true, privacy: host.prohibited };
    chosen = { host: host.value, ipClass: host.ipClass, hostChanged: host.changed, scheme: null, port: null, path: null, source: "explicit" };
    if (!state.destinationClass) state.destinationClass = "EXPLICIT";
  } else if (parsed.length) {
    chosen = parsed[0];
    if (!state.destinationClass) {
      state.destinationClass = chosen.source === "connected" ? "CONNECTED" : "REQUESTED_URL";
    }
  }
  for (const item of parsed) {
    if (chosen && item.host !== chosen.host) {
      state.configurationFault = true;
      addReason(state, "DESTINATION_CONFLICT");
      addDisposition(state, "REJECT_FIELD");
      rejectField(state, "destination_host");
      return { conflict: true };
    }
    if (chosen && item.host === chosen.host) {
      if (chosen.port == null && item.port != null) chosen.port = item.port;
      if (!chosen.scheme && item.scheme) chosen.scheme = item.scheme;
      if (!chosen.path && item.path) chosen.path = item.path;
      if (!chosen.ipClass && item.ipClass) chosen.ipClass = item.ipClass;
    }
  }
  if (!chosen) return { empty: true, explicitPort, explicitScheme, explicitPath };
  if (explicitPort.present && explicitPort.value == null) {
    if (chosen.port == null) chosen.portNullAccepted = true;
  } else if (explicitPort.present) {
    const parsedPort = portNumber(explicitPort.value);
    if (!parsedPort) {
      rejectField(state, "destination_port");
      if (stringSecret(explicitPort.value)) markPrivacy(state);
    } else if (chosen.port != null && chosen.port !== parsedPort.value) {
      state.configurationFault = true;
      addReason(state, "DESTINATION_CONFLICT");
      addDisposition(state, "REJECT_FIELD");
      rejectField(state, "destination_host");
      return { conflict: true };
    } else {
      chosen.port = parsedPort.value;
      chosen.portChanged = parsedPort.changed;
    }
  }
  if (explicitScheme.present) {
    const scheme = typeof explicitScheme.value === "string" ? explicitScheme.value.toLowerCase() : "";
    if (!SCHEMES.has(scheme) || scheme === "unknown" && explicitScheme.value !== "unknown") {
      if (scheme !== "unknown") {
        rejectField(state, "scheme");
        if (stringSecret(explicitScheme.value)) markPrivacy(state);
      }
    }
    if (SCHEMES.has(scheme)) {
      if (chosen.scheme && chosen.scheme !== scheme) {
        state.configurationFault = true;
        addReason(state, "DESTINATION_CONFLICT");
        rejectField(state, "scheme");
        return { conflict: true };
      }
      chosen.scheme = scheme;
      chosen.schemeChanged = scheme !== explicitScheme.value;
    }
  }
  if (!chosen.scheme) chosen.scheme = "unknown";
  if (explicitPath.present) {
    const pathValue = normalizePath(explicitPath.value);
    if (!pathValue.ok) {
      rejectField(state, "path");
      if (pathValue.oversize) addReason(state, "PATH_OVERSIZE");
      if (pathValue.prohibited) markPrivacy(state);
    } else if (chosen.path && chosen.path !== pathValue.value) {
      state.configurationFault = true;
      addReason(state, "DESTINATION_CONFLICT");
      rejectField(state, "path");
      return { conflict: true };
    } else {
      chosen.path = pathValue.value;
      chosen.pathChanged = pathValue.changed;
    }
  }
  return { chosen };
}

function storeDestination(state, record, collected) {
  if (!collected || collected.fail) {
    if (collected && collected.privacy) markPrivacy(state);
    addReason(state, "DESTINATION_UNSAFE");
    addDisposition(state, "REJECT_FIELD");
    rejectField(state, "destination_host");
    rejectField(state, "destination_port");
    rejectField(state, "scheme");
    rejectField(state, "path");
    return;
  }
  if (collected.conflict || collected.empty) return;
  const chosen = collected.chosen;
  put(state, record, "destination_host", chosen.host, chosen.hostChanged ? "normalized" : "accepted");
  if (chosen.port == null) {
    if (chosen.portNullAccepted) put(state, record, "destination_port", null, "accepted");
  } else put(state, record, "destination_port", chosen.port, chosen.portChanged ? "normalized" : "accepted");
  put(state, record, "scheme", chosen.scheme, chosen.schemeChanged ? "normalized" : "accepted");
  if (chosen.path) put(state, record, "path", chosen.path, chosen.pathChanged ? "normalized" : "accepted");
  state.destinationIpClass = chosen.ipClass || null;
}

function commonIdentity(input, seen, state, record, kind) {
  const producer = take(input, seen, "producer");
  const version = take(input, seen, "cli_or_sdk_version");
  const producerVersion = take(input, seen, "producer_version");
  let versionValue = null;
  if (version.present) {
    const token = versionToken(version.value, 32);
    if (token && token.prohibited) {
      rejectField(state, "cli_or_sdk_version");
      markPrivacy(state);
    } else if (typeof token === "string") {
      versionValue = token;
      put(state, record, "cli_or_sdk_version", token, "accepted");
    } else if (version.value != null) rejectField(state, "cli_or_sdk_version");
  } else if (producerVersion.present) {
    stripKey(state, "producer_version");
    const token = versionToken(producerVersion.value, 32);
    if (typeof token === "string") {
      versionValue = token;
      put(state, record, "cli_or_sdk_version", token, "normalized");
    }
  }
  let producerValue = null;
  if (producer.present && PRODUCERS.has(producer.value)) {
    producerValue = producer.value;
    put(state, record, "producer", producer.value, "accepted");
  } else if (producer.present) {
    rejectField(state, "producer");
    if (stringSecret(producer.value)) markPrivacy(state);
  }

  const runId = take(input, seen, "run_id");
  if (runId.present && runId.value != null) {
    const token = idToken(runId.value, 80);
    if (token && token.prohibited) {
      rejectField(state, "run_id");
      markPrivacy(state);
    } else if (typeof token === "string") put(state, record, "run_id", token, "accepted");
    else rejectField(state, "run_id");
  }
  const parent = take(input, seen, "parent_run_id");
  if (parent.present) {
    if (parent.value == null) put(state, record, "parent_run_id", null, "accepted");
    else {
      const token = idToken(parent.value, 80);
      if (typeof token === "string") put(state, record, "parent_run_id", token, "accepted");
      else {
        rejectField(state, "parent_run_id");
        if (token && token.prohibited) markPrivacy(state);
      }
    }
  }
  const producerId = take(input, seen, "producer_id");
  let producerIdValue = null;
  if (producerId.present && producerId.value != null) {
    const token = idToken(producerId.value, 80);
    if (typeof token === "string") {
      if (record.run_id && token === record.run_id) {
        state.configurationFault = false;
        put(state, record, "producer_id", token, "accepted");
        put(state, record, "identity_conflict", "PRODUCER_SEQUENCE", "normalized");
        producerIdValue = token;
      } else {
        producerIdValue = token;
        put(state, record, "producer_id", token, "accepted");
      }
    } else {
      rejectField(state, "producer_id");
      if (token && token.prohibited) markPrivacy(state);
    }
  }
  const sequence = take(input, seen, "producer_sequence");
  let sequenceValue = null;
  if (sequence.present && sequence.value != null) {
    const n = nonNegativeInt(sequence.value);
    if (n == null) rejectField(state, "producer_sequence");
    else {
      sequenceValue = n;
      put(state, record, "producer_sequence", n, "accepted");
    }
  }
  if (kind === "observation") {
    const seq = take(input, seen, "sequence");
    if (sequenceValue != null) {
      if (!seq.present || seq.value !== sequenceValue) {
        put(state, record, "sequence", sequenceValue, "normalized");
        if (seq.present && seq.value !== sequenceValue) {
          put(state, record, "identity_conflict", "PRODUCER_SEQUENCE", "normalized");
        }
      } else put(state, record, "sequence", sequenceValue, "accepted");
    } else if (seq.present) {
      rejectField(state, "sequence");
    }
    if (producerIdValue != null && sequenceValue != null) {
      const canonical = eventIdFor(producerIdValue, sequenceValue);
      const eventId = take(input, seen, "event_id");
      if (canonical.length <= bounds.event_id_max_chars) {
        put(state, record, "event_id", canonical, eventId.present && eventId.value === canonical ? "accepted" : "normalized");
      }
    } else {
      const eventId = take(input, seen, "event_id");
      if (eventId.present) {
        const token = typeof eventId.value === "string" && /^e\.[0-9]+\.[A-Za-z0-9_-]+\.[0-9]+$/.test(eventId.value)
          && eventId.value.length <= bounds.event_id_max_chars
          ? eventId.value
          : null;
        if (token && !privacy.containsProhibited(token)) put(state, record, "event_id", token, "accepted");
        else {
          rejectField(state, "event_id");
          if (stringSecret(eventId.value)) markPrivacy(state);
        }
      }
    }
  }
  return { producer: producerValue, version: versionValue };
}

function applyTrace(input, seen, state, record) {
  const direct = take(input, seen, "trace_id");
  const basis = take(input, seen, "trace_id_basis");
  const inherited = take(input, seen, "vantio_trace_id");
  const parentHeader = take(input, seen, "traceparent");
  const span = take(input, seen, "span_id");
  const parentSpan = take(input, seen, "parent_span_id");
  if (inherited.present) stripKey(state, "vantio_trace_id");
  if (parentHeader.present) stripKey(state, "traceparent");

  const accepted = [];
  if (direct.present && direct.value != null) {
    const norm = traceNormalize(direct.value);
    if (!norm || norm.prohibited) {
      markContext(state);
      if (norm && norm.prohibited) markPrivacy(state);
    } else accepted.push({ trace: norm.value, changed: norm.changed, source: "trace_id" });
  }
  if (inherited.present && inherited.value != null) {
    const norm = traceNormalize(inherited.value);
    if (!norm || norm.prohibited) {
      markContext(state);
      if (norm && norm.prohibited) markPrivacy(state);
      state.traceMeaning = "ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF";
    } else {
      accepted.push({ trace: norm.value, changed: true, source: "vantio_trace_id" });
      state.traceMeaning = "ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF";
    }
  }
  let headerSpan = null;
  if (parentHeader.present && parentHeader.value != null) {
    const parsed = parseTraceparent(parentHeader.value);
    if (!parsed) {
      markContext(state);
      if (stringSecret(parentHeader.value)) markPrivacy(state);
    } else {
      accepted.push({ trace: parsed.trace, changed: true, source: "traceparent" });
      headerSpan = parsed.span;
    }
  }
  const distinct = Array.from(new Set(accepted.map((item) => item.trace)));
  if (distinct.length > 1) {
    markContext(state);
    state.configurationFault = true;
    put(state, record, "trace_id", null, "normalized");
    put(state, record, "trace_id_basis", null, "normalized");
    put(state, record, "span_id", null, "normalized");
    put(state, record, "parent_span_id", null, "normalized");
    return;
  }
  if (distinct.length === 1) {
    const item = accepted[0];
    let basisValue = null;
    if (basis.present && TRACE_BASIS.has(basis.value)) basisValue = basis.value;
    else if (item.source !== "trace_id") basisValue = "ASSERTED_CONTEXT";
    else {
      markContext(state);
      put(state, record, "trace_id", null, "normalized");
      put(state, record, "trace_id_basis", null, "normalized");
      return;
    }
    put(state, record, "trace_id", item.trace, item.changed || item.source !== "trace_id" ? "normalized" : "accepted");
    put(state, record, "trace_id_basis", basisValue, basis.present && basis.value === basisValue ? "accepted" : "normalized");
  } else if (direct.present || inherited.present || parentHeader.present) {
    put(state, record, "trace_id", null, "normalized");
    put(state, record, "trace_id_basis", null, "normalized");
  }

  if (state.contextRejected && distinct.length !== 1) return;
  if (span.present) {
    if (span.value == null) put(state, record, "span_id", null, "accepted");
    else {
      const norm = spanNormalize(span.value);
      if (!norm || norm.prohibited) {
        markContext(state);
        put(state, record, "span_id", null, "normalized");
        if (norm && norm.prohibited) markPrivacy(state);
      } else put(state, record, "span_id", norm.value, norm.changed ? "normalized" : "accepted");
    }
  } else if (headerSpan && !state.contextRejected) {
    put(state, record, "span_id", headerSpan, "normalized");
  }
  if (parentSpan.present) {
    if (parentSpan.value == null) put(state, record, "parent_span_id", null, "accepted");
    else {
      const norm = spanNormalize(parentSpan.value);
      if (!norm || norm.prohibited) {
        markContext(state);
        put(state, record, "parent_span_id", null, "normalized");
        if (norm && norm.prohibited) markPrivacy(state);
      } else put(state, record, "parent_span_id", norm.value, norm.changed ? "normalized" : "accepted");
    }
  }
}

function applySession(input, seen, state, record, producerOk) {
  const id = take(input, seen, "session_id");
  const basis = take(input, seen, "session_id_basis");
  if (!id.present && !basis.present) return;
  if (!id.present || !basis.present || id.value == null || basis.value == null) {
    markSession(state);
    if (stringSecret(id.value) || stringSecret(basis.value)) markPrivacy(state);
    return;
  }
  const checked = checkSession(id.value, basis.value, producerOk);
  if (!checked.ok) {
    markSession(state);
    if (checked.privacy) markPrivacy(state);
    return;
  }
  put(state, record, "session_id", checked.value, "accepted");
  put(state, record, "session_id_basis", checked.basis, "accepted");
}

function applyClockAndStatus(input, seen, state, record, kind) {
  for (const key of ["started_at", "ended_at"]) {
    if (kind === "observation" && key === "ended_at") continue;
    const item = take(input, seen, key);
    if (!item.present || item.value == null) continue;
    const time = canonicalTime(item.value);
    if (!time) {
      rejectField(state, key);
      if (stringSecret(item.value)) markPrivacy(state);
    } else put(state, record, key, time.value, time.changed ? "normalized" : "accepted");
  }
  const duration = take(input, seen, "duration_ms");
  if (duration.present && duration.value != null) {
    const n = nonNegativeInt(duration.value);
    if (n == null) rejectField(state, "duration_ms");
    else put(state, record, "duration_ms", n, "accepted");
  }
  const clock = take(input, seen, "clock_quality");
  if (clock.present && CLOCK.has(clock.value)) put(state, record, "clock_quality", clock.value, "accepted");
  else if (clock.present && clock.value != null) rejectField(state, "clock_quality");
  const life = take(input, seen, "lifecycle");
  if (life.present && LIFECYCLE.has(life.value)) {
    put(state, record, "lifecycle", life.value, "accepted");
    if (life.value === "INTERRUPTED") state.interrupted = true;
  } else if (life.present && life.value != null) rejectField(state, "lifecycle");
  const conflict = take(input, seen, "identity_conflict");
  if (!record.identity_conflict) {
    if (conflict.present && CONFLICT.has(conflict.value)) put(state, record, "identity_conflict", conflict.value, "accepted");
    else if (conflict.present && conflict.value != null) rejectField(state, "identity_conflict");
    else if (kind === "observation" || kind === "envelope") put(state, record, "identity_conflict", "NONE", conflict.present ? "normalized" : "normalized");
  }
  const runtime = take(input, seen, "runtime");
  if (runtime.present && RUNTIMES.has(runtime.value)) put(state, record, "runtime", runtime.value, "accepted");
  else if (runtime.present && runtime.value != null) rejectField(state, "runtime");
  const runtimeVersion = take(input, seen, "runtime_version");
  if (runtimeVersion.present) {
    const token = versionToken(runtimeVersion.value, 32);
    if (typeof token === "string") put(state, record, "runtime_version", token, "accepted");
    else {
      rejectField(state, "runtime_version");
      if (token && token.prohibited) markPrivacy(state);
    }
  }
  const platform = take(input, seen, "platform");
  if (platform.present && PLATFORMS.has(platform.value)) put(state, record, "platform", platform.value, "accepted");
  else if (platform.present && platform.value != null) {
    rejectField(state, "platform");
    if (stringSecret(platform.value)) markPrivacy(state);
  }
  const arch = take(input, seen, "arch");
  if (arch.present && ARCHES.has(arch.value)) put(state, record, "arch", arch.value, "accepted");
  else if (arch.present && arch.value != null) rejectField(state, "arch");
  for (const key of ["process_id", "parent_process_id"]) {
    const item = take(input, seen, key);
    if (!item.present) continue;
    if (item.value == null) put(state, record, key, null, "accepted");
    else {
      const n = nonNegativeInt(item.value);
      if (n == null) rejectField(state, key);
      else put(state, record, key, n, "accepted");
    }
  }
}

function applySchema(state, record, input, seen, recordType) {
  put(state, record, "record_type", recordType, input.record_type === recordType ? "accepted" : "normalized");
  seen.add("record_type");
  const status = take(input, seen, "schema_status");
  put(
    state,
    record,
    "schema_status",
    "unstable-pre-1.0",
    status.present && status.value === "unstable-pre-1.0" ? "accepted" : "normalized",
  );
  if (status.present && status.value !== "unstable-pre-1.0") addReason(state, "SCHEMA_STATUS_CORRECTED");
  const version = take(input, seen, "schema_version");
  put(state, record, "schema_version", 0, version.present && version.value === 0 ? "accepted" : "normalized");
  return version.present && isInteger(version.value) ? version.value : null;
}

function applyObservationFields(input, seen, state, record) {
  const status = take(input, seen, "http_status");
  const legacyStatus = take(input, seen, "status");
  const rawStatus = status.present ? status.value : legacyStatus.present ? legacyStatus.value : undefined;
  if (legacyStatus.present) stripKey(state, "status");
  const code = rawStatus == null ? null : httpStatus(rawStatus);
  if (rawStatus != null && code == null) {
    rejectField(state, "http_status");
    if (stringSecret(rawStatus)) markPrivacy(state);
  }
  if (code != null) {
    state.httpStatus = code;
    put(state, record, "http_status", code, rawStatus === code ? "accepted" : "normalized");
  }
  const derivedApp = code == null ? null : applicationStatusFromHttp(code);
  const app = take(input, seen, "application_status");
  const legacyApp = take(input, seen, "applicationStatus");
  if (legacyApp.present) stripKey(state, "applicationStatus");
  const coverage = take(input, seen, "coverage_gap");
  if (coverage.present) {
    stripKey(state, "coverage_gap");
    if (coverage.value === "EVIDENCED") state.coverageEvidenced = true;
    else state.coverageUnevidenced = true;
  }
  let appValue;
  if (derivedApp) appValue = derivedApp;
  else if (app.present && app.value === "NOT_OBSERVED") appValue = "NOT_OBSERVED";
  else if (legacyApp.present && legacyApp.value === "NOT_OBSERVED") appValue = "NOT_OBSERVED";
  else appValue = "UNAVAILABLE";
  if (app.present || legacyApp.present || code != null) {
    const same = (app.present && app.value === appValue) || (!app.present && legacyApp.present && legacyApp.value === appValue);
    put(state, record, "application_status", appValue, same ? "accepted" : "normalized");
  }
  const failure = take(input, seen, "failure_kind");
  if (failure.present && FAILURES.has(failure.value)) {
    put(state, record, "failure_kind", failure.value, "accepted");
    if (NETWORK_KINDS.has(failure.value) && code == null) state.networkNoHttp = true;
    if (failure.value === "wrapped" && code == null) state.customerException = true;
    if (failure.value !== "none") state.failureIdentified = true;
  } else if (failure.present && failure.value != null) {
    rejectField(state, "failure_kind");
    if (stringSecret(failure.value)) markPrivacy(state);
  }
  const errorClass = take(input, seen, "error_class");
  if (errorClass.present && errorClass.value != null) {
    if (typeof errorClass.value === "string" && /^[A-Za-z0-9_]{1,64}$/.test(errorClass.value)
      && !privacy.containsProhibited(errorClass.value)) {
      put(state, record, "error_class", errorClass.value, "accepted");
      if (code == null && (!failure.present || failure.value === "wrapped" || failure.value == null)) {
        state.customerException = true;
      }
    } else {
      rejectField(state, "error_class");
      markPrivacy(state);
    }
  }
  const action = take(input, seen, "action");
  if (action.present && action.value !== "OBSERVED") {
    if (stringSecret(action.value)) markPrivacy(state);
    dropRecord(state, "ENFORCEMENT_ACTION_EXCLUDED");
    rejectField(state, "action");
  } else if (action.present) put(state, record, "action", "OBSERVED", "accepted");
  else put(state, record, "action", "OBSERVED", "normalized");

  const method = take(input, seen, "method");
  if (method.present && method.value != null) {
    const upper = typeof method.value === "string" ? method.value.toUpperCase() : "";
    if (METHODS.has(upper)) put(state, record, "method", upper, upper === method.value ? "accepted" : "normalized");
    else if (stringSecret(method.value)) {
      rejectField(state, "method");
      markPrivacy(state);
    } else put(state, record, "method", "unknown", "normalized");
  }
  const bytesIn = take(input, seen, "request_bytes");
  if (bytesIn.present && bytesIn.value != null) {
    const n = nonNegativeInt(bytesIn.value);
    if (n == null) rejectField(state, "request_bytes");
    else put(state, record, "request_bytes", n, "accepted");
  }
  const response = take(input, seen, "response_bytes");
  const legacyBytes = take(input, seen, "bytes");
  if (legacyBytes.present) stripKey(state, "bytes");
  if (response.present) {
    if (response.value == null) put(state, record, "response_bytes", null, "accepted");
    else {
      const n = nonNegativeInt(response.value);
      if (n == null) rejectField(state, "response_bytes");
      else put(state, record, "response_bytes", n, "accepted");
    }
  } else if (legacyBytes.present) {
    if (legacyBytes.value === 0 || legacyBytes.value == null) put(state, record, "response_bytes", null, "normalized");
    else {
      const n = nonNegativeInt(legacyBytes.value);
      if (n == null) rejectField(state, "response_bytes");
      else put(state, record, "response_bytes", n, "normalized");
    }
  }
  const type = take(input, seen, "content_type");
  if (type.present && type.value != null) {
    const media = contentType(type.value);
    if (!media.ok) {
      rejectField(state, "content_type");
      if (media.prohibited) markPrivacy(state);
    } else put(state, record, "content_type", media.value, media.changed ? "normalized" : "accepted");
  }
  const mediation = take(input, seen, "mediation");
  if (mediation.present && mediation.value != null) {
    if (typeof mediation.value === "string" && MEDIATION.has(mediation.value)) {
      put(state, record, "mediation", mediation.value, "accepted");
    } else if (stringSecret(mediation.value)) {
      rejectField(state, "mediation");
      markPrivacy(state);
    } else put(state, record, "mediation", "unknown", "normalized");
  }
  const sampling = take(input, seen, "sampling");
  if (!sampling.present || sampling.value === "UNSAMPLED") {
    put(state, record, "sampling", "UNSAMPLED", sampling.present ? "accepted" : "normalized");
  } else {
    put(state, record, "sampling", "UNSAMPLED", "normalized");
    if (stringSecret(sampling.value)) markPrivacy(state);
  }
  const duplicate = take(input, seen, "duplicate_of");
  if (duplicate.present) {
    if (duplicate.value == null) put(state, record, "duplicate_of", null, "accepted");
    else if (typeof duplicate.value === "string" && duplicate.value.length <= bounds.event_id_max_chars
      && !privacy.containsProhibited(duplicate.value)) {
      put(state, record, "duplicate_of", duplicate.value, "accepted");
    } else {
      rejectField(state, "duplicate_of");
      if (stringSecret(duplicate.value)) markPrivacy(state);
    }
  }
  const provider = take(input, seen, "provider_id");
  const confidence = take(input, seen, "provider_confidence");
  const legacyProvider = take(input, seen, "provider");
  if (legacyProvider.present) {
    stripKey(state, "provider");
    if (stringSecret(legacyProvider.value)) markPrivacy(state);
  }
  let providerValue = "unknown";
  let confidenceValue = "NONE";
  let providerKind = "normalized";
  if (provider.present && typeof provider.value === "string" && /^[a-z0-9_-]{1,64}$/.test(provider.value)) {
    providerValue = provider.value;
    providerKind = "accepted";
  } else if (provider.present && provider.value != null && provider.value !== "unknown") {
    rejectField(state, "provider_id");
    if (stringSecret(provider.value)) markPrivacy(state);
  }
  if (confidence.present && CONFIDENCE.has(confidence.value)) confidenceValue = confidence.value;
  if (confidenceValue === "LOCAL_OLLAMA") {
    const host = record.destination_host;
    const port = record.destination_port;
    const local = host === "localhost" || host === "127.0.0.1" || host === "::1";
    if (!(local && port === 11434)) {
      providerValue = "unknown";
      confidenceValue = "NONE";
      providerKind = "normalized";
    }
  }
  if (confidenceValue === "NONE") providerValue = "unknown";
  if (provider.present || confidence.present || legacyProvider.present) {
    put(state, record, "provider_id", providerValue, providerValue === provider.value ? providerKind : "normalized");
    put(state, record, "provider_confidence", confidenceValue, confidence.present && confidence.value === confidenceValue ? "accepted" : "normalized");
  }
  const optics = take(input, seen, "optics_status");
  const legacyOptics = take(input, seen, "opticsStatus");
  if (legacyOptics.present) stripKey(state, "opticsStatus");
  const opticsValue = optics.present ? optics.value : legacyOptics.present ? legacyOptics.value : undefined;
  if (state.dropRecord) return;
  if (OPTICS_STATUS.has(opticsValue)) put(state, record, "optics_status", opticsValue, "accepted");
  else put(state, record, "optics_status", "SUCCESS", "normalized");

  const internal = take(input, seen, "optics_internal_failure");
  if (internal.present) {
    stripKey(state, "optics_internal_failure");
    if (internal.value === true) {
      state.opticsInternal = true;
      dropRecord(state, "OPTICS_WRITE_FAILURE");
    }
  }
  const environment = take(input, seen, "environment_condition");
  if (environment.present) {
    stripKey(state, "environment_condition");
    if (environment.value === true) state.environmentFault = true;
  }
  const parentConflict = take(input, seen, "parent_conflict");
  if (parentConflict.present) {
    stripKey(state, "parent_conflict");
    if (parentConflict.value === true && record.identity_conflict !== "PRODUCER_SEQUENCE") {
      put(state, record, "identity_conflict", "PARENT", "normalized");
    }
  }
}

function buildObservation(input, inherited) {
  const state = inherited || createState();
  const seen = new Set();
  const record = Object.create(null);
  const legacyVersion = applySchema(state, record, input, seen, "observation_event");
  const who = commonIdentity(input, seen, state, record, "observation");
  applySession(input, seen, state, record, Boolean(who.producer && who.version));
  applyTrace(input, seen, state, record);
  applyClockAndStatus(input, seen, state, record, "observation");
  const destination = collectDestination(input, seen, state);
  if (!state.dropRecord) storeDestination(state, record, destination);
  applyObservationFields(input, seen, state, record);
  const demo = record.destination_host === meta.demo_host;
  const requestedOrigin = Object.prototype.hasOwnProperty.call(input, "evidence_origin") ? input.evidence_origin : undefined;
  seen.add("evidence_origin");
  applyOrigin(state, record, requestedOrigin, who.producer, who.version, demo);
  const location = issueLocation(state);
  put(state, record, "issue_location", location, input.issue_location === location ? "accepted" : "normalized");
  seen.add("issue_location");
  if (input.issue_location === "Provider fault") markPrivacy(state);
  sweepLeftovers(input, seen, state);
  if (state.dropRecord) {
    state.accepted.clear();
    state.normalized.clear();
    delete record.optics_status;
  }
  return { state, record: state.dropRecord ? null : record, legacyVersion };
}

function buildEnvelope(input) {
  const state = createState();
  const seen = new Set();
  const record = Object.create(null);
  const legacyVersion = applySchema(state, record, input, seen, "run_envelope");
  const who = commonIdentity(input, seen, state, record, "envelope");
  applySession(input, seen, state, record, Boolean(who.producer && who.version));
  applyTrace(input, seen, state, record);
  applyClockAndStatus(input, seen, state, record, "envelope");
  state.accepted.delete("span_id");
  state.normalized.delete("span_id");
  state.accepted.delete("parent_span_id");
  state.normalized.delete("parent_span_id");
  put(state, record, "span_id", null, input.span_id == null && Object.prototype.hasOwnProperty.call(input, "span_id") ? "accepted" : "normalized");
  put(state, record, "parent_span_id", null, input.parent_span_id == null && Object.prototype.hasOwnProperty.call(input, "parent_span_id") ? "accepted" : "normalized");
  seen.add("span_id");
  seen.add("parent_span_id");
  const coverage = take(input, seen, "coverage_note");
  if (coverage.present && COVERAGE.has(coverage.value)) put(state, record, "coverage_note", coverage.value, "accepted");
  else if (coverage.present && coverage.value != null) {
    rejectField(state, "coverage_note");
    if (stringSecret(coverage.value)) markPrivacy(state);
  }
  const declaredCalls = take(input, seen, "call_count");
  if (declaredCalls.present && declaredCalls.value != null) {
    const n = nonNegativeInt(declaredCalls.value);
    if (n == null) rejectField(state, "call_count");
    else put(state, record, "call_count", n, "accepted");
  }
  const declaredDrops = take(input, seen, "dropped_count");
  if (declaredDrops.present && declaredDrops.value != null) {
    const n = nonNegativeInt(declaredDrops.value);
    if (n == null) rejectField(state, "dropped_count");
    else put(state, record, "dropped_count", n, "accepted");
  }
  const calls = take(input, seen, "calls");
  let callCount = null;
  if (calls.present && Array.isArray(calls.value)) {
    if (calls.value.length > bounds.calls_max) {
      dropRecord(state, "INPUT_BOUND");
      callCount = calls.value.length;
    } else callCount = calls.value.length;
  }
  if (callCount != null && !state.dropRecord) put(state, record, "call_count", callCount, "normalized");
  const demo = false;
  const requestedOrigin = Object.prototype.hasOwnProperty.call(input, "evidence_origin") ? input.evidence_origin : undefined;
  seen.add("evidence_origin");
  applyOrigin(state, record, requestedOrigin, who.producer, who.version, demo);
  sweepLeftovers(input, seen, state);
  return { state, record: state.dropRecord ? null : record, legacyVersion, calls: calls.present ? calls.value : null };
}

function buildDerived(input) {
  const state = createState();
  const seen = new Set();
  const record = Object.create(null);
  applySchema(state, record, input, seen, "derived_diagnostic");
  put(state, record, "evidence_origin", "DERIVED_DIAGNOSTIC", input.evidence_origin === "DERIVED_DIAGNOSTIC" ? "accepted" : "normalized");
  seen.add("evidence_origin");
  state.readerOrigin = "DERIVED_DIAGNOSTIC";
  state.provenance = "NOT_APPLICABLE";
  for (const key of ["subject_event_id", "subject_run_id"]) {
    const item = take(input, seen, key);
    if (!item.present || item.value == null) continue;
    const token = idToken(item.value, key === "subject_event_id" ? 160 : 80);
    if (typeof token === "string") put(state, record, key, token, "accepted");
    else {
      rejectField(state, key);
      if (token && token.prohibited) markPrivacy(state);
    }
  }
  const outcome = take(input, seen, "application_outcome_label");
  if (outcome.present) {
    if (OUTCOME_LABELS.has(outcome.value)) put(state, record, "application_outcome_label", outcome.value, "accepted");
    else {
      rejectField(state, "application_outcome_label");
      if (stringSecret(outcome.value)) markPrivacy(state);
    }
  }
  const phrase = take(input, seen, "provider_response_phrase");
  if (phrase.present) {
    if (PROVIDER_PHRASES.has(phrase.value)) put(state, record, "provider_response_phrase", phrase.value, "accepted");
    else {
      rejectField(state, "provider_response_phrase");
      if (stringSecret(phrase.value)) markPrivacy(state);
    }
  }
  const next = take(input, seen, "next_action_category");
  if (next.present && NEXT_ACTION.has(next.value)) put(state, record, "next_action_category", next.value, "accepted");
  else if (next.present) rejectField(state, "next_action_category");
  const location = take(input, seen, "issue_location");
  if (location.present && enums.issue_location.includes(location.value)) {
    put(state, record, "issue_location", location.value, "accepted");
  } else if (location.present) {
    rejectField(state, "issue_location");
    if (location.value === "Provider fault" || stringSecret(location.value)) markPrivacy(state);
  }
  sweepLeftovers(input, seen, state);
  return { state, record: state.dropRecord ? null : record, legacyVersion: null };
}

function buildAnnotation(input) {
  const state = createState();
  const seen = new Set();
  const record = Object.create(null);
  applySchema(state, record, input, seen, "annotation");
  if (Object.prototype.hasOwnProperty.call(input, "evidence_origin")) {
    seen.add("evidence_origin");
    stripKey(state, "evidence_origin");
    addReason(state, "ANNOTATION_ORIGIN_REFUSED");
    addDisposition(state, "REPLACE_WITH_SAFE_CATEGORY");
    if (input.evidence_origin === "LOCAL_OBSERVATION") state.readerOrigin = "LEGACY_UNMARKED";
  }
  const role = take(input, seen, "annotation_role");
  if (role.present && role.value === "CUSTOMER_ANNOTATION") {
    put(state, record, "annotation_role", "CUSTOMER_ANNOTATION", "accepted");
  } else put(state, record, "annotation_role", "CUSTOMER_ANNOTATION", "normalized");
  for (const key of ["annotation_id", "subject_run_id"]) {
    const item = take(input, seen, key);
    if (!item.present) continue;
    const token = idToken(item.value, 80);
    if (typeof token === "string") put(state, record, key, token, "accepted");
    else {
      rejectField(state, key);
      if (token && token.prohibited) markPrivacy(state);
    }
  }
  const created = take(input, seen, "created_at");
  if (created.present) {
    const time = canonicalTime(created.value);
    if (!time) rejectField(state, "created_at");
    else put(state, record, "created_at", time.value, time.changed ? "normalized" : "accepted");
  }
  const text = take(input, seen, "text");
  if (text.present) {
    const scanned = consumeStringField(text.value);
    const tooLong = typeof text.value === "string" && codePoints(text.value).length > bounds.annotation_text_max_chars;
    if (scanned.prohibited || tooLong || scanned.bad) {
      rejectField(state, "text");
      markPrivacy(state);
    } else put(state, record, "text", scanned.value, "accepted");
  }
  sweepLeftovers(input, seen, state);
  if (state.privacy && state.rejected.has("text")) {
    // Text is omitted. The annotation shell remains only when other fields survived.
  }
  return { state, record: state.dropRecord ? null : record, legacyVersion: null };
}

function buildHealth(input) {
  const state = createState();
  const seen = new Set();
  const record = Object.create(null);
  applySchema(state, record, input, seen, "product_health");
  put(state, record, "evidence_origin", "PRODUCT_HEALTH", input.evidence_origin === "PRODUCT_HEALTH" ? "accepted" : "normalized");
  seen.add("evidence_origin");
  state.readerOrigin = "PRODUCT_HEALTH";
  const name = take(input, seen, "name");
  if (name.present && HEALTH_NAMES.has(name.value)) put(state, record, "name", name.value, "accepted");
  else {
    dropRecord(state, "RECORD_TYPE_REJECTED");
    rejectField(state, "name");
  }
  const value = take(input, seen, "value");
  if (value.present && record.name) {
    const enumValue = valueEnum(record.name, value.value);
    if (enumValue == null) {
      rejectField(state, "value");
      if (stringSecret(value.value)) markPrivacy(state);
    } else put(state, record, "value", enumValue.value, enumValue.changed ? "normalized" : "accepted");
  }
  const at = take(input, seen, "observed_at");
  if (at.present) {
    const time = canonicalTime(at.value);
    if (!time) rejectField(state, "observed_at");
    else put(state, record, "observed_at", time.value, time.changed ? "normalized" : "accepted");
  }
  const detail = take(input, seen, "detail_code");
  if (detail.present && detail.value != null) {
    if (typeof detail.value === "string" && /^[A-Za-z0-9_]{1,64}$/.test(detail.value)) {
      put(state, record, "detail_code", detail.value, "accepted");
    } else {
      rejectField(state, "detail_code");
      markPrivacy(state);
    }
  }
  sweepLeftovers(input, seen, state);
  return { state, record: state.dropRecord ? null : record, legacyVersion: null };
}

function valueEnum(name, value) {
  if (name === "integrity_state" && enums.integrity_state.includes(value)) return { value, changed: false };
  if (name === "migration_state" && enums.migration_state.includes(value)) return { value, changed: false };
  if (name === "telemetry_last_result" && enums.telemetry_last_result.includes(value)) return { value, changed: false };
  if (name === "last_successful_write_at") {
    const time = canonicalTime(value);
    if (time) return { value: time.value, changed: time.changed };
  }
  const n = nonNegativeInt(value);
  if (n != null && name !== "integrity_state" && name !== "migration_state" && name !== "telemetry_last_result") {
    return { value: n, changed: false };
  }
  return null;
}

function buildQuarantine(input) {
  const state = createState();
  const seen = new Set();
  const record = Object.create(null);
  applySchema(state, record, input, seen, "import_quarantine");
  const requested = input.evidence_origin;
  seen.add("evidence_origin");
  put(state, record, "evidence_origin", "IMPORTED", requested === "IMPORTED" ? "accepted" : "normalized");
  if (requested && requested !== "IMPORTED") {
    addReason(state, "ORIGIN_NOT_PROMOTED");
    addDisposition(state, "REPLACE_WITH_SAFE_CATEGORY");
  }
  state.readerOrigin = "IMPORTED";
  state.provenance = "INSUFFICIENT";
  const original = take(input, seen, "original_evidence_origin");
  if (original.present && ORIGINAL_ORIGIN.has(original.value)) {
    put(state, record, "original_evidence_origin", original.value, "accepted");
  } else {
    put(state, record, "original_evidence_origin", "LEGACY_UNMARKED", "normalized");
  }
  const label = take(input, seen, "source_label");
  if (label.present) {
    if (typeof label.value === "string" && codePoints(label.value).length <= bounds.source_label_max_chars
      && !privacy.hasUsernamePath(label.value) && !privacy.containsProhibited(label.value) && !label.value.includes("\\")) {
      put(state, record, "source_label", label.value, "accepted");
    } else {
      rejectField(state, "source_label");
      markPrivacy(state);
    }
  }
  const hash = take(input, seen, "content_sha256");
  if (hash.present && hash.value != null) {
    if (typeof hash.value === "string" && /^[0-9a-fA-F]{64}$/.test(hash.value)) {
      const lower = hash.value.toLowerCase();
      put(state, record, "content_sha256", lower, lower === hash.value ? "accepted" : "normalized");
    } else {
      rejectField(state, "content_sha256");
      if (stringSecret(hash.value)) markPrivacy(state);
    }
  }
  const seenStatus = take(input, seen, "schema_status_seen");
  if (seenStatus.present && typeof seenStatus.value === "string" && /^[A-Za-z0-9._+-]{1,64}$/.test(seenStatus.value)) {
    put(state, record, "schema_status_seen", seenStatus.value, "accepted");
  } else if (seenStatus.present) rejectField(state, "schema_status_seen");
  const importedAt = take(input, seen, "imported_at");
  if (importedAt.present) {
    const time = canonicalTime(importedAt.value);
    if (!time) rejectField(state, "imported_at");
    else put(state, record, "imported_at", time.value, time.changed ? "normalized" : "accepted");
  }
  const accepted = take(input, seen, "accepted");
  if (accepted.present && typeof accepted.value === "boolean") put(state, record, "accepted", accepted.value, "accepted");
  else put(state, record, "accepted", false, "normalized");
  const reason = take(input, seen, "reason_code");
  if (reason.present && typeof reason.value === "string" && /^[A-Za-z0-9_]{1,64}$/.test(reason.value)) {
    put(state, record, "reason_code", reason.value, "accepted");
  } else if (reason.present && reason.value != null) {
    rejectField(state, "reason_code");
    if (stringSecret(reason.value)) markPrivacy(state);
  }
  sweepLeftovers(input, seen, state);
  return { state, record: state.dropRecord ? null : record, legacyVersion: null };
}

function sourceShape(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return "unknown";
  if (input.vantio_run_log === "1" && Array.isArray(input.calls)) {
    if (input.runtime === "python" || input.workflow === "sight_loop") return "python_run_log";
    return "node_run_log";
  }
  if (typeof input.record_type === "string") return "contract_record";
  if (Object.prototype.hasOwnProperty.call(input, "hostname")) return "legacy_call";
  return "unknown";
}

function legacyCallToContract(call) {
  const out = Object.create(null);
  out.record_type = "observation_event";
  const map = {
    hostname: "destination_host",
    method: "method",
    path: "path",
    scheme: "scheme",
    request_bytes: "request_bytes",
    status: "http_status",
    content_type: "content_type",
    duration_ms: "duration_ms",
    action: "action",
    ts: "started_at",
    error_class: "error_class",
    failure_kind: "failure_kind",
    mediation: "mediation",
    opticsStatus: "optics_status",
    applicationStatus: "application_status",
  };
  for (const [from, to] of Object.entries(map)) {
    if (Object.prototype.hasOwnProperty.call(call, from) && call[from] != null) out[to] = call[from];
  }
  if (Object.prototype.hasOwnProperty.call(call, "bytes")) out.bytes = call.bytes;
  for (const key of Object.keys(call)) {
    if (key === "bytes" || Object.prototype.hasOwnProperty.call(map, key)) continue;
    out[key] = call[key];
  }
  return out;
}

function legacyEnvelopeToContract(input) {
  const out = Object.create(null);
  out.record_type = "run_envelope";
  if (typeof input.trace_id === "string") out.run_id = input.trace_id;
  if (Object.prototype.hasOwnProperty.call(input, "pid")) out.process_id = input.pid;
  if (Object.prototype.hasOwnProperty.call(input, "ppid")) out.parent_process_id = input.ppid;
  if (typeof input.node_version === "string") {
    out.runtime = "node";
    out.runtime_version = input.node_version;
  }
  if (input.runtime === "python" || input.runtime === "node") out.runtime = input.runtime;
  if (typeof input.platform === "string") out.platform = input.platform;
  if (typeof input.arch === "string") out.arch = input.arch;
  if (typeof input.started_at === "string") out.started_at = input.started_at;
  if (typeof input.generated_at === "string") out.ended_at = input.generated_at;
  if (Object.prototype.hasOwnProperty.call(input, "duration_ms")) out.duration_ms = input.duration_ms;
  if (typeof input.cli_version === "string") out.cli_or_sdk_version = input.cli_version;
  for (const key of ["schema_status", "schema_version", "evidence_origin", "producer", "session_id", "session_id_basis"]) {
    if (Object.prototype.hasOwnProperty.call(input, key)) out[key] = input[key];
  }
  for (const key of Object.keys(input)) {
    if (key === "calls" || key === "trace_id" || key === "vantio_run_log") continue;
    if (!Object.prototype.hasOwnProperty.call(out, key === "pid" ? "process_id" : key)) {
      if (["pid", "ppid", "node_version", "generated_at", "cli_version"].includes(key)) continue;
      out[key] = input[key];
    }
  }
  return out;
}

function finalize(state, record, events, applicationResult, compatibility) {
  const disposition = highest(DISPOSITION_RANK, state.dispositions, "ACCEPT");
  const reason = highest(REASON_RANK, state.reasons, "OK");
  const location = state.dropRecord && state.opticsInternal
    ? "OPTICS"
    : (record && Object.prototype.hasOwnProperty.call(record, "issue_location")
      ? record.issue_location
      : issueLocation(state));
  const health = {
    events_rejected: state.health.events_rejected,
    redaction_failures: state.health.redaction_failures,
    rejected_context: state.health.rejected_context,
    session_id_rejected: state.health.session_id_rejected,
  };
  const emitted = record != null;
  return {
    schema_status: "unstable-pre-1.0",
    schema_version: 0,
    disposition,
    reason_code: reason,
    remediation_code: enums.remediation_by_reason[reason] || "VALIDATOR_INTERNAL",
    reader_origin_label: state.readerOrigin,
    issue_location: location,
    issue_location_label: ISSUE_LABELS[location] || "Unknown",
    completeness_impact: completenessList(state),
    health_impact: health,
    optics_health_impact: healthLabel(health),
    fields: {
      accepted: sorted(state.accepted),
      normalized: sorted(state.normalized),
      rejected: sorted(state.rejected),
      stripped: sorted(state.stripped),
    },
    record: emitted ? record : null,
    events,
    record_emitted: emitted,
    diagnostics: {
      destination_class: state.destinationClass,
      destination_ip_class: state.destinationIpClass,
      privacy_event: state.privacy ? "REDACTION_DROP" : null,
      provenance: state.provenance,
      scope_complete: false,
      trace_basis_meaning: state.traceMeaning,
    },
    completeness_inputs: {
      accept_reject: emitted ? "ACCEPT" : "REJECT",
      drop_state: state.completeness.has("EVENT_DROPPED") || state.completeness.has("REDACTION_DROP") ? "DROPS_IN_SCOPE" : "NONE",
      evidence_origin_label: state.readerOrigin,
      integrity_state: "UNKNOWN",
      interrupted: state.interrupted,
      privacy_invariant: state.privacy ? "VIOLATED" : "HELD",
      sampling: "UNSAMPLED",
      scope_complete: false,
      stripped_fields: sorted(state.stripped),
      validation_result: emitted ? "EMITTED" : "REJECTED",
    },
    compatibility,
    application_result: applicationResult === undefined ? null : applicationResult,
  };
}

function emptyCompatibility(shape, legacyMarker, legacyVersion) {
  return {
    legacy_marker: legacyMarker,
    legacy_schema_version: legacyVersion,
    live_writer_modified: false,
    source_shape: shape,
  };
}

function terminal(reason, applicationResult, shape) {
  const state = createState();
  dropRecord(state, reason);
  if (reason === "MALFORMED_UTF8" || reason === "HOSTILE_INPUT" || reason === "CYCLE_REJECTED"
    || reason === "EXCESSIVE_NESTING" || reason === "INPUT_BOUND" || reason === "VALIDATOR_FAULT"
    || reason === "MALFORMED_JSON") {
    state.opticsInternal = true;
  }
  state.provenance = "NOT_APPLICABLE";
  return finalize(state, null, [], applicationResult, emptyCompatibility(shape || "unavailable", false, null));
}

function validatePlain(input, applicationResult) {
  const shape = sourceShape(input);
  if (shape === "node_run_log" || shape === "python_run_log") {
    const mapped = legacyEnvelopeToContract(input);
    const built = buildEnvelope(mapped);
    const events = [];
    let dropped = 0;
    const calls = Array.isArray(input.calls) ? input.calls : [];
    if (calls.length > bounds.calls_max) {
      dropRecord(built.state, "INPUT_BOUND");
    } else {
      for (const call of calls) {
        const callInput = legacyCallToContract(call && typeof call === "object" ? call : {});
        const child = buildObservation(callInput);
        if (built.state.readerOrigin === "LEGACY_UNMARKED" && child.state.readerOrigin === "LEGACY_UNMARKED") {
          // Child observations of an unmarked legacy file stay unmarked unless they are demo.
        }
        if (!child.record) dropped += 1;
        events.push(finalize(
          child.state,
          child.record,
          [],
          null,
          emptyCompatibility("legacy_call", false, null),
        ));
        mergeState(built.state, child.state);
      }
    }
    if (built.record && !built.state.dropRecord) {
      put(built.state, built.record, "call_count", calls.length, "normalized");
      put(built.state, built.record, "dropped_count", dropped, "normalized");
    }
    const legacyVersion = isInteger(input.schema_version) ? input.schema_version : null;
    return finalize(
      built.state,
      built.state.dropRecord ? null : built.record,
      events,
      applicationResult,
      emptyCompatibility(shape, true, legacyVersion),
    );
  }
  if (shape === "legacy_call") {
    const child = buildObservation(legacyCallToContract(input));
    return finalize(child.state, child.record, [], applicationResult, emptyCompatibility(shape, false, null));
  }
  const recordType = input.record_type;
  let built;
  if (recordType === "observation_event" || recordType == null) {
    if (recordType == null && shape === "unknown") {
      const state = createState();
      dropRecord(state, "RECORD_TYPE_REJECTED");
      const seen = new Set();
      sweepLeftovers(input, seen, state);
      return finalize(state, null, [], applicationResult, emptyCompatibility(shape, false, null));
    }
    built = buildObservation(recordType == null ? { ...input, record_type: "observation_event" } : input);
  } else if (recordType === "run_envelope") built = buildEnvelope(input);
  else if (recordType === "derived_diagnostic") built = buildDerived(input);
  else if (recordType === "annotation") built = buildAnnotation(input);
  else if (recordType === "product_health") built = buildHealth(input);
  else if (recordType === "import_quarantine") built = buildQuarantine(input);
  else {
    const state = createState();
    dropRecord(state, "RECORD_TYPE_REJECTED");
    return finalize(state, null, [], applicationResult, emptyCompatibility(shape, false, null));
  }
  const legacyVersion = isInteger(input.schema_version) ? input.schema_version : null;
  return finalize(
    built.state,
    built.record,
    [],
    applicationResult,
    emptyCompatibility(shape, input.vantio_run_log === "1", input.vantio_run_log === "1" ? legacyVersion : null),
  );
}

function mergeState(parent, child) {
  for (const value of child.dispositions) parent.dispositions.add(value);
  for (const value of child.reasons) parent.reasons.add(value);
  for (const value of child.completeness) parent.completeness.add(value);
  parent.health.events_rejected += child.health.events_rejected;
  parent.health.redaction_failures += child.health.redaction_failures;
  parent.health.rejected_context += child.health.rejected_context;
  parent.health.session_id_rejected += child.health.session_id_rejected;
  if (child.privacy) parent.privacy = true;
  if (!parent.readerOrigin && child.readerOrigin) parent.readerOrigin = child.readerOrigin;
  if (child.readerOrigin === "SIMULATED_DEMO" && parent.readerOrigin === "LEGACY_UNMARKED") {
    // The envelope stays unmarked unless every destination is demo. Per-event labels live on events.
  }
}

function applicationOf(options) {
  if (!options || typeof options !== "object") return null;
  if (Object.prototype.hasOwnProperty.call(options, "applicationResult")) return options.applicationResult;
  return null;
}

function validateEvidence(input, options) {
  const applicationResult = applicationOf(options);
  try {
    if (options && options.injectFault === true) {
      throw new Error("injected");
    }
    if (typeof input === "string") {
      if (input.length > bounds.max_input_chars) return terminal("INPUT_BOUND", applicationResult, "bytes");
      if (privacy.containsProhibited(input) && !input.startsWith("{") && !input.startsWith("[")) {
        const state = createState();
        markPrivacy(state);
        dropRecord(state, "REDACTION_DROP");
        return finalize(state, null, [], applicationResult, emptyCompatibility("unknown", false, null));
      }
      if (input.startsWith("{") || input.startsWith("[")) {
        try {
          input = JSON.parse(input);
        } catch {
          return terminal("MALFORMED_JSON", applicationResult, "bytes");
        }
      } else {
        return terminal("RECORD_TYPE_REJECTED", applicationResult, "unknown");
      }
    }
    if (input == null || typeof input !== "object") {
      return terminal("RECORD_TYPE_REJECTED", applicationResult, "unknown");
    }
    const copied = plainCopy(input);
    if (!copied.ok) return terminal(copied.reason, applicationResult, "unknown");
    if (Array.isArray(copied.value)) {
      const state = createState();
      markPrivacy(state);
      dropRecord(state, "PROMPT_COMPLETION_EXCLUDED");
      return finalize(state, null, [], applicationResult, emptyCompatibility("unknown", false, null));
    }
    return validatePlain(copied.value, applicationResult);
  } catch {
    return terminal("VALIDATOR_FAULT", applicationResult, "unavailable");
  }
}

function validateBytes(buffer, options) {
  const applicationResult = applicationOf(options);
  try {
    if (options && options.injectFault === true) throw new Error("injected");
    const bytes = Buffer.isBuffer(buffer) ? buffer : Buffer.from(buffer);
    let text;
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch {
      return terminal("MALFORMED_UTF8", applicationResult, "bytes");
    }
    if (text.length > bounds.max_input_chars) return terminal("INPUT_BOUND", applicationResult, "bytes");
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      return terminal("MALFORMED_JSON", applicationResult, "bytes");
    }
    return validateEvidence(parsed, options);
  } catch {
    return terminal("VALIDATOR_FAULT", applicationResult, "bytes");
  }
}

module.exports = {
  validateEvidence,
  validateBytes,
  canonicalJson,
  contractMeta: meta,
};
