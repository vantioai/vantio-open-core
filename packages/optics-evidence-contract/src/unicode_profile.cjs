"use strict";

const { createHash } = require("crypto");
const { readFileSync, statSync } = require("fs");
const path = require("path");

const CONTRACT_DIR = path.join(__dirname, "..", "contract");
const MAX_FILE_BYTES = 8000000;
const SCALAR = 0x110000;

let ready = false;
let loadError = "UNLOADED";
let forcedOff = false;
let profileId = null;
let profileVersion = null;
let bounds = null;
let canonical = new Map();
let compatibility = new Map();
let combining = new Map();
let exclusion = new Set();
let composeMap = new Map();
let letterRanges = [];
let numberRanges = [];
let otherRanges = [];
let formatRanges = [];
let hangul = null;
let maxDepth = 32;

function readBounded(name) {
  const full = path.join(CONTRACT_DIR, name);
  const size = statSync(full).size;
  if (size <= 0 || size > MAX_FILE_BYTES) {
    throw new Error("UNICODE_PROFILE_SIZE");
  }
  return readFileSync(full);
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function inRanges(ranges, code) {
  let lo = 0;
  let hi = ranges.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const start = ranges[mid][0];
    const end = ranges[mid][1];
    if (code < start) hi = mid - 1;
    else if (code > end) lo = mid + 1;
    else return true;
  }
  return false;
}

function hangulDecompose(code) {
  const index = code - hangul.sbase;
  if (index < 0 || index >= hangul.scount) return null;
  const lIndex = Math.floor(index / hangul.ncount);
  const vIndex = Math.floor((index % hangul.ncount) / hangul.tcount);
  const tIndex = index % hangul.tcount;
  const lead = hangul.lbase + lIndex;
  const vowel = hangul.vbase + vIndex;
  if (tIndex === 0) return [lead, vowel];
  return [lead, vowel, hangul.tbase + tIndex];
}

function ccc(code) {
  return combining.get(code) || 0;
}

function mapping(code, useCompatibility) {
  const hangulParts = hangulDecompose(code);
  if (hangulParts) return hangulParts;
  if (useCompatibility && compatibility.has(code)) return compatibility.get(code);
  if (canonical.has(code)) return canonical.get(code);
  return null;
}

function decomposeFully(codes, useCompatibility) {
  const out = [];
  function rec(code, depth) {
    if (depth > maxDepth) {
      const error = new Error("UNICODE_PROFILE_DEPTH");
      error.code = "UNICODE_PROFILE_DEPTH";
      throw error;
    }
    const seq = mapping(code, useCompatibility);
    if (seq) {
      for (let i = 0; i < seq.length; i += 1) rec(seq[i], depth + 1);
      return;
    }
    out.push(code);
  }
  for (let i = 0; i < codes.length; i += 1) rec(codes[i], 0);
  let changed = true;
  while (changed) {
    changed = false;
    for (let index = 0; index < out.length - 1; index += 1) {
      const left = ccc(out[index]);
      const right = ccc(out[index + 1]);
      if (left > right && right > 0) {
        const swap = out[index];
        out[index] = out[index + 1];
        out[index + 1] = swap;
        changed = true;
      }
    }
  }
  return out;
}

function composePair(left, right) {
  const lIndex = left - hangul.lbase;
  if (lIndex >= 0 && lIndex < hangul.lcount) {
    const vIndex = right - hangul.vbase;
    if (vIndex >= 0 && vIndex < hangul.vcount) {
      return hangul.sbase + (lIndex * hangul.vcount + vIndex) * hangul.tcount;
    }
  }
  const sIndex = left - hangul.sbase;
  if (sIndex >= 0 && sIndex < hangul.scount && sIndex % hangul.tcount === 0) {
    const tIndex = right - hangul.tbase;
    if (tIndex > 0 && tIndex < hangul.tcount) return left + tIndex;
  }
  const key = left * SCALAR + right;
  return composeMap.has(key) ? composeMap.get(key) : null;
}

function compose(codes) {
  if (codes.length === 0) return [];
  const result = [codes[0]];
  let starter = ccc(codes[0]) === 0 ? 0 : null;
  let previous = 0;
  for (let index = 1; index < codes.length; index += 1) {
    const code = codes[index];
    const cc = ccc(code);
    if (starter !== null && (previous < cc || previous === 0)) {
      const composed = composePair(result[starter], code);
      if (composed !== null) {
        result[starter] = composed;
        continue;
      }
    }
    result.push(code);
    if (cc === 0) {
      starter = result.length - 1;
      previous = 0;
    } else previous = cc;
  }
  return result;
}

function toCodes(text) {
  const codes = [];
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = text.charCodeAt(i + 1);
      if (next >= 0xdc00 && next <= 0xdfff) {
        codes.push(((code - 0xd800) << 10) + (next - 0xdc00) + 0x10000);
        i += 1;
        continue;
      }
      return null;
    }
    if (code >= 0xdc00 && code <= 0xdfff) return null;
    codes.push(code);
  }
  return codes;
}

function fromCodes(codes) {
  let out = "";
  for (let i = 0; i < codes.length; i += 1024) {
    out += String.fromCodePoint.apply(null, codes.slice(i, i + 1024));
  }
  return out;
}

function utf8Length(codes) {
  let total = 0;
  for (let i = 0; i < codes.length; i += 1) {
    const code = codes[i];
    if (code <= 0x7f) total += 1;
    else if (code <= 0x7ff) total += 2;
    else if (code <= 0xffff) total += 3;
    else total += 4;
  }
  return total;
}

function buildCompose() {
  composeMap = new Map();
  for (const [code, seq] of canonical) {
    if (exclusion.has(code)) continue;
    if (seq.length === 2 && ccc(seq[0]) === 0) composeMap.set(seq[0] * SCALAR + seq[1], code);
  }
}

function loadPairMap(pairs) {
  const map = new Map();
  for (let i = 0; i < pairs.length; i += 1) map.set(pairs[i][0], pairs[i][1]);
  return map;
}

function categoryLookup(code) {
  if (inRanges(letterRanges, code)) return "LETTER";
  if (inRanges(numberRanges, code)) return "NUMBER";
  if (inRanges(otherRanges, code)) return "OTHER";
  return "UNKNOWN_TO_PROFILE";
}

function checkVectors(vectors) {
  for (let i = 0; i < vectors.length; i += 1) {
    const vector = vectors[i];
    const normalized = compose(decomposeFully(vector.input, vector.form === "NFKC"));
    if (normalized.length !== vector.output.length) return false;
    for (let j = 0; j < normalized.length; j += 1) {
      if (normalized[j] !== vector.output[j]) return false;
    }
    if (categoryLookup(vector.input[0]) !== vector.category) return false;
  }
  return true;
}

function loadProfile() {
  const metadataBytes = readBounded("unicode-profile-metadata.json");
  const metadata = JSON.parse(metadataBytes.toString("utf8"));
  const outputs = {};
  for (const item of metadata.outputs) outputs[item.name] = item.sha256;
  const names = ["unicode-profile.json", "unicode-nfkc-map.json", "unicode-category-ranges.json"];
  const parsed = {};
  for (const name of names) {
    const bytes = readBounded(name);
    if (sha256(bytes) !== outputs[name]) throw new Error("UNICODE_PROFILE_HASH");
    parsed[name] = JSON.parse(bytes.toString("utf8"));
  }
  for (const source of metadata.sources) {
    const bytes = readBounded(path.join("unicode-source", source.name));
    if (sha256(bytes) !== source.sha256) throw new Error("UNICODE_PROFILE_SOURCE_HASH");
  }
  const profile = parsed["unicode-profile.json"];
  const mapFile = parsed["unicode-nfkc-map.json"];
  const categories = parsed["unicode-category-ranges.json"];
  if (profile.id !== metadata.profile_id || profile.profile_version !== metadata.profile_version) {
    throw new Error("UNICODE_PROFILE_ID");
  }
  if (mapFile.profile_id !== profile.id || categories.profile_id !== profile.id) {
    throw new Error("UNICODE_PROFILE_ID");
  }
  profileId = profile.id;
  profileVersion = profile.profile_version;
  bounds = profile.bounds;
  hangul = mapFile.hangul;
  maxDepth = mapFile.max_decomposition_depth;
  canonical = loadPairMap(mapFile.canonical);
  compatibility = loadPairMap(mapFile.compatibility);
  combining = new Map(mapFile.combining_class);
  exclusion = new Set(mapFile.composition_exclusion);
  letterRanges = categories.letter;
  numberRanges = categories.number;
  otherRanges = categories.other;
  formatRanges = categories.format_controls;
  buildCompose();
  if (!checkVectors(profile.verification_vectors)) throw new Error("UNICODE_PROFILE_VECTOR");
  ready = true;
  loadError = null;
}

try {
  loadProfile();
} catch (error) {
  ready = false;
  loadError = "UNICODE_PROFILE_UNAVAILABLE";
}

function profileReady() {
  return ready && !forcedOff;
}

function setProfileUnavailableForTest(flag) {
  forcedOff = flag === true;
}

function categoryOf(code) {
  if (!profileReady()) return "UNKNOWN_TO_PROFILE";
  return categoryLookup(code);
}

function isFormat(code) {
  if (!profileReady()) return false;
  return inRanges(formatRanges, code);
}

function normalizeCodes(codes, form) {
  if (form !== "NFC" && form !== "NFKC") return { ok: false, reason: "FORM" };
  if (!profileReady()) return { ok: false, reason: "PROFILE" };
  if (codes.length > bounds.max_code_points) return { ok: false, reason: "BOUND" };
  const inputBytes = utf8Length(codes);
  if (inputBytes > bounds.max_input_bytes) return { ok: false, reason: "BOUND" };
  let ascii = true;
  for (let i = 0; i < codes.length; i += 1) {
    if (codes[i] > 127) {
      ascii = false;
      break;
    }
  }
  if (ascii) return { ok: true, codes };
  let normalized;
  try {
    normalized = compose(decomposeFully(codes, form === "NFKC"));
  } catch (error) {
    return { ok: false, reason: "DEPTH" };
  }
  const outputBytes = utf8Length(normalized);
  const ratio = outputBytes / (inputBytes || 1);
  if (outputBytes > bounds.max_output_bytes || ratio > bounds.max_expansion_ratio) {
    return { ok: false, reason: "EXPANSION" };
  }
  return { ok: true, codes: normalized };
}

function normalizeText(text, form) {
  if (typeof text !== "string") return { ok: false, reason: "TYPE" };
  if (!profileReady()) return { ok: false, reason: "PROFILE" };
  const codes = toCodes(text);
  if (!codes) return { ok: false, reason: "MALFORMED" };
  const normalized = normalizeCodes(codes, form);
  if (!normalized.ok) return normalized;
  return { ok: true, text: fromCodes(normalized.codes) };
}

module.exports = {
  profileReady,
  setProfileUnavailableForTest,
  profileId: () => profileId,
  profileVersion: () => profileVersion,
  loadError: () => loadError,
  categoryOf,
  isFormat,
  normalizeText,
  normalizeCodes,
  toCodes,
  MAX_FILE_BYTES,
};
