# T4 host copy

Audience: INTERNAL_RESTRICTED

Date: 2026-10-16

Authorization: Founder Q11 and Q12, Lane K. The copy, when a later loader exists, runs on a Vantio-owned enrolled Linux host only.

Lane lab seal: `6d3ce580`. Public pin stays `e0b19d55`.

Section 6.2 of `00-DESIGN.md` refused to choose a ring primitive. This file is that choice. It does not load a program. JSON parsing stays in the userspace library.

## Labels

| Result | Label |
| --- | --- |
| `classifyCopy` on a record the caller already holds | Lab-only |
| Ring attach, fd registration, and a live enrolled host | Roadmap |
| Host enforce, a withhold on `write` | Roadmap |
| TLS plaintext for rustls, QUIC, or any stack without an attached probe | Roadmap |

## Primitive

One `BPF_MAP_TYPE_RINGBUF`. A per-CPU array value is not a place for a frame. Perf-event output is the fallback, and its size field is 16 bits, so one record cannot hold the parser's 256 KiB frame cap.

Each ring record is a 32-byte header plus at most **4096** bytes of payload. 4096 is one page. The copy uses `bpf_probe_read_user` into the reserved ring record. It does not put the frame on the 512-byte stack.

`packages/vantio-mcp-awareness` `MAX_FRAME` stays 256 KiB. A frame longer than 4096, or a copy shorter than the frame the caller measured, is `truncated_capture`. That row is a gap. It is not an allow. The unread tail can hide a write tool. Fail closed.

## What is copied

| Source | Copy | Why |
| --- | --- | --- |
| A stdio pipe whose fd the loader registered for one cgroup | Up to 4096 bytes from the user buffer at `sys_enter_write` or `sys_enter_read` | The pipe is plaintext |
| Any other fd | `unregistered_fd` | The program does not discover MCP by parsing |
| A TLS socket | `ciphertext` | Socket bytes are not MCP. OpenSSL `SSL_read` / `SSL_write` remain the only plaintext probes named in the phase-1 design, and this track still adds none. rustls stays uncovered |

The durable observation is the existing T4 record plus `capture` and `copied_bytes`. The ring bytes are dropped after the userspace parser runs. A complete copy is `HAND_TO_PARSER`. The parser's own decision is the only allow. This module does not return `ALLOW`.

A copy that reaches userspace after `write` has returned cannot withhold that write. Host enforce needs a synchronous decision point. This design does not name that hook. Enforce stays Roadmap.

## Registration

Userspace inserts `(cgroup id, fd) -> stream id` after the process is in the lab cgroup. The cgroup is a leaf the loader created. It is not `vantio-enrolled.slice` and it is not a Navera host. The map starts empty, so an unregistered fd copies nothing.

## Loss

A full ring drops the event. The gap is a missing observation, not an allow. Perf-event fallback uses the same truncation rule and cannot raise the 4096-byte cap, because a 16-bit size still cannot hold 256 KiB and this design does not raise the copy.

## Harness

`packages/vantio-mcp-awareness/src/hostCopy.js` classifies a record. It is not exported from the package entry. It does not open a socket. Tests: `node --test packages/vantio-mcp-awareness/test/host-copy.test.js`.

## Risks

| ID | Risk | Label | Exposure |
| --- | --- | --- | --- |
| R23 | The unread tail of a truncated frame can hold a write tool. | Lab-only decision. Roadmap for the attach | Truncation is a gap, not an allow. A later reader that treats the prefix as the whole frame would miss the tail |
| R24 | A dup'd or replaced fd can point the registered slot at a different stream. | Roadmap | The map is not a proof of which pipe the bytes came from |
| R25 | TLS and every unregistered fd are invisible to this copy. | Roadmap | A tools/call on those paths is not observed here |
| R26 | A full ring drops the event. | Roadmap | Loss looks like no call. It is not an allow |
| R27 | This classification can be described as host enforce. | Roadmap for enforce | A copy after `write` returns cannot withhold the write |

No workflow was edited. No lab was started. AWS stays with `bc-8b310b16` through Monday. GCP was not dispatched.
