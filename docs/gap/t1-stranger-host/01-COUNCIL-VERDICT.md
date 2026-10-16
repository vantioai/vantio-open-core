# T1 phase-1 council verdict

UTC: 2026-10-16T15:47:41Z

Subject: `00-DESIGN.md`, `STRANGER_HOST_STANDARD.md`, `EVIDENCE-BUNDLE.md`, `PENTEST-SCOPE.md`, `RISK-REGISTER.md`, `DEPENDENCIES.md`, `LABEL.md`.

Scope of this verdict: the design, before code. This session produced the design and this verdict together. A later review from a different model family has to cover the final commits. This verdict does not do that, and it does not apply a founder-approved label.

## Verdict

**Approve the design for implementation**, with the conditions below. The track label is Roadmap.

## What holds

- The package sits on main `69671e97` and names the lab functions it copies as rules: new-boot evidence (boot id, live cmdline, live LSM list, serial log) and uninstall `VERIFIED_REMOVED`.
- Lab workflows, guest scripts, and the stranger-host refusal packet stay unmodified. Lab agent `bc-8b310b16` keeps the lab slot.
- Preflight fail-closed order matches the comparison plan and adds the unreadable-lockdown, bpffs, and exact-image stops so the two gaps in that comparison (lockdown file not recorded, exact image not recorded) cannot pass silently.
- Signatures accept the pinned TEST document only for `AWAITING_OUTSIDE_REVIEW`. The public pin is refused as a seal and is not a signing key. Fixture signatures cannot flip the host-proof bit.
- The pen-test scope defines the target build and stops at the vendor gate.
- No price, no production root, no Navera access, no cloud run.

## Conditions the code has to meet

1. Operator commands implement every reason code in `STRANGER_HOST_STANDARD.md`. A missing list is a failure, not an empty list.
2. Tests cover each preflight stop, a pass that records lockdown mode and an exact image, each step failure and one all-pass fixture, stale boot id, confidentiality, and signature rejection of a non-TEST key, a production flag, the public pin as a seal, a private-key PEM, and a fixture claim presented as a host proof.
3. The proof script writes an evidence artifact and prints that the stranger host was not run.
4. No edit lands under `.github/workflows/`, `scripts/gcp/`, `scripts/aws/`, `scripts/lab/`, `docs/planning/stranger-host-gate/`, or `README.md`.
5. The implementation commit follows this verdict. It does not rewrite the label to Verified or Lab-only.

## Dissent recorded

The design's step 4 depends on loader words the enterprise guest may not emit by itself. Failing closed is the right default. It means a real bundle can fail step 4 until the operator copies the lab battery words. That is a dependency, not a reason to edit the lab guest in this track.
