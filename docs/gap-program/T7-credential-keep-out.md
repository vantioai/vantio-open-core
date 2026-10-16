# T7 — Credential keep-out

Audience: INTERNAL

Phase: 1 design only. No feature code.

Track label: Roadmap

Written: 2026-10-16T15:48:08Z

## Question

How can a supported workload hold a placeholder, pass policy, and have the real credential appear only on an approved egress, while a compromised workload still cannot read that credential?

## Current evidence

The supported observe path patches `globalThis.fetch` at require time. It does not rewrite arbitrary sockets. Public docs say a developer can skip the wrap. The installer starts Phantom Engine in observe-only mode. Path deny and traffic control stay off in that installer path.

Nothing in this tree swaps a placeholder for a secret. Nothing in this tree holds a production credential for this purpose. Phase 2 uses a mock secret created inside the test and discarded. The mock string is not a customer key and is not printed in CI logs.

Program rule: there is no required proxy hop. Tier 2 deliberately kept enforcement on the SDK side rather than putting every call through a network proxy. This design keeps that rule. Uncredentialed traffic does not gain a hop.

## Design

The workload environment and its files contain a placeholder of the form `vantio-placeholder://mock/name`. The placeholder is not a credential. Sending it to a destination is a failed closed outcome, not a success.

The real mock secret lives in a broker process:

- different uid from the workload
- no shared memory with the workload
- secret file mode readable by the broker uid only
- `ptrace` scope that the workload uid cannot attach
- not a network proxy for the host's other traffic

Flow on a supported path:

1. The workload presents the placeholder on a call the supported interceptor can see.
2. Policy runs first, with the T6 identity reference attached. `UNVERIFIED` identity, a hold from T10, or a policy deny stops the flow. The broker is not asked.
3. On allow, the broker opens the one approved connection and places the mock secret on that connection. The secret is not written back into the workload's address space, environment, or files.
4. The workload receives the call result, not the secret.

Calls that do not carry a placeholder stay on the existing path. Customers who do not use placeholders have no broker hop. For a call that does carry a placeholder, the broker is a required local hop and a single point of failure: if it is down, that call fails closed. The broker is a local process on the enrolled host. It is not a central proxy, and it is not required for Observe or for uncredentialed traffic.

An in-process swap inside the workload is rejected by this design. A compromised workload that shares the interceptor's address space can read a secret the interceptor holds. Keep-out against that workload requires the secret to stay in the broker.

Kernel payload rewrite inside TLS is not the mechanism. Current uprobes observe `SSL_write` and `gnutls_record_send`. They do not terminate TLS. This design does not add a TLS-rewriting eBPF program.

## Threat model

| Threat | What the design claims | Residual |
| --- | --- | --- |
| Workload reads its own environment and maps | The placeholder is present. The mock secret is absent | A bug that copies the secret back fails the proof |
| Workload reads the broker `/proc/<pid>/environ` or mem | Different uid and file mode return `EACCES` | Root on the host can still read both. Root is a named residual |
| Workload `ptrace`s the broker | The workload uid cannot attach | A kernel that ignores `ptrace` scope is outside the claim |
| Workload opens a raw socket with a secret it already had | Keep-out applies to secrets the broker holds. A secret the workload already possessed is outside this control | T5 covers egress of that class |
| Policy bypass by calling the broker directly | The allow bit is decided in the broker, outside the workload. The in-process interceptor may only present the placeholder and the destination metadata. A compromised workload can send that presentation. It cannot mark the presentation allowed, because the broker does not trust an allow bit that comes from the workload address space | A bug that trusts a workload-supplied allow bit fails the proof |
| Destination echoes the credential | The broker removes the exact mock secret from the response bytes before they are returned, and the proof checks those bytes | A transformed encoding of the secret can still come back. That encoding is a named residual |
| Broker used as a general proxy | The broker dials only after a placeholder allow. Other traffic is not accepted | A future patch that accepts all traffic violates the no-required-proxy rule and fails review |

## Failure modes

Fail closed on the credentialed call. Any of these deny the call and leave the mock secret in the broker: policy deny, `UNVERIFIED` identity, T10 hold, broker down, broker uid equal to the workload uid, secret file readable by the workload, or the supported path cannot see the call.

The placeholder is not forwarded to the destination. Reason: a placeholder that reaches the network is both a failed control and a confusing credential.

Uncredentialed traffic fails open relative to this control. It keeps the previous Observe or Enforce behavior. Reason: keep-out must not become a required hop for traffic that has no placeholder.

If the broker process dies mid-call, the call fails and no retry from the workload is given the secret. A retry repeats policy from the start.

## Edge cases

- Placeholder in a header the supported fetch path does not parse. The call is not treated as approved. Phase 2 lists the header sites the interceptor actually sees and denies the rest when a placeholder name is configured for them.
- Two placeholders in one call. One allow covers one named secret. A second name needs its own allow. A missing second secret fails the whole call.
- Destination changes after policy allow and before dial. The broker dials the destination that was allowed. A mismatch fails the call.
- Workload and broker share a user namespace that maps the broker uid to the workload. The proof includes the uid as seen from the workload namespace. Equal uids fail closed.
- Core dump of the broker. The design sets the broker non-dumpable in the later implementation. Phase 1 does not ship that setting. The proof plan asserts it once code exists.

## Memory footprint

The broker holds one mock secret and one in-flight request in the phase-2 test. A later implementation caps in-flight broker requests. Over the cap, new credentialed calls fail closed. This design states the cap as a parameter the implementation must set and test. It does not claim a measured RSS.

The workload's extra memory is the placeholder string. No secret-sized buffer is allocated in the workload for the real value.

## eBPF verifier limits

No new eBPF program. Verifier limits are unchanged. Do not "help" keep-out by rewriting TLS payloads in a `tc` or uprobe program. If a later force proposes that, it needs its own verifier budget, its own council, and a reason that defeats this userspace broker design.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | The broker binary and its unit file are part of the company stack. T0 hygiene applies to them. This track does not vendor a credential helper from an unreviewed agent runtime |
| T1 | The broker runs only on an enrolled host. A stranger host does not receive the mock secret file |
| T2 | The sandbox proof is the right place to show the workload uid cannot read the broker. This design does not replace T2 |
| T3 | Inventory must show the broker as a Vantio component and the workload as the enrolled agent, so an operator can see which uid holds the secret |
| T4 | A tool call is a credentialed call when it carries a placeholder. Tool awareness does not get the secret |
| T5 | Egress drills include a denied call and assert the mock secret never appears on the wire or in the workload |

T6 is also required. Policy allow is meaningless without `agent_identity` and `owner`.

## Rollback

Stop the broker. Credentialed calls fail closed. Uncredentialed traffic is unchanged. The placeholder remains in the workload and is useless. Rollback deletes the mock secret file on the lab host used for the proof. Rollback does not export the secret into a log, a core, or a support bundle.

A rollback that cannot stop the broker leaves Enforce in the failed-closed credential path: no new credentialed dials. It does not fall back to handing the secret to the workload.

## Proof plan

Phase 2 lab, mock secret only. The proof is an assertion list, not a procedure for extracting a customer secret.

1. Start the broker as uid B with a mock secret created in the test.
2. Start the workload as uid A, A different from B, with only the placeholder in its environment.
3. From uid A, assert: the secret string is absent from the environment, from readable maps, and from files the workload can open; opening the broker secret path and the broker `/proc` environ returns `EACCES`; `ptrace` of the broker fails.
4. A policy deny does not dial, and a capture on the lab interface does not contain the mock secret.
5. A policy allow dials from the broker. The workload's maps still do not contain the mock secret after the call returns. The bytes returned to the workload do not contain the exact mock secret. A gzip or otherwise transformed body is part of the encoding residual and is not a pass of this step.
6. Kill the broker. The next credentialed call fails and does not fall back to an in-process secret.

Passing this list is still Lab-only until it is repeated on an enrolled host the program allows. It is not a production claim. Root on the host remains able to read the broker. That residual stays in the report.

## Risks

- An implementation returns the secret to the interceptor "just for this request" and the proof becomes false.
- The broker grows into a required proxy for all egress.
- Logs, traces, or the T8 exporter capture the secret. The export allowlist must treat the secret and the placeholder value as forbidden bytes, the same way the observability packet treats canaries.
- A lab proof runs as root and passes by skipping the uid check.

## Approval gates

- No real credential, cloud IAM key, or customer token in any phase.
- No broker installed on a host Vantio does not own. No AWS or GCP lab from this force. Lab agent `bc-8b310b16` owns the lab slot.
- Founder decision before the broker is allowed to dial anywhere except a local mock listener.
- Draft PR only.

## Council

Verdict: PASS_WITH_NONBLOCKING_NOTES

Recorded from the Claude Opus review of design head `3c2c581a48ef001c3ef78df232926d6c236acb88`. Detail is in `COUNCIL-VERDICT.md`. The producer does not sit the council.
