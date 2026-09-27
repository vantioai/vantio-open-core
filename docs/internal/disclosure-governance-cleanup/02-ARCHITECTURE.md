# Disclosure and governance cleanup — architecture

Audience: INTERNAL_RESTRICTED

Two residues are separate. The documentation gate can see a test file. GitHub can still serve a closed pull request. This force accounts for both without moving customer-manual bytes onto public `main`.

## Collision-test inventory

`docs/governance/STALE-NAMES.json` lists retired public names. `docs/scripts/docs-release-lib.mjs` counts them outside `docs/governance/` and `docs/scripts/`. `docs/governance/LEGACY-STALE-NAMES.json` `hits` is the frozen debt. A new path fails `legacy-stale-name-inventory-frozen`.

The collision test is new debt because it contains the prohibition needles. The reviewed disposition is `FROZEN_DEBT`:

- `reviewed_updates` names the path, the count, and the reason.
- `hits` carries the same path and count.
- `intentional_leftovers` does not name the path. That list is for the Optics manual's declared leftover storage, not for a test that is supposed to forbid the strings.
- `legacy_scan.exclude_prefixes` does not hide the path. An exclude would make the scan report the file missing after it had been added, or would omit it before review. Either result hides the path.

`collisionTestInventoryProblems` is check `collision-test-inventory-reviewed`. It fails when the review entry is missing, the disposition is not `FROZEN_DEBT`, the counts disagree, the path is an intentional leftover, an exclude prefix hides it, or the live scan does not see it. A different new file that contains a retired name still fails the frozen-inventory check. This review does not except that other file.

## Public draft residue

Pull request #66 is closed and unmerged. The branch ref is gone. `refs/pull/66/head` still points at `60726bef7a7d7da35525a4d832ec63b5f8ca5bad`. GitHub documents that pull refs are read-only from a client push, and that cached pull-request views are removed by contacting GitHub Support after other refs are gone.

This force does not rewrite `main`. The eight commits diverge from `main` at merge base `14249ba84ff1f3d5aa8ad7a7366172f29235c76e`. A mirror history rewrite would touch refs that do not contain the manual. The purge packet asks a later authorized person to request removal of this pull request's cache and the eight objects only. It also records GitHub's limit: Support does not remove data it judges non-sensitive, and it prefers credential rotation when that mitigates the risk. This residue is document text, not a credential. Support may decline. The packet does not claim a purge.

The private repository already holds the manual. Sixteen private blobs match the public tip. Two private blobs match the reviewed wording-fix hashes. The hash table in `DISCLOSURE-RECORD.json` is the public preservation of those identities. The manual text stays in the private repository.

## Council

`INDEPENDENT-COUNCIL.md` is the slot. This producer does not fill a pass.
