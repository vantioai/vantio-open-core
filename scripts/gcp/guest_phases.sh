#!/bin/bash
# Extra enforcement phases. A phase that cannot run on this host prints NOT_RUN.
# NOT_RUN is not a pass. Signed stop is the teardown.
set -u
phase="${1:?}"
OUT="${VANTIO_LAB_DIR:?}"
LOADER="${VANTIO_LOADER:?}"
LOADER_PID=""
CGROUP="${VANTIO_LAB_CGROUP:-/sys/fs/cgroup/vantio-enforcement-proof}"
mkdir -p "$OUT"
: >"$OUT/transcript.txt"
note() { printf '%s\n' "$*" | tee -a "$OUT/transcript.txt"; }
finish_not_proven() { note "live_enforcement=NOT_PROVEN"; }

stop_loader() {
  if [[ -n "${LOADER_PID:-}" ]] && kill -0 "$LOADER_PID" 2>/dev/null; then
    local token="${VANTIO_LAB_STOP_TOKEN}"
    local dir py
    dir="$(dirname "$token")"
    py="$(cd "$(dirname "$0")" && pwd)/lab_stop.py"
    if [[ -f "$py" ]]; then
      python3 "$py" next-stop "$dir" >/dev/null 2>&1 || true
      if [[ -f "$dir/stop-next.json" ]]; then
        token="$dir/stop-next.json"
      fi
    fi
    send_stop() {
      timeout 20 env VANTIO_LAB_SCOPE=lab-nonprod VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
        "$LOADER" --authenticated-stop --stop-token "$1" >/tmp/vantio-phase-stop.log 2>&1 || true
    }
    send_stop "$token"
    local i
    for i in $(seq 1 50); do
      local state=""
      if [[ -r "/proc/${LOADER_PID}/stat" ]]; then
        state="$(awk '{print $3}' "/proc/${LOADER_PID}/stat" 2>/dev/null || true)"
      fi
      if [[ "$state" == "Z" ]] || ! kill -0 "$LOADER_PID" 2>/dev/null; then
        wait "$LOADER_PID" 2>/dev/null || true
        break
      fi
      sleep 0.3
    done
    if kill -0 "$LOADER_PID" 2>/dev/null; then
      python3 "$py" next-stop "$dir" >/dev/null 2>&1 || true
      if [[ -f "$dir/stop-next.json" ]]; then
        send_stop "$dir/stop-next.json"
      fi
      for i in $(seq 1 50); do
        if ! kill -0 "$LOADER_PID" 2>/dev/null; then
          wait "$LOADER_PID" 2>/dev/null || true
          break
        fi
        sleep 0.3
      done
    fi
  fi
  LOADER_PID=""
}

start_enforcing() {
  local log="$1"
  shift
  : >"$log"
  "$@" >"$log" 2>&1 &
  LOADER_PID=$!
  local i
  for i in $(seq 1 40); do
    if grep -F "LOADER_INTEGRITY_REFUSED" "$log" >/dev/null 2>&1; then
      echo REFUSED
      return 0
    fi
    if grep -F "enforcing" "$log" >/dev/null 2>&1; then
      echo ENFORCING
      return 0
    fi
    if ! kill -0 "$LOADER_PID" 2>/dev/null; then
      echo EXITED
      return 0
    fi
    sleep 0.5
  done
  echo TIMEOUT
}

arm_loader() {
  local log="$1"
  shift
  start_enforcing "$log" env VANTIO_LAB_SCOPE=lab-nonprod \
    VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
    VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
    "$@" >"$OUT/banner.txt"
  banner="$(tr -d '\n' < "$OUT/banner.txt")"
  if [[ "$banner" != "ENFORCING" ]]; then
    note "${phase}=FAIL"
    note "banner=$banner"
    stop_loader
    finish_not_proven
    exit 1
  fi
}

case "$phase" in
  k8s)
    note "k8s=NOT_RUN"
    finish_not_proven
    exit 0
    ;;
  vlan)
    if ! ip link add link lo name vantio-vlan-probe type vlan id 10 >/tmp/vantio-vlan-probe.err 2>&1; then
      ip link del vantio-vlan-probe >/dev/null 2>&1 || true
      note "vlan=NOT_RUN"
      finish_not_proven
      exit 0
    fi
    ip link del vantio-vlan-probe >/dev/null 2>&1 || true
    note "vlan=NOT_RUN"
    finish_not_proven
    exit 0
    ;;
  host-enroll)
    note "host_enroll=NOT_RUN"
    finish_not_proven
    exit 0
    ;;
  pin-absent)
    mkdir -p "$CGROUP"
    env -u VANTIO_LOADER_PIN "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" \
      --iface lo --startup-enroll-cgroup "$CGROUP" >"$OUT/pin-absent.log" 2>&1 || true
    if grep -F "reason=PIN_ABSENT" "$OUT/pin-absent.log" >/dev/null; then
      note "pin_absent=REFUSED"
    else
      note "pin_absent=ENFORCING"
    fi
    start_enforcing "$OUT/pin-present.log" env VANTIO_LAB_SCOPE=lab-nonprod \
      VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
      "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface lo \
      --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/pin.ndjson" >"$OUT/banner.txt"
    banner="$(tr -d '\n' < "$OUT/banner.txt")"
    note "pin_present=$banner"
    stop_loader
    finish_not_proven
    if [[ "$(grep '^pin_absent=' "$OUT/transcript.txt" | tail -1)" == "pin_absent=REFUSED" && "$banner" == "ENFORCING" ]]; then
      exit 0
    fi
    exit 1
    ;;
  host-wide)
    hw=/sys/fs/cgroup/vantio-hw-lab
    mkdir -p "$hw/out" "$hw/except"
    stop_dir="$(dirname "${VANTIO_LAB_STOP_TOKEN}")"
    python3 "$(dirname "$0")/lab_stop.py" exception "$stop_dir" "$hw/except"
    arm_loader "$OUT/host-wide.log" \
      env VANTIO_CGROUP_ROOT="$hw" \
      VANTIO_LAB_SCOPE=lab-nonprod \
      VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
      "$LOADER" --enforce --host-wide --stop-authority "${VANTIO_LAB_STOP_TOKEN}" \
      --cgroup-exception-file "$stop_dir/exceptions.json" --iface lo \
      --output-file "$OUT/host-wide.ndjson"
    while IFS= read -r line; do note "$line"; done < <(python3 - "$hw" <<'PY'
import os, socket, sys
root = sys.argv[1]
def send(where):
    if os.fork() != 0:
        return
    if where != "agent":
        open(root + "/" + where + "/cgroup.procs", "w").write(str(os.getpid()))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.5)
    try:
        sock.sendto(b"x", ("127.0.0.1", 9))
        print(f"hostwide_{where}=allowed")
    except socket.timeout:
        print(f"hostwide_{where}=blocked")
    except OSError as exc:
        print(f"hostwide_{where}=" + ("blocked" if exc.errno in (1, 13) else "other"))
        print(f"hostwide_{where}_errno={exc.errno or 0}")
    raise SystemExit(0)
for where in ("out", "except", "agent"):
    send(where)
    os.wait()
PY
)
    stop_loader
    rmdir "$hw/out" "$hw/except" "$hw" 2>/dev/null || true
    finish_not_proven
    grep -q '^hostwide_out=blocked$' "$OUT/transcript.txt" \
      && grep -q '^hostwide_except=allowed$' "$OUT/transcript.txt" \
      && grep -q '^hostwide_agent=allowed$' "$OUT/transcript.txt"
    exit $?
    ;;
  hard-link)
    secret="$OUT/pe-secret"
    rm -rf "$secret" "$OUT/link-before" "$OUT/link-after"
    mkdir -p "$secret"
    printf 'rt-secret-marker\n' > "$secret/file"
    ln "$secret/file" "$OUT/link-before"
    mkdir -p "$CGROUP"
    arm_loader "$OUT/hard-link.log" \
      env VANTIO_PHANTOM_DENY=1 VANTIO_LAB_SCOPE=lab-nonprod \
      VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
      "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface lo \
      --enforce-path "${secret}/" --startup-enroll-cgroup "$CGROUP" \
      --output-file "$OUT/hard-link.ndjson"
    while IFS= read -r line; do note "$line"; done < <(python3 - "$CGROUP" "$secret/file" "$OUT/link-before" "$OUT/link-after" <<'PY'
import os, sys
cgroup, original, before, after = sys.argv[1:]
def child(enrolled, fn):
    if os.fork() != 0:
        os.wait()
        return
    if enrolled:
        open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
    fn()
    raise SystemExit(0)
def open_result(path):
    try:
        fd = os.open(path, os.O_RDONLY)
        os.close(fd)
        return "allowed"
    except OSError as exc:
        return "denied" if exc.errno in (1, 13) else "other"
child(True, lambda: print("hardlink_before=" + open_result(before)))
child(True, lambda: print("hardlink_original=" + open_result(original)))
def make_link():
    try:
        os.link(original, after)
        print("hardlink_root_link=created")
    except OSError as exc:
        print("hardlink_root_link=denied")
        print(f"hardlink_root_errno={exc.errno or 0}")
child(False, make_link)
child(True, lambda: print("hardlink_after=" + open_result(after)))
def enrolled_link():
    dest = after + "-enrolled"
    try:
        os.link(original, dest)
        print("hardlink_enrolled_link=created")
    except OSError as exc:
        print("hardlink_enrolled_link=" + ("denied" if exc.errno in (1, 13) else "other"))
child(True, enrolled_link)
PY
)
    stop_loader
    rm -rf "$secret" "$OUT/link-before" "$OUT/link-after" "$OUT/link-after-enrolled"
    finish_not_proven
    grep -q '^hardlink_before=denied$' "$OUT/transcript.txt" \
      && grep -q '^hardlink_original=denied$' "$OUT/transcript.txt" \
      && grep -q '^hardlink_root_link=created$' "$OUT/transcript.txt" \
      && grep -q '^hardlink_after=denied$' "$OUT/transcript.txt" \
      && grep -q '^hardlink_enrolled_link=denied$' "$OUT/transcript.txt"
    exit $?
    ;;
  enrolled-root)
    secret="$OUT/root-secret"
    rm -rf "$secret"
    mkdir -p "$secret"
    printf 'rt-secret-marker\n' > "$secret/file"
    mkdir -p "$CGROUP"
    arm_loader "$OUT/enrolled-root.log" \
      env VANTIO_PHANTOM_DENY=1 VANTIO_LAB_SCOPE=lab-nonprod \
      VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
      "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface lo \
      --enforce-path "${secret}/" --startup-enroll-cgroup "$CGROUP" \
      --output-file "$OUT/enrolled-root.ndjson"
    while IFS= read -r line; do note "$line"; done < <(python3 - "$CGROUP" "$secret/file" <<'PY'
import os, sys
cgroup, path = sys.argv[1:]
def once(enrolled, label):
    if os.fork() != 0:
        os.wait()
        return
    if enrolled:
        open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
    try:
        fd = os.open(path, os.O_RDONLY)
        os.read(fd, 32)
        os.close(fd)
        print(f"{label}=allowed")
    except OSError as exc:
        print(f"{label}=" + ("denied" if exc.errno in (1, 13) else "other"))
        print(f"{label}_errno={exc.errno or 0}")
    raise SystemExit(0)
once(True, "root_enrolled_open")
once(False, "root_outside_open")
PY
)
    stop_loader
    rm -rf "$secret"
    finish_not_proven
    grep -q '^root_enrolled_open=denied$' "$OUT/transcript.txt" \
      && grep -q '^root_outside_open=allowed$' "$OUT/transcript.txt"
    exit $?
    ;;
  nonce-truncate)
    mkdir -p "$CGROUP"
    arm_loader "$OUT/nonce.log" \
      env VANTIO_LAB_SCOPE=lab-nonprod \
      VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
      "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface lo \
      --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/nonce.ndjson"
    stop_dir="$(dirname "${VANTIO_LAB_STOP_TOKEN}")"
    python3 "$(dirname "$0")/lab_stop.py" next-stop "$stop_dir"
    token="$stop_dir/stop-next.json"
    env VANTIO_LAB_SCOPE=lab-nonprod VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      "$LOADER" --authenticated-stop --stop-token "$token" >"$OUT/nonce-first.log" 2>&1 || true
    if grep -F "authenticated stop accepted" "$OUT/nonce-first.log" >/dev/null; then
      note "nonce_first=accepted"
    else
      note "nonce_first=refused"
    fi
    for _ in $(seq 1 50); do
      if ! kill -0 "$LOADER_PID" 2>/dev/null; then
        break
      fi
      sleep 0.3
    done
    : > /run/vantio-stop-nonces
    env VANTIO_LAB_SCOPE=lab-nonprod VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      "$LOADER" --authenticated-stop --stop-token "$token" >"$OUT/nonce-replay.log" 2>&1 || true
    if grep -F "STOP_NONCE_REPLAY" "$OUT/nonce-replay.log" >/dev/null; then
      note "nonce_replay=replay"
    else
      note "nonce_replay=other"
    fi
    if [[ ! -s /run/vantio-stop-nonces ]]; then
      note "nonce_file=empty"
    else
      note "nonce_file=present"
    fi
    LOADER_PID=""
    finish_not_proven
    grep -q '^nonce_first=accepted$' "$OUT/transcript.txt" \
      && grep -q '^nonce_replay=replay$' "$OUT/transcript.txt" \
      && grep -q '^nonce_file=empty$' "$OUT/transcript.txt"
    exit $?
    ;;
  ledger-forgery)
    mkdir -p "$CGROUP"
    rm -f "$OUT/ledger.ndjson" "$OUT/ledger.ndjson.head"
    arm_loader "$OUT/ledger.log" \
      env VANTIO_LAB_SCOPE=lab-nonprod \
      VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
      "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface lo \
      --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/ledger.ndjson"
    python3 - "$CGROUP" <<'PY'
import os, socket, sys
cgroup = sys.argv[1]
if os.fork() == 0:
    open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(b"ledger", ("127.0.0.1", 9))
    except OSError:
        pass
    raise SystemExit(0)
os.wait()
PY
    stop_loader
    verify="$(cd "$(dirname "$0")" && pwd)/verify_ledger.py"
    while IFS= read -r line; do note "$line"; done < <(python3 - "$verify" "$OUT/ledger.ndjson" <<'PY'
import base64, hashlib, json, os, subprocess, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
verify, src = sys.argv[1:]
def run(rows, head_text, path):
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    head_path = path + ".head"
    if head_text is None:
        try:
            os.remove(head_path)
        except OSError:
            pass
    else:
        with open(head_path, "w", encoding="utf-8") as handle:
            handle.write(head_text)
    trust_src = src + ".head.trust"
    if os.path.isfile(trust_src):
        with open(path + ".trust", "w", encoding="utf-8") as handle:
            handle.write(open(trust_src, encoding="utf-8").read())
    done = subprocess.run([sys.executable, verify, path], capture_output=True, text=True)
    return done.returncode, (done.stderr or "") + (done.stdout or "")
genuine = subprocess.run([sys.executable, verify, src], capture_output=True, text=True)
print("ledger_genuine=" + ("ok" if genuine.returncode == 0 else "bad"))
rows = [json.loads(line) for line in open(src, encoding="utf-8") if line.strip() and "chain_hash" in line]
head = open(src + ".head", encoding="utf-8").read()
extra = dict(rows[-1])
extra["chain_key"] = base64.b64encode(b"\x11" * 32).decode()
extra["chain_prev"] = rows[-1]["chain_hash"]
rc, text = run(rows + [extra], head, src + ".key")
print("ledger_key_changed=" + ("rejected" if rc != 0 and "chain key changed" in text else "accepted"))
zeroed = json.loads(json.dumps(rows))
if len(zeroed) == 1:
    second = dict(zeroed[0])
    second["chain_prev"] = "00" * 32
    zeroed.append(second)
else:
    zeroed[1]["chain_prev"] = "00" * 32
rc, text = run(zeroed, head, src + ".zero")
print("ledger_zero_prev=" + ("rejected" if rc != 0 and "zero chain_prev" in text else "accepted"))
rc, text = run(rows[:1], head, src + ".trunc")
print("ledger_truncated=" + ("rejected" if rc != 0 and "does not match" in text else "accepted"))
body = {"attacker": 1}
canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
digest = hashlib.sha256(bytes(32) + canon).digest()
signing = Ed25519PrivateKey.generate()
pub = base64.b64encode(signing.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
attacker = dict(body)
attacker["chain_prev"] = "00" * 32
attacker["chain_hash"] = digest.hex()
attacker["chain_sig"] = base64.b64encode(signing.sign(digest)).decode()
attacker["chain_key"] = pub
rc, text = run([attacker], None, src + ".attacker")
print("ledger_attacker=" + ("rejected" if rc != 0 and "not the trusted key" in text else "accepted"))
PY
)
    finish_not_proven
    grep -q '^ledger_genuine=ok$' "$OUT/transcript.txt" \
      && grep -q '^ledger_key_changed=rejected$' "$OUT/transcript.txt" \
      && grep -q '^ledger_zero_prev=rejected$' "$OUT/transcript.txt" \
      && grep -q '^ledger_truncated=rejected$' "$OUT/transcript.txt" \
      && grep -q '^ledger_attacker=rejected$' "$OUT/transcript.txt"
    exit $?
    ;;
  ptrace-task)
    mkdir -p "$CGROUP"
    arm_loader "$OUT/ptrace-task.log" \
      env VANTIO_LAB_SCOPE=lab-nonprod \
      VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
      "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface lo \
      --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/ptrace-task.ndjson"
    while IFS= read -r line; do note "$line"; done < <(python3 - "$CGROUP" <<'PY'
import ctypes, os, sys, time
cgroup = sys.argv[1]
libc = ctypes.CDLL(None, use_errno=True)
def ptrace(pid):
    ctypes.set_errno(0)
    rc = libc.ptrace(16, pid, 0, 0)
    if rc == 0:
        os.waitpid(pid, os.WUNTRACED)
        libc.ptrace(17, pid, 0, 0)
        return 0
    return ctypes.get_errno()
def sleeper(enrolled):
    pid = os.fork()
    if pid == 0:
        if enrolled:
            open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
        time.sleep(30)
        raise SystemExit(0)
    if enrolled:
        for _ in range(50):
            try:
                text = open(f"/proc/{pid}/cgroup", encoding="utf-8").read()
            except OSError:
                text = ""
            if cgroup in text:
                break
            time.sleep(0.05)
    return pid
def finish(pid, err):
    os.kill(pid, 9)
    os.waitpid(pid, 0)
    return err
outside = sleeper(False)
print("ptrace_unenrolled=" + str(finish(outside, ptrace(outside))))
target = sleeper(True)
print("ptrace_enrolled_target=" + str(finish(target, ptrace(target))))
read_fd, write_fd = os.pipe()
caller = os.fork()
if caller == 0:
    os.close(read_fd)
    open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
    child = sleeper(False)
    err = ptrace(child)
    os.kill(child, 9)
    os.waitpid(child, 0)
    os.write(write_fd, f"{err}\n".encode())
    raise SystemExit(0)
os.close(write_fd)
os.waitpid(caller, 0)
print("ptrace_enrolled_caller=" + os.read(read_fd, 16).decode().strip())
PY
)
    stop_loader
    finish_not_proven
    grep -q '^ptrace_unenrolled=0$' "$OUT/transcript.txt" \
      && grep -q '^ptrace_enrolled_target=1$' "$OUT/transcript.txt" \
      && grep -q '^ptrace_enrolled_caller=1$' "$OUT/transcript.txt"
    exit $?
    ;;
  *)
    ;;
esac

mkdir -p "$CGROUP"
start_enforcing "$OUT/${phase}.log" env VANTIO_LAB_SCOPE=lab-nonprod \
  VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
  "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface lo \
  --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/${phase}.ndjson" >"$OUT/banner.txt"
banner="$(tr -d '\n' < "$OUT/banner.txt")"
if [[ "$banner" != "ENFORCING" ]]; then
  note "${phase}=FAIL"
  note "banner=$banner"
  stop_loader
  finish_not_proven
  exit 1
fi

case "$phase" in
  unix-socket)
    sock="$OUT/peer.sock"
    rm -f "$sock"
    while IFS= read -r line; do note "$line"; done < <(python3 - "$CGROUP" "$sock" <<'PY'
import os, socket, sys
cgroup, path = sys.argv[1], sys.argv[2]
if os.fork() == 0:
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen(1)
    listener.settimeout(3)
    try:
        conn, _ = listener.accept()
        conn.close()
    except OSError:
        pass
    raise SystemExit(0)
if os.fork() == 0:
    try:
        open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
    except OSError as exc:
        print(f"unix_enrolled=denied errno={exc.errno}")
        raise SystemExit(0)
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(1.5)
    try:
        client.connect(path)
        print("unix_enrolled=connected")
    except OSError as exc:
        print("unix_enrolled=denied" if exc.errno == 1 else f"unix_enrolled=connected errno={exc.errno}")
    raise SystemExit(0)
os.wait()
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(1.5)
try:
    client.connect(path)
    print("unix_outside=connected")
except OSError:
    print("unix_outside=denied")
PY
)
    ;;
  ptrace-deny)
    target="$LOADER_PID"
    if [[ -r "/proc/${target}/comm" ]] && ! grep -q '^vantio-loader$' "/proc/${target}/comm"; then
      child="$(ps --ppid "$target" -o pid=,comm= | awk '$2=="vantio-loader"{print $1; exit}')"
      if [[ -n "$child" ]]; then
        target="$child"
      fi
    fi
    while IFS= read -r line; do note "$line"; done < <(python3 - "$target" <<'PY'
import ctypes, os, sys
pid = int(sys.argv[1])
libc = ctypes.CDLL(None, use_errno=True)
def errno_of(rc):
    return 0 if rc == 0 else ctypes.get_errno()
class Iovec(ctypes.Structure):
    _fields_ = [("iov_base", ctypes.c_void_p), ("iov_len", ctypes.c_size_t)]
# flags must be a real 0. syscall() without argtypes leaves that register
# unset, and the kernel returns EINVAL before the LSM.
libc.process_vm_writev.restype = ctypes.c_ssize_t
libc.process_vm_writev.argtypes = [
    ctypes.c_int, ctypes.POINTER(Iovec), ctypes.c_ulong,
    ctypes.POINTER(Iovec), ctypes.c_ulong, ctypes.c_ulong,
]
local_buf = ctypes.create_string_buffer(4)
local_io = Iovec(ctypes.cast(local_buf, ctypes.c_void_p), 4)
remote_io = Iovec(ctypes.c_void_p(0x1000), 4)
ctypes.set_errno(0)
wrote = libc.process_vm_writev(pid, ctypes.byref(local_io), 1, ctypes.byref(remote_io), 1, 0)
vm = errno_of(wrote)
ctypes.set_errno(0)
ptrace = errno_of(libc.ptrace(16, pid, 0, 0))
if ptrace == 0:
    libc.ptrace(17, pid, 0, 0)
try:
    os.open(f"/proc/{pid}/mem", os.O_RDWR)
    mem = 0
except OSError as exc:
    mem = exc.errno or 0
pidfd = libc.syscall(434, pid, 0)
getfd = 1
if pidfd >= 0:
    ctypes.set_errno(0)
    stolen = libc.syscall(438, pidfd, 1, 0)
    getfd = errno_of(stolen)
comm = open(f"/proc/{pid}/comm", encoding="ascii").read().strip()
print(f"ptrace_comm={comm}")
print(f"ptrace_errno={ptrace}")
print(f"process_vm_errno={vm}")
print(f"proc_mem_errno={mem}")
print(f"pidfd_getfd_errno={getfd}")
PY
)
    ;;
  inbound)
    while IFS= read -r line; do note "$line"; done < <(python3 - "$CGROUP" <<'PY'
import os, socket, sys
cgroup = sys.argv[1]
print("inbound_client_cgroup=" + open("/proc/self/cgroup").read().strip().split(":")[-1], flush=True)
def read_line(fd):
    data = b""
    while b"\n" not in data:
        chunk = os.read(fd, 64)
        if not chunk:
            break
        data += chunk
    return data.split(b"\n", 1)[0].decode()
def serve(where):
    read_fd, write_fd = os.pipe()
    if os.fork() != 0:
        os.close(write_fd)
        return read_fd
    os.close(read_fd)
    if where == "enrolled":
        open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
        print("inbound_listener_cgroup=enrolled", flush=True)
    else:
        print("inbound_listener_cgroup=outside", flush=True)
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    os.write(write_fd, f"{sock.getsockname()[1]}\n".encode())
    sock.settimeout(4)
    try:
        conn, _ = sock.accept()
        conn.close()
        os.write(write_fd, b"accepted\n")
    except socket.timeout:
        os.write(write_fd, b"timeout\n")
    except OSError as exc:
        os.write(write_fd, f"errno={exc.errno}\n".encode())
    raise SystemExit(0)
def poke(where, fd):
    port = int(read_line(fd))
    sock = socket.socket()
    sock.settimeout(2)
    client = "error"
    errno = 0
    try:
        sock.connect(("127.0.0.1", port))
        client = "connected"
    except socket.timeout:
        client = "timeout"
    except OSError as exc:
        errno = exc.errno or 0
    finally:
        sock.close()
    accept = read_line(fd)
    print(f"inbound_{where}_client={client}", flush=True)
    print(f"inbound_{where}_errno={errno}", flush=True)
    print(f"inbound_{where}_accept={accept}", flush=True)
    if client == "connected" and accept.startswith("accepted"):
        return "connected"
    if accept == "timeout" or client == "timeout":
        return "blocked"
    return "refused"
outside_fd = serve("outside")
enrolled_fd = serve("enrolled")
print("inbound_outside=" + poke("outside", outside_fd), flush=True)
print("inbound_enrolled=" + poke("enrolled", enrolled_fd), flush=True)
os.wait()
os.wait()
PY
)
    ;;
  bpffs-overmount)
    while IFS= read -r line; do note "$line"; done < <(python3 - <<'PY'
import ctypes, os
libc = ctypes.CDLL(None, use_errno=True)
libc.mount.restype = ctypes.c_int
libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p]
libc.umount.restype = ctypes.c_int
libc.umount.argtypes = [ctypes.c_char_p]
ctypes.set_errno(0)
rc = libc.mount(b"bpf", b"/sys/fs/bpf", b"bpf", 0, None)
err = ctypes.get_errno()
if rc == 0:
    libc.umount(b"/sys/fs/bpf")
    print("bpffs_overmount=mounted")
    print("bpffs_errno=0")
    print("bpffs_pins=hidden")
else:
    print("bpffs_overmount=refused")
    print(f"bpffs_errno={err}")
    pins = False
    for _dir, _names, files in os.walk("/sys/fs/bpf"):
        if any(name.startswith("vantio") for name in files):
            pins = True
            break
    print("bpffs_pins=" + ("remain" if pins else "hidden"))
PY
)
    ;;
  af-packet)
    while IFS= read -r line; do note "$line"; done < <(python3 - "$CGROUP" <<'PY'
import os, socket, sys
cgroup = sys.argv[1]
def attempt(enrolled):
    if enrolled:
        open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
    try:
        socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
        return "ok"
    except OSError as exc:
        return "denied" if exc.errno == 1 else "ok"
if os.fork() == 0:
    print("af_packet_enrolled=" + attempt(True))
    raise SystemExit(0)
os.wait()
print("af_packet_outside=" + attempt(False))
PY
)
    ;;
  stop-token)
    python3 "$(dirname "$0")/lab_stop.py" expired-stop "$(dirname "${VANTIO_LAB_STOP_TOKEN}")" || true
    python3 "$(dirname "$0")/lab_stop.py" bare-stop "$(dirname "${VANTIO_LAB_STOP_TOKEN}")" || true
    python3 "$(dirname "$0")/lab_stop.py" next-stop "$(dirname "${VANTIO_LAB_STOP_TOKEN}")" || true
    dir="$(dirname "${VANTIO_LAB_STOP_TOKEN}")"
    try_stop() {
      env VANTIO_LAB_SCOPE=lab-nonprod VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
        "$LOADER" --authenticated-stop --stop-token "$1" >"$OUT/stop-try.log" 2>&1 || true
      if grep -E "accepted|authenticated stop accepted" "$OUT/stop-try.log" >/dev/null; then
        echo accepted
      else
        echo refused
      fi
    }
    note "stop_expired=$(try_stop "$dir/stop-expired.json")"
    note "stop_bare=$(try_stop "$dir/stop-bare.json")"
    if ! kill -0 "$LOADER_PID" 2>/dev/null; then
      note "stop_replay=accepted"
      note "stop_fresh=refused"
    else
      note "stop_fresh=$(try_stop "$dir/stop-next.json")"
      note "stop_replay=$(try_stop "$dir/stop-next.json")"
    fi
    ;;
  missing-path)
    missing="$OUT/missing-file"
    rm -f "$missing"
    stop_loader
    start_enforcing "$OUT/missing.log" env VANTIO_LAB_SCOPE=lab-nonprod \
      VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" VANTIO_LOADER_PIN="${VANTIO_LOADER_PIN:-}" \
      "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface lo \
      --enforce-path "$missing" --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/missing.ndjson" >"$OUT/banner.txt"
    banner="$(tr -d '\n' < "$OUT/banner.txt")"
    while IFS= read -r line; do note "$line"; done < <(python3 - "$CGROUP" "$missing" <<'PY'
import os, sys
cgroup, path = sys.argv[1], sys.argv[2]
open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
try:
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    os.close(fd)
    print("missing_create=created")
except OSError as exc:
    print("missing_create=denied" if exc.errno in (1, 13) else "missing_create=created")
print("missing_created=" + ("yes" if os.path.exists(path) else "no"))
PY
)
    rm -f "$missing"
    ;;
  *)
    note "${phase}=NOT_RUN"
    ;;
esac
stop_loader
finish_not_proven
exit 0
