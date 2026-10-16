# cgroup_skb_survives_container_exit

`cgroup_skb_egress_enforce` is a Phantom Engine program. The engine object defines it with `#[cgroup_skb(egress)]`. `vantio-loader` loads it when the process is started with `--cgroup-skb-enforce`, then attaches it to the enrolled cgroup. The Enterprise adapter adds that flag when deny is enabled.

`descendant_probe` does not load it. That program is a userspace vfork that opens a path and sends one UDP datagram.

## What the lab saw

On 2026-10-16 the enterprise arm ran on AWS instance `i-0f602b4829b53f1d6` at open-core `613f6b23`, image `vantio-phantom-engine:deb6faa3`, seal `6d3ce580`. The host had already run reboot-check, two lsm-guard arms, and descendant-b1.

Run `38950295404` stopped the loader container. `docker ps` was empty. `bpftool prog show` still listed `cgroup_skb_egress_enforce`. `guest_rows.py` records that list before the shell runs `/var/lib/vantio/vantio-loader --uninstall`. The loader then printed `UNINSTALL_VERIFIED`. The bpffs name check in that shell found no `vantio*` pin at depth 2. The arm did not read bpftool again after uninstall, so this record does not say whether uninstall cleared the program.

Rows: `removal.loader_programs` was `["cgroup_skb_egress_enforce"]`, `removal.docker_containers` was empty, `removal.verified_removed` was false, and `uninstall_tail` was `UNINSTALL_VERIFIED`.

Evidence from that run:

- `w3-lab-arm.json` for run 38950295404, reason `programs_not_removed`, guest_rc 1, boot `f9435e11-3aaf-4423-8cd1-94ff8b30ed0a`
- `w3-lab-enterprise-rows.json` for the same run

## What the harness does

The lab does not detach this program and does not unlink its pins. After `vantio-loader --uninstall`, the enterprise arm reads bpftool and `/sys/fs/bpf`. `verified_removed` is true only when that read shows no engine program and no Vantio pin, and no container is left. A program that is still listed fails the arm as `programs_not_removed`.

The list guest_rows wrote before uninstall is kept on the rows as `after_container_exit`. That field is the container-exit observation. It is not a lab cleanup.
