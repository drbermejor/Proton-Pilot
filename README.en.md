# Proton Pilot

Proton Pilot is a Linux desktop app for managing Steam/Proton launch profiles per
game. It helps configure Gamescope, GameMode, MangoHud, HDR, VRR, Proton
versions, ProtonDB information, handheld presets, and custom launch options.

Current version: 0.11.0

## Install

```bash
./install.sh --deps
```

To skip dependency installation:

```bash
./install.sh --no-deps
```

The installed command is:

```bash
proton-pilot
```

## AppImage

Build an AppImage with:

```bash
./build-appimage.sh
```

The output is created in `dist/`.

## Main Features

- Detects installed Steam games and manually added games.
- Reads and writes Steam launch options per game.
- Shows and changes the Proton compatibility tool used by each game.
- Provides system recommendations based on GPU, display, session, and tools.
- Provides Gamescope resolution forcing, HDR, VRR, FPS cap, handheld, RT/DXR,
  FSR4, Wayland, MangoHud, and GameMode toggles.
- Splits `ENABLE_GAMESCOPE_WSI=1` into its own HDR-related option and warns
  when FSR4 is combined with HDR/WSI, because some games can show bad color.
- HDR/VRR diagnostics explain which HDR options to enable based on detected
  KDE, Gamescope, Gamescope WSI, and monitor state.
- Adds an experimental skip intro/splash option using
  `-nosplash -nostartupscreen`.
- Uses clearer goal-oriented option categories:
  - Base and performance
  - Gamescope, display and VRR
  - HDR
  - Scaling and handheld
  - Advanced compatibility
  - Custom / other
- Lets users create custom launch-option toggles, assign them to categories,
  delete them to a restoreable trash list, and restore them later.
- Stores profiles and app configuration in `~/.config/proton-pilot/config.json`.
- Redesigns the flow around profiles: real Steam command, applied profile,
  selected pending profile, and prepared changes are shown separately.
- Detects manual Steam commands that do not match any saved profile and lets you
  import them as a profile, overwrite them with the selected profile, or compare
  differences.
- Shows each game's state in the list: no profile, applied profile, pending
  changes, or manual command.
- Offers compact mode, read-only mode, and a persistent English/Spanish language
  preference.
- The interface can switch between English and Spanish across panels, buttons,
  tooltips, option descriptions, diagnostics, and common dialogs.

## Safe Steam Writes

Steam can overwrite `localconfig.vdf` when it exits. Proton Pilot can close Steam
before writing launch options in Desktop Mode and reopen it afterwards. If Steam
Gaming Mode is detected, Proton Pilot avoids closing Steam automatically and asks
you to apply changes from Desktop Mode or after closing Steam manually.

## Handheld Notes

Proton Pilot includes handheld-aware profiles for Bazzite, SteamOS-style sessions,
and Lenovo Legion Go class devices. Current handheld support is profile-oriented.
A controller-first handheld UI is planned separately.

## GitHub Releases

Stable builds are published in GitHub Releases as AppImages:

https://github.com/drbermejor/Proton-Pilot/releases
