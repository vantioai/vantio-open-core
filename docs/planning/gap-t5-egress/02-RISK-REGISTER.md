# T5 risk register

Audience: INTERNAL_RESTRICTED

Track: T5

Date: 2026-10-16

Labels used below are Verified, Lab-only, or Roadmap. This register does not use the words "unbreakable" or "audited".

| ID | Risk | Label of the related result | Remaining exposure |
| --- | --- | --- | --- |
| R-T5-1 | The decision library and the netns drills run on the cloud-agent runner. They do not attach to an enrolled production cgroup. | Lab-only | A host without this helper still has the previous egress behavior. Kernel attach is Roadmap. |
| R-T5-2 | `cgroup_skb` and LSM programs are specified with verifier budgets and are not loaded. | Roadmap | DNS, ICMP, and loopback TCP are not dropped by a kernel program in this track. |
| R-T5-3 | Shannon entropy is the Lab-only detector. `skb_label_signal` is a digit-ratio stand-in for a future skb program. They can disagree on the same label. Sample entropy of short strings is biased low: base32 near 12 characters and hex near 20 characters can sit under the 3.5 ceiling. The drill proves the function against that ceiling. The left-hand octet sum still caps the unscored alphabet at `max_label_length`. | Lab-only for Shannon. Roadmap for the digit-ratio function. | A later kernel port that enforced only the digit ratio would miss some high-entropy alphabetic labels and would flag some numeric names the Shannon ceiling allows. The port has to pick one detector and re-run these drills. |
| R-T5-4 | TLS and DoH hide the method and the qname from `cgroup_skb`. `dns_transport_not_visible` and `get_method_not_visible` are evaluation failures. Section 6 drops them in observe and in enforce. | Lab-only decision. Roadmap for an uprobe that could supply the bytes. | Legitimate calls to a listed host are dropped in both modes until the method or name is visible. The cost shows up in the evidence row. Observe is not a non-disruptive tap for these flows. rustls and QUIC remain invisible to the WSL2 OpenSSL/GnuTLS uprobe. |
| R-T5-5 | The volume window is one process-local list behind a lock. It is not a shared BPF map. | Lab-only | Two processes in the same workload can each stay under the cap. A kernel port has to use the per-cgroup map in the design, or the cap is per process. |
| R-T5-6 | Default caps (left-hand octet sum 32, entropy 3.5, 30 queries in 10 seconds) will flag some legitimate CDN, DKIM, and cache-busting names. Labels outside `A-Z`, `a-z`, `0-9`, `-`, and `_` are denied, including non-ASCII IDN. Underscore is allowed so `_dmarc` and `_domainkey` stay usable. A query or path that contains `%` is `get_path_not_normalized`, so a legitimate percent-encoded GET is denied. | Lab-only | Operators change `policy.json` for the numeric caps. The percent-encoding rule is code, not a cap. The drill proof uses the defaults. A wider production list is a policy change, not a code change, and still cannot come from model output. |
| R-T5-7 | `openat2` is required. Kernels that return `ENOSYS` fail the symlink drill closed. | Lab-only on this runner, which has syscall 437. Roadmap for an LSM attach on hosts where the syscall exists but no BPF LSM is loaded. | A host that only has `open` can still be escaped if some other component follows symlinks. This helper will not be that component. |
| R-T5-8 | The netns uses documentation addresses on `lo`. Packets do not cross a physical NIC. | Lab-only | The drill does not prove a drop on a routed interface, a bridge, or a pod network. |
| R-T5-9 | Unix sockets and abstract-namespace sockets are outside the loopback TCP/UDP check. | Lab-only for paths that leave the workload directory through `openat2`. | A socket path inside the workload root is not an escape. A host socket the workload opens by an absolute path is `path_not_relative` only when the caller uses this helper. |
| R-T5-10 | Track 6 egress authority is intentionally not modified. The two evaluators can disagree if both are later called on one event. | Lab-only | A later track has to define which decision wins before either one is wired into the interceptor. |
| R-T5-11 | Cloud lab wiring is a documented step and is not done. | Roadmap for the lab agent's battery list | `scripts/aws/w3_lab_steps.py` will reject an unknown battery id until a separate change adds it. |
| R-T5-12 | IPv4 is the drilled path. ICMPv6 is denied in this track. IPv6 resolvers are parsed only far enough to fail closed when the header walk or the address is outside the exact list. | Lab-only | An IPv6 deployment needs allow-list entries written as exact addresses and a drill on that family before anyone calls it covered. |
| R-T5-13 | Closed by the design revision. A tunnel split across several short labels is scored on the concatenation of every label to the left of the allowed suffix, and the octet sum of those labels is capped by `max_label_length`. | Lab-only | An exact listed name with no left-hand labels is not entropy-scored. The operator listed that name. |
| R-T5-14 | The helper does not enumerate the host's NIC addresses. A connect to the machine's own eth0 or docker0 address can reach a listener bound to `0.0.0.0` without using a loopback-class address. | Roadmap for a host-address set supplied by the attach site | Loopback-class covers `127.0.0.0/8`, `0.0.0.0/8`, `::`, `::1`, and IPv4-mapped or IPv4-compatible forms of those ranges. It does not cover the NIC address. |
| R-T5-15 | The userspace volume window slides. The kernel record `{window_start_ns, count}` is a fixed window and can allow about twice the cap across a boundary. Denied and unlisted attempts count in the userspace window. | Lab-only for the sliding window. Roadmap for the fixed window. | A kernel port has to re-state which window it enforces and re-run `t5-dns-query-volume`. |
| R-T5-16 | An allowed suffix that another tenant can write (`github.io`, a shared zone) lets a tunnel use the allowed recursive resolver and an attacker-controlled authoritative server. The left-hand length and entropy checks still apply. | Lab-only | Operators allow-list names they control. The loader does not add a public-suffix table. |
| R-T5-17 | Echo payloads to a listed ICMP destination are not inspected. | Lab-only | An echo tunnel to a listed monitor stays inside the allow. Removing echo from `allowed_types` closes it and also removes the health check. |
| R-T5-18 | GET header names are not parsed. `header_bytes` is a length. A short header can carry a write. Path segments that are not under a write prefix, and that stay inside the length cap and the normalization rules, are not a write signal. | Lab-only | A caller that omits `header_bytes` is denied. A caller that passes a small length can still hide a short header write. |
| R-T5-19 | Link-local destinations, including `169.254.169.254`, are `link_local_not_allowed` when the address is visible to the helper. | Lab-only | A destination the helper is not given is `get_host_not_allowed` or an evaluation failure. The helper does not discover metadata by probing. |
| R-T5-20 | A listed hostname can resolve to a loopback-class or link-local address. When the caller supplies `connected_address`, that address is class-checked and the GET is not treated as external. When it is omitted, the name decision stands. | Lab-only | The attach site has to pass the connected address before this rebinding case is closed. The drill that omits it does not claim the close. |
| R-T5-21 | Drill evidence stores SHA-256 of synthetic fixture bytes only. An unkeyed hash of a real, low-entropy request body can be guessed. | Lab-only for fixture hashes. Roadmap for any production evidence wiring. | This track's proof does not hash a customer body. A later wiring needs a keyed digest or no body digest at all. |

Approval-gate items this track stops in front of:

- Merge, and the founder-approved label.
- Any AWS or GCP lab run, including a run by lab agent `bc-8b310b16`.
- Editing in-flight lab workflows or the battery allow-list.
- Loading eBPF, restarting a phantom box, or production enrollment.
- Publishing a package, moving a public README claim, or changing pin `e0b19d55`.
- Spending money, issuing a credential, or sending mail to a vendor.

Dependencies on other tracks:

- None for the local proof. T5 does not need Track 6 to merge, and Track 6 does not need T5.
- A cluster claim needs the Phantom Engine loader on a privileged host this runner is not, and a charter this track does not have.
- A cloud run of these drills needs the integration step in `00-DESIGN.md` section 9, done by the lab agent in a later change.
