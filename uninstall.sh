#!/usr/bin/env bash
set -euo pipefail

APP_ID="proton-pilot"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID"
DESKTOP_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/applications/proton-pilot.desktop"
BIN_LINK="$HOME/.local/bin/proton-pilot"

rm -f "$DESKTOP_FILE" "$BIN_LINK"
rm -rf "$INSTALL_DIR"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" >/dev/null 2>&1 || true
fi

echo "Proton Pilot uninstalled."
echo "User config is kept at: $HOME/.config/proton-pilot"
