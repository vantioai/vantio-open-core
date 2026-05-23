import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";

/**
 * Immutable context object propagated through every async hop
 * of a single withVantio execution frame.
 */
export interface VantioContext {
  readonly traceId: string;
}

/**
 * Options accepted by withVantio.
 */
export interface WithVantioOptions {
  /**
   * Supply an explicit trace ID instead of generating one.
   * Useful for continuing a trace across process boundaries.
   */
  traceId?: string;
}

// Single AsyncLocalStorage instance shared across the module.
// Never exported — callers interact only through the public API.
const _storage = new AsyncLocalStorage<VantioContext>();

/**
 * Wraps an asynchronous agent callback in a Vantio execution context.
 *
 * - Generates (or accepts) a VANTIO_TRACE_ID via `crypto.randomUUID()`.
 * - Propagates the ID through the full async call-tree via AsyncLocalStorage
 *   without patching any native modules or global objects.
 * - The returned promise settles with whatever the callback resolves/rejects with.
 *
 * @example
 * ```ts
 * const result = await withVantio(async () => {
 *   console.log(getCurrentTraceId()); // "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
 *   return runMyAgent();
 * });
 * ```
 */
export async function withVantio<T>(
  callback: () => Promise<T>,
  options: WithVantioOptions = {},
): Promise<T> {
  const traceId = options.traceId ?? randomUUID();
  const ctx: VantioContext = { traceId };
  return _storage.run(ctx, callback);
}

/**
 * Returns the VANTIO_TRACE_ID for the current async execution context,
 * or `undefined` when called outside of a withVantio frame.
 *
 * @example
 * ```ts
 * await withVantio(async () => {
 *   const id = getCurrentTraceId(); // always defined here
 *   await fetch(`/api/log?trace=${id}`);
 * });
 *
 * getCurrentTraceId(); // undefined — outside withVantio frame
 * ```
 */
export function getCurrentTraceId(): string | undefined {
  return _storage.getStore()?.traceId;
}

/**
 * Returns the full VantioContext for the current async execution context,
 * or `undefined` when called outside of a withVantio frame.
 */
export function getCurrentContext(): VantioContext | undefined {
  return _storage.getStore();
}
