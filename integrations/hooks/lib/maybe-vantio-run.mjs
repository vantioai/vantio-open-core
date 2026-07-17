#!/usr/bin/env node
/**
 * Hook helper: if VANTIO_HOOKS=1 and the command looks like a Node agent,
 * rewrite to `vantio run …`. Prints JSON guidance for hosts that expect stdout.
 * Never fails the parent hard — observe is opt-in.
 */
const raw = process.env.CURSOR_HOOK_COMMAND || process.argv.slice(2).join(" ") || "";
const enabled = process.env.VANTIO_HOOKS === "1" || process.env.VANTIO_HOOKS === "true";

const looksLikeNodeAgent =
  /\b(node|tsx|ts-node|npx)\b/.test(raw) &&
  !/\bvantio\s+run\b/.test(raw);

if (!enabled || !looksLikeNodeAgent) {
  console.log(
    JSON.stringify({
      ok: true,
      rewritten: false,
      hint: "Set VANTIO_HOOKS=1 to auto-wrap node/tsx with vantio run",
    }),
  );
  process.exit(0);
}

const rewritten = `vantio run ${raw}`;
console.log(
  JSON.stringify({
    ok: true,
    rewritten: true,
    command: rewritten,
    plane: "Observe",
    brand: "Vantio Optics",
  }),
);
process.exit(0);
