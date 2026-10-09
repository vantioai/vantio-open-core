# Changelog

## 3.1.1

CANDIDATE_ONLY_NOT_FOR_PUBLICATION. This heading is source. It is not a PyPI release.

Candidate behavior, not a registry release. The sealed publisher stays on 3.1.0.

- New run logs omit the leftover workflow field and set `producer` to `python_observe`. `runtime` stays `python`. Files already on disk are not rewritten.
- Optics remains observational. This package does not block, redact, or cap a call.

## 3.1.0

- HTTP 400–599 is stored with `ok` false for urllib, requests, httpx, aiohttp, and urllib3. urllib HTTP errors are application outcomes and are not labeled `network_error`.
- Recorded calls and the run summary separate `opticsStatus` (Optics status) from `applicationStatus` (machine token). The customer lines are Optics status, observed outcome (`applicationOutcomeLabel`), and provider response. `APPLICATION_ERROR` stays the machine category. `schema_status` on the run log is `unstable-pre-1.0`.
- DNS, connection, TLS, and timeout errors are classified from a bounded exception chain (`__cause__`, `__context__`, exception `.reason`, and exception `args`) for urllib, requests, httpx, aiohttp, and urllib3. A final HTTP status wins over a nested transport error on that same attempt. urllib3's own retry re-enters that attempt and is stored as the final response. The chain limits are an internal safety cap, not a compatibility promise. Unknown hosts use Upstream wording on those transport lines.
- `socket.connect`, `connect_ex`, `create_connection`, and a distinct `SSLSocket.connect` store `duration_ms` measured around the real connect.
- Telemetry stays off unless `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` still override that opt-in.
- Phantom Engine and Enterprise APIs remain separately provisioned. The package-local MIT license is unchanged.
- `vantio.__version__` is 3.1.0.

## 3.0.15

Documentation correction for anonymous telemetry. The payload schema and send behavior are unchanged.

- Telemetry stays off unless `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` still override that opt-in.
- The automatic once-per-process run ping is sent when `shield()` starts, before HTTP observations are recorded, so `callCount` on that ping is 0 and `hosts` is empty.
- Free Optics still needs no account and no API key. Control-plane variables stay labeled as Phantom Engine / Enterprise.
- `vantio.__version__` matches the package version, 3.0.15.

## 3.0.14

Packaging metadata correction only. No SDK behavior change.

- Corrects public package metadata to the Optics, Phantom Engine, and Enterprise names.
- Removes a retired standalone product name and its retired price from the project URL and the long description.
- Does not add a fourth public product.
- Does not claim external proof or customer validation.

## 3.0.13

Packaging metadata only. PyPI long description and project URLs matched the public ladder then in effect. Continuous Assurance is named as the platform trust loop, not a fifth product. No SDK behavior change.

> **Historical note:** an older note for this release used a retired product name and a retired
> price. Those words are not current. Phantom Engine is the enforcement product. Optics observes.
