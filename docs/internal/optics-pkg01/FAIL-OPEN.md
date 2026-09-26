# PKG-01 fail-open

Audience: INTERNAL_RESTRICTED

`validateEvidence` and `validateBytes` catch their own failures and return a result. They do not throw into the caller. The caller-supplied `applicationResult` is returned as the same reference when validation omits a secret, drops an event, hits the injected fault seam, receives malformed UTF-8, or receives a string longer than the input bound.

The injected fault is `options.injectFault === true`. It exists so tests can force the internal path. The result reason is `VALIDATOR_FAULT`, the issue location is `OPTICS`, and the exception text is not copied into the result.

Malformed UTF-8 bytes return `MALFORMED_UTF8` without a decoded secret. A string above `max_input_chars` returns `INPUT_BOUND` without scanning or copying the string into the result.

Cycles, enumerable throwing getters, and nesting at the depth bound return `CYCLE_REJECTED`, `HOSTILE_INPUT`, and `EXCESSIVE_NESTING`. The getter message is not stored.

These tests cover the private validator only. They do not claim that the frozen CLI or Python runtime fail open, and they do not execute those writers.
