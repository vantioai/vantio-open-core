# Stage B artifact path

This note is for the operator who will place sealed bytes on a host before a later live run. The second-lab gate is closed. `proof_state` stays `NOT_PROVED`. This file does not publish a download URL, a registry token, or a public image name.

Place the bytes in the bundle directory on the host that will keep the node. The installer reads that directory. It does not fetch them.

Optics CLI 0.3.24:

- Path: `artifacts/optics/cli-0.3.24.tgz`
- SHA-256: `82fe13ad6fc916ac67a670bd95fbf18b24389ecb383d81246e1d52cb96712a1f`

Agent SDK npm 0.2.4:

- Path: `artifacts/optics/agent-sdk-0.2.4.tgz`
- SHA-256: `465eca5e0db9240530c15b6ab9725c5e302626cdbec541b31b4987d52d36c55c`

Agent SDK Python 3.1.0 wheel:

- Path: `artifacts/optics/vantio_agent_sdk-3.1.0-py3-none-any.whl`
- SHA-256: `dcf84cb3c4f144ece21032001657bfd9c91067faeffbefd0fb2ae19d6109dbeb`

Optional Python sdist, only if you include it:

- Path: `artifacts/optics/vantio_agent_sdk-3.1.0.tar.gz`
- SHA-256: `9f991291d5e44a23e17a9b0d7db24f6e7048d4c76cf0a9c37e35ccbcfe999c4f`

Sealed Phantom Engine archive:

- Path: `artifacts/phantom-engine/vantio-phantom-engine-w3-aws-internal-fab81efc0811-linux-amd64.oci.tar`
- SHA-256: `72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128`
- Source commit: `fab81efc08110506ff90847495197e7051a253b5`
- Manifest digest: `sha256:4d932b93bf4c20983142d5f9bff1ea060d9407a19a5e8c9f59db29f7a4122553`

`artifacts/phantom-engine/PHANTOM-ARTIFACT-MANIFEST.json` records that commit, that archive hash, and that manifest digest. `SHA256SUMS` lists every file in the bundle. A mismatch stops `plan`.

The host for this contract is Ubuntu 24.04 on x86_64, with kernel BTF, cgroup v2, bpffs, tracefs at `/sys/kernel/tracing`, Docker, AppArmor with `apparmor_parser`, and Node.js 18 or newer. The observe-only Phantom Engine container loads profile `vantio-pe-observe` so pin writes under `/sys/fs/bpf` are allowed, and it bind-mounts that tracefs path. Set `iface` to an interface that is up, and set `workload_roots` to absolute directories you own.

`vantio-install plan --bundle <bundle> --config <config> --json` checks the host and the hashes. It does not install.

A later live apply, after the second-lab gate is opened by a separate authorization, looks like this:

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install apply --transaction-id <id> --yes --plan <PLAN.json> --plan-sha256 <hex> --i-accept-live-mutations --json`

`<hex>` is the SHA-256 of `PLAN.json`. Rollback and uninstall use the same two gates, the same plan file, and the same hash. The mode stays observe-only. Enforcement stays off. The installer runs an allowlisted argv list and checks the host again before it records a step as verified.

`vantio-install status --transaction-id <id> --json` reads the saved transaction. If the process stops in the middle, status reports `INTERRUPTED`. Run the same live command again with the same transaction id and the same plan hash to continue, or run rollback if the failure class is `ROLLBACK_REQUIRED`.

`vantio-install verify-removal --transaction-id <id> --json` is the check that confirms removal. `VERIFIED_REMOVED` means the residual list is empty. `RESIDUAL_FOUND` means something from that scope is still on the host. The list includes `<prefix>/bin/vantio` when that file is on disk, even if the saved snapshot has no CLI version. It also includes the Agent SDK npm package, the Python `vantio` module, its dist-info, and `agent-sdk-receipt.json` when those are on disk under the prefix. From `RESIDUAL_FOUND`, the same dual-gated rollback clears those prefix artifacts. `uninstall --scope optics` or `--scope all` with the same gates does that too. `--scope pe` leaves the prefix in place. Run `verify-removal` again after that recovery. Evidence stays in the evidence directory, including `TRANSACTION.json`, `PLAN.json`, `HEALTH.json`, and `LIVE-OPS.jsonl`.

A hash mismatch, a tip mismatch, a missing plan hash, a shell string, an extra argument, or an enforce flag stops the command before that step changes the host. Bounded memory under 3 GiB, including a Free-eligible t3.small, can still plan. Preflight records that as a limitation. The health result is degraded when that is the only limitation. Other preflight failures stop the live command.
