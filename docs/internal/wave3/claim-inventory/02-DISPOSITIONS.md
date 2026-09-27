# Dispositions

Audience: INTERNAL_RESTRICTED

Every claim has `executes_now: false`. A disposition is a recommendation for council. It does not edit a surface.

| Disposition | Meaning on this ledger |
| --- | --- |
| `KEEP` | Leave the public sentence. This is not permission to republish it. |
| `REWRITE` | A later copy change is recommended. Used for the Optics manual version sentence and for the documented API host that did not resolve. Neither file was edited. |
| `HOLD` | Do not change the surface. Used when the evidence is thin, or when the change would reopen a frozen version, yank a release, or add a file. |
| `RETIRE` | In the enum, so a later removal can be named. No claim uses it as the executing recommendation. Where the later action would be a yank, the recommendation is `HOLD` and `later_action_not_authorized` is `RETIRE`. |
| `EXTERNAL_ACCOUNT_ACTION_REQUIRED` | The only edit path is an account this repository does not change: the website, the GitHub org description, LinkedIn, X, or another public repository. Logging in is not authorized. |
| `DEFER_TO_T16` | The sentence needs canonical public language. Track 16 was not written. |

`later_action_not_authorized` records a content direction that this freeze refuses to perform. It does not override `executes_now`.

Track 14 dispositions stay `UNREVIEWED` because writing them would look like an approved rewrite. The claim ledger is the disposition record.
