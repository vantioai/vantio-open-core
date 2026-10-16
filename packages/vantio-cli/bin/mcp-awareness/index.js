/**
 * Package entry. createRuntime() does not accept a key.
 * The test helper that injects a key is not exported from here.
 */

import { productionKey, assemble } from "./runtime.js";

export function createRuntime() {
  return assemble(productionKey());
}

export { normalizePolicy } from "./policy.js";
