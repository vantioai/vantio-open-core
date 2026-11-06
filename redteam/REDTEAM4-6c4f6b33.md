# REDTEAM4 — Phantom Engine `6c4f6b33`

Independent pass. The tester did not write this engine. The only file added to `vantio-open-core` is this report. Product and harness sources were not edited.

The private tree was the uploaded archive, not a clone. The archive has no `.git` directory, so this run cannot prove the tree bytes are commit `6c4f6b33e66cee3dafe8a84d247a1114ccf34140`. That is the commit the task named. The archive SHA-256 is `e14cacb540eafe6ec0e7939534a32b15130fbdf24a431095d7b74bd5de3ec78a`. A hash of the extracted file bytes is `a36eed2795c5f002163e02fca225f1fb596f63cd4fe17441b089b7afa057e951`.

## Result

| Rating | Count |
| --- | ---: |
| HOLDS | 31 |
| BREAKS | 9 |
| OVERCLAIM | 2 |
| UNTESTABLE_HERE | 3 |
| TARGET_DESIGN_ONLY | 1 |

No public page fetched on 2026-11-06 presents kernel enforcement as something a customer can turn on today. The pages say enforcement is not yet available. The breaks below are in the private tree's own "present" and "live-verified" sentences, and in two internal lines that say a control is stronger than this host showed.

## Environment

| Item | Value |
| --- | --- |
| Kernel | `6.12.113+` |
| Boot id | `c308daf4-b4e1-4221-a158-aa27d14d23e3` |
| LSM list | `capability,landlock,selinux,bpf` |
| cgroup | v2 at `/sys/fs/cgroup` |
| bpffs | `/sys/fs/bpf` |
| Toolchain | `rustc 1.101.0-nightly (2d20b42b8 2026-11-04)`, `bpf-linker 0.12.0` |
| Built loader | `114d1997355f8087c236ad9d031ae7247e8bc0a70bbb271b578fef0a136624dc` |
| Built eBPF object | `f0f3a93224e5c3913eac52b5088d6f888044234f0394c1f689bd7f4c0f817b05` |
| Open-core base | `aeb059a78af510a2f9013ac6053afbb79a124af3` |

This boot was not a new lab boot. Nothing here is a clean-host pass, a customer install, or a managed cluster. The loader was started from the extracted tree with a lab Ed25519 key (`dev-nonprod-lab-redteam4`, `not_a_production_root`). `VANTIO_CGROUP_ROOT` was `/sys/fs/cgroup/pe-rt4`, so cgroup programs were attached on that subtree. This agent's cgroup was not enrolled. Before and after each run, a TCP connect to `1.1.1.1:443` from that cgroup completed, and an `AF_UNIX` socket could be created there.

Enforcement flags that were on: `VANTIO_PHANTOM_DENY=1`, `--enforce`, `--iface lo`. The loader also attached the classifier to `enp0s3` because that is the IPv4 default route. Scoped mode was the mode in the log (`SCOPED (drop enrolled)`). `--node-wide-enforcement` and `--kill-on-enforce` were not passed.

`kprobe_open_deny` and `kprobe_openat_deny` did not load. The verifier rejected `bpf_override_return` (`program of this type cannot use helper bpf_override_return#58`). The loader continued with the file LSM. `lsm_bprm_check` and `lsm_bprm_creds` attached for this process only. The log said a kill drops exec deny.

## How a claim was rated

- **HOLDS** — a command on this host matched the sentence.
- **BREAKS** — a command on this host contradicted the sentence.
- **OVERCLAIM** — the sentence says more than the tree does, or says a control cannot be bypassed when a bypass ran.
- **UNTESTABLE_HERE** — the missing piece is named.
- **TARGET_DESIGN_ONLY** — the tree itself says the behavior is not present.

A sentence that only repeats another sentence is not a second claim.

## Claims

### Public pages

Fetched 2026-11-06: `https://vantio.ai/`, `/pricing`, `/llms.txt`, `/phantom-engine`, `/architecture`, `/enterprise`, `/solutions/your-ai`, `/solutions/malicious-ai`, `/docs/install/phantom-engine`.

| # | Claim | Source | Rating |
| --- | --- | --- | --- |
| 1 | "Enforcement is not yet available." | Homepage, `/phantom-engine`, `/architecture`, `/solutions/your-ai`, `/solutions/malicious-ai`, `llms.txt` | HOLDS |
| 2 | "The lab proof does not yet cover child processes." | Homepage, `/phantom-engine`, `llms.txt` | HOLDS |
| 3 | "What it needs from the AI. Nothing. No proxy, no SDK, no prompt." | `/phantom-engine` | HOLDS |
| 4 | Self-install is Ubuntu 24.04 LTS x86_64. "Until the release is configured, that answer is that downloads are not live yet." "Enforcement steps stay off this page until that lab result is published." | `/docs/install/phantom-engine` | HOLDS |
| 5 | "Enterprise governance of Phantom Engine is in progress; it has passed only in Vantio's own lab." | `llms.txt`, `/enterprise`, `/architecture`, `/pricing` | HOLDS |
| 6 | "The design: a change to what AI may do is signed by a named person on your team, and unsigned changes don't take effect." | `/enterprise` | HOLDS |
| 7 | "Your own AI acting on its own and malicious AI coming in from outside meet the same boundary, because it sits on the Linux system." | Homepage | HOLDS |
| 8 | "Phantom Engine is Contact Vantio." | `/pricing`, `llms.txt` | HOLDS |
| 9 | "Use Optics, Phantom Engine, or Enterprise on its own, or run them together." | `llms.txt` | HOLDS |

Claim 1 is the public offer. This private tree does enforce when it is built and started with the lab gates. The site does not ship that binary. Claim 2 is about their published lab proof. On this VM a forked child of an enrolled task was denied (`errno 13`). That does not make their lab-proof sentence false. Claim 3 held in the tests: the denied process was a normal Python interpreter with no SDK. Claim 6 held when a signed cgroup exception was flipped to a bad signature: the exempt cgroup started being dropped on the next sweep. Claim 7 is the mechanism. The tests did not load a poisoned model. Enrollment, not intent, was the switch. The loader accepts only a `dev-nonprod-` lab key. There is no production root in this binary.

Present-tense lines on those pages ("The AI doesn't get a vote.", "Only a person can widen the boundary.", "A person holds the allowlist. The model file does not get to add a destination.") sit on pages that also say enforcement is not yet available. They are not scored as a claim that the stop works today.

### File, exec, and lifetime

| # | Claim | Source | Rating |
| --- | --- | --- | --- |
| 10 | "an enrolled task, including uid 0, cannot read an enforce path or a hard link of that inode. An unenrolled task is outside this row." | `README.md`, Maturity table | HOLDS |
| 11 | A new open of a symlink, a bind mount, a renamed path, or a `./` / `../` path of that inode is denied. | `docs/product-spec.md` path and inode paragraphs; `docs/DESCENDANT_TEST_COVERAGE.md` unresolved-path row | HOLDS |
| 12 | An enrolled task cannot read the bytes of an enforce file. | README sentence in claim 10, read as a read, not only as `open` | BREAKS |
| 13 | The file ceiling covers a descendant of an enrolled cgroup past eight parents. | README "enrolled task" read together with `architecture_state.md` parent walk; CISO packet "not agent-bypassable" | BREAKS |
| 14 | A forked child of an enrolled task is inside the file deny. | `docs/product-spec.md`: "child processes inherit trace context"; fork is the child the lab page says is not yet in the proof | HOLDS |
| 15 | After the task is moved into an unenrolled cgroup, the file deny remains. | `docs/DESCENDANT_TEST_COVERAGE.md`: "Egress stays subject after the current cgroup is not enrolled." File side: "Non-root file open is denied from the anchor." | HOLDS |
| 16 | A new mount namespace or user namespace does not clear the file deny. | `docs/DESCENDANT_TEST_COVERAGE.md` unshare row | HOLDS |
| 17 | "An enrolled non-root lineage may exec only an allowlisted path whose inode is also on the allowlist. ... Uid 0 is not denied." | `docs/operations-guide.md`, Exec allowlist | HOLDS |
| 18 | "A signed stop token removes the pins. SIGINT, SIGTERM, SIGHUP, and SIGKILL do not." Applied to exec deny. | `docs/operations-guide.md`, Exec allowlist | BREAKS |
| 19 | The same SIGKILL sentence, applied to file deny. `docs/product-spec.md`: "SIGINT, SIGTERM, and SIGHUP do not detach those programs." Operations guide: a killed loader keeps returning `EACCES` on a protected open. | `docs/operations-guide.md`, Stopping; `docs/product-spec.md` cross-product table | BREAKS |
| 20 | "SIGINT, SIGTERM, and SIGHUP do not detach an enforcing loader." | `docs/operations-guide.md`, Stopping | HOLDS |

While the loader was alive, uid 65534 and uid 0 in `/sys/fs/cgroup/pe-rt4/leaf` got `errno 13` on `open` of `/tmp/pe-rt4/vault/secret` (mode `0644`). The same uid outside that tree got a successful open. Hard link, symlink, bind mount, `vault/./secret`, `vault/../vault/secret`, and an unenrolled rename of the inode to a new path were all `errno 13` for a new `open`. Depth 8 under the enrolled directory was `errno 13`. Depth 9 was `errno 0`. A second anchor, created twelve levels under `/sys/fs/cgroup/pe-rt4` and enrolled alone, also allowed `open` from nine levels below it.

A root task that was denied, then wrote its pid into `/sys/fs/cgroup/pe-rt4-out`, was still denied (`before_errno_13 moved after_errno_13`). `unshare(CLONE_NEWNS)` as root and `unshare(CLONE_NEWUSER)` as uid 65534 still got `errno 13`.

Exec: `--exec-preset web-server --exec-allow /usr/bin/true`. Enrolled uid 65534 `execve("/bin/sh")` was `errno 13`. Enrolled uid 0 `execve("/bin/sh")` ran. Enrolled uid 65534 `execve("/usr/bin/true")` ran. A forked child, with output flushed, got `errno 13` on the secret.

`SIGINT`, `SIGTERM`, and `SIGHUP` left the loader alive and the open at `errno 13`. `SIGKILL` left the open at `errno 0` and let enrolled uid 65534 run `/bin/sh`. That matches the loader log: the exec links were process-only, and the open kprobes never loaded. After that kill, a connect from the enrolled cgroup still timed out, and a later stop still detached `cgroup_skb` programs. The network attachment outlived the process. The file and exec denies did not.

### Network

| # | Claim | Source | Rating |
| --- | --- | --- | --- |
| 21 | Scoped enforce drops enrolled egress that is not allowlisted, for IPv4, IPv6, UDP/53, ICMP, and raw IP. | `README.md` "Per-agent enforcement"; `docs/product-spec.md` "IPv4 + IPv6"; `docs/operations-guide.md` "an agent cannot escape a drop policy by resolving an AAAA record" | HOLDS |
| 22 | Unenrolled egress is not dropped. | `docs/product-spec.md`: drops "only for enrolled cgroups" | HOLDS |
| 23 | "An enrolled task cannot connect or send on `AF_UNIX` to an unenrolled peer unless that peer's cgroup is on the signed unix allowlist." | `docs/product-spec.md` | HOLDS |
| 24 | "Ingress to an enrolled cgroup is dropped and recorded as `NETWORK_BLOCK`." | `docs/product-spec.md` | HOLDS |
| 25 | "It does not block inbound connections." The loader also prints "ingress: accept/accept4 observe-only (never drop)". | `docs/P0_CUSTOMER_PROTECTION_STATE.md`; loader status line | BREAKS |
| 26 | "Custom allowlist — CIDR ranges (longest-prefix-match ...) ... the address one step past the `/24` boundary was also dropped." | `docs/operations-guide.md`, Enforcement Mode | BREAKS |
| 27 | "`BytesSevered` is the full dropped packet length, including IP and transport headers, not the userspace payload length." | `docs/product-spec.md` | HOLDS |

Enrolled connects to `192.0.2.10` and `2001:db8::10` on `lo` timed out (`errno` empty, which is the socket timeout). The same IPv4 connect from `/sys/fs/cgroup/pe-rt4-out` was `errno 0`. UDP to port 53, ICMP, and `IPPROTO_RAW` from the enrolled cgroup returned `errno 1`, and the UDP listener received nothing. Ledger rows for those drops have `"DropPath":"cgroup_skb"`, `"ActionTaken":"BLOCKED"`, `"BytesObserved":0`. One UDP payload of 13 bytes was recorded as `BytesSevered` 41 (20 + 8 + 13). TCP SYNs were `BytesSevered` 60. The `tc` counter in `/run/vantio-drop-count` stayed 0 while `cgroup_skb` incremented. The classifier was attached to `lo` and `enp0s3`. This run did not show a packet that reached TC and was dropped there. The drop that was counted was `cgroup_skb`.

`AF_UNIX` `socket()` from an enrolled task succeeded. `connect` to an unenrolled listener returned `errno 1`, including when the socket was created before the task moved. The stated claim is connect and send, and that part held. Create is a residual, not a pass of a stronger sentence.

Ingress: a listener in the enrolled leaf bound `192.0.2.10:19042` and printed `ready`. The connect from outside timed out, and the accept timed out. An unenrolled connect to the same address with nothing listening returned `errno 111`. The packet to the enrolled listener was not refused by an empty port. It was dropped. Claim 24 held. Claim 25 did not.

CIDR: the log line was `Allowlisted CIDR range (v4): 192.0.2.0/24`. Enrolled connects to `192.0.2.10` (inside) and `192.0.3.1` (outside) both timed out, and the ledger recorded `NETWORK_BLOCK` / `cgroup_skb` / `BytesSevered` 60 for that process. The prefix did not let the in-range address through, so the boundary demo was not reached.

### Tamper, ledger, TLS

| # | Claim | Source | Rating |
| --- | --- | --- | --- |
| 28 | "Root program detach, link detach, map update, and bpffs unlink or rename of Vantio objects are denied unless the caller is the loader." | `docs/product-spec.md` cross-product table; `docs/operations-guide.md` Stopping | HOLDS |
| 29 | Detach is a signed stop token, and a used nonce cannot be replayed. | `docs/operations-guide.md` Stopping; `vantio-loader/src/authenticated_stop.rs` module comment | BREAKS |
| 30 | Deleting `/run/vantio-stop-nonces` does not make a used stop token usable again. | `vantio-loader/src/authenticated_stop.rs`: the nonce is also stored in `vantio_used_nonce` | HOLDS |
| 31 | The nonce map stays closed to root after the loader exits, so a spent token stays spent. | Same stop design, read with the SIGKILL survival claim | BREAKS |
| 32 | "`ptrace`, `process_vm_*`, `/proc/<pid>/mem`, and `pidfd_getfd`" cannot inspect the loader. | `vantio-phantom-engine/src/main.rs` `lsm_ptrace` comment | HOLDS |
| 33 | An appended, truncated, rolled-back, or bit-flipped ledger row fails `scripts/verify_ledger.py`. | `vantio-loader/src/ledger_chain.rs`; `scripts/verify_ledger.py` docstring | HOLDS |
| 34 | A ledger replaced with a new key, and a matching head, fails that verifier. | Same files, read as proof the loader produced the file | BREAKS |
| 35 | "`--host-cgroup-enroll` enrolls every cgroup on this host, including cgroups created later." A signed exception is required to leave one out. An unsigned file excepts nothing. | `vantio-loader` `--host-cgroup-enroll` help; `vantio-loader/src/host_enroll.rs` | HOLDS |
| 36 | OpenSSL `SSL_write` / `SSL_write_ex`, GnuTLS `gnutls_record_send`, and NSS `PR_Write` are observed. | `docs/product-spec.md` Observe list; `vantio-loader/src/tls_stacks.rs` | HOLDS |
| 37 | "rustls is covered when `Writer::write` is present" and "Go `crypto/tls` is observed at `crypto/tls.(*Conn).Write`" with no binary path required. | `docs/product-spec.md` | OVERCLAIM |
| 38 | Go `crypto/tls.(*Conn).Write` is observed when `VANTIO_GO_TLS_BIN` names the binary. | Loader source for `VANTIO_GO_TLS_BIN`; same spec sentence, narrowed to what the loader does | HOLDS |
| 39 | BoringSSL `SSL_write` in `libboringssl.so` is an attached uprobe. | `docs/product-spec.md`; `tls_stacks.rs` | HOLDS |
| 40 | "the kernel control is not agent-bypassable." | `docs/enterprise/CISO_PACKET.md`, Controls table, L3 residual "not agent-bypassable" | OVERCLAIM |

Claim 28 was while the loader was alive: unlink `errno 1`, rename `errno 1`, `mount -t bpf` on a side directory failed with "permission denied", and `BPF_OBJ_GET` of the enrolled map returned `EPERM`. Claim 29: the stop-authority file's 32-byte `proof_b64` was written into `/sys/fs/bpf/vantio_stop_prf` (four `BPF_MAP_UPDATE_ELEM` calls, `rc=0`). The next unlink of `/sys/fs/bpf/vantio_enrolled_cgroups` succeeded. The nonce and the stop command were not used. The map comment says a non-loader may write that map. The userspace nonce check never ran.

Claim 30: after a real stop, deleting `/run/vantio-stop-nonces` and calling `--authenticated-stop` again still returned `STOP_NONCE_REPLAY`. Claim 31: `BPF_MAP_DELETE_ELEM` on the real nonce key then returned `rc=0`. The next stop did not say `STOP_NONCE_REPLAY`. On the run where cgroup programs had survived `SIGKILL`, that stop was accepted and detached `cgroup_skb_egress_enforce`, `cgroup_skb_ingress_enforce`, and the connect-owner programs.

Claim 32: enrolled and unenrolled `PTRACE_ATTACH` of the loader returned `errno 1`. `open("/proc/<loader>/mem")` returned `errno 13`. A `process_vm_writev` call from this harness returned `errno 22` (`EINVAL`) and did not show a successful write. That call is not evidence of a bypass. The loader's own canary logged `vm errno 1`. This report does not treat the canary as the test.

Claim 33 and 34 used `ledger-run1.ndjson` (135 signed rows, `verify_ledger.py` exit 0). An extra unsigned line: `row 136: unsigned row inside the chain`. Dropping the last row and keeping the old head: head count mismatch. Flipping one hex digit of `chain_hash`: `hash chain broken`. Rewriting every row and the head under a new Ed25519 key: `ledger-ok rows=135`.

Claim 35 was `--host-cgroup-enroll` with `VANTIO_CGROUP_ROOT=/sys/fs/cgroup/pe-rt4`, not the real cgroup root. A cgroup created after the ready line was dropped. `/sys/fs/cgroup/pe-rt4-out` was not. A signed exception for `.../exempt` let that cgroup's connect get `errno 111` (nothing listening). Replacing `Ed25519` with `Ed2551x` in the exception file, then waiting for the one-second sweep, made the same cgroup time out. The real cgroup root was not enrolled. Doing that would have put this agent in the map and dropped its egress on `enp0s3`.

Claim 36: local clients against `127.0.0.1:9443`. Ledger `TLS_EGRESS` / `OBSERVED` lengths included 21 (OpenSSL marker), 22 (GnuTLS marker), 20 (NSS marker). Claim 38: with `VANTIO_GO_TLS_BIN` set, the Go client produced a `TLS_EGRESS` row of 22 bytes. The first loader, started without that variable, did not log a Go attach. Rustls was not attached either. `sudo` `cargo` in the rustls client directory exited because no default toolchain was selected (`rustup default` was not set). A live rustls write was not produced. Claim 39: the uprobe was `SSL_write` in `/lib/x86_64-linux-gnu/libboringssl.so`. That file was a stub built for this test (`SSL_write` returns the length). The call produced a `TLS_EGRESS` row of 24 bytes. It was not upstream BoringSSL.

Claim 40 is the internal packet, not the public site. The pre-opened fd, the passed fd, the depth-9 open, and the post-kill open are ways an enrolled process, or a process after the loader has been killed, reads a file the packet says the kernel control will not let an agent bypass.

### Not present, or not runnable here

| # | Claim | Source | Rating |
| --- | --- | --- | --- |
| 41 | "Spanner WORM write: TARGET_DESIGN — local NDJSON is verified; live cloud write not yet executed." | `docs/product-spec.md` | TARGET_DESIGN_ONLY |
| 42 | A reboot clears bpffs, and enforcement returns only after the loader starts again. | `docs/operations-guide.md`; `docs/product-spec.md` | UNTESTABLE_HERE |
| 43 | "VLAN-tagged (802.1Q / QinQ) egress is parsed so it cannot bypass enforcement." | `docs/operations-guide.md` | UNTESTABLE_HERE |
| 44 | "A production-managed K8s node (GKE/EKS/AKS)" and a live Spanner project are still to be validated. | `docs/product-spec.md` "Still requires cloud infra" | UNTESTABLE_HERE |
| 45 | "`--kill-on-enforce` stays off" unless `VANTIO_PHANTOM_DENY=1` and the flag are both set. | `docs/operations-guide.md` | HOLDS |
| 46 | Scoped mode is the default. Node-wide is a separate flag. | `docs/operations-guide.md`; loader log `SCOPED (drop enrolled)` | HOLDS |

Claim 42 needs a reboot of this VM. That reboot was not performed. Claim 43 needs a VLAN interface. This host has `lo`, `enp0s3`, and `docker0`. Claim 44 needs a managed cluster or a Spanner project. Neither was used. Claim 45: the readers that got `errno 13` were still alive afterward. Claim 46: `--node-wide-enforcement` was not passed, and the ready line said scoped.

The spec also says kernel TLS, QUIC, and a stripped binary are not covered. Those were not sent. The sentence is an exclusion, not a promise that they are covered.

## Not executed

These sentences were not given a rating because the matching command was not run:

- Docker `--enroll-docker-watch` and a container cgroup. `docker0` is down. No container was started.
- Rogue Reconciliation / `BYPASS_INDICATOR`. No Optics process was recording app-layer rows.
- Gate hostname block, redaction, and spend caps. The on-prem Gate process was not started.
- An allow-CIDR boundary in the direction the guide describes, beyond the failed in-range allow in claim 26.
- A packet that reached the TC classifier after `cgroup_skb` had not already dropped it.
- `process_vm_writev` with a valid remote address. The call used here returned `EINVAL`.
- Host-wide enrollment of the real cgroup root.
- Upstream BoringSSL, and a rustls binary.
- Link-local IPv6 as its own case. Global unicast `2001:db8::10` was dropped.

## Repro for every BREAKS and OVERCLAIM

Workloads were uid 65534 or uid 0 inside a cgroup under `/sys/fs/cgroup/pe-rt4`. The secret was `/tmp/pe-rt4/vault/secret`, mode `0644`, text `rt4-secret-marker`. The loader was `target/release/vantio-loader` with `VANTIO_PHANTOM_DENY=1`, `VANTIO_LAB_SCOPE=lab-nonprod`, a lab trust file, a signed loader pin, a signed stop authority, `--enforce --iface lo --enforce-path /tmp/pe-rt4/vault/`. `192.0.2.10/32` and `2001:db8::10/128` were on `lo`. A timeout (`errno` empty) means the connect did not complete in 1.2–1.5 seconds. `errno 111` means the host refused the port.

### 12 — pre-opened fd and passed fd

1. From the unenrolled parent, `open` the secret and read 8 bytes.
2. Move that process into `pe-rt4/leaf`.
3. `read` the same fd again. It returned the rest of the file (`pre=8 post=18`).
4. From the unenrolled parent, `sendmsg` the secret fd with `SCM_RIGHTS` to a socket created before the move.
5. The enrolled process `read` 18 bytes from the received fd.

New `open` calls in that same cgroup still returned `errno 13`.

### 13 — depth 9 file open

1. Enroll `/sys/fs/cgroup/pe-rt4/deep` only. Create `d1` through `d9` under it.
2. Move uid 65534 into `d8` and `open` the secret: `errno 13`.
3. Move uid 65534 into `d9` and `open` the secret: `errno 0`.
4. Repeat with the enrolled directory twelve levels below `pe-rt4`, and the task nine levels below that directory. `open` returned `errno 0`. The connect from that task still timed out.

### 18 and 19 — SIGKILL drops file and exec deny

1. With the loader alive, enrolled uid 65534 `open` returns `errno 13`, and `execve("/bin/sh")` returns `errno 13`.
2. `kill -INT`, `kill -TERM`, and `kill -HUP` the loader. It stays alive. The open stays `errno 13`.
3. `kill -9` the loader.
4. The same open returns `errno 0`. `execve("/bin/sh")` runs.
5. A connect from that cgroup still times out until a later stop detaches `cgroup_skb`.

The open kprobes never loaded (`bpf_override_return` rejected). The exec links were logged as process-only.

### 25 — ingress is not "never drop"

1. Move a root process into the enrolled leaf.
2. Bind and listen on `192.0.2.10:19042`. The process prints `ready`.
3. From outside that cgroup, connect to that port with a 2 second timeout.
4. The connect times out. The accept times out (`result=errno=None`).
5. A connect to the same address with no listener returns `errno 111`.

The loader's status line on that start was `ingress: accept/accept4 observe-only (never drop; enrolled TraceId only)`. The packet was still dropped. `P0_CUSTOMER_PROTECTION_STATE.md` says the ingress truth "does not block inbound connections."

### 26 — CIDR allow did not allow the prefix

1. Start with `--allow-cidr 192.0.2.0/24`. The log says `Allowlisted CIDR range (v4): 192.0.2.0/24`.
2. Put `192.0.2.10/32` and `192.0.3.1/32` on `lo`.
3. From the enrolled cgroup, connect to `192.0.2.10:9` and to `192.0.3.1:9`.
4. Both time out. The ledger has `NETWORK_BLOCK` rows for that pid, `DropPath` `cgroup_skb`, `BytesSevered` 60.

### 29 — proof map skips the nonce

1. With the loader alive, `unlink` and `rename` of `/sys/fs/bpf/vantio_enrolled_cgroups` return `errno 1`. `mount -t bpf` is denied. `BPF_OBJ_GET` of that pin returns `EPERM`.
2. Read `proof_b64` from the stop-authority file used at startup.
3. `BPF_MAP_UPDATE_ELEM` those four native `u64` words into `/sys/fs/bpf/vantio_stop_prf`. Each update returned `rc=0`.
4. `unlink` the enrolled pin. It succeeds.

### 31 — nonce map delete after the loader is gone

1. Stop once with a signed token. A second call returns `STOP_NONCE_REPLAY`.
2. Delete `/run/vantio-stop-nonces`. The second call still returns `STOP_NONCE_REPLAY`.
3. `BPF_MAP_DELETE_ELEM` the FNV-1a key of that nonce in `/sys/fs/bpf/vantio_used_nonce`. After `SIGKILL`, this returned `rc=0`.
4. Call `--authenticated-stop` with the same token. It does not return `STOP_NONCE_REPLAY`. On the run where `cgroup_skb` had survived the kill, the stop was accepted and detached those programs.

### 34 — foreign key ledger

1. Copy a ledger that `python3 scripts/verify_ledger.py` accepts (`ledger-run1.ndjson`, 135 rows).
2. Generate a new Ed25519 key. Restamp each row: SHA-256 of the previous hash plus the canonical body, signature over that digest, `chain_key` set to the new public key.
3. Write a head whose `count` and `final_hash` match, signed by the same key.
4. The verifier prints `ledger-ok rows=135`.

The append, truncation, rollback, and one-byte hash flip of that same file were rejected.

### 37 — Go and rustls are not attached by themselves

1. Start the loader with no `VANTIO_GO_TLS_BIN` and no `VANTIO_RUSTLS_BIN`.
2. The log attaches OpenSSL, GnuTLS, BoringSSL (the stub soname, once that file exists), and NSS. It does not attach Go or rustls.
3. Restart with `VANTIO_GO_TLS_BIN` pointing at a Go binary that calls `crypto/tls.(*Conn).Write`.
4. That run records a `TLS_EGRESS` row of 22 bytes for the Go marker.

The spec lists Go and rustls in the same sentence as the libraries the loader finds by soname. The loader attaches Go and rustls only when those environment variables name a binary.

### 40 — "not agent-bypassable"

The CISO packet says the kernel control's bypass residual is "Requires kernel privileges to disable; not agent-bypassable." The pre-opened fd, the passed fd, and the depth-9 open did not need a kernel exploit. The post-kill open needed the ability to signal the loader, which is more than an ordinary enrolled uid, and it is the case the survival claim says does not work.

## Public versus this tree

The public pages that were fetched do not say the kernel stop is available. They say it is not. The private README maturity table says path protection, host observe, Docker enroll, and Rogue Reconciliation are present. The product spec says local enforcement was live-verified and that the public site still says enforcement is not yet available until a GCP lab pass. This host showed the file and network denies above, and the nine breaks. It is not that GCP pass, and it is not a reboot.
