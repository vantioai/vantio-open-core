# T5 kernel port

Audience: INTERNAL_RESTRICTED

Date: 2026-10-16

Authorization: Founder Q11 and Q12, Lane K. Vantio-owned hosts only.

Lane lab seal: `6d3ce580ffb5d52fa0bfb70bdee28409fa6282f86737011e3d85c1093f5ea403`

Public pin: `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e` (unchanged)

This file is the kernel port. The phase-1 design in `00-DESIGN.md` still describes the userspace drills. Where that file says the track does not compile eBPF, this port is the later authorization.

## Labels

| Result | Label |
| --- | --- |
| Userspace drills and the Python model of the program | Lab-only |
| `clang -target bpf` object, not loaded | Lab-only |
| `bpf()` attach, verifier acceptance, cgroup drop on a Vantio host | Roadmap |
| Shannon entropy | Lab-only, userspace only |
| Cluster, customer, stranger-host | Not run |

## Program

`packages/t5-egress-kernel/bpf/t5_egress.bpf.c` is GPL-2.0-only because `bpf_spin_lock` is a GPL-only helper. It is not linked into the Python package. The repo license is otherwise unchanged.

Attach sections, one program each, no tail calls:

- `cgroup_skb/egress`
- `cgroup/connect4`
- `cgroup/connect6`

The loader in `t5_kernel/loader.py` refuses the syscall unless every gate passes, and even then the default path does not issue it. Gates: host class `vantio-owned`, project `vantio-lab-oct08`, cgroup leaf under `/sys/fs/cgroup/vantio-t5-lab.slice/`, not `vantio-enrolled.slice`, not a Navera name, lane seal if a seal is supplied, and `entropy_userspace == 1`.

The program does not call the userspace entropy function. A left-hand name at least `entropy_min_length` long is dropped when its distinct byte count times 4 exceeds that length (`dns_label_entropy`, classified). A repeated character stays allowed. The userspace score is still the drill measurement. The two can disagree (R-T5-K11). The old fail-open on a high-diversity label (R-T5-K1) is closed for that case.

## What the program decides

DNS over UDP/53: wire parse with a 16-step, 8-label, 4-pointer budget, resolver list, LDH, per-label cap, suffix match, fixed window. TCP/53 is `dns_transport_not_visible` and does not transmit in observe or enforce.

ICMP echo to a listed IPv4 destination is allowed. Other types, other destinations, and link-local are classified denies. ICMPv6 is `icmp_type_not_allowed`. Other IPv6 is `icmp_header_unreadable` because extension headers are not walked.

Connect to an allowed resolver on port 53 is allowed, including loopback. Other loopback ports must be on `allowed_ports`. Link-local connects are classified denies. Every other connect is `case_not_applicable` and does not transmit.

TCP/80 is `get_method_not_visible` in both modes. The program does not parse an HTTP host header. Cleartext GET stays a userspace drill.

A fixed window can allow about twice the cap across a boundary. The userspace drill still uses a sliding window.

## Battery

Battery id `t5-egress` is on the allow-list in `scripts/aws/w3_lab_steps.py`. The guest script runs the userspace proof and this model. It does not attach. It refuses a Navera path and does not mention `vantio-enrolled.slice` as an attach target.

GCP `scripts/gcp/t5_lab_plan.py` records the same id and returns `dispatch: false`. The default GCP schedule is still enterprise, then descendant-b1, twice. The workflow file on main has no input for this battery. Workload identity for provision still requires that file on main. This change does not edit workflow permissions and does not dispatch.

Slot check at `2026-10-16T21:47:32Z`: no in-progress GitHub Actions runs. Last GCP lab provision [38848458042](https://github.com/vantioai/vantio-open-core/actions/runs/38848458042) completed success at `2026-10-16T04:01:37Z`. Sweeper [38963011708](https://github.com/vantioai/vantio-open-core/actions/runs/38963011708) completed success at `2026-10-16T20:32:45Z`. AWS workflows were not started. Lab agent `bc-8b310b16` owns the AWS slot through Monday.

## Risks

| ID | Risk | Label | Exposure |
| --- | --- | --- | --- |
| R-T5-K1 | Entropy is not a kernel drop. A high-entropy label the userspace score would deny is allowed by the program, with `entropy_deferred` set. | Lab-only model. Roadmap for any host where userspace is not also on the path | A process that bypasses the userspace drill can tunnel in a long high-entropy label |
| R-T5-K2 | The object was compiled here and was not loaded. Verifier acceptance, the spin lock, and the port byte order in `user_port` are unexecuted. | Roadmap | A load on a Vantio host can still be rejected, or can read the port in the wrong half of the word |
| R-T5-K3 | TCP/80 is an evaluation failure. A benign GET the userspace drill allows is dropped if this program is attached on that cgroup. | Roadmap for attach | Do not attach this program around the GET drill |
| R-T5-K4 | IPv6 extension headers are not walked. Non-ICMPv6 IPv6 is `icmp_header_unreadable`. | Lab-only decision | An IPv6 DNS query is not a DNS decision |
| R-T5-K5 | The kernel name walk is 16 steps and 8 labels. The userspace parser allows 128 steps. Longer names are `dns_parse_budget`. | Lab-only | Fail closed relative to the userspace parser |
| R-T5-K6 | The fixed window resets when `start_ns` is 0. A timestamp of 0 cannot be stored. `bpf_ktime_get_ns` after boot is not 0. | Roadmap until loaded | The model tests start the window above 0 |
| R-T5-K7 | Unclassified egress and non-resolver connects do not transmit. Attaching this program outside the drill cgroup would drop host traffic. | Roadmap | The loader refuses the root cgroup, `system.slice`, and `vantio-enrolled.slice` |
| R-T5-K8 | The battery id is wired and was not dispatched. A guest run has not happened. | Roadmap for the cloud run. Lab-only for the allow-list test | `cloud_run` stays false |
| R-T5-K9 | `user_port` is taken from the low 16 bits. That matches the usual connect4 selftest and was not executed here. | Roadmap | A wrong shift would allow or deny the wrong port |
| R-T5-K10 | One cgroup window is shared by every process in the leaf. The userspace gate is per process and per workload id. | Lab-only model | Two processes can exhaust one kernel window, or one process can stay under a cap the other already used |

Rollback before merge: delete the branch. Nothing is attached and no workflow on main changed.
