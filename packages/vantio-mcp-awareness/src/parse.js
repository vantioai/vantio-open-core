/**
 * Bounded MCP framing and a JSON walker that keeps the first duplicate key.
 * String values stay on the ephemeral tree only. Callers must not put that
 * tree on a record or a session.
 */

import { MAX_ARRAY, MAX_DEPTH, MAX_FRAME, MAX_KEYS } from "./bounds.js";

const DECODER = new TextDecoder("utf-8", { fatal: true });

export function decodeUtf8(buffer) {
  try {
    return { ok: true, text: DECODER.decode(buffer) };
  } catch {
    return { ok: false, reason: "invalid_utf8" };
  }
}

function skipWs(ctx) {
  const s = ctx.s;
  while (ctx.i < ctx.n) {
    const c = s.charCodeAt(ctx.i);
    if (c === 32 || c === 9 || c === 10 || c === 13) ctx.i += 1;
    else break;
  }
}

function fail() {
  return null;
}

function parseValue(ctx) {
  if (ctx.depth > MAX_DEPTH) {
    ctx.truncated = true;
    return skipValue(ctx) ? { t: "truncated" } : fail();
  }
  const s = ctx.s;
  if (ctx.i >= ctx.n) return fail();
  const c = s[ctx.i];
  if (c === "{") return parseObject(ctx);
  if (c === "[") return parseArray(ctx);
  if (c === '"') return parseString(ctx);
  if (c === "t") return consumeLit(ctx, "true", { t: "bool", v: true });
  if (c === "f") return consumeLit(ctx, "false", { t: "bool", v: false });
  if (c === "n") return consumeLit(ctx, "null", { t: "null" });
  if (c === "-" || (c >= "0" && c <= "9")) return parseNumber(ctx);
  return fail();
}

function consumeLit(ctx, lit, node) {
  if (ctx.s.startsWith(lit, ctx.i)) {
    ctx.i += lit.length;
    return node;
  }
  return fail();
}

function parseNumber(ctx) {
  const start = ctx.i;
  const s = ctx.s;
  if (s[ctx.i] === "-") ctx.i += 1;
  if (ctx.i >= ctx.n || s[ctx.i] < "0" || s[ctx.i] > "9") return fail();
  if (s[ctx.i] === "0") ctx.i += 1;
  else {
    while (ctx.i < ctx.n && s[ctx.i] >= "0" && s[ctx.i] <= "9") ctx.i += 1;
  }
  if (s[ctx.i] === ".") {
    ctx.i += 1;
    const frac = ctx.i;
    while (ctx.i < ctx.n && s[ctx.i] >= "0" && s[ctx.i] <= "9") ctx.i += 1;
    if (ctx.i === frac) return fail();
  }
  if (s[ctx.i] === "e" || s[ctx.i] === "E") {
    ctx.i += 1;
    if (s[ctx.i] === "+" || s[ctx.i] === "-") ctx.i += 1;
    const exp = ctx.i;
    while (ctx.i < ctx.n && s[ctx.i] >= "0" && s[ctx.i] <= "9") ctx.i += 1;
    if (ctx.i === exp) return fail();
  }
  const lex = s.slice(start, ctx.i);
  if (lex.length > 64) ctx.truncated = true;
  return { t: "number", lex: lex.slice(0, 64) };
}

function parseString(ctx) {
  const s = ctx.s;
  if (s[ctx.i] !== '"') return fail();
  ctx.i += 1;
  let out = "";
  while (ctx.i < ctx.n) {
    const c = s[ctx.i];
    if (c === '"') {
      ctx.i += 1;
      return { t: "string", v: out, bytes: Buffer.byteLength(out) };
    }
    if (c === "\\") {
      const esc = escapeOne(ctx);
      if (esc == null) return fail();
      out += esc;
      continue;
    }
    const code = s.charCodeAt(ctx.i);
    if (code < 0x20) return fail();
    out += c;
    ctx.i += 1;
  }
  return fail();
}

function escapeOne(ctx) {
  const s = ctx.s;
  ctx.i += 1;
  if (ctx.i >= ctx.n) return null;
  const c = s[ctx.i];
  ctx.i += 1;
  if (c === '"' || c === "\\" || c === "/") return c;
  if (c === "b") return "\b";
  if (c === "f") return "\f";
  if (c === "n") return "\n";
  if (c === "r") return "\r";
  if (c === "t") return "\t";
  if (c === "u") {
    if (ctx.i + 4 > ctx.n) return null;
    const hex = s.slice(ctx.i, ctx.i + 4);
    if (!/^[0-9a-fA-F]{4}$/.test(hex)) return null;
    ctx.i += 4;
    const unit = parseInt(hex, 16);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      if (
        s[ctx.i] === "\\" &&
        s[ctx.i + 1] === "u" &&
        /^[0-9a-fA-F]{4}$/.test(s.slice(ctx.i + 2, ctx.i + 6))
      ) {
        const low = parseInt(s.slice(ctx.i + 2, ctx.i + 6), 16);
        if (low >= 0xdc00 && low <= 0xdfff) {
          ctx.i += 6;
          return String.fromCharCode(unit, low);
        }
      }
      return null;
    }
    if (unit >= 0xdc00 && unit <= 0xdfff) return null;
    return String.fromCharCode(unit);
  }
  return null;
}

function parseObject(ctx) {
  const s = ctx.s;
  ctx.i += 1;
  ctx.depth += 1;
  const map = Object.create(null);
  const order = [];
  let dup = false;
  skipWs(ctx);
  if (s[ctx.i] === "}") {
    ctx.i += 1;
    ctx.depth -= 1;
    return { t: "object", map, order, dup };
  }
  let stored = 0;
  while (ctx.i < ctx.n) {
    if (s[ctx.i] !== '"') {
      ctx.depth -= 1;
      return fail();
    }
    const keyNode = parseString(ctx);
    if (!keyNode) {
      ctx.depth -= 1;
      return fail();
    }
    skipWs(ctx);
    if (s[ctx.i] !== ":") {
      ctx.depth -= 1;
      return fail();
    }
    ctx.i += 1;
    skipWs(ctx);
    const value = parseValue(ctx);
    if (!value) {
      ctx.depth -= 1;
      return fail();
    }
    if (Object.prototype.hasOwnProperty.call(map, keyNode.v)) {
      dup = true;
      ctx.dups = true;
    } else if (stored < MAX_KEYS) {
      map[keyNode.v] = value;
      order.push(keyNode.v);
      stored += 1;
    } else {
      ctx.truncated = true;
    }
    skipWs(ctx);
    if (s[ctx.i] === ",") {
      ctx.i += 1;
      skipWs(ctx);
      continue;
    }
    if (s[ctx.i] === "}") {
      ctx.i += 1;
      ctx.depth -= 1;
      return { t: "object", map, order, dup };
    }
    ctx.depth -= 1;
    return fail();
  }
  ctx.depth -= 1;
  return fail();
}

function parseArray(ctx) {
  const s = ctx.s;
  ctx.i += 1;
  ctx.depth += 1;
  const items = [];
  let total = 0;
  let truncated = false;
  skipWs(ctx);
  if (s[ctx.i] === "]") {
    ctx.i += 1;
    ctx.depth -= 1;
    return { t: "array", items, total: 0, truncated: false };
  }
  while (ctx.i < ctx.n) {
    const value = parseValue(ctx);
    if (!value) {
      ctx.depth -= 1;
      return fail();
    }
    total += 1;
    if (items.length < MAX_ARRAY) items.push(value);
    else {
      truncated = true;
      ctx.truncated = true;
    }
    skipWs(ctx);
    if (s[ctx.i] === ",") {
      ctx.i += 1;
      skipWs(ctx);
      continue;
    }
    if (s[ctx.i] === "]") {
      ctx.i += 1;
      ctx.depth -= 1;
      return { t: "array", items, total, truncated };
    }
    ctx.depth -= 1;
    return fail();
  }
  ctx.depth -= 1;
  return fail();
}

/** Skip a value when depth is already past the cap. Still bounds by the frame. */
function skipValue(ctx) {
  const s = ctx.s;
  if (ctx.i >= ctx.n) return false;
  const c = s[ctx.i];
  if (c === '"') return parseString(ctx) != null;
  if (c === "{") return skipContainer(ctx, "{", "}");
  if (c === "[") return skipContainer(ctx, "[", "]");
  if (c === "t") return consumeLit(ctx, "true", { t: "bool", v: true }) != null;
  if (c === "f") return consumeLit(ctx, "false", { t: "bool", v: false }) != null;
  if (c === "n") return consumeLit(ctx, "null", { t: "null" }) != null;
  if (c === "-" || (c >= "0" && c <= "9")) return parseNumber(ctx) != null;
  return false;
}

function skipContainer(ctx, open, close) {
  const s = ctx.s;
  let depth = 0;
  let inString = false;
  let escape = false;
  for (; ctx.i < ctx.n; ctx.i += 1) {
    const c = s[ctx.i];
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (c === "\\") {
        escape = true;
        continue;
      }
      if (c === '"') inString = false;
      continue;
    }
    if (c === '"') {
      inString = true;
      continue;
    }
    if (c === open) depth += 1;
    else if (c === close) {
      depth -= 1;
      if (depth === 0) {
        ctx.i += 1;
        return true;
      }
    }
  }
  return false;
}

export function parseJson(text) {
  if (typeof text !== "string") return { ok: false, reason: "malformed_json" };
  let s = text;
  if (s.charCodeAt(0) === 0xfeff) s = s.slice(1);
  const ctx = { s, i: 0, n: s.length, depth: 0, truncated: false, dups: false };
  skipWs(ctx);
  if (ctx.i >= ctx.n) return { ok: false, reason: "malformed_json" };
  const value = parseValue(ctx);
  if (!value) return { ok: false, reason: "malformed_json" };
  skipWs(ctx);
  if (ctx.i !== ctx.n) return { ok: false, reason: "malformed_json" };
  return { ok: true, value, truncated: ctx.truncated, dups: ctx.dups };
}

function frame(kind, raw, extra) {
  return { kind, raw, ...extra };
}

export function createFramer(transport) {
  let buf = Buffer.alloc(0);
  const kind = transport || "stdio";

  function pull(end) {
    if (kind === "sse") return pullSse(end);
    if (kind === "http") return pullHttp(end);
    if (kind === "json-body") return pullJsonBody(end);
    return pullStdio(end);
  }

  function push(chunk) {
    const next = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    const out = [];
    let offset = 0;
    while (offset < next.length) {
      const room = MAX_FRAME - buf.length;
      if (room <= 0) {
        buf = Buffer.alloc(0);
        out.push(frame("oversize", Buffer.alloc(0)));
        continue;
      }
      const take = Math.min(room, next.length - offset);
      const piece = next.subarray(offset, offset + take);
      buf = buf.length === 0 ? Buffer.from(piece) : Buffer.concat([buf, piece]);
      offset += take;
      out.push(...pull(false));
      if (buf.length >= MAX_FRAME) {
        buf = Buffer.alloc(0);
        out.push(frame("oversize", Buffer.alloc(0)));
      }
    }
    return out;
  }

  function finish() {
    const out = pull(true);
    if (buf.length > MAX_FRAME) {
      buf = Buffer.alloc(0);
      out.push(frame("oversize", Buffer.alloc(0)));
    }
    return out;
  }

  function pullStdio(end) {
    const out = [];
    while (buf.length) {
      if (startsWithContentLength(buf)) {
        const taken = takeContentLength();
        if (taken === "need") break;
        if (taken) out.push(taken);
        continue;
      }
      const nl = buf.indexOf(0x0a);
      if (nl < 0) {
        if (end) {
          if (buf.length) out.push(lineFrame(buf));
          buf = Buffer.alloc(0);
        }
        break;
      }
      const raw = buf.subarray(0, nl + 1);
      buf = buf.subarray(nl + 1);
      out.push(lineFrame(raw));
    }
    return out;
  }

  function lineFrame(raw) {
    let text;
    const decoded = decodeUtf8(raw);
    if (!decoded.ok) return frame("invalid_utf8", raw);
    text = decoded.text.replace(/\r?\n$/, "");
    if (text.length === 0) return frame("ignore", raw, { reason: "empty" });
    const trimmed = text.trimStart();
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
      return frame("ignore", raw, { reason: "ignored_non_json" });
    }
    return frame("json", raw, { text: trimmed });
  }

  function takeContentLength() {
    const sep = findHeaderEnd(buf);
    if (sep < 0) {
      if (buf.length > MAX_FRAME) {
        buf = Buffer.alloc(0);
        return frame("oversize", Buffer.alloc(0));
      }
      return "need";
    }
    const head = buf.subarray(0, sep).toString("latin1");
    const lens = [...head.matchAll(/content-length\s*:\s*([0-9]+)/gi)];
    if (lens.length !== 1) {
      const raw = buf.subarray(0, sep);
      buf = buf.subarray(sep);
      return frame("malformed_frame", raw, { reason: "content_length_rejected" });
    }
    const len = Number(lens[0][1]);
    if (!Number.isSafeInteger(len) || len < 0 || len > MAX_FRAME) {
      buf = Buffer.alloc(0);
      return frame("oversize", Buffer.alloc(0));
    }
    if (buf.length < sep + len) return "need";
    const raw = buf.subarray(0, sep + len);
    const body = buf.subarray(sep, sep + len);
    buf = buf.subarray(sep + len);
    const decoded = decodeUtf8(body);
    if (!decoded.ok) return frame("invalid_utf8", raw);
    return frame("json", raw, { text: decoded.text });
  }

  function pullSse(end) {
    const out = [];
    while (true) {
      const sep = findBlank(buf);
      if (!sep) {
        if (end && buf.length) {
          out.push(sseEvent(buf, buf.length));
          buf = Buffer.alloc(0);
        }
        break;
      }
      out.push(sseEvent(buf, sep.at));
      buf = buf.subarray(sep.next);
    }
    return out.filter(Boolean);
  }

  function pullHttp(end) {
    const out = [];
    if (buf.length === 0) return out;
    const sep = findHeaderEnd(buf);
    if (sep < 0) {
      if (end) {
        out.push(frame("malformed_frame", buf, { reason: "malformed_frame" }));
        buf = Buffer.alloc(0);
      }
      return out;
    }
    const headBuf = buf.subarray(0, sep);
    const head = headBuf.toString("latin1");
    if (/transfer-encoding\s*:\s*chunked/i.test(head)) {
      buf = Buffer.alloc(0);
      out.push(frame("malformed_frame", headBuf, { reason: "chunked_unsupported" }));
      return out;
    }
    const lens = [...head.matchAll(/content-length\s*:\s*([0-9]+)/gi)];
    if (lens.length > 1) {
      buf = Buffer.alloc(0);
      out.push(frame("malformed_frame", headBuf, { reason: "content_length_rejected" }));
      return out;
    }
    let len = lens.length === 1 ? Number(lens[0][1]) : null;
    if (len != null && (!Number.isSafeInteger(len) || len > MAX_FRAME)) {
      buf = Buffer.alloc(0);
      out.push(frame("oversize", Buffer.alloc(0)));
      return out;
    }
    if (len == null) {
      if (!end) return out;
      len = buf.length - sep;
    }
    if (buf.length < sep + len) {
      if (end) {
        out.push(frame("malformed_frame", buf, { reason: "malformed_frame" }));
        buf = Buffer.alloc(0);
      }
      return out;
    }
    const raw = buf.subarray(0, sep + len);
    const body = buf.subarray(sep, sep + len);
    buf = buf.subarray(sep + len);
    const type = headerValue(head, "content-type");
    if (type.includes("text/event-stream")) {
      const sse = createFramer("sse");
      out.push(...sse.push(body), ...sse.finish());
      return out;
    }
    const decoded = decodeUtf8(body);
    if (!decoded.ok) {
      out.push(frame("invalid_utf8", raw));
      return out;
    }
    out.push(frame("json", raw, { text: decoded.text }));
    return out;
  }

  function pullJsonBody(end) {
    if (!end && buf.length === 0) return [];
    if (!end) return [];
    const raw = buf;
    buf = Buffer.alloc(0);
    const decoded = decodeUtf8(raw);
    if (!decoded.ok) return [frame("invalid_utf8", raw)];
    return [frame("json", raw, { text: decoded.text })];
  }

  return {
    push,
    finish,
    buffered() {
      return buf.length;
    },
  };
}

function startsWithContentLength(buffer) {
  const n = Math.min(buffer.length, 20);
  const head = buffer.subarray(0, n).toString("latin1").toLowerCase();
  return head.startsWith("content-length:");
}

function findHeaderEnd(buffer) {
  const crlf = buffer.indexOf("\r\n\r\n");
  if (crlf >= 0) return crlf + 4;
  return -1;
}

function findBlank(buffer) {
  const a = buffer.indexOf("\n\n");
  const b = buffer.indexOf("\r\n\r\n");
  if (a < 0 && b < 0) return null;
  if (a >= 0 && (b < 0 || a < b)) return { at: a, next: a + 2 };
  return { at: b, next: b + 4 };
}

function sseEvent(raw, end) {
  const decoded = decodeUtf8(raw.subarray(0, end));
  if (!decoded.ok) return frame("invalid_utf8", raw.subarray(0, end));
  const lines = decoded.text.split(/\r?\n/);
  const data = [];
  let commentOnly = true;
  for (const line of lines) {
    if (line.length === 0) continue;
    if (line.startsWith(":")) continue;
    commentOnly = false;
    if (line.startsWith("data:")) {
      data.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (commentOnly || data.length === 0) {
    return frame("ignore", raw.subarray(0, end), { reason: "empty" });
  }
  return frame("json", raw.subarray(0, end), { text: data.join("\n") });
}

function headerValue(head, name) {
  const re = new RegExp(`^${name}\\s*:\\s*(.*)$`, "im");
  const m = head.match(re);
  return m ? m[1].trim().toLowerCase() : "";
}
