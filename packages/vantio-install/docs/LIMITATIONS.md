# Limitations

This installer starts Phantom Engine in observe-only mode. Enforcement stays off. OTLP stays disabled. Path deny stays disabled. Traffic control stays audit-only.

The observe-only container is started with `--security-opt apparmor=vantio-pe-observe`. Docker's default profile denies writes under `/sys/fs/bpf`, so `BPF_OBJ_PIN` for the trace map fails after the eBPF object loads. The named profile keeps the rest of the default denials and allows read, write, lock, and link under `/sys/fs/bpf`. The container capability list on that command is `NET_ADMIN`, `BPF`, and `SYS_ADMIN`. Privileged mode stays off. The installer writes the profile under the stage directory and loads it with `apparmor_parser` before the container starts. Preflight records AppArmor and `apparmor_parser` as PF-APPARMOR. Rollback and uninstall unload that profile. `CAP_PERFMON` stays off this start path. A later uprobe that needs it is a separate residual. This change does not raise the proof ceiling.

`proof_state` in the JSON is `NOT_PROVED`. The proof ceiling recorded on the transaction is `INTERNAL_CLEAN_HOST_PROOF`. A local fixture run does not raise that ceiling.

Hosts with less than 3 GiB of memory are recorded as a bounded-memory limitation. Full resource sufficiency stays outside that result. A Free-eligible t3.small is in that class. Preflight records it as PF-MEM, a limitation, and an observe-only install is not stopped for that reason alone. This package does not change the instance size.

The sealed Phantom Engine archive, manifest digest, and Optics package versions are pinned. A hash or tip mismatch stops the install. GHCR tag 0.1.0 is not a source. A transfer that needs a network path must list operator allowlisted source CIDRs, and `0.0.0.0/0` is refused.

Live changes on a host run only when you set `VANTIO_INSTALL_ALLOW_LIVE=1` and pass `--i-accept-live-mutations` on `apply`, `rollback`, or `uninstall`. Either one alone stops before any host change and the command returns `FAILED_SAFE`. With both set, the command still stops unless the plan hash matches, the sealed artifacts match, the host is x86_64 with kernel BTF, the mode is observe-only, and rollback and residual checks are in the plan. The command runs an allowlisted argv list. It does not use a shell string. Exit 0 from one of those commands is not enough; the installer reads the host again before it records the step as verified. A live residual check reports `RESIDUAL_FOUND` when something from that scope is still on the host. From that state, the same dual-gated rollback, or uninstall with `--scope optics` or `--scope all`, removes a leftover Optics CLI or Agent SDK tree under the prefix. Apply stays refused until `verify-removal` reports an empty residual list.

Fixture tests exercise the transaction without those live commands. `proof_state` stays `NOT_PROVED`. The second-lab gate stays closed until a later authorization.
