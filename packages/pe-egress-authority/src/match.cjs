"use strict";

// Hostname rule matches llm-hosts.cjs hostListed at 89f95099:
// exact, or suffix only when the listed name contains a dot.

function hostListed(hostname, items) {
  const h = String(hostname || "").toLowerCase();
  if (!h) return false;
  const arr = Array.isArray(items) ? items : [];
  for (const item of arr) {
    const b = String(item || "").toLowerCase().trim();
    if (!b) continue;
    if (h === b) return true;
    if (b.includes(".") && h.endsWith("." + b)) return true;
  }
  return false;
}

function ipv4ToInt(ip) {
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(ip);
  if (!m) return null;
  const parts = [m[1], m[2], m[3], m[4]].map((p) => Number(p));
  if (parts.some((n) => n > 255)) return null;
  return (((parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]) >>> 0);
}

function inCidr4(ip, cidr) {
  const slash = cidr.indexOf("/");
  if (slash <= 0) return null;
  const bits = Number(cidr.slice(slash + 1));
  if (!Number.isInteger(bits) || bits < 0 || bits > 32) return null;
  const ipInt = ipv4ToInt(ip);
  const baseInt = ipv4ToInt(cidr.slice(0, slash));
  if (ipInt == null || baseInt == null) return null;
  if (bits === 0) return true;
  const mask = bits === 32 ? 0xffffffff : ((0xffffffff << (32 - bits)) >>> 0);
  return (ipInt & mask) === (baseInt & mask);
}

function parseIpv6(input) {
  if (typeof input !== "string") return null;
  let text = input.trim().toLowerCase();
  if (text.startsWith("[") && text.endsWith("]")) text = text.slice(1, -1);
  if (text.includes("%")) return null;
  const zoneFree = text;
  if (!/^[0-9a-f:]+$/.test(zoneFree.includes(".") ? zoneFree.replace(/\./g, "a") : zoneFree) && !zoneFree.includes(".")) {
    return null;
  }
  const halves = zoneFree.split("::");
  if (halves.length > 2) return null;
  const parseSide = (side) => {
    if (side === "") return [];
    const labels = side.split(":");
    const out = [];
    for (let i = 0; i < labels.length; i++) {
      const label = labels[i];
      if (label.includes(".")) {
        if (i !== labels.length - 1) return null;
        const v4 = ipv4ToInt(label);
        if (v4 == null) return null;
        out.push((v4 >>> 16) & 0xffff, v4 & 0xffff);
      } else {
        if (!/^[0-9a-f]{1,4}$/.test(label)) return null;
        out.push(parseInt(label, 16));
      }
    }
    return out;
  };
  const left = parseSide(halves[0]);
  if (!left) return null;
  if (halves.length === 1) {
    return left.length === 8 ? left : null;
  }
  const right = parseSide(halves[1]);
  if (!right) return null;
  if (left.length + right.length > 8) return null;
  const zeros = new Array(8 - left.length - right.length).fill(0);
  return left.concat(zeros, right);
}

function inCidr6(ip, cidr) {
  const slash = cidr.indexOf("/");
  if (slash <= 0) return null;
  const bits = Number(cidr.slice(slash + 1));
  if (!Number.isInteger(bits) || bits < 0 || bits > 128) return null;
  const ipWords = parseIpv6(ip);
  const baseWords = parseIpv6(cidr.slice(0, slash));
  if (!ipWords || !baseWords) return null;
  let remain = bits;
  for (let i = 0; i < 8; i++) {
    if (remain <= 0) return true;
    const take = Math.min(16, remain);
    const mask = take === 16 ? 0xffff : ((0xffff << (16 - take)) & 0xffff);
    if ((ipWords[i] & mask) !== (baseWords[i] & mask)) return false;
    remain -= take;
  }
  return true;
}

function classifyIp(value) {
  if (typeof value !== "string") return null;
  const text = value.trim().toLowerCase();
  if (ipv4ToInt(text) != null) return { family: 4, text };
  const v6 = parseIpv6(text);
  if (v6) return { family: 6, text };
  return null;
}

function dottedFromInt(n) {
  return [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].join(".");
}

// Exact and CIDR checks share one integer address. Leading zeros and an
// IPv4-mapped IPv6 form compare as the embedded IPv4 address.
function canonicalAddress(value) {
  const classified = classifyIp(value);
  if (!classified) return null;
  if (classified.family === 4) {
    const n = ipv4ToInt(classified.text);
    if (n == null) return null;
    return { kind: "v4", int: n };
  }
  const words = parseIpv6(classified.text);
  if (!words) return null;
  const v4Mapped = words[0] === 0 && words[1] === 0 && words[2] === 0 && words[3] === 0 && words[4] === 0 && words[5] === 0xffff;
  if (v4Mapped) return { kind: "v4", int: ((words[6] << 16) | words[7]) >>> 0 };
  return { kind: "v6", words };
}

function entryMatchesIp(ip, entry) {
  if (typeof entry !== "string") return { ok: false };
  const raw = entry.trim().toLowerCase();
  if (!raw) return { ok: true, match: false };
  if (raw.includes("/")) {
    const slash = raw.indexOf("/");
    const want = canonicalAddress(raw.slice(0, slash));
    const got = canonicalAddress(ip);
    if (!want || !got) return { ok: false };
    if (want.kind !== got.kind) return { ok: true, match: false };
    if (want.kind === "v4") {
      const hit = inCidr4(dottedFromInt(got.int), dottedFromInt(want.int) + "/" + raw.slice(slash + 1));
      if (hit == null) return { ok: false };
      return { ok: true, match: hit };
    }
    const hit = inCidr6(ip, raw);
    if (hit == null) return { ok: false };
    return { ok: true, match: hit };
  }
  const want = canonicalAddress(raw);
  const got = canonicalAddress(ip);
  if (!want || !got) return { ok: false };
  if (want.kind !== got.kind) return { ok: true, match: false };
  if (want.kind === "v4") return { ok: true, match: want.int === got.int };
  for (let i = 0; i < 8; i++) if (want.words[i] !== got.words[i]) return { ok: true, match: false };
  return { ok: true, match: true };
}

function ipListed(ip, items) {
  if (!Array.isArray(items) || items.length === 0) return { listed: false, bad: false };
  if (ip == null || ip === "") return { listed: false, bad: false, absent: true };
  for (const item of items) {
    const hit = entryMatchesIp(ip, item);
    if (!hit.ok) return { listed: false, bad: true };
    if (hit.match) return { listed: true, bad: false };
  }
  return { listed: false, bad: false };
}

module.exports = {
  classifyIp,
  hostListed,
  ipListed,
  ipv4ToInt,
  parseIpv6,
};
