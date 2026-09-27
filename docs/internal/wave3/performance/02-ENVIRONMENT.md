# Qualification environment

Audience: INTERNAL_RESTRICTED

This file is written by `scripts/qualify.mjs --write` from the same object as `PERFORMANCE-REGISTER.json`.

| Field | Value |
| --- | --- |
| Pod | `pod-eysq5mdccfbqfk43cdivzr2hwi-1092f170` |
| Cgroup | `0::/system.slice/pod-eysq5mdccfbqfk43cdivzr2hwi-1092f170/init` |
| Hostname | `cursor` |
| uname | `Linux 6.12.94+ x86_64` |
| OS | Ubuntu 24.04.4 LTS |
| Node | `v22.14.0` |
| /sys/kernel/btf/vmlinux | false |
| Kernel module directory | false |
| Selected plane | `NONE` |
| Producer pod verdict | `INELIGIBLE` |
| Measured tree | `123a70546a2579e03d4712bb4ff342c0721f9b86` |
| Starting ref | `0cd36cf1d01c4db83a0a6999db0a322441f61c98` |
| Runtime matches starting ref | true |
| Worktree dirty at measurement | false |
| Run start (ET) | `2026-09-27T11:27:51-04:00` |
| Run start (UTC) | `2026-09-27T15:27:51.260Z` |
| Cursor environment public id | `0d643aa5-b4ac-11f1-bb68-864e54d14197` |
| Cursor environment id source | `CURSOR_ENVIRONMENT_PUBLIC_ID` |
| Cursor environment version | `0d76af42-b4ac-11f1-bb68-864e54d14197` |
| Cursor environment build | `bld-20260927-a2fe54b4-1f8d-45d2-bd12-b4d67f7c587b` |

Observed absent: /sys/kernel/btf/vmlinux, /lib/modules/6.12.94+. This force did not select the producer pod.

Host attachment action: `NOT_PERFORMED`.

| Metric | Result | Value | ET start |
| --- | --- | --- | --- |
| `cpu` | `NOT_MEASURED` |  |  |
| `memory` | `NOT_MEASURED` |  |  |
| `disk` | `NOT_MEASURED` |  |  |
| `evidence_growth` | `MEASURED` | 19092 bytes | `2026-09-27T11:27:52-04:00` |
| `startup` | `NOT_MEASURED` |  |  |
| `policy_load` | `NOT_MEASURED` |  |  |
| `decision_latency` | `MEASURED` | 25345 ns | `2026-09-27T11:27:51-04:00` |
| `connection_latency` | `NOT_MEASURED` |  |  |
| `throughput` | `MEASURED` | 14029 decisions in 200012012 ns | `2026-09-27T11:27:51-04:00` |
| `event_loss` | `NOT_MEASURED` |  |  |
| `backpressure` | `NOT_MEASURED` |  |  |
| `reboot_recovery` | `NOT_MEASURED` |  |  |
| `degradation_recovery` | `NOT_MEASURED` |  |  |
| `rollback` | `NOT_MEASURED` |  |  |
| `uninstall` | `NOT_MEASURED` |  |  |

Reasons for `NOT_MEASURED` rows are on those metrics in `PERFORMANCE-REGISTER.json`.

