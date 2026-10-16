# T5 — side-channel and egress drills

Audience: INTERNAL_RESTRICTED

Track: T5 of the market-readiness gap program

Repository: `vantioai/vantio-open-core`

Base commit this design was written against: `69671e97fa359b685232ec7dd4e9fb4badc7be57`

Branch: `gap/t5-egress-drills`

Date: 2026-10-16

Revision: council pass 2, after `NEEDS_REVISION` on the first packet

Producer classification: `T5_EGRESS_DRILL_DESIGN_READY_FOR_COUNCIL`

This document is the phase-1 design. It contains no product claim that the kernel path is loaded. The local drills that follow this design are labeled **Lab-only**. Kernel attachment is labeled **Roadmap**.

## 1. Threat model

Phantom Engine covers supported AI workloads on enrolled Linux machines. This track hardens the egress and side-channel surface those workloads can use to leave the machine or to reach a host service they were not granted.

Actors:

- An enrolled workload that is buggy or hostile and tries to move data out, or to reach a host-only service.
- A process on the same host that is not enrolled. It is outside the attach scope. This track does not govern it.

Actions in scope:

| Case | What the workload does | Why it matters |
| --- | --- | --- |
| DNS allow-list | Queries a name that is not on the operator list, or asks a resolver that is not on the list | Ordinary DNS is an egress channel |
| Long label | Puts a long label, or several labels whose combined length is long, under an allowed suffix | DNS tunnel carrying encoded bytes |
| High-entropy label | Puts a compressed or encoded left-hand name under an allowed suffix | Same tunnel, when each label stays under the length cap |
| Query volume | Sends more queries in a short window than the policy allows | Burst tunnel and resolver abuse |
| Unknown delegation | Follows an NS or glue address that is not on the resolver list | Redirect via a resolver the operator did not name |
| ICMP | Sends ICMP to a destination that is not on the ICMP list, or sends a non-echo type | ICMP tunnel and a path that TCP allow-lists do not see |
| GET write | Sends a GET whose query or body carries a write to an external host | A method list that permits GET still leaks or mutates |
| Loopback privilege | Connects to a loopback-class address on a port that can control the host | Reaches a local admin listener from the workload |
| Symlink escape | Opens a path that resolves outside the workload directory through a symlink, a magic link, a bind mount, or `..` | Reads or writes host files from a granted directory |

Out of scope for this track, and left unchanged: prompt or answer scoring, content moderation, model evaluation, an identity provider, generic antivirus, a WAF, DDoS protection, and robotic physical safety. This track does not store conversation content. A drill evidence file stores action tokens, reason tokens, lengths, counters, and a SHA-256 of synthetic drill bytes that would have been sent or opened. Those bytes are the fixture, not a customer request. A later production wiring must not store an unkeyed hash of a real request body: a low-entropy body can be guessed and checked against the hash (R-T5-21). It does not store prompts, completions, HTTP bodies, query strings, qnames, paths, or packet payloads. The proof file also stores `policy_sha256`, the SHA-256 of the policy file bytes, so the policy is identified without copying it into the evidence body.

Product boundary used here, checked against the open-core tree and the 2026-07-01 tier notes in the workspace rule:

- Tier 1 observe wraps `globalThis.fetch` with `NODE_OPTIONS=--require`. It is not an AST rewrite.
- SDK-side enforcement is the v1 architecture. A proxy hop is not required, and this track does not add one.
- Tier 3 kernel acceptance and `SSL_write` / `gnutls_record_send` uprobe observation were recorded on a privileged WSL2 host. They are not recorded here as cluster-verified. cgroup-scoped enforcement, TC drop, Kubernetes `--enroll-watch`, and live Spanner writes stay out of this track's claims.
- This repository does not contain the proprietary loader. This track does not vendor an eBPF object, does not call `bpf()`, and does not attach a program.

## 2. Permissions ladder

The ladder is Observe, then Enforce, then Control.

The pure decision function takes `mode`: `observe` or `enforce`. `transmit` is an output of that function, not a choice the drill helper invents after the fact.

| Step | Behavior in this track |
| --- | --- |
| Observe | A classified policy violation returns `OBSERVE_WOULD_DENY` and `transmit` true. The drill sends so the evidence shows the peer received the packet. |
| Enforce | The same violation returns `DENY` and `transmit` false. The peer's receive counter stays at the pre-attempt value. |
| Control | Not implemented. No function adds an allow-list entry. The policy schema is closed. |

`enforce_outcome` is the enforce-mode result of the same inputs. It is `fail_closed` for every violation and every evaluation failure, `allow` for `ALLOW`, and `not_applicable` for `NOT_IN_SCOPE`. Observe rows that still transmit keep `enforce_outcome` `fail_closed`. The field describes what enforce would do. It does not claim the observe attempt was dropped.

Observe mode is not a non-disruptive tap for evaluation failures. A flow whose method, DNS name, header length, or body length the helper cannot see is dropped in observe as well as in enforce. The cost of that drop is the evidence row, not a copy of the packet.

Evaluation failures refuse to transmit in both modes. They return `DENY`, not `OBSERVE_WOULD_DENY`. A missing policy, a missing enrollment bit, an unparsable header, a volume-gate update failure, and an `openat2` failure are not classified observations of a valid policy. Sending them in observe would fail open. Section 6 is the full transmit table.

The symlink case has no observe-transmit path. The only open uses the resolve flags in section 5. Observe and enforce both refuse the open on escape, and both allow an in-root file. There is no mode that follows a symlink in order to record it.

`enrolled` is an explicit boolean supplied by the attach site:

| `enrolled` | Decision | Transmit in both modes |
| --- | --- | --- |
| `true` | Apply the case policy | Send only when section 6 says so |
| `false` | `NOT_IN_SCOPE` / `control_not_attached` | No. A false flag does not unlock a send. |
| missing or not a boolean | `DENY` / `enrollment_unknown` | No |

The kernel program, when a later track attaches it, attaches to the enrolled cgroup only. Unenrolled processes, including SSH, DHCP, and host DNS, are outside that attach. This track does not attach anything, so it does not demonstrate that host split on a machine.

## 3. Decision contract

One library, `t5_egress`, is the code the drills call. Each case function returns:

| Field | Values |
| --- | --- |
| `action` | `ALLOW`, `DENY`, `OBSERVE_WOULD_DENY`, `NOT_IN_SCOPE` |
| `reason` | Stable token from section 5 |
| `enforce_outcome` | `fail_closed`, `allow`, or `not_applicable` |
| `transmit` | From section 6, given `mode` |
| `evaluation_failure` | `true` when the row is an evaluation failure in section 6. `false` otherwise. Evidence stores this boolean. |
| `label` | `Lab-only` on the userspace result |

The pure functions do not open sockets and do not open files except the symlink helper, whose open is the enforcement. A transmit helper in the drill process sends only when `transmit` is true. That split is what the netns drill measures.

### Policy schema

Default drill policy lives in `scripts/clean-host/t5/policy.json`. The loader accepts only these top-level keys: `dns`, `icmp`, `http_get`, `loopback`. Any other key, including `model_grant`, `prompt`, and `completion`, is `policy_malformed`. Unknown keys inside a section are malformed too. An empty-string list entry is malformed. `match.cjs` skips empty entries. This loader does not.

An empty list is valid and means deny-all for that check. An empty `allowed_names` denies every DNS name. An empty `allowed_resolvers` denies every resolver. An empty `allowed_destinations` denies every ICMP destination. An empty `allowed_hosts` denies every GET host. An empty `allowed_ports` denies every loopback port.

Numeric bounds, all inclusive. A value outside the range is `policy_malformed`:

| Field | Range |
| --- | --- |
| `max_label_length` | 1..63. This is both the per-label cap and the cap on the sum of octets to the left of the matched suffix. |
| `entropy_min_length` | 1..63 |
| `entropy_bits_max` | greater than 0 and at most 8 |
| `max_queries` | 1..64 |
| `window_seconds` | 1..3600 |
| `max_query_length` | 1..128 |
| `max_path_length` | 1..256 |
| `max_header_bytes` | 0..1024 |

IPv4 policy entries are dotted decimal with each octet in `0..255` and no leading zero. A CIDR is malformed. IPv6 policy entries are exact text parsed to eight 16-bit words. A candidate address that is not strict dotted decimal or strict IPv6 text is `address_not_canonical`. That includes a leading zero (`127.0.0.01`), a short form (`127.1`), a decimal integer (`2130706433`), and a hex form (`0x7f000001`). `address_not_canonical` is an evaluation failure in every case. It is not `NOT_IN_SCOPE`. The loader does not use a conversion that would turn `127.0.0.01` into `127.0.0.1`.

### Names

Hostname comparison deltas from `packages/pe-egress-authority/src/match.cjs` `hostListed`:

- Shared rule: exact match, or a suffix match only when the listed name contains a dot and the candidate ends with `.` plus that name.
- T5 strips one trailing dot on the candidate and on the listed entry.
- T5 trims ASCII whitespace on listed entries. Whitespace that remains after the trim is `policy_malformed`.
- T5 folds ASCII `A-Z` only. It does not use Unicode case fold.
- A non-ASCII byte in a candidate name is `dns_label_not_ldh`. A non-ASCII byte in a listed entry is `policy_malformed`.
- A candidate label may contain only `A-Z`, `a-z`, `0-9`, `-`, and `_`. Underscore keeps `_dmarc` and `_domainkey` usable. Any other byte is `dns_label_not_ldh`.

### Addresses

Addresses are classified before any loopback, external, or link-local test. IPv4-mapped IPv6 (`::ffff:0:0/96`) collapses to the embedded IPv4 for both class tests and allow-list equality, matching `canonicalAddress` in `match.cjs`. IPv4-compatible IPv6 (the first 96 bits are zero and the address is not `::`) collapses to the embedded IPv4 only for the loopback and link-local class tests. Allow-list equality does not apply that second collapse, so `::8.8.8.8` does not match an IPv4 entry `8.8.8.8`. `match.cjs` leaves IPv4-compatible addresses as IPv6. The class-test collapse is a T5 delta.

Loopback-class, after canonicalization:

- IPv4 `127.0.0.0/8`
- IPv4 `0.0.0.0/8`, which includes `0.0.0.0` and `::1` once `::1` is read as compatible `0.0.0.1`
- IPv6 `::`
- IPv6 `::1` when it was not collapsed
- The mapped and compatible forms of the IPv4 ranges above

`::1` is loopback-class either way. A connect to `0.0.0.0:2375` or `::ffff:127.0.0.1:2375` is the loopback case, not the GET case.

Link-local, after canonicalization: IPv4 `169.254.0.0/16` (including `169.254.169.254`) and IPv6 `fe80::/10`. Link-local is denied by ICMP and by GET (`link_local_not_allowed`). It is not external.

External, for the GET case only: an address or host that is not loopback-class and not link-local. A hostname GET is compared to `allowed_hosts`. The name must not itself be an IP literal in those two classes. A destination the helper was not given is `get_method_not_visible` when the method is the missing part, or `get_host_not_allowed` when the host is missing. The helper does not guess.

When the caller supplies `connected_address`, that address is class-checked even if the hostname is listed. A listed name that resolved to a loopback-class or link-local address is denied (`link_local_not_allowed`, or `NOT_IN_SCOPE` with reason `case_not_applicable` when the GET case is the one being asked and the address is loopback-class). When `connected_address` is omitted, the name decision stands and the rebinding gap is R-T5-20.

A case function that is asked about a destination outside that case returns `NOT_IN_SCOPE` with reason `case_not_applicable` and `transmit` false in both modes. `control_not_attached` stays the token for `enrolled` false. An unparsable address is `address_not_canonical`, not `case_not_applicable`.

This library does not enumerate the host's NIC addresses. A connect to the machine's own eth0 or docker0 address is residual risk R-T5-14.

This track does not import or modify `packages/pe-egress-authority`. Track 6 keeps its own verdicts.

## 4. Named drills

Each row is one drill id. The proof script runs every drill except the symlink drill inside `unshare --user --map-root-user --net`. The symlink drill uses a temporary directory on the same runner. This runner has no Docker and no Podman. `ip` from iproute2 is not installed. The netns helper brings `lo` up with `SIOCGIFFLAGS` / `SIOCSIFFLAGS` and adds documentation addresses with `SIOCSIFADDR`. Those addresses exist only inside the namespace.

| Drill id | Pass condition |
| --- | --- |
| `t5-dns-allow-list` | Observe and enforce both `ALLOW` and the upstream receives a short listed name. An unlisted name is `OBSERVE_WOULD_DENY` and received in observe, and `DENY` and not received in enforce. |
| `t5-dns-long-label` | One label over `max_label_length`, or several left-hand labels whose octet sum exceeds `max_label_length`, under an allowed suffix, is would-deny / deny. A short listed name still `ALLOW`. |
| `t5-dns-high-entropy` | Left-hand labels whose concatenated entropy is above `entropy_bits_max`, and whose length is at least `entropy_min_length`, are would-deny / deny under an allowed suffix. A long low-entropy left-hand label still `ALLOW`. |
| `t5-dns-query-volume` | The first `max_queries` attempts in the window `ALLOW` when the name is listed. The next attempt is would-deny / deny. Denied and unlisted attempts count toward the cap. After the window, a new listed query `ALLOW` again. |
| `t5-dns-unknown-delegation` | An NS or glue address outside the resolver list is `delegation_unknown`. A follow-up query to that address is `resolver_not_allowed` and is not received in enforce. A follow-up to the listed resolver `ALLOW`. |
| `t5-icmp-egress` | Echo to a listed IPv4 destination `ALLOW` and the listener counts it. Echo to any other destination, a non-echo type to the listed destination, ICMPv6, and a link-local destination are would-deny / deny and are not counted in enforce. |
| `t5-get-write` | A short GET, `body_length` 0, `header_bytes` within the cap, to a listed external host `ALLOW` and the server counts it. A body, an over-long raw query, a write query key, a write path, a `%` / `..` / `//` form, or a too-long path is would-deny / deny. The enforce attempt is not counted. A GET to `127.0.0.1` or `0.0.0.0` is `NOT_IN_SCOPE` for this drill. |
| `t5-loopback-priv-esc` | TCP to an allow-listed loopback port `ALLOW` and the listener accepts. TCP to a privileged port on `127.0.0.1`, on `0.0.0.0`, and on `::ffff:127.0.0.1` is would-deny / deny and is not accepted in enforce. One UDP datagram to a privileged loopback port is denied and not received in enforce. One UDP datagram to the allow-listed port is allowed and received. |
| `t5-symlink-escape` | The root is opened with `O_PATH\|O_DIRECTORY\|O_NOFOLLOW` and checked with `fstat`. `openat2` with `RESOLVE_BENEATH\|RESOLVE_NO_XDEV\|RESOLVE_NO_MAGICLINKS` reads a file inside the root and reads an in-root symlink to an in-root file. A symlink to an outside file, a `..` escape, and a directory symlink that leaves the root return a fail-closed token and the outside sentinel is not read. The bind-mount case runs in its own `unshare --user --map-root-user --mount`. If that mount cannot be created, the drill fails. It does not skip. |

A drill exits 0 only when every case matches. The evidence file for that drill records `pass` or `fail`.

## 5. Reason tokens and check order

Allow and scope:

- `policy_permits`
- `control_not_attached`
- `case_not_applicable`
- `address_not_canonical`

Fail-closed denies:

- `policy_malformed`
- `enrollment_unknown`
- `dns_unparsable`
- `dns_parse_budget`
- `dns_qdcount`
- `dns_label_not_ldh`
- `dns_label_too_long`
- `dns_label_entropy`
- `dns_query_volume`
- `dns_name_not_allowed`
- `resolver_not_allowed`
- `delegation_unknown`
- `delegation_unresolved`
- `dns_transport_not_visible`
- `icmp_header_unreadable`
- `icmp_destination_not_allowed`
- `icmp_type_not_allowed`
- `link_local_not_allowed`
- `get_method_not_visible`
- `get_host_not_allowed`
- `get_body_write`
- `get_query_too_long`
- `get_query_write_key`
- `get_path_write`
- `get_path_not_normalized`
- `get_path_too_long`
- `get_body_length_unknown`
- `get_header_length_unknown`
- `get_headers_too_long`
- `loopback_port_not_allowed`
- `loopback_header_unreadable`
- `symlink_escape`
- `symlink_root`
- `symlink_race_unresolved`
- `path_absent`
- `open_denied`
- `path_not_directory`
- `open_failed`
- `openat2_unavailable`
- `openat2_rejected`
- `path_not_relative`

DNS query order when enrollment and policy are valid:

1. Wire parse, including the budget in section 7. Failure stops the decision. `QDCOUNT` other than 1 is `dns_qdcount`.
2. Resolver address against the exact resolver list, after canonicalization. Link-local resolvers are `link_local_not_allowed`.
3. Per-label character rule and per-label length.
4. The matched suffix is the longest listed suffix that matches. If the name has labels to the left of that suffix, those labels are checked as a tunnel: each label length, the sum of their octets against `max_label_length`, then Shannon entropy of their concatenation with the dots removed. Labels shorter than `entropy_min_length` are not scored on their own. The concatenation is scored when its length is at least `entropy_min_length`. An exact listed name with no left-hand labels skips this step.
5. Name against the name list.
6. Volume window. Every attempt counts, including names that already failed steps 3 through 5, so a tunnel cannot refresh the window by using rejected names. The process holds one gate and one workload id. A second workload id in that process is `dns_query_volume` with `evaluation_failure` true. The list keeps at most `max_queries` timestamps, and `max_queries` cannot exceed 64. When the list is already full, a further attempt replaces the oldest timestamp and is denied. That keeps the window full for over-cap traffic without growing the list. The `t5-dns-query-volume` drill waits one full window after the last attempt before it expects `ALLOW` again. Timestamps outside the window are dropped first. The clock is `time.monotonic_ns`. The default cap is 30 queries in 10 seconds. The userspace window slides. The kernel record in section 7 is a fixed window. Those are different counters (R-T5-15).

Shannon entropy is `-sum(p log2(p))` over byte frequencies of the concatenation. The default ceiling is 3.5 bits per character. Sample entropy on short strings sits below the true entropy. The drill proves the function against its own ceiling. It does not prove that every real tunnel alphabet exceeds 3.5 (R-T5-3). The left-hand octet sum still caps that alphabet at `max_label_length`.

Delegation is a userspace parse of a DNS response the drill already holds. `cgroup_skb/egress` does not see that response. A kernel port enforces the follow-up with `resolver_not_allowed` and does not implement `delegation_unknown` in the skb program. Each NS name must sit on the name list. Each glue A or AAAA must sit on the resolver list. A glue-less NS is `delegation_unresolved`.

ICMP: IPv4 headers with `ihl` below 5, or a header that extends past the buffer, are `icmp_header_unreadable`. IPv6 extension-header walks stop at 4 headers. ICMPv6 is `icmp_type_not_allowed` in this track even when the walk succeeds. Echo request (8) and echo reply (0) to a listed IPv4 destination are the only allows. Other types to a listed destination are `icmp_type_not_allowed`. Echo payload contents are not inspected (R-T5-17).

GET: loopback-class destinations are `NOT_IN_SCOPE` for this case. Link-local destinations are `link_local_not_allowed`. External hosts must be on `allowed_hosts`. A missing method, or `method_visible` false, is `get_method_not_visible`. A missing `body_length` is `get_body_length_unknown`. A missing `header_bytes` is `get_header_length_unknown`. `header_bytes` above `max_header_bytes` is `get_headers_too_long`. The helper does not parse header names (R-T5-18).

Write signals, applied to the raw query and the raw path, before any percent-decode: a body length above 0, a raw query longer than `max_query_length`, a query key in the write-key list, or a path under a write prefix. Write-prefix comparison ASCII-casefolds the path. The raw path and the raw query are denied with `get_path_not_normalized` when they contain `%`, `..`, `//`, `\`, `;`, or a non-ASCII byte. A legitimate percent-encoded query is denied by that rule (R-T5-6). Query keys are split on `&` and `=`, then ASCII-casefolded. Any matching key denies, including a repeated key. A path longer than `max_path_length` (at most 256, the compare budget) is `get_path_too_long`. The length caps count raw bytes, not decoded characters. Evidence stores the signal token and the lengths.

Loopback: after canonicalization, the destination must be loopback-class or the case returns `NOT_IN_SCOPE`. Every TCP or UDP port below 1024 is privileged, plus 2375, 2376, 6443, 10250, 10255, and 5001. The only permit is `allowed_ports`. An unlisted high port on loopback is denied too. Unix-domain sockets are not this case. A Docker socket opened by path is the symlink case when the caller uses that helper.

Symlink root: `open(root, O_PATH|O_DIRECTORY|O_NOFOLLOW)`, then `fstat` on that descriptor. On this kernel a symlink opened that way returns `ENOTDIR`, not `ELOOP`. `ENOTDIR` and every other errno from the root open are `symlink_root`. A descriptor that `fstat` shows is not a directory is `symlink_root` and is closed. There is no `lstat` followed by a later open. Child opens use `openat2` (`SYS_openat2` 437 on this x86_64 runner) with `RESOLVE_BENEATH | RESOLVE_NO_XDEV | RESOLVE_NO_MAGICLINKS`. `RESOLVE_NO_SYMLINKS` is not set, so an in-root symlink to an in-root file remains usable. `RESOLVE_NO_XDEV` is set, so a bind mount inside the root is `symlink_escape` rather than a residual. `RESOLVE_NO_MAGICLINKS` is set because the magic-link block that `RESOLVE_BENEATH` also applies is documented as subject to change.

Errno map, one attempt, no retry:

| errno | Token |
| --- | --- |
| `EXDEV`, `ELOOP` | `symlink_escape` |
| `EAGAIN` | `symlink_race_unresolved` |
| `ENOENT` | `path_absent` |
| `EACCES`, `EPERM` | `open_denied` |
| `ENOTDIR` | `path_not_directory` |
| `ENOSYS` | `openat2_unavailable` |
| `EINVAL` | `openat2_rejected` |
| any other | `open_failed` |

`EAGAIN` from a `..` rename race is not retried. A retry could land on a path the attacker then holds still. Absolute paths and NUL bytes are `path_not_relative` and do not reach the syscall. The race check opens the same path many times while another thread replaces the file with a symlink to a sentinel. A pass is "the sentinel bytes were never read". Any fail-closed token, with no bytes read, is a pass. A read of the sentinel is a fail.

## 6. Transmit table

`enforce_outcome` is `fail_closed` for every row that is not an allow or a scope skip. No row transmits in enforce except `policy_permits`.

| Reason class | Observe action | Observe transmit | Enforce action | Enforce transmit |
| --- | --- | --- | --- | --- |
| `policy_permits` | `ALLOW` | yes | `ALLOW` | yes |
| `control_not_attached`, `case_not_applicable` | `NOT_IN_SCOPE` | no | `NOT_IN_SCOPE` | no |
| `policy_malformed`, `enrollment_unknown`, `address_not_canonical` | `DENY` | no | `DENY` | no |
| Classified policy violation: name, label length, entropy, volume, resolver, delegation, ICMP destination or type, link-local, GET write signals, GET host, loopback port | `OBSERVE_WOULD_DENY` | yes | `DENY` | no |
| Evaluation failure: `dns_unparsable`, `dns_parse_budget`, `dns_qdcount`, `dns_label_not_ldh`, `icmp_header_unreadable`, `loopback_header_unreadable`, `dns_transport_not_visible`, `get_method_not_visible`, `get_body_length_unknown`, `get_header_length_unknown`, `get_path_not_normalized`, volume gate update failure (reported as `dns_query_volume`) | `DENY` | no | `DENY` | no |
| Symlink tokens, including `openat2_unavailable`, `openat2_rejected`, `symlink_race_unresolved` | `DENY` | no open | `DENY` | no open |

`get_path_not_normalized` is an evaluation failure, not a classified would-deny: the helper refuses to interpret a path it will not normalize, in both modes. A clean write-key hit on an otherwise normal query is a classified violation and does transmit in observe.

Volume-gate update failure uses the same token as a full window, `dns_query_volume`, and takes the evaluation-failure row (no transmit in observe). The drill's ordinary over-cap case is a classified violation and does transmit in observe. The implementation distinguishes them with `evaluation_failure: true` on the result. Evidence records that boolean.

No row in this track chooses fail-open.

## 7. eBPF verifier limits

This track does not compile or load eBPF. The bounds below are the contract a later kernel port has to meet. The userspace parser uses the same budgets so a name the verifier would refuse to walk is already `dns_parse_budget` here.

Program type for DNS queries, ICMP, and cleartext TCP, when that port exists: `cgroup_skb/egress` on the enrolled cgroup. One program. No tail calls. `MAX_TAIL_CALL_CNT` (33) does not apply.

Verifier facts the port must respect:

| Limit | Value used by this design | What the userspace code does with it |
| --- | --- | --- |
| Complexity | 1,000,000 instructions, the privileged-loader ceiling on current kernels | The DNS walk is capped so a port stays far under this |
| Stack | 512 bytes | No 256-bin histogram on the stack |
| Packet loads | `data + offset <= data_end` before every load | The Python parser returns unparsable at the first short read |
| Bounded loops | A loop the verifier can bound | Name walk at most 128 steps. Pointer hops at most 4. IPv6 extension headers at most 4. Cleartext HTTP scan at most 512 bytes. Path compare at most 256 bytes |
| DNS label | 63 octets, name 255 octets | Longer than the wire rule is `dns_unparsable`. A left-hand sum above the policy cap (default 32) is `dns_label_too_long` |
| Shannon entropy | Not in the skb program | eBPF has no floating point, so `log2` would be a fixed-point table. A 256-bin table plus a 63-step loop also risks the 512-byte stack and multiplies complexity. Entropy stays in userspace. The kernel fast path, if written later, is a separate pure function `skb_label_signal`: one 63-step pass, flag when length is at least 20 and digit count times 2 exceeds the length. That function is tested and labeled Roadmap. It is not the enforce decision. The two detectors can disagree (R-T5-3) |
| Maps | Allow-list hash and a per-cgroup fixed window `{window_start_ns, count}` | Lookup returning NULL is a drop in enforce. A spin lock around the counter must be released on every path. If `bpf_spin_lock` is unavailable, the loader refuses to attach. A racy under-count would fail open. The fixed window can allow about twice the cap across a boundary. The userspace drill uses a sliding window (R-T5-15) |
| Time | `bpf_ktime_get_ns` | Userspace uses `time.monotonic_ns` |
| Response parse | Not in `cgroup_skb/egress` | `delegation_unknown` is userspace only. The kernel port's delegation control is `resolver_not_allowed` on the next query |
| LSM path | `file_open` plus `bpf_d_path` into a fixed buffer | `bpf_d_path` error or a truncated path is a deny. This track uses `openat2` instead, and does not load an LSM program |
| Helpers while holding a lock | Restricted by the verifier | The userspace volume lock covers the timestamp list and no socket I/O |

`cgroup_skb` does not see a Unix socket and does not see a TLS method. The WSL2 uprobe on `SSL_write` can see cleartext the application passed to OpenSSL or GnuTLS. rustls and QUIC do not hit that uprobe. When the method or the DNS name is not in the buffer the decision function was given, the result is the evaluation-failure row in section 6. This track does not claim the uprobe ran.

Memory of the userspace library on a drill workload: one volume list of at most 64 integers, one workload id of at most 64 ASCII characters, a 255-byte name buffer, and one evidence object aimed at under 8 KiB. Nothing in that set is conversation text.

## 8. Local execution

Proof command, after the code exists:

```bash
python3 scripts/clean-host/t5/proof.py
```

The script runs the unit tests, then each named drill, and writes `docs/planning/gap-t5-egress/evidence/proof.json`. Exit 0 means every drill passed on this runner. That file's label is `Lab-only`. It is not a cluster result and not a customer result.

Netns drills fork through `unshare --user --map-root-user --net`. That invocation does not pass `--pid`. The parent does not look for a new PID namespace. The child writes the inode of `/proc/self/ns/net` into the evidence. The parent compares it with the inode of its own `/proc/self/ns/net`. A pass requires the two inodes to differ. A drill that cannot enter a network namespace exits non-zero and the proof fails. There is no fallback that pretends the packets were gated.

## 9. Lab registration

`scripts/clean-host/t5/LAB-REGISTRATION.json` lists the drill ids, the proof command, `cloud_run: false`, and the integration step.

Integration step, not performed by this track: a later lab agent may copy `scripts/clean-host/t5` onto a guest it already owns and add a battery id to the allow-list in `scripts/aws/w3_lab_steps.py`, then run that battery. This track does not edit that file, does not edit `.github/workflows/w3-lab-*.yml` or `.github/workflows/gcp-lab-*.yml`, and does not start a cloud lab. Lab agent `bc-8b310b16` owns the lab slot. `6d3ce580` is not the working seal, and this track does not change a seal or a pin. The public pin stays `e0b19d55`.

## 10. Dependencies, failure modes, rollback

Dependencies:

- Python 3.10 or newer, standard library only.
- `unshare` from util-linux.
- Linux `openat2` on the drill runner. Absence is a failed symlink drill, not a silent allow.
- No new package install, no network fetch, no cloud account.

Failure modes:

- `unshare` denied: proof exits non-zero. No evidence file is marked pass.
- A drill timeout: the parent kills the child and records `fail`.
- A peer that receives a packet the enforce decision said it would not send: `fail`.
- A peer that misses a packet the allow decision said it sent: `fail`.
- An observe violation that the peer does not receive: `fail`.

Rollback before merge: delete the branch. No unit is installed, no program is pinned, no workflow is changed, no package is published. There is nothing to detach. This track does not merge. If a later human merge were reverted, that revert would be a separate commit. It is not an action this track takes.

## 11. Files this design authorizes

Design packet, this phase:

- `docs/planning/gap-t5-egress/00-DESIGN.md`
- `docs/planning/gap-t5-egress/01-COUNCIL-VERDICT.md`
- `docs/planning/gap-t5-egress/02-RISK-REGISTER.md`

Implementation phase, only after the verdict is committed:

- `packages/t5-egress-drills/t5_egress/` decision library
- `packages/t5-egress-drills/tests/` unit tests
- `scripts/clean-host/t5/` drills, catalog, policy, proof script, `LAB-REGISTRATION.json`
- `docs/planning/gap-t5-egress/evidence/proof.json` written by the proof script
- `docs/planning/gap-t5-egress/03-LAB-INTEGRATION.md` the same integration step, kept next to the risks

Not authorized: edits under `.github/workflows/`, `scripts/aws/w3_lab_steps.py`, `README.md`, installer pin files, or `packages/pe-egress-authority/`.

## 12. Labels

| Result | Label |
| --- | --- |
| Userspace decisions and local drills, once the proof script exits 0 | Lab-only |
| `skb_label_signal` and any `cgroup_skb` or LSM attach | Roadmap |
| Cluster, stranger-host, customer | Not run. Not claimed |
