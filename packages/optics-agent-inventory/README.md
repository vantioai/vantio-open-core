# optics-agent-inventory

Lab-only. `schema_status` is `unstable-pre-1.0`. This package is not published and it is not Phantom Engine coverage.

It answers, for one procfs view: where recognized AI workloads are, which catalog destinations were observed, and which closed capability classes were observed. It does not store prompts, completions, headers, query strings, URL paths, or environ values. `can_do` is not a permission grant.

```bash
PYTHONPATH=packages/optics-agent-inventory/src \
  python3 -m optics_agent_inventory --host-id lab-runner --enrollment enrollment.json
```

A file under the runs directory that cannot be read holds host coverage at `partial` (`runs_unreadable`). That is fail-closed. It is not a defect in the scan.

Host `covered` describes this procfs view and this catalog. It does not mean every renamed binary was seen, and it does not mean a Phantom Engine host is enrolled.
