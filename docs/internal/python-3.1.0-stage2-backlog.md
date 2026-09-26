# Stage 2 backlog — Python SDK 3.1.0

CLI 0.3.24 does not change Python runtime behavior. This note is the handoff for the later 3.1.0 design-and-code pass. Do not publish, seal, or build a Python release from this note.

## Bug to fix: `ok=True` on HTTP error status

In `packages/vantio-agent-sdk-py/vantio/_http_observe.py`, these observe paths set `ok=True` whenever the client returns a response object, including when the HTTP status is 4xx or 5xx:

- `requests` (`_observe_send`) stores `status=resp.status_code` and `ok=True`
- `httpx` sync and async send paths store `status=resp.status_code` and `ok=True`
- `aiohttp` stores `status=resp.status` and `ok=True`
- `urllib3` (`_observe_urllib3_urlopen`) stores `status=resp.status` and `ok=True`

`urllib.request.urlopen` is a related recording bug: HTTP errors raise, and the `except` path stores `status` from the exception code with `error="network_error"` and `action="OBSERVED"`.

CLI 0.3.24 display derives `applicationStatus` from the raw HTTP `status` field and does not trust `ok`. Python 3.1.0 should store an `ok` value that matches that HTTP status, and should stop labeling HTTP error responses as `network_error`.

No Python product source was changed for this CLI release.
