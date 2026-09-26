"""Customer-facing Optics outcome lines.

Machine tokens stay SUCCESS, APPLICATION_ERROR, NOT_OBSERVED, UNAVAILABLE,
PARTIAL, and OPTICS_ERROR. This module only chooses the human lines a customer
reads: Optics status, observed outcome, and provider response.
"""
from __future__ import annotations

import errno
import http.client
import socket
import ssl
from typing import Any, Optional

SCHEMA_STATUS = "unstable-pre-1.0"

# Exact catalog hosts. Identity is never inferred from a substring of an
# arbitrary hostname. Keep the host set aligned with _LLM_HOSTS.
_CATALOG: dict[str, tuple[str, str]] = {
    "api.openai.com": ("openai", "OpenAI"),
    "api.anthropic.com": ("anthropic", "Anthropic"),
    "generativelanguage.googleapis.com": ("google", "Google"),
    "api.cohere.ai": ("cohere", "Cohere"),
    "api.cohere.com": ("cohere", "Cohere"),
    "api.mistral.ai": ("mistral", "Mistral"),
    "api.groq.com": ("groq", "Groq"),
    "api.together.xyz": ("together", "Together"),
    "api.perplexity.ai": ("perplexity", "Perplexity"),
    "inference.ai.azure.com": ("azure_openai", "Azure OpenAI"),
    "openai.azure.com": ("azure_openai", "Azure OpenAI"),
    "api.x.ai": ("xai", "xAI"),
    "api.deepseek.com": ("deepseek", "DeepSeek"),
    "api.fireworks.ai": ("fireworks", "Fireworks"),
    "openrouter.ai": ("openrouter", "OpenRouter"),
    "api.cerebras.ai": ("cerebras", "Cerebras"),
    "api.voyageai.com": ("voyage", "Voyage"),
    "api.sambanova.ai": ("sambanova", "SambaNova"),
    "api.deepinfra.com": ("deepinfra", "DeepInfra"),
    "router.huggingface.co": ("huggingface", "Hugging Face"),
    "api-inference.huggingface.co": ("huggingface", "Hugging Face"),
    "api.replicate.com": ("replicate", "Replicate"),
    "ollama.com": ("ollama", "Ollama"),
    "integrate.api.nvidia.com": ("nvidia", "NVIDIA"),
}

_HTTP_OUTCOME = {
    400: "Provider rejected the request",
    401: "Provider authentication failed",
    403: "Provider denied the request",
    404: "Provider endpoint not found",
    408: "Provider request timed out",
    409: "Provider reported a request conflict",
    422: "Provider could not process the request",
    429: "Provider rate-limited the request",
}

_CAUSE_LIMIT = 6

_DNS_ERRNOS = {
    getattr(socket, "EAI_NONAME", None),
    getattr(socket, "EAI_AGAIN", None),
    getattr(socket, "EAI_FAIL", None),
}
_DNS_ERRNOS.discard(None)


def http_outcome_label(status: int) -> str:
    """Human observed outcome for an exact HTTP status. Does not invent a code."""
    if 200 <= status < 400:
        return "Successful"
    specific = _HTTP_OUTCOME.get(status)
    if specific is not None:
        return specific
    if 500 <= status <= 599:
        return "Provider service error"
    if 400 <= status <= 499:
        return "Provider rejected the request"
    return "Provider outcome unavailable"


def http_response_text(status: int) -> str:
    """Concrete provider response line. Reason text comes from the stdlib table."""
    reason = http.client.responses.get(status)
    if reason:
        return f"HTTP {status} {reason}"
    return f"HTTP {status}"


def next_action_for_status(status: int) -> tuple[str, str]:
    """Remediation first for an unsuccessful provider response. Inspection for success."""
    if 200 <= status < 400:
        return (
            "inspection",
            "No provider change is needed. The local Optics record is in the run log for this shield() trace.",
        )
    if status == 401:
        return (
            "remediation",
            "Check the API credential the agent sent, then run again under shield().",
        )
    if status == 403:
        return (
            "remediation",
            "Check the provider account permission, then run again under shield().",
        )
    if status == 429:
        return (
            "remediation",
            "Wait and retry the provider request. Optics only recorded the response.",
        )
    if 500 <= status <= 599:
        return (
            "remediation",
            "Retry later. The provider returned a service error.",
        )
    if status == 404:
        return (
            "remediation",
            "Check the request path the agent sent. The provider endpoint was not found.",
        )
    if status == 408:
        return (
            "remediation",
            "Check the request the agent sent. The provider request timed out.",
        )
    if status == 409:
        return (
            "remediation",
            "Check the request the agent sent. The provider reported a request conflict.",
        )
    if status == 422:
        return (
            "remediation",
            "Check the request the agent sent (method, path, parameters). The provider could not process the request.",
        )
    return (
        "remediation",
        "Check the request the agent sent (method, path, parameters). The provider rejected the request.",
    )


def _regional_provider(hostname: str) -> Optional[tuple[str, str]]:
    h = hostname
    if h.startswith("bedrock-runtime") and h.endswith(".amazonaws.com"):
        labels = h.split(".")
        if len(labels) == 4 and labels[0] in ("bedrock-runtime", "bedrock-runtime-fips"):
            return ("bedrock", "Bedrock")
    if h.startswith("bedrock-mantle.") and h.endswith(".api.aws"):
        labels = h.split(".")
        if len(labels) == 4 and labels[0] == "bedrock-mantle":
            return ("bedrock", "Bedrock")
    if h.startswith("bedrock-agent-runtime") and h.endswith(".amazonaws.com"):
        labels = h.split(".")
        if len(labels) == 4 and labels[0] in (
            "bedrock-agent-runtime",
            "bedrock-agent-runtime-fips",
        ):
            return ("bedrock", "Bedrock")
    if h == "aiplatform.googleapis.com" or h.endswith("-aiplatform.googleapis.com"):
        return ("vertex", "Vertex")
    if h in ("aiplatform.us.rep.googleapis.com", "aiplatform.eu.rep.googleapis.com"):
        return ("vertex", "Vertex")
    if h == "endpoints.huggingface.cloud" or h.endswith(".endpoints.huggingface.cloud"):
        return ("huggingface", "Hugging Face")
    return None


def resolve_provider(hostname: str, port: Optional[str] = None) -> Optional[tuple[str, str]]:
    """Catalog provider id and display name, or None when the host is not in the map."""
    h = (hostname or "").lower().strip().strip("[]")
    if not h:
        return None
    exact = _CATALOG.get(h)
    if exact is not None:
        return exact
    for host, ident in _CATALOG.items():
        if h.endswith("." + host):
            return ident
    regional = _regional_provider(h)
    if regional is not None:
        return regional
    if str(port or "") == "11434" and h in ("localhost", "127.0.0.1", "::1"):
        return ("ollama", "Ollama")
    return None


def _classify_one(exc: BaseException) -> Optional[tuple[str, str]]:
    if isinstance(exc, ssl.SSLError):
        return "tls", "TLS handshake failed"
    if isinstance(exc, socket.gaierror):
        return "dns", "DNS lookup failed"
    if isinstance(exc, ConnectionRefusedError):
        return "connection", "Connection refused"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "connection", "Connection timed out"
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError)):
        return "connection", "Connection failed"
    err = getattr(exc, "errno", None)
    if isinstance(err, int):
        if err in _DNS_ERRNOS:
            return "dns", "DNS lookup failed"
        if err == errno.ECONNREFUSED:
            return "connection", "Connection refused"
        if err == errno.ETIMEDOUT:
            return "connection", "Connection timed out"
        if err in (errno.EHOSTUNREACH, errno.ENETUNREACH, errno.ECONNRESET):
            return "connection", "Connection failed"
    return None


def classify_exception(exc: BaseException, depth: int = 0) -> tuple[str, str]:
    """Transport kind and a fixed response phrase. Never returns the exception text."""
    if depth > _CAUSE_LIMIT:
        return "wrapped", type(exc).__name__
    found = _classify_one(exc)
    if found is not None:
        return found
    reason = getattr(exc, "reason", None)
    if isinstance(reason, BaseException) and reason is not exc:
        kind, phrase = classify_exception(reason, depth + 1)
        if kind != "wrapped":
            return kind, phrase
    cause = exc.__cause__
    if isinstance(cause, BaseException) and cause is not exc:
        kind, phrase = classify_exception(cause, depth + 1)
        if kind != "wrapped":
            return kind, phrase
    return "wrapped", type(exc).__name__


def socket_failure(error_class: str) -> tuple[str, str]:
    """Map a connect-path class name to a transport kind. The name is not a message."""
    name = error_class or "OSError"
    if name.startswith("SSL"):
        return "tls", "TLS handshake failed"
    if name == "gaierror":
        return "dns", "DNS lookup failed"
    if name == "ConnectionRefusedError":
        return "connection", "Connection refused"
    if name in ("TimeoutError", "timeout"):
        return "connection", "Connection timed out"
    return "connection", "Connection failed"


def _transport_outcome(kind: str, phrase: str) -> tuple[str, str, str, str]:
    if kind == "dns":
        return (
            "Provider could not be resolved",
            phrase or "DNS lookup failed",
            "remediation",
            "Check the provider hostname. DNS did not resolve.",
        )
    if kind == "connection":
        return (
            "Connection to provider failed",
            phrase or "Connection failed",
            "remediation",
            "Check network reachability to the provider.",
        )
    if kind == "tls":
        return (
            "Secure connection to provider failed",
            phrase or "TLS handshake failed",
            "remediation",
            "Check the TLS setup. The secure connection did not complete.",
        )
    return (
        "Wrapped application raised an exception",
        phrase or "Exception",
        "remediation",
        "The wrapped application raised an exception before a provider response. Fix that exception and run again under shield().",
    )


def _unavailable_outcome() -> tuple[str, str, str, str]:
    return (
        "Provider outcome unavailable",
        "No HTTP response",
        "inspection",
        "Optics recorded the call and no provider outcome was available.",
    )


def apply_customer_outcome(rec: dict[str, Any]) -> None:
    """Add human outcome fields. Leaves opticsStatus, applicationStatus, and status in place."""
    status = rec.get("status")
    if isinstance(status, int) and not isinstance(status, bool):
        label = http_outcome_label(status)
        response = http_response_text(status)
        category, action = next_action_for_status(status)
    else:
        kind = rec.get("failure_kind")
        if kind in ("dns", "connection", "tls", "wrapped"):
            phrase = str(rec.pop("failure_response", "") or "")
            if kind == "wrapped":
                phrase = str(rec.get("error_class") or phrase or "Exception")
            label, response, category, action = _transport_outcome(str(kind), phrase)
        else:
            rec.pop("failure_response", None)
            label, response, category, action = _unavailable_outcome()
    rec["applicationOutcomeLabel"] = label
    rec["applicationLabel"] = label
    identity = resolve_provider(str(rec.get("hostname") or ""), rec.get("port") if rec.get("port") is not None else None)
    if identity is not None:
        provider_id, provider_name = identity
        rec["providerName"] = provider_name
        rec["destination"] = rec.get("hostname") or ""
        rec["providerResponseLabel"] = "Provider response"
        if rec.get("provider") in (None, "", "other"):
            rec["provider"] = provider_id
    else:
        host = str(rec.get("hostname") or "")
        if host:
            rec["upstreamService"] = host
        rec["providerResponseLabel"] = "Upstream response"
    rec["providerResponse"] = response
    rec["nextActionCategory"] = category
    rec["nextAction"] = action


def empty_observation() -> dict[str, str]:
    """View for a shield() trace that recorded no supported call. Not a run log by itself."""
    return {
        "schema_status": SCHEMA_STATUS,
        "opticsStatus": "NOT_OBSERVED",
        "applicationStatus": "NOT_OBSERVED",
        "opticsLabel": "Not observed",
        "applicationOutcomeLabel": "No supported AI call observed",
        "applicationLabel": "No supported AI call observed",
        "providerResponseLabel": "Upstream response",
        "providerResponse": "",
        "nextActionCategory": "inspection",
        "nextAction": "No supported AI call was observed. Confirm the agent calls a supported host under shield().",
    }


def summarize_customer_fields(calls: list[dict[str, Any]], application_status: str) -> dict[str, str]:
    """Run-summary human lines. Per-call labels stay specific. Mixed lines read Partial."""
    if not calls or application_status == "NOT_OBSERVED":
        empty = empty_observation()
        return {
            "applicationOutcomeLabel": empty["applicationOutcomeLabel"],
            "applicationLabel": empty["applicationLabel"],
            "providerResponseLabel": empty["providerResponseLabel"],
            "providerResponse": empty["providerResponse"],
            "nextActionCategory": empty["nextActionCategory"],
            "nextAction": empty["nextAction"],
        }
    labels = {str(call.get("applicationOutcomeLabel") or "") for call in calls}
    responses = {str(call.get("providerResponse") or "") for call in calls}
    response_labels = {str(call.get("providerResponseLabel") or "") for call in calls}
    mixed = application_status == "PARTIAL" or len(labels) > 1
    if mixed:
        if len(responses) == 1:
            response = next(iter(responses))
        else:
            response = "Multiple provider responses"
        if len(response_labels) == 1:
            response_label = next(iter(response_labels))
        else:
            response_label = "Provider response"
        return {
            "applicationOutcomeLabel": "Partial",
            "applicationLabel": "Partial",
            "providerResponseLabel": response_label,
            "providerResponse": response,
            "nextActionCategory": "inspection",
            "nextAction": "This run has more than one observed outcome. Review each call in the local run log.",
        }
    sample = calls[0]
    return {
        "applicationOutcomeLabel": str(sample.get("applicationOutcomeLabel") or ""),
        "applicationLabel": str(sample.get("applicationOutcomeLabel") or ""),
        "providerResponseLabel": str(sample.get("providerResponseLabel") or "Upstream response"),
        "providerResponse": str(sample.get("providerResponse") or ""),
        "nextActionCategory": str(sample.get("nextActionCategory") or "inspection"),
        "nextAction": str(sample.get("nextAction") or ""),
    }


def customer_view_lines(rec: dict[str, Any]) -> list[str]:
    """Three customer lines. Optics status, observed outcome, then the response heading."""
    heading = str(rec.get("providerResponseLabel") or "Provider response")
    return [
        f"Optics status: {rec.get('opticsLabel', '')}",
        f"Observed outcome: {rec.get('applicationOutcomeLabel', '')}",
        f"{heading}: {rec.get('providerResponse', '')}",
    ]
