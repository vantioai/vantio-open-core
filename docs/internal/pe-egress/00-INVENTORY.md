# Track 6 inventory

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_EGRESS_PROGRAM_REVISION_READY_FOR_COUNCIL`

Starting commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

This inventory records what this repository can prove about egress paths. It does not re-execute the private Phantom Engine tree, a kernel, or a cluster.

## Application paths in this repository

The Node wrap is `packages/vantio-cli/bin/interceptor.cjs`. Its header names the patched surfaces: `globalThis.fetch`, undici fetch/request/dispatch/stream/pipeline/connect/upgrade, Node `http`/`https`, Node `http2`, `net.Socket.connect` / `tls.connect`, WebSocket and CONNECT tunnel writes, and `child_process` spawn/exec of curl, wget, httpie, and aria2c. Browsers stay outside the wrap.

The Python entry is `packages/vantio-cli/bin/python-wrap/sitecustomize.py`. It installs `vantio-agent-sdk` when that package is importable. The SDK module `vantio/_http_observe.py` states that a Phantom Engine key can block, redact PII, or enforce a spend limit on HTTP bodies, and that file contents and stdin pipes are not read.

Observed limits in those sources, used as path capabilities:

| Limit | Where it is visible |
| --- | --- |
| Fail-open until policy loads, and on unexpected decision errors | `enforceRequest` comment and `policyReady` |
| Spend cap counts bytes after the fact and gates a later call | `trackStreamBytes` comment |
| Streaming, FormData, Blob, file, and pipe bodies are not scanned | `unscannableBodyLabel` and the Python wrap comment |
| No redirect handler | no `redirect` symbol in `interceptor.cjs` |
| Raw sockets do not redact TLS payloads | `patchNodeNetTls` comment |
| WebSocket and CONNECT payloads are not parsed | tunnel comment |
| Child wrap names curl, wget, httpie, and aria2c | `patchCurlSpawn` |
| Hostname match is exact, or a DNS suffix when the listed name contains a dot | `llm-hosts.cjs` `hostListed` |

`@vantio/gate-mcp` evaluates a dry-run and does not block a socket. This authority does not call it.

## Host paths not executed here

`docs/planning/phantom-engine-production/COVERAGE-MATRIX.json` records earlier repository evidence. This force did not repeat those runs.

| Row | What this force may say |
| --- | --- |
| Enrolled TC drop on WSL2 | `OBSERVED_FROM_REPOSITORY_EVIDENCE`. Not executed here |
| TLS uprobe byte counts on WSL2 | Observation, not a drop. Not executed here |
| `cgroup_skb/egress` not auto-attached by Kubernetes enroll-watch | Residual named in the matrix |
| IPv6 CIDR live dual-stack | `NOT_INDEPENDENTLY_VERIFIED` in the matrix. This package can match an IPv6 prefix on a supplied case. That match is not a kernel proof |
| Managed GKE, EKS, AKS | `TARGET_DESIGN` |

A host decision in this package requires a supplied observation. `this_force_executed_host` stays false. A case field that claims this force executed the host is `UNKNOWN`.

## What is not in this tree

`vantio-phantom-engine` is not checked out here. This force does not edit it, load eBPF, or copy `docs/operations-guide.md`.
