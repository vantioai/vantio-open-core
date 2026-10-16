# Kernel lockdown and Secure Boot — installer preflight

UTC: 2026-10-16

Check id: `PF-KERNEL-LOCKDOWN` in `vantio-install` plan preflight.

This check reads two facts. Kernel lockdown is the bracketed mode in `/sys/kernel/security/lockdown`. Secure Boot is the EFI variable `SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c`: four attribute bytes, then one value byte, `1` on or `0` off. A missing variable is `absent`. Any other shape is `unreadable`.

The check does not open a TPM. It does not read a measured-boot log. `measured_boot` is the literal `not_checked`. `tpm_attestation` is the literal `roadmap`.

## Matrix

| Secure Boot | lockdown | Result | Reason |
| --- | --- | --- | --- |
| off | none | PASS | `continue` |
| off | integrity | PASS | `continue` |
| off | confidentiality | BLOCKED | `lockdown_confidentiality` |
| on | none | BLOCKED | `secure_boot_lockdown_mismatch` |
| on | integrity | PASS | `continue` |
| on | confidentiality | BLOCKED | `lockdown_confidentiality` |
| absent | none | PASS | `continue` |
| absent | integrity | PASS | `continue` |
| absent | confidentiality | BLOCKED | `lockdown_confidentiality` |

`absent` is an EFI variable that is not on the host. Cloud images often have no `efivars` mount. Missing Secure Boot is not, by itself, a refusal.

Confidentiality is a refusal in every Secure Boot state, including on and unreadable. The remediation sentence is: "Kernel lockdown is confidentiality. The installer refuses this host. Measured boot and TPM attestation were not checked."

Secure Boot on with lockdown `none` is a refusal. Those two facts disagree, and the check does not pick one of them.

An unreadable lockdown file is `lockdown_unreadable`. An unreadable Secure Boot variable, when lockdown is `none` or `integrity`, is `secure_boot_unreadable`.

## Measured boot and TPM

Roadmap. A later design would have to name the TPM quote, the PCR set, and the event log it trusts. This preflight does not do that work, and a passing row is not an attestation.

## Labels

| Result | Label |
| --- | --- |
| The nine-pair matrix, the confidentiality sentence, and the EFI byte parser, from `packages/vantio-install/tests/test_kernel_lockdown.py` | Verified |
| A live host whose `/sys/kernel/security/lockdown` and EFI variable were read by this preflight | Lab-only. This workspace has neither file |
| Measured boot and TPM attestation | Roadmap |

The stranger-host operator package has its own lockdown stop. This page does not change that package.
