# Deployment guide

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

Install only on Linux you own, after the architecture review. Start in audit mode. Enrollment and enforcement are separate steps ([ENROLLMENT-GUIDE.md](./ENROLLMENT-GUIDE.md), [POLICY-GUIDE.md](./POLICY-GUIDE.md)).

Commands below refer to the private product repository `vantioai/vantio-phantom-engine`. They are not commands in the public Optics tree.

## 1. Check the host

```bash
uname -r
stat -fc %T /sys/fs/cgroup
ls /sys/kernel/btf/vmlinux
ls /sys/fs/bpf
ldconfig -p | grep -E "libssl.so.3|libgnutls.so.30"
sudo -n true
```

Expected: kernel 5.8 or later, `cgroup2fs`, BTF present, bpffs present, at least one of the two TLS libraries, and a working sudo or the three capabilities in [SUPPORTED-ENVIRONMENTS.md](./SUPPORTED-ENVIRONMENTS.md). Install `curl` on the host. The loader runs a short `curl` at startup to calibrate process identity. The loader's own HTTP client does not use OpenSSL or GnuTLS, so it cannot perform that calibration.

```bash
sudo mount -t bpf bpf /sys/fs/bpf 2>/dev/null || true
```

## 2. Choose an install path

| Path | When | Status |
|---|---|---|
| A. Container image via Helm | Kubernetes workers | Chart render and a local `kind` run are **independently tested**. Your cluster is **not tested** until you validate it. |
| B. Build `vantio-loader` from the private repository | Bare metal or a host where you do not want the chart | Lab builds are **independently tested**. |

Pull `ghcr.io/vantioai/vantio-phantom-engine:0.1.0` only. Do not use `:latest`. If the cluster cannot pull the tag, stop and use the digest supplied with your subscription. This manual does not publish an image.

A complete node also runs the bundled on-prem Enforce component from the authorized customer pack. The Helm release does not start that component. Its health URL, when the pack is running, is `http://127.0.0.1:5001/health` unless you override `GATE_ONPREM_URL` or `VANTIO_PRO_PORT`. Call the node install complete only after that health check passes and the loader is Ready. The pack scripts are not in the public Optics repository and are not repeated here.

## 3. Kubernetes (Helm)

From a checkout of the private product repository at commit `631e435315cd780d83d3259e111893c1d0569bc3` or a later commit you have been told to run:

```bash
kubectl create namespace vantio

kubectl create secret generic vantio-secrets -n vantio \
  --from-literal=VANTIO_TRACE_ID=0x$(openssl rand -hex 8)

helm upgrade --install vantio-phantom-engine ./deploy/helm \
  --namespace vantio \
  --set image.tag=0.1.0 \
  --set nodeIface=eth0 \
  --set enforce=false \
  --set nodeWideEnforcement=false \
  --set enrollWatch=true \
  --set scheduleOnControlPlane=false \
  --set sovereignMode=local \
  --set outputFile=/run/vantio/events.ndjson \
  --set telemetry.signalShare.enabled=false
```

Set `nodeIface` to the node interface you measured (`eth0`, `ens5`, or another name). Helm writes that string into the container arguments.

The raw file `deploy/kubernetes/daemonset.yaml` passes the interface as the literal token `$(NODE_IFACE)` in an exec-form command list. Kubernetes does not shell-expand that token, and the loader does not read `NODE_IFACE` as a substitute for `--iface`. If you apply the raw manifest, replace the interface argument with the real name before apply. Prefer Helm.

`outputFile=/run/vantio/events.ndjson` is on the chart's writable `emptyDir`. That file is ephemeral. See [BACKUP-AND-RECOVERY.md](./BACKUP-AND-RECOVERY.md). Leave `spannerDatabase` empty until a live insert has been validated in your project. Live Spanner insert is **not tested**.

`telemetry.signalShare.enabled` must stay `false`. The loader does not send Signal Share in this version.

Confirm:

```bash
kubectl get pods -n vantio -o wide
kubectl logs -n vantio daemonset/vantio-phantom-engine
```

The loader is up when the log shows the engine active and the event table header. In audit mode the log line for the classifier says audit (log only). A Ready pod means the liveness probe sees the pinned trace map and a heartbeat file newer than 60 seconds. The heartbeat is refreshed about every 15 seconds at `/run/vantio/heartbeat`.

The ServiceAccount may `get`/`list` nodes and `get`/`list`/`watch` pods. That is the enroll-watch permission. It is not a cluster-admin binding.

## 4. Bare metal (build)

Requirements: Rust nightly, `rust-src`, and a prebuilt `bpf-linker` installed with `cargo binstall` (the same approach as the image build). Building `bpf-linker` from source is not the supported path.

```bash
git clone git@github.com:vantioai/vantio-phantom-engine.git
cd vantio-phantom-engine
git checkout 631e435315cd780d83d3259e111893c1d0569bc3

cargo build -p vantio-loader --release
```

That build compiles the kernel programs and checks the embedded object. If the loader reports that the embedded object is the wrong format, rebuild with the same command. Do not hand-edit the binary.

```bash
export VANTIO_TRACE_ID=0x$(openssl rand -hex 8)
sudo mkdir -p /var/log/vantio
sudo VANTIO_TRACE_ID="$VANTIO_TRACE_ID" \
  ./target/release/vantio-loader \
  --iface eth0 \
  --output-file /var/log/vantio/events.ndjson
```

Omit `--enforce` for the first run. A successful start prints the trace map path `/sys/fs/bpf/vantio_trace_map`, the enrolled map path `/sys/fs/bpf/vantio_enrolled_cgroups`, and the event header. The classifier line names the interface and audit mode.

Host-crate checks that do not build the kernel target:

```bash
cargo check  --workspace --exclude vantio-phantom-engine
cargo clippy --workspace --exclude vantio-phantom-engine
```

## 5. Optional dashboard ingest

Leave this unset for a sovereign node. If your architecture review includes the hosted dashboard:

```bash
sudo VANTIO_TRACE_ID="$VANTIO_TRACE_ID" \
  VANTIO_API_KEY="$VANTIO_API_KEY" \
  VANTIO_CLOUD_INGEST_URL=https://vantio.ai \
  ./target/release/vantio-loader --iface eth0
```

The loader can post an `ENGINE_STARTED` event and an `ENGINE_HEARTBEAT` about every 4 minutes when that URL is set. Store the API key in your secret manager. This manual has no key material. Dashboard reachability from your network is your check (**customer validated** only after you see it).

## 6. Spanner settings (do not make this the only copy)

Schema and writer columns are aligned in the product repository (**independently tested** as a code review). A live insert is **not tested**. When you are ready to test in your own project, the loader reads:

- `GOOGLE_SPANNER_DATABASE` in the form `projects/PROJECT/instances/INSTANCE/databases/DATABASE`
- `GOOGLE_APPLICATION_CREDENTIALS` pointing at a service account JSON

Helm sets those only when `sovereignMode=cloud` and `spannerDatabase` is non-empty. Create the Google secret before relying on it. The chart references secret `google-cloud-key`. Keep NDJSON or loader logs until your project shows a row. See [EVIDENCE-AND-ASSURANCE.md](./EVIDENCE-AND-ASSURANCE.md).

## 7. Order of operations

1. Audit mode, one worker or one bare host.
2. Confirm the event header and a heartbeat.
3. Enroll one pilot workload.
4. Confirm that workload appears in enroll-watch logs or in an explicit enroll command.
5. Only then consider scoped `--enforce`, with an allowlist that includes destinations the pilot must reach.
6. Keep `nodeWideEnforcement` false.
7. Keep control-plane nodes off the DaemonSet.

Switching on enforcement is a customer change control. The chart default `enforce` is false.
