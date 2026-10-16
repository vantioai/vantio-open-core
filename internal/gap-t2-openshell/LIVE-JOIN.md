# T2 live join — design and file harness

Audience: INTERNAL_RESTRICTED

Date: 2026-10-16

Authorization: Founder Q11 and Q12, Lane K. A future tail runs on a Vantio-owned enrolled host only.

Lane lab seal: `6d3ce580`. Public pin stays `e0b19d55`. This note does not change either constant in the installer.

## Verdict that still holds

OpenShell and Phantom Engine stay side by side. The join is Rogue Reconciliation. This design does not put Phantom Engine inside the OpenShell supervisor, middleware, or gateway. It does not contact NVIDIA. It does not spend money.

## What "live" means here

A live join is a tail of three record streams that already exist on the host: Phantom Engine observations, OpenShell OCSF rows, and Gate rows. The streams are not a socket this package opens.

The harness in `harness/live.cjs` is the Lab-only stand-in. It reads three local NDJSON files and calls the same `reconcile` function as the closed snapshot. It does not enroll a host, load an eBPF program, or start OpenShell.

| Result | Label |
| --- | --- |
| File harness against recorded rows | Lab-only |
| OpenShell process and Phantom Engine on one enrolled host | Roadmap |
| A monotonic kernel clock with no caller-supplied offset | Lab-only. The row stays `UNATTRIBUTED` / `kernel_time_not_unix` |

## Clock

OpenShell `time` is Unix milliseconds. Phantom Engine case-study timestamps are monotonic nanoseconds. Those clocks are not the same value.

The harness converts `kernel_monotonic_ns` only when the caller passes `clockOffsetMs`:

`observed_at_ms = clockOffsetMs + floor(kernel_monotonic_ns / 1000000)`

The result has to sit in the existing Unix window or the stamp is dropped and the row stays unattributed. The offset is not learned from the records. A wrong offset can join two unrelated events inside the run window. That is R21.

Binding the clock does not let a process record cover a later network write. The bypass fixture stays `BYPASS_INDICATOR` once the kernel row has a Unix stamp. Before the offset, the same row is `UNATTRIBUTED`.

## Loss

OpenShell export is best-effort. A full 1,024-line queue drops new lines. A missing sandbox row is `BYPASS_INDICATOR` because the kernel row has no match. The harness does not repair that loss and does not treat it as proof the sandbox was bypassed on a live host.

## Host gate

`hostClass` must be `vantio-owned`. Any path containing `navera` is rejected. The harness still does not prove the machine is that host. The check is the caller's declaration plus the path refusal.

## What this does not do

- No network client.
- No package install.
- No change to the public pin, the README, or a price.
- No merge and no tag.
- AWS and GCP labs are not started. Lab agent `bc-8b310b16` owns the AWS slot through Monday.

## Risks added for this harness

| ID | Risk | Label | Exposure |
| --- | --- | --- | --- |
| R21 | A caller-supplied clock offset can join unrelated events inside the window. | Lab-only | The offset is an input, not a measurement |
| R22 | The file harness can be described as a live OpenShell run. | Roadmap for the live stack | `openshell_runtime` stays `not-executed` |
| R23 | An OCSF drop still becomes `BYPASS_INDICATOR`. | Lab-only | Absence is not a captured bypass on a live host |
| R24 | Re-reading the same files is idempotent. A concurrent append during the read is not locked. | Lab-only | Two readers can observe different prefixes. The join does not claim a total order across processes |
