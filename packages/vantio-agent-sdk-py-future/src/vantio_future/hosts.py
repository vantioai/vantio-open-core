"""In-scope hosts for the future observer.

The static set matches the sealed 3.1.0 host list so a future shield covers
the same names. Extra hosts come from `VANTIO_EXTRA_LLM_HOSTS`.
"""

import os

_LLM_HOSTS = {
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
}


def _extra_hosts():
    raw = os.environ.get("VANTIO_EXTRA_LLM_HOSTS", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def host_in_scope(hostname):
    host = (hostname or "").strip().lower()
    if not host:
        return False
    listed = _LLM_HOSTS | _extra_hosts()
    if host in listed:
        return True
    for item in listed:
        if item and "." in item and host.endswith("." + item):
            return True
    return False
