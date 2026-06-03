#!/bin/sh
# Vantio CLI installer — https://vantio.ai/install.sh
#
# Installs the @vantio/cli npm package globally. Short and readable on purpose:
# it only checks for node/npm and runs `npm install -g @vantio/cli`.
#
#   curl -fsSL https://vantio.ai/install.sh | sh
#
set -eu

info() { printf '  %s\n' "$1"; }
err()  { printf 'vantio install: %s\n' "$1" >&2; }

printf '\n  ∅ Installing the Vantio CLI…\n\n'

if ! command -v node >/dev/null 2>&1; then
  err "Node.js is required but was not found."
  err "Install Node 18+ from https://nodejs.org and re-run this script."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  err "npm is required but was not found (it ships with Node.js)."
  exit 1
fi

info "node $(node --version)"
info "installing @vantio/cli (global)…"

if npm install -g @vantio/cli; then
  printf '\n  ✓ Vantio CLI installed.\n\n'
  info "Next steps:"
  info "  vantio login <your-api-key>   # grab your key at https://vantio.ai/dashboard"
  info "  vantio run node agent.js"
  printf '\n'
else
  err "npm install failed."
  err "If this is a permissions error, try a Node version manager (nvm) or: sudo npm install -g @vantio/cli"
  exit 1
fi
