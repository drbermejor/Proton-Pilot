# Proton Pilot

<p align="center">
  <img src="assets/proton-pilot.png" alt="Proton Pilot logo" width="160">
</p>

<p align="center">
  <strong>Per-game Steam/Proton launch profile manager for Linux gaming.</strong>
</p>

Version: 0.8.7

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
- Lets you add a Steam game manually by name and AppID when local detection misses it.
- Lets you add an external Windows executable as a local Proton Pilot profile and launch it with an installed Proton build.
- Can also add external executable profiles to Steam's non-Steam shortcut library.
- Lets you edit or remove manually added games, with confirmation before removal.
- Extracts external executable icons when `icoutils` is available, so manual
  Proton profiles can look closer to their launcher/menu icon.
- Lets you choose and persist a custom Steam root path if automatic detection misses it.
- Reads and writes Steam launch options in `localconfig.vdf`.
- Creates a backup before writing changes.
- Shows system-aware recommendations based on detected GPU, session type, and installed tools.
- Shows clear system status cards for display resolution, HDR, VRR, GPU, and tools.
- Detects Bazzite, SteamOS-style sessions, Lenovo Legion Go devices, and handheld-friendly setups.
- Detects the primary monitor resolution and can force Gamescope to expose the real physical resolution to the game.
- Provides built-in per-game presets and user-created shared presets stored in a JSON config file.
- Provides an automatic shared `Recomendado del sistema` preset based on detected hardware and session.
- Lets you create, load, update, and delete your own shared presets.
- Lets you save a manually edited final command as a per-game custom preset.
- Shows ProtonDB official summary data, colored ratings, and community launch hints when available.
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
- `python-vdf` / `python3-vdf` for Steam non-Steam shortcut editing
- Steam installed locally

Optional tools detected and used by presets:

- `gamescope`
- `gamemoderun`
- `mangohud`
- `xdg-open`
- `icoutils` (`wrestool` and `icotool`) for extracting icons from external
  Windows executables

The installer supports dependency installation through:

- `pacman` for Arch/CachyOS
- `dnf` for Fedora
- `rpm-ostree` for Bazzite/Fedora Atomic
- `apt` for Debian/Ubuntu-based systems
- `zypper` for openSUSE

On Arch/CachyOS:

```bash
sudo pacman -S python-pyside6 python-vdf icoutils gamescope gamemode mangohud
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

Proton Pilot includes handheld-aware detection and presets for devices
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

## Test

```bash
python3 -m unittest discover -s tests
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

When Steam is open, the GUI can close Steam, write or clear launch options, and
then try to reopen Steam. If reopening fails, Proton Pilot shows a message asking
you to open Steam manually.

## Recommendation Colors

- Green: generally recommended default.
- Yellow: recommended based on detected local hardware/session/tools.
- Blue: option already detected in the current Steam launch command.

## Interface Notes

- The game list keeps a compact width and uses a horizontal scrollbar for long names.
- Steam library icons are shown when they exist in Steam's local cache.
- External executable icons are extracted from the `.exe` when `icoutils` is
  installed; otherwise Proton Pilot falls back to the generic icon.
- Launch options are displayed as a vertical list so each option is easier to scan.
- `Guardar comando manual` is highlighted in green. It is meant for cases where
  you edit the `Comando final` text directly; Proton Pilot will offer to create
  a per-game custom preset for that exact command.
- `Borrar opciones` is highlighted in red and asks for confirmation before clearing
  the saved Steam launch options for the selected game.
- The selected game panel shows the currently saved launch command and whether it
  matches a saved preset.
- Selecting a preset loads its options immediately. `Aplicar preset` is only
  needed when you want to save that selected preset to the game.
- If multiple presets generate the same launch command, Proton Pilot remembers
  the exact preset you applied for that game and selects it again when you
  return to the game.

## External Executables

The `Añadir juego` button supports two paths:

- `Steam AppID`: adds a Steam game manually when local manifest detection misses it.
- `Ejecutable Proton`: selects a Windows `.exe`/`.msi`, chooses an installed Proton
  build or a custom Proton path, and stores a local Proton Pilot profile.

External executable profiles do not write to Steam's `localconfig.vdf`. They are
stored in Proton Pilot's config and launched with:

```bash
STEAM_COMPAT_DATA_PATH=~/.config/proton-pilot/compatdata/<profile> proton run <exe>
```

When adding an external profile, Proton Pilot can optionally add it to Steam's
non-Steam shortcut library by writing `shortcuts.vdf` with a backup. If that
shortcut exists, saving the external profile can also update its Steam launch
options.

## Forcing Real Gamescope Resolution

On KDE Wayland with fractional scaling, a 2560x1440 monitor at 125% scale may
appear to games as a logical 2048x1152 surface. Proton Pilot can now force
Gamescope to expose the real monitor resolution using:

```bash
gamescope -f --force-windows-fullscreen -W 2560 -H 1440 -w 2560 -h 1440 -r 180 -- ...
```

Use the `Resolucion real Gamescope` option and press `Usar monitor principal`.
The app will fill the detected width, height, and refresh rate. It also creates
a per-game preset named `Monitor nativo Gamescope: <resolution>`.

## VRR FPS Cap

Use `VRR cap automatico` with Gamescope/Adaptive Sync to cap FPS just below the
applied refresh rate. Proton Pilot uses `Hz - 3`, so a 180 Hz display becomes:

```bash
MANGOHUD_CONFIG=fps_limit=177,no_display gamescope ... -- mangohud %command%
```

This uses MangoHud's limiter because Gamescope's `--framerate-limit` is rounded
as a divisor of the refresh rate on the tested local version, so `177` on a
180 Hz display can behave like 180.

The cap uses the refresh value currently applied in the Gamescope resolution
section. Press `Aplicar resolucion` or `Usar monitor principal` before saving if
you changed the Hz fields.

## Usability Notes

Preset selectors and Gamescope resolution spin boxes ignore the mouse wheel, so
scrolling through the app will not accidentally change the selected preset or
width/height/Hz fields. New presets created from the GUI are shared by default
and can be loaded for any game.

Yellow launch options are recommended or important for the detected system.
`Marcar recomendadas` enables those detected recommendations in the UI, but it
does not write anything to Steam until you create/update/apply a preset or save a
manual command.
Red launch options are useful but experimental or game-sensitive; Proton Pilot
may still recommend them when the system supports them, but they should be
validated per game.

`Gamescope fullscreen` starts the game inside Gamescope. `Resolucion real
Gamescope` is the mode-setting layer on top of that: it supplies the monitor's
real width, height, and refresh rate with `-W/-H/-w/-h/-r`.

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
- 0.6.2: Made the main window more compact and scrollable for small screens and
  handheld-style displays.
- 0.7.0: Added real-monitor Gamescope resolution forcing with automatic display
  detection, per-game native monitor presets, and UI fields for width/height/Hz.
- 0.7.1: Improved desktop layout: fixed-width game list, wider startup window,
  no horizontal scroll on the options panel, and two-column option grid.
- 0.7.2: Switched launch options to a vertical list, added Steam cached game
  icons, manual game entries, clearer save/delete buttons, and delete confirmation.
- 0.7.3: Added preset update flow, clearer preset feedback/confirmations, visible
  button frames, and experimental external executable profiles launched through
  detected or manually selected Proton builds.
- 0.7.4: Added configurable Steam root path and safer Steam launch-option writes
  that can close Steam, save/clear options, and reopen Steam automatically.
- 0.7.5: Fixed recommended options being re-selected after reloading a game,
  which could bring back MangoHud/GameMode after saving a preset without them.
- 0.7.6: Fixed preset application using stale stored commands and persisted
  side-effect options such as Unreal HDR tweaks per game.
- 0.7.7: Gamescope resolution fields now affect the command only after pressing
  `Aplicar resolucion` or `Usar monitor principal`, and preset logic has
  regression tests.
- 0.7.8: Added `VRR cap automatico`, which derives a Gamescope FPS cap from the
  applied monitor refresh rate.
- 0.7.9: Changed `VRR cap automatico` to use MangoHud's FPS limiter instead of
  Gamescope's divisor-based limiter.
- 0.8.0: Added shared user presets, disabled accidental mouse-wheel changes on
  preset and resolution controls, enabled launching Steam games from the GUI,
  highlighted key Gamescope options, and added official ProtonDB summary data.
- 0.8.1: Improved system recommendations for Gamescope/HDR, added colored
  ProtonDB ratings in the game list, clarified Gamescope option descriptions,
  and added optional Steam non-Steam shortcut creation for external profiles.
- 0.8.2: Added clearer colored system status cards, explicit HDR/VRR detection,
  ProtonDB rating badges, MangoHud toggle help, and cautious VRR/Adaptive Sync
  recommendations.
- 0.8.3: Added an automatic system-recommended preset, clearer selected-game
  panel, manual game edit/removal, a more prominent start button, cleaner GPU
  names, and removed launch confirmation popups.
- 0.8.4: Fixed initial game-list population so every detected Steam game appears
  in the GUI, not only the last sorted entry.
- 0.8.5: Preset selection now loads options automatically, the current applied
  preset is selected when opening a game, and applying a different preset asks
  for confirmation.
- 0.8.6: Stores the exact applied preset per game and shows a red pending state
  when the selected preset differs from the saved/applied one.
- 0.8.7: Extracts icons for external executables when `icoutils` is available
  and clarifies manual command saving by creating per-game custom presets.
