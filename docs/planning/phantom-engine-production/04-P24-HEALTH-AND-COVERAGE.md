# P24 — health and coverage

Audience: INTERNAL_RESTRICTED

Producer classification: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

Status: `PLAN_ONLY`. No loader was started. No probe was curled. No ledger row was written.

## 1. Three health channels stay separate

P24 has three channels. A green value on one channel does not fill the others.

| Channel | Where it is specified | What a fresh value means |
| --- | --- | --- |
| Node liveness file | Raw DaemonSet and Helm template probe `/run/vantio/heartbeat`, age under 60 seconds, together with pinned map `/sys/fs/bpf/vantio_trace_map`. Initial delay 20 seconds, period 30 seconds. Raw manifest sets `failureThreshold: 3`. The Helm template does not set `failureThreshold` | The loader process refreshed a file and the map pin exists. It does not mean workloads are enrolled, enforcement is latched, or a cloud ledger accepted a row |
| Protection state | `python/pe_protection_state.py` `STATES` | One of the nine names in `05-SHARED-HEALTH-VOCABULARY.md`. Missing enroll is `not_enrolled`. A missing loader after `protected` stays off the `observing` name |
| Optional control-plane heartbeat | Named in the `CUSTOMER_SHIPPED` operations guide (blob `1b973342b3bf7f6aa6cdad70de49fa6e26db0077`) | A dashboard signal when a cloud ingest URL is configured. Interval and event names stay in that private document. This packet does not copy them. The file probe’s 60-second window is a different clock |

`CONFLICT-HEARTBEAT-PATH` in the access inventory is a P24 defect. Manifests probe `/run/vantio/heartbeat`. The operations guide troubleshooting table names another filename. Until those bytes match, a health reader uses the manifest path for DaemonSet liveness and records the guide filename as unresolved drift. This plan does not patch the private files.

## 2. Protection-state rules already in source

The evaluator in `python/pe_protection_state.py` is the coverage state machine. Planning consequences:

- `coverage_unknown` is the state when the loader is not installed, and the fallback when a computed name is outside `STATES`.
- `not_enrolled` is the state when the loader is present and no enrolled workload is named.
- `observing` is enrolled without enforcement latched.
- `protected` requires enrolled, enforcement latched, loader up, a reachable required control plane, writable evidence, and no policy drift from last-known.
- `degraded` covers loader loss, malformed policy, required control-plane failure, and unwritable evidence.
- `protection_stale` covers a proof older than the current boot.
- `policy_stale` covers a policy version drift from last-known applied policy.
- `quarantined` wins when the quarantine marker is active. The register’s F-10 key fact is `dual_control_executor_wired=False` on `pe_scoped_quarantine.py`. A quarantine marker is not a wired dual-control executor.
- `recovery_required` covers an upgrade-in-progress flag.
- `stranger_host_present` is set false in `collect_facts`.
- `compatibility_status` is `internally_proven` on the company-host name set and `not_stranger_proven` otherwise.
- Spoken output that contains a banned claim forces `coverage_unknown`. Banned tokens in that module include universal coverage, generic EDR, action reversal, a stranger-host pass, third-party notarization, and worm storage.

`docs/enterprise/P0_INVENTORY.md` honesty constraints match that fence: local NDJSON is append-oriented; Spanner live write is `TARGET_DESIGN`; certifications are not held; an internal test is not stranger-host proof.

## 3. Coverage matrix

`COVERAGE-MATRIX.json` is the row list. Every row this force could check in-repo is `this_force: NOT_EXECUTED` and `evidence_class: OBSERVED_FROM_REPOSITORY_EVIDENCE` or `NOT_INDEPENDENTLY_VERIFIED` as the private documents already labeled them.

Scope labels used in the matrix:

| `platform_scope` | Meaning |
| --- | --- |
| `REPOSITORY_ONLY` | Read from git. No process started |
| `WSL2_PRIVILEGED` | Claim in the architecture matrix for the privileged WSL2 host |
| `KIND_LOCAL` | Claim for local `kind` on that same class of host. Not GKE, EKS, or AKS |
| `REFERENCE_HOST` | Company host the enterprise script calls its reference host. Not read live here |
| `MANAGED_CLOUD` | GKE, EKS, or AKS |
| `STRANGER_HOST` | A Linux host Vantio does not operate |

Managed-cloud and stranger-host columns in this packet are `UNVERIFIED`. Findings F-14, F-15, F-16, and F-17 in the remediation register are `BLOCKED` on those environments. This wave’s P2 prerequisite work and those audit findings share the environments. They do not share an ID.

## 4. Coverage that must stay named when a later health command runs

A later health command, after authorization, prints the protection state and a `not_covered` list. The source module already requires these to stay named:

- Workloads that were never enrolled
- Windows and macOS
- A privileged operator on the host who can stop the loader
- Kubernetes and VM shapes that were not stranger-proved
- External calls already sent (no action reversal)
- Company-host proof offered as stranger-host proof

P24 adds these planning rows to that list until a later force closes them with a new evidence class:

- Image digest not pinned (P1)
- `kind` rows offered as managed-cloud rows
- Control-plane heartbeat offered as node liveness
- Verifier result `BLOCKED` offered as enforcement `ActionTaken` `BLOCKED`
- Optics display token `OBSERVED` offered as protection state `protected`

## 5. Ledger health

Local NDJSON is the evidence plane the cloud checklist calls verified in-repo. Spanner insert remains `TARGET`. A health fact for the ledger uses `subject` `LEDGER` and must not use the word WORM for the local file. Schema alignment in git is `REPOSITORY_ONLY`. A live commit timestamp is a different fact and is `UNVERIFIED`.
