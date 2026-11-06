# Red team 3 — Phantom Engine snapshot fd7b69f7

Independent break attempt. This run did not treat the product's own lab scripts as the result. The engine under test is the tarball named by the task, not the open-core tree. Product and harness sources were not edited. No pull request was opened.

## What was tested

| Item | Value |
| --- | --- |
| Task commit name | `fd7b69f7d9a7f845b05cca442ce68d18680df7c4` |
| Tarball | `/home/ubuntu/.cursor/projects/agent-repos-vantio-open-core/uploads/pe-fd7b69f7_7df1.tgz` |
| Tarball SHA-256 | `11be070fe8bbc2152ce2f95f8b20838380cbc2f2c35cf353d2123478d045e894` |
| Git object | Not checked. The tarball has no `.git` directory. Files inside name other commits (`b2a4ace`, `eb42f8ab`, `ed1c3281`, `e890c5e0`). This report identifies the tree by the tarball hash. |
| Host | Ubuntu 24.04.5 LTS, kernel `6.12.113+`, boot id `d4c4a104-810e-4c22-91e5-e80354453658` |
| LSM | `capability,landlock,selinux,bpf` (`CONFIG_BPF_LSM=y`, BTF present) |
| Interface used | `enp0s3` (the loader default `eth0` is not present) |
| Toolchain | `rustc 1.101.0-nightly (2d20b42b8 2026-11-04)`, `bpf-linker 0.12.0` |
| Built loader SHA-256 | `7cccfd3a33dbfe7388dca4fa3c098d489b32724640077fcbc419bbfff8ad8884` |
| Built eBPF object SHA-256 | `aebc30749bb0f77fa0c2897f9a0ca64a9e560370e2c0a33c235281f6ba214475` |
| Open-core checkout this file was committed from | `aeb059a78af510a2f9013ac6053afbb79a124af3` at branch creation |

`cargo build -p vantio-loader --release` exited 0. The first start exited 1 with `LOADER_INTEGRITY_REFUSED reason=PIN_ABSENT`. A signed lab pin was then supplied through `VANTIO_LOADER_PIN`. A copy of the loader hash written beside the binary, with the pin variable unset, exited 1 with `LOADER_INTEGRITY_REFUSED reason=SELF_SIDECAR`.

The enforcing process was:

`vantio-loader --enforce --iface enp0s3 --startup-enroll-cgroup /sys/fs/cgroup/pe-in --enforce-path /tmp/pe-secret/ --allow-cidr 10.255.0.0/24 --stop-authority <lab token> --exec-allow /tmp/pe-rt/probe --exec-allow /usr/bin/true`

`VANTIO_PHANTOM_DENY=1`, `VANTIO_LAB_SCOPE=lab-nonprod`, and a trust file whose key id starts with `dev-nonprod-lab-` were set. The trust key was generated for this run and is not in the repo. The enrolled cgroup was `/sys/fs/cgroup/pe-in` only. `--node-wide-enforcement` was not used. After the last signed stop, a UDP datagram from that cgroup to `10.255.1.1:19553` was received by a listener, and `pgrep vantio-loader` found no process. The `clsact` qdisc this run added on `enp0s3` was deleted after `tc filter show` printed no filters.

## How a rating is used

- **HOLDS** means a command in this run produced the outcome the sentence describes.
- **BREAKS** means a command in this run produced the opposite of the sentence.
- **OVERCLAIM** means the wording covers more than this tree does, including a host-wide or "already done" sentence whose code path is narrower or failed here.
- **UNTESTABLE_HERE** names the missing environment or the command that was not run.
- **TARGET_DESIGN_ONLY** means the tree itself labels the behavior as not yet a live result.

A homepage sentence that says a control does not exist, while this tree enforced it, is **BREAKS**. It is an understatement of this tree, not a promise that the code exceeds.

## Claims

The same public sentence is one claim. Each URL that carries it is listed.

### C1. Enforcement is not yet available

Sources, fetched 2026-11-06:

- `https://vantio.ai/` title and body: "Enforcement is not yet available."
- `https://vantio.ai/phantom-engine`: "Enforcement is not yet available. The lab proof does not yet cover child processes."
- `https://vantio.ai/architecture`: "The stop. Enforcement is not yet available."
- `https://vantio.ai/llms.txt`: "Enforcement is not yet available. The lab proof does not yet cover child processes."
- `https://vantio.ai/solutions/your-ai`, `https://vantio.ai/solutions/malicious-ai`, `https://vantio.ai/trust`, `https://vantio.ai/docs`, `https://vantio.ai/docs/compatibility`: the same "not yet available" sentence.

**BREAKS** for this tree on this host. After the signed pin, the loader printed `enforcing — scoped egress drop; file deny; exec deny` and `SCOPED (drop enrolled)`. An enrolled `nobody` UDP send to `10.255.1.1:19553` returned `errno=1` (`Operation not permitted`) and the listener did not get the token. An unenrolled send of `outside-token` did arrive. The public sentence is false as a description of this snapshot. It is not an overclaim. The install page adds a separate download sentence (C12).

### C2. The lab proof does not yet cover child processes

Source: `https://vantio.ai/phantom-engine` and `https://vantio.ai/llms.txt`, quoted in C1.

**UNTESTABLE_HERE.** Needs the lab record those pages say is not published. This VM is not that record. A related code result is C44: a child that stayed in the enrolled cgroup did not deliver a UDP token. That does not certify or refute their lab packet.

### C3. Optics does not stop the call

Source: `https://vantio.ai/` : "Optics records the program, 203.0.113.50, the time, the size, and a trace id. That address is outside authority, so the first connection is flagged. Optics does not stop the call."

**UNTESTABLE_HERE.** The Optics CLI was not installed or invoked. The loader tested here is a different program, and it did stop enrolled sends.

### C4. Optics stores the destination, process, time, size, and trace id, and does not store prompts

Source: `https://vantio.ai/optics`: "Prompts and completions are never stored." and "It sees the connection, not the conversation."

**UNTESTABLE_HERE** for the Optics CLI, which was not run. The loader ledger result is C40.

### C5. Phantom Engine needs nothing from the AI

Source: `https://vantio.ai/phantom-engine`: "What it needs from the AI. Nothing. No proxy, no SDK, no prompt."

**HOLDS.** The probe was a static C program with no SDK and no prompt. Enrolled calls were still denied (C19, C16, C36).

### C6. A person signs Enterprise changes, and that governance is in progress

Source: `https://vantio.ai/enterprise`: "Enterprise is designed for your security team to hold and sign the rules that govern Phantom Engine, so AI can't grant itself permission or grant it to another AI. Enterprise governance of Phantom Engine is in progress; it has passed only in Vantio's own lab." Also: "It has passed only in Vantio's own lab, so it is not yet available on your systems."

**HOLDS** as that status sentence. The page says the control is in progress. This loader has no production root. `active_dev_trust()` returns empty unless `VANTIO_LAB_SCOPE=lab-nonprod` and `VANTIO_LAB_DEV_TRUST` points at a file this operator wrote. A key generated for this run was accepted. An unsigned policy was not applied (C37). That is a lab trust the operator supplies, which matches the page's "not yet available on your systems."

### C7. Applications reach only destinations a person approved

Source: `https://vantio.ai/solutions`: "Applications that hold real credentials reach only the destinations a person approved."

**OVERCLAIM.** The code drops traffic for an enrolled cgroup. The same host, from `/sys/fs/cgroup/pe-out`, delivered `outside-token` to `10.255.1.1`, which was not on the allow list. The sentence has no enrolled-cgroup limit. A sibling bullet on the same site says enforcement is not yet available (C1).

### C8. Contain AI wherever it runs on Linux

Source: `https://vantio.ai/solutions`: "Wherever AI runs on Linux, contain it."

**OVERCLAIM.** Containment in this run was the enrolled cgroup plus the loader's own program protection. An unenrolled process was not contained. Root inside the enrolled cgroup read the enforce-path file (C17). A hard link outside the path prefix was readable by `nobody` (C18).

### C9. The model file does not add a destination

Source: `https://vantio.ai/solutions/malicious-ai`: "A person holds the allowlist. The model file does not get to add a destination." The same page also says "Enforcement is not yet available."

**HOLDS** for the mechanism on this tree. Root `BPF_MAP_UPDATE_ELEM` on `/sys/fs/bpf/vantio_cgroup_exceptions` returned `errno=1`. An enrolled sender did not reach `10.255.1.1`. No model file was loaded. The sentence is about the map and the allow list, which is what was tested.

### C10. The stop stays on the Linux system

Source: `https://vantio.ai/trust`: "The stop stays on the Linux system. The control runs on the Linux servers you operate."

**HOLDS** for this boot until a signed stop. `SIGTERM`, `SIGINT`, and `SIGHUP` logged `unauthenticated stop refused` and the enrolled UDP token still did not arrive. After `SIGKILL`, an enrolled UDP send still returned `errno=1`. A later signed stop logged `authenticated stop accepted`, and a following send from the same cgroup was received.

### C11. Phantom Engine is self-installed on Ubuntu 24.04

Source: `https://vantio.ai/docs/install/phantom-engine`: "Phantom Engine is self-installed on Ubuntu 24.04 LTS x86_64. Enforcement is not yet available."

**HOLDS** for this userspace: Ubuntu 24.04.5, x86_64, and a source build enforced. This kernel is `6.12.113+`, not a stock Ubuntu 24.04 kernel. The "enforcement is not yet available" half is C1.

### C12. The sealed bundle is not a public download yet

Source: `https://vantio.ai/llms.txt`: "The sealed bundle has no public download yet." Install page: "Until the release is configured, that answer is that downloads are not live yet. No download command is invented here."

**UNTESTABLE_HERE** for a licensed fetch. An unauthenticated `GET https://vantio.ai/api/pe/download` on 2026-11-06 returned HTTP 401 and `{"ok":false,"error":"A license token is required."}`. That is not the page's "downloads are not live" sentence. No license was presented. Needs a real license token, which this run did not have and did not invent.

### C13. Phantom Engine has no public self-serve price

Source: `https://vantio.ai/pricing`: "What does Phantom Engine cost? Phantom Engine is Contact Vantio." `https://vantio.ai/llms.txt`: "Phantom Engine is Contact Vantio."

**HOLDS** as the text of those pages. The tarball README contains an internal price table and says it is not a website change. The figures are not copied here.

### C14. Your AI and malicious AI meet the same boundary

Source: `https://vantio.ai/`: "Your own AI acting on its own and malicious AI coming in from outside meet the same boundary, because it sits on the Linux system."

**HOLDS** for the path that was run. One enrolled cgroup, one allow CIDR, and one file prefix were applied to the probe with no separate "own AI" versus "malicious AI" switch. A poisoned-model load was not executed.

### C15. Forbidden paths fail on the host

Source: tarball `README.md` maturity table: "Path protection on `enforce_paths` (`drill absolute`) | Present — forbidden paths fail on the host."

**BREAKS.** Enrolled `nobody` opening `/tmp/pe-secret/file` got `errno=13`. The same file was read (17 bytes) by enrolled root, by `nobody` outside the cgroup, and by enrolled `nobody` through a hard link (C18). The product spec already narrows this (C16, C17). The README row does not.

### C16. An enrolled non-root open of an enforce path fails

Source: tarball `docs/product-spec.md`: exec and file text, and `docs/P0_CUSTOMER_PROTECTION_STATE.md`: "lsm_bprm_check (and lsm_bprm_creds when the hook loads) can return EACCES for an enrolled non-root lineage." File open is the LSM `file_open` program. The enforce path in this run was `/tmp/pe-secret/` plus the compiled defaults.

**HOLDS.** Enrolled `nobody` `open("/tmp/pe-secret/file")` returned `errno=13`. The file mode was `0644`. Enrolled `nobody` opening `/tmp/pe-secret/../pe-secret/file` also returned `errno=13`. `/etc/passwd` was readable (`read_n=32`).

### C17. Real uid 0 is spared on the file path unless a file ceiling is already stored

Source: tarball `architecture_state.md`: "The kprobe path still skips uid 0." `vantio-common` `open_deny_decision` returns deny for uid 0 only when the file ceiling bit is set.

**HOLDS.** Enrolled root `open("/tmp/pe-secret/file")` returned `read_n=17`. Root had not called `setuid` before that open.

### C18. Hard-link and symlink attaches refuse exfiltration of an enforce path

Source: tarball `architecture_state.md`: "Link/symlink-family attaches refuse hard-link exfil and symlink plant on the same enforce strings."

**BREAKS** on this kernel.

The loader log said these programs failed the verifier and were not attached: `link old`, `link new`, `linkat old`, `linkat new`, `symlink target`, `symlink linkpath`, `symlinkat target`, `symlinkat linkpath`. The log's own words: "residual coverage gap; glibc/python open/openat still covered."

Repro, loader up, enforce path `/tmp/pe-secret/`:

1. Before start, `link /tmp/pe-secret/file /tmp/pe-secret-hardlink` and `symlink /tmp/pe-secret/file /tmp/pe-secret-link`.
2. Enrolled `nobody` open of `/tmp/pe-secret/file` returned `errno=13`.
3. Enrolled `nobody` open of `/tmp/pe-secret-hardlink` returned `read_n=17` (`rt-secret-marker`).
4. With the loader still up, enrolled root `link("/tmp/pe-secret/file", "/tmp/armed-hard")` returned `errno=0`.
5. Enrolled `nobody` open of `/tmp/armed-hard` returned `read_n=17`.

The symlink path returned `errno=13`. The hard link did not. `lsm_inode_link` was logged as attached and still did not stop root's `link()`.

### C19. Scoped enforcement drops enrolled egress and passes everyone else

Source: tarball `docs/product-spec.md`: "TC egress classifier scoped per-agent: drops traffic to non-allowlisted destinations (`TC_ACT_SHOT`) only for enrolled cgroups." `architecture_state.md` says an empty enrolled set drops nothing.

**HOLDS.** Allow CIDR `10.255.0.0/24`. Enrolled `nobody` to `10.255.0.1:19553` delivered `allow-token`. Enrolled `nobody` to `10.255.1.1:19553` returned `errno=1` and `deny-token` did not arrive. Unenrolled root to `10.255.1.1` delivered `outside-token`. The loader was not started with `--node-wide-enforcement`.

### C20. CIDR allow lists use prefix length

Source: tarball `docs/product-spec.md`: "CIDR-range allowlist (`LpmTrie`) — verified live with exact prefix-boundary precision." `docs/operations-guide.md` describes longest-prefix match.

**HOLDS** for this pair. `10.255.0.1` is inside `10.255.0.0/24` and arrived. `10.255.1.1` is outside that prefix and did not arrive. Both addresses were added on `lo` with `/32`.

### C21. Scoped mode does not auto-allow private or loopback destinations

Source: tarball `docs/operations-guide.md`: "Scoped enforcement does not auto-allow RFC-1918 or IPv6 ULA for an enrolled sender." `private_dest_passes` is false when the mode is scoped.

**HOLDS.** Enrolled root UDP to `127.0.0.1:19553` returned `errno=1`. The token did not arrive.

### C22. IPv6 from an enrolled sender is covered

Source: tarball `README.md`: "Enforcement covers both IPv4 and IPv6, so an agent cannot escape a drop policy by resolving an AAAA record."

**HOLDS** for the addresses that were sent. Enrolled root UDP to `fd00::255` and to `::1` on port 19553 both returned `errno=1`, and neither token arrived. A global IPv6 destination was not sent. Link-local `fe80::/10` is a pass in the source and was not sent.

### C23. DNS from an enrolled sender does not get an answer

Source: the task's DNS case, against the egress claim in C19. The tree does not special-case port 53. A UDP send to a resolver is an ordinary datagram.

**HOLDS.** Enrolled `nobody` DNS to `8.8.8.8:53` returned `errno=1`. Enrolled `nobody` DNS to `127.0.0.53:53` returned `errno=1`. Unenrolled root DNS to `8.8.8.8:53` printed `dns_reply=61`.

### C24. ICMP from an enrolled sender is denied

**HOLDS.** Enrolled root ICMP echo to `127.0.0.1` and to `1.1.1.1` both returned `errno=1` from `socket(AF_INET, SOCK_DGRAM, IPPROTO_ICMP)` or the raw fallback.

### C25. A raw IPv4 UDP send from an enrolled sender does not arrive

**HOLDS.** Enrolled root `SOCK_RAW` / `IPPROTO_UDP` with `IP_HDRINCL` toward `10.255.1.1:19553` returned `errno=1`. `raw-token` did not arrive.

### C26. AF_PACKET is denied for an enrolled task

Source: `lsm_socket_create` returns `-1` when the family is 17 and the task cgroup is enrolled.

**HOLDS.** Enrolled root `socket(AF_PACKET, SOCK_RAW, ETH_P_ALL)` returned `errno=1`.

### C27. An enrolled task cannot use AF_UNIX to an unenrolled peer

Source: tarball `docs/product-spec.md`: "An enrolled task cannot connect or send on `AF_UNIX` to an unenrolled peer unless that peer's cgroup is on the signed unix allowlist."

**HOLDS.** No unix allow file was passed. Enrolled `nobody` `connect` on a stream socket to `/tmp/pe-rt/outside.sock` returned `errno=13`. The datagram connect returned `errno=1`. The outside listener's buffer stayed empty.

### C28. Ingress to an enrolled cgroup is dropped, and a listener outside still accepts

Source: tarball `docs/product-spec.md`: "Ingress to an enrolled cgroup is dropped and recorded as `NETWORK_BLOCK`. A listener outside an enrolled cgroup still accepts."

**HOLDS.** A Python listener moved into `/sys/fs/cgroup/pe-in` and bound `0.0.0.0:19555` printed `ingress-timeout`. A connect from outside to `127.0.0.1:19555` timed out. A listener left outside, on port 19556, accepted. The loader also logged `BLOCKED cgroup 3189`, which is the inode of `/sys/fs/cgroup/pe-in`.

### C29. Root detach, link detach, map update, and bpffs unlink or rename are denied

Source: tarball `docs/product-spec.md`: "Root program detach, link detach, map update, and bpffs unlink or rename of Vantio objects are denied unless the caller is the loader."

**HOLDS** for those operations. The loader's own line was `root resistance canary: detach errno 1, map update errno 1, link detach errno 1, unlink errno 1, rename errno 1, ptrace errno 1, vm errno 1, mem errno 13, pidfd_getfd errno 1, stolen update errno 1, pin_remains=true, links_held=true`. An independent root probe then got `errno=1` for unlink, rename, map update, link detach, and lookup of `/sys/fs/bpf/vantio_stop_sec`.

`umount2("/sys/fs/bpf", MNT_DETACH)` returned 0 while the loader was alive. The next enrolled UDP send still returned `errno=1`. Umount removed the pin names from the mount and did not remove the drop. It is not a successful detach.

### C30. A new bpf mount is denied

Source: `lsm_sb_mount` returns `-1` when the type word is `bpf`.

**HOLDS.** Root `mount("bpf", "/tmp/pe-rt/bpf-mnt", "bpf", 0, NULL)` from the enrolled cgroup returned `errno=1`.

### C31. SIGINT, SIGTERM, and SIGHUP do not detach

Source: tarball `docs/product-spec.md`: "SIGINT, SIGTERM, and SIGHUP do not detach those programs. A signed stop token does."

**HOLDS.** Each signal left the loader alive (`poll` still none). The log printed `unauthenticated stop refused signal=SIGTERM`, then `SIGINT`, then `SIGHUP`. After each signal an enrolled UDP token did not arrive.

### C32. SIGKILL does not remove the drop

Source: tarball `architecture_state.md`: "SIGINT, SIGTERM, SIGHUP, and SIGKILL do not remove a successful pin."

**HOLDS** for the drop. `kill -9` of the loader was followed by an enrolled UDP send that still returned `errno=1` and did not arrive. The pin directory had already been lazily unmounted, so this run does not show a pin file surviving `SIGKILL` on a still-mounted bpffs. The drop survived the signal.

The same log line says exec deny did not get a second pin: "lsm_bprm_check stays attached in this process only ... A kill drops exec deny." `/bin/sh` was not executed again after `SIGKILL`. That half was not re-tested.

### C33. A signed stop token detaches, and a bad signature does not

**HOLDS.** A token whose `action` string was altered returned `authenticated stop refused reason=SIGNATURE_INVALID` and the loader stayed up. After the nonce file was emptied, the original token printed `authenticated stop accepted` and the process exited. A following UDP send from the enrolled cgroup was received.

### C34. A repeated stop nonce is refused while the nonce file still lists it

Source: `authenticated_stop.rs` `commit_nonce` returns `STOP_NONCE_REPLAY` when the nonce is already in `/run/vantio-stop-nonces`.

**HOLDS** for that state. A second `vantio-loader --authenticated-stop --stop-token` of the same file, while the file still contained `redteam-nonce-1`, returned `reason=refused STOP_NONCE_REPLAY`. The loader stayed up.

### C35. Root cannot reuse a stop token by editing the nonce file

**BREAKS.** Root `Path.write_text("")` on `/run/vantio-stop-nonces` succeeded. The same token then printed `authenticated stop accepted`. `unlink` and `rename` of that file returned `errno=1` because the dentry name starts with `vantio` and `unlink_target_is_pin` treats the name alone as a pin. The replay store can be emptied without being unlinked.

### C36. Exec deny is enrolled, non-root, and allowlist-based

Source: tarball `docs/product-spec.md`: "Without `--exec-preset` or `--exec-allow`, exec stays observe-only. Uid 0, an unenrolled task, and a host with no exec policy are not denied." With an allow list and `--enforce`, an enrolled non-root exec that misses the path and the inode is denied.

**HOLDS** on this boot. This is not a new-boot lab pass. The spec says that pass is not recorded. Enrolled `nobody` `execve("/bin/sh")` returned `errno=13` and the log said `DENIED pid ... execve /bin/sh`. Enrolled `nobody` `execve("/usr/bin/true")` replaced the process (exit 0, no error line). Enrolled root `execve("/bin/true")` also replaced the process. `/usr/bin/true` and the probe path were the allow list.

### C37. An unsigned policy does not replace the compiled paths

Source: tarball `architecture_state.md`: "An unsigned file does not replace compiled defaults or activate a grant."

**HOLDS.** `VANTIO_POLICY_PATH` pointed at a JSON object with no signature. The log said `VANTIO_POLICY_PATH is not a verified dev-signed policy. Unsigned contents were not applied.` and `enterprise widen was not applied (SIGNATURE_MISSING)`. The enforce path still denied enrolled `nobody`.

### C38. The loader will not start on a self-hash or on no pin

Source: `loader_integrity.rs`: a sidecar whose hash matches the file is `SELF_SIDECAR`. No pin is `PIN_ABSENT`.

**HOLDS.** First start, no pin: exit 1, `PIN_ABSENT`. Sidecar file `loader.sha256` next to the binary and `VANTIO_LOADER_PIN` unset: exit 1, `SELF_SIDECAR`. Start with a lab-signed `loader.pin.json` whose `sha256` was the loader digest: the process reached `SCOPED (drop enrolled)`.

### C39. An appended ledger line that the loader did not sign fails verification

Source: tarball `scripts/verify_ledger.py` docstring: "An appended line that was not produced by the loader fails." `ledger_chain.rs`: "An appended line that was not signed by this key fails."

**BREAKS.** `python3 scripts/verify_ledger.py` on a two-row chain signed by one Ed25519 key exited 0 (`ledger-ok rows=2`). The same file with one payload byte changed exited 1 (`row 2: hash chain broken`). Appending a third row signed by a different key, with `chain_prev` of 32 zero bytes, exited 0 (`ledger-ok rows=3`). A file containing only the first row exited 0. A file containing only an attacker-signed row with a zero `chain_prev` exited 0. The verifier resets the chain whenever `chain_prev` is 32 zero bytes and adopts `chain_key` from that row. A loader restart does the same thing, because `Chain::generate()` creates a new key. The verifier cannot tell those apart.

### C40. A mutated chain fails, and TLS marker bytes are not written into the ledger

Source: product spec observe section, and the public "prompts and completions are never stored" sentence as it would apply to this ledger.

**HOLDS** for what was checked. The mutated row failed (C39). The strings `openssl-marker-21b!!!`, `gnutls-marker-22bytes!`, `nss-marker-20-bytes!`, `go-tls-marker-22bytes!`, `rustls-marker-22bytes!`, and `rt-secret-marker` were absent from `live2.ndjson`. The ledger does store path strings. Rows included `Payload` `/etc/passwd` and `/etc/shadow` for `SYSCALL_OPENAT`. Those are path names, not file bytes and not the TLS markers.

`NETWORK_BLOCK` rows in the first ledger had `BytesObserved` 0 and `BytesSevered` set (28, 36, 37, 38, 39, 40, 41, 56, 57, 58, 60). This run did not capture the frame on the wire, so it does not prove those integers include the IP and transport headers. The field split matches the loader's blocked-row shape.

### C41. OpenSSL, GnuTLS, NSS, rustls, and Go crypto/tls writes are observed by length

Source: tarball `docs/product-spec.md` and `vantio-loader/src/tls_stacks.rs` `COVERAGE_SENTENCE`: uprobes on OpenSSL `SSL_write` and `SSL_write_ex`, BoringSSL `SSL_write` in `libboringssl.so`, GnuTLS `gnutls_record_send`, NSS `PR_Write`, rustls `Writer::write` when the symbol is present, and Go `crypto/tls.(*Conn).Write`.

**HOLDS** for the five stacks that were attached and written. The loader log said `watching TLS: openssl, gnutls, nss, rustls, go`. Local clients against `127.0.0.1:9443`, outside the enrolled cgroup:

| Client | Exit | Ledger |
| --- | --- | --- |
| `openssl-client` marker length 21 | 0 | `TLS_EGRESS` `OBSERVED` `BytesObserved` 21, pid 11460 |
| `gnutls-client` marker length 22 | 0 | `TLS_EGRESS` `BytesObserved` 22, pid 11464 |
| `nss-client` marker length 20 | 0 | `TLS_EGRESS` `BytesObserved` 20, pid 11467 |
| `rustls-client` marker length 22 | 0 | `TLS_EGRESS` `BytesObserved` 22 twice, pid 11475. The log also said the program was already loaded and then attached to the rustls `Writer::write` symbol. |
| `go-tls` marker length 22, invoked as `127.0.0.1:9443` | 0 | `TLS_EGRESS` `BytesObserved` 22, pid 11653, in `live-go.ndjson`. An earlier invocation passed the port as a second argument and exited 4 before any write. The symbol `crypto/tls.(*Conn).Write` was present in that binary and the loader logged the attach. |

### C42. BoringSSL `SSL_write` in `libboringssl.so`

**UNTESTABLE_HERE.** Needs `libboringssl.so` on the host. The loader logged `SSL_write uprobe skipped — none of ["libboringssl.so"] found`. It was not built in this run.

### C43. Kernel TLS, QUIC, and a stripped binary are outside TLS coverage

Source: the same coverage sentence: "Kernel TLS, QUIC, and statically stripped binaries are not covered."

**UNTESTABLE_HERE.** A kTLS sender, a QUIC sender, and a stripped binary were not built. The sentence is the tree's own exclusion. This run does not show those paths.

### C44. A forked child in the enrolled cgroup does not get a quiet send

Source: tarball `README.md`: "Fork inheritance — on enrolled hosts, child processes inherit TraceId." The public lab-proof sentence is C2. The code claim tested here is the send, not the trace id.

**HOLDS** for the send. `fork` then child UDP of `fork-token` to `10.255.1.1` did not arrive. The parent probe returned `errno=5` because the child exited non-zero. The trace map was not dumped, so trace-id inheritance was not shown.

### C45. A move out of the enrolled cgroup keeps the deny ceiling

Source: loader log and `architecture_state.md`: "A task that leaves an enrolled cgroup keeps its deny ceiling." The startup log said `lineage cgroup-move attached: cgroup_attach_task`.

Not rated **HOLDS**. Enrolled root wrote the out cgroup and then sent `move-token` and `move2-token`. Both sends returned `errno=1` and neither token arrived. `/proc/self/cgroup` after the write was not recorded, so a failed write and a ceiling that survived a successful move are not separated.

`clone3` with `CLONE_INTO_CGROUP` into `/sys/fs/cgroup/pe-out` printed `clone_pid=9973` and `clone_status=11` (signal 11). The child crashed. That is not a policy result.

### C46. A new network namespace does not deliver a loopback datagram

**HOLDS** as a non-delivery, not as a clean errno. Enrolled root `unshare(CLONE_NEWNET)`, brought `lo` up, bound `127.0.0.1:19559`, and sent `ns-token`. `recv` returned -1 with `errno=11`. The host listener is in a different netns, so it was not the oracle. The token did not come back inside the new netns. A veth from the new netns to the host was not built.

### C47. Ptrace of the loader is denied, and ptrace of another process is not

Source: `lsm_ptrace` returns `-1` only when the target tgid is the loader. The comment in `main.rs` says root `ptrace`, `process_vm_writev`, `/proc/<pid>/mem`, and `pidfd_getfd` of the loader are denied.

**HOLDS.** Enrolled root `ptrace` of the loader returned `errno=1`, `/proc/<loader>/mem` returned `errno=13`, and `process_vm_writev` returned `errno=1`. Enrolled root `ptrace` of a `sleep` process returned 0. The host is not covered by that hook. That is what the source says. It is part of why C8 is an overclaim.

### C48. Spanner live write

Source: tarball `docs/product-spec.md`: "Spanner WORM write: TARGET_DESIGN — local NDJSON is verified; live cloud write not yet executed."

**TARGET_DESIGN_ONLY.** No GCP project was used. Local verification is C39 and C40, and C39 breaks the "any appended line fails" sentence.

### C49. Managed Kubernetes, VLAN or QinQ on a trunk, and a reboot clearing bpffs

Source: tarball `docs/product-spec.md` and `architecture_state.md`. Managed clusters and a reboot are named as not proven on the agent VM. VLAN parsing is described in code.

**UNTESTABLE_HERE.**

- Managed Kubernetes needs a GKE, EKS, or AKS node. No cluster was created.
- VLAN or QinQ needs a tagged interface. None was configured. The parser was not fed a tagged frame.
- A reboot needs a host that can reboot without ending this run. `SIGKILL` and bpffs umount were tested instead (C29, C32). They are not a reboot.

### C50. Everything that does not need a cloud account is already verified

Source: tarball `docs/product-spec.md`: "Remaining work is cloud-account-gated, not engineering-gated — everything achievable without external infrastructure has been built and locally verified."

**OVERCLAIM.** This host has BPF LSM and no cloud account. On it, 19 kprobes failed the verifier (C18), a hard link outside the prefix was readable (C18), and the ledger verifier accepted an attacker chain (C39). Those are local.

### C51. Docker cgroup enrollment is present

Source: tarball `README.md` maturity table: "Docker cgroup enroll + TGID | Present."

**UNTESTABLE_HERE.** `docker0` existed and was `DOWN`. No container was started. Needs a running container daemon and a container in a cgroup the loader enrolls.

### C52. Rogue Reconciliation is present

Source: tarball `README.md`: "Rogue Reconciliation / BYPASS_INDICATOR | Present" and the workflow that correlates an app trace with a host send.

**UNTESTABLE_HERE** in the sense that it was not executed. `scripts/demo_bypass_reconciliation.sh` was not run. No app-layer Optics record was produced in this pass. The script does not need a cloud account. This report does not treat an unread script as a result.

### C53. A deny does not kill the caller unless kill-on-enforce is set

Source: tarball `README.md`: "Emergency process kill (`--kill-on-enforce`) | Present · off by default · needs a person."

**HOLDS.** `--kill-on-enforce` was not passed. Denied probes returned an errno and kept running. A same-user kill test was not valid: `runuser -u nobody -- sleep` left the recorded pid at uid 0, so `nobody`'s `kill` returning `errno=1` is the ordinary permission check. No signal hook was shown by that test.

## Counts

| Rating | Count | Claims |
| --- | --- | --- |
| HOLDS | 34 | C5 C6 C9 C10 C11 C13 C14 C16 C17 C19 C20 C21 C22 C23 C24 C25 C26 C27 C28 C29 C30 C31 C32 C33 C34 C36 C37 C38 C40 C41 C44 C46 C47 C53 |
| BREAKS | 5 | C1 C15 C18 C35 C39 |
| OVERCLAIM | 3 | C7 C8 C50 |
| UNTESTABLE_HERE | 9 | C2 C3 C4 C12 C42 C43 C49 C51 C52 |
| TARGET_DESIGN_ONLY | 1 | C48 |
| Not rated | 1 | C45, the cgroup-move ceiling. The send failed and the cgroup after the write was not recorded. |

C1 is BREAKS because the sentence is false for this tree. It is an understatement, not a promise that the code does more than it does. C32 is HOLDS for the drop after `SIGKILL`. The log's statement that exec deny dies with the process was not re-tested. Rated claims are 34+5+3+9+1 = 52, plus C45.

## Every BREAKS and OVERCLAIM, with the repro

### C1 BREAKS — "Enforcement is not yet available"

The homepage, `/phantom-engine`, `/architecture`, and `llms.txt` say that. This tree enforced.

1. Build `vantio-loader` from the tarball with nightly `2026-11-05` and `bpf-linker 0.12.0`.
2. Sign a lab pin and a stop token. Set `VANTIO_LAB_SCOPE=lab-nonprod`, `VANTIO_LAB_DEV_TRUST`, `VANTIO_LOADER_PIN`, `VANTIO_PHANTOM_DENY=1`.
3. Start with `--enforce --iface enp0s3 --startup-enroll-cgroup /sys/fs/cgroup/pe-in --allow-cidr 10.255.0.0/24`.
4. From that cgroup, send UDP to `10.255.1.1`. Result here: `errno=1`, token absent. From another cgroup, the same address delivered the token.

### C15 BREAKS — "forbidden paths fail on the host"

README maturity row for `enforce_paths`.

1. Create `/tmp/pe-secret/file` mode `0644`.
2. Start as in C1 with `--enforce-path /tmp/pe-secret/`.
3. Enrolled `nobody` open returns 13.
4. Enrolled root open returns the 17 bytes.
5. `nobody` in `/sys/fs/cgroup/pe-out` open returns the 17 bytes.

### C18 BREAKS — hard-link exfil

1. `ln /tmp/pe-secret/file /tmp/pe-secret-hardlink` before the loader starts.
2. Start as in C15.
3. Enrolled `nobody` reads `/tmp/pe-secret-hardlink` (17 bytes) while `/tmp/pe-secret/file` returns 13.
4. While the loader is up, root in the cgroup `link()`s the file to `/tmp/armed-hard` (return 0). Enrolled `nobody` reads that name too.
5. The loader log lists `link old`, `link new`, `linkat old`, `linkat new`, and the four symlink attaches as verifier failures.

### C35 BREAKS — stop-token replay after the nonce file is emptied

1. Start with a stop token whose nonce is `redteam-nonce-1`.
2. Call `--authenticated-stop` once so `/run/vantio-stop-nonces` contains that nonce. A second call returns `STOP_NONCE_REPLAY` and the process stays up.
3. As root, open `/run/vantio-stop-nonces` and write an empty file. `unlink` and `rename` return `errno=1`. The write succeeds.
4. Call `--authenticated-stop` with the same token. Result here: `authenticated stop accepted`.

### C39 BREAKS — ledger append

From the tarball root:

1. Build two NDJSON rows with `chain_prev`, `chain_hash`, `chain_sig`, and `chain_key` the way `scripts/verify_ledger.py` describes. Sign them with one Ed25519 key. `python3 scripts/verify_ledger.py` exits 0.
2. Change a payload byte. The script exits 1, `hash chain broken`.
3. Append a row signed by another key with `chain_prev` of 32 zero bytes. The script exits 0, `ledger-ok rows=3`.
4. A file that is only that attacker row also exits 0.

### C7 OVERCLAIM — only approved destinations

`https://vantio.ai/solutions` says applications reach only destinations a person approved. Repro is the unenrolled half of C19: `outside-token` to `10.255.1.1` arrived while that address was not in `10.255.0.0/24`.

### C8 OVERCLAIM — contain AI wherever it runs

Same page: "Wherever AI runs on Linux, contain it." The unenrolled send in C19 arrived. The hard link in C18 was readable inside the enrolled cgroup. Root ptrace of a `sleep` process returned 0 (C47).

### C50 OVERCLAIM — local work is already verified

`docs/product-spec.md` says remaining work is only cloud-account-gated. This host has no cloud account and has BPF LSM. C18 and C39 failed here, and 19 kprobes did not load.

## Commands and exits

| Command | Exit | What it showed |
| --- | --- | --- |
| `cargo build -p vantio-loader --release` | 0 | Loader and embedded eBPF object built |
| Loader start with no pin | 1 | `PIN_ABSENT` |
| Loader start with a matching sidecar and no signed pin | 1 | `SELF_SIDECAR` |
| Loader start with signed pin, lab trust, `--enforce` | 0 (process stayed up) | `SCOPED (drop enrolled)`, canary errnos 1 and 13 |
| Enrolled UDP to `10.255.1.1` | probe exit 1 | `errno=1`, token absent |
| Unenrolled UDP to `10.255.1.1` | probe exit 0 | token arrived |
| Enrolled UDP to `10.255.0.1` | probe exit 0 | token arrived |
| `verify_ledger.py` good chain | 0 | `ledger-ok rows=2` |
| `verify_ledger.py` mutated row | 1 | `hash chain broken` |
| `verify_ledger.py` attacker append | 0 | `ledger-ok rows=3` |
| `GET https://vantio.ai/api/pe/download` with no license | HTTP 401 | `A license token is required.` |
| `--authenticated-stop` with a damaged token | 1 | `SIGNATURE_INVALID`, process stayed |
| `--authenticated-stop` with a used nonce | 1 | `STOP_NONCE_REPLAY`, process stayed |
| `--authenticated-stop` after the nonce file was emptied | 0 | `authenticated stop accepted` |

## What only another environment can show

- A new boot, and whether bpffs pins are gone after that boot. This boot id did not change.
- A stock Ubuntu 24.04 kernel. This kernel is `6.12.113+`.
- `libboringssl.so` for the BoringSSL uprobe.
- A kTLS client, a QUIC client, and a stripped TLS binary.
- A VLAN or QinQ trunk.
- A managed Kubernetes node, and a Docker daemon with a running container.
- A licensed download from `https://vantio.ai/api/pe/download`.
- A live Spanner write.
- The Optics CLI. It was not run.
- `scripts/demo_bypass_reconciliation.sh`. It was not run.
- Whether a cgroup move that is proven by `/proc/self/cgroup` still drops. The send failed, and the membership after the write was not recorded.
- Whether exec deny survives `SIGKILL`. The loader said a kill drops it, and `/bin/sh` was not retried after the signal.
