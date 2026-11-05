# Lab seal dispatch

`scripts/lab/seal_dispatch.py` checks a GCP lab seal and bundle commit before a person dispatches the provision workflow.

## Warning: `paste` prints the seal

`python3 scripts/lab/seal_dispatch.py paste` prints the seal on standard output on purpose. The line is the whole operator paste:

```text
seal=<64 lowercase hex characters> bundle_commit=<40 lowercase hex characters>
```

Run that command in the operator's own terminal. The seal is the public digest recorded in `release/pe-seal-history.json`. It is not a credential. Do not send that line to a GitHub Actions log, a job output, a step summary, or a step environment file.

`paste` refuses when `GITHUB_ACTIONS=true`. It then prints only lengths and `pass` or `fail`, and it exits non-zero. The provision workflow does not call `paste` or `seal_dispatch.py`.

The `sealcheck` job prints only `seal_len=<n> result=pass|fail`. That job has no outputs. Its check step does not write `GITHUB_OUTPUT`, `GITHUB_STEP_SUMMARY`, or `GITHUB_ENV`, and it does not echo the seal. `check` and `check-pasted` print lengths and `pass` or `fail` only.

## Require main

`sealcheck` runs `Require main on vantio-open-core` before it reads the seal. The step is the same four checks `fetch` and `teardown` run before they authenticate. The event is `workflow_dispatch`, the repository is `vantioai/vantio-open-core`, the ref is `refs/heads/main`, and the workflow ref is this file on `main`. The job has no cloud credentials. A failed step fails the job, so `fetch`, `gate`, and `deliver` stay skipped. `teardown` still runs because its `if` is `always()`.

## Log mask

`fetch` and `deliver` pass the workflow input as `EXPECTED_SEAL`. `fetch` also passes it as `W3_EXPECTED_SEAL`. Each of those jobs runs `Mask the seal input` as the first step whose environment contains the value, after `Require main`. When the value is 64 lowercase hex characters, the step writes one workflow command: `::add-mask::` followed by the value. The runner consumes that command. Later log text in the same job that contains the same string is redacted, including a step-debug environment line from a later step. A value that is not 64 lowercase hex characters prints `seal_len=<n> result=fail` and fails the job. The failure line does not contain the value.

`::add-mask::` does not cover the mask step's own step-debug environment. The runner writes that environment before the script, so a line emitted before the command still shows the value. Leave `ACTIONS_STEP_DEBUG` off.

A mask does not cross jobs. `sealcheck` keeps the value in `SEAL` on the check step and does not call `::add-mask::`. That step holds `SEAL`, and the job has no later step that reads it. A command in the check step would run after the runner had already written the debug environment, so it would not hide that dump. `gate` and `teardown` do not receive the seal.

The command does not remove the workflow input. It does not remove the fetch job output `seal_sha256`. Those stay on the run. Redaction applies to log text after the command, not to the Actions output panel. The input is not a GitHub Actions secret. Do not copy it into a secret to get a mask.

`w3-lab-auto-arm.yml` rejects an empty, short, or non-hex seal in `Check the seal input` before checkout and before any arm step. Failure prints `seal_len=<n> result=fail` and does not write `::add-mask::`. Success prints the length line and then the mask command, so later steps on that runner are covered and the Actions log of this step is the length line. `Read the canonical seal` does not substitute `lane_seal.sha256` for an empty input. It rejects that input again and prints the length only. An empty public pin still uses `public_pin.archive_sha256`. The canonical step writes `seal=` to `GITHUB_OUTPUT` so later steps can read the digest. That file is the step output, not the log. The same pre-script debug limit applies to `Check the seal input`, because that step's environment holds `SEAL`.

A diagnostic that prints workflow inputs before the first user step cannot be masked from inside a step. This page does not claim that diagnostic is covered.
