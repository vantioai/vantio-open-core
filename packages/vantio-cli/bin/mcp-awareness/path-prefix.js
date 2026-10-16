/**
 * Lexical path prefix for operator rules.
 * This is not a filesystem jail: it does not resolve symlinks or change case.
 * A path that cannot be normalized safely is a rejection, which the caller
 * must treat as deny.
 */

const HEX = "0123456789abcdefABCDEF";

function isHex(char) {
  return HEX.includes(char);
}

function decodeOnce(input) {
  let out = "";
  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];
    if (char === "%") {
      const high = input[i + 1];
      const low = input[i + 2];
      if (!isHex(high) || !isHex(low)) return { ok: false, reason: "ambiguous" };
      const byte = Number.parseInt(high + low, 16);
      if (byte === 0) return { ok: false, reason: "nul" };
      out += String.fromCharCode(byte);
      i += 2;
      continue;
    }
    if (input.charCodeAt(i) === 0) return { ok: false, reason: "nul" };
    out += char;
  }
  if (out.toLowerCase().includes("%2e") || out.toLowerCase().includes("%2f")) {
    return { ok: false, reason: "encoded_traversal" };
  }
  return { ok: true, text: out };
}

function lexical(path) {
  if (path.includes("\\")) return { ok: false, reason: "ambiguous" };
  const absolute = path.startsWith("/");
  const parts = path.split("/");
  const stack = [];
  for (const part of parts) {
    if (part === "" || part === ".") continue;
    if (part === "..") {
      if (stack.length === 0) return { ok: false, reason: "escapes_root" };
      stack.pop();
      continue;
    }
    stack.push(part);
  }
  if (absolute) return { ok: true, path: `/${stack.join("/")}` };
  if (stack.length === 0) return { ok: false, reason: "ambiguous" };
  return { ok: true, path: stack.join("/") };
}

/**
 * @returns {{ ok: true, path: string } | { ok: false, reason: string }}
 */
export function normalizePath(input) {
  if (typeof input !== "string" || input.length === 0) return { ok: false, reason: "ambiguous" };
  if (input.includes("\0")) return { ok: false, reason: "nul" };
  const decoded = decodeOnce(input);
  if (!decoded.ok) return decoded;
  return lexical(decoded.text);
}

function stripTrailingSlash(path) {
  if (path.length > 1 && path.endsWith("/")) return path.slice(0, -1);
  return path;
}

function onSegmentBoundary(path, prefix) {
  const left = stripTrailingSlash(path);
  const right = stripTrailingSlash(prefix);
  if (right === "/") return left.startsWith("/");
  if (left === right) return true;
  return left.startsWith(`${right}/`);
}

/**
 * @returns {"match" | "miss" | "reject"}
 */
export function pathPrefixMatch(candidate, prefix) {
  const left = normalizePath(candidate);
  const right = normalizePath(prefix);
  if (!left.ok || !right.ok) return "reject";
  return onSegmentBoundary(left.path, right.path) ? "match" : "miss";
}
