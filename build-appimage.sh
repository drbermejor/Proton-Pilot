#!/usr/bin/env bash
set -euo pipefail

APP_ID="proton-pilot"
APP_NAME="Proton Pilot"
VERSION="$(grep -E '^APP_VERSION = ' proton-pilot.py | sed -E 's/.*"([^"]+)".*/\1/')"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$ROOT_DIR/dist/appimage"
APPDIR="$BUILD_DIR/ProtonPilot.AppDir"
OUT_DIR="$ROOT_DIR/dist"
APPIMAGETOOL="$BUILD_DIR/appimagetool-x86_64.AppImage"

mkdir -p "$APPDIR/usr/share/$APP_ID" "$APPDIR/usr/share/$APP_ID/tools" "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$OUT_DIR"
rm -rf "$APPDIR/usr/share/$APP_ID" "$APPDIR/usr/venv"
mkdir -p "$APPDIR/usr/share/$APP_ID" "$APPDIR/usr/share/$APP_ID/tools" "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

python3 -m venv --copies "$APPDIR/usr/venv"
"$APPDIR/usr/venv/bin/python" -m pip install --upgrade pip
"$APPDIR/usr/venv/bin/python" -m pip install PySide6 vdf

install -m 755 "$ROOT_DIR/proton-pilot.py" "$APPDIR/usr/share/$APP_ID/proton-pilot.py"
install -m 755 "$ROOT_DIR/tools/hung-process-selector.py" "$APPDIR/usr/share/$APP_ID/tools/hung-process-selector.py"
install -m 644 "$ROOT_DIR/README.md" "$APPDIR/usr/share/$APP_ID/README.md"
mkdir -p "$APPDIR/usr/share/$APP_ID/assets"
install -m 644 "$ROOT_DIR/assets/proton-pilot.png" "$APPDIR/usr/share/$APP_ID/assets/proton-pilot.png"
install -m 644 "$ROOT_DIR/assets/proton-pilot.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
install -m 644 "$ROOT_DIR/assets/proton-pilot.png" "$APPDIR/$APP_ID.png"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONNOUSERSITE=1
exec "$HERE/usr/venv/bin/python" "$HERE/usr/share/proton-pilot/proton-pilot.py" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/usr/share/applications/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Steam/Proton launch profile manager
Exec=proton-pilot
Icon=$APP_ID
Categories=Game;Utility;
Terminal=false
EOF
cp "$APPDIR/usr/share/applications/$APP_ID.desktop" "$APPDIR/$APP_ID.desktop"

ln -sf ../venv/bin/python "$APPDIR/usr/bin/proton-pilot-python"

if command -v appimagetool >/dev/null 2>&1; then
  TOOL="$(command -v appimagetool)"
else
  if [ ! -x "$APPIMAGETOOL" ]; then
    curl -L --fail -o "$APPIMAGETOOL" "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
  fi
  echo "Extracting appimagetool runtime for systems without libfuse.so.2..."
  rm -rf "$BUILD_DIR/squashfs-root"
  (cd "$BUILD_DIR" && "$APPIMAGETOOL" --appimage-extract >/dev/null)
  TOOL="$BUILD_DIR/squashfs-root/AppRun"
fi

ARCH=x86_64 "$TOOL" "$APPDIR" "$OUT_DIR/Proton-Pilot-$VERSION-x86_64.AppImage"
echo "Built: $OUT_DIR/Proton-Pilot-$VERSION-x86_64.AppImage"
