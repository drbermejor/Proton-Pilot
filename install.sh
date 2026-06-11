#!/usr/bin/env bash
set -euo pipefail

APP_ID="proton-pilot"
APP_NAME="Proton Pilot"
SRC_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
BIN_DIR="$HOME/.local/bin"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

echo "Installing $APP_NAME..."

if ! need_cmd python3; then
  echo "Error: python3 is required." >&2
  exit 1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import PySide6
PY
then
  cat >&2 <<'EOF'
Warning: PySide6 is not installed.

Install it with your distro package manager, for example:
  Arch/CachyOS: sudo pacman -S python-pyside6
  Fedora:       sudo dnf install python3-pyside6
  Debian/Ubuntu: sudo apt install python3-pyside6.qtwidgets

The app may fall back to Zenity if available, but the full interface needs PySide6.
EOF
fi

mkdir -p "$INSTALL_DIR/assets" "$DESKTOP_DIR" "$BIN_DIR"
install -m 755 "$SRC_DIR/proton-pilot.py" "$INSTALL_DIR/proton-pilot.py"
install -m 644 "$SRC_DIR/assets/proton-pilot.png" "$INSTALL_DIR/assets/proton-pilot.png"
install -m 644 "$SRC_DIR/README.md" "$INSTALL_DIR/README.md"

cat > "$DESKTOP_DIR/proton-pilot.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Proton Pilot
Comment=Per-game Steam/Proton launch profile manager
Exec=$INSTALL_DIR/proton-pilot.py
Icon=$INSTALL_DIR/assets/proton-pilot.png
Terminal=false
Categories=Utility;Game;
EOF

ln -sf "$INSTALL_DIR/proton-pilot.py" "$BIN_DIR/proton-pilot"

if need_cmd update-desktop-database; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "Installed."
echo "Run from your application menu as: $APP_NAME"
echo "Or from terminal: proton-pilot"
