import { createRequire } from "node:module";
import { describe, test } from "node:test";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const {
  LLM_HOSTS,
  catalogInScope,
  hostListed,
  hostMatchesRegional,
  isOllamaLocal,
  guessProvider,
} = require("../bin/llm-hosts.cjs");

describe("llm-hosts catalog", () => {
  test("existing OpenAI and Anthropic hosts stay in scope", () => {
    assert.equal(catalogInScope("api.openai.com", "443", LLM_HOSTS), true);
    assert.equal(catalogInScope("eastus.api.openai.com", "443", LLM_HOSTS), true);
    assert.equal(catalogInScope("api.anthropic.com", "443", LLM_HOSTS), true);
  });

  test("Amazon Bedrock regional runtime hosts are in scope; whole AWS is not", () => {
    assert.equal(hostMatchesRegional("bedrock-runtime.us-east-1.amazonaws.com"), true);
    assert.equal(hostMatchesRegional("bedrock-runtime-fips.us-west-2.amazonaws.com"), true);
    assert.equal(hostMatchesRegional("bedrock-mantle.us-east-1.api.aws"), true);
    assert.equal(hostMatchesRegional("bedrock-agent-runtime.eu-west-1.amazonaws.com"), true);
    assert.equal(catalogInScope("bedrock-runtime.us-east-1.amazonaws.com", "443", LLM_HOSTS), true);
    assert.equal(hostMatchesRegional("s3.us-east-1.amazonaws.com"), false);
    assert.equal(catalogInScope("s3.amazonaws.com", "443", LLM_HOSTS), false);
    assert.equal(guessProvider("bedrock-runtime.us-east-1.amazonaws.com"), "bedrock");
  });

  test("Google Vertex AI regional and REP hosts are in scope; generic googleapis is not", () => {
    assert.equal(hostMatchesRegional("aiplatform.googleapis.com"), true);
    assert.equal(hostMatchesRegional("us-central1-aiplatform.googleapis.com"), true);
    assert.equal(hostMatchesRegional("aiplatform.us.rep.googleapis.com"), true);
    assert.equal(hostMatchesRegional("aiplatform.eu.rep.googleapis.com"), true);
    assert.equal(catalogInScope("europe-west1-aiplatform.googleapis.com", "443", LLM_HOSTS), true);
    assert.equal(catalogInScope("www.googleapis.com", "443", LLM_HOSTS), false);
    assert.equal(catalogInScope("generativelanguage.googleapis.com", "443", LLM_HOSTS), true);
    assert.equal(guessProvider("us-central1-aiplatform.googleapis.com"), "vertex");
  });

  test("Hugging Face inference, Replicate, Ollama cloud, NVIDIA NIM are in scope", () => {
    assert.equal(catalogInScope("router.huggingface.co", "443", LLM_HOSTS), true);
    assert.equal(catalogInScope("api-inference.huggingface.co", "443", LLM_HOSTS), true);
    assert.equal(catalogInScope("my-ep.us-east-1.endpoints.huggingface.cloud", "443", LLM_HOSTS), true);
    assert.equal(catalogInScope("huggingface.co", "443", LLM_HOSTS), false);
    assert.equal(catalogInScope("api.replicate.com", "443", LLM_HOSTS), true);
    assert.equal(catalogInScope("ollama.com", "443", LLM_HOSTS), true);
    assert.equal(catalogInScope("integrate.api.nvidia.com", "443", LLM_HOSTS), true);
  });

  test("Ollama localhost is only in scope on port 11434", () => {
    assert.equal(isOllamaLocal("127.0.0.1", "11434"), true);
    assert.equal(isOllamaLocal("localhost", "11434"), true);
    assert.equal(isOllamaLocal("127.0.0.1", "80"), false);
    assert.equal(catalogInScope("127.0.0.1", "11434", LLM_HOSTS), true);
    assert.equal(catalogInScope("127.0.0.1", "9", LLM_HOSTS), false);
    assert.equal(guessProvider("127.0.0.1", "11434"), "ollama");
    assert.equal(guessProvider("127.0.0.1", "80"), "local");
  });

  test("hostListed still suffix-matches regional OpenAI and does not sweep .com", () => {
    assert.equal(hostListed("eastus.api.openai.com", LLM_HOSTS), true);
    assert.equal(hostListed("example.com", LLM_HOSTS), false);
  });
});
