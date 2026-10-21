/**
 * Read release/pe-canonical-seal.json. Values stay the digests already pinned.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

const HEX64 = /^[0-9a-f]{64}$/;
const HEX40 = /^[0-9a-f]{40}$/;

export function readCanonicalSeal(root) {
  const body = JSON.parse(readFileSync(join(root, "release/pe-canonical-seal.json"), "utf8"));
  if (body.schema !== 1) throw new Error("schema");
  const pin = body.public_pin?.archive_sha256;
  const source = body.public_pin?.source_commit;
  const manifest = body.public_pin?.manifest_digest;
  const lane = body.lane_seal?.sha256;
  if (!HEX64.test(pin) || !HEX40.test(source) || !HEX64.test(lane)) throw new Error("seal");
  if (typeof manifest !== "string" || !manifest.startsWith("sha256:") || !HEX64.test(manifest.slice(7))) {
    throw new Error("manifest_digest");
  }
  if (typeof body.lane_seal?.note !== "string" || !body.lane_seal.note.includes("one seal")) {
    throw new Error("lane_note");
  }
  if (body.signer_kid !== null) throw new Error("signer_kid");
  return body;
}

export function readSealHistory(root) {
  const body = JSON.parse(readFileSync(join(root, "release/pe-seal-history.json"), "utf8"));
  for (const key of ["previous_working_seal", "plumbing_only_seal", "tracking_seal"]) {
    if (!HEX64.test(body[key])) throw new Error(key);
  }
  return body;
}

export function publicPin(root) {
  return readCanonicalSeal(root).public_pin.archive_sha256;
}

export function laneSeal(root) {
  return readCanonicalSeal(root).lane_seal.sha256;
}
