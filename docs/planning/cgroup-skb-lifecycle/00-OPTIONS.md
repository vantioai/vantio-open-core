# R15 — `cgroup_skb_egress_enforce` after the loader container exits

UTC: 2026-10-16

Status: design only. **Roadmap**. This document does not choose an option.

The loader is not modified. No attach flag, link flag, pin, or uninstall path is changed. Lab agent `bc-8b310b16` is measuring the live behavior. This page does not report that measurement and does not speak for it.

## What is already on record

`docs/gap/t1-stranger-host/CGROUP-SKB-CONTAINER-EXIT.md` records one lab observation. Label for that observation: **Lab-only**.

On 2026-10-16 the enterprise arm ran on AWS instance `i-0f602b4829b53f1d6` at open-core `613f6b23`, image `vantio-phantom-engine:deb6faa3`, seal `6d3ce580`. Run `38950295404` stopped the loader container. `docker ps` was empty. `bpftool prog show` still listed `cgroup_skb_egress_enforce`. That list was written before `/var/lib/vantio/vantio-loader --uninstall`. The loader then printed `UNINSTALL_VERIFIED`. The arm did not read bpftool again after uninstall. The record therefore does not say whether uninstall detached the program.

`removal.loader_programs` was `["cgroup_skb_egress_enforce"]`, `removal.docker_containers` was empty, `removal.verified_removed` was false, and `uninstall_tail` was `UNINSTALL_VERIFIED`.

`cgroup_skb_egress_enforce` is a Phantom Engine program. The engine object defines it with `#[cgroup_skb(egress)]`. `vantio-loader` loads it when started with `--cgroup-skb-enforce` and attaches it to the enrolled cgroup. The Enterprise adapter adds that flag when deny is enabled. Those sentences are the existing record. This page does not re-verify them on a host.

## The question

After the loader container exits, and before `vantio-loader --uninstall`, should `cgroup_skb_egress_enforce` stay attached to the enrolled cgroup?

Two options. Both are **Roadmap** until a measurement this document does not own is written down and a later change selects one. Selecting one would be a loader change. That change is not in this commit.

## Option A — keep enforcing

Stopping the loader container does not detach the program. The enrolled cgroup keeps the last `cgroup_skb_egress_enforce` until uninstall or a later loader replaces it.

This is the tamper-resistance option. A stop or a kill of the container is not, by itself, a way to turn egress deny off.

What that costs:

- The last program keeps running after a crash. If the maps still hold the previous allow and deny sets, traffic follows that old policy until something replaces the program. This page does not claim the maps are pinned, and it does not claim they are not. That is part of what `bc-8b310b16` is measuring.
- A new policy file does nothing until a loader start replaces the program. There is a window of stale deny.
- The enterprise grade that lists programs after the container is gone, and before uninstall, will keep seeing this program. `programs_not_removed` is then the expected reading of that early list, not proof that uninstall failed. The grade has to separate "container exited" from "uninstall finished". The 2026-10-16 arm did not read bpftool after uninstall, so it cannot settle that split.
- Uninstall is the detach. If uninstall leaves the program, removal failed. Keeping the program on container exit is not an excuse for a failed uninstall.
- A reboot drops BPF that was not saved across boot. The boot-hold note already says pins are empty after reboot until the loader attaches. Survival past container exit is not survival past reboot. The boot-hold packet filter is a different mechanism and is not changed here.

## Option B — detach when the container exits

The program's lifetime ends with the loader process. After `docker stop`, `bpftool` does not list `cgroup_skb_egress_enforce` on the enrolled cgroup, and any pin that belonged only to that attach is gone.

This matches a grade that expects no engine program once the container is gone, including the pre-uninstall list from the 2026-10-16 arm.

What that costs:

- A stop of the container removes egress deny. A caller that can stop the container can turn that deny off. That is the opposite of the tamper-resistance option.
- A crash and an intentional stop look the same. Enrolled egress follows the rest of the host policy until the loader attaches again. The boot hold, when it is installed, can still drop enrolled egress. This option does not install or remove the boot hold. A host without the boot hold has a gap from container exit until the next successful attach.
- Restart has to attach again. The gap is the time between exit and the next attach.
- Uninstall still has to prove that no program and no Vantio pin remain. Detach-on-exit does not replace that proof. A pin that outlives the process is still a failed removal.

## Tradeoff

| Question | Keep enforcing | Detach on exit |
| --- | --- | --- |
| Can stopping the container turn deny off? | No, not by the stop alone | Yes |
| What runs after a crash? | The last program, on the last maps if those maps are still alive | No `cgroup_skb_egress_enforce` until the next attach |
| Pre-uninstall `bpftool` after the container is gone | The program is still listed. That list is not an uninstall result | The program is absent if detach ran |
| Uninstall | Must detach. A program that remains is a failed removal | Must still show no program and no Vantio pin |
| Reboot | Unpinned BPF is gone after reboot either way | Same |

No row in that table is selected.

## What stays unchanged

- `vantio-loader` in the engine tree. This repository does not contain that source, and this commit does not patch a copy of it.
- Lab workflows, `scripts/aws`, `scripts/gcp`, and the guest row scripts.
- The boot-hold units.
- The public pin and the seal constants.

## Labels

| Result | Label |
| --- | --- |
| Option A and option B, with the tradeoff above | Roadmap |
| The 2026-10-16 `bpftool` listing after container exit and before uninstall | Lab-only |
| A loader build that keeps or detaches the program | Not in this commit. Not Verified |

`bc-8b310b16` owns the measurement that would show which of these the current loader already does. Until that measurement is filed, this page does not describe the current loader as either option.
