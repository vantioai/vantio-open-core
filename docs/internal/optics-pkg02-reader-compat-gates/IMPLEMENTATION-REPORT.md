# PKG-02 reader compatibility entry gates — implementation report

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification before council: `OPTICS_PKG02_READER_COMPAT_GATES_READY_FOR_COUNCIL`

This classification means the gate packet is ready for a separate council agent. It is not a council verdict, not a merge, and not authorization for Unit D or Unit E.

The producer did not sit the council. Units D and E stay `NOT_AUTHORIZED`.

Starting commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`.

## What landed

Private package `@vantio/optics-reader-compat-gates` at `0.0.0-unstable-pre-1.0`. The evaluator calls the merged Unit F reader. It is not a bump of CLI `0.3.24`, Node SDK `0.2.4`, Python `3.1.0`, the evidence contract, the vocabulary package, the node adapter, or the Unit F reader.

The package is not in `pnpm-workspace.yaml`. Live CLI and SDK sources do not import it.

## Checks

From the repository root:

```sh
node --test tests/optics-pkg02-reader-compat-gates/*.test.cjs
```

The producer run of that command reported 15 tests and 0 failures. The direct test built a real CLI `0.3.24` run file and a real Python `3.1.0` `shield()` file in temporary homes, placed those bytes beside a future canonical record, and all eleven gates passed. Adversarial tests covered a forged frozen display, a missing role, a symlink, a path escape, promote and writer options, unknown tokens, canary suppression, and a non-directory path.

A failed gate keeps the report classification at `OPTICS_PKG02_READER_COMPAT_GATES_BLOCKED`. The ready token in this file is the packet classification for the passing suite. It is not a council verdict.

## Hard-stop attestations

- No CLI `0.3.24`, Node SDK `0.2.4`, or Python `3.1.0` source change, and no version bump.
- No Unit D package and no Unit E package.
- No live writer and no write-back. Gate reads re-check file bytes.
- No SQLite, migration, UI, daemon, exporter, or alerting.
- No stable schema.
- No release candidate, seal, publish, tag, or announcement.
- Draft pull request only. Not marked ready. Not merged.
- Council is a separate agent. This producer did not run it.
