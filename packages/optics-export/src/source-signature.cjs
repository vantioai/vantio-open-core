"use strict";

const crypto = require("node:crypto");

// This flag is the product claim. A verified test signature does not set it.
const PRODUCT_OTLP_EXPORT_AUTHORIZED = false;

const SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");

function publicKeyFromRaw(raw) {
  if (!Buffer.isBuffer(raw) || raw.length !== 32) return null;
  try {
    return crypto.createPublicKey({
      key: Buffer.concat([SPKI_PREFIX, raw]),
      format: "der",
      type: "spki",
    });
  } catch {
    return null;
  }
}

function signatureBytes(value) {
  if (Buffer.isBuffer(value) && value.length === 64) return value;
  if (typeof value !== "string" || value.length < 80 || value.length > 120) return null;
  try {
    const raw = Buffer.from(value, "base64");
    return raw.length === 64 ? raw : null;
  } catch {
    return null;
  }
}

function verifyExternalSourceSignature(canonicalBytes, signature, publicKey) {
  if (PRODUCT_OTLP_EXPORT_AUTHORIZED !== false) {
    return { ok: false, reason: "UNAUTHORIZED", authorized: false };
  }
  const sig = signatureBytes(signature);
  const key = publicKeyFromRaw(publicKey);
  if (!Buffer.isBuffer(canonicalBytes) || !sig || !key) {
    return { ok: false, reason: "SIGNATURE_INVALID", authorized: false };
  }
  let ok = false;
  try {
    ok = crypto.verify(null, canonicalBytes, key, sig);
  } catch {
    ok = false;
  }
  return ok
    ? { ok: true, reason: null, authorized: false }
    : { ok: false, reason: "SIGNATURE_INVALID", authorized: false };
}

// Drop-in check. trust is null until an outside signer supplies a public key.
// A caller cannot set trust.authorized and make this a product authorization.
function checkBeforeSend(canonicalBytes, signature, trust) {
  if (PRODUCT_OTLP_EXPORT_AUTHORIZED !== false) {
    return { ok: false, reason: "UNAUTHORIZED", authorized: false };
  }
  if (!trust) return { ok: true, reason: null, authorized: false, attestation: "in-process" };
  if (trust.authorized === true) return { ok: false, reason: "UNAUTHORIZED", authorized: false };
  if (!publicKeyFromRaw(trust.publicKey)) return { ok: false, reason: "NO_EXTERNAL_SIGNER", authorized: false };
  if (signature == null) return { ok: false, reason: "SIGNATURE_REQUIRED", authorized: false };
  const verified = verifyExternalSourceSignature(canonicalBytes, signature, trust.publicKey);
  if (!verified.ok) return verified;
  return { ok: true, reason: null, authorized: false, attestation: "in-process" };
}

module.exports = {
  PRODUCT_OTLP_EXPORT_AUTHORIZED,
  checkBeforeSend,
  verifyExternalSourceSignature,
};
