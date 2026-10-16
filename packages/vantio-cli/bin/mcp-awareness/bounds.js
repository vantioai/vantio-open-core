/** Caps from the T4 design. Past a cap the walker stops storing and marks truncation. */

export const MAX_FRAME = 256 * 1024;
export const MAX_DEPTH = 32;
export const MAX_KEYS = 64;
export const MAX_ARRAY = 128;
export const MAX_SHAPE_NODES = 256;
export const MAX_TOOLS = 256;
export const MAX_SESSIONS = 64;
export const MAX_TOMBSTONES = 64;
export const MAX_PENDING = 128;
export const MAX_RETAIN_KEYS = 8;
export const MAX_RETAIN_BYTES = 512;
export const MAX_NAME = 128;
export const MAX_NESTED_OBJECTS = 8;
export const MAX_NESTED_BYTES = 64 * 1024;
export const MAX_CANON = 64 * 1024;
export const MAX_PROPERTY_NAMES = 64;
export const MAX_ENUM = 16;
export const MAX_TAPS = 64;
export const MAX_GATES = 64;

export const ACTIONS = ["ALLOW", "LOG", "WOULD_BLOCK", "BLOCK", "GAP"];

export const KNOWN_METHODS = [
  "initialize",
  "ping",
  "completion/complete",
  "logging/setLevel",
  "prompts/get",
  "prompts/list",
  "resources/list",
  "resources/templates/list",
  "resources/read",
  "resources/subscribe",
  "resources/unsubscribe",
  "tools/call",
  "tools/list",
  "notifications/initialized",
  "notifications/cancelled",
  "notifications/progress",
  "notifications/message",
  "notifications/prompts/list_changed",
  "notifications/resources/list_changed",
  "notifications/resources/updated",
  "notifications/tools/list_changed",
  "notifications/roots/list_changed",
  "sampling/createMessage",
  "roots/list",
  "elicitation/create",
];

const KNOWN = new Set(KNOWN_METHODS);

export function isKnownMethod(method) {
  return KNOWN.has(method);
}

export function blank() {
  return Object.create(null);
}
