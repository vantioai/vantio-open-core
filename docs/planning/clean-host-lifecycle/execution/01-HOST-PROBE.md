# Host probe

Audience: INTERNAL_RESTRICTED

Environment class: `CLEAN_HOST_INTERNAL_PROOF`

Evidence tier: `UNSET`

Probe time: `2026-09-27T11:18:58Z`

Source commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

The probe describes the producer pod. It is an inventory of what that pod presented. It is not a clean-baseline certificate and it is not a compatibility pass.

## 1. Identity of the environment

| Fact | Observed value |
| --- | --- |
| `uname -r` | `6.12.94+` |
| `/proc/1/cgroup` | `0::/system.slice/pod-gaa3lai7yrhjnlcigqmih3fb4q-4c8e13b4/init` |
| User | `ubuntu` uid `1000`, group `sudo` |
| `sudo -n true` | exit 0 |
| Effective capabilities, uid 1000 | `Current: =i` |
| Effective capabilities, `sudo -n capsh --print` | `Current: =eip` |
| `$HOME` | `/home/ubuntu` |
| `$HOME/.vantio` | `ABSENT` before and after the exerciser |
| `/run/vantio` | `ABSENT` |
| `/usr/local/bin/vantio` | `ABSENT` |
| `python3 -m pip show vantio-agent-sdk` | `Package(s) not found` |
| Listener on port `5001` | `0` (`ss -lnt`) |
| Process command lines containing `vantio` or `phantom` | none |
| `VANTIO_HOME`, `VANTIO_SOAK_LOCAL`, `VANTIO_INGEST_URL`, `VANTIO_API_KEY` | unset |

The cgroup path is a pod init cgroup. The merged design's architecture section 10 keeps a second machine, a VM image, a container build, and a Kubernetes job out of the lab. This force did not provision one.

## 2. Kernel and BPF

| Fact | Observed value |
| --- | --- |
| `/sys/kernel/btf` | `ABSENT` as root |
| `/sys/kernel/btf/vmlinux` | `ABSENT` as root |
| `/proc/config.gz` | `ABSENT` |
| `/boot/config-6.12.94+` | `ABSENT` |
| `/lib/modules/6.12.94+` | `ABSENT` |
| `/proc/sys/kernel/unprivileged_bpf_disabled` | `2` |
| `/sys/fs/bpf` | mounted `bpf`, mode `1700`, owner `root`, entry count `0` |
| `/sys/fs/cgroup` | cgroup2, controllers `cpuset cpu io memory hugetlb pids` |
| `bpftool` | `ABSENT` |
| `clang --version` | Ubuntu clang `18.1.3` |
| `clang -print-targets` | includes `bpf`, `bpfeb`, `bpfel` |
| `docker`, `kind`, `kubectl`, `helm` | `ABSENT` |
| `/var/run/docker.sock` | `ABSENT` |
| `ip` | `ABSENT` |
| `/sys/kernel/security/lockdown` | `ABSENT` |

`unprivileged_bpf_disabled=2` means unprivileged BPF is disabled and the sysctl is locked. Root via sudo holds a full capability set. The BTF file the Phantom Engine prerequisite names is still absent, and the running kernel's module directory is absent.

## 3. Userspace libraries named by the packaging plan

| Fact | Observed value |
| --- | --- |
| `curl` | `/usr/bin/curl`, curl `8.5.0` |
| `libssl.so.3` | `/lib/x86_64-linux-gnu/libssl.so.3` |
| `libgnutls.so.30` | `/lib/x86_64-linux-gnu/libgnutls.so.30` |
| `node` | `v22.14.0` |
| `git` | `2.43.0` |
| In-tree `@vantio/cli` version | `0.3.24` in `packages/vantio-cli/package.json` |
| `node_modules` at the repository root | `ABSENT` |

OpenSSL and GnuTLS libraries are present. Their presence does not supply BTF or a loader.

## 4. Phantom Engine artifact access

Command:

`gh repo view vantioai/vantio-phantom-engine --json name,visibility`

Result:

`GraphQL: Could not resolve to a Repository with the name 'vantioai/vantio-phantom-engine'. (repository)`

No checkout of that repository exists on this pod. `GHCR_TOKEN` and `GITHUB_TOKEN` were unset in the probe shell. No image digest, Helm chart, or embedded eBPF object was on disk. This force did not query GHCR and did not pull an image.

`docs/planning/phantom-engine-production/02-P1-PACKAGE-ARTIFACT-PROVENANCE.md` records the private tip it read as `631e435315cd780d83d3259e111893c1d0569bc3` and records registry existence of `ghcr.io/vantioai/vantio-phantom-engine:0.1.0` as `UNVERIFIED`. This force did not re-read that private tip.

## 5. Phantom-Box

| Signal | Probe |
| --- | --- |
| `VANTIO_SOAK_LOCAL` | unset |
| `VANTIO_INGEST_URL` | unset |
| Port `5001` listeners | `0` |
| Soak process | none found |

The exerciser refusal cases set those variables only inside a child environment and expect exit `21`. The parent environment used for capture left them unset. No Phantom-Box directory or control-plane state was used as a baseline.
