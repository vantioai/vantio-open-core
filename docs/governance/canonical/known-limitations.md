# Known limitations

A call that never hits the interceptor is not recorded.

Browser paths stay outside this wrap.

Without vantio-agent-sdk, prefixing vantio run python does not intercept.

`vantio run` injects the Node interceptor only for `node`, `npx`, `tsx`, and `ts-node`.

On Linux, `vantio run` still writes a run file for every command. That file records the process tree and the outbound sockets sampled from the local process table. A socket that opens and closes between samples is not in the file. Commands other than Node and Python print a New destination line while they run when a sampled socket is new. Node and Python print that line from the interceptor when a supported call is recorded.

Optics does not block actions or retain prompts or completions.

JSON records use schema_status unstable-pre-1.0.

`vantio coverage` lists processes and connections recorded on this system. A process outside the wrap is marked not covered when the local process table shows it.

`vantio destinations` flags the first recorded connection from a program to a destination that is not on the allowlist. It does not stop the call.

OTLP/HTTP JSON and OTLP/gRPC export the same fields to a URL you set. OTLP/gRPC is a unary HTTP/2 export of the same fields. Optics does not start a collector.

http.client and pycurl do not store an HTTP status on the success path. That outcome stays unavailable.

Free Optics needs no account and no API key.
