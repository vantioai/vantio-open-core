# @vantio/w3-otlp-enable-test-disable

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Wave 3 Track 10. This package proves one enable, test, and disable cycle for the default-disabled WS7 I3 traces adapter.

`runEnableTestDisable()` reads the disabled rest state, sends in-process export attempts, and finishes on that same disabled rest state. The proof transport does not open a socket. `public_shipped_support` stays false. Founder decision 12 stays unresolved. Mapping `i3_status` stays `NOT_AUTHORIZED`.

Run from the repository root:

```sh
node --test tests/w3-otlp-enable-test-disable/*.test.cjs
```
