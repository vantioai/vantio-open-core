# Policy guide

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Policy has two places:

1. **Host controls** on `vantio-loader` (this document).
2. **Application-path controls** (hostname block, redaction, spend or size caps) in the bundled on-prem component. That component applies policy in process. Phantom Engine is not a network proxy for that path. This manual does not publish that component's policy schema. The schema ships with the authorized pack and was not re-validated while this manual was written.

A dry-run evaluator shipped as `@vantio/gate-mcp` in the public Optics repository can ask whether a call would be blocked. It does not block live traffic. Live application-path enforcement is the on-prem component. Live host drops are the loader flags below.

## Host modes

| Mode | How you set it | Behavior | Default |
|---|---|---|---|
| Audit | Omit `--enforce`, Helm `enforce=false` | Log only. Egress is not dropped. | Chart default and bare-metal default |
| Scoped | `--enforce`, or Helm `enforce=true` | Drop egress **from enrolled cgroups** to destinations outside the private ranges and your allow rules. Unenrolled traffic passes. | Off |
| Node-wide | `--node-wide-enforcement`, or Helm `nodeWideEnforcement=true` | Drop non-allowlisted egress on the interface for every cgroup. Can sever the node. Overrides scoped mode when set. | Off |

Audit is **observed**. Scoped and node-wide are **enforced** only while the loader is running with that flag and the program is attached. If the process is stopped, the probes detach on a clean shutdown. Do not assume a killed process left the previous mode in force. See [INCIDENT-RESPONSE.md](./INCIDENT-RESPONSE.md).

Lab evidence (**independently tested**): scoped mode dropped an enrolled cgroup's egress to a non-allowlisted address and passed that same destination before enrollment and after unenrollment. Node-wide mode has a lab drop record. Both remain **customer validated**: none.

Never enable either enforcement mode on control-plane nodes. Leave `scheduleOnControlPlane` false.

Validate enrollment and the allow rules in audit before you set `enforce=true`.

## Destinations that are always permitted

These ranges are permitted without an allowlist entry:

| Family | Ranges |
|---|---|
| IPv4 | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16` |
| IPv6 | `fc00::/7` (ULA), `fe80::/10` (link-local) |

Enforcement evaluates IPv4 and IPv6. An AAAA answer is in scope of the classifier when the program is attached. IPv6 **CIDR** allowlist behavior on a live dual-stack network is **not tested**. Exact IPv6 addresses in `--allowlist` are implemented; treat a live IPv6 allow as **customer validated** only after you test it.

## Allow rules

Exact addresses (IPv4 and IPv6), Helm `customAllowlist` or loader `--allowlist`:

```bash
sudo VANTIO_TRACE_ID="$VANTIO_TRACE_ID" ./target/release/vantio-loader \
  --iface eth0 --enforce \
  --allowlist 93.184.216.34,2606:4700:4700::1111
```

CIDR ranges, loader `--allow-cidr` (longest prefix match):

```bash
sudo VANTIO_TRACE_ID="$VANTIO_TRACE_ID" ./target/release/vantio-loader \
  --iface eth0 --enforce \
  --allow-cidr 52.0.0.0/8,2620:1ec::/36
```

IPv4 CIDR prefix-boundary behavior is **independently tested** on the lab host (`1.1.1.0/24`: an in-prefix address passed, an unrelated address was dropped, and the next address outside the prefix was dropped). IPv6 CIDR on a live network is **not tested**. Helm 0.1.1 has no `allow-cidr` value. Setting CIDR allow on Kubernetes means a command override beyond the chart values. That override is **not tested** as a chart setting.

`--sever-cidr` is a hard-block list applied before the allowlist. An allow entry does not override it. It is unset unless you pass it. It is not a Helm value.

`--block-port` blocks listed TCP destination ports on enrolled or node-wide egress. It does not inspect payload contents. It is unset unless you pass it. It is not a Helm value.

## Control path protection

You can configure filesystem path prefixes that the host refuses. The match is **host-wide**. It is not scoped to enrolled cgroups. A process outside the pilot can hit a prefix you listed.

Full path canonicalization (every link, rename race, and alternate path form) is **unavailable**. Assume a prefix matches the path string the kernel call presents, and review prefixes in the architecture review before you enable them.

Process termination after a path refusal is a separate switch. It stays off unless you set both the loader flag `--kill-on-enforce` and the protection switch `VANTIO_PHANTOM_DENY=1`. Shipped unit defaults and the Helm chart do not enable it. Leave it off unless the architecture review has accepted process termination. It is not a substitute for scoped network policy.

## Keyword mark

`--tls-sever-keyword` is an optional mark. The loader inspects a short prefix of a plaintext TLS write. A match marks the process so later egress can be dropped. The write that matched is not stopped. The flag is unset unless you pass it. It is not a content firewall and it is not a Helm value.

Do not treat this flag as coverage of an encrypted body, of a write that never reaches the OpenSSL or GnuTLS probe, or of a library the probe did not attach to.

## Application path versus host path

| Situation | What you get |
|---|---|
| Process is wired to the on-prem policy and the call matches a block, redact, or cap | **enforced** in process (`BLOCKED` or `REDACTED`, or a cap outcome) |
| Process is not wired | No application-layer record. If the host probe sees the transmission, Rogue Reconciliation names the gap `BYPASS_INDICATOR` when a comparison is performed. The comparison service is **unavailable**; a lab demo has produced the label. |
| Workload is enrolled and scoped enforce is on and the destination is outside allow rules | **enforced** at the host, for traffic the classifier can attribute |
| Workload is not enrolled | Passed by scoped mode, even if application policy would have blocked a wired call |
| Audit mode | **observed** only |

Author policy, run a dry-run, then enforce. The public dry-run tool does not flip the host into `--enforce`.

## Signal Share

`telemetry.signalShare.enabled` is false in the shipped values. The loader does not transmit Signal Share in this version. Leave the value false. A customer override plus a consent addendum is the only documented future gate, and the send path remains **unavailable**.
