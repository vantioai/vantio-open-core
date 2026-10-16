# Phantom-Box procedure

This agent cannot reach the host. Do not run the approval-gate block from CI or from this branch. The read-only block does not pull, recreate, restart, or print secrets.

Container: `vantio-plane1-openclaw`
Checkout: `/home/vantioai/vantio-enterprise`
Commit the files were read at: `59002fb5df244702b1df344c1258839f9b8a3d6b`
Pin: `ghcr.io/openclaw/openclaw@sha256:614004ec2cf2e6095124ea544dc8d950c49306aef445a1fc300b88717e24261a`
That digest is OpenClaw `2026.10.4`. CVE-2026-25253 is fixed in `2026.1.29`. A version below that line is affected.

`scripts/plane1_openclaw_desktop_enable.sh cua-probe` pulls `:latest`. Do not run it as part of this check.

## Read-only verification

```bash
set -u
date -u +%Y-%m-%dT%H:%M:%SZ
docker inspect --format 'id={{.Id}} image={{.Image}} config_image={{.Config.Image}} status={{.State.Status}} created={{.Created}}' vantio-plane1-openclaw
IMG="$(docker inspect --format '{{.Image}}' vantio-plane1-openclaw)"
docker image inspect "$IMG" --format 'image_id={{.Id}} version={{index .Config.Labels "org.opencontainers.image.version"}} revision={{index .Config.Labels "org.opencontainers.image.revision"}}'
docker image inspect "$IMG" --format '{{json .RepoDigests}}'
docker exec vantio-plane1-openclaw openclaw --version
docker exec vantio-plane1-openclaw openclaw plugins list
docker exec vantio-plane1-openclaw openclaw skills list
docker exec vantio-plane1-openclaw node -e 'const fs=require("fs"); const c=JSON.parse(fs.readFileSync("/home/node/.openclaw/openclaw.json","utf8")); const plugins=c.plugins||{}; const entries=plugins.entries||{}; const skills=c.skills; const hooks=c.hooks; console.log("plugins.allow", plugins.allow); console.log("plugin.ids", Object.keys(entries).sort()); console.log("skills.keys", skills&&typeof skills==="object"&&!Array.isArray(skills)?Object.keys(skills).sort():typeof skills); console.log("hooks.keys", hooks&&typeof hooks==="object"&&!Array.isArray(hooks)?Object.keys(hooks).sort():typeof hooks);'
python3 - << 'PY'
from pathlib import Path
path = Path.home() / ".config" / "vantio" / "openclaw.env"
print(f"env_file_exists={path.is_file()}")
if not path.is_file():
    raise SystemExit(0)
for line in path.read_text().splitlines():
    if not line or line.lstrip().startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key == "OPENCLAW_IMAGE":
        print(f"OPENCLAW_IMAGE={value}")
    elif key == "OPENCLAW_GATEWAY_PORT":
        print(f"OPENCLAW_GATEWAY_PORT={value}")
    elif any(part in key for part in ("TOKEN", "KEY", "SECRET", "PASSWORD")):
        print(f"{key}={'empty' if not value.strip() else 'present'}")
PY
VERSION_TEXT="$(docker exec vantio-plane1-openclaw openclaw --version | head -n 1)"
python3 - "$VERSION_TEXT" << 'PY'
import re
import sys
match = re.search(r"(\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?)", sys.argv[1])
if match is None:
    print("parsed=none affected=unknown")
    raise SystemExit(2)
raw = match.group(1)
core, sep, _pre = raw.partition("-")
parts = tuple(int(piece) for piece in core.split("."))
floor = (2026, 1, 29)
width = max(len(parts), len(floor))
left = parts + (0,) * (width - len(parts))
right = floor + (0,) * (width - len(floor))
affected = left < right if left != right else bool(sep)
print(f"parsed={raw} affected={affected}")
PY
```

Save the `image=` value. That image id is the rollback target. Do not use the tag `latest` as a rollback target.

Interpret the last line:

- `affected=True`: the running binary is below 2026.1.29. The CVE patch is still required.
- `affected=False`: the running binary is on the fix line or newer. The git default is still floating and still needs the file pin. No recreate is required for this CVE.
- A parse error means the version string was not CalVer. Stop and keep the container as it is.

## Approval gate — file pin, no restart

Do not run this block unless a founder approves it. It edits the checkout and, if present, the host image assignment. It does not pull and does not recreate.

```bash
set -euo pipefail
PIN='ghcr.io/openclaw/openclaw@sha256:614004ec2cf2e6095124ea544dc8d950c49306aef445a1fc300b88717e24261a'
OLD='ghcr.io/openclaw/openclaw:latest'
ROOT=/home/vantioai/vantio-enterprise
cd "$ROOT"
python3 - << PY
from pathlib import Path
old = "$OLD"
new = "$PIN"
expected = {
    "plane1-openclaw/docker-compose.yml": 1,
    "scripts/start_plane1_openclaw.sh": 1,
    "scripts/plane1_openclaw_desktop_enable.sh": 1,
    "agent-hands/docker-compose.yml": 2,
    "docs/ops/OPENCLAW_PLANE1_PHANTOM_BOX.md": 2,
}
for rel, count in expected.items():
    path = Path(rel)
    text = path.read_text()
    found = text.count(old)
    if found != count:
        raise SystemExit(f"{rel}: found {found}, expected {count}")
    path.write_text(text.replace(old, new))
    print(f"pinned {rel} {found}")
PY
python3 - << PY
from pathlib import Path
path = Path.home() / ".config" / "vantio" / "openclaw.env"
old = "$OLD"
new = "$PIN"
if not path.is_file():
    print("openclaw.env absent")
    raise SystemExit(0)
text = path.read_text()
if old not in text:
    print("OPENCLAW_IMAGE assignment does not use the floating tag")
    raise SystemExit(0)
path.write_text(text.replace(old, new))
print("pinned OPENCLAW_IMAGE in openclaw.env")
PY
```

Confirm the container is still the same id:

```bash
docker inspect --format '{{.Image}} {{.State.Status}} {{.State.StartedAt}}' vantio-plane1-openclaw
```

`StartedAt` must be unchanged. If it changed, the edit was not file-only and the gate was exceeded.

## Approval gate — restart

`openclaw plugins install` and an edit of the live `openclaw.json` can reload the gateway inside the same container. That is a restart-class change. It stays in this block, not in the file-pin block. `StartedAt` does not move on an in-process reload, so it is not a sufficient guard.

Do not run this block unless the read-only result is `affected=True`, or a founder separately approves moving the running container onto the 2026.10.4 digest or reinstalling a plugin.

```bash
set -euo pipefail
PIN='ghcr.io/openclaw/openclaw@sha256:614004ec2cf2e6095124ea544dc8d950c49306aef445a1fc300b88717e24261a'
ROLLBACK="$(docker inspect --format '{{.Image}}' vantio-plane1-openclaw)"
echo "rollback_image=$ROLLBACK" | tee /tmp/plane1-openclaw-rollback.txt
docker pull "$PIN"
cd /home/vantioai/vantio-enterprise
OPENCLAW_IMAGE="$PIN" docker compose -f plane1-openclaw/docker-compose.yml up -d --force-recreate openclaw
python3 scripts/vantio_assure.py pe-enroll
docker exec vantio-plane1-openclaw openclaw --version
```

Rollback, if the recreated gateway is not usable, is the saved image id, not `latest`:

```bash
ROLLBACK="$(cut -d= -f2 /tmp/plane1-openclaw-rollback.txt)"
docker tag "$ROLLBACK" plane1-openclaw-rollback:pinned
cd /home/vantioai/vantio-enterprise
OPENCLAW_IMAGE=plane1-openclaw-rollback:pinned docker compose -f plane1-openclaw/docker-compose.yml up -d --force-recreate openclaw
python3 scripts/vantio_assure.py pe-enroll
```

Plugin and MCP reinstalls, only after the recreate above, and only for an id the read-only list showed as installed:

```bash
git clone https://github.com/jeehou/openclaw-cursor-cli.git /tmp/openclaw-cursor-cli-pin
git -C /tmp/openclaw-cursor-cli-pin checkout ee2fc0c57d39dd65e3cbc260a3a43f319a74ece9
printf '%s  %s\n' 8963a59dcf32e532344d053ae4f58f5d292f5021d86513d513f63027351e4ef6 /tmp/openclaw-cursor-cli-pin/package.json | sha256sum -c -
docker cp /tmp/openclaw-cursor-cli-pin vantio-plane1-openclaw:/tmp/openclaw-cursor-cli-pin
docker exec vantio-plane1-openclaw openclaw plugins install /tmp/openclaw-cursor-cli-pin
docker exec vantio-plane1-openclaw openclaw plugins install @openclaw/googlechat@2026.10.4
```

Point `plane1-fs-proof` at `npx -y @modelcontextprotocol/server-filesystem@1.0.0`. The integrity for that tarball is `sha512-2fN6qhpsiPSBAe0ev1qDPk4sCWdULCZQTuYc4ZY7+BDWQ1XCxLB+7dqStF2ZflgG4G/9vTwQsjxh7pjFqrrpcg==`. Confirm it with `npm view @modelcontextprotocol/server-filesystem@1.0.0 dist.integrity` before changing the live MCP entry.

If `affected=True`, rotate `OPENCLAW_GATEWAY_TOKEN` in the mode-600 env file and recreate so the gateway loads the new token. Do not write the token into a log, a chat, or a commit. Rotation restarts the gateway, so it stays inside this gate.
