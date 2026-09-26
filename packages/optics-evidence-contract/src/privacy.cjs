"use strict";

const { readFileSync } = require("fs");
const path = require("path");

const policy = JSON.parse(
  readFileSync(path.join(__dirname, "..", "contract", "prohibited-fields.json"), "utf8"),
);

const CONFUSABLE = new Map(policy.confusables);

function normalizeName(name) {
  return String(name).toLowerCase().replace(/[-_\s]/g, "");
}

const NAME_SET = new Set(policy.prohibited_field_names.map((name) => normalizeName(name)));
const PAYLOAD_SET = new Set(policy.payload_drop_record_names.map((name) => normalizeName(name)));
const BAGGAGE_SET = new Set(policy.baggage_names.map((name) => normalizeName(name)));

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
  return (ch >= "0" && ch <= "9") || (ch >= "a" && ch <= "f") || (ch >= "A" && ch <= "F");
}

function isDigit(ch) {
  return ch >= "0" && ch <= "9";
}

function startsWithFold(text, prefix, index) {
  if (index + prefix.length > text.length) return false;
  for (let i = 0; i < prefix.length; i += 1) {
    const left = text[index + i];
    const right = prefix[i];
    if (left.toLowerCase() !== right.toLowerCase()) return false;
  }
  return true;
}

function hasBearer(text) {
  const lower = text.toLowerCase();
  let from = 0;
  while (from < lower.length) {
    const at = lower.indexOf("bearer", from);
    if (at === -1) return false;
    let i = at + 6;
    if (i >= text.length || (text[i] !== " " && text[i] !== "\t")) {
      from = at + 6;
      continue;
    }
    while (i < text.length && (text[i] === " " || text[i] === "\t")) i += 1;
    let n = 0;
    while (i < text.length) {
      const ch = text[i];
      const ok = (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9")
        || ch === "-" || ch === "." || ch === "_" || ch === "~" || ch === "+" || ch === "/" || ch === "=";
      if (!ok) break;
      n += 1;
      i += 1;
    }
    if (n >= 8) return true;
    from = at + 6;
  }
  return false;
}

function hasBasic(text) {
  const lower = text.toLowerCase();
  let from = 0;
  while (from < lower.length) {
    const at = lower.indexOf("basic", from);
    if (at === -1) return false;
    let i = at + 5;
    if (i >= text.length || (text[i] !== " " && text[i] !== "\t")) {
      from = at + 5;
      continue;
    }
    while (i < text.length && (text[i] === " " || text[i] === "\t")) i += 1;
    let n = 0;
    while (i < text.length) {
      const ch = text[i];
      const ok = (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9")
        || ch === "+" || ch === "/" || ch === "=";
      if (!ok) break;
      n += 1;
      i += 1;
    }
    if (n >= 8) return true;
    from = at + 5;
  }
  return false;
}

function hasCookieMarker(text) {
  const lower = text.toLowerCase();
  if (lower.includes("set-cookie")) return true;
  if (lower.includes("cookie:")) return true;
  if (lower.includes("cookie=")) return true;
  return false;
}

function hasOpenAiKey(text) {
  const prefixes = policy.openai_prefixes;
  for (let i = 0; i < text.length; i += 1) {
    for (const prefix of prefixes) {
      if (!startsWithFold(text, prefix, i)) continue;
      let n = 0;
      let j = i + prefix.length;
      while (j < text.length) {
        const ch = text[j];
        const ok = (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9");
        if (!ok) break;
        n += 1;
        j += 1;
      }
      if (n >= policy.openai_tail_min) return true;
    }
  }
  return false;
}

function hasCloudKey(text) {
  for (let i = 0; i + 20 <= text.length; i += 1) {
    const head = text.slice(i, i + 4);
    if ((head === "AKIA" || head === "ASIA") && isCloudTail(text, i + 4)) return true;
  }
  if (text.includes("AIza") || text.includes("ya29.")) return true;
  const markers = ["xoxb-", "xoxp-", "xoxa-", "ghp_", "github_pat_"];
  for (const marker of markers) {
    if (text.includes(marker)) return true;
  }
  return false;
}

function isCloudTail(text, start) {
  if (start + policy.cloud_akia_tail > text.length) return false;
  for (let i = 0; i < policy.cloud_akia_tail; i += 1) {
    const ch = text[start + i];
    const ok = (ch >= "A" && ch <= "Z") || (ch >= "0" && ch <= "9");
    if (!ok) return false;
  }
  return true;
}

function hasPem(text) {
  const upper = text.toUpperCase();
  for (const marker of policy.pem_markers) {
    if (upper.includes(marker)) return true;
  }
  return false;
}

function hasJwt(text) {
  let from = 0;
  while (from < text.length) {
    const at = text.indexOf("eyJ", from);
    if (at === -1) return false;
    const dot = text.indexOf(".", at + 3);
    if (dot === -1 || dot - (at + 3) < 8) {
      from = at + 3;
      continue;
    }
    let n = 0;
    let i = dot + 1;
    while (i < text.length) {
      const ch = text[i];
      const ok = (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9")
        || ch === "-" || ch === "_";
      if (!ok) break;
      n += 1;
      i += 1;
    }
    if (n >= 4) return true;
    from = at + 3;
  }
  return false;
}

function hasDbScheme(text) {
  const lower = text.toLowerCase();
  for (const scheme of policy.db_schemes) {
    if (lower.includes(scheme + "://")) return true;
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
    const name = part.slice(0, eq).toLowerCase();
    if (policy.sensitive_query_names.includes(name)) return true;
  }
  return false;
}

function hasEmail(text) {
  const localOk = (ch) => (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9")
    || ch === "." || ch === "_" || ch === "%" || ch === "+" || ch === "-";
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] !== "@") continue;
    let left = i - 1;
    while (left >= 0 && localOk(text[left])) left -= 1;
    if (i - left - 1 < 1) continue;
    let right = i + 1;
    let dot = -1;
    while (right < text.length) {
      const ch = text[right];
      const ok = (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9")
        || ch === "." || ch === "-";
      if (!ok) break;
      if (ch === ".") dot = right;
      right += 1;
    }
    if (dot > i + 1 && right - dot - 1 >= 2) return true;
  }
  return false;
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
      if ((text[j] === " " || text[j] === "-") && !separated && digits > 0 && isDigit(text[j + 1] || "")) {
        separated = true;
        j += 1;
        continue;
      }
      break;
    }
    if (digits >= 13 && digits <= 19 && (j >= text.length || !isDigit(text[j]))) {
      const before = i > 0 ? text[i - 1] : "";
      const after = j < text.length ? text[j] : "";
      const letter = (ch) => (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z");
      if (!letter(before) && !letter(after)) return true;
    }
    i = Math.max(j, i + 1);
  }
  return false;
}

function hasMrn(text) {
  let from = 0;
  while (from < text.length) {
    const at = text.indexOf("MRN:", from);
    if (at === -1) return false;
    let n = 0;
    let i = at + 4;
    while (i < text.length) {
      const ch = text[i];
      const ok = (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9");
      if (!ok) break;
      n += 1;
      i += 1;
    }
    if (n >= 6) return true;
    from = at + 4;
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
  return (ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z") || (ch >= "0" && ch <= "9") || ch === "+" || (allowSlash && ch === "/");
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
  if (value.length > 8192) return true;
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

module.exports = {
  policy,
  normalizeName,
  isProhibitedName,
  isPayloadName,
  isBaggageName,
  containsProhibited,
  hasUsernamePath,
  hasDbScheme,
  hasSensitiveQuery,
  scanDirect,
};
