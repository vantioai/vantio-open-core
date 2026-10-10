# Python guide

Two Python versions matter. Only one is on PyPI.

| | Published install | This git tree |
| --- | --- | --- |
| Package | `vantio-agent-sdk` | `vantio-agent-sdk` |
| Version | **3.0.14** | **3.1.0 unpublished** |
| `pip install vantio-agent-sdk` | Installs this | Does not install this |
| Telemetry gate | `shield()` sends unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` | Off unless `VANTIO_TELEMETRY=1` |
| HTTP 4xx/5xx `ok` | urllib `urlopen` in a local 3.0.14 check stored `ok` false and `error` `network_error` with the status still set. The return path in that source can store `ok` true. CLI display ignores `ok` | Source stores `ok` false for 400–599 and does not label an HTTP status as `network_error` |
| Customer outcome lines on the file | Absent | Present in source (`opticsStatus`, `applicationOutcomeLabel`, and related fields) |
| `schema_status` on the run file | Absent | `unstable-pre-1.0` in source |

CLI 0.3.24 is the reader for both. Its display rules are in [STATUS-AND-OUTCOMES.md](STATUS-AND-OUTCOMES.md). Those rules already derive Optics status and application outcome when you `tail`, `search`, or `prove`. They do not require the unpublished file fields.

## Install the published SDK

```bash
# Example status: illustrative
pip install 'vantio-agent-sdk==3.0.14'
```

Requires Python 3.10 or newer. Core observe uses the standard library. `requests`, `httpx`, `aiohttp`, `urllib3`, and `pycurl` are observed when they are already installed. They are not required dependencies.

## `vantio run python`

```bash
# Example status: illustrative
vantio run python agent.py
vantio run python3 agent.py
```

The CLI treats `python`, `python3`, `py`, and `python3.N` as Python. It puts `bin/python-wrap` on `PYTHONPATH` so `sitecustomize` can load the SDK. If the SDK is missing, the process prints a warning and continues without interception.

`sitecustomize` prefers `install_process_wrap`, which calls `install(trace_id)` and writes the log on interpreter exit. That path does not call the telemetry ping. `shield()` does. See [TELEMETRY.md](TELEMETRY.md).

Prefixing `vantio run python` without the SDK does not intercept.

## `shield()` on 3.0.14

```python
# Example status: illustrative
from vantio import shield

@shield
async def run_agent():
    return await call_provider()

async with shield() as ctx:
    print(ctx.trace_id)
```

`get_current_trace_id()` returns the active id inside `shield()`, and `None` outside it.

On 3.0.14, entering `shield()` sends the usage ping unless you set `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. Set one of those when you need the published SDK to stay silent.

While `shield()` or the process wrap is active, 3.0.14 observes in-scope calls made through:

- `urllib.request.urlopen` and custom opener `open`
- `requests`, `httpx` (sync and async), `aiohttp`, when installed
- `urllib3`, when installed
- `pycurl`, when installed
- `http.client`
- `socket.connect`, `connect_ex`, and `create_connection`
- subprocess `curl`, `wget`, `httpie`, and `aria2c`

Browsers stay outside. A client you did not patch, or a host outside the catalog and outside `VANTIO_EXTRA_LLM_HOSTS`, is not observed.

## What 3.0.14 writes

A run file is written only when there is at least one recorded call and a trace id. Zero calls leave no Python file.

The file is JSON with `vantio_run_log` `"1"`, `schema_version` 2, `plane` `"optics"`, `runtime` `"python"`, timestamps, `calls`, and a `summary` of `total_calls` and `hosts`. The summary `hosts` array is the hostnames stored on those calls. That file field is the run log, not the telemetry ping. The telemetry field of the same name is defined in [TELEMETRY.md](TELEMETRY.md).

Each call stores `hostname`, `provider`, `action`, `mediation`, and `ts`, plus extras the hook passed (`path`, `ok`, `duration_ms`, `error`, `error_class`, and similar). Published 3.0.14 sets `provider` to `"other"` unless a caller passed another value. No in-tree call site passes one, so published logs label `provider` as `other`. The hostname is still stored. Node's substring provider guess does not run on these files.

Published Python 3.0.14 also contains `"workflow": "sight_loop"`. That value is leftover storage from an older name. It is not the product name. Vantio Optics is the product name. The string does not turn a feature on. Source candidate 3.1.1 does not write that field. CLI Node files do not write `workflow`.

The file does not include `pid`, `ppid`, `free_mode`, `duration_ms` on the envelope, `by_host`, or `schema_status`.

`http.client` and `pycurl` success paths in this generation do not store an HTTP status. CLI display then shows application outcome `Unavailable`.

A local check of the published 3.0.14 wheel, using `urllib.request.urlopen` against HTTP 500, stored `status` 500, `ok` false, and `error` `network_error` (`error_class` `HTTPError`). urllib raises for that status, so this path is the exception path. The return path in the 3.0.14 source (a `requests` / `httpx` / `aiohttp` call that returns a response object) sets `ok` true together with the status code. That return path was read from the 3.0.14 sources and was not re-executed in this manual's command check. CLI display ignores `ok` and uses the HTTP status, so a stored 500 is application outcome `APPLICATION_ERROR` either way. The stored `error` string `network_error` on the urllib path is what 3.0.14 wrote. Unpublished 3.1.0 source stops labeling that HTTP status as `network_error`.

## Unpublished 3.1.0 source

Do not describe the following as what `pip install` does today.

In this repository's Python 3.1.0 source:

- HTTP 200–399 stores `ok` true. HTTP 400–599 stores `ok` false. A 4xx or 5xx is not labeled `network_error`. DNS, connection, TLS, and timeout failures use `network_error` and have no HTTP status. A wrapped application exception stores the exception class name, with no HTTP status, and is not labeled `network_error`.
- Classification walks `__cause__`, `__context__`, exception `.reason`, and exception `args`, with an internal depth cap. A final HTTP status on an attempt wins over a nested transport error.
- Recorded calls and the summary add `opticsStatus`, `applicationStatus`, and customer lines (`applicationOutcomeLabel`, `providerResponse`, and related keys). `schema_status` on the run file is `unstable-pre-1.0`. Mixed application outcomes in one run roll up to `PARTIAL`.
- `socket.connect`, `connect_ex`, `create_connection`, and a distinct `SSLSocket.connect` store `duration_ms` measured around the real connect.
- Catalog hostnames can replace provider `"other"`. Other hosts stay upstream wording in those customer lines.
- `http.client` and `pycurl` still do not store an HTTP status on the success path. Outcome stays `UNAVAILABLE` with the line `Provider outcome unavailable`.
- Telemetry matches the CLI opt-in rule.

Published `@vantio/cli@0.3.24` says "Application outcome" and "Application error". Source candidate 0.3.25 says "Observed outcome" and the specific sentence for that HTTP status. The machine token for HTTP 400–599 stays `APPLICATION_ERROR`.

## Upgrade from Python v2

v3.0.0 replaced the v2 API. `VantioSession` and `VANTIO_PROXY_ENDPOINT` are gone. There is no proxy hop.

```python
# v2 — removed
# from vantio.session import VantioSession
# with VantioSession(agent_name="my-agent") as session:
#     ...

# v3.0.14 published API
from vantio import shield

@shield
async def run_agent():
    ...
```

Run logs written by v3 use `schema_version` 2. The CLI does not migrate old files and does not refuse newer files. See [UPGRADE-ROLLBACK-UNINSTALL.md](UPGRADE-ROLLBACK-UNINSTALL.md).

## Names that are not free Optics

`fetch_policy`, `redact_pii`, and `report_anomaly` are exported by the package. They belong to a separately provisioned control plane. This manual does not document them. Free Optics does not require them, and Optics does not enforce policy.
