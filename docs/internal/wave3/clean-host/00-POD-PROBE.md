# Producer pod probe

Audience: INTERNAL_RESTRICTED

Plane id: `cursor-coding-pod`

Verdict: `INELIGIBLE`

Probe time: `2026-09-27T14:34:19Z`

Source commit: `0620f10ee52d3abcea18c1c988df02f687f51b36`

The probe describes the producer pod. It is an inventory of what that pod presented. It is not a clean-baseline certificate and it is not a compatibility pass.

## 1. Identity

| Fact | Observed value |
| --- | --- |
| `uname -a` | `Linux cursor 6.12.94+ #1 SMP PREEMPT_DYNAMIC Thu Sep 24 16:04:37 UTC 2026 x86_64 GNU/Linux` |
| `uname -m` | `x86_64` |
| OS | Ubuntu 24.04.4 LTS (`ID=ubuntu`, `VERSION_ID=24.04`) |
| `/proc/1/cgroup` | `0::/system.slice/pod-gc5te7zkozh5neaqpwm4mgnzpe-3239cabe/init` |
| User | `ubuntu` uid `1000`, group `sudo` |
| `sudo -n true` | exit 0 |
| Effective capabilities, uid 1000 | `Current: =i` |
| Effective capabilities, root via `sudo -n capsh --print` | `Current: =eip` |
| Bounding set includes | `cap_bpf`, `cap_net_admin`, `cap_sys_admin` |
| Environment build snapshot | `bld-20260927-f7f18e2d-1e93-4ae1-a8e5-adce44c693d5` |
| `usePrivateWorker` on this run | false |

The snapshot id is the build this pod booted from. This force did not call a reset API and did not treat the snapshot as attachment rollback.

## 2. Kernel and BPF

| Fact | Observed value |
| --- | --- |
| `/sys/kernel/btf` | absent as root |
| `/sys/kernel/btf/vmlinux` | absent as root |
| `/proc/config.gz` | absent |
| `/boot/config-6.12.94+` | absent |
| `/lib/modules/6.12.94+` | absent |
| `/proc/sys/kernel/unprivileged_bpf_disabled` | `2` |
| `/sys/fs/bpf` | mounted `bpf`, `mode=700`, entry count `0` |
| `/sys/fs/cgroup` | cgroup2, controllers `cpuset cpu io memory hugetlb pids` |
| `bpftool` | absent |
| `ip` | absent |
| `/sys/kernel/security/lockdown` | absent |
| `docker`, `kind`, `kubectl`, `helm` | absent |
| `/var/run/docker.sock` | absent |

`unprivileged_bpf_disabled=2` means unprivileged BPF is disabled and the sysctl is locked. Root via sudo holds a full capability set. The BTF file P2 names is absent, and the running kernel's module directory is absent.

## 3. Userspace named by the packaging plan

| Fact | Observed value |
| --- | --- |
| `curl` | `/usr/bin/curl` |
| `libssl.so.3` | present |
| `libgnutls.so.30` | present |
| `node` | `v22.14.0` |
| `clang` | `/usr/bin/clang` |

OpenSSL and GnuTLS libraries are present. Their presence does not supply BTF or a loader. Clang's presence does not create `/sys/kernel/btf/vmlinux`.

## 4. Vantio process state on this pod

| Fact | Observed value |
| --- | --- |
| `$HOME/.vantio` | absent |
| `/run/vantio` | absent |
| `/usr/local/bin/vantio` | absent |
| `VANTIO_HOME`, `VANTIO_SOAK_LOCAL`, `VANTIO_INGEST_URL` | unset |
| `VANTIO_API_KEY` | unset |
| `GHCR_TOKEN`, `GITHUB_TOKEN` | unset |
| Listeners on port `5001` | none (`ss -lnt`) |

No Phantom-Box control-plane process was used as a baseline. Port `5001` had no listener.

## 5. Artifact channel

`gh repo view vantioai/vantio-phantom-engine --json name,visibility` returned `Could not resolve to a Repository`. No local Phantom Engine checkout was mounted. This force did not pull an image and did not query a registry.
