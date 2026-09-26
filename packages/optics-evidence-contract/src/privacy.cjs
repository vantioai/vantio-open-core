"use strict";

const { readFileSync } = require("fs");
const path = require("path");

const CONTRACT_DIR = path.join(__dirname, "..", "contract");
const policy = JSON.parse(readFileSync(path.join(CONTRACT_DIR, "prohibited-fields.json"), "utf8"));
const detectorSpec = JSON.parse(readFileSync(path.join(CONTRACT_DIR, "detector-classes.json"), "utf8"));
const fieldNameMaxBytes = JSON.parse(readFileSync(path.join(CONTRACT_DIR, "normalization.json"), "utf8")).bounds.field_name_max_bytes;

const CONFUSABLE = new Map(policy.confusables);
const CLASS_CODES = new Map();

function classCodes(name) {
  if (CLASS_CODES.has(name)) return CLASS_CODES.get(name);
  const def = detectorSpec.classes[name];
  const codes = new Set();
  if (!def) {
    CLASS_CODES.set(name, codes);
    return codes;
  }
  if (Array.isArray(def.union)) {
    for (const part of def.union) {
      for (const code of classCodes(part)) codes.add(code);
    }
  }
  if (Array.isArray(def.ranges)) {
    for (const pair of def.ranges) {
      for (let code = pair[0]; code <= pair[1]; code += 1) codes.add(code);
    }
  }
  if (Array.isArray(def.codepoints)) {
    for (const code of def.codepoints) codes.add(code);
  }
  CLASS_CODES.set(name, codes);
  return codes;
}

const ASCII_ALPHA = classCodes("ASCII_ALPHA");
const ASCII_DIGIT = classCodes("ASCII_DIGIT");
const ASCII_ALNUM = classCodes("ASCII_ALNUM");
const ASCII_HEX = classCodes("ASCII_HEX");
const BEARER_EXTRA = new Set(detectorSpec.tails.bearer.extra);
const BASIC_EXTRA = new Set(detectorSpec.tails.basic.extra);
const JWT_EXTRA = new Set(detectorSpec.tails.jwt_extra);
const PAN_SEPARATORS = new Set(detectorSpec.pan.separators);
const BASE64_EXTRA = new Set(detectorSpec.base64_standard_extra);
const EMAIL_CATEGORIES = detectorSpec.email_unicode_category_prefixes;

function unitCode(ch) {
  return ch ? ch.charCodeAt(0) : -1;
}

function inClass(ch, codes) {
  const code = unitCode(ch);
  return code >= 0 && codes.has(code);
}

function isNonAsciiUnit(ch) {
  return unitCode(ch) > detectorSpec.non_ascii.min_exclusive;
}

function asciiMap(text, spec) {
  let out = "";
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    if (code >= spec.from && code <= spec.to) out += String.fromCharCode(code + spec.delta);
    else out += text[i];
  }
  return out;
}

function asciiFold(text) {
  return asciiMap(text, detectorSpec.ascii_case_fold.lower);
}

function asciiFoldUpper(text) {
  return asciiMap(text, detectorSpec.ascii_case_fold.upper);
}

function scanTail(text, start, allowed) {
  let ascii = 0;
  let insertions = 0;
  let i = start;
  while (i < text.length) {
    const ch = text[i];
    if (isNonAsciiUnit(ch)) {
      insertions += 1;
      i += 1;
      continue;
    }
    if (allowed(unitCode(ch))) {
      ascii += 1;
      i += 1;
      continue;
    }
    break;
  }
  return { ascii, insertions, end: i };
}

function tailHit(scanned, minimum) {
  if (scanned.ascii >= minimum) return true;
  return Boolean(
    detectorSpec.credential_tails.mixed_script_matches_when_ascii_tail_and_insertion
    && scanned.insertions > 0
    && scanned.ascii > 0,
  );
}

const SAFE_NAME = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;
const EXACT_NAMES = new Set(policy.prohibited_field_names);
const SEPARATORS = new Set(["-", "_", " ", ".", ":", "/", "\\", "|", ",", ";", "\t"]);

function isNameControl(code) {
  return code <= 0x1f || code === 0x7f || code === 0x2028 || code === 0x2029 || code === 0xfeff
    || (code >= 0x200b && code <= 0x200f) || (code >= 0x202a && code <= 0x202e)
    || (code >= 0x2066 && code <= 0x2069);
}

function comparisonForm(name) {
  if (typeof name !== "string") return "";
  let text = name.normalize("NFC");
  const decoded = percentDecodeOnce(text);
  if (decoded.changed && !decoded.prohibited && decoded.text) text = decoded.text.normalize("NFC");
  let out = "";
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (isNameControl(code) || SEPARATORS.has(ch)) continue;
    if (code >= 65 && code <= 90) out += String.fromCharCode(code + 32);
    else out += ch;
  }
  return out;
}

function normalizeName(name) {
  return comparisonForm(name);
}

const NAME_SET = new Set(policy.prohibited_field_names.map((name) => comparisonForm(name)));
const PAYLOAD_SET = new Set(policy.payload_drop_record_names.map((name) => comparisonForm(name)));
const BAGGAGE_SET = new Set(policy.baggage_names.map((name) => comparisonForm(name)));

function classifyFieldName(name) {
  if (typeof name !== "string") {
    return {
      comparison: "",
      payload: false,
      baggage: false,
      prohibited: false,
      detector: false,
      control: false,
      oversized: false,
      exact: false,
      safe: false,
      locatorKind: "redacted",
      disguised: false,
    };
  }
  const chars = Array.from(name);
  let control = false;
  for (const ch of chars) {
    if (isNameControl(ch.codePointAt(0))) control = true;
  }
  const oversized = Buffer.byteLength(name, "utf8") > fieldNameMaxBytes;
  const comparison = oversized ? "" : comparisonForm(name);
  const payload = comparison !== "" && PAYLOAD_SET.has(comparison);
  const baggage = comparison !== "" && BAGGAGE_SET.has(comparison);
  const prohibited = comparison !== "" && NAME_SET.has(comparison);
  const detector = !oversized && containsProhibited(name);
  const exact = EXACT_NAMES.has(name);
  const safeGrammar = !control && !detector && !oversized && name.normalize("NFC") === name && SAFE_NAME.test(name);
  let locatorKind = safeGrammar ? "safe" : "redacted";
  if ((payload || prohibited) && !exact) locatorKind = "prohibited";
  if (exact && !detector && !control && !oversized) locatorKind = "safe";
  return {
    comparison,
    payload,
    baggage,
    prohibited,
    detector,
    control,
    oversized,
    exact,
    safe: locatorKind === "safe",
    locatorKind,
    disguised: locatorKind === "prohibited",
  };
}

function isProhibitedName(name) {
  return NAME_SET.has(normalizeName(name));
}

function isPayloadName(name) {
  return PAYLOAD_SET.has(normalizeName(name));
}

function isBaggageName(name) {
  return BAGGAGE_SET.has(normalizeName(name));
}

function isHexChar(ch) {
  return inClass(ch, ASCII_HEX);
}

function isDigit(ch) {
  return inClass(ch, ASCII_DIGIT);
}

function startsWithFold(text, prefix, index) {
  const foldedPrefix = asciiFold(prefix);
  if (index + foldedPrefix.length > text.length) return false;
  for (let i = 0; i < foldedPrefix.length; i += 1) {
    if (asciiFold(text[index + i]) !== foldedPrefix[i]) return false;
  }
  return true;
}

function hasBearer(text) {
  const folded = asciiFold(text);
  let from = 0;
  while (from < folded.length) {
    const at = folded.indexOf("bearer", from);
    if (at === -1) return false;
    let i = at + 6;
    if (i >= text.length || (text[i] !== " " && text[i] !== "\t")) {
      from = at + 6;
      continue;
    }
    while (i < text.length && (text[i] === " " || text[i] === "\t")) i += 1;
    const scanned = scanTail(text, i, (code) => ASCII_ALNUM.has(code) || BEARER_EXTRA.has(code));
    if (tailHit(scanned, detectorSpec.tails.bearer.minimum)) return true;
    from = at + 6;
  }
  return false;
}

function hasBasic(text) {
  const folded = asciiFold(text);
  let from = 0;
  while (from < folded.length) {
    const at = folded.indexOf("basic", from);
    if (at === -1) return false;
    let i = at + 5;
    if (i >= text.length || (text[i] !== " " && text[i] !== "\t")) {
      from = at + 5;
      continue;
    }
    while (i < text.length && (text[i] === " " || text[i] === "\t")) i += 1;
    const scanned = scanTail(text, i, (code) => ASCII_ALNUM.has(code) || BASIC_EXTRA.has(code));
    if (tailHit(scanned, detectorSpec.tails.basic.minimum)) return true;
    from = at + 5;
  }
  return false;
}

function hasCookieMarker(text) {
  const folded = asciiFold(text);
  if (folded.includes("set-cookie")) return true;
  if (folded.includes("cookie:")) return true;
  if (folded.includes("cookie=")) return true;
  return false;
}

function hasOpenAiKey(text) {
  const prefixes = policy.openai_prefixes;
  for (let i = 0; i < text.length; i += 1) {
    for (const prefix of prefixes) {
      if (!startsWithFold(text, prefix, i)) continue;
      const scanned = scanTail(text, i + prefix.length, (code) => ASCII_ALNUM.has(code));
      if (tailHit(scanned, policy.openai_tail_min)) return true;
    }
  }
  return false;
}

function hasCloudKey(text) {
  const folded = asciiFold(text);
  for (let i = 0; i + 4 <= folded.length; i += 1) {
    const head = folded.slice(i, i + 4);
    if (head !== "akia" && head !== "asia") continue;
    const scanned = scanTail(text, i + 4, (code) => ASCII_ALNUM.has(code));
    if (tailHit(scanned, policy.cloud_akia_tail)) return true;
  }
  for (const marker of detectorSpec.presence_markers_ascii_case_insensitive) {
    if (folded.includes(asciiFold(marker))) return true;
  }
  return false;
}

function hasPem(text) {
  const folded = asciiFoldUpper(text);
  for (const marker of policy.pem_markers) {
    if (folded.includes(asciiFoldUpper(marker))) return true;
  }
  return false;
}

function hasJwt(text) {
  const folded = asciiFold(text);
  let from = 0;
  while (from < folded.length) {
    const at = folded.indexOf("eyj", from);
    if (at === -1) return false;
    const first = scanTail(text, at + 3, (code) => ASCII_ALNUM.has(code) || JWT_EXTRA.has(code));
    if (first.ascii < detectorSpec.tails.jwt_first_minimum || text[first.end] !== ".") {
      from = at + 3;
      continue;
    }
    const second = scanTail(text, first.end + 1, (code) => ASCII_ALNUM.has(code) || JWT_EXTRA.has(code));
    if (tailHit(second, detectorSpec.tails.jwt_second_minimum)) return true;
    from = at + 3;
  }
  return false;
}

function hasDbScheme(text) {
  const folded = asciiFold(text);
  for (const scheme of policy.db_schemes) {
    if (folded.includes(asciiFold(scheme) + "://")) return true;
  }
  return false;
}

function hasUserinfo(text) {
  const scheme = text.indexOf("://");
  if (scheme === -1) return false;
  const rest = text.slice(scheme + 3);
  const slash = rest.indexOf("/");
  const authority = slash === -1 ? rest : rest.slice(0, slash);
  const at = authority.indexOf("@");
  return at > 0;
}

function hasSensitiveQuery(text) {
  const q = text.indexOf("?");
  if (q === -1) return false;
  const parts = text.slice(q + 1).split("#")[0].split("&");
  for (const part of parts) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    const name = asciiFold(part.slice(0, eq));
    if (policy.sensitive_query_names.includes(name)) return true;
  }
  return false;
}

function isUnicodeAlnum(ch) {
  const code = ch.codePointAt(0);
  if (ASCII_ALNUM.has(code)) return true;
  if (code < 128) return false;
  if (EMAIL_CATEGORIES.includes("L") && /^\p{L}$/u.test(ch)) return true;
  if (EMAIL_CATEGORIES.includes("N") && /^\p{N}$/u.test(ch)) return true;
  return false;
}

function emailIn(chars) {
  for (let i = 0; i < chars.length; i += 1) {
    if (chars[i] !== "@") continue;
    let left = i - 1;
    while (left >= 0 && (isUnicodeAlnum(chars[left]) || "._%+-".includes(chars[left]))) left -= 1;
    if (i - left - 1 < 1) continue;
    let right = i + 1;
    let dot = -1;
    while (right < chars.length && (isUnicodeAlnum(chars[right]) || chars[right] === "." || chars[right] === "-")) {
      if (chars[right] === ".") dot = right;
      right += 1;
    }
    if (dot > i + 1 && right - dot - 1 >= 2) return true;
  }
  return false;
}

function hasEmail(text) {
  if (typeof text !== "string" || text.length === 0) return false;
  return emailIn(Array.from(text.normalize("NFC")));
}

function hasSsn(text) {
  for (let i = 0; i + 11 <= text.length; i += 1) {
    if (i > 0 && isDigit(text[i - 1])) continue;
    if (!isDigit(text[i]) || !isDigit(text[i + 1]) || !isDigit(text[i + 2])) continue;
    if (text[i + 3] !== "-") continue;
    if (!isDigit(text[i + 4]) || !isDigit(text[i + 5])) continue;
    if (text[i + 6] !== "-") continue;
    if (!isDigit(text[i + 7]) || !isDigit(text[i + 8]) || !isDigit(text[i + 9]) || !isDigit(text[i + 10])) continue;
    if (i + 11 < text.length && isDigit(text[i + 11])) continue;
    return true;
  }
  return false;
}

function hasPhone(text) {
  for (let i = 0; i < text.length; i += 1) {
    let p = i;
    let separated = false;
    if (text[p] === "(") {
      if (!(isDigit(text[p + 1]) && isDigit(text[p + 2]) && isDigit(text[p + 3]) && text[p + 4] === ")")) continue;
      p += 5;
      separated = true;
    } else {
      if (!(isDigit(text[p]) && isDigit(text[p + 1]) && isDigit(text[p + 2]))) continue;
      p += 3;
    }
    if (p < text.length && (text[p] === "-" || text[p] === "." || text[p] === " ")) {
      separated = true;
      p += 1;
    }
    if (!(isDigit(text[p]) && isDigit(text[p + 1]) && isDigit(text[p + 2]))) continue;
    p += 3;
    if (p < text.length && (text[p] === "-" || text[p] === "." || text[p] === " ")) {
      separated = true;
      p += 1;
    }
    if (!separated) continue;
    if (!(isDigit(text[p]) && isDigit(text[p + 1]) && isDigit(text[p + 2]) && isDigit(text[p + 3]))) continue;
    const end = p + 4;
    const before = i > 0 ? text[i - 1] : "";
    const after = end < text.length ? text[end] : "";
    if ((before >= "0" && before <= "9") || (after >= "0" && after <= "9")) continue;
    return true;
  }
  return false;
}

function hasCard(text) {
  let i = 0;
  while (i < text.length) {
    if (!isDigit(text[i])) {
      i += 1;
      continue;
    }
    if (i > 0 && isDigit(text[i - 1])) {
      i += 1;
      continue;
    }
    let digits = 0;
    let separated = false;
    let j = i;
    while (j < text.length) {
      if (isDigit(text[j])) {
        digits += 1;
        separated = false;
        j += 1;
        continue;
      }
      if (PAN_SEPARATORS.has(unitCode(text[j])) && !separated && digits > 0 && isDigit(text[j + 1] || "")) {
        separated = true;
        j += 1;
        continue;
      }
      break;
    }
    if (digits >= detectorSpec.pan.min_digits && digits <= detectorSpec.pan.max_digits && (j >= text.length || !isDigit(text[j]))) {
      const before = i > 0 ? text[i - 1] : "";
      const after = j < text.length ? text[j] : "";
      const suppresses = (ch) => inClass(ch, ASCII_ALPHA);
      if (!suppresses(before) && !suppresses(after)) return true;
    }
    i = Math.max(j, i + 1);
  }
  return false;
}

function hasMrn(text) {
  const prefix = detectorSpec.prefixes_intentionally_case_sensitive[0];
  let from = 0;
  while (from < text.length) {
    const at = text.indexOf(prefix, from);
    if (at === -1) return false;
    const scanned = scanTail(text, at + prefix.length, (code) => ASCII_ALNUM.has(code));
    if (tailHit(scanned, detectorSpec.tails.mrn_minimum)) return true;
    from = at + prefix.length;
  }
  return false;
}

function hasUsernamePath(text) {
  for (const marker of policy.username_path_markers) {
    if (text.includes(marker)) return true;
  }
  return false;
}

function scanDirect(text) {
  if (!text) return false;
  return hasPem(text)
    || hasBearer(text)
    || hasBasic(text)
    || hasCookieMarker(text)
    || hasOpenAiKey(text)
    || hasCloudKey(text)
    || hasJwt(text)
    || hasDbScheme(text)
    || hasUserinfo(text)
    || hasSensitiveQuery(text)
    || hasEmail(text)
    || hasSsn(text)
    || hasPhone(text)
    || hasCard(text)
    || hasMrn(text);
}

function percentDecodeOnce(text) {
  if (!text.includes("%")) return { changed: false, text, prohibited: false };
  const bytes = [];
  let changed = false;
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    if (text[i] === "%" && i + 2 < text.length && isHexChar(text[i + 1]) && isHexChar(text[i + 2])) {
      bytes.push(parseInt(text.slice(i + 1, i + 3), 16));
      changed = true;
      i += 2;
      continue;
    }
    if (code > 127) return { changed: true, text: "", prohibited: true };
    bytes.push(code);
  }
  if (!changed) return { changed: false, text, prohibited: false };
  try {
    const decoded = new TextDecoder("utf-8", { fatal: true }).decode(Uint8Array.from(bytes));
    return { changed: true, text: decoded, prohibited: false };
  } catch {
    return { changed: true, text: "", prohibited: true };
  }
}

function foldDetection(text) {
  const nfkc = text.normalize("NFKC");
  let out = "";
  for (const ch of nfkc) {
    out += CONFUSABLE.get(ch) || ch;
  }
  return out;
}

function isBase64Char(ch, allowSlash) {
  const code = unitCode(ch);
  if (code < 0 || code > detectorSpec.non_ascii.min_exclusive) return false;
  if (ASCII_ALNUM.has(code) || BASE64_EXTRA.has(code)) return true;
  return allowSlash && code === detectorSpec.base64_slash;
}

const B64_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

function decodeBase64(run) {
  if (run.length % 4 !== 0) return null;
  const bytes = [];
  for (let i = 0; i < run.length; i += 4) {
    const c0 = B64_ALPHA.indexOf(run[i]);
    const c1 = B64_ALPHA.indexOf(run[i + 1]);
    const c2raw = run[i + 2];
    const c3raw = run[i + 3];
    const c2 = c2raw === "=" ? 0 : B64_ALPHA.indexOf(c2raw);
    const c3 = c3raw === "=" ? 0 : B64_ALPHA.indexOf(c3raw);
    if (c0 < 0 || c1 < 0 || c2 < 0 || c3 < 0) return null;
    if (c2raw === "=" && c3raw !== "=") return null;
    if (c2raw !== "=" && c3raw === "=" && run.slice(i + 4).includes("=")) return null;
    bytes.push((c0 << 2) | (c1 >> 4));
    if (c2raw !== "=") bytes.push(((c1 & 15) << 4) | (c2 >> 2));
    if (c3raw !== "=") bytes.push(((c2 & 3) << 6) | c3);
  }
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(Uint8Array.from(bytes));
  } catch {
    return null;
  }
}

function scanBase64Runs(text, allowSlash) {
  let i = 0;
  while (i < text.length) {
    if (!isBase64Char(text[i], allowSlash) && text[i] !== "=") {
      i += 1;
      continue;
    }
    const start = i;
    while (i < text.length && isBase64Char(text[i], allowSlash)) i += 1;
    let pads = 0;
    while (i < text.length && text[i] === "=" && pads < 2) {
      pads += 1;
      i += 1;
    }
    const run = text.slice(start, i);
    if (allowSlash && !run.includes("+") && !run.includes("=")) continue;
    const bodyLen = run.length - pads;
    if (bodyLen < policy.base64_min_run) continue;
    if (run.length > policy.base64_max_run) return true;
    const interesting = pads > 0 || run.includes("+") || /[A-Z]/.test(run);
    if (!interesting) continue;
    if (run.length % 4 !== 0) continue;
    const decoded = decodeBase64(run);
    if (decoded && scanDirect(decoded)) return true;
  }
  return false;
}

function scanBase64(text) {
  if (scanBase64Runs(text, false)) return true;
  if ((text.includes("=") || text.includes("+")) && text.includes("/") && scanBase64Runs(text, true)) return true;
  return false;
}

function containsProhibited(value) {
  if (typeof value !== "string" || value.length === 0) return false;
  if (Buffer.byteLength(value, "utf8") > detectorSpec.max_scan_bytes) return true;
  if (scanDirect(value)) return true;
  const decoded = percentDecodeOnce(value);
  if (decoded.prohibited) return true;
  if (decoded.changed && scanDirect(decoded.text)) return true;
  if (scanBase64(value)) return true;
  const folded = foldDetection(value);
  if (folded !== value && scanDirect(folded)) return true;
  if (decoded.changed) {
    const foldedDecoded = foldDetection(decoded.text);
    if (foldedDecoded !== decoded.text && scanDirect(foldedDecoded)) return true;
  }
  return false;
}

function sensitivePath(text) {
  if (typeof text !== "string" || text.length === 0) return false;
  const nfc = text.normalize("NFC");
  if (containsProhibited(text) || containsProhibited(nfc) || hasUsernamePath(text) || hasUsernamePath(nfc)) return true;
  const decoded = percentDecodeOnce(nfc);
  if (decoded.prohibited) return true;
  if (!decoded.changed) return false;
  const form = decoded.text.normalize("NFC");
  return containsProhibited(form) || hasUsernamePath(form);
}

module.exports = {
  policy,
  normalizeName,
  comparisonForm,
  classifyFieldName,
  isProhibitedName,
  isPayloadName,
  isBaggageName,
  containsProhibited,
  asciiFold,
  asciiFoldUpper,
  detectorSpec,
  hasUsernamePath,
  hasDbScheme,
  hasSensitiveQuery,
  sensitivePath,
  percentDecodeOnce,
  scanDirect,
};
