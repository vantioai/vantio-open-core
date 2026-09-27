# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `OPTICS_O7_STORE_BLOCKED_NODE_BINDING_UNSELECTED_READY_FOR_COUNCIL`

Producer: Cursor cloud agent `bc-4b9b153e-e636-58b6-a894-7de8dd2cd819`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-4b9b153e-e636-58b6-a894-7de8dd2cd819

This file is the producer stub. The store producer does not sit the council and does not write a verdict.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Packet | `docs/planning/optics-o7-store/` |
| Package | `@vantio/optics-operational-store` `0.0.0-unstable-pre-1.0` |
| Tests | `tests/optics-o7-store/` |
| Base | `6d409eb73b8875b1c525348a92e9db42a74291b9` |
| Engine | Embedded SQLite, WAL, application-owned schema, cited from decision-pack section 12 and A2 section 4 |
| Python mechanism | Standard-library `sqlite3`, the mechanism A2 already names |
| Node binding | `UNSELECTED` |
| Classification the producer claims | `OPTICS_O7_STORE_BLOCKED_NODE_BINDING_UNSELECTED_READY_FOR_COUNCIL` |
| Evidence tier | `UNSET` |
| Default write path | Off |
| `PACKAGES.json` `O7` cell | Left `NOT_AUTHORIZED` |
| Gate 8 | Left closed |

## 2. Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Python file, WAL, `user_version` 1, row schema version, `privacy_generation` 1 | `UNSAT` |
| 2 | Symlink refusal, mode `0600`, corrupt-file preservation, recovery envelope | `UNSAT` |
| 3 | Caller SQL rejected, allowlist before insert, no legacy copy | `UNSAT` |
| 4 | Node binding still unselected and Node creates no file | `UNSAT` |
| 5 | Unmet `O1`, `O2`, `O6`, `O11`, and `O12` are not marked accepted | `UNSAT` |
| 6 | Frozen CLI `0.3.24`, closed Gate 8, no customer migration, evidence tier `UNSET` | `UNSAT` |

## 3. Checks the council can re-run

From the repository root:

```sh
python3 tests/optics-o7-store/direct_test.py
python3 tests/optics-o7-store/adversarial_test.py
node --test tests/optics-o7-store/*.test.cjs
node --test tests/optics-option-c-revalidation/*.test.cjs
```

Also:

- Node sources under `packages/optics-operational-store/` do not require `sqlite3`, `better-sqlite3`, or `node:sqlite`.
- `@vantio/cli` is `0.3.24`.
- `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` still says Gate 8 is closed.
- No tracked file name ends in `.sqlite`.
- The producer classification is the blocked token above, not `OPTICS_O7_STORE_READY_FOR_COUNCIL`.

## 4. Notes for the council

A pass of this packet would accept the Python store and the Node refusal as the current implementation. It would not select a Node binding, would not open Gate 8, and would not assign an evidence tier.

A council that finds a Node SQLite import, a customer migration, a CLI version other than `0.3.24`, or a claim of `INTEGRATION_PROVED` should refuse the packet.
