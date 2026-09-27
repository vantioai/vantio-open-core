# Progressive enforcement boundary

PRIVATE | INERT | NOT SHIPPED | NO HOST ATTACHMENT | NO AUTO-ENFORCE | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer role: implementation producer. This agent does not sit the independent council and does not self-assign a council pass.

Producer identity: Cursor cloud agent `bc-58791138-d3dc-53a6-9bdb-78496fb18e51`, model Grok 4.7, reasoning `xhigh`, context `500k`, fast `false`.

Producer URL: https://cursor.com/agents/bc-58791138-d3dc-53a6-9bdb-78496fb18e51

Producer classification: `PE_PROGRESSIVE_ENFORCEMENT_READY_FOR_COUNCIL`

That classification means this package is ready for a separate council. It is not a council verdict, not a customer deploy, and not host enforcement.

## 1. Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Commit subject | Merge pull request #83 from `vantioai/cursor/pe-ws4-vocabulary-binding-f9f5` |
| Branch | `cursor/pe-progressive-enforcement-8e51` |
| Force | Founder Program Wave 2, Track 9, progressive enforcement |

## 2. What this force implements

A private in-process lifecycle with these stages, in this order:

`DISCOVER`, `OBSERVE`, `PROPOSE`, `SIMULATE`, `CANARY`, `ENFORCE`, `REVIEW`, `REVOKE_OR_ROLLBACK`, `RETIRE`, `VERIFY_REMOVAL`.

Observed behavior may create a proposal when the caller sets `propose` exactly to `true`. No observation path writes the active promotion set. `ENFORCE` is reached only by `promote` after proposal evidence, historical replay, shadow decisions, per-rule impact, a bounded canary, a distinct approver, and a known-good snapshot. The first armed rollout step is `COHORT`. Later steps move one at a time.

## 3. What `ENFORCE` means here

`decide` can return `PROMOTED_MATCH` for a subject inside the current rollout set. The same result sets `enforcement_attached` false, `applied_to_host` false, `live_enforcement` false, and `host_attachment` `NOT_PERFORMED`.

This package does not drop packets, redact bytes, or call the live interceptor. Optics remains observation. Phantom Engine on an enrolled host remains the product that attaches enforcement. Enterprise approval classes in `docs/planning/enterprise-governance/` stay planned. The distinct-actor check in this package is local and does not implement those classes.

## 4. What this force keeps closed

- Customer deploy, stranger-host execution, announcements, credentials, and money.
- CLI `@vantio/cli` `0.3.24`, Node SDK `@vantio/agent-sdk` `0.2.4`, and Python `vantio-agent-sdk` `3.1.0`.
- Copies of private Phantom Engine customer manuals or unread private blobs.
- Edits to `docs/governance/`, the pnpm workspace, and the live Gate or Optics MCP servers.
- A council pass. `05-COUNCIL-SLOT.md` stays `PENDING_INDEPENDENT_COUNCIL`.
- Merge of this pull request.

## 5. Vocabulary

Lifecycle decision classes are local to this package: `OBSERVATION`, `PROPOSAL`, `SHADOW`, `CANARY`, `PROMOTED_MATCH`, `FROZEN`, `EXCEPTION`, `ROLLED_BACK`, `RETIRED`, `REMOVED`, `REFUSED`.

`OBSERVATION` is not protection state `protected`. This force does not write `docs/governance/STATUS-TOKENS.json` and does not add these classes to the Workstream 4 catalog. Shadow decisions are in-process labels. They are not a product name.
