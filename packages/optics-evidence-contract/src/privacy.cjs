"use strict";

const { readFileSync } = require("fs");
const path = require("path");
const unicode = require("./unicode_profile.cjs");

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

function contractForm(text, form) {
  const normalized = unicode.normalizeText(text, form);
  if (!normalized.ok) return null;
  return normalized.text;
}

function contractNfc(text) {
  return contractForm(text, "NFC");
}

function stripFormat(text) {
  const parts = [];
  let changed = false;
  for (const ch of text) {
    if (unicode.isFormat(ch.codePointAt(0))) {
      changed = true;
      continue;
    }
    parts.push(ch);
  }
  return changed ? parts.join("") : text;
}

function codeUnitAt(text, index) {
  const code = text.charCodeAt(index);
  if (code >= 0xd800 && code <= 0xdbff) {
    const next = text.charCodeAt(index + 1);
    if (next >= 0xdc00 && next <= 0xdfff) {
      return { ch: text.slice(index, index + 2), size: 2, nonAscii: true };
    }
  }
  return { ch: text[index], size: 1, nonAscii: code > detectorSpec.non_ascii.min_exclusive };
}

function matchPrefixAt(text, prefix, index, caseSensitive) {
  let cursor = index;
  let skipped = 0;
  const budget = 1;
  for (let part = 0; part < prefix.length; part += 1) {
    if (cursor >= text.length) return -1;
    const unit = codeUnitAt(text, cursor);
    const same = caseSensitive ? unit.ch === prefix[part] : asciiFold(unit.ch) === asciiFold(prefix[part]);
    if (same && unit.size === 1) {
      cursor += 1;
      continue;
    }
    if (part > 0 && skipped < budget && unit.nonAscii) {
      skipped += 1;
      cursor += unit.size;
      part -= 1;
      continue;
    }
    return -1;
  }
  return cursor;
}

function utf8Prefix(text, maxBytes) {
  let bytes = 0;
  let index = 0;
  while (index < text.length) {
    const code = text.codePointAt(index);
    const width = code <= 0x7f ? 1 : code <= 0x7ff ? 2 : code <= 0xffff ? 3 : 4;
    const step = code > 0xffff ? 2 : 1;
    if (bytes + width > maxBytes) break;
    bytes += width;
    index += step;
  }
  return text.slice(0, index);
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
  let text = contractForm(name, "NFC");
  if (text == null) return "";
  const decoded = percentDecodeOnce(text);
  if (decoded.changed && !decoded.prohibited && decoded.text) {
    text = contractForm(decoded.text, "NFC");
    if (text == null) return "";
  }
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
  const nfcName = contractForm(name, "NFC");
  const safeGrammar = !control && !detector && !oversized && nfcName === name && SAFE_NAME.test(name);
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
  for (let index = 0; index < text.length; index += 1) {
    const end = matchPrefixAt(text, "Bearer", index, false);
    if (end < 0) continue;
    let cursor = end;
    if (cursor >= text.length || (text[cursor] !== " " && text[cursor] !== "\t")) continue;
    while (cursor < text.length && (text[cursor] === " " || text[cursor] === "\t")) cursor += 1;
    const scanned = scanTail(text, cursor, (code) => ASCII_ALNUM.has(code) || BEARER_EXTRA.has(code));
    if (tailHit(scanned, detectorSpec.tails.bearer.minimum)) return true;
  }
  return false;
}

function hasBasic(text) {
  for (let index = 0; index < text.length; index += 1) {
    const end = matchPrefixAt(text, "Basic", index, false);
    if (end < 0) continue;
    let cursor = end;
    if (cursor >= text.length || (text[cursor] !== " " && text[cursor] !== "\t")) continue;
    while (cursor < text.length && (text[cursor] === " " || text[cursor] === "\t")) cursor += 1;
    const scanned = scanTail(text, cursor, (code) => ASCII_ALNUM.has(code) || BASIC_EXTRA.has(code));
    if (tailHit(scanned, detectorSpec.tails.basic.minimum)) return true;
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
  for (let index = 0; index < text.length; index += 1) {
    for (const prefix of prefixes) {
      const end = matchPrefixAt(text, prefix, index, false);
      if (end < 0) continue;
      const scanned = scanTail(text, end, (code) => ASCII_ALNUM.has(code));
      if (tailHit(scanned, policy.openai_tail_min)) return true;
    }
  }
  return false;
}

function hasMarker(text, marker, caseSensitive) {
  for (let index = 0; index < text.length; index += 1) {
    if (matchPrefixAt(text, marker, index, caseSensitive) >= 0) return true;
  }
  return false;
}

function hasCloudKey(text) {
  for (let index = 0; index < text.length; index += 1) {
    for (const head of detectorSpec.akia_prefixes) {
      const end = matchPrefixAt(text, head, index, false);
      if (end < 0) continue;
      const scanned = scanTail(text, end, (code) => ASCII_ALNUM.has(code));
      if (tailHit(scanned, policy.cloud_akia_tail)) return true;
    }
  }
  for (const marker of detectorSpec.presence_markers_ascii_case_insensitive) {
    if (hasMarker(text, marker, false)) return true;
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
  for (let index = 0; index < text.length; index += 1) {
    const end = matchPrefixAt(text, "eyJ", index, false);
    if (end < 0) continue;
    const first = scanTail(text, end, (code) => ASCII_ALNUM.has(code) || JWT_EXTRA.has(code));
    if (first.ascii < detectorSpec.tails.jwt_first_minimum || text[first.end] !== ".") continue;
    const second = scanTail(text, first.end + 1, (code) => ASCII_ALNUM.has(code) || JWT_EXTRA.has(code));
    if (tailHit(second, detectorSpec.tails.jwt_second_minimum)) return true;
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

function emailClass(ch) {
  const code = ch.codePointAt(0);
  if (ASCII_ALNUM.has(code)) return "ALNUM";
  if (code < 128) return "OTHER";
  const category = unicode.categoryOf(code);
  if (category === "UNKNOWN_TO_PROFILE") return "UNKNOWN";
  if (category === "LETTER" || category === "NUMBER") return "ALNUM";
  return "OTHER";
}

function emailIn(chars) {
  for (let i = 0; i < chars.length; i += 1) {
    if (chars[i] !== "@") continue;
    let left = i - 1;
    let unknown = false;
    while (left >= 0) {
      const kind = emailClass(chars[left]);
      if (kind === "ALNUM" || "._%+-".includes(chars[left])) {
        left -= 1;
        continue;
      }
      if (kind === "UNKNOWN") {
        unknown = true;
        left -= 1;
        continue;
      }
      break;
    }
    if (i - left - 1 < 1 && !unknown) continue;
    let right = i + 1;
    let dot = -1;
    while (right < chars.length) {
      const kind = emailClass(chars[right]);
      if (kind === "ALNUM" || chars[right] === "." || chars[right] === "-") {
        if (chars[right] === ".") dot = right;
        right += 1;
        continue;
      }
      if (kind === "UNKNOWN") {
        unknown = true;
        right += 1;
        continue;
      }
      break;
    }
    if (unknown && (dot !== -1 || i - left - 1 >= 1)) return true;
    if (dot > i + 1 && right - dot - 1 >= 2) return true;
  }
  return false;
}

function hasEmail(text) {
  if (typeof text !== "string" || text.length === 0) return false;
  const nfc = contractForm(text, "NFC");
  if (nfc == null) return true;
  return emailIn(Array.from(nfc));
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
  for (let index = 0; index < text.length; index += 1) {
    const end = matchPrefixAt(text, prefix, index, true);
    if (end < 0) continue;
    const scanned = scanTail(text, end, (code) => ASCII_ALNUM.has(code));
    if (tailHit(scanned, detectorSpec.tails.mrn_minimum)) return true;
  }
  return false;
}

function hasUsernamePath(text) {
  for (const marker of policy.username_path_markers) {
    if (text.includes(marker)) return true;
  }
  return false;
}

function scanDirectRaw(text) {
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

function scanDirect(text) {
  if (!text) return false;
  if (scanDirectRaw(text)) return true;
  const view = stripFormat(text);
  return view !== text && scanDirectRaw(view);
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
  const nfkc = contractForm(text, "NFKC");
  if (nfkc == null) return null;
  const parts = [];
  for (const ch of nfkc) parts.push(CONFUSABLE.get(ch) || ch);
  return parts.join("");
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

function scanAll(text) {
  if (scanDirect(text)) return true;
  const decoded = percentDecodeOnce(text);
  if (decoded.prohibited) return true;
  if (decoded.changed && decoded.text && scanDirect(decoded.text)) return true;
  if (scanBase64(text)) return true;
  const folded = foldDetection(text);
  if (folded == null) return true;
  if (folded !== text && scanDirect(folded)) return true;
  if (decoded.changed && decoded.text) {
    const foldedDecoded = foldDetection(decoded.text);
    if (foldedDecoded == null) return true;
    if (foldedDecoded !== decoded.text && scanDirect(foldedDecoded)) return true;
  }
  return false;
}

function containsProhibited(value) {
  if (typeof value !== "string" || value.length === 0) return false;
  if (!unicode.profileReady()) return true;
  const size = Buffer.byteLength(value, "utf8");
  const text = size > detectorSpec.max_scan_bytes ? utf8Prefix(value, detectorSpec.max_scan_bytes) : value;
  return scanAll(text);
}

function boundaryCandidate(prefix) {
  const view = stripFormat(prefix);
  if (!view) return false;
  let index = view.length - 1;
  let digits = 0;
  while (index >= 0 && isDigit(view[index])) {
    digits += 1;
    index -= 1;
  }
  if (digits > 0 && digits < detectorSpec.pan.min_digits) {
    const before = index >= 0 ? view[index] : "";
    if (!inClass(before, ASCII_ALPHA)) return true;
  }
  const windowStart = Math.max(0, view.length - 80);
  const heads = detectorSpec.akia_prefixes.concat(policy.openai_prefixes);
  for (let start = windowStart; start < view.length; start += 1) {
    for (const head of heads) {
      const end = matchPrefixAt(view, head, start, false);
      if (end < 0) continue;
      if (end >= view.length) return true;
      const scanned = scanTail(view, end, (code) => ASCII_ALNUM.has(code));
      const minimum = detectorSpec.akia_prefixes.indexOf(head) >= 0 ? policy.cloud_akia_tail : policy.openai_tail_min;
      if (scanned.end === view.length && scanned.ascii < minimum) return true;
    }
  }
  const at = view.lastIndexOf("@");
  if (at >= windowStart && at < view.length - 1) {
    let domain = true;
    for (let cursor = at + 1; cursor < view.length; cursor += 1) {
      const kind = emailClass(view[cursor]);
      if (!(kind === "ALNUM" || kind === "UNKNOWN" || view[cursor] === "." || view[cursor] === "-")) {
        domain = false;
        break;
      }
    }
    if (domain) {
      const dot = view.lastIndexOf(".");
      if (dot < at || view.length - dot - 1 < 2) return true;
    }
  }
  return false;
}

function scanBoundedPrefix(text) {
  if (typeof text !== "string" || text.length === 0) return { matched: false, boundary: false };
  if (!unicode.profileReady()) return { matched: true, boundary: false };
  const prefix = utf8Prefix(text, detectorSpec.max_scan_bytes);
  const matched = containsProhibited(prefix);
  const cut = Buffer.byteLength(text, "utf8") > Buffer.byteLength(prefix, "utf8");
  return { matched, boundary: cut && !matched && boundaryCandidate(prefix) };
}

function sensitivePath(text) {
  if (typeof text !== "string" || text.length === 0) return false;
  if (!unicode.profileReady()) return true;
  const nfc = contractForm(text, "NFC");
  if (nfc == null) return true;
  if (containsProhibited(text) || containsProhibited(nfc) || hasUsernamePath(text) || hasUsernamePath(nfc)) return true;
  const decoded = percentDecodeOnce(nfc);
  if (decoded.prohibited) return true;
  if (!decoded.changed) return false;
  const form = contractForm(decoded.text, "NFC");
  if (form == null) return true;
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
  contractNfc,
  scanBoundedPrefix,
  profileReady: unicode.profileReady,
  profileId: unicode.profileId,
  profileVersion: unicode.profileVersion,
  setProfileUnavailableForTest: unicode.setProfileUnavailableForTest,
  detectorSpec,
  hasUsernamePath,
  hasDbScheme,
  hasSensitiveQuery,
  sensitivePath,
  percentDecodeOnce,
  scanDirect,
};
