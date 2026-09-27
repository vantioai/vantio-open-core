# @vantio/optics-node-adapter

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

PKG-02 Unit B only. This package calls the private evidence-contract mapper on copies. It does not write run logs, sit on the `vantio run` exit path, or bump `@vantio/cli` 0.3.24.

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. The future writer version placeholder is `PKG02-FUTURE-CLI-UNASSIGNED`. That string is not a release.

Run the isolated tests from the repository root:

```sh
node --test tests/optics-node-adapter/*.test.cjs
```
