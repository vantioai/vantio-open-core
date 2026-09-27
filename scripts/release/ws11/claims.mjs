import { readFileSync } from "node:fs";
import { join } from "node:path";

export function loadRequirements(root) {
  const catalog = JSON.parse(readFileSync(join(root, "docs/programs/release-engineering/REQUIREMENTS.json"), "utf8"));
  return {
    ids: catalog.requirements.map((item) => item.id),
    patterns: catalog.forbidden_claim_patterns.map((source) => new RegExp(source, "i")),
  };
}

export function findForbiddenClaims(value, patterns, path = "$") {
  const hits = [];
  if (typeof value === "string") {
    for (const pattern of patterns) {
      if (pattern.test(value)) hits.push({ path, pattern: pattern.source });
    }
    return hits;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => hits.push(...findForbiddenClaims(item, patterns, `${path}[${index}]`)));
    return hits;
  }
  if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      if (key === "forbidden_claim_patterns") continue;
      hits.push(...findForbiddenClaims(child, patterns, `${path}.${key}`));
    }
  }
  return hits;
}
