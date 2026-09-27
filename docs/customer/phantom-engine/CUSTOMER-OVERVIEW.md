# Phantom Engine — customer overview

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Source match: private product repository `vantioai/vantio-phantom-engine` commit `631e435315cd780d83d3259e111893c1d0569bc3`. Machine-readable fields are in [VERSION-METADATA.json](./VERSION-METADATA.json).

---

## What this manual is

This is the customer operating manual for **Vantio Phantom Engine** on Linux hosts you enroll. One node purchase covers Observe, Enforce, and Control on that host. The price recorded for this manual is **$799 per enrolled node per month**. Vantio Enterprise is an optional governance add-on; commercial terms for that add-on are talk to sales.

Vantio Optics is a separate, free observe product. This manual does not replace the Optics documentation.

Every deployment starts with a technical architecture review. This draft is not a self-serve production approval, a certification, or a statement that your environment has been validated.

## How to read status words

Use these words exactly. A later sentence does not promote a weaker word to a stronger one.

| Word | Meaning in this manual |
|---|---|
| **observed** | An event was recorded. Recording does not refuse the action. |
| **enforced** | A control that was turned on refused or changed the action (drop, in-process block, redaction, cap, or path refusal). |
| **configured** | An operator set a flag, allowlist, annotation, file path, or policy. Configuration alone does not enroll a workload and does not enforce. |
| **enrolled** | The workload's cgroup, or the pod subtree resolved from it, is in the enrolled set. Enrollment alone does not drop traffic. |
| **independently tested** | Vantio has a lab record on Vantio-controlled Linux (a privileged host and, where stated, a local `kind` cluster). That record is not your environment. |
| **customer validated** | Exercised and accepted in a customer's own environment. This manual records none. |
| **unsupported** | Out of scope for this product version. |
| **unavailable** | Named in the design and not available to operate in this version. |
| **not tested** | Present in code or in a manifest, with no recorded successful run of that check. |

Lab rows in this manual are **independently tested** as repository evidence. The September 20, 2026 product remediation did not load eBPF. Writing this manual did not load eBPF, did not deploy a cluster, and did not write to Spanner.

## What you are running

Phantom Engine is a Linux daemon (`vantio-loader`) on hosts you control. It loads kernel programs that:

- record encrypted writes that pass through OpenSSL `SSL_write` or GnuTLS `gnutls_record_send` when those libraries are present
- record process execution and file-open activity that the attached tracepoints see
- can drop egress from **enrolled** workloads to destinations outside the allow rules, when scoped enforcement is on
- can refuse configured filesystem path prefixes on the host (Control path protection)

Application-path enforcement (block by hostname, redaction, spend or size caps) is the bundled on-prem component delivered with the Phantom Engine purchase. It is not a second invoice. The Helm chart installs the host Control DaemonSet. It does not install that on-prem component. See [DEPLOYMENT-GUIDE.md](./DEPLOYMENT-GUIDE.md).

Default host mode is **audit**: events are **observed**, and egress is not dropped. Scoped enforcement and node-wide drop are separate operator choices. See [POLICY-GUIDE.md](./POLICY-GUIDE.md).

## Evidence labels you will see

| Label | Plane | What it means |
|---|---|---|
| `OBSERVED` | Optics, and the host wire record for a TLS write that was seen | Recorded. The TLS probe does not stop that write. |
| `ALLOWED` | Phantom Engine product label for a host pass-through | The product name for a seen, not-dropped host event. The wire field may still say `OBSERVED`. |
| `BLOCKED` | Host drop or in-process block | An enforced refusal. A host `NETWORK_BLOCK` row is the drop record, with the dropped length in `BytesSevered`. |
| `REDACTED` | In-process application-path enforcement | Payload handling on the wired application path. |
| `BYPASS_INDICATOR` | Rogue Reconciliation | The host recorded a transmission and the application layer has no matching record. |

Rogue Reconciliation is the name of that gap. A lab demo has produced `BYPASS_INDICATOR`. A standing reconciliation service is **unavailable**. This manual does not include a procedure for creating that gap.

Local NDJSON is an append-oriented log. It is the lab-verified evidence file on a host that runs the loader with an output file. It is not a WORM store. A Google Cloud Spanner writer exists in the loader and matches the ledger schema. A live Spanner insert is **not tested**.

## Document map

| Document | Use it for |
|---|---|
| [DEPLOYMENT-GUIDE.md](./DEPLOYMENT-GUIDE.md) | Install on a host or with Helm |
| [SUPPORTED-ENVIRONMENTS.md](./SUPPORTED-ENVIRONMENTS.md) | Kernels, clusters, and what has been exercised |
| [ARCHITECTURE-BOUNDARIES.md](./ARCHITECTURE-BOUNDARIES.md) | What sits in the customer environment |
| [ENROLLMENT-GUIDE.md](./ENROLLMENT-GUIDE.md) | Which workloads are in scope |
| [POLICY-GUIDE.md](./POLICY-GUIDE.md) | Audit, scoped drop, allow rules, path control |
| [OPERATIONS-RUNBOOK.md](./OPERATIONS-RUNBOOK.md) | Day-2 operation |
| [UPGRADE-AND-ROLLBACK.md](./UPGRADE-AND-ROLLBACK.md) | Version pin and return to a prior install |
| [BACKUP-AND-RECOVERY.md](./BACKUP-AND-RECOVERY.md) | What is durable |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | Startup and silence |
| [SECURITY-GUIDE.md](./SECURITY-GUIDE.md) | Threats, residuals, handling of this manual |
| [EVIDENCE-AND-ASSURANCE.md](./EVIDENCE-AND-ASSURANCE.md) | Labels, lab evidence, and what is not attested |
| [REMOVAL-AND-UNINSTALL.md](./REMOVAL-AND-UNINSTALL.md) | Stop and remove |
| [INCIDENT-RESPONSE.md](./INCIDENT-RESPONSE.md) | Preserve evidence and return to audit |
| [KNOWN-LIMITATIONS.md](./KNOWN-LIMITATIONS.md) | Residuals for this version |
| [CUSTOMER-AI-GUIDE.md](./CUSTOMER-AI-GUIDE.md) | Rules for an assistant that reads this manual |
| [CUSTOMER-RELEASE-NOTES.md](./CUSTOMER-RELEASE-NOTES.md) | What manual version 1 matches |
| [VERSION-METADATA.json](./VERSION-METADATA.json) | Version, commit, distribution |

## Distribution

Authorized customers and the Vantio review of this draft may hold these files. The public Optics packages do not contain this directory. Their npm `files` lists and the Python wheel package list do not include `docs/customer/`. `git archive` omits `docs/customer/phantom-engine/` via `export-ignore` in the open-core `.gitattributes`.

Do not copy this tree into a public website, `llms.txt`, an npm tarball, a PyPI artifact, a release note on a public tag, or a marketing page. Do not link it from the public open-core README.

This draft lives on a branch of `vantio-open-core` so it can be reviewed. Merging it to the public default branch would place customer-confidential text on a public repository. That merge is outside this draft.

## What this manual leaves out

Operational procedure that a customer needs to install, enroll, constrain, back up, and remove the product is in the documents above.

The following are omitted on purpose:

- kernel offsets, map layouts, and probe-attachment internals
- procedures or payloads that demonstrate a control gap
- private lab host names, host paths, and operator drop-in files
- customer names, credentials, and live project identifiers
- calendar dates for unshipped work
- Vantio Enterprise governance material that is not required to operate Phantom Engine
- internal engineering names where a customer word exists (say **Control**, including path protection, rather than internal feature nicknames)

Questions about this draft: `security@vantio.ai`.
