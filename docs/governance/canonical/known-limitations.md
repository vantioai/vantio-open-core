# Known limitations

A call that never hits the interceptor is not recorded.

Browser paths stay outside this wrap.

Without vantio-agent-sdk, prefixing vantio run python does not intercept.

`vantio run` injects the Node interceptor only for `node`, `npx`, `tsx`, and `ts-node`.

Optics does not block actions or retain prompts or completions.

JSON records use schema_status unstable-pre-1.0.

There is no OTLP exporter.

http.client and pycurl do not store an HTTP status on the success path. That outcome stays unavailable.

Free Optics needs no account and no API key.
