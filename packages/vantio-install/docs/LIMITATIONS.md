# Limitations

This installer starts Phantom Engine in observe-only mode. Enforcement stays off. OTLP stays disabled. Path deny stays disabled. Traffic control stays audit-only.

`proof_state` in the JSON is `NOT_PROVED`. The proof ceiling recorded on the transaction is `INTERNAL_CLEAN_HOST_PROOF`. A local fixture run does not raise that ceiling.

Hosts with less than 3 GiB of memory are recorded as a bounded-memory limitation. Full resource sufficiency stays outside that result.

The sealed Phantom Engine archive, manifest digest, and Optics package versions are pinned. A hash or tip mismatch stops the install. GHCR tag 0.1.0 is not a source. A transfer that needs a network path must list operator allowlisted source CIDRs, and `0.0.0.0/0` is refused.

Live changes on a host (Docker load, package install, BPF, traffic control) stay disabled until a later authorized clean-host run. Source tests exercise the transaction with a fixture host.
