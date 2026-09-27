# PKG-02 reader compatibility entry gates — design

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

`evaluateEntryGates` scores one directory. The caller names each file's role and passes the frozen `displayCall` result for the future record. The evaluator returns a JSON report. It does not write the directory.

## Steps

1. Refuse a request that is missing the directory, the absent-file name, or the exact role set.
2. Refuse a symlink directory. Resolve each file name inside the directory. Refuse a symlink file and a name that escapes the directory.
3. Read each file, call `readRunFile`, and read it again. Record whether the bytes match.
4. Call `readRunFile` on the absent name. That path must stay missing, with reason `ABSENT_FILE` and health `UNAVAILABLE`.
5. Call `readRunFile` on the claimed-local file with `promote` set. The bytes and the reader origin must stay unpromoted.
6. Call `readRunFile` on the future file with `write`, `activate`, `migrate`, and `path` set. The reader returns `WRITER_INACTIVE` and the bytes stay.
7. Score the eleven gates. Any byte change fails every gate.

The report lists safe markers: role, byte length, schema version, schema status, origin labels, classified optics tokens, and reader health. It does not copy raw file text, absolute paths, unknown optics tokens, or prohibited values.

## Frozen CLI oracle

The package does not import `optics-cx.cjs`. The test calls `displayCall` and passes the object in. The future gate passes only when that object's `opticsStatus` is `SUCCESS` and the future file's stored optics token is `OBSERVED`. The recorded disposition is `UNSUPPORTED`.

## Placeholders

`PKG02-FUTURE-CLI-UNASSIGNED` appears as the producer version on the future fixture so the existing contract can recognize provenance. It is not a published version. The report's `activates_unit_d` and `activates_unit_e` fields stay false.
