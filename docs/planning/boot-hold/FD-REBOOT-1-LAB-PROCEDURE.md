# FD-REBOOT-1 lab procedure — reboot hold reproof

**Audience:** INTERNAL_RESTRICTED  
**Do not run this from the open-core PR.** This file is the procedure for a later authorized Free-plan host reproof.  
**Row:** `B1-REBOOT-EXPOSURE` / GAP-FIP-014  
**Until that host reproof:** **NOT_PROVED**. Unknown is never PASS.  
**Frozen seal (not retro-claimed):** `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e`  
**Ceiling:** `INTERNAL_CLEAN_HOST_PROOF`  
**Account:** `960577828987` only  
**Expected out-of-pocket:** `expected_oop_usd=0` (OOP $0). No Cost Explorer. No Paid instance sizes. No publish. No soak, fleet, or k3s.

Measured on the short run `2026-09-30T2225ET-b1-short` before this change: `W_unprotected≈23.05s`, `W_race≈12.84s`. Loader down and pins empty during the window. The enrolled timeout was not a Phantom Engine deny. An unenrolled connect completed. This procedure exists so a later run can record hold time and show zero enrolled allows. It does not convert that earlier run into a pass.

## Guards (same shape as the B1 short)

1. Fresh cost gate at launch: Free/Active, `expected_oop_usd=0`, `abort=false`, account `960577828987`, no Cost Explorer, no Paid.
2. One lab instance. Prefer `t3.micro`, then `t3.small`. `associate_public_ipv4=false`. `stop_after_minutes` stays inside the short-lab cap. No public IPv4.
3. Region and tags follow the B1 short plan. Re-establish access with SSM or serial.
4. Install the open-core boot hold on the guest (`vantio-boot-hold install`) and set `VANTIO_BOOT_HOLD_LIVE=1` only for the root install and boot units. Enroll one workload and record one unenrolled control with `observe-unenrolled`.
5. Point the loader at `/sys/fs/cgroup/vantio-enrolled.slice` and keep the Phantom Engine container on `--restart=no`, outside that slice.
6. Export timestamps before any terminate. Do not mark the row PASS in the export. A missing timestamp is NOT_PROVED.

## Clock and metrics

Record `T_boot`, `T_egress`, and `T_ready` with the guest clock source (chrony/UTC). Also record `T_hold`, the guest time when `vantio-boot-hold` state is `HELD` and the scoped rules are present.

- `W_unprotected = max(0, T_ready − T_boot)`
- `W_race = T_ready − T_egress` when `T_egress < T_ready`, else `0`
- `W_hold = T_ready − T_hold` when both exist

Report the measured numbers. Do not invent a maximum-seconds marketing threshold.

Target for a future PASS, which this procedure does not award: zero enrolled allows at any point during boot, hold time recorded, and either a deny of the first enrolled egress or a documented fail-closed hold while the loader is absent. An unenrolled connect may complete. That shows the host was not placed on a host-wide default-route hold.

## Matrix

Run these as separate boots. Each boot exports its own `timestamps.json`, `egress-probe.txt`, `hold-status.json`, and a journal excerpt. The enrolled probe and the unenrolled probe race from t=0 (a unit that fires as soon as its gate allows).

### 1. Enrolled and unenrolled from t=0 (both mechanisms on)

Default config: hold on, ordering on. Reboot. From the first userspace moment, attempt enrolled egress and unenrolled egress.

Expect: enrolled unit does not become active before `vantio-pe-enforce-ready.service`. If it is forced to run, its egress does not complete while `state` is `HELD`. Unenrolled egress may complete. SSH session survives. Record `W_hold`.

### 2. Loader fails, hold stays, SSH works, release works

Leave `/etc/vantio/pe-loader.argv.json` absent or point it at a missing binary. Reboot.

Expect: `vantio-pe-loader.service` fails, `vantio-pe-enforce-ready.service` fails, enrolled workload stays inactive, `vantio-boot-hold status` shows `HELD` and `DEGRADED` with the operator message. Open an SSH session and a console session. From SSH as root, `vantio-boot-hold release --break-glass --i-am-root-operator` returns `RELEASED`, health stays `DEGRADED`, and `audit.log` contains `BREAK_GLASS`. Do not call that a reboot PASS.

### 3. Docker restart policy

Create a second container with `--restart=always` and try to enroll it. Expect enroll to refuse until `docker update --restart=no`. After enroll, reboot and confirm `docker ps` does not show the enrolled container before enforce-ready. A container left on `always` and not enrolled is unprotected in status; record it that way rather than calling it held.

### 4. Hold alone

As root, `vantio-boot-hold configure --hold on --ordering off`, then reboot.

Expect: the enrolled unit may start (no `Requires=` on enforce-ready) and its egress still fails while the cgroup and subnet rules are installed. Unenrolled egress may complete. Record hold time. This boot is not a PASS by itself.

### 5. Ordering alone

As root, `vantio-boot-hold configure --hold off --ordering on`, then reboot.

Expect: the packet rules are absent, and the enrolled unit stays inactive until enforce-ready. Record the start time relative to `T_ready`. This boot is not a PASS by itself. Ordering alone leaves a hole if something starts the workload by hand before ready; that is why the hold exists.

### 6. Both together

`vantio-boot-hold opt-in` (hold on and ordering on). Reboot.

Expect: the unit does not start early, and the rules are present until the enforce-ready release. Record `W_hold` and the enrolled and unenrolled probe results.

### 7. Five or more reboots

Repeat the both-together boot five times (5+). Each iteration records `W_hold`, `W_unprotected`, and `W_race` in `reboot-N/timestamps.json`. A missing sample is NOT_PROVED for that iteration. Do not average them into a pass.

### 8. Enrolled workload tries to release

From a process in `vantio-enrolled.slice` (the enrolled unit, including uid 0 inside that cgroup), run `vantio-boot-hold release --break-glass --i-am-root-operator`.

Expect: exit non-zero, JSON `state` `FAILED_SAFE`, and an audit line with `"result": "REFUSED"`. The hold remains. Repeat as a non-root caller and expect the same refusal.

## Evidence

```text
ROW-B1-REBOOT-EXPOSURE/
  timestamps.json
  probe-spec.txt
  egress-probe.txt
  hold-status.json
  audit-excerpt.log
  journal-boot.txt
  matrix/
    hold-alone/
    ordering-alone/
    both/
    loader-fail/
    docker-restart/
    reboot-1/ ... reboot-5/
```

`hold-status.json` is the `vantio-boot-hold status` object. `reboot_row` in that object stays `NOT_PROVED` even when the lab looks clean. A human pass decision waits on the verifier and a fresh seal if Phantom Engine changed. This open-core change does not seal Phantom Engine.
