# vantio-install

`vantio-install` plans and applies a Vantio node from a bundle that is already on the machine. It checks the host and the artifact hashes before it changes anything.

The default mode is observe-only. Enforcement stays off. When Phantom Engine is started, traffic control stays audit-only.

This package is separate from `@vantio/cli` 0.3.24. Installing a node does not modify that CLI package. The Agent SDK pins stay npm 0.2.4 and Python 3.1.0.

Obtain `vantio-install` and `vantio-verify` from the sealed wheel in `docs/QUICKSTART.md`. Cloning this repository is forbidden on the customer path.

Run the commands from the host that will keep the node:

- `vantio-install plan` writes a plan and does not change installed products.
- `vantio-install apply` on a customer host is the dual-gated command in `docs/INSTALL.md`. `--fixture-host` is forbidden for customer operators.
- `vantio-install status` reads the saved transaction.
- `vantio-install rollback` on a customer host is the dual-gated command in `docs/ROLLBACK.md`.
- `vantio-install uninstall` on a customer host is the dual-gated command in `docs/UNINSTALL.md`.
- `vantio-install verify-removal` checks whether that scope is actually gone, including the known pin names on `/sys/fs/bpf` for a Phantom Engine scope.

`vantio-boot-hold` is the early-boot hold for enrolled workloads. It is on unless a root admin opts out. Read `docs/BOOT-HOLD.md`. The command prints the same JSON envelope, and the reboot exposure row stays `NOT_PROVED` until a later host reproof.

Every command prints one JSON object. `proof_state` stays `NOT_PROVED` in this package. `vantio-verify` reads the evidence directory and the bundle from disk, and it ignores an installer exit code of 0.

A live change needs `VANTIO_INSTALL_ALLOW_LIVE=1` and `--i-accept-live-mutations` together, plus `--plan` and `--plan-sha256`, on `apply`, `rollback`, or `uninstall`. The installer then runs an allowlisted observe-only command list and checks the host again before it treats the step as verified.

The supported host for this contract is Ubuntu 24.04 LTS on x86_64, with cgroup v2, kernel BTF, bpffs, tracefs at `/sys/kernel/tracing`, Docker, AppArmor, and Node.js 18 or newer.
