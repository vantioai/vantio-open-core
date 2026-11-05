# Lab seal dispatch

`scripts/lab/seal_dispatch.py` checks a GCP lab seal and bundle commit before a person dispatches the provision workflow.

## Warning: `paste` prints the seal

`python3 scripts/lab/seal_dispatch.py paste` prints the seal on standard output on purpose. The line is the whole operator paste:

```text
seal=<64 lowercase hex characters> bundle_commit=<40 lowercase hex characters>
```

Run that command in the operator's own terminal. The seal is the public digest recorded in `release/pe-seal-history.json`. It is not a credential. Do not send that line to a GitHub Actions log, a job output, a step summary, or a step environment file.

`paste` refuses when `GITHUB_ACTIONS=true`. It then prints only lengths and `pass` or `fail`, and it exits non-zero. The provision workflow does not call `paste` or `seal_dispatch.py`.

The `sealcheck` job prints only `seal_len=<n> result=pass|fail`. That job has no outputs. Its step does not write `GITHUB_OUTPUT`, `GITHUB_STEP_SUMMARY`, or `GITHUB_ENV`, and it does not echo the seal. `check` and `check-pasted` print lengths and `pass` or `fail` only.

Actions step debug (`ACTIONS_STEP_DEBUG=true`) makes the runner print a step's environment. The `sealcheck` step environment includes `SEAL`. Leave step debug off for this workflow so that environment is not copied into the log. Do not rely on log masking. The workflow input is not a secret, and this step does not mask it.
