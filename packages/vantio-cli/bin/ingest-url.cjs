"use strict";

function parseIngestUrl(raw) {
  if (raw == null || String(raw).trim() === "") {
    return { ok: true, href: "https://vantio.ai", publicHost: true, source: "default" };
  }
  let url;
  try {
    url = new URL(String(raw).trim());
  } catch {
    return { ok: false, reason: "VANTIO_INGEST_URL is not a valid URL" };
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return { ok: false, reason: "VANTIO_INGEST_URL must use http or https" };
  }
  if (!url.hostname) {
    return { ok: false, reason: "VANTIO_INGEST_URL has no host" };
  }
  const host = url.hostname.toLowerCase();
  return {
    ok: true,
    href: url.origin,
    publicHost: host === "vantio.ai" || host === "www.vantio.ai",
    source: "env",
  };
}

module.exports = { parseIngestUrl };
