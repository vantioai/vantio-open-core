/**
 * Test-only key injection. Not exported from the package entry.
 * A caller-chosen key would make HMAC values confirmable.
 */

import { assemble } from "./runtime.js";

export function createRuntimeWithKey(key) {
  if (!Buffer.isBuffer(key) || key.length !== 32) {
    throw new Error("test key must be 32 bytes");
  }
  return assemble(key);
}
