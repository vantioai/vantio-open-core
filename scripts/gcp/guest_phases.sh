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
    timeout 20 env VANTIO_LAB_SCOPE=lab-nonprod VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      "$LOADER" --authenticated-stop --stop-token "$token" >/tmp/vantio-phase-stop.log 2>&1 || true
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
      if ! kill -0 "$LOADER_PID" 2>/dev/null; then
        break
      fi
      sleep 0.3
    done
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
    while IFS= read -r line; do note "$line"; done < <(python3 - "$LOADER_PID" <<'PY'
import ctypes, os, sys
pid = int(sys.argv[1])
libc = ctypes.CDLL(None, use_errno=True)
def errno_of(rc):
    return 0 if rc == 0 else ctypes.get_errno()
ctypes.set_errno(0)
ptrace = errno_of(libc.ptrace(16, pid, 0, 0))
if ptrace == 0:
    libc.ptrace(17, pid, 0, 0)
ctypes.set_errno(0)
local_buf = ctypes.create_string_buffer(4)
class Iovec(ctypes.Structure):
    _fields_ = [("iov_base", ctypes.c_void_p), ("iov_len", ctypes.c_size_t)]
local_io = Iovec(ctypes.cast(local_buf, ctypes.c_void_p), 4)
remote_io = Iovec(ctypes.c_void_p(0x1000), 4)
wrote = libc.syscall(311, pid, ctypes.byref(local_io), 1, ctypes.byref(remote_io), 1, 0)
vm = errno_of(wrote)
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
def serve(where):
    if os.fork() != 0:
        return
    if where == "enrolled":
        open(cgroup + "/cgroup.procs", "w").write(str(os.getpid()))
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.listen(1)
    open(f"/tmp/vantio-{where}.port", "w").write(str(port))
    sock.settimeout(2)
    try:
        conn, _ = sock.accept()
        conn.close()
    except OSError:
        pass
    raise SystemExit(0)
def poke(where):
    port = int(open(f"/tmp/vantio-{where}.port").read())
    sock = socket.socket()
    sock.settimeout(1.5)
    try:
        sock.connect(("127.0.0.1", port))
        return "connected"
    except socket.timeout:
        return "blocked"
    except OSError as exc:
        return "blocked" if exc.errno == 1 else "connected"
serve("enrolled")
serve("outside")
os.wait()
os.wait()
print("inbound_enrolled=" + poke("enrolled"))
print("inbound_outside=" + poke("outside"))
PY
)
    ;;
  bpffs-overmount)
    if mount -t tmpfs tmpfs /sys/fs/bpf >/tmp/vantio-mount.err 2>&1; then
      umount /sys/fs/bpf >/dev/null 2>&1 || umount -l /sys/fs/bpf >/dev/null 2>&1 || true
      note "bpffs_overmount=mounted"
      note "bpffs_errno=0"
      note "bpffs_pins=hidden"
    else
      note "bpffs_overmount=refused"
      note "bpffs_errno=1"
      if find /sys/fs/bpf -name 'vantio*' -print -quit 2>/dev/null | grep -q .; then
        note "bpffs_pins=remain"
      else
        note "bpffs_pins=hidden"
      fi
    fi
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
