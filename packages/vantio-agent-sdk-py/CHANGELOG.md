# Changelog

## 3.1.0

- HTTP 400–599 is stored with `ok` false for urllib, requests, httpx, aiohttp, and urllib3. urllib HTTP errors are application outcomes and are not labeled `network_error`.
- Recorded calls and the run summary separate `opticsStatus` (Optics status) from `applicationStatus` (Application outcome).
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

- Corrects public package metadata to reflect the current Optics, Phantom Engine, and Vantio Enterprise product model.
- Removes stale Gate project metadata from the published package (project URL and long description as served by PyPI).
- Does not reintroduce Gate as a current standalone SKU.
- Does not claim external proof or customer validation.

## 3.0.13

Packaging metadata only. PyPI long description and project URLs now match vantio.ai Present packaging: Optics Observe (Free), Phantom Engine ($799/node/mo — Observe, Enforce, and Control in one purchase), Enterprise (talk to sales). Continuous Assurance named as the platform trust loop, not a fifth product. No SDK behavior change.

> **Historical note:** this release originally listed Gate as a separate $499/month SKU. Gate is the
> internal name for the Enforce function set inside Phantom Engine; it is not a current standalone
> public product.
