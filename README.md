# Proton Pilot

<p align="center">
  <img src="assets/proton-pilot.png" alt="Proton Pilot logo" width="160">
</p>

<p align="center">
  <strong>Per-game Steam/Proton launch profile manager for Linux gaming.</strong>
</p>

Version: 0.6.1

Proton Pilot is a local GUI for managing Steam launch options per installed game.
It is designed for Linux gaming setups using Steam, Proton, GE-Proton, Gamescope,
GameMode, MangoHud, HDR, VKD3D-Proton, and experimental options such as FSR4 upgrade.

## Descripcion En Castellano

**Proton Pilot** es una aplicacion grafica para gestionar opciones de lanzamiento
de Steam por juego en Linux. Detecta tus juegos instalados, tu GPU, tu sesion
grafica y herramientas como Gamescope, GameMode y MangoHud, y te propone perfiles
practicos para rendimiento, HDR, Ray Tracing, FSR4, Wayland y handhelds como
Lenovo Legion Go 2 con Bazzite o SteamOS.

La app no instala Steam ni modifica configuraciones globales del sistema. Solo
edita las opciones de lanzamiento por juego y crea copias de seguridad antes de
tocar `localconfig.vdf`.

## What It Does

- Detects installed Steam games from local app manifests.
- Reads and writes Steam launch options in `localconfig.vdf`.
- Creates a backup before writing changes.
- Shows system-aware recommendations based on detected GPU, session type, and installed tools.
- Detects Bazzite, SteamOS-style sessions, Lenovo Legion Go devices, and handheld-friendly setups.
- Provides per-game presets stored in a JSON config file.
- Lets you save, apply, and delete your own presets.
- Shows ProtonDB community recommendations when available.
- Opens the selected game's ProtonDB page.
- Can apply Unreal Engine HDR config tweaks for games that need them.

## Install

Clone the repository and run:

```bash
./install.sh
```

The installer can install missing dependencies on supported distributions. It
will ask before using `sudo` or `rpm-ostree`.

Automatic dependency install:

```bash
./install.sh --deps
```

Skip dependency installation:

```bash
./install.sh --no-deps
```

The installer copies the app to:

```bash
~/.local/share/proton-pilot
```

and creates:

```bash
~/.local/bin/proton-pilot
~/.local/share/applications/proton-pilot.desktop
```

Run it from the application menu as **Proton Pilot**, or from a terminal:

```bash
proton-pilot
```

## Requirements

- Python 3
- PySide6 for the full GUI
- Steam installed locally

Optional tools detected and used by presets:

- `gamescope`
- `gamemoderun`
- `mangohud`
- `xdg-open`

The installer supports dependency installation through:

- `pacman` for Arch/CachyOS
- `dnf` for Fedora
- `rpm-ostree` for Bazzite/Fedora Atomic
- `apt` for Debian/Ubuntu-based systems
- `zypper` for openSUSE

On Arch/CachyOS:

```bash
sudo pacman -S python-pyside6 gamescope gamemode mangohud
```

On Bazzite / Fedora Atomic-style systems, first check whether PySide6 is already
available:

```bash
python3 -c "import PySide6"
```

If it is missing, install it through your OS-supported package flow. On many
Fedora-based immutable systems this is:

```bash
rpm-ostree install python3-pyside6
systemctl reboot
```

SteamOS/Bazzite Gaming Mode normally already handles display modes, TDP, frame
limits, and overlays at the session level. Proton Pilot only edits per-game
Steam launch options.

## Legion Go 2 / Bazzite / SteamOS Compatibility

Proton Pilot 0.6.0 includes handheld-aware detection and presets for devices
like the Lenovo Legion Go 2 running Bazzite or SteamOS-style environments.

The Legion Go 2 class display is commonly reported as an 8.8-inch OLED 16:10
panel at 1920x1200 with up to 144 Hz and VRR. Proton Pilot therefore adds:

- `Handheld bateria: 800p / 60 FPS`
- `Handheld equilibrado: 800p / 72 FPS`
- `Legion Go 2 nativo: 1200p / 72 FPS`
- `Legion Go 2 OLED HDR`
- `Legion Go 2 FSR4 + Wayland`

The 800p profiles use:

```bash
gamescope -f -w 1280 -h 800
```

The native profile uses:

```bash
gamescope -f -w 1920 -h 1200
```

The app recommends handheld profiles when it detects Bazzite, SteamOS,
Gamescope sessions, or Lenovo Legion Go hardware. It does not modify BIOS,
TDP, fan curves, controller firmware, or system-level handheld services.

HDR on handheld Linux setups is still game, compositor, display, and OS-version
dependent. The HDR preset enables the launch path, but you may still need HDR
enabled in the OS/session and in the game.

## Uninstall

```bash
./uninstall.sh
```

User config is intentionally kept at:

```bash
~/.config/proton-pilot/config.json
```

## Config File

The app stores its own configuration here:

```bash
~/.config/proton-pilot/config.json
```

If an older config exists at `~/.config/steam-game-options/config.json`, Proton Pilot
copies it on first launch.

## Steam Files Touched

Launch options are written to:

```bash
~/.local/share/Steam/userdata/<account>/config/localconfig.vdf
```

Backups are created next to that file before saving.

Close Steam before saving launch options when possible. Steam can rewrite
`localconfig.vdf` when it exits.

## Recommendation Colors

- Green: generally recommended default.
- Yellow: recommended based on detected local hardware/session/tools.
- Blue: option already detected in the current Steam launch command.

## Important Notes

`PROTON_FSR4_UPGRADE=1` attempts to upgrade compatible FSR 3.1 paths to FSR4 in
Proton builds that support it. It is not universal and depends on the game,
GPU, driver, and Proton build.

`PROTON_ENABLE_WAYLAND=1` forces Wine/Proton's Wayland driver. It can improve
integration on Wayland sessions, but some games may have input, overlay, or
launcher issues.

HDR generally needs Gamescope HDR, a working HDR desktop/display path, and game
support or game-specific configuration.

## Iteration History

- 0.1.0: Initial Zenity launch option tool.
- 0.2.0: Added HDR, GameMode, MangoHud, Gamescope, and custom options.
- 0.3.0: Added ProtonDB actions and per-game presets.
- 0.4.0: Rebuilt as a PySide6 GUI with clearer panels and recommendations.
- 0.5.0: Renamed to Proton Pilot, added custom logo, system-aware recommendations,
  hover descriptions, FSR4/Wayland options, README, and versioning.
- 0.6.0: Added Bazzite/SteamOS/handheld detection, Legion Go 2 presets, 800p/1200p
  Gamescope profiles, frame-limit presets, and handheld documentation.
- 0.6.1: Added dependency installation to `install.sh`, README logo, and Spanish
  project description.
