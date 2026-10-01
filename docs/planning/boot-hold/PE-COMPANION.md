# Phantom Engine companion note — FD-REBOOT-1

**Audience:** INTERNAL_RESTRICTED  
**Repo this note belongs to:** open-core packaging. It does not patch `vantio-phantom-engine` and it does not invent a seal.

## What open-core ships

`packages/vantio-install` installs these units:

- `vantio-boot-hold.service` — early, `DefaultDependencies=no`, `Before=docker.service containerd.service`, `WantedBy=sysinit.target`
- `vantio-pe-loader.service` — `After=vantio-boot-hold.service docker.service`, `Before=vantio-pe-enforce-ready.service`, `Restart=no`
- `vantio-pe-enforce-ready.service` — `Requires=vantio-pe-loader.service`, runs `release --require-enforce-ready`
- `vantio-enrolled.slice` and `vantio-enrolled-docker@.service`

The loader command is not baked into the unit. A root admin writes `/etc/vantio/pe-loader.argv.json` as a JSON list. Example for a container that was created with `--restart=no` and is not in the enrolled slice:

```json
["/usr/bin/docker", "start", "-a", "vantio-pe"]
```

The container's loader arguments need `--enforce`, `--cgroup-skb-enforce`, and:

```text
--startup-enroll-cgroup /sys/fs/cgroup/vantio-enrolled.slice
```

Enrolled systemd units set `Slice=vantio-enrolled.slice`, so their cgroup is `/sys/fs/cgroup/vantio-enrolled.slice/<unit>`.

## What the PE tree does today

The Phantom Engine tree on this machine has no systemd unit. Startup enrollment is the loop in `vantio-loader/src/main.rs` that calls `resolve_cgroup_spec` for each `--startup-enroll-cgroup` value and inserts that one cgroup id. `cgroup_skb` is then attached to that cgroup path.

A PE repository change is not required for open-core to install the units. If the parent wants the unit to live in the Phantom Engine repo, add `vantio-pe-loader.service` with the same ordering as `vantio_install/boot_hold/units.py` (`pe_loader_service`) and point `ExecStart` at the loader binary with the slice path above. Do not treat that copy as a seal. A merge that changes loader behavior needs a new seal from the parent. Seal `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e` stays frozen and is not retro-claimed.

## What the parent should re-verify on the next seal

The boot units set `VANTIO_BOOT_HOLD_LIVE=1` so apply, release, and loader start actually touch the host. Fixture tests leave that variable unset and pass a fake root, so they record commands instead of changing packet filters. The enforce-ready unit does not set `VANTIO_BOOT_HOLD_ALLOW_FACTS` or `VANTIO_BOOT_HOLD_ALLOW_CALLER_FIXTURE`.

The open-core probe treats enforce-ready as all of:

- a live `vantio-loader` command line containing `--enforce`
- the pinned names `vantio_trace_map`, `vantio_enrolled_cgroups`, `vantio_debug_counters`, `vantio_debug_last_comm`, `vantio_tls_severed_pids`
- `bpftool prog show` containing `cgroup_skb_egress_enforce`
- loader health `OK` (process state R, S, or D)

Unknown on any of those keeps the hold. The parent should confirm on the sealed loader that attaching `cgroup_skb` to `/sys/fs/cgroup/vantio-enrolled.slice` covers descendant cgroups under that slice. This note does not record that confirmation.

A root attacker who can disable host controls is Battery 4. This hold does not detect that tampering.
