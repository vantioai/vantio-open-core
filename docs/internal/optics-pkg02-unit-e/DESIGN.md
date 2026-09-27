# PKG-02 Unit E design

Audience: INTERNAL_RESTRICTED

## Order

1. A sealed `3.1.0` `shield()` runs with the Unit C adapter imported and unused. The run file bytes are compared before and after `adapt_copy`.
2. A call with no optics token, and a call whose `opticsStatus` is `SUCCESS` (the token `packages/vantio-agent-sdk-py/tests/test_optics_status.py` still expects), both read as `UNAVAILABLE` on the adapter copy.
3. The future package then writes canonical records from its own `shield()`.

## Writer

`shield()` installs three hooks and one asyncio client while the context is active:

- `urllib.request.urlopen`
- `socket.create_connection` for a failed in-scope connect
- `subprocess.run` for `curl`, `wget`, `httpie`, and `aria2c`
- `async_http_get`, an HTTP/1.0 GET on `asyncio.open_connection`

Each record is appended after the call finishes. The contract validates the event. A prohibited name drops the event. `optics_status` `SUCCESS` and a missing optics token are stored as `UNAVAILABLE`. A seen call is sent as `OBSERVED`.

The file is a bundle. `schema_version` is `0`. `runtime` is `python`. `producer` is `python_observe`. `compatibility.legacy_schema_version` is `2`. `unicode_profile_id` is `PKG01-UCD-16.0.0`, copied from the contract diagnostic. Host `unicodedata` is not the oracle.

## Empty shield

Empty `shield()` writes a file. Bundle `optics_status` is `NOT_OBSERVED`. `events` is empty. Envelope `call_count` is `0`. `duration_ms` is present when the shield interval was measured and absent when it was not. The file is not an `optics_status` of `SUCCESS`. Sealed `3.1.0` still writes no file for an empty shield.

## Rollback

`set_writer_mode("legacy")` or `VANTIO_PKG02_PYTHON_WRITER=legacy` makes the next `shield()` write the previous shape: `vantio_run_log` `"1"`, `schema_version` `2`, `workflow` `sight_loop`, `opticsStatus` `SUCCESS`, and `+00:00` timestamps. The stored call path is the URL path with the query removed, the same path sealed `3.1.0` stores. The file includes `summary` with the same fields sealed `3.1.0` writes for that call. An empty shield in that mode writes no file, which is the previous empty behavior. An existing canonical file is not replaced. `read_rolled_back` reports `UNSUPPORTED`, shows `schema_status`, and leaves the bytes in place.

A validator exception is caught inside the writer. The wrapped function's return value is unchanged, and no success file is written.
