# PKG-01 fail-open

Audience: INTERNAL_RESTRICTED

`validateEvidence` and `validateBytes` catch their own failures and return a result. They do not throw into the caller. The caller-supplied `applicationResult` is returned as a detached plain copy when validation omits a secret, drops an event, hits the injected fault seam, receives malformed UTF-8, or receives a string longer than the input bound. The copy is not the caller's object. Mutating the input after validation does not change the result, and mutating the result does not change the input.

The injected fault is `options.injectFault === true`. It exists so tests can force the internal path. The result reason is `VALIDATOR_FAULT`, the issue location is `OPTICS`, and the exception text is not copied into the result.

Malformed UTF-8 bytes return `MALFORMED_UTF8` without a decoded secret. A string above `max_input_chars` returns `INPUT_BOUND` without scanning or copying the string into the result.

Cycles and nesting at the depth bound return `CYCLE_REJECTED` and `EXCESSIVE_NESTING`. An accessor property or proxy is rejected as `ACCESSOR_PROPERTY_FORBIDDEN` before the getter runs. A plain class instance is `REJECT_RECORD` / `UNSUPPORTED_COMPLEX_VALUE`. A function or other callable is `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE`. A getter that never returns is not given an in-process timeout. That case is executed only in a killable subprocess. The getter message is not stored.

These tests cover the private validator only. They do not claim that the frozen CLI or Python runtime fail open, and they do not execute those writers.
