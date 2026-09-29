# Install

`vantio-install` and `vantio-verify` come from the sealed wheel in `QUICKSTART.md`. Both commands are on `PATH` before you use this page. The product bundle is already on the host. The installer reads that directory. It does not fetch it.

Set `iface` in the config to a network interface that is up on that host, and set `workload_roots` to absolute directories you own. `artifact_source` stays `sealed_archive`.

`vantio-install plan --bundle <bundle> --config <config> --json` checks the host, the artifact hashes, and the config. It writes `PLAN.json` and `PREFLIGHT.json` under the evidence directory. It does not install Optics or start Phantom Engine.

Exit 0 means the transaction reached `PLANNED`. A blocked or unsupported host returns a non-zero exit and a JSON `state` you can read.

Apply asks for `--yes` so a plan is not executed by accident. The default mode is observe-only, and enforcement stays `NOT_ENABLED`.

A customer apply uses both live gates and the plan hash. `--yes` alone has no live grant. That ungated form is forbidden for customer operators. `--fixture-host` loads an internal JSON host fixture, skips the live grant, and is forbidden for customer operators. The same two rules cover `rollback` and `uninstall`. Customer commands do not pass `--fixture-host`.

The install principal must already match a privilege mode in `PREFLIGHT.md` (`root` as effective uid 0, `sudo`, or `docker_group`). The installer runs Docker from its allowlisted argv list. Raw `docker` and raw `sudo docker` are forbidden.

A customer apply on the host that will keep the node uses both gates and the plan hash:

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install apply --transaction-id <id> --yes --plan <PLAN.json> --plan-sha256 <hex> --i-accept-live-mutations --json`

`<hex>` is the SHA-256 of that `PLAN.json` file. The installer recomputes the hash, checks the transaction id, and checks the artifact bytes again before each change. A mismatch stops the command. The sealed Phantom Engine tip, archive hash, and manifest digest stay the ones recorded for this package.

Apply is finished only when `state` is `HEALTHY` or `DEGRADED` and `HEALTH.json` records that result. `APPLIED` means the steps ran and health is not confirmed yet. A process exit of 0 from Docker, npm, or pip is not that result. After the Optics npm install, the host check requires `<prefix>/bin/vantio` and the pinned CLI version (`vantio --version`, or the installed package manifest when the binary does not print a version). After the Agent SDK npm install, the host check requires `<prefix>/lib/node_modules/@vantio/agent-sdk` and the pinned version in that package manifest. After the Agent SDK pip install, the host check requires the `vantio` module under the prefix and the pinned version. Debian and Ubuntu pip write that module at `local/lib/python3.X/dist-packages`. An upstream prefix layout writes it at `lib/python3.X/site-packages`. When the module does not declare a version, the check reads the matching dist-info metadata. `install_agent_sdks` is checkpointed only after both SDK checks pass. Before the observe-only Phantom Engine container starts, the installer loads AppArmor profile `vantio-pe-observe` and passes `--security-opt apparmor=vantio-pe-observe`. The same start bind-mounts host `/sys/fs/bpf` and host `/sys/kernel/tracing`. Preflight records the tracing mount as PF-TRACEFS and blocks when that directory is missing or empty. The host check for that container requires the process to be running under that profile.
