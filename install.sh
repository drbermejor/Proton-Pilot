#!/usr/bin/env bash
set -euo pipefail

APP_ID="proton-pilot"
APP_NAME="Proton Pilot"
SRC_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
BIN_DIR="$HOME/.local/bin"
INSTALL_DEPS="ask"

usage() {
  cat <<'EOF'
Usage: ./install.sh [--deps|--no-deps|--help]

Options:
  --deps     Install missing dependencies automatically when supported.
  --no-deps  Do not install dependencies; only install Proton Pilot.
  --help     Show this help.

Steam is intentionally not installed by this script.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deps) INSTALL_DEPS="yes" ;;
    --no-deps) INSTALL_DEPS="no" ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

python_has_pyside6() {
  python3 - <<'PY' >/dev/null 2>&1
import PySide6
PY
}

python_has_vdf() {
  python3 - <<'PY' >/dev/null 2>&1
import vdf
PY
}

missing_runtime_tools() {
  local missing=()
  need_cmd python3 || missing+=("python3")
  python_has_pyside6 || missing+=("PySide6")
  python_has_vdf || missing+=("python-vdf")
  if ! need_cmd wrestool || ! need_cmd icotool; then
    missing+=("icoutils")
  fi
  need_cmd gamescope || missing+=("gamescope")
  need_cmd gamemoderun || missing+=("gamemode")
  need_cmd mangohud || missing+=("mangohud")
  if [[ ${#missing[@]} -gt 0 ]]; then
    printf '%s\n' "${missing[@]}"
  fi
}

confirm() {
  local prompt="$1"
  if [[ "$INSTALL_DEPS" == "yes" ]]; then
    return 0
  fi
  if [[ "$INSTALL_DEPS" == "no" ]]; then
    return 1
  fi
  read -r -p "$prompt [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

install_with_pacman() {
  sudo pacman -S --needed python python-pyside6 python-vdf icoutils gamescope gamemode mangohud xdg-utils
}

install_with_dnf() {
  sudo dnf install -y python3 python3-pyside6 python3-vdf icoutils gamescope gamemode mangohud xdg-utils
}

install_with_rpm_ostree() {
  sudo rpm-ostree install python3-pyside6 python3-vdf icoutils gamescope gamemode mangohud xdg-utils
  echo
  echo "rpm-ostree installed packages. Reboot may be required before all dependencies are available."
}

install_with_apt() {
  sudo apt update
  sudo apt install -y python3 python3-pyside6.qtwidgets python3-vdf icoutils gamescope gamemode mangohud xdg-utils
}

install_with_zypper() {
  sudo zypper install -y python3 python3-qt6 python3-vdf icoutils gamescope gamemode mangohud xdg-utils
}

install_dependencies() {
  mapfile -t missing < <(missing_runtime_tools)
  if [[ ${#missing[@]} -eq 0 ]]; then
    echo "Dependencies look good."
    return 0
  fi

  echo "Missing or unavailable optional/runtime dependencies:"
  printf '  - %s\n' "${missing[@]}"
  echo
  echo "Steam is not installed by this script."

  if ! confirm "Install supported dependencies now?"; then
    echo "Skipping dependency installation."
    return 0
  fi

  if need_cmd pacman; then
    install_with_pacman
  elif need_cmd rpm-ostree; then
    install_with_rpm_ostree
  elif need_cmd dnf; then
    install_with_dnf
  elif need_cmd apt; then
    install_with_apt
  elif need_cmd zypper; then
    install_with_zypper
  else
    cat >&2 <<'EOF'
Could not detect a supported package manager.

Install these manually:
  python3, PySide6, python-vdf/python3-vdf, icoutils, gamescope, gamemode, mangohud, xdg-utils
EOF
  fi
}

echo "Installing $APP_NAME..."

install_dependencies

if ! need_cmd python3; then
  echo "Error: python3 is required and could not be installed automatically." >&2
  exit 1
fi

if ! python_has_pyside6; then
  echo "Warning: PySide6 is still unavailable. The full GUI needs PySide6." >&2
fi

if ! python_has_vdf; then
  echo "Warning: python-vdf is unavailable. Adding external profiles to Steam shortcuts will not work." >&2
fi

if ! need_cmd wrestool || ! need_cmd icotool; then
  echo "Warning: icoutils is unavailable. External executable icons will use the generic icon." >&2
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
