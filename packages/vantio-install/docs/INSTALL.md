# Install

Copy the bundle onto the host. Set `iface` in the config to a network interface that is up on that host, and set `workload_roots` to absolute directories you own.

`vantio-install plan --bundle <bundle> --config <config> --json` checks the host, the artifact hashes, and the config. It writes `PLAN.json` and `PREFLIGHT.json` under the evidence directory. It does not install Optics or start Phantom Engine.

Exit 0 means the transaction reached `PLANNED`. A blocked or unsupported host returns a non-zero exit and a JSON `state` you can read.

When the plan is acceptable, run `vantio-install apply --transaction-id <id> --yes --json`. Apply asks for `--yes` so a plan is not executed by accident. The default mode is observe-only, and enforcement stays `NOT_ENABLED`.

Apply is finished only when `state` is `HEALTHY` or `DEGRADED` and `HEALTH.json` records that result. `APPLIED` means the steps ran and health is not confirmed yet.
