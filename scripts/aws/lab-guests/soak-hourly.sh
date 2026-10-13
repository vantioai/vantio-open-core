#!/bin/bash
# Hourly soak check. Writes one vantio-lab-check line. Leaves the loader in place.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E bash "$0" "$@"
fi

bin=/var/lib/vantio-lab/bin
record=$bin/record-check.sh
probe=$bin/soak_check.py
stage=${VANTIO_STAGE:-/opt/vantio-enterprise}
seqfile=/var/lib/vantio-lab/soak-seq

install_units() {
  install -d /etc/systemd/system /var/lib/vantio-lab/bin /var/lib/vantio-lab/checks
  cat > /etc/systemd/system/vantio-soak-hourly.service <<'EOF'
[Unit]
Description=Vantio lab hourly soak check
[Service]
Type=oneshot
TimeoutStartSec=900
ExecStart=/var/lib/vantio-lab/bin/soak-hourly.sh
EOF
  cat > /etc/systemd/system/vantio-soak-hourly.timer <<'EOF'
[Unit]
Description=Run the Vantio lab soak check every hour
[Timer]
OnCalendar=hourly
Persistent=true
AccuracySec=1min
[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable vantio-soak-hourly.timer
  systemctl start vantio-soak-hourly.timer
}

if [ "${1:-}" = "install" ]; then
  install_units
  exit 0
fi

install -d /var/lib/vantio-lab/checks
if [ ! -x "$record" ] && [ ! -f "$record" ]; then
  echo "record-check missing" >&2
  exit 1
fi
next=1
if [ -f "$seqfile" ]; then
  prev=$(tr -cd '0-9' < "$seqfile" || true)
  if [ -n "$prev" ]; then
    next=$((prev + 1))
  fi
fi
printf '%s\n' "$next" > "$seqfile"

result=skip
detail=reason:engine_not_loaded
if [ -f "$probe" ]; then
  tmp=$(mktemp)
  set +e
  if [ "${1:-}" = "start" ]; then
    python3 "$probe" "$stage" start >"$tmp" 2>>/var/lib/vantio-lab/soak-check.err
  else
    python3 "$probe" "$stage" >"$tmp" 2>>/var/lib/vantio-lab/soak-check.err
  fi
  set -e
  got_result=$(awk -F= '/^result=/{print $2}' "$tmp" | tail -n 1)
  got_detail=$(awk -F= '/^detail=/{v=substr($0, index($0, "=")+1)} END{print v}' "$tmp")
  rm -f "$tmp"
  case "$got_result" in
    pass|fail|skip)
      result=$got_result
      detail=${got_detail:-reason:probe_output}
      ;;
    *)
      result=fail
      detail=reason:probe_output
      ;;
  esac
fi
case "$detail" in
  *[!A-Za-z0-9_.:-]*) detail=reason:probe_output ;;
esac
"$record" "$next" hourly "$result" "$detail"
chmod a+r /var/lib/vantio-lab/checks.ndjson /var/lib/vantio-lab/checks/* 2>/dev/null || true
if [ "$result" = "fail" ]; then
  exit 1
fi
