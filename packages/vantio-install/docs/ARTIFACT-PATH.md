# Customer artifact path (sealed-byte placement)

Audience: customer-facing documentation draft (INTERNAL staging — published=false)

This note is for an operator who places **already-sealed** bytes into a local bundle directory before a later guided install. The installer reads that directory. It does **not** fetch artifacts from a network registry, object store, or custody host.

**Claim ceiling:** `INTERNAL_CLEAN_HOST_PROOF` only. This document does not claim stranger-host proof, customer validation, or enforce-mode efficacy.

## What this document does not do

- Does **not** name any internal custody host, lab alias, or transfer workstation as a download source.
- Does **not** publish a download URL, registry token, GHCR image, or public PE release.
- Does **not** authorize Class B provision, live apply, or GHCR enablement.
- `published` remains **false** for Phantom Engine media.

Transfer of sealed bytes into the customer-controlled staging area is a **designated operator handoff** outside this document. Customer materials name only the relative bundle path below. They do not name an internal custody host, a workstation alias, an absolute filesystem path, a port, or a download URL.

## Optics pins (registry facts — not PE)

Optics CLI 0.3.24:

- Path: `artifacts/optics/cli-0.3.24.tgz`
- SHA-256: `82fe13ad6fc916ac67a670bd95fbf18b24389ecb383d81246e1d52cb96712a1f`

Agent SDK npm 0.2.4:

- Path: `artifacts/optics/agent-sdk-0.2.4.tgz`
- SHA-256: `465eca5e0db9240530c15b6ab9725c5e302626cdbec541b31b4987d52d36c55c`

Agent SDK Python 3.1.0 wheel:

- Path: `artifacts/optics/vantio_agent_sdk-3.1.0-py3-none-any.whl`
- SHA-256: `dcf84cb3c4f144ece21032001657bfd9c91067faeffbefd0fb2ae19d6109dbeb`

Optional Python sdist (only if included):

- Path: `artifacts/optics/vantio_agent_sdk-3.1.0.tar.gz`
- SHA-256: `9f991291d5e44a23e17a9b0d7db24f6e7048d4c76cf0a9c37e35ccbcfe999c4f`

## Sealed Phantom Engine archive

Place the sealed tar under this basename. Apply opens that path and checks this SHA-256.

- Path: `artifacts/phantom-engine/vantio-phantom-engine-pe-residuals-06696d5-linux-amd64.oci.tar`
- SHA-256: `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e`
- Source commit: `06696d5020700693b0154c59d0e072a24f648378`
- Manifest digest: `sha256:8b40aec5c125043ec4278a14170677474c9ca31a7ae78e8496c40dffa69d0e19`

That manifest digest is the digest inside the sealed tar. On Ubuntu 24.04, apply writes a temporary load archive when a layer is gzip and the manifest calls it an uncompressed tar, then `docker load` records the corrected manifest. The sealed file hash stays `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e`.

**Naming rule:** customer docs and checksums use the basename above. Do not substitute a shorter untagged alias or any absolute path.

`artifacts/phantom-engine/PHANTOM-ARTIFACT-MANIFEST.json` must record the same commit, archive hash, and manifest digest. `SHA256SUMS` lists every file in the bundle. A mismatch stops `plan`.

### Example SHA256SUMS line

```
e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e  artifacts/phantom-engine/vantio-phantom-engine-pe-residuals-06696d5-linux-amd64.oci.tar
```

## GHCR / registries

GitHub Container Registry (GHCR) is **not** a Phantom Engine distribution source for this contract. Do not enable GHCR pulls for PE in customer docs. Optics npm/PyPI pins above are separate from PE sealed-byte placement.

## Host contract (observe-oriented)

Host for this contract: Ubuntu 24.04 on x86_64, with kernel BTF, cgroup v2, bpffs, tracefs at `/sys/kernel/tracing`, Docker, AppArmor with `apparmor_parser`, and Node.js 18 or newer. Observe-oriented PE container profile and interface/`workload_roots` settings remain as in the installer preflight docs. Mode stays observe-only. Enforcement stays off.

## Plan / apply gates

`vantio-install plan --bundle <bundle> --config <config> --json` checks the host and the hashes. It does not install.

A later live apply requires a **separate authorization** (not granted by this document):

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install apply --transaction-id <id> --yes --plan <PLAN.json> --plan-sha256 <hex> --i-accept-live-mutations --json`

Rollback, uninstall, status, and verify-removal semantics remain as documented in QUICKSTART / ROLLBACK / UNINSTALL. Hash mismatch, tip mismatch, missing plan hash, shell strings, extra arguments, or an enforce flag stop the command before host mutation.

## Frozen identity (must match evidence)

| Field | Value |
| --- | --- |
| pe_source_commit | `06696d5020700693b0154c59d0e072a24f648378` |
| pe_archive_sha256 | `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e` |
| published | `false` |
| claim_ceiling | `INTERNAL_CLEAN_HOST_PROOF` |
