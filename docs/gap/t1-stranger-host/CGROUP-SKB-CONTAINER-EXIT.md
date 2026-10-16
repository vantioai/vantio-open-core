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

## What uninstall did on 533c0181

Open-core `533c01816848c1a9bb2dc186927cb0a9a958cffd` ran the same enterprise arm on instance `i-0a06cb63d2ac0d4b3`. Run `38960187559` still listed `cgroup_skb_egress_enforce` in `after_container_exit` after the container was gone. The product uninstall then ran with no lab detach. `removal.loader_programs` was empty, `removal.bpffs_vantio` was empty, `removal.verified_removed` was true, and the tail was `UNINSTALL_VERIFIED`.

That run did not probe the secret open or a denied egress in the window after the container exited and before uninstall. `guest_rows` removes the lab cgroup before it reads bpftool, so the listing is not an enforcement measurement.

## What the next battery measures

`r15-container-exit` stops the loader container, leaves the cgroup in place, and probes the secret open and one egress before `vantio-loader --uninstall`. The rows record `fail_open`, `fail_closed`, `mixed`, or `unmeasured`. The harness does not detach the program to change that result.
