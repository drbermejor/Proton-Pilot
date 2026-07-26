#!/usr/bin/env bash
set -euo pipefail

APP_ID="proton-pilot"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID"
DESKTOP_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/applications/proton-pilot.desktop"
PROCESS_SELECTOR_DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications/proton-pilot-process-selector.desktop"
BIN_LINK="$HOME/.local/bin/proton-pilot"
PROCESS_SELECTOR_BIN="$HOME/.local/bin/proton-pilot-process-selector"

rm -f "$DESKTOP_FILE" "$PROCESS_SELECTOR_DESKTOP" "$BIN_LINK" "$PROCESS_SELECTOR_BIN"
rm -rf "$INSTALL_DIR"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" >/dev/null 2>&1 || true
fi

echo "Proton Pilot uninstalled."
echo "User config is kept at: $HOME/.config/proton-pilot"
