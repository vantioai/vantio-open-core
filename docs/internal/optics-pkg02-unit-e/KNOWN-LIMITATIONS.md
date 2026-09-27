# PKG-02 Unit E known limitations

Audience: INTERNAL_RESTRICTED

- Claimed CPython is 3.12 only. This run used CPython 3.12.3.
- The future observer covers `urllib.request.urlopen`, `socket.create_connection` failures, `subprocess.run` for curl/wget/httpie/aria2c, and `async_http_get`. `requests`, `httpx`, `aiohttp`, `urllib3`, `pycurl`, `http.client`, and `OpenerDirector.open` stay on the sealed 3.1.0 module. This line does not wrap them.
- A successful bare TCP connect is not a separate event. A refused in-scope `create_connection` is.
- `subprocess.Popen` without `subprocess.run` is not recorded.
- Enforcement actions are not emitted. This line observes.
- The bundle is the writer file. `optics_status` on a `run_envelope` is not a contract field, so the bundle root carries `NOT_OBSERVED` or `OBSERVED` and the envelope carries `call_count`.
- `read_rolled_back` is the Unit E rollback reader. The Unit F reader is unchanged.
- The planning matrix achievement stays `NOT_SHIPPED`. This unit's marker is `READY_FOR_COUNCIL`.
- Nothing here is merged, sealed, or published.
