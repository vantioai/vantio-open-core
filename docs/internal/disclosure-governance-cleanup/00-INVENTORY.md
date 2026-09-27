# Disclosure and governance cleanup — inventory

Audience: INTERNAL_RESTRICTED

Base: `89f95099d0dce463307eb75d78e7fcf2ef99feb2` (`Merge pull request #83`).

This inventory records what was true before the fix. It does not copy a customer manual into this tree.

## Documentation governance

`node docs/scripts/check-docs-release.mjs` on the base failed one check:

`legacy-stale-name-inventory-frozen`: `new stale-name files: tests/shared-health-vocabulary/collision.test.cjs`

The legacy scan extensions include `.cjs`. `docs/governance/MANIFEST.json` does not exclude `tests/shared-health-vocabulary/`. The frozen `hits` list in `docs/governance/LEGACY-STALE-NAMES.json` did not name that test. The live match count on the base was 2. No other path was new, missing, or changed.

The collision test still asserts that the shared-health catalog directory does not contain the retired public strings, and that it does not contain a live probe command. Those strings are why the file is in the scan. Removing the strings, or excluding the path, would hide the debt instead of reviewing it.

## Public Phantom Engine draft

| Fact | Observation |
| --- | --- |
| Pull request | https://github.com/vantioai/vantio-open-core/pull/66 |
| State | `closed`, draft, `merged` false, `merged_at` null |
| Closed at | `2026-09-27T07:33:14Z` |
| Head ref name | `docs/phantom-engine-customer-manual-v1` |
| Head SHA | `60726bef7a7d7da35525a4d832ec63b5f8ca5bad` |
| Branch on origin | absent (`git ls-remote` of that head returned no ref) |
| Remaining advertised ref | `refs/pull/66/head` at the same SHA |
| Other advertised refs at the eight draft commits | none |
| Forks | 0 |
| Compare with this main | `diverged`, 8 commits ahead, merge base `14249ba84ff1f3d5aa8ad7a7366172f29235c76e` |
| Customer manual on this worktree | absent |

The eight public commits are `8baead08d12192799ad51bae6f411cd394c444e4` through `60726bef7a7d7da35525a4d832ec63b5f8ca5bad`. They are not ancestors of this main. Closing the pull request did not delete the pull ref or the commit objects.

## Private channel

| Fact | Observation |
| --- | --- |
| Repository | `vantioai/vantio-pe-customer-docs` |
| Visibility | private |
| Anonymous HTML and API | 404 |
| Forking | disabled |
| Main tip | `d876ced0531607b7468efa3d0da981821be2cbbc` |
| Tip change | `INTERNAL-RELOCATION.md` only (blob `d94b631f91b402e3c17f455cd0280cb0b0aaafea`) |
| Wording-fix commit | `ec633d192544c22cde2853226b3f8e77d753a49f` |
| Manual path | `docs/customer/phantom-engine/` |
| Placement status | `PHANTOM_CUSTOMER_DOCS_PRIVATE_CHANNEL_PLACED` |

Contents-listing blob SHAs on the private default branch match the reviewed public-tip blobs for 16 manual files. `CUSTOMER-OVERVIEW.md` and `EVIDENCE-AND-ASSURANCE.md` match the reviewed post-edit blobs `3d4de013f6da9db6418a02cedf6c5009d1b95356` and `3c68008c6702f8daf082c1315aaa2f0072ca9109`. Public-tip SHA-256 values were recomputed from the still-cached public blobs and match the private relocation record. Manual bytes were not written into this worktree. Post-edit SHA-256 was not recomputed here; the private git blob is the checked identity for those two files.

## Support purge

No GitHub Support ticket exists from this force. The cached pull request diff, the pull ref, and the eight commits are still the public residue.
