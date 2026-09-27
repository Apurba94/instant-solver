#!/usr/bin/env bash
# One-time local setup inside WSL Ubuntu (or any Ubuntu/Debian machine).
#
#   sudo bash scripts/setup-wsl.sh      # system packages (needs root)
#   bash scripts/setup-wsl.sh --user    # virtualenv + npm packages (as yourself)
#
# Running it without --user as root does both steps, handing the second one to
# the invoking user so the project files are not left owned by root.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

install_system() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y build-essential python3 python3-venv python3-pip curl ca-certificates make

  # Next.js 16 needs Node >= 20; Ubuntu's own nodejs package is older.
  if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
  fi
}

install_user() {
  cd "$APP_DIR"
  # A virtualenv cannot live on a Windows drive (/mnt/c, /mnt/d): keep it in the
  # Linux home directory there. The Makefile looks in both places.
  local venv=.venv
  case "$APP_DIR" in /mnt/*) venv="$HOME/.venvs/instant-solver" ;; esac
  [ -x "$venv/bin/python" ] || { rm -rf "$venv"; python3 -m venv "$venv"; }
  "$venv/bin/pip" install --upgrade pip
  "$venv/bin/pip" install -r requirements-dev.txt
  [ -f .env ] || cp .env.example .env
  (cd web && npm install)
  echo
  echo "Done. Start the app with two terminals:"
  echo "  make api    # engine on :8000"
  echo "  make web    # UI on :3000, then open http://localhost:3000"
}

if [ "${1:-}" = "--user" ]; then
  install_user
elif [ "$(id -u)" -eq 0 ]; then
  install_system
  if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    sudo -u "$SUDO_USER" bash "$0" --user
  else
    install_user
  fi
else
  echo "Run as root for system packages: sudo bash $0" >&2
  exit 1
fi
