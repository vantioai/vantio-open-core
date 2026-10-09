// Destinations the Node interceptor may record. Keep in lockstep with
// vantio-open-core/packages/vantio-agent-sdk-py/vantio/_http_observe.py
//
// Exact DNS names plus regional patterns verified against provider docs
// (2026-08-14). Do not add company NEVER_BLOCK SaaS, Cursor, or whole-cloud
// suffixes such as amazonaws.com / googleapis.com.

"use strict";

const LLM_HOSTS = [
  "api.openai.com",
  "api.anthropic.com",
  "generativelanguage.googleapis.com",
  "api.cohere.ai",
  "api.cohere.com",
  "api.mistral.ai",
  "api.groq.com",
  "api.together.xyz",
  "api.perplexity.ai",
  "inference.ai.azure.com",
  "openai.azure.com",
  "api.x.ai",
  "api.deepseek.com",
  "api.fireworks.ai",
  "openrouter.ai",
  "api.cerebras.ai",
  "api.voyageai.com",
  "api.sambanova.ai",
  "api.deepinfra.com",
  "router.huggingface.co",
  "api-inference.huggingface.co",
  "api.replicate.com",
  "ollama.com",
  "integrate.api.nvidia.com",
];

function hostListed(hostname, items) {
  const h = String(hostname || "").toLowerCase();
  if (!h) return false;
  const arr = items && typeof items.has === "function" ? [...items] : Array.isArray(items) ? items : [];
  for (const item of arr) {
    const b = String(item || "").toLowerCase().trim();
    if (!b) continue;
    if (h === b) return true;
    // Suffix match only when the listed host looks like a DNS name (has a dot)
    // so a bare token like "com" cannot sweep the internet.
    if (b.includes(".") && h.endsWith("." + b)) return true;
  }
  return false;
}

/** Regional / infix API DNS that exact+suffix matching cannot cover honestly. */
function hostMatchesRegional(hostname) {
  const h = String(hostname || "").toLowerCase();
  if (!h) return false;
  // Amazon Bedrock Runtime + Mantle + Agents Runtime (region is a DNS label).
  if (/^bedrock-runtime(-fips)?\.[a-z0-9-]+\.amazonaws\.com$/.test(h)) return true;
  if (/^bedrock-mantle\.[a-z0-9-]+\.api\.aws$/.test(h)) return true;
  if (/^bedrock-agent-runtime(-fips)?\.[a-z0-9-]+\.amazonaws\.com$/.test(h)) return true;
  // Google Vertex AI: global, {region}-aiplatform, multi-region REP.
  if (h === "aiplatform.googleapis.com") return true;
  if (h.endsWith("-aiplatform.googleapis.com") && h.includes(".")) return true;
  if (/^aiplatform\.(us|eu)\.rep\.googleapis\.com$/.test(h)) return true;
  // Hugging Face Inference Endpoints: {name}.{region}.endpoints.huggingface.cloud
  if (h === "endpoints.huggingface.cloud" || h.endsWith(".endpoints.huggingface.cloud")) return true;
  return false;
}

function isOllamaLocal(hostname, port) {
  const h = String(hostname || "").toLowerCase();
  const p = String(port == null ? "" : port);
  if (p !== "11434") return false;
  return h === "localhost" || h === "127.0.0.1" || h === "::1" || h === "[::1]";
}

function catalogInScope(hostname, port, hosts) {
  return (
    hostListed(hostname, hosts) ||
    hostMatchesRegional(hostname) ||
    isOllamaLocal(hostname, port)
  );
}

const PROVIDER_BY_HOST = Object.freeze({
  "api.openai.com": "openai",
  "api.anthropic.com": "anthropic",
  "generativelanguage.googleapis.com": "google",
  "api.cohere.ai": "cohere",
  "api.cohere.com": "cohere",
  "api.mistral.ai": "mistral",
  "api.groq.com": "groq",
  "api.together.xyz": "together",
  "api.perplexity.ai": "perplexity",
  "inference.ai.azure.com": "azure_openai",
  "openai.azure.com": "azure_openai",
  "api.x.ai": "xai",
  "api.deepseek.com": "deepseek",
  "api.fireworks.ai": "fireworks",
  "openrouter.ai": "openrouter",
  "api.cerebras.ai": "cerebras",
  "api.voyageai.com": "voyage",
  "api.sambanova.ai": "sambanova",
  "api.deepinfra.com": "deepinfra",
  "router.huggingface.co": "huggingface",
  "api-inference.huggingface.co": "huggingface",
  "api.replicate.com": "replicate",
  "ollama.com": "ollama",
  "integrate.api.nvidia.com": "nvidia",
});

function hostMatchesCatalog(hostname, listed) {
  const h = String(hostname || "").toLowerCase();
  const b = String(listed || "").toLowerCase();
  if (!h || !b) return false;
  return h === b || h.endsWith("." + b);
}

function guessProvider(hostname, port) {
  const h = String(hostname || "").toLowerCase();
  if (!h) return "unknown";
  if (isOllamaLocal(hostname, port)) return "ollama";
  if (/^bedrock-(runtime(-fips)?|agent-runtime(-fips)?)\.[a-z0-9-]+\.amazonaws\.com$/.test(h)) return "bedrock";
  if (/^bedrock-mantle\.[a-z0-9-]+\.api\.aws$/.test(h)) return "bedrock";
  if (h === "aiplatform.googleapis.com" || h.endsWith("-aiplatform.googleapis.com")) return "vertex";
  if (/^aiplatform\.(us|eu)\.rep\.googleapis\.com$/.test(h)) return "vertex";
  if (h === "endpoints.huggingface.cloud" || h.endsWith(".endpoints.huggingface.cloud")) return "huggingface";
  for (const listed of Object.keys(PROVIDER_BY_HOST)) {
    if (hostMatchesCatalog(h, listed)) return PROVIDER_BY_HOST[listed];
  }
  if (h === "localhost" || h === "127.0.0.1" || h === "::1" || h === "[::1]") return "local";
  return "other";
}

module.exports = {
  LLM_HOSTS,
  hostListed,
  hostMatchesRegional,
  isOllamaLocal,
  catalogInScope,
  guessProvider,
};
