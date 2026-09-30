# PR split decision for optics audit remediation

Audience: review of pull request 143.

Status: one pull request. `split_done`: false.

Publication: `CANDIDATE_ONLY_NOT_FOR_PUBLICATION`.

## What was checked

Pull request 143 is two commits on `cursor/optics-audit-p1-security-f25c`, based on `dc3f96d5abd9ede2537e09329b20c2bb60dd3a2e`.

- `1bbed9021c9ceb494b34d1d3ab4d625d5e7c32f3` is the P1 security fix.
- `bab3107ce1478557c41818dc636d2d08ba3f8dd8` is the P2–P5 remediation, stacked on that P1 commit.

A clean split would put P1 on a review pull request and leave P2–P5 on 143, or move P2–P5 to a follow-on. That needs either a history rewrite of 143, which this work is not allowed to do, or a cherry-pick of the P2–P5 commit onto the pre-P1 base.

## Cherry-pick result

`git cherry-pick bab3107ce1478557c41818dc636d2d08ba3f8dd8` onto `dc3f96d5abd9ede2537e09329b20c2bb60dd3a2e` stopped with conflicts in:

- `.github/workflows/ci.yml`
- `deploy/docker/Dockerfile.observe`
- `deploy/docker/compose.observe.yml`
- `docs/planning/optics-audit-p1/04-INDEPENDENT-COUNCIL.md` (modified in the P2–P5 commit, absent on the pre-P1 base)

`packages/vantio-gate-mcp/src/policy.js` auto-merged. That file's P2–P5 host-matching edit sits on the P1 API-key edit, so a split still has to be checked by hand even where git does not stop.

The probe worktree was removed. No branch was rewritten.

## Decision

Keep one pull request. Kate can review it in the sections below. The `api_base` remediation stays with the P1 security work in this same branch, because it closes a residual on the gate-mcp fetch tools that the P1 council named.

### Section: P1 security

Installer stage symlink refusal, effective uid 0 for live mutations, observe image pin and `vantio run node`, and `VANTIO_API_KEY` from the environment only.

### Section: api_base remediation

`gate_get_policy` and `gate_residual_risk` do not take `api_base`. The host that receives `VANTIO_API_KEY` is `VANTIO_API_BASE`, or `https://api.vantio.ai` when that variable is unset or blank. A caller-supplied host is ignored.

### Section: P2–P5

Ingest URL failure reporting, observation fail-open without a key, Python ingest fields, `VANTIO_HOME` in CLI readers, streaming byte counts, `http.client` status, concurrent `shield()` run files, gate-mcp DNS suffix and `DRY_RUN_` labels, and the documentation and CI notes already on this branch.

Source candidates stay unpublished: `@vantio/cli` `0.3.25`, `vantio-agent-sdk` `3.1.1`, `@vantio/gate-mcp` `0.1.1`.
