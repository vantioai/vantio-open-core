#!/usr/bin/env bash
# Cloud Agent bootstrap for vantio-open-core.
# Idempotent: safe to run repeatedly and against cached/partial state.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# strace is a hard dependency of the @vantio/cli test suite:
# packages/vantio-cli/test/optics-cx.test.js asserts "strace must be installed"
# (it verifies `vantio demo`/`status` perform no network syscalls).
if ! command -v strace >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends strace
fi

# JS workspace dependencies (pnpm-only monorepo; frozen lockfile matches CI).
corepack enable >/dev/null 2>&1 || true
pnpm install --frozen-lockfile

# Optional HTTP clients the Python SDK observe tests exercise (see CI test-python).
python3 -m pip install --disable-pip-version-check --break-system-packages \
  requests httpx aiohttp urllib3
