# PKG-02 Unit E ordinary-client proof

Audience: INTERNAL_RESTRICTED

Command:

```sh
python3 -m unittest discover -s tests/optics-pkg02-unit-e -v
```

Claimed CPython: 3.12.

| Proof | Test |
| --- | --- |
| urllib HTTP 4xx, missing size omitted | `test_urllib_http_4xx_omits_missing_size` |
| asyncio HTTP client, record after completion | `test_asyncio_client_records_after_completion` |
| socket failure, `failure_kind` `connection` | `test_socket_failure_keeps_failure_kind` |
| empty `shield()` is `NOT_OBSERVED` | `test_empty_shield_is_not_observed` |
| subprocess size, body text absent | `test_subprocess_size_omits_body_and_response_bytes` |
| 3.1.0 file byte-identical with the adapter unused | `test_adapter_present_and_unused_keeps_3_1_0_bytes` |
| rollback and fail-open return value | `test_04_rollback.py` |

The producer run reported 21 tests and 0 failures on CPython 3.12.3.
