/**
 * Observe-only copy record for a future enrolled-host tail.
 * This module does not load a kernel program and does not export an allow.
 * A short copy is not a complete frame. Truncation is a gap.
 */

export const COPY_LIMIT = 4096;
export const HEADER_BYTES = 32;
export const HOST_ATTACH = "Roadmap";

function gap(capture, reason) {
  return {
    capture,
    decision: "GAP",
    parse: false,
    reason,
    host_attach: HOST_ATTACH,
    label: "Lab-only",
  };
}

export function classifyCopy(input) {
  if (input == null || typeof input !== "object") {
    return gap("truncated_capture", "record");
  }
  if (input.registered !== true) {
    return gap("unregistered_fd", "registered");
  }
  if (input.ciphertext === true) {
    return gap("ciphertext", "ciphertext");
  }
  const copied = input.copiedBytes;
  const frame = input.frameLength;
  if (typeof copied !== "number" || !Number.isSafeInteger(copied) || copied < 0 || copied > COPY_LIMIT) {
    return gap("truncated_capture", "copy_bounds");
  }
  if (frame != null && (typeof frame !== "number" || !Number.isSafeInteger(frame) || frame < 0)) {
    return gap("truncated_capture", "frame_length");
  }
  if (copied === 0 || (frame != null && (frame > COPY_LIMIT || copied < frame))) {
    return gap("truncated_capture", "short_copy");
  }
  return {
    capture: "complete",
    decision: "HAND_TO_PARSER",
    parse: true,
    reason: "within_copy_limit",
    copiedBytes: copied,
    host_attach: HOST_ATTACH,
    label: "Lab-only",
  };
}
