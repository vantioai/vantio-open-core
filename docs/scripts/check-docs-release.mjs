import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { checkRelease } from "./docs-release-lib.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const result = checkRelease(root);
const payload = {
  ok: result.ok,
  checks: result.checks.map((check) => ({ id: check.id, ok: check.ok })),
  failures: result.failures,
};
process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
process.exit(result.ok ? 0 : 1);
