# Known limitations

A call that never hits the interceptor is not recorded.

Browser paths stay outside this wrap.

Without vantio-agent-sdk, prefixing vantio run python does not intercept.

`vantio run` injects the Node interceptor only for `node`, `npx`, `tsx`, and `ts-node`.

Optics does not block actions or retain prompts or completions.

JSON records use schema_status unstable-pre-1.0.

`vantio coverage` lists processes and connections recorded on this system. A process that was not started with vantio run is not in the coverage map.

`vantio destinations` flags the first recorded connection from a program to a destination that is not on the allowlist. It does not stop the call.

OTLP export is OTLP/HTTP JSON to a URL you set. Optics does not start a collector and does not speak OTLP/gRPC.

http.client and pycurl do not store an HTTP status on the success path. That outcome stays unavailable.

Free Optics needs no account and no API key.
