# Vantio AI — Standard Operating Procedure
## Tier 01 (Developer SDK) and Tier 03 (Phantom Engine)

**Version:** 1.0  
**Last Updated:** May 28, 2026  
**Applies To:** Internal engineering, client onboarding, external developers

---

## Table of Contents

1. [Tier 01 — Developer SDK](#tier-01--developer-sdk)
   - [Prerequisites](#tier-01-prerequisites)
   - [Installation](#tier-01-installation)
   - [Verification](#tier-01-verification)
   - [Running an Agent](#tier-01-running-an-agent)
   - [Interpreting Output](#tier-01-interpreting-output)
   - [Troubleshooting](#tier-01-troubleshooting)

2. [Tier 03 — Phantom Engine](#tier-03--phantom-engine)
   - [Prerequisites](#tier-03-prerequisites)
   - [Build](#tier-03-build)
   - [Startup Sequence](#tier-03-startup-sequence)
   - [Injecting a Trace Context](#tier-03-injecting-a-trace-context)
   - [Verifying Interception](#tier-03-verifying-interception)
   - [Stopping the Engine](#tier-03-stopping)
   - [Troubleshooting](#tier-03-troubleshooting)

3. [Quick Reference](#quick-reference)

---

## Tier 01 — Developer SDK

### What it does

Tier 01 wraps any AI agent process and automatically intercepts every outbound call to a known LLM provider (OpenAI, Anthropic, Gemini, Cohere, Mistral, Groq, etc.). No code changes required. The CLI patches `globalThis.fetch` at Node.js startup via `--require` injection.

---

### Tier 01 Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Node.js | ≥ 18.3.0 | Required for native `fetch` support |
| npm | Any | Used to install the CLI |
| Internet access | — | For LLM API calls to be intercepted |

---

### Tier 01 Installation

```bash
# Install the CLI globally
npm install -g @vantio/cli

# Verify installation
vantio --help
```

Expected output:
```
Vantio AI — process supervisor

Usage:
  vantio run [flags] <program> [...args]
...
```

Optionally install the Node.js SDK for explicit trace correlation:
```bash
npm install @vantio/agent-sdk
```

For Python agents:
```bash
pip install vantio-agent-sdk
```

---

### Tier 01 Verification

Run the following to confirm the interceptor is working without any API key:

```bash
# Create a minimal test agent
cat > /tmp/agent-test.js << 'EOF'
fetch('https://api.openai.com/v1/models', {
  headers: { 'Authorization': 'Bearer test' }
}).then(r => console.log('status:', r.status)).catch(() => {});
EOF

# Run it through Vantio
vantio run --summary node /tmp/agent-test.js
```

**Expected output (free tier — no API key):**
```
[ ∅ VANTIO ] Outbound LLM call intercepted
  host:    api.openai.com
  pid:     XXXXX
  bytes:   237
  time:    2026-05-28T...
  → Set VANTIO_API_KEY to route events to your dashboard.

[ ∅ VANTIO ] Run Summary
  LLM calls:    1
  Hosts:        api.openai.com
  Total bytes:  237
  Duration:     0.5s
  → Upgrade at vantio.ai to persist events to your dashboard.
```

✅ **Tier 01 is operational** when the intercept message appears.

---

### Tier 01 Running an Agent

**Zero-code integration:**
```bash
vantio run node agent.js
vantio run python agent.py
vantio run tsx agent.ts
```

**With audit mode (flags all events as under review):**
```bash
vantio run --audit node agent.js
```

**With run summary on exit:**
```bash
vantio run --summary node agent.js
```

**With cloud routing (Tier 02 — requires API key):**
```bash
export VANTIO_API_KEY=vantio_xxxxxxxxxxxx
export VANTIO_INGEST_URL=https://vantio.ai
export VANTIO_CLOUD_INGEST=true
vantio run node agent.js
```

**Supported runtimes:** `node`, `npx`, `tsx`, `ts-node`  
**Pass-through (no interception):** `python`, `ruby`, `go`, `java`, and all other runtimes

---

### Tier 01 Interpreting Output

| Field | Meaning |
|---|---|
| `host` | LLM API endpoint that was called |
| `pid` | Process ID of the intercepted process |
| `bytes` | Response `Content-Length` in bytes |
| `time` | ISO 8601 timestamp of the call |
| `LLM calls` | Total outbound LLM calls in the run |
| `Total bytes` | Sum of all response sizes |
| `Duration` | Wall-clock time from process start to exit |

**What is NOT captured:** prompt content, completion content, or any data from the request/response body. Only metadata.

---

### Tier 01 Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No intercept output | Runtime is not Node.js | Use `node`, `tsx`, or `ts-node` as the program |
| `vantio: command not found` | Global install didn't land in PATH | Run `npm install -g @vantio/cli` and restart terminal |
| Events not appearing in dashboard | `VANTIO_CLOUD_INGEST` not set | Set `VANTIO_CLOUD_INGEST=true` |
| `ReferenceError: fetch is not defined` | Node.js < 18 | Upgrade to Node.js ≥ 18.3.0 |
| `-e` flag error | CLI consuming child flags | Update to `@vantio/cli@0.1.2` or later |

---

---

## Tier 03 — Phantom Engine

### What it does

Tier 03 deploys a pure-Rust eBPF hypervisor into the Linux kernel. It attaches three programs simultaneously:

1. **`sched_process_fork` tracepoint** — propagates trace context from parent to child PIDs automatically
2. **`ssl_write` uprobe on libssl.so.3** — intercepts TLS egress at the OpenSSL boundary
3. **`gnutls_record_send` uprobe on libgnutls.so.30** — intercepts TLS egress at the GnuTLS boundary
4. **TC egress classifier** — network-layer enforcement (audit or drop mode)

---

### Tier 03 Prerequisites

| Requirement | Version/Value | Notes |
|---|---|---|
| OS | Linux (Ubuntu 22.04+, Amazon Linux 2, RHEL 8+) | Bare metal or WSL2 |
| Kernel | ≥ 5.8 | Required for ring buffer support |
| BTF | `/sys/kernel/btf/vmlinux` must exist | Most kernels since 5.8 include it |
| BPF filesystem | `/sys/fs/bpf` mounted | May need manual mount on WSL2 |
| Root access | `sudo` | Required to load eBPF programs |
| Rust toolchain | nightly | For building from source |
| `bpf-linker` | 0.10.x | Installed via `cargo install bpf-linker` |
| libssl.so.3 | OpenSSL 3.x | Uprobe target |
| libgnutls.so.30 | GnuTLS 3.x | Uprobe target (Ubuntu 24.04+) |

**Verify prerequisites:**
```bash
# Kernel version
uname -r
# Should be ≥ 5.8

# BTF support
ls /sys/kernel/btf/vmlinux && echo "BTF OK"

# BPF filesystem
ls /sys/fs/bpf && echo "BPFfs mounted"

# TLS libraries
ldconfig -p | grep -E "libssl.so.3|libgnutls.so.30"
```

---

### Tier 03 Build

Run all commands from within WSL (Ubuntu) or directly on a Linux machine.

```bash
cd /home/zach_vantio/vantio-phantom-engine
```

**Step 1 — Build the eBPF kernel crate:**
```bash
unset CARGO_TARGET_DIR
cargo build -p vantio-phantom-engine \
  --target bpfel-unknown-none \
  -Z build-std=core \
  --release
```

**Step 2 — Patch the ELF (required for this kernel/linker combination):**
```bash
python3 -c "
data = bytearray(open('target/bpfel-unknown-none/release/vantio-phantom-engine','rb').read())
if data[7] != 0:
    data[7] = 0
    open('target/bpfel-unknown-none/release/vantio-phantom-engine','wb').write(data)
    print('ELF patched')
else:
    print('ELF OK')
"
```

**Step 3 — Build the userspace loader:**
```bash
cargo build -p vantio-loader --release
```

**Verify binaries exist:**
```bash
ls -lh target/release/vantio-loader
ls -lh target/bpfel-unknown-none/release/vantio-phantom-engine
```

---

### Tier 03 Startup Sequence

```bash
# Step 1 — Mount BPF filesystem (WSL2 only; bare metal usually pre-mounted)
sudo mount -t bpf bpf /sys/fs/bpf 2>/dev/null || true

# Step 2 — Generate a session trace ID
export VANTIO_TRACE_ID=0x$(openssl rand -hex 8)
echo "Session Trace ID: $VANTIO_TRACE_ID"

# Step 3 — Start the loader
sudo VANTIO_TRACE_ID=$VANTIO_TRACE_ID ./target/release/vantio-loader
```

**Expected startup output:**
```
Seeded pid XXXXX → trace_id 0xXXXXXXXXXXXXXXXX
  gnutls   : gnutls_record_send uprobe (libgnutls.so.30)
[ ∅ VANTIO ] Phantom Engine active
  trace map  : /sys/fs/bpf/vantio_trace_map
  fork probe : sched_process_fork (BTF tracepoint)
  tls probe  : SSL_write uprobe (libssl.so.3)
  tc enforce : AUDIT (log only) iface 'eth0' [🟡]
  press Ctrl-C to stop

PID                   Trace ID          Action         Bytes  Timestamp (ns)
────────────────────────────────────────────────────────────────────────
```

✅ **Phantom Engine is active** when this table header appears.

**Optional flags:**
```bash
# Enforce mode — drops packets to non-allowlisted IPs
sudo VANTIO_TRACE_ID=$VANTIO_TRACE_ID ./target/release/vantio-loader --enforce

# Different network interface (default: eth0)
sudo VANTIO_TRACE_ID=$VANTIO_TRACE_ID ./target/release/vantio-loader --iface ens5

# Custom IP allowlist (beyond RFC-1918 defaults)
sudo VANTIO_TRACE_ID=$VANTIO_TRACE_ID ./target/release/vantio-loader \
  --allowlist 93.184.216.34,8.8.8.8

# Write events to NDJSON for Spanner import
sudo VANTIO_TRACE_ID=$VANTIO_TRACE_ID ./target/release/vantio-loader \
  --output-file /var/log/vantio/events.ndjson

# Live Spanner write (Enterprise)
sudo GOOGLE_SPANNER_DATABASE=projects/P/instances/I/databases/D \
     GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json \
     VANTIO_TRACE_ID=$VANTIO_TRACE_ID \
     ./target/release/vantio-loader --enforce
```

---

### Tier 03 Injecting a Trace Context

With the loader running, inject any process into the trace map from a second terminal:

```bash
# Inject by PID
sudo /path/to/vantio-loader --inject $VANTIO_TRACE_ID <PID>

# Example: inject the current shell
sudo ./target/release/vantio-loader --inject $VANTIO_TRACE_ID $$

# Example: inject a running agent
sudo ./target/release/vantio-loader --inject $VANTIO_TRACE_ID $(pgrep -f "node agent.js")
```

Once injected, any TLS write from that PID (or its children, if fork inheritance is working) will appear in the loader's event table.

---

### Tier 03 Verifying Interception

**Verified interception output (case study — May 28, 2026):**
```
PID                   Trace ID          Action         Bytes  Timestamp (ns)
────────────────────────────────────────────────────────────────────────
257186      0x1234567890abcdef         SEVERED           103  74594084443157
257186      0x1234567890abcdef         SEVERED            26  74594084662580
257186      0x1234567890abcdef         SEVERED             9  74594101730734
257186      0x1234567890abcdef         SEVERED            26  74594105401352
```

| Column | Meaning |
|---|---|
| `PID` | Kernel PID of the process that called SSL_write |
| `Trace ID` | The VANTIO_TRACE_ID associated with this process |
| `Action` | `SEVERED` (audit mode) or `HARD_DROP` (enforce mode) |
| `Bytes` | Number of bytes in the SSL_write call |
| `Timestamp (ns)` | `bpf_ktime_get_ns()` — nanoseconds since kernel boot |

---

### Tier 03 Stopping

Press `Ctrl-C` in the loader terminal. The loader will:

1. Detach all eBPF programs (tracepoint, uprobes, TC classifier)
2. Print: `Detached cleanly. Pinned map remains at /sys/fs/bpf/vantio_trace_map.`

The pinned map persists at `/sys/fs/bpf/vantio_trace_map` until the BPF filesystem is unmounted or the system reboots. This is intentional — it allows `--inject` to work without restarting the loader.

---

### Tier 03 Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `error parsing ELF data` | Old binary / wrong ELF alignment | Rebuild both crates from source; patch OSABI byte |
| `failed to pin map: File exists` | Stale pin from previous run | Loader now auto-removes stale pin on startup |
| `failed to add clsact qdisc: File exists` | Qdisc left from previous run | Loader ignores this error (idempotent) |
| `BPF_PROG_LOAD failed: invalid size of register spill` | BTF tracepoint arg mismatch | Rebuild — regular tracepoint is used, not BTF variant |
| `unknown func bpf_get_current_pid_tgid` | Called from TC classifier | Fixed in current build — TC doesn't use this helper |
| `failed to pin map: No such file or directory` | BPF filesystem not mounted | Run: `sudo mount -t bpf bpf /sys/fs/bpf` |
| No events appear after inject | PID namespace offset (WSL2) | Loader uses `/proc/PID/sched` for global PID — rebuilt binary handles this |
| Events show `0xffff000000XXXXXX` trace ID | Fallback PID encoding (diagnostic mode) | Use production build — filter is active |
| Uprobe not firing for curl | curl uses GnuTLS, not OpenSSL on Ubuntu 26.04 | GnuTLS uprobe is now attached alongside OpenSSL |

---

---

## Quick Reference

### Tier 01 — One-liner

```bash
# Install once
npm install -g @vantio/cli

# Run any agent
vantio run --summary node agent.js
```

### Tier 03 — Startup sequence

```bash
cd /home/zach_vantio/vantio-phantom-engine
sudo mount -t bpf bpf /sys/fs/bpf 2>/dev/null || true
export VANTIO_TRACE_ID=0x$(openssl rand -hex 8)
sudo VANTIO_TRACE_ID=$VANTIO_TRACE_ID ./target/release/vantio-loader
```

### Tier 03 — Rebuild sequence (after source changes)

```bash
cd /home/zach_vantio/vantio-phantom-engine
unset CARGO_TARGET_DIR
cargo build -p vantio-phantom-engine --target bpfel-unknown-none -Z build-std=core --release
python3 -c "
data = bytearray(open('target/bpfel-unknown-none/release/vantio-phantom-engine','rb').read())
if data[7] != 0: data[7] = 0; open('target/bpfel-unknown-none/release/vantio-phantom-engine','wb').write(data)
"
cargo build -p vantio-loader --release
```

### Supported LLM providers (Tier 01 auto-intercept)

| Provider | Hostname |
|---|---|
| OpenAI | `api.openai.com` |
| Anthropic | `api.anthropic.com` |
| Google Gemini | `generativelanguage.googleapis.com` |
| Cohere | `api.cohere.ai` |
| Mistral | `api.mistral.ai` |
| Groq | `api.groq.com` |
| Together AI | `api.together.xyz` |
| Perplexity | `api.perplexity.ai` |
| Azure AI | `inference.ai.azure.com` |

---

*Vantio AI, Inc. — Delaware C-Corporation*  
*security@vantio.ai*
