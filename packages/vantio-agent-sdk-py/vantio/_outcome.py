"""Customer-facing Optics outcome lines.

Machine tokens stay SUCCESS, APPLICATION_ERROR, NOT_OBSERVED, UNAVAILABLE,
PARTIAL, and OPTICS_ERROR. This module only chooses the human lines a customer
reads: Optics status, observed outcome, and provider response.
"""
from __future__ import annotations

import asyncio
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

# Internal safety caps for exception-chain walking. They are not a customer
# compatibility guarantee: a chain deeper or wider than these limits is
# classified only from the nodes the walk actually visits.
CHAIN_MAX_DEPTH = 8
CHAIN_MAX_VISITS = 16
CHAIN_MAX_ARGS = 8

# Lower rank wins when one attempt carries more than one recognized failure.
_KIND_RANK = {
    "tls": 0,
    "dns": 1,
    "connection": 2,
    "timeout": 3,
    "network": 4,
}

_NETWORK_ERRNOS = {
    errno.EPIPE,
    errno.ENOTCONN,
    errno.ESHUTDOWN,
}

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


def _safe_get(obj: Any, name: str) -> Any:
    """Read one attribute. A hostile property must not escape classification."""
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _classify_one(exc: BaseException) -> Optional[tuple[str, str]]:
    """Kind of this object only. Does not follow a chain or read a message."""
    try:
        if isinstance(exc, ssl.SSLError):
            return "tls", "TLS handshake failed"
        if isinstance(exc, socket.gaierror):
            return "dns", "DNS lookup failed"
        if isinstance(exc, ConnectionRefusedError):
            return "connection", "Connection refused"
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError)):
            return "connection", "Connection failed"
        if isinstance(exc, (TimeoutError, socket.timeout, asyncio.TimeoutError)):
            return "timeout", "Request timed out"
        if isinstance(exc, ConnectionError):
            return "connection", "Connection failed"
        if isinstance(exc, BrokenPipeError):
            return "network", "Network error"
        err = _safe_get(exc, "errno")
        if isinstance(err, int):
            if err in _DNS_ERRNOS:
                return "dns", "DNS lookup failed"
            if err == errno.ECONNREFUSED:
                return "connection", "Connection refused"
            if err == errno.ETIMEDOUT:
                return "timeout", "Request timed out"
            if err in (errno.EHOSTUNREACH, errno.ENETUNREACH, errno.ECONNRESET, errno.ECONNABORTED):
                return "connection", "Connection failed"
            if err in _NETWORK_ERRNOS:
                return "network", "Network error"
    except Exception:
        return None
    return None


def _exception_edges(exc: BaseException) -> list[BaseException]:
    """Allowed links only: cause, context, reason, and exception args.

    This is not an object-graph walk. Arbitrary attributes are ignored.
    """
    found: list[BaseException] = []
    seen: set[int] = set()

    def add(value: Any) -> None:
        if isinstance(value, BaseException) and value is not exc and id(value) not in seen:
            seen.add(id(value))
            found.append(value)

    add(_safe_get(exc, "__cause__"))
    add(_safe_get(exc, "__context__"))
    add(_safe_get(exc, "reason"))
    args = _safe_get(exc, "args")
    if isinstance(args, tuple):
        for item in args[:CHAIN_MAX_ARGS]:
            if isinstance(item, (tuple, list)):
                for sub in list(item)[:CHAIN_MAX_ARGS]:
                    add(sub)
            else:
                add(item)
    return found


def classify_exception(exc: BaseException) -> tuple[str, str]:
    """Best transport kind on a bounded chain. Never returns exception text.

    Walk order is breadth-first: __cause__, then __context__, then .reason
    when it is an exception, then args entries that are exceptions or a
    bounded tuple/list of exceptions. Cycles are skipped. The fixed depth
    and visit caps above are internal safety limits, not a compatibility promise.
    """
    try:
        if not isinstance(exc, BaseException):
            return "wrapped", "Exception"
    except Exception:
        return "wrapped", "Exception"
    best_rank = 99
    best: Optional[tuple[str, str]] = None
    visited: set[int] = set()
    queue: list[tuple[BaseException, int]] = [(exc, 0)]
    while queue and len(visited) < CHAIN_MAX_VISITS:
        current, level = queue.pop(0)
        marker = id(current)
        if marker in visited or level > CHAIN_MAX_DEPTH:
            continue
        visited.add(marker)
        direct = _classify_one(current)
        if direct is not None:
            rank = _KIND_RANK.get(direct[0], 99)
            if rank < best_rank:
                best_rank = rank
                best = direct
                if best_rank == 0:
                    break
        if level >= CHAIN_MAX_DEPTH:
            continue
        try:
            children = _exception_edges(current)
        except Exception:
            children = []
        for child in children:
            if id(child) not in visited:
                queue.append((child, level + 1))
    if best is None:
        try:
            name = type(exc).__name__
        except Exception:
            name = "Exception"
        return "wrapped", name
    return best


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
        return "timeout", "Request timed out"
    return "connection", "Connection failed"


def _failure_lines(kind: str, phrase: str, known: bool) -> tuple[str, str, str, str]:
    """Observed-outcome sentence names the interaction layer, not a fault owner."""
    if kind == "dns":
        label = "Provider could not be resolved" if known else "Upstream service could not be resolved"
        return (
            label,
            phrase or "DNS lookup failed",
            "remediation",
            "Check the hostname the agent called. DNS did not resolve.",
        )
    if kind in ("connection", "network"):
        label = "Connection to provider failed" if known else "Connection to upstream service failed"
        fallback = "Network error" if kind == "network" else "Connection failed"
        return (
            label,
            phrase or fallback,
            "remediation",
            "Check network reachability to the host the agent called.",
        )
    if kind == "tls":
        label = "Secure connection to provider failed" if known else "Secure connection to upstream service failed"
        return (
            label,
            phrase or "TLS handshake failed",
            "remediation",
            "Check the TLS setup. The secure connection did not complete.",
        )
    if kind == "timeout":
        label = "Provider request timed out" if known else "Upstream request timed out"
        return (
            label,
            phrase or "Request timed out",
            "remediation",
            "The request timed out before a response was stored. Check the client timeout and run again under shield().",
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
    """Add human outcome fields. Leaves opticsStatus, applicationStatus, and status in place.

    An integer HTTP status is the final response for this attempt. It is not
    replaced by a transport error nested on the same exception.
    """
    identity = resolve_provider(str(rec.get("hostname") or ""), rec.get("port") if rec.get("port") is not None else None)
    known = identity is not None
    status = rec.get("status")
    if isinstance(status, int) and not isinstance(status, bool):
        label = http_outcome_label(status)
        response = http_response_text(status)
        category, action = next_action_for_status(status)
    else:
        kind = rec.get("failure_kind")
        if kind in ("dns", "connection", "tls", "timeout", "network", "wrapped"):
            phrase = str(rec.pop("failure_response", "") or "")
            if kind == "wrapped":
                phrase = str(rec.get("error_class") or phrase or "Exception")
            label, response, category, action = _failure_lines(str(kind), phrase, known)
        else:
            rec.pop("failure_response", None)
            label, response, category, action = _unavailable_outcome()
    rec["applicationOutcomeLabel"] = label
    rec["applicationLabel"] = label
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
