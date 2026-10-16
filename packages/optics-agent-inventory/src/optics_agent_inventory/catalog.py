"""Closed catalogs. Endpoint hosts stay aligned with llm-hosts.cjs."""

from __future__ import annotations

import re

COMM_LIMIT = 15

LLM_HOSTS = (
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
)

AGENT_BINARIES = (
    "claude",
    "claude-code",
    "codex",
    "cursor-agent",
    "aider",
    "goose",
    "cody",
)

MODEL_BINARIES = (
    "ollama",
    "ollama-runner",
    "llama-server",
    "vllm",
    "lmstudio",
    "text-generation-launcher",
)

INTERACTIVE_BINARIES = (
    "curl",
    "wget",
    "httpie",
    "aria2c",
    "chrome",
    "chromium",
    "firefox",
    "msedge",
)

CREDENTIAL_NAMES = frozenset(
    {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "MISTRAL_API_KEY",
        "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY",
        "DEEPSEEK_API_KEY",
        "COHERE_API_KEY",
        "XAI_API_KEY",
    }
)

PROVIDERS = frozenset(
    {
        "unknown",
        "ollama",
        "openai",
        "anthropic",
        "vertex",
        "google",
        "cohere",
        "mistral",
        "groq",
        "together",
        "perplexity",
        "azure_openai",
        "xai",
        "deepseek",
        "fireworks",
        "openrouter",
        "cerebras",
        "voyage",
        "sambanova",
        "deepinfra",
        "bedrock",
        "huggingface",
        "replicate",
        "nvidia",
        "local",
        "other",
    }
)

ROLES = (
    "local_model_server",
    "mcp_server",
    "agent_runtime",
    "api_client",
    "credential_only",
)

SIDECAR_ROLES = frozenset({"local_model_server", "mcp_server"})

_BEDROCK_RUNTIME = re.compile(r"^bedrock-runtime(-fips)?\.[a-z0-9-]+\.amazonaws\.com$")
_BEDROCK_MANTLE = re.compile(r"^bedrock-mantle\.[a-z0-9-]+\.api\.aws$")
_BEDROCK_AGENT = re.compile(r"^bedrock-agent-runtime(-fips)?\.[a-z0-9-]+\.amazonaws\.com$")
_VERTEX_REP = re.compile(r"^aiplatform\.(us|eu)\.rep\.googleapis\.com$")
_FLAG = re.compile(r"^--?[A-Za-z0-9-]{1,40}$")
_MCP_NAME = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_LAB_HOSTNAME = re.compile(r"^vantio-t3-[a-z0-9-]{1,40}$")


def host_listed(hostname: str, extra: tuple[str, ...]) -> bool:
    host = (hostname or "").lower()
    if not host:
        return False
    for item in (*LLM_HOSTS, *extra):
        listed = (item or "").lower().strip()
        if not listed:
            continue
        if host == listed:
            return True
        if "." in listed and host.endswith("." + listed):
            return True
    return False


def host_matches_regional(hostname: str) -> bool:
    host = (hostname or "").lower()
    if not host:
        return False
    if _BEDROCK_RUNTIME.match(host) or _BEDROCK_MANTLE.match(host) or _BEDROCK_AGENT.match(host):
        return True
    if host == "aiplatform.googleapis.com":
        return True
    if host.endswith("-aiplatform.googleapis.com") and "." in host:
        return True
    if _VERTEX_REP.match(host):
        return True
    if host == "endpoints.huggingface.cloud" or host.endswith(".endpoints.huggingface.cloud"):
        return True
    return False


def is_ollama_local(hostname: str, port: int | None) -> bool:
    host = (hostname or "").lower()
    if port != 11434:
        return False
    return host in {"localhost", "127.0.0.1", "::1", "[::1]"}


def catalog_in_scope(hostname: str, port: int | None, extra: tuple[str, ...]) -> bool:
    return host_listed(hostname, extra) or host_matches_regional(hostname) or is_ollama_local(hostname, port)


def guess_provider(hostname: str, port: int | None) -> str:
    host = (hostname or "").lower()
    if not host:
        return "unknown"
    if is_ollama_local(hostname, port) or host == "ollama.com" or host.endswith(".ollama.com"):
        return "ollama"
    if "openai" in host or host == "api.openai.com":
        return "openai"
    if "anthropic" in host:
        return "anthropic"
    if "aiplatform" in host:
        return "vertex"
    if "googleapis" in host or "generativelanguage" in host:
        return "google"
    if "cohere" in host:
        return "cohere"
    if "mistral" in host:
        return "mistral"
    if "groq" in host:
        return "groq"
    if "together" in host:
        return "together"
    if "perplexity" in host:
        return "perplexity"
    if "azure" in host or "openai.azure" in host:
        return "azure_openai"
    if "x.ai" in host or host.endswith(".x.ai"):
        return "xai"
    if "deepseek" in host:
        return "deepseek"
    if "fireworks" in host:
        return "fireworks"
    if "openrouter" in host:
        return "openrouter"
    if "cerebras" in host:
        return "cerebras"
    if "voyageai" in host:
        return "voyage"
    if "sambanova" in host:
        return "sambanova"
    if "deepinfra" in host:
        return "deepinfra"
    if "bedrock" in host:
        return "bedrock"
    if "huggingface" in host or host.endswith(".huggingface.cloud"):
        return "huggingface"
    if "replicate" in host:
        return "replicate"
    if "nvidia" in host:
        return "nvidia"
    if "localhost" in host or host.startswith("127."):
        return "local"
    return "other"


def extra_hosts_from_env(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    kept: list[str] = []
    for token in raw.split(","):
        host = token.strip().lower()
        if not host or "." not in host:
            continue
        if any(mark in host for mark in ("@", "/", "?", " ")):
            continue
        kept.append(host)
    return tuple(kept)


def basename_matches(name: str | None, catalog: tuple[str, ...]) -> bool:
    if not name:
        return False
    base = name.rsplit("/", 1)[-1].lower()
    for item in catalog:
        full = item.lower()
        if base == full:
            return True
        if len(full) > COMM_LIMIT and base == full[:COMM_LIMIT]:
            return True
    return False


def is_mcp_basename(name: str | None) -> bool:
    if not name:
        return False
    base = name.rsplit("/", 1)[-1].lower()
    if base == "mcp-server":
        return True
    if base.startswith("mcp-server-") or base.startswith("mcp-server."):
        return True
    return False


def is_flag(token: str) -> bool:
    return _FLAG.match(token) is not None


def is_mcp_server_name(name: str) -> bool:
    return _MCP_NAME.match(name) is not None


def is_lab_hostname(name: str) -> bool:
    return _LAB_HOSTNAME.match(name) is not None
