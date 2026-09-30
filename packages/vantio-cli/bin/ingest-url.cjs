"use strict";

// Node and Python both keep the path on VANTIO_INGEST_URL. The origin alone is not enough.
function parseIngestUrl(raw) {
  if (raw == null || String(raw).trim() === "") {
    return { ok: true, href: "https://vantio.ai", publicHost: true };
  }
  let url;
  try {
    url = new URL(String(raw).trim());
  } catch {
    return { ok: false, href: "", publicHost: false, reason: "VANTIO_INGEST_URL is not a valid URL" };
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return { ok: false, href: "", publicHost: false, reason: "VANTIO_INGEST_URL must use http or https" };
  }
  if (!url.hostname) {
    return { ok: false, href: "", publicHost: false, reason: "VANTIO_INGEST_URL has no host" };
  }
  const path = url.pathname && url.pathname !== "/" ? url.pathname.replace(/\/+$/, "") : "";
  const href = `${url.origin}${path}`;
  const host = url.hostname.toLowerCase();
  return {
    ok: true,
    href,
    publicHost: host === "vantio.ai" || host === "www.vantio.ai",
  };
}

module.exports = { parseIngestUrl };
