# @vantio/optics-reader-compat-gates

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

PKG-02 reader compatibility entry gates. This package scores a directory of records with the inert Unit F reader. It does not write those records, sit inside `@vantio/cli` 0.3.24, or authorize Unit D or Unit E.

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. The package version is `0.0.0-unstable-pre-1.0`.

Run the isolated tests from the repository root:

```sh
node --test tests/optics-pkg02-reader-compat-gates/*.test.cjs
```
