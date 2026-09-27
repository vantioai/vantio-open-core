"use strict";

function reject(reason) {
  return { ok: false, reason };
}

function parseCustomerEndpoint(value) {
  if (typeof value !== "string" || value.length < 1 || value.length > 2048) {
    return reject("ENDPOINT_REQUIRED");
  }
  if (/[\s\\]/.test(value)) return reject("ENDPOINT_REJECTED");
  let url;
  try {
    url = new URL(value);
  } catch {
    return reject("ENDPOINT_REJECTED");
  }
  if (url.username !== "" || url.password !== "") return reject("ENDPOINT_USERINFO_REJECTED");
  if (url.search !== "" || url.hash !== "") return reject("ENDPOINT_QUERY_REJECTED");
  if (url.protocol !== "http:" && url.protocol !== "https:") return reject("ENDPOINT_SCHEME_REJECTED");
  const path = url.pathname === "" ? "/" : url.pathname;
  if (path !== "/" && path !== "/v1/traces") return reject("ENDPOINT_PATH_REJECTED");
  return {
    ok: true,
    url: url.origin + "/v1/traces",
    origin: url.origin,
    path: "/v1/traces",
  };
}

module.exports = { parseCustomerEndpoint };
