"use strict";

const fs = require("node:fs");
const Module = require("node:module");
const os = require("node:os");
const path = require("node:path");

const { catalogInScope, LLM_HOSTS } = require("../../vantio-cli/bin/llm-hosts.cjs");
const boundary = require("./boundary.cjs");
const { composeCanonical } = require("./record.cjs");

const sidecar = [];
let installed = false;
let originalWrite = null;

function writerEnabled() {
  return process.env.VANTIO_PKG02_WRITER !== "0";
}

function hosts() {
  const extra = String(process.env.VANTIO_EXTRA_LLM_HOSTS || "").split(",");
  const set = new Set(LLM_HOSTS);
  for (let i = 0; i < extra.length; i += 1) {
    const token = extra[i].trim();
    if (token) set.add(token);
  }
  return set;
}

function requestTarget(input) {
  try {
    if (typeof input === "string") return new URL(input);
    if (input instanceof URL) return input;
    if (typeof Request !== "undefined" && input instanceof Request) return new URL(input.url);
    if (input && typeof input.url === "string") return new URL(input.url);
  } catch {
    return null;
  }
  return null;
}

function inScope(target) {
  if (!target) return false;
  const port = target.port ? Number(target.port) : (target.protocol === "https:" ? 443 : 80);
  try {
    return catalogInScope(target.hostname, port, hosts());
  } catch {
    return false;
  }
}

function explicitPort(target) {
  if (!target || target.port === "") return null;
  const port = Number(target.port);
  return Number.isInteger(port) && port > 0 ? port : null;
}

function lengthOf(response) {
  try {
    const headers = response && response.headers;
    if (!headers || typeof headers.get !== "function") return { lengthPresent: false, responseBytes: null };
    const raw = headers.get("content-length");
    if (raw == null || raw === "") return { lengthPresent: false, responseBytes: null };
    const value = Number.parseInt(String(raw), 10);
    if (!Number.isInteger(value) || value < 0) return { lengthPresent: false, responseBytes: null };
    return { lengthPresent: true, responseBytes: value };
  } catch {
    return { lengthPresent: false, responseBytes: null };
  }
}

function pushSide(target, fields) {
  if (!inScope(target)) return;
  sidecar.push(Object.assign({
    errorClass: null,
    lengthPresent: false,
    mediation: "node_fetch",
    networkError: false,
    port: explicitPort(target),
    responseBytes: null,
  }, fields));
}

function errorClassName(err) {
  if (!err || typeof err.name !== "string") return null;
  return /^[A-Za-z0-9_]{1,64}$/.test(err.name) ? err.name : null;
}

function wrapFetch() {
  const current = globalThis.fetch;
  if (typeof current !== "function" || current.__vantioPkg02Wrapped === true) return;
  const wrapped = async function vantioPkg02Fetch(input, init) {
    const target = requestTarget(input);
    try {
      const response = await current.call(globalThis, input, init);
      pushSide(target, lengthOf(response));
      return response;
    } catch (err) {
      pushSide(target, {
        errorClass: errorClassName(err),
        lengthPresent: false,
        networkError: true,
        responseBytes: null,
      });
      throw err;
    }
  };
  wrapped.__vantioPkg02Wrapped = true;
  globalThis.fetch = wrapped;
}

function legacyPayload(data) {
  try {
    const text = Buffer.isBuffer(data) ? data.toString("utf8") : (typeof data === "string" ? data : null);
    if (typeof text !== "string") return null;
    const parsed = JSON.parse(text);
    if (!parsed || parsed.vantio_run_log !== "1" || !Array.isArray(parsed.calls)) return null;
    if (parsed.schema_version !== boundary.LEGACY_SCHEMA_VERSION) return null;
    return parsed;
  } catch {
    return null;
  }
}

function runsPath(file) {
  const value = path.resolve(String(file));
  const home = process.env.VANTIO_HOME || path.join(os.homedir(), ".vantio");
  const runs = path.resolve(home, "runs") + path.sep;
  return value.startsWith(runs) && value.endsWith(".json");
}

function takeSidecar() {
  return sidecar.slice();
}

function writeCanonical(file, data, options) {
  const legacy = legacyPayload(data);
  if (!legacy || !writerEnabled() || !runsPath(file)) return originalWrite(file, data, options);
  const fault = process.env.VANTIO_PKG02_INJECT_FAULT === "1";
  const composed = composeCanonical(legacy, takeSidecar(), {
    applicationResult: null,
    injectFault: fault,
  });
  const body = `${JSON.stringify(composed.document, null, 2)}\n`;
  return originalWrite(file, body, options);
}

function installWriter() {
  if (installed) return;
  installed = true;
  originalWrite = fs.writeFileSync;
  const patched = function vantioPkg02WriteFileSync(file, data, options) {
    try {
      return writeCanonical(file, data, options);
    } catch {
      try {
        if (writerEnabled() && runsPath(file) && legacyPayload(data)) {
          const composed = composeCanonical({ vantio_run_log: "1", schema_version: 2, calls: [] }, [], {
            injectFault: true,
          });
          return originalWrite(file, `${JSON.stringify(composed.document, null, 2)}\n`, options);
        }
      } catch {
        // The frozen exit handler still owns the workload exit code.
      }
      return originalWrite(file, data, options);
    }
  };
  fs.writeFileSync = patched;
  const originalRequire = Module.prototype.require;
  Module.prototype.require = function vantioPkg02Require(id) {
    const exported = originalRequire.apply(this, arguments);
    if (typeof id === "string" && id.endsWith("interceptor.cjs")) wrapFetch();
    return exported;
  };
}

module.exports = {
  installWriter,
  takeSidecar,
  writerEnabled,
};
