# Stage 2 — Python SDK 3.1.0 design and code

CLI 0.3.24 stays frozen. This note tracks the Python 3.1.0 design-and-code pass. It is not a release seal and it does not authorize a PyPI upload.

## Fixed in tree: `ok` on HTTP error status

`packages/vantio-agent-sdk-py/vantio/_http_observe.py` now stores `ok` from the HTTP status:

- 200–399 → `ok` true, `applicationStatus` `SUCCESS`
- 400–599 → `ok` false, `applicationStatus` `APPLICATION_ERROR`
- DNS, connection, or TLS failure with no HTTP status → `ok` false, `applicationStatus` `UNAVAILABLE`, `error` `network_error`
- a wrapped application exception with no HTTP status → `ok` false, `applicationStatus` `UNAVAILABLE`, exception class name only, not `network_error`

Covered clients: urllib (`urlopen` and `OpenerDirector.open`), requests, httpx sync and async, aiohttp, and urllib3. urllib HTTP errors used to be stored as `network_error` because `urlopen` raises `HTTPError`. Those responses are application outcomes now.

Each recorded call stores `opticsStatus` / `applicationStatus` and the customer lines Optics status, observed outcome (`applicationOutcomeLabel`), and provider response. `APPLICATION_ERROR` stays the machine category. The run log names those headings in `status_labels` and sets `schema_status` to `unstable-pre-1.0`. Mixed machine outcomes in one run are `PARTIAL`. The summary line for that run is `Partial`.

A hostname in the supported provider catalog is named. Any other host uses Upstream response. CLI customer-line refinement is deferred in `docs/internal/optics-cli-post-0324-cx-backlog.md`. `@vantio/cli@0.3.24` is not reopened.

`socket.connect`, `connect_ex`, `create_connection`, and a distinct `SSLSocket.connect` store `duration_ms` measured around the real connect. A connect that has not returned is not recorded as a success.

## Already true, kept

- Telemetry sends only when `VANTIO_TELEMETRY=1`.
- `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` both force telemetry off, including when opt-in is set.
- Package-local MIT `LICENSE`. No root `LICENSE` added.
- `fetch_policy` and `report_anomaly` stay labeled as separately provisioned Phantom Engine / Enterprise APIs.
- Customer README has no trial, Stripe, login, or dashboard onboarding.

## Left without an invented HTTP status

`http.client.request` and `pycurl.perform` still do not see a response status on the success path, so this pass does not invent one. `applicationStatus` there is `UNAVAILABLE`, and the observed-outcome line is `Provider outcome unavailable` with provider response `No HTTP response`. Their exception path uses the same HTTP-versus-network split, so an HTTP-status exception is not labeled `network_error`.

## Not done

- No release-candidate seal for Founder promotion.
- No Twine, PyPI, or TestPyPI upload, and no credential use.
- No CLI source change. `@vantio/cli@0.3.24` stays frozen. The deferred `run --json` / `discover --json` schema backlog is not fixed here.
- Python 3.0.15 is not the ship target and is not published from this pass.
- No ordinary-client install from public PyPI. That waits on a later Force after publication.

## Verification (local, 2026-09-26)

`python -m unittest discover -s tests -t .` from `packages/vantio-agent-sdk-py`, with requests, httpx, aiohttp, urllib3, and build installed:

| Interpreter | Result |
|---|---|
| CPython 3.10.21 | 107 tests, 0 failures, 2 skipped (pycurl is not installed; the success-path gap test skips with it) |
| CPython 3.11.16 | 107 tests, 0 failures, 2 skipped (pycurl is not installed; the success-path gap test skips with it) |
| CPython 3.12.3 | 107 tests, 0 failures, 2 skipped (pycurl is not installed; the success-path gap test skips with it) |

Socket timing (`tests/test_socket_timing.py`) passed on all three. `connect`, `connect_ex`, `create_connection`, a refused connect, and the SSL entry this interpreter installs each store `duration_ms` around the real call (a 250 ms delay inside the original connect is included).

`tests/test_wheel_sdist.py` passed on all three. Each run built a wheel and sdist in a temporary directory, compared `vantio/*.py` byte-for-byte, checked metadata version 3.1.0, and checked that both archives carry the package `LICENSE`. The temp directory was deleted. Those builds are not a sealed release candidate and were not uploaded.
