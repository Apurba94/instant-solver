#!/usr/bin/env bash
# Copy the project from the Windows drive into the WSL home directory and run it
# from there. Node and Python tooling cannot set Linux permissions on /mnt/<drive>
# and is many times slower there, so the Windows folder stays the copy you edit
# and ~/instant-solver is the copy that runs.
#
#   bash "/mnt/d/C Drive Download/instant-solver/instant-solver/scripts/sync-to-wsl.sh"
#
# Re-run after editing files on Windows. Dependencies and build output in the
# WSL copy are kept.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$HOME/instant-solver}"

command -v rsync >/dev/null || { echo "Installing rsync"; sudo apt-get install -y rsync; }
mkdir -p "$DEST"
rsync -rt --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
  --exclude node_modules --exclude .next --exclude .venv --exclude __pycache__ \
  --exclude .env --exclude screenshots \
  "$SRC/" "$DEST/"
chmod +x "$DEST"/scripts/*.sh "$DEST"/deploy/*.sh
[ -f "$DEST/.env" ] || { [ -f "$SRC/.env" ] && cp "$SRC/.env" "$DEST/.env" || true; }
echo "Synced to $DEST"
