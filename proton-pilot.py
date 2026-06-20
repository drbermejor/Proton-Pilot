#!/usr/bin/env python3
import datetime as _dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path


HOME = Path.home()
APP_NAME = "Proton Pilot"
APP_VERSION = "0.10.5"
APP_REPO = "drbermejor/Proton-Pilot"
APP_DIR = Path(__file__).resolve().parent
APP_ICON_CANDIDATES = [
    APP_DIR / "assets/proton-pilot.png",
    APP_DIR / "proton-pilot-assets/proton-pilot.png",
]
APP_CONFIG_DIR = HOME / ".config/proton-pilot"
APP_CONFIG_FILE = APP_CONFIG_DIR / "config.json"
APP_CACHE_DIR = APP_CONFIG_DIR / "cache"
LEGACY_CONFIG_FILE = HOME / ".config/steam-game-options/config.json"
STEAM_ROOTS = [
    HOME / ".local/share/Steam",
    HOME / ".steam/root",
    HOME / ".var/app/com.valvesoftware.Steam/data/Steam",
]
PROTON_TOOL_DIRS = [
    HOME / ".local/share/Steam/compatibilitytools.d",
    HOME / ".steam/root/compatibilitytools.d",
    HOME / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d",
    Path("/usr/share/steam/compatibilitytools.d"),
]

PRESETS = {
    "HDR": "HDR via Gamescope",
    "RT": "Ray Tracing DXR (forzar VKD3D)",
    "NVIDIA": "NVIDIA NVAPI/DLSS",
    "DX12": "Forzar DX12 (-dx12)",
    "GAMEMODE": "GameMode",
    "MANGOHUD": "MangoHud",
    "GAMESCOPE": "Gamescope fullscreen",
    "ADAPTIVE": "Adaptive Sync",
    "CAPVRR": "VRR cap automatico",
    "UEHDR": "Forzar HDR Unreal Engine.ini",
    "NODXR": "Desactivar Ray Tracing DXR",
    "PROTONDB": "Abrir ProtonDB del juego",
    "RECOMMEND": "Ver recomendaciones ProtonDB",
    "CUSTOM": "Ajustes personalizados",
}

SIDE_EFFECT_OPTIONS = {"UEHDR"}

HIDDEN_APP_NAMES = (
    "Proton ",
    "Steam Linux Runtime",
    "Steamworks Common Redistributables",
)

HDR_ENGINE_LINES = {
    "r.AllowHDR": "1",
    "r.HDR.EnableHDROutput": "1",
    "r.HDR.Display.OutputDevice": "5",
    "r.HDR.Display.ColorGamut": "2",
    "r.HDR.UI.CompositeMode": "1",
    "r.HDR.UI.Level": "1.5",
}

DEFAULT_APP_CONFIG = {
    "protondb_api": "https://protondb.max-p.me",
    "custom": {},
    "external_games": [],
    "external_launch_options": {},
    "manual_games": [],
    "presets": {},
    "shared_presets": {},
    "protondb_cache": {},
    "last_selected": [],
    "steam_root": "",
    "launch_history": {},
    "proton_history": {},
    "compact_mode": False,
    "read_only": False,
    "custom_options": [],
    "custom_options_trash": [],
    "option_category_expanded": {},
    "language": "es",
}

OPTION_INFO = {
    "GAMEMODE": {
        "label": "Activar GameMode",
        "description": "Activa GameMode para pedir al sistema perfil de rendimiento mientras el juego esta abierto.",
        "tokens": "gamemoderun",
        "recommended": True,
    },
    "MANGOHUD": {
        "label": "Mostrar MangoHud",
        "description": "Muestra overlay de FPS, frametime, GPU/CPU y temperaturas. Con Gamescope se aplica como --mangoapp. Atajo ingame: Shift derecho + F12 muestra u oculta el overlay.",
        "tokens": "mangohud o gamescope --mangoapp",
        "recommended": True,
    },
    "HDR": {
        "label": "Activar HDR con Gamescope",
        "description": "Ruta principal para HDR en Proton: activa Gamescope HDR, Gamescope WSI y HDR WSI para que el juego pueda ver una pantalla HDR.",
        "tokens": "ENABLE_HDR_WSI=1 ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope --hdr-enabled",
        "recommended": False,
        "important": True,
    },
    "WAYLAND": {
        "label": "Usar Proton Wayland",
        "description": "Fuerza el driver Wayland de Wine/Proton. Puede mejorar integracion en Wayland, pero en algunos juegos rompe overlay o entrada.",
        "tokens": "PROTON_ENABLE_WAYLAND=1",
        "recommended": False,
    },
    "PROTONHDR": {
        "label": "Activar HDR de Proton",
        "description": "Activa el flag HDR propio de Proton si tu build lo soporta. Complementa, no sustituye, Gamescope HDR.",
        "tokens": "PROTON_ENABLE_HDR=1",
        "recommended": False,
        "important": True,
    },
    "FSR4": {
        "label": "Intentar upgrade a FSR 4",
        "description": "Intenta actualizar FSR 3.1 a FSR 4 en builds Proton/GE/Cachy que lo soportan. Requiere juego compatible y GPU/driver adecuados; no es universal.",
        "tokens": "PROTON_FSR4_UPGRADE=1",
        "recommended": False,
    },
    "FSR4IND": {
        "label": "Mostrar indicador FSR 4",
        "description": "Muestra un indicador/overlay para comprobar si el upgrade FSR4 esta funcionando, si tu Proton lo soporta.",
        "tokens": "PROTON_FSR4_INDICATOR=1",
        "recommended": False,
    },
    "GAMESCOPE": {
        "label": "Usar Gamescope a pantalla completa",
        "description": "Mete el juego dentro de Gamescope a pantalla completa. Es el contenedor/compositor: habilita HDR, VRR, escalado y control de pantalla. Por si solo no fuerza una resolucion concreta.",
        "tokens": "gamescope -f --",
        "recommended": False,
        "important": True,
    },
    "REALRES": {
        "label": "Forzar resolucion nativa en Gamescope",
        "description": "Anade -W/-H/-w/-h/-r para que Gamescope exponga al juego la resolucion y Hz reales del monitor. Requiere Gamescope; es el ajuste de modo/resolucion, no el contenedor.",
        "tokens": "gamescope -W <monitor_w> -H <monitor_h> -w <game_w> -h <game_h> -r <hz>",
        "recommended": False,
        "important": True,
    },
    "HANDHELD800P": {
        "label": "Modo portatil 800p",
        "description": "Ejecuta el juego a 1280x800 dentro de Gamescope. Perfil util para Legion Go 2, SteamOS/Bazzite y juegos pesados.",
        "tokens": "gamescope -f -w 1280 -h 800 --",
        "recommended": False,
    },
    "HANDHELD1200P": {
        "label": "Modo portatil 1200p nativo",
        "description": "Ejecuta el juego a 1920x1200 dentro de Gamescope, pensado para la pantalla 16:10 de Legion Go 2.",
        "tokens": "gamescope -f -w 1920 -h 1200 --",
        "recommended": False,
    },
    "CAP60": {
        "label": "Limitar a 60 FPS",
        "description": "Anade limite simple de 60 FPS en Gamescope para bajar consumo y estabilizar frametime.",
        "tokens": "gamescope --framerate-limit 60",
        "recommended": False,
    },
    "CAP72": {
        "label": "Limitar a 72 FPS",
        "description": "Anade limite simple de 72 FPS en Gamescope. Encaja bien con pantallas de 144 Hz al dividir por dos.",
        "tokens": "gamescope --framerate-limit 72",
        "recommended": False,
    },
    "CAPVRR": {
        "label": "Limitar FPS para VRR",
        "description": "Limita FPS unos pocos frames por debajo de los Hz aplicados para evitar tocar el techo VRR. Usa MangoHud porque Gamescope redondea su limitador a divisores del refresco.",
        "tokens": "MANGOHUD_CONFIG=fps_limit=<Hz-3> mangohud",
        "recommended": False,
        "caution": True,
    },
    "GSFSR": {
        "label": "Escalar con FSR de Gamescope",
        "description": "Usa el escalador FSR 1.0 de Gamescope para subir desde una resolucion menor. No es FSR2/3/4 del juego.",
        "tokens": "gamescope -F fsr --sharpness 5",
        "recommended": False,
    },
    "GSNIS": {
        "label": "Escalar con NIS de Gamescope",
        "description": "Usa NVIDIA Image Scaling en Gamescope. Puede gustar mas o menos que FSR segun juego/pantalla.",
        "tokens": "gamescope -F nis --sharpness 5",
        "recommended": False,
    },
    "ADAPTIVE": {
        "label": "Activar VRR / Adaptive Sync",
        "description": "Pide VRR/Adaptive Sync a Gamescope si tu pantalla y sesion lo soportan.",
        "tokens": "gamescope --adaptive-sync",
        "recommended": False,
        "caution": True,
    },
    "RT": {
        "label": "Forzar Ray Tracing DXR",
        "description": "Fuerza DXR en VKD3D-Proton incluso si se considera inseguro. Hoy DXR suele activarse solo; usalo si el juego no lo expone.",
        "tokens": "VKD3D_CONFIG=dxr",
        "recommended": False,
    },
    "NODXR": {
        "label": "Desactivar Ray Tracing DXR",
        "description": "Desactiva DXR en VKD3D-Proton. Util si el ray tracing causa cuelgues, glitches o bajones fuertes.",
        "tokens": "VKD3D_CONFIG=nodxr",
        "recommended": False,
    },
    "DX12": {
        "label": "Anadir -dx12",
        "description": "Anade -dx12 despues de %command%. Solo algunos juegos o motores lo reconocen.",
        "tokens": "%command% -dx12",
        "recommended": False,
    },
    "NVIDIA": {
        "label": "Activar NVIDIA DLSS/NVAPI",
        "description": "Solo para NVIDIA: expone NVAPI/DLSS/NGX al juego. En AMD normalmente no conviene.",
        "tokens": "PROTON_ENABLE_NVAPI=1 PROTON_HIDE_NVIDIA_GPU=0 PROTON_ENABLE_NGX_UPDATER=1",
        "recommended": False,
    },
    "UEHDR": {
        "label": "Forzar HDR Unreal Engine.ini",
        "description": "Escribe variables HDR en Engine.ini y GameUserSettings.ini para juegos Unreal que no muestran HDR por menu.",
        "tokens": "Engine.ini [SystemSettings] r.HDR...",
        "recommended": False,
    },
}

OPTION_GROUPS = [
    ("Base y rendimiento", ("GAMEMODE", "MANGOHUD", "DX12", "FSR4", "FSR4IND")),
    ("Gamescope, pantalla y VRR", ("GAMESCOPE", "REALRES", "ADAPTIVE", "CAPVRR", "CAP60", "CAP72")),
    ("HDR", ("HDR", "PROTONHDR", "UEHDR")),
    ("Escalado y handheld", ("HANDHELD800P", "HANDHELD1200P", "GSFSR", "GSNIS")),
    ("Compatibilidad avanzada", ("WAYLAND", "RT", "NODXR", "NVIDIA")),
    ("Personalizadas / otros", ()),
]
OPTION_GROUP_TITLES = [title for title, _keys in OPTION_GROUPS]
LEGACY_OPTION_GROUPS = {
    "Rendimiento y monitorizacion": "Base y rendimiento",
    "Pantalla, HDR y Gamescope": "Gamescope, pantalla y VRR",
    "Compatibilidad Proton": "Compatibilidad avanzada",
}
CUSTOM_OPTION_PREFIX = "CUSTOMOPT:"

OPTION_LABEL_EN = {
    "GAMEMODE": "Enable GameMode",
    "MANGOHUD": "Show MangoHud",
    "HDR": "Enable HDR with Gamescope",
    "WAYLAND": "Use Proton Wayland",
    "PROTONHDR": "Enable Proton HDR",
    "FSR4": "Try FSR 4 upgrade",
    "FSR4IND": "Show FSR 4 indicator",
    "GAMESCOPE": "Use Gamescope fullscreen",
    "REALRES": "Force native resolution in Gamescope",
    "HANDHELD800P": "Handheld mode 800p",
    "HANDHELD1200P": "Handheld mode native 1200p",
    "CAP60": "Limit to 60 FPS",
    "CAP72": "Limit to 72 FPS",
    "CAPVRR": "Limit FPS for VRR",
    "GSFSR": "Scale with Gamescope FSR",
    "GSNIS": "Scale with Gamescope NIS",
    "ADAPTIVE": "Enable VRR / Adaptive Sync",
    "RT": "Force Ray Tracing DXR",
    "NODXR": "Disable Ray Tracing DXR",
    "DX12": "Add -dx12",
    "NVIDIA": "Enable NVIDIA DLSS/NVAPI",
    "UEHDR": "Force HDR in Unreal Engine",
}

OPTION_DESCRIPTION_EN = {
    "GAMEMODE": "Enables GameMode so the system uses a performance profile while the game is running.",
    "MANGOHUD": "Shows the FPS, frametime, GPU/CPU and temperature overlay. With Gamescope it is applied as --mangoapp. In game: Right Shift + F12 toggles the overlay.",
    "HDR": "Main HDR path for Proton: enables Gamescope HDR, Gamescope WSI and HDR WSI so the game can see an HDR display.",
    "WAYLAND": "Forces Wine/Proton's Wayland driver. It can improve Wayland integration, but some games may lose overlays or input behavior.",
    "PROTONHDR": "Enables Proton's own HDR flag when your Proton build supports it. It complements Gamescope HDR; it does not replace it.",
    "FSR4": "Attempts to upgrade FSR 3.1 to FSR 4 on Proton/GE/Cachy builds that support it. Requires a compatible game, GPU and driver; it is not universal.",
    "FSR4IND": "Shows an indicator/overlay to check whether the FSR 4 upgrade is working, if your Proton build supports it.",
    "GAMESCOPE": "Runs the game inside fullscreen Gamescope. This is the compositor/container that enables HDR, VRR, scaling and display control. It does not force a specific resolution by itself.",
    "REALRES": "Adds -W/-H/-w/-h/-r so Gamescope exposes the monitor's real resolution and refresh rate to the game. Requires Gamescope.",
    "HANDHELD800P": "Runs the game at 1280x800 inside Gamescope. Useful for Legion Go 2, SteamOS/Bazzite and heavy games.",
    "HANDHELD1200P": "Runs the game at 1920x1200 inside Gamescope, aimed at 16:10 handheld displays.",
    "CAP60": "Adds a simple 60 FPS Gamescope limit to reduce power use and stabilize frametimes.",
    "CAP72": "Adds a simple 72 FPS Gamescope limit. Works well on 144 Hz screens as a half-rate cap.",
    "CAPVRR": "Limits FPS a few frames below the active refresh rate to avoid hitting the VRR ceiling. Uses MangoHud because Gamescope can round limits to refresh divisors.",
    "GSFSR": "Uses Gamescope FSR 1.0 scaling from a lower resolution. This is not the game's FSR2/3/4.",
    "GSNIS": "Uses NVIDIA Image Scaling in Gamescope. It may look better or worse than FSR depending on the game and display.",
    "ADAPTIVE": "Requests VRR/Adaptive Sync in Gamescope if your display and session support it.",
    "RT": "Forces DXR in VKD3D-Proton even when it is considered unsafe. Modern DXR is often automatic; use this when the game does not expose it.",
    "NODXR": "Disables DXR in VKD3D-Proton. Useful if ray tracing causes crashes, glitches or large FPS drops.",
    "DX12": "Adds -dx12 after %command%. Only some games or engines understand it.",
    "NVIDIA": "NVIDIA only: exposes NVAPI/DLSS/NGX to the game. It is usually not useful on AMD.",
    "UEHDR": "Writes HDR variables into Engine.ini and GameUserSettings.ini for Unreal games that do not show HDR in their menu.",
}

CATEGORY_LABEL_EN = {
    "Base y rendimiento": "Base and performance",
    "Gamescope, pantalla y VRR": "Gamescope, display and VRR",
    "HDR": "HDR",
    "Escalado y handheld": "Scaling and handheld",
    "Compatibilidad avanzada": "Advanced compatibility",
    "Personalizadas / otros": "Custom / other",
}

UI_TEXT = {
    "es": {
        "version_subtitle": "Version {version} - perfiles de lanzamiento para Steam/Proton",
        "steam_path": "Ruta Steam",
        "compact": "Modo compacto",
        "read_only": "Solo lectura",
        "games_installed": "1. Juegos instalados",
        "add_game": "Añadir juego",
        "edit_manual": "Editar manual",
        "remove_manual": "Quitar manual",
        "launch": "Iniciar juego",
        "tabs": ["Resumen", "Presets", "Opciones", "Avanzado"],
        "options_box": "Opciones que se aplicaran al lanzamiento",
        "add_option": "+ Opcion manual",
        "delete_option": "Papelera",
        "restore_option": "Restaurar",
        "save_manual": "Guardar comando manual",
        "clear_options": "Borrar opciones",
        "reload": "Recargar",
        "active": "activas",
        "recommended": "recomendadas",
        "options": "opciones",
        "manual": "manual",
        "expand": "Abrir",
        "collapse": "Cerrar",
        "select_game": "Selecciona un juego",
        "select_game_hint": "Selecciona un juego para ver sus opciones.",
        "launch_tip": "Inicia el juego seleccionado. Steam usara las opciones que ya esten guardadas.",
        "proton_missing": "Proton: sin detectar",
        "proton_recommended_btn": "Recomendada",
        "apply_proton": "Aplicar Proton",
        "no_pending": "Sin cambios pendientes.",
        "current_preset_unknown": "Preset actual: sin detectar",
        "protondb_no_data": "ProtonDB: sin datos",
        "system_recs": "Recomendaciones segun tu sistema",
        "status_system": "Sistema",
        "status_display": "Pantalla",
        "status_hdr": "HDR sistema",
        "status_tools": "Herramientas",
        "status_mode": "Modo",
        "yes": "si",
        "no": "no",
        "detected": "DETECTADO",
        "desktop_mode": "Desktop Mode",
        "not_detected": "no detectado",
        "session": "sesion",
        "main_monitor": "monitor",
        "actions": "Acciones frecuentes",
        "tools": "Herramientas y diagnostico",
        "recommendations": "Recomendaciones",
        "open_protondb": "Abrir ProtonDB",
        "mark_recommended": "Marcar recomendadas",
        "profile_assistant": "Asistente perfil",
        "apply_prepared": "Aplicar cambios preparados",
        "compare": "Comparar",
        "history": "Historial",
        "display_diag": "Diagnostico HDR/VRR",
        "proton_history": "Historial Proton",
        "register_appimage": "Registrar AppImage",
        "check_updates": "Buscar actualizacion",
        "about": "Acerca de",
        "presets_box": "Presets del juego",
        "apply_preset": "Aplicar preset",
        "create_preset": "Crear nuevo preset",
        "update_preset": "Actualizar preset",
        "delete_preset": "Borrar preset",
        "preset_choose": "Selecciona un preset para cargarlo.",
        "resolution_box": "Resolucion Gamescope",
        "apply_resolution": "Aplicar resolucion",
        "use_main_monitor": "Usar monitor principal",
        "width": "Ancho",
        "height": "Alto",
        "custom_box": "Ajustes personalizados",
        "before": "Antes:",
        "after": "Despues:",
        "final_command": "Comando final",
        "option_detail_hint": "Pasa el cursor por encima de una opcion para ver que hace y que anade al lanzamiento.",
        "system_recommended_suffix": "sistema",
        "recommended_suffix": "recomendado",
        "try_suffix": "probar",
        "important_suffix": "importante",
    },
    "en": {
        "version_subtitle": "Version {version} - Steam/Proton launch profiles",
        "steam_path": "Steam path",
        "compact": "Compact mode",
        "read_only": "Read only",
        "games_installed": "1. Installed games",
        "add_game": "Add game",
        "edit_manual": "Edit manual",
        "remove_manual": "Remove manual",
        "launch": "Launch game",
        "tabs": ["Summary", "Presets", "Options", "Advanced"],
        "options_box": "Launch options to apply",
        "add_option": "+ Custom option",
        "delete_option": "Trash",
        "restore_option": "Restore",
        "save_manual": "Save manual command",
        "clear_options": "Clear options",
        "reload": "Reload",
        "active": "active",
        "recommended": "recommended",
        "options": "options",
        "manual": "manual",
        "expand": "Expand",
        "collapse": "Collapse",
        "select_game": "Select a game",
        "select_game_hint": "Select a game to see its options.",
        "launch_tip": "Launches the selected game. Steam will use the options already saved.",
        "proton_missing": "Proton: not detected",
        "proton_recommended_btn": "Recommended",
        "apply_proton": "Apply Proton",
        "no_pending": "No pending changes.",
        "current_preset_unknown": "Current preset: not detected",
        "protondb_no_data": "ProtonDB: no data",
        "system_recs": "Recommendations from your system",
        "status_system": "System",
        "status_display": "Display",
        "status_hdr": "System HDR",
        "status_tools": "Tools",
        "status_mode": "Mode",
        "yes": "yes",
        "no": "no",
        "detected": "DETECTED",
        "desktop_mode": "Desktop Mode",
        "not_detected": "not detected",
        "session": "session",
        "main_monitor": "monitor",
        "actions": "Frequent actions",
        "tools": "Tools and diagnostics",
        "recommendations": "Recommendations",
        "open_protondb": "Open ProtonDB",
        "mark_recommended": "Mark recommended",
        "profile_assistant": "Profile assistant",
        "apply_prepared": "Apply prepared changes",
        "compare": "Compare",
        "history": "History",
        "display_diag": "HDR/VRR diagnostics",
        "proton_history": "Proton history",
        "register_appimage": "Register AppImage",
        "check_updates": "Check for updates",
        "about": "About",
        "presets_box": "Game presets",
        "apply_preset": "Apply preset",
        "create_preset": "Create new preset",
        "update_preset": "Update preset",
        "delete_preset": "Delete preset",
        "preset_choose": "Select a preset to load it.",
        "resolution_box": "Gamescope resolution",
        "apply_resolution": "Apply resolution",
        "use_main_monitor": "Use primary monitor",
        "width": "Width",
        "height": "Height",
        "custom_box": "Custom adjustments",
        "before": "Before:",
        "after": "After:",
        "final_command": "Final command",
        "option_detail_hint": "Hover an option to see what it does and what it adds to launch.",
        "system_recommended_suffix": "system",
        "recommended_suffix": "recommended",
        "try_suffix": "try",
        "important_suffix": "important",
    },
}


def z(args, text=None, check=True):
    proc = subprocess.run(
        ["zenity", *args],
        input=text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        sys.exit(proc.returncode)
    return proc.stdout.strip()


def info(msg):
    z(["--info", "--title=Steam Game Options", f"--text={msg}"], check=False)


def question(msg):
    proc = subprocess.run(
        ["zenity", "--question", "--title=Steam Game Options", f"--text={msg}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def error(msg):
    z(["--error", "--title=Steam Game Options", f"--text={msg}"], check=False)


def load_app_config():
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not APP_CONFIG_FILE.exists() and LEGACY_CONFIG_FILE.exists():
        shutil.copy2(LEGACY_CONFIG_FILE, APP_CONFIG_FILE)
    if not APP_CONFIG_FILE.exists():
        data = dict(DEFAULT_APP_CONFIG)
        ensure_builtin_presets(data)
        APP_CONFIG_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))
        return data
    try:
        data = json.loads(APP_CONFIG_FILE.read_text(errors="replace"))
    except json.JSONDecodeError:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(APP_CONFIG_FILE, APP_CONFIG_FILE.with_suffix(f".broken-{stamp}.json"))
        data = {}
    merged = dict(DEFAULT_APP_CONFIG)
    merged.update(data)
    ensure_builtin_presets(merged)
    save_app_config(merged)
    return merged


def save_app_config(config):
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    APP_CONFIG_FILE.write_text(json.dumps(config, indent=2, sort_keys=True))


def ensure_builtin_presets(config):
    config.setdefault("shared_presets", {})
    presets = config.setdefault("presets", {})
    dune = presets.setdefault("1172710", {})
    builtins = {
        "Seguro: GameMode + MangoHud": {
            "options": ["GAMEMODE", "MANGOHUD"],
            "custom_pre": "",
            "custom_post": "",
            "command": "mangohud gamemoderun %command%",
        },
        "HDR: Gamescope + GameMode": {
            "options": ["HDR", "GAMEMODE", "MANGOHUD", "UEHDR"],
            "custom_pre": "",
            "custom_post": "",
            "command": "ENABLE_HDR_WSI=1 ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope -f --hdr-enabled --mangoapp -- gamemoderun %command%",
        },
        "FSR4 + Wayland literal": {
            "options": ["FSR4", "WAYLAND"],
            "custom_pre": "",
            "custom_post": "",
            "command": "PROTON_FSR4_UPGRADE=1 PROTON_ENABLE_WAYLAND=1 %command%",
        },
        "Experimental: FSR4 + Wayland + HDR": {
            "options": ["FSR4", "WAYLAND", "PROTONHDR", "HDR", "GAMEMODE", "MANGOHUD"],
            "custom_pre": "",
            "custom_post": "",
            "command": "PROTON_FSR4_UPGRADE=1 PROTON_ENABLE_WAYLAND=1 PROTON_ENABLE_HDR=1 ENABLE_HDR_WSI=1 ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope -f --hdr-enabled --mangoapp -- gamemoderun %command%",
        },
    }
    for name, payload in builtins.items():
        dune.setdefault(name, payload)


def ensure_game_builtin_presets(config, appid):
    game_presets = config.setdefault("presets", {}).setdefault(appid, {})
    builtins = {
        "Handheld bateria: 800p / 60 FPS": {
            "options": ["HANDHELD800P", "CAP60", "GAMEMODE", "MANGOHUD"],
            "custom_pre": "",
            "custom_post": "",
            "command": "gamescope -f -w 1280 -h 800 --framerate-limit 60 --mangoapp -- gamemoderun %command%",
        },
        "Handheld equilibrado: 800p / 72 FPS": {
            "options": ["HANDHELD800P", "CAP72", "GAMEMODE", "MANGOHUD"],
            "custom_pre": "",
            "custom_post": "",
            "command": "gamescope -f -w 1280 -h 800 --framerate-limit 72 --mangoapp -- gamemoderun %command%",
        },
        "Legion Go 2 nativo: 1200p / 72 FPS": {
            "options": ["HANDHELD1200P", "CAP72", "GAMEMODE", "MANGOHUD"],
            "custom_pre": "",
            "custom_post": "",
            "command": "gamescope -f -w 1920 -h 1200 --framerate-limit 72 --mangoapp -- gamemoderun %command%",
        },
        "Legion Go 2 OLED HDR": {
            "options": ["HDR", "PROTONHDR", "HANDHELD1200P", "ADAPTIVE", "GAMEMODE", "MANGOHUD"],
            "custom_pre": "",
            "custom_post": "",
            "command": "PROTON_ENABLE_HDR=1 ENABLE_HDR_WSI=1 ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope -f -w 1920 -h 1200 --hdr-enabled --mangoapp --adaptive-sync -- gamemoderun %command%",
        },
        "Legion Go 2 FSR4 + Wayland": {
            "options": ["FSR4", "WAYLAND", "HANDHELD800P", "CAP72", "GAMEMODE", "MANGOHUD"],
            "custom_pre": "",
            "custom_post": "",
            "command": "PROTON_ENABLE_WAYLAND=1 PROTON_FSR4_UPGRADE=1 gamescope -f -w 1280 -h 800 --framerate-limit 72 --mangoapp -- gamemoderun %command%",
        },
    }
    for name, payload in builtins.items():
        game_presets.setdefault(name, payload)


def get_shared_presets(config):
    return config.setdefault("shared_presets", {})


def preset_ref(scope, name):
    return f"{scope}:{name}"


def split_preset_ref(ref):
    if not ref:
        return "", ""
    scope, _, name = str(ref).partition(":")
    return (scope or "game"), name


def system_preset_name():
    return "Recomendado del sistema"


def system_preset_payload(system):
    display = display_resolution_or_empty(system.get("display", {}))
    options = sorted(system_recommended_keys(system), key=lambda key: list(OPTION_INFO).index(key) if key in OPTION_INFO else 999)
    command = compose_launch(options, "", "", display)
    return {
        "options": options,
        "custom_pre": "",
        "custom_post": "",
        "gamescope_res": display,
        "command": command,
        "builtin": True,
    }


def ensure_system_shared_preset(config, system):
    config.setdefault("shared_presets", {})[system_preset_name()] = system_preset_payload(system)


def normalize_command(command):
    return " ".join(str(command or "").split())


def slugify_option_label(label):
    slug = re.sub(r"[^a-z0-9]+", "-", str(label or "").lower()).strip("-")
    return slug or "opcion"


def custom_option_key(option):
    return CUSTOM_OPTION_PREFIX + str(option.get("id", ""))


def is_custom_option_key(key):
    return str(key or "").startswith(CUSTOM_OPTION_PREFIX)


def custom_option_tokens(option):
    tokens = []
    for field in ("pre", "gamescope", "post"):
        tokens.extend(shell_words(option.get(field, "")))
    return [token for token in tokens if token != "%command%"]


def custom_option_matches_command(option, command):
    command = str(command or "")
    tokens = custom_option_tokens(option)
    return bool(tokens) and all(token in command for token in tokens)


def normalize_option_category(category):
    category = str(category or "").strip()
    category = LEGACY_OPTION_GROUPS.get(category, category)
    return category if category in OPTION_GROUP_TITLES else OPTION_GROUP_TITLES[-1]


def launch_commands_equivalent(first, second):
    left = normalize_command(first)
    right = normalize_command(second)
    default_forms = {"", "%command%"}
    if left in default_forms and right in default_forms:
        return True
    return left == right


def ensure_display_preset(config, appid, display):
    width = int(display.get("width") or 0)
    height = int(display.get("height") or 0)
    refresh = int(display.get("refresh") or 0)
    if not width or not height:
        return
    refresh_part = f" -r {refresh}" if refresh else ""
    name = f"Monitor nativo Gamescope: {width}x{height}" + (f"@{refresh}" if refresh else "")
    config.setdefault("presets", {}).setdefault(appid, {}).setdefault(
        name,
        {
            "options": ["REALRES", "GAMEMODE", "MANGOHUD"],
            "custom_pre": "",
            "custom_post": "",
            "gamescope_res": {"width": width, "height": height, "refresh": refresh},
            "command": f"gamescope -f --force-windows-fullscreen -W {width} -H {height} -w {width} -h {height}{refresh_part} --mangoapp -- gamemoderun %command%",
        },
    )


def first_existing(paths):
    for path in paths:
        if path.exists():
            return path
    return None


def command_output(args):
    try:
        proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=4)
        return proc.stdout
    except Exception:
        return ""


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text or "")


def clean_gpu_name(line):
    if not line:
        return "GPU no detectada"
    cleaned = re.sub(r"^\S+\s+(?:VGA compatible controller|3D controller|Display controller):\s*", "", line, flags=re.I)
    bracket_names = re.findall(r"\[([^\[\]]*(?:Radeon|GeForce|RTX|GTX|Arc)[^\[\]]*)\]", cleaned, re.I)
    if bracket_names:
        return bracket_names[-1].strip()
    cleaned = re.sub(r"\[[0-9a-fA-F:.]+\]", "", cleaned)
    cleaned = re.sub(r"\(rev\s+[0-9a-fA-F]+\)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned or line.strip()


def detect_gaming_mode():
    env_blob = " ".join(
        os.environ.get(key, "")
        for key in (
            "XDG_CURRENT_DESKTOP",
            "DESKTOP_SESSION",
            "SteamGamepadUI",
            "GAMESCOPE_WAYLAND_DISPLAY",
            "WAYLAND_DISPLAY",
        )
    ).lower()
    if os.environ.get("SteamGamepadUI") or os.environ.get("GAMESCOPE_WAYLAND_DISPLAY"):
        return True
    return "gamescope" in env_blob and ("steam" in env_blob or "gamepad" in env_blob)


def detect_system():
    lspci = command_output(["lspci", "-nnk"])
    os_release = read_os_release()
    product_name = read_text_file("/sys/class/dmi/id/product_name")
    product_version = read_text_file("/sys/class/dmi/id/product_version")
    product_family = read_text_file("/sys/class/dmi/id/product_family")
    gpu = "unknown"
    gpu_name = "GPU no detectada"
    if re.search(r"NVIDIA", lspci, re.I):
        gpu = "nvidia"
        gpu_name = clean_gpu_name(next((line.strip() for line in lspci.splitlines() if re.search(r"VGA|3D|Display", line, re.I)), "NVIDIA"))
    elif re.search(r"AMD/ATI|Radeon|amdgpu", lspci, re.I):
        gpu = "amd"
        gpu_name = clean_gpu_name(next((line.strip() for line in lspci.splitlines() if re.search(r"VGA|3D|Display", line, re.I)), "AMD Radeon"))
    elif re.search(r"Intel", lspci, re.I):
        gpu = "intel"
        gpu_name = clean_gpu_name(next((line.strip() for line in lspci.splitlines() if re.search(r"VGA|3D|Display", line, re.I)), "Intel"))

    session = {
        "type": os_environ("XDG_SESSION_TYPE"),
        "desktop": os_environ("XDG_CURRENT_DESKTOP"),
    }
    tools = {
        "gamescope": bool(shutil.which("gamescope")),
        "gamemoderun": bool(shutil.which("gamemoderun")),
        "mangohud": bool(shutil.which("mangohud")),
        "xdg-open": bool(shutil.which("xdg-open")),
    }
    display = detect_primary_display()
    wsi = bool(list(Path("/usr/share/vulkan").glob("**/*gamescope*wsi*.json")))
    os_id = os_release.get("ID", "").lower()
    os_name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "OS desconocido"
    product_blob = " ".join([product_name, product_version, product_family]).lower()
    is_bazzite = "bazzite" in os_id or "bazzite" in os_name.lower()
    is_steamos = "steamos" in os_id or "steam os" in os_name.lower() or "steamos" in os_name.lower()
    is_legion_go = "legion go" in product_blob or "83e1" in product_blob or "8asp" in product_blob
    gaming_mode = detect_gaming_mode()
    is_handheld = is_bazzite or is_steamos or is_legion_go or session.get("desktop", "").lower() == "gamescope" or gaming_mode
    return {
        "gpu": gpu,
        "gpu_name": gpu_name,
        "session": session,
        "tools": tools,
        "display": display,
        "gamescope_wsi": wsi,
        "os": {"id": os_id, "name": os_name},
        "device": {
            "product_name": product_name,
            "product_version": product_version,
            "product_family": product_family,
            "is_bazzite": is_bazzite,
            "is_steamos": is_steamos,
            "is_legion_go": is_legion_go,
            "is_handheld": is_handheld,
            "gaming_mode": gaming_mode,
        },
    }


def detect_primary_display():
    kscreen = strip_ansi(command_output(["kscreen-doctor", "-o"]))
    mode = re.search(r"Modes:.*?(\d+):(\d+)x(\d+)@([0-9.]+)\*", kscreen, re.S)
    name = re.search(r"Output:\s*\d+\s+(\S+)", kscreen)
    hdr = re.search(r"^\s*HDR:\s*([^\n]+)", kscreen, re.M)
    vrr = re.search(r"^\s*Vrr:\s*([^\n]+)", kscreen, re.M)
    wcg = re.search(r"^\s*Wide Color Gamut:\s*([^\n]+)", kscreen, re.M)
    scale = re.search(r"^\s*Scale:\s*([^\n]+)", kscreen, re.M)
    geometry = re.search(r"^\s*Geometry:\s*([^\n]+)", kscreen, re.M)
    if mode:
        return {
            "name": name.group(1) if name else "",
            "width": int(mode.group(2)),
            "height": int(mode.group(3)),
            "refresh": round(float(mode.group(4))),
            "hdr": (hdr.group(1).strip().lower() if hdr else ""),
            "vrr": (vrr.group(1).strip().lower() if vrr else ""),
            "wide_color": (wcg.group(1).strip().lower() if wcg else ""),
            "scale": scale.group(1).strip() if scale else "",
            "geometry": geometry.group(1).strip() if geometry else "",
        }

    xrandr = command_output(["xrandr", "--current"])
    match = re.search(r"^(\S+)\s+connected\s+primary\s+(\d+)x(\d+)\+\d+\+\d+", xrandr, re.M)
    if not match:
        match = re.search(r"^(\S+)\s+connected\s+(\d+)x(\d+)\+\d+\+\d+", xrandr, re.M)
    if match:
        width = int(match.group(2))
        height = int(match.group(3))
        refresh = None
        mode_line = re.search(rf"^\s*{width}x{height}\s+([0-9.]+)\*", xrandr, re.M)
        if mode_line:
            refresh = round(float(mode_line.group(1)))
        return {
            "name": match.group(1),
            "width": width,
            "height": height,
            "refresh": refresh,
            "hdr": "",
            "vrr": "",
            "wide_color": "",
            "scale": "",
            "geometry": "",
        }
    return {"name": "", "width": 0, "height": 0, "refresh": None, "hdr": "", "vrr": "", "wide_color": "", "scale": "", "geometry": ""}


def display_resolution_or_empty(display):
    return {
        "width": int(display.get("width") or 0),
        "height": int(display.get("height") or 0),
        "refresh": int(display.get("refresh") or 0) or "",
    }


def display_hdr_enabled(display):
    return str((display or {}).get("hdr", "")).lower() in {"enabled", "on", "active", "true", "yes"}


def display_vrr_available(display):
    value = str((display or {}).get("vrr", "")).lower()
    return value not in {"", "disabled", "off", "unsupported", "never", "false", "no"}


def os_environ(key):
    return os.environ.get(key, "")


def read_text_file(path):
    try:
        return Path(path).read_text(errors="replace").strip()
    except OSError:
        return ""


def read_os_release():
    data = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        text = read_text_file(path)
        if not text:
            continue
        for line in text.splitlines():
            if "=" not in line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            data[key] = value.strip().strip('"')
        if data:
            break
    return data


def system_recommended_keys(system):
    keys = set()
    if system["tools"].get("gamemoderun"):
        keys.add("GAMEMODE")
    if system["tools"].get("mangohud"):
        keys.add("MANGOHUD")
    if system["tools"].get("gamescope"):
        keys.add("GAMESCOPE")
        display = system.get("display", {})
        if int(display.get("width") or 0) and int(display.get("height") or 0):
            keys.add("REALRES")
    if system["tools"].get("gamescope") and system.get("gamescope_wsi"):
        keys.add("HDR")
        keys.add("PROTONHDR")
    if system["tools"].get("gamescope") and display_vrr_available(system.get("display", {})):
        keys.add("ADAPTIVE")
        if system["tools"].get("mangohud") and int(system.get("display", {}).get("refresh") or 0):
            keys.add("CAPVRR")
    if system["session"].get("type") == "wayland":
        keys.add("WAYLAND")
    if system.get("device", {}).get("is_handheld"):
        keys.add("HANDHELD800P")
        keys.add("CAP60")
    if system["gpu"] == "amd":
        keys.add("FSR4")
    if system["gpu"] == "nvidia":
        keys.add("NVIDIA")
    return keys


def recommendation_reasons(system):
    reasons = []
    if system["tools"].get("gamemoderun"):
        reasons.append("GameMode disponible: recomendado para rendimiento general.")
    if system["tools"].get("mangohud"):
        reasons.append("MangoHud disponible: util para comprobar FPS, frametime y carga.")
    if system["session"].get("type") == "wayland":
        reasons.append("Sesion Wayland detectada: Proton Wayland puede merecer prueba por juego.")
    if system["tools"].get("gamescope") and system["gamescope_wsi"]:
        reasons.append("Gamescope + WSI detectados: se recomiendan Gamescope, resolucion real y HDR via Gamescope para juegos compatibles.")
    display = system.get("display", {})
    if display_hdr_enabled(display):
        reasons.append("HDR del sistema activo: KDE informa HDR enabled en el monitor seleccionado.")
    elif display.get("hdr"):
        reasons.append(f"HDR del sistema detectado como {display.get('hdr')}: activa HDR en KDE antes de usar presets HDR.")
    if display_vrr_available(display):
        reasons.append(f"VRR disponible: KDE informa Vrr {display.get('vrr')}; Adaptive Sync y VRR cap merecen prueba por juego.")
    elif display.get("vrr"):
        reasons.append(f"VRR detectado como {display.get('vrr')}: Adaptive Sync puede no tener efecto.")
    if system.get("device", {}).get("is_bazzite"):
        reasons.append("Bazzite detectado: presets handheld y Gamescope encajan bien con Gaming Mode.")
    if system.get("device", {}).get("is_steamos"):
        reasons.append("SteamOS detectado: usa perfiles por juego y evita tocar ajustes globales desde la app.")
    if system.get("device", {}).get("is_legion_go"):
        reasons.append("Lenovo Legion Go detectado: 1280x800 ahorra bateria; 1920x1200 usa la pantalla nativa.")
    elif system.get("device", {}).get("is_handheld"):
        reasons.append("Dispositivo handheld detectado: 800p + limite FPS suele mejorar bateria y estabilidad.")
    if system.get("device", {}).get("gaming_mode"):
        reasons.append("Gaming Mode detectado: revisa y lanza desde la app, pero aplica cambios de Steam preferiblemente en Desktop Mode.")
    if system["gpu"] == "amd":
        reasons.append("GPU AMD detectada: FSR4 upgrade puede merecer prueba en juegos compatibles.")
    if system["gpu"] == "nvidia":
        reasons.append("GPU NVIDIA detectada: NVAPI/DLSS puede ser util en juegos compatibles.")
    return reasons


def unescape_vdf(value):
    return value.replace(r"\\", "\\").replace(r"\"", '"')


def escape_vdf(value):
    return value.replace("\\", r"\\").replace('"', r"\"")


def vdf_value(text, key):
    match = re.search(rf'"{re.escape(key)}"\s+"((?:\\.|[^"])*)"', text)
    return unescape_vdf(match.group(1)) if match else ""


def find_named_block(text, key):
    match = re.search(rf'\n(?P<indent>[ \t]*)"{re.escape(key)}"\s*\n[ \t]*{{', text)
    if not match:
        match = re.search(rf'^(?P<indent>[ \t]*)"{re.escape(key)}"\s*\n[ \t]*{{', text)
    if not match:
        return None
    open_pos = text.find("{", match.end() - 1)
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return {
                    "key_start": match.start() + (0 if match.start() == 0 else 1),
                    "block_start": open_pos,
                    "block_end": i + 1,
                    "indent": match.group("indent"),
                }
    return None


def valid_steam_root(path):
    root = Path(path).expanduser() if path else None
    return bool(root and root.exists() and (root / "steamapps").exists())


def steam_root(config=None):
    configured = (config or {}).get("steam_root", "")
    if valid_steam_root(configured):
        return Path(configured).expanduser().resolve()
    root = first_existing(STEAM_ROOTS)
    if not root:
        error("No encuentro la carpeta de Steam.")
        sys.exit(1)
    return root.resolve()


def library_paths(root):
    paths = [root]
    lib_vdf = root / "steamapps/libraryfolders.vdf"
    if lib_vdf.exists():
        text = lib_vdf.read_text(errors="replace")
        for raw in re.findall(r'"path"\s+"((?:\\.|[^"])*)"', text):
            p = Path(unescape_vdf(raw))
            if p.exists() and p not in paths:
                paths.append(p)
    return paths


def installed_games(root):
    games = []
    seen = set()
    for lib in library_paths(root):
        for manifest in sorted((lib / "steamapps").glob("appmanifest_*.acf")):
            text = manifest.read_text(errors="replace")
            appid = vdf_value(text, "appid") or manifest.stem.removeprefix("appmanifest_")
            name = vdf_value(text, "name") or f"App {appid}"
            installdir = vdf_value(text, "installdir")
            if appid in seen or appid == "228980":
                continue
            if any(name.startswith(prefix) for prefix in HIDDEN_APP_NAMES):
                continue
            seen.add(appid)
            games.append(
                {
                    "appid": appid,
                    "name": name,
                    "installdir": installdir,
                    "library": lib,
                    "manifest": manifest,
                    "manual": False,
                }
            )
    return sorted(games, key=lambda g: g["name"].casefold())


def merged_games(root, config):
    games = installed_games(root)
    seen = {game["appid"] for game in games}
    for manual in config.get("manual_games", []):
        appid = str(manual.get("appid", "")).strip()
        name = str(manual.get("name", "")).strip()
        if not appid or not name or appid in seen:
            continue
        seen.add(appid)
        games.append(
            {
                "appid": appid,
                "name": name,
                "installdir": "",
                "library": root,
                "manifest": None,
                "manual": True,
                "external": False,
            }
        )
    for external in config.get("external_games", []):
        game_id = str(external.get("id", "")).strip()
        name = str(external.get("name", "")).strip()
        exe = str(external.get("exe", "")).strip()
        if not game_id or not name or not exe or game_id in seen:
            continue
        seen.add(game_id)
        games.append(
            {
                "appid": game_id,
                "name": name,
                "installdir": str(Path(exe).parent),
                "library": root,
                "manifest": None,
                "manual": True,
                "external": True,
                "exe": exe,
                "proton": external.get("proton", ""),
                "prefix": external.get("prefix", ""),
                "steam_shortcut": bool(external.get("steam_shortcut")),
                "steam_shortcut_appid": external.get("steam_shortcut_appid", ""),
            }
        )
    return sorted(games, key=lambda g: g["name"].casefold())


def find_game_icon(root, appid):
    cache = root / "appcache" / "librarycache"
    candidates = [
        cache / f"{appid}_icon.jpg",
        cache / f"{appid}_icon.png",
        cache / appid / "icon.jpg",
        cache / appid / "icon.png",
        cache / f"{appid}_library_600x900.jpg",
        cache / f"{appid}_header.jpg",
    ]
    icon = first_existing(candidates)
    if icon:
        return icon
    app_cache = cache / appid
    if app_cache.exists():
        images = sorted(
            [p for p in app_cache.glob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}],
            key=lambda p: p.stat().st_size,
        )
        if images:
            return images[0]
    return None


def external_icon_cache_path(exe):
    digest = hashlib.sha1(str(exe).encode("utf-8", "replace")).hexdigest()[:16]
    return APP_CACHE_DIR / "icons" / f"{digest}.png"


def find_external_icon(exe):
    exe_path = Path(exe)
    cached = external_icon_cache_path(exe_path)
    if cached.exists():
        return cached
    wrestool = shutil.which("wrestool")
    icotool = shutil.which("icotool")
    if not exe_path.exists() or not wrestool or not icotool:
        return None
    icon_dir = cached.parent / (cached.stem + ".extract")
    ico_path = icon_dir / "resources.ico"
    try:
        icon_dir.mkdir(parents=True, exist_ok=True)
        with ico_path.open("wb") as handle:
            proc = subprocess.run(
                [wrestool, "-x", "-t", "14", str(exe_path)],
                stdout=handle,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
        if proc.returncode != 0 or not ico_path.exists() or ico_path.stat().st_size == 0:
            return None
        subprocess.run([icotool, "-x", "-o", str(icon_dir), str(ico_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        images = sorted(
            [p for p in icon_dir.iterdir() if p.suffix.lower() in {".png", ".ico", ".bmp"} and p.name != ico_path.name],
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if not images:
            return None
        cached.parent.mkdir(parents=True, exist_ok=True)
        source = images[0]
        if source.suffix.lower() == ".png":
            shutil.copy2(source, cached)
        elif shutil.which("magick"):
            subprocess.run(["magick", str(source), str(cached)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        elif shutil.which("convert"):
            subprocess.run(["convert", str(source), str(cached)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        return cached if cached.exists() else None
    except Exception:
        return None


def game_icon(root, game):
    if game.get("external"):
        return find_external_icon(game.get("exe", ""))
    return find_game_icon(root, game["appid"])


def external_game_id(name, exe):
    digest = hashlib.sha1(f"{name}\0{exe}".encode("utf-8", "replace")).hexdigest()[:12]
    return f"external-{digest}"


def compatibility_tool_metadata(path):
    compat = path / "compatibilitytool.vdf"
    manifest = path / "toolmanifest.vdf"
    internal = ""
    display = ""
    if compat.exists():
        text = compat.read_text(errors="replace")
        match = re.search(r'"compat_tools"\s*\{[\s\S]*?\n[ \t]*"([^"]+)"\s*(?://[^\n]*)?\n[ \t]*\{', text)
        if match:
            internal = match.group(1)
        display = vdf_value(text, "display_name")
    if not internal:
        if path.name == "Proton - Experimental":
            internal = "proton_experimental"
        elif path.name == "Proton Hotfix":
            internal = "proton_hotfix"
        else:
            internal = path.name
    if not display:
        display = path.name
    version = ""
    version_file = path / "version"
    if version_file.exists():
        version = " ".join(version_file.read_text(errors="replace").split())
    layer = ""
    if manifest.exists():
        layer = vdf_value(manifest.read_text(errors="replace"), "compatmanager_layer_name")
    return {"name": display, "compat": internal, "path": str(path / "proton"), "version": version, "layer": layer}


def proton_tools(root):
    tools = []
    seen_paths = set()
    seen_compat = set()
    candidates = [root / "steamapps/common/Proton - Experimental", root / "steamapps/common/Proton Hotfix"]
    for base in PROTON_TOOL_DIRS:
        if base.exists():
            candidates.extend(sorted(p for p in base.iterdir() if p.is_dir()))
    for path in candidates:
        proton = path / "proton"
        real = proton.resolve() if proton.exists() else proton
        if not proton.exists() or real in seen_paths:
            continue
        tool = compatibility_tool_metadata(path)
        if tool["compat"] in seen_compat:
            continue
        seen_paths.add(real)
        seen_compat.add(tool["compat"])
        tools.append(tool)
    return sorted(tools, key=lambda item: proton_sort_key(item["name"], item.get("version", "")), reverse=True)


def proton_sort_key(name, version=""):
    text = f"{name} {version}".lower()
    score = 0
    if "ge-proton" in text:
        score += 3000
    if "cachy" in text:
        score += 2500
    if "experimental" in text:
        score += 2000
    if "hotfix" in text:
        score += 1500
    nums = [int(part) for part in re.findall(r"\d+", text)[:4]]
    while len(nums) < 4:
        nums.append(0)
    return (score, *nums)


def recommended_proton_tool(system, tools):
    if not tools:
        return ""
    wants_new = system.get("gpu") == "amd" or system.get("session", {}).get("type") == "wayland" or display_hdr_enabled(system.get("display", {}))
    os_text = f"{system.get('os', {}).get('id', '')} {system.get('os', {}).get('name', '')}".lower()
    if "cachy" in os_text:
        for tool in tools:
            if "cachy" in f"{tool['name']} {tool.get('compat', '')}".lower():
                return tool["compat"]
    if wants_new:
        for needle in ("GE-Proton", "cachy", "Experimental"):
            for tool in tools:
                if needle.lower() in f"{tool['name']} {tool.get('compat', '')}".lower():
                    return tool["compat"]
    return tools[0]["compat"]


def shell_join(parts):
    return " ".join(shlex.quote(str(part)) for part in parts)


def shell_words(text):
    text = str(text or "").strip()
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def localconfig_path(root):
    configs = sorted((root / "userdata").glob("*/config/localconfig.vdf"))
    if not configs:
        error("No encuentro userdata/*/config/localconfig.vdf.")
        sys.exit(1)
    if len(configs) == 1:
        return configs[0]

    rows = []
    for cfg in configs:
        rows.extend(["FALSE", cfg.parts[-3], str(cfg)])
    choice = z(
        [
            "--list",
            "--radiolist",
            "--title=Selecciona cuenta Steam",
            "--column=",
            "--column=Cuenta",
            "--column=Archivo",
            "--width=900",
            "--height=320",
            *rows,
        ]
    )
    for cfg in configs:
        if str(cfg) == choice or cfg.parts[-3] == choice:
            return cfg
    sys.exit(1)


def steam_config_path(root):
    path = root / "config/config.vdf"
    if not path.exists():
        error("No encuentro config/config.vdf de Steam.")
        sys.exit(1)
    return path


def current_compat_tool(config_text, appid):
    mapping = find_named_block(config_text, "CompatToolMapping")
    if not mapping:
        return ""
    body = config_text[mapping["block_start"] : mapping["block_end"]]
    app_block = find_app_block(body, appid)
    if not app_block:
        return ""
    app_body = body[app_block["block_start"] : app_block["block_end"]]
    return vdf_value(app_body, "name")


def compat_tool_display_name(tool_name, tools):
    if not tool_name:
        return "Steam por defecto"
    for tool in tools:
        if tool.get("compat") == tool_name:
            version = f" ({tool['version']})" if tool.get("version") else ""
            return f"{tool['name']}{version}"
    return tool_name


def compact_proton_label(label):
    label = re.sub(r"^\d+\s+", "", str(label or "")).strip()
    label = label.replace(" (steam linux runtime)", " SLR")
    return label


def compat_tool_block(appid, tool_name, indent):
    child = indent + "\t"
    escaped = escape_vdf(tool_name)
    return (
        f'{indent}"{appid}"\n'
        f"{indent}{{\n"
        f'{child}"name"\t\t"{escaped}"\n'
        f'{child}"config"\t\t""\n'
        f'{child}"priority"\t\t"250"\n'
        f"{indent}}}\n"
    )


def set_compat_tool(config_path, appid, tool_name):
    text = config_path.read_text(errors="replace")
    mapping = find_named_block(text, "CompatToolMapping")
    if not mapping and not tool_name:
        return None
    if not mapping:
        steam_block = find_named_block(text, "Steam")
        if not steam_block:
            raise RuntimeError('No encuentro el bloque "Steam" en config.vdf.')
        insert_at = text.find("\n", steam_block["block_start"]) + 1
        indent = steam_block["indent"] + "\t"
        app_indent = indent + "\t"
        new_mapping = (
            f'{indent}"CompatToolMapping"\n'
            f"{indent}{{\n"
            f"{compat_tool_block(appid, tool_name, app_indent)}"
            f"{indent}}}\n"
        )
        new_text = text[:insert_at] + new_mapping + text[insert_at:]
    else:
        body = text[mapping["block_start"] : mapping["block_end"]]
        app_block = find_app_block(body, appid)
        app_indent = mapping["indent"] + "\t"
        if app_block:
            start = mapping["block_start"] + app_block["key_start"]
            end = mapping["block_start"] + app_block["block_end"]
            if tool_name:
                replacement = compat_tool_block(appid, tool_name, app_indent)
                new_text = text[:start] + replacement.rstrip("\n") + text[end:]
            else:
                new_text = text[:start] + text[end:]
        elif tool_name:
            insert_at = text.find("\n", mapping["block_start"]) + 1
            replacement = compat_tool_block(appid, tool_name, app_indent)
            new_text = text[:insert_at] + replacement + text[insert_at:]
        else:
            new_text = text
    backup = config_path.with_suffix(config_path.suffix + "." + _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".bak")
    shutil.copy2(config_path, backup)
    config_path.write_text(new_text)
    return backup


def shortcuts_path(root):
    return localconfig_path(root).with_name("shortcuts.vdf")


def signed_32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def steam_shortcut_appid(name, exe):
    raw = zlib.crc32(f"{exe}{name}".encode("utf-8", "replace")) | 0x80000000
    return signed_32(raw)


def load_shortcuts(path):
    try:
        import vdf
        if path.exists() and path.stat().st_size:
            with path.open("rb") as handle:
                data = vdf.binary_load(handle)
        else:
            data = {"shortcuts": {}}
    except Exception:
        data = {"shortcuts": {}}
    shortcuts = data.setdefault("shortcuts", {})
    if not isinstance(shortcuts, dict):
        data["shortcuts"] = {}
    return data


def dump_shortcuts(path, data):
    import vdf
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = path.with_suffix(path.suffix + "." + _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".bak")
        shutil.copy2(path, backup)
    with path.open("wb") as handle:
        vdf.binary_dump(data, handle)
    return backup


def shortcut_entry(name, exe, launch_options=""):
    exe_path = Path(exe)
    start_dir = str(exe_path.parent) + "/"
    return {
        "appid": steam_shortcut_appid(name, str(exe_path)),
        "AppName": name,
        "Exe": f'"{exe_path}"',
        "StartDir": start_dir,
        "icon": "",
        "ShortcutPath": "",
        "LaunchOptions": launch_options,
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": "",
        "DevkitOverrideAppID": 0,
        "LastPlayTime": 0,
        "FlatpakAppID": "",
        "sortas": "",
        "tags": {"0": APP_NAME},
    }


def find_shortcut(data, name, exe):
    target_exe = f'"{Path(exe)}"'
    shortcuts = data.setdefault("shortcuts", {})
    for key, entry in shortcuts.items():
        if str(entry.get("AppName", "")) == name and str(entry.get("Exe", "")) == target_exe:
            return key, entry
    return None, None


def add_steam_shortcut(root, name, exe, launch_options=""):
    path = shortcuts_path(root)
    data = load_shortcuts(path)
    shortcuts = data.setdefault("shortcuts", {})
    key, entry = find_shortcut(data, name, exe)
    if entry is None:
        existing_ids = [int(k) for k in shortcuts if str(k).isdigit()]
        key = str(max(existing_ids, default=-1) + 1)
        entry = shortcut_entry(name, exe, launch_options)
        shortcuts[key] = entry
    else:
        entry["LaunchOptions"] = launch_options
    backup = dump_shortcuts(path, data)
    return {"path": path, "backup": backup, "appid": entry.get("appid"), "key": key}


def update_steam_shortcut_launch_options(root, name, exe, launch_options):
    path = shortcuts_path(root)
    data = load_shortcuts(path)
    _, entry = find_shortcut(data, name, exe)
    if entry is None:
        return None
    entry["LaunchOptions"] = launch_options
    backup = dump_shortcuts(path, data)
    return {"path": path, "backup": backup, "appid": entry.get("appid")}


def find_app_block(text, appid):
    match = re.search(rf'\n(?P<indent>[ \t]*)"{re.escape(appid)}"\s*\n[ \t]*{{', text)
    if not match:
        return None
    open_pos = text.find("{", match.end() - 1)
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return {
                    "key_start": match.start() + 1,
                    "block_start": open_pos,
                    "block_end": i + 1,
                    "indent": match.group("indent"),
                }
    return None


def current_launch_options(config_text, appid):
    block = find_app_block(config_text, appid)
    if not block:
        return ""
    return vdf_value(config_text[block["block_start"] : block["block_end"]], "LaunchOptions")


def set_launch_options(config_path, appid, launch_options):
    text = config_path.read_text(errors="replace")
    block = find_app_block(text, appid)
    escaped = escape_vdf(launch_options)

    if block:
        body = text[block["block_start"] : block["block_end"]]
        line_match = re.search(r'\n(?P<indent>[ \t]*)"LaunchOptions"\s+"(?:\\.|[^"]*)"', body)
        if line_match:
            start = block["block_start"] + line_match.start()
            end = block["block_start"] + line_match.end()
            if launch_options:
                new_line = f'\n{line_match.group("indent")}"LaunchOptions"\t\t"{escaped}"'
                new_text = text[:start] + new_line + text[end:]
            else:
                new_text = text[:start] + text[end:]
        else:
            insert_at = text.find("\n", block["block_start"]) + 1
            indent = block["indent"] + "\t"
            new_line = f'{indent}"LaunchOptions"\t\t"{escaped}"\n' if launch_options else ""
            new_text = text[:insert_at] + new_line + text[insert_at:]
    else:
        apps = re.search(r'\n(?P<indent>[ \t]*)"apps"\s*\n[ \t]*{', text)
        if not apps:
            raise RuntimeError('No encuentro el bloque "apps" en localconfig.vdf.')
        insert_at = text.find("\n", text.find("{", apps.end() - 1)) + 1
        indent = apps.group("indent") + "\t"
        opt_line = f'{indent}\t"LaunchOptions"\t\t"{escaped}"\n' if launch_options else ""
        new_block = f'{indent}"{appid}"\n{indent}{{\n{opt_line}{indent}}}\n'
        new_text = text[:insert_at] + new_block + text[insert_at:]

    backup = config_path.with_suffix(config_path.suffix + "." + _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".bak")
    shutil.copy2(config_path, backup)
    config_path.write_text(new_text)
    return backup


def detect_flags(current):
    framerate_limit = detect_framerate_limit(current)
    mangohud_fps_limit = detect_mangohud_fps_limit(current)
    mangohud_hidden = detect_mangohud_no_display(current)
    return {
        "HDR": "--hdr-enabled" in current or "DXVK_HDR=1" in current,
        "WAYLAND": "PROTON_ENABLE_WAYLAND=1" in current,
        "PROTONHDR": "PROTON_ENABLE_HDR=1" in current,
        "FSR4": "PROTON_FSR4_UPGRADE=1" in current,
        "FSR4IND": "PROTON_FSR4_INDICATOR=1" in current,
        "RT": "VKD3D_CONFIG=dxr" in current,
        "NVIDIA": "PROTON_ENABLE_NVAPI=1" in current or "PROTON_HIDE_NVIDIA_GPU=0" in current,
        "DX12": "-dx12" in current,
        "GAMEMODE": "gamemoderun" in current,
        "MANGOHUD": "--mangoapp" in current or ("mangohud" in current and not mangohud_hidden),
        "GAMESCOPE": "gamescope" in current,
        "REALRES": "-W " in current and "-H " in current and "-w " in current and "-h " in current,
        "HANDHELD800P": "-w 1280" in current and "-h 800" in current,
        "HANDHELD1200P": "-w 1920" in current and "-h 1200" in current,
        "CAP60": "--framerate-limit 60" in current,
        "CAP72": "--framerate-limit 72" in current,
        "CAPVRR": bool(mangohud_fps_limit or (framerate_limit and framerate_limit not in {60, 72})),
        "GSFSR": "-F fsr" in current,
        "GSNIS": "-F nis" in current,
        "ADAPTIVE": "--adaptive-sync" in current,
        "UEHDR": False,
        "NODXR": "VKD3D_CONFIG=nodxr" in current,
        "PROTONDB": False,
        "RECOMMEND": False,
        "CUSTOM": False,
    }


def detect_gamescope_resolution(current):
    values = {}
    for key, flag in (("width", "-w"), ("height", "-h"), ("refresh", "-r")):
        match = re.search(rf"(?:^|\s){re.escape(flag)}\s+(\d+)(?:\s|$)", current)
        if match:
            values[key] = int(match.group(1))
    return values


def detect_framerate_limit(current):
    match = re.search(r"(?:^|\s)--framerate-limit\s+(\d+)(?:\s|$)", current)
    return int(match.group(1)) if match else 0


def detect_mangohud_fps_limit(current):
    match = re.search(r"(?:^|\s)MANGOHUD_CONFIG=(?:\"[^\"]*|'[^']*|\S*)fps_limit=(\d+)", current)
    return int(match.group(1)) if match else 0


def detect_mangohud_no_display(current):
    return bool(re.search(r"(?:^|\s)MANGOHUD_CONFIG=(?:\"[^\"]*|'[^']*|\S*)no_display", current))


def vrr_cap_from_refresh(refresh, margin=3):
    try:
        refresh = int(refresh or 0)
    except (TypeError, ValueError):
        return 0
    return max(30, refresh - margin) if refresh else 0


def compose_launch(selected, custom_pre="", custom_post="", gamescope_res=None, custom_options=None):
    selected = set(selected)
    custom_defs = {custom_option_key(option): option for option in (custom_options or [])}
    selected_custom = [custom_defs[key] for key in selected if key in custom_defs]
    gamescope_options = {"HDR", "GAMESCOPE", "REALRES", "ADAPTIVE", "HANDHELD800P", "HANDHELD1200P", "CAP60", "CAP72", "CAPVRR", "GSFSR", "GSNIS"}
    use_gamescope = bool(gamescope_options & selected) or any(shell_words(option.get("gamescope", "")) for option in selected_custom)
    parts = []
    post_args = []
    if custom_pre.strip():
        parts.extend(shell_words(custom_pre))
    for option in selected_custom:
        parts.extend(shell_words(option.get("pre", "")))

    if "WAYLAND" in selected:
        parts.append("PROTON_ENABLE_WAYLAND=1")
    if "PROTONHDR" in selected:
        parts.append("PROTON_ENABLE_HDR=1")
    if "FSR4" in selected:
        parts.append("PROTON_FSR4_UPGRADE=1")
    if "FSR4IND" in selected:
        parts.append("PROTON_FSR4_INDICATOR=1")
    if "HDR" in selected:
        parts.extend(["ENABLE_HDR_WSI=1", "ENABLE_GAMESCOPE_WSI=1", "DXVK_HDR=1"])
    if "NODXR" in selected:
        parts.append("VKD3D_CONFIG=nodxr")
    elif "RT" in selected:
        parts.append("VKD3D_CONFIG=dxr")
    if "NVIDIA" in selected:
        parts.extend(["PROTON_ENABLE_NVAPI=1", "PROTON_HIDE_NVIDIA_GPU=0", "PROTON_ENABLE_NGX_UPDATER=1"])
    if "DX12" in selected:
        post_args.append("-dx12")
    for option in selected_custom:
        post_args.extend(shell_words(option.get("post", "")))

    vrr_cap = vrr_cap_from_refresh((gamescope_res or {}).get("refresh")) if "CAPVRR" in selected else 0
    if vrr_cap:
        mango_config = f"fps_limit={vrr_cap}" if "MANGOHUD" in selected else f"fps_limit={vrr_cap},no_display"
        parts.append(f"MANGOHUD_CONFIG={mango_config}")

    if use_gamescope:
        flags = ["-f"]
        if "REALRES" in selected and gamescope_res:
            width = str(gamescope_res.get("width") or "").strip()
            height = str(gamescope_res.get("height") or "").strip()
            refresh = str(gamescope_res.get("refresh") or "").strip()
            if width and height:
                flags.extend(["--force-windows-fullscreen", "-W", width, "-H", height, "-w", width, "-h", height])
            if refresh:
                flags.extend(["-r", refresh])
        elif "HANDHELD1200P" in selected:
            flags.extend(["-w", "1920", "-h", "1200"])
        elif "HANDHELD800P" in selected:
            flags.extend(["-w", "1280", "-h", "800"])
        if "CAP72" in selected:
            flags.extend(["--framerate-limit", "72"])
        elif "CAP60" in selected:
            flags.extend(["--framerate-limit", "60"])
        if "GSFSR" in selected:
            flags.extend(["-F", "fsr", "--sharpness", "5"])
        elif "GSNIS" in selected:
            flags.extend(["-F", "nis", "--sharpness", "5"])
        for option in selected_custom:
            flags.extend(shell_words(option.get("gamescope", "")))
        if "HDR" in selected:
            flags.append("--hdr-enabled")
        if "MANGOHUD" in selected and not vrr_cap:
            flags.append("--mangoapp")
        if "ADAPTIVE" in selected:
            flags.append("--adaptive-sync")
        parts.extend(["gamescope", *flags, "--"])
    if vrr_cap:
        parts.append("mangohud")
    elif not use_gamescope and "MANGOHUD" in selected:
        parts.append("mangohud")

    if "GAMEMODE" in selected:
        parts.append("gamemoderun")
    parts.append("%command%")
    parts.extend(post_args)
    if custom_post.strip():
        parts.extend(shell_words(custom_post))
    return " ".join(parts)


def steam_is_running():
    proc = subprocess.run(
        ["pgrep", "-u", str(HOME.name), "-x", "steam"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def wait_for_steam_state(running, timeout=20):
    end = _dt.datetime.now() + _dt.timedelta(seconds=timeout)
    while _dt.datetime.now() < end:
        if steam_is_running() == running:
            return True
        subprocess.run(["sleep", "0.5"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return steam_is_running() == running


def close_steam(timeout=25):
    if not steam_is_running():
        return True
    steam_cmd = shutil.which("steam")
    if steam_cmd:
        subprocess.Popen([steam_cmd, "-shutdown"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["pkill", "-TERM", "-u", str(HOME.name), "-x", "steam"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if wait_for_steam_state(False, timeout):
        return True
    subprocess.run(["pkill", "-TERM", "-u", str(HOME.name), "-x", "steam"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return wait_for_steam_state(False, 8)


def open_steam(root=None):
    candidates = [shutil.which("steam")]
    if root:
        candidates.extend([str(Path(root) / "steam.sh"), str(Path(root) / "ubuntu12_32/steam")])
    for cmd in candidates:
        if cmd and Path(cmd).exists():
            subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return wait_for_steam_state(True, 20)
    return False


def open_url(url):
    if shutil.which("xdg-open"):
        subprocess.Popen([shutil.which("xdg-open"), url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def short_command(command, limit=180):
    command = normalize_command(command)
    if not command:
        return "(sin opciones)"
    if len(command) <= limit:
        return command
    return command[: limit - 1].rstrip() + "..."


def running_appimage_path():
    appimage = os.environ.get("APPIMAGE", "")
    if appimage and Path(appimage).exists():
        return Path(appimage)
    candidates = [
        APP_DIR / "dist" / f"Proton-Pilot-{APP_VERSION}-x86_64.AppImage",
        APP_DIR / f"Proton-Pilot-{APP_VERSION}-x86_64.AppImage",
    ]
    return first_existing(candidates)


def latest_release_info():
    url = f"https://api.github.com/repos/{APP_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                raise urllib.error.URLError(f"HTTP {response.status}")
            data = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {
                "tag": "",
                "url": f"https://github.com/{APP_REPO}/releases",
                "asset_url": "",
                "asset_name": "",
                "missing": True,
            }
        raise
    asset_url = ""
    asset_name = ""
    for asset in data.get("assets", []) or []:
        name = asset.get("name", "")
        if name.endswith(".AppImage"):
            asset_name = name
            asset_url = asset.get("browser_download_url", "")
            break
    return {
        "tag": str(data.get("tag_name", "")).lstrip("v"),
        "url": data.get("html_url", f"https://github.com/{APP_REPO}/releases"),
        "asset_url": asset_url,
        "asset_name": asset_name,
    }


def version_tuple(version):
    return tuple(int(part) for part in re.findall(r"\d+", str(version or ""))[:4])


def is_newer_version(candidate, current):
    return version_tuple(candidate) > version_tuple(current)


def protondb_reports(appid, config):
    base = config.get("protondb_api") or DEFAULT_APP_CONFIG["protondb_api"]
    url = base.rstrip("/") + f"/games/{appid}/reports/"
    req = urllib.request.Request(url, headers={"User-Agent": "steam-game-options/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status != 200:
                return []
            data = json.loads(response.read().decode("utf-8", "replace"))
            return data if isinstance(data, list) else []
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []


def protondb_summary(appid):
    url = f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status != 200:
                return {}
            data = json.loads(response.read().decode("utf-8", "replace"))
            return data if isinstance(data, dict) else {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def protondb_cached_summary(config, appid, refresh=False):
    cache = config.setdefault("protondb_cache", {})
    item = cache.get(str(appid), {})
    now = int(_dt.datetime.now().timestamp())
    max_age = 14 * 24 * 60 * 60
    if item and not refresh and now - int(item.get("timestamp") or 0) < max_age:
        summary = item.get("summary", {})
        return summary if isinstance(summary, dict) else {}
    summary = protondb_summary(appid)
    if summary:
        cache[str(appid)] = {"timestamp": now, "summary": summary}
    return summary


def protondb_cache_age_label(config, appid):
    item = config.get("protondb_cache", {}).get(str(appid), {})
    timestamp = int(item.get("timestamp") or 0)
    if not timestamp:
        return ""
    age = max(0, int(_dt.datetime.now().timestamp()) - timestamp)
    if age < 3600:
        return "cache hace menos de 1 h"
    if age < 48 * 3600:
        return f"cache hace {age // 3600} h"
    return f"cache hace {age // 86400} dias"


def protondb_tier(summary):
    return str((summary or {}).get("tier") or (summary or {}).get("bestReportedTier") or "").strip().lower()


def protondb_tier_label(summary):
    tier = protondb_tier(summary)
    return tier.upper() if tier else ""


def protondb_tier_color(tier):
    colors = {
        "platinum": ("#e5e4e2", "#263238"),
        "gold": ("#ffd54f", "#4e3500"),
        "silver": ("#cfd8dc", "#263238"),
        "bronze": ("#d6a46f", "#4a2a0a"),
        "borked": ("#ffcdd2", "#7f130f"),
        "pending": ("#eeeeee", "#5f6368"),
    }
    return colors.get(str(tier).lower(), ("#ffffff", "#263238"))


def protondb_summary_lines(summary):
    if not summary:
        return []
    lines = []
    total = summary.get("total")
    tier = summary.get("tier")
    best = summary.get("bestReportedTier")
    trending = summary.get("trendingTier")
    confidence = summary.get("confidence")
    score = summary.get("score")
    if tier or best or trending:
        parts = []
        if tier:
            parts.append(f"rating actual: {tier}")
        if best:
            parts.append(f"mejor reportado: {best}")
        if trending:
            parts.append(f"tendencia: {trending}")
        lines.append("Resumen oficial ProtonDB: " + ", ".join(parts))
    if total is not None or confidence or score is not None:
        parts = []
        if total is not None:
            parts.append(f"{total} reportes")
        if confidence:
            parts.append(f"confianza {confidence}")
        if score is not None:
            parts.append(f"score {score}")
        lines.append("Datos: " + ", ".join(parts))
    return lines


def extract_launch_hints(text):
    hints = []
    if not text:
        return hints
    patterns = [
        r"(?:[A-Z0-9_]+=[^\s`]+(?:\s+|$)){1,8}%command%(?:\s+[-][^\n`]+)?",
        r"%command%(?:\s+[-][A-Za-z0-9_=./:+-]+){1,8}",
        r"(?:gamemoderun|mangohud|gamescope|VKD3D_CONFIG=\S+|PROTON_ENABLE_NVAPI=\S+|DXVK_HDR=\S+)[^\n`]{0,160}%command%",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text):
            hint = " ".join(match.strip().split())
            if hint and hint not in hints:
                hints.append(hint)
    return hints[:6]


def protondb_recommendations(game, config):
    reports = protondb_reports(game["appid"], config)
    summary = protondb_cached_summary(config, game["appid"])
    if not reports:
        lines = [f"ProtonDB: {game['name']} ({game['appid']})", ""]
        lines.extend(protondb_summary_lines(summary))
        if summary:
            lines.extend(
                [
                    "",
                    "No he podido extraer launch options concretas desde la API comunitaria antigua.",
                    "Abre ProtonDB para leer los reportes detallados y copia aqui cualquier launch option que recomienden.",
                ]
            )
        else:
            lines.append("No he encontrado datos automaticos para este juego.")
        lines.extend(["", f"Pagina: https://www.protondb.com/app/{game['appid']}"])
        return "\n".join(lines)

    ratings = {}
    proton_versions = {}
    launch_hints = []
    notes_bits = []
    for report in reports[:20]:
        rating = str(report.get("rating") or report.get("tier") or "").lower()
        if rating:
            ratings[rating] = ratings.get(rating, 0) + 1
        proton = str(report.get("protonVersion") or report.get("proton_version") or "").strip()
        if proton:
            proton_versions[proton] = proton_versions.get(proton, 0) + 1
        notes = str(report.get("notes") or report.get("description") or "")
        for hint in extract_launch_hints(notes):
            if hint not in launch_hints:
                launch_hints.append(hint)
        if notes and len(notes_bits) < 3:
            notes_bits.append(" ".join(notes.split())[:280])

    lines = [f"ProtonDB comunitario: {game['name']} ({game['appid']})", ""]
    if ratings:
        lines.append("Ratings recientes: " + ", ".join(f"{k}: {v}" for k, v in sorted(ratings.items(), key=lambda kv: -kv[1])))
    if proton_versions:
        lines.append("Proton mencionado: " + ", ".join(k for k, _ in sorted(proton_versions.items(), key=lambda kv: -kv[1])[:5]))
    if launch_hints:
        lines.append("")
        lines.append("Launch options detectadas en reportes:")
        lines.extend(f"- {hint}" for hint in launch_hints[:6])
    if notes_bits:
        lines.append("")
        lines.append("Notas recientes:")
        lines.extend(f"- {note}" for note in notes_bits)
    lines.append("")
    lines.append(f"Pagina: https://www.protondb.com/app/{game['appid']}")
    return "\n".join(lines)


def protondb_recommendation_data(game, config):
    reports = protondb_reports(game["appid"], config)
    summary = protondb_cached_summary(config, game["appid"])
    data = {"text": "", "launch_hints": [], "reports": len(reports), "summary": summary}
    if not reports:
        lines = [f"ProtonDB: {game['name']} ({game['appid']})", "", "Resumen oficial"]
        lines.extend(protondb_summary_lines(summary))
        cache_age = protondb_cache_age_label(config, game["appid"])
        if cache_age:
            lines.append(f"Fuente: {cache_age}")
        if summary:
            lines.extend(
                [
                    "",
                    "Launch options comunitarias",
                    "He encontrado el resumen oficial, pero no launch options extraibles automaticamente.",
                    "La web de ProtonDB carga los reportes detallados por JavaScript; abre la pagina para leerlos.",
                    "Si ves una launch option util, pegala en Ajustes personalizados o en Comando final.",
                ]
            )
        else:
            lines.append("No he encontrado datos automaticos. Revisa la pagina manualmente.")
        lines.extend(["", f"Pagina: https://www.protondb.com/app/{game['appid']}"])
        data["text"] = "\n".join(lines)
        return data

    ratings = {}
    proton_versions = {}
    notes_bits = []
    for report in reports[:25]:
        rating = str(report.get("rating") or report.get("tier") or "").lower()
        if rating:
            ratings[rating] = ratings.get(rating, 0) + 1
        proton = str(report.get("protonVersion") or report.get("proton_version") or "").strip()
        if proton:
            proton_versions[proton] = proton_versions.get(proton, 0) + 1
        notes = str(report.get("notes") or report.get("description") or "")
        for hint in extract_launch_hints(notes):
            if hint not in data["launch_hints"]:
                data["launch_hints"].append(hint)
        if notes and len(notes_bits) < 4:
            notes_bits.append(" ".join(notes.split())[:420])

    lines = [f"ProtonDB: {game['name']} ({game['appid']})", "", "Resumen oficial"]
    lines.extend(protondb_summary_lines(summary))
    cache_age = protondb_cache_age_label(config, game["appid"])
    if cache_age:
        lines.append(f"Fuente: {cache_age}")
    if summary:
        lines.append("")
    if ratings:
        lines.append("Reportes comunitarios")
        lines.append("Ratings recientes: " + ", ".join(f"{k}: {v}" for k, v in sorted(ratings.items(), key=lambda kv: -kv[1])))
    if proton_versions:
        lines.append("Proton mencionado: " + ", ".join(k for k, _ in sorted(proton_versions.items(), key=lambda kv: -kv[1])[:5]))
    if data["launch_hints"]:
        lines.append("")
        lines.append("Launch options detectadas")
        lines.extend(f"- {hint}" for hint in data["launch_hints"][:8])
    if notes_bits:
        lines.append("")
        lines.append("Notas recientes:")
        lines.extend(f"- {note}" for note in notes_bits)
    lines.append("")
    lines.append(f"Pagina: https://www.protondb.com/app/{game['appid']}")
    data["text"] = "\n".join(lines)
    return data


def choose_game(games, config_text):
    rows = []
    for idx, game in enumerate(games):
        current = current_launch_options(config_text, game["appid"])
        rows.extend(["TRUE" if idx == 0 else "FALSE", game["appid"], game["name"], current])
    choice = z(
        [
            "--list",
            "--radiolist",
            "--title=Steam Game Options",
            "--text=Paso 1/3: selecciona un juego y pulsa Aceptar.\nLas opciones salen en la siguiente pantalla.",
            "--column=",
            "--column=AppID",
            "--column=Juego",
            "--column=Opciones actuales",
            "--width=1100",
            "--height=560",
            *rows,
        ]
    )
    for game in games:
        if game["appid"] == choice:
            return game
    sys.exit(1)


def choose_options(current):
    flags = detect_flags(current)
    rows = []
    for key, label in PRESETS.items():
        rows.extend(["TRUE" if flags.get(key) else "FALSE", key, label])
    output = z(
        [
            "--list",
            "--checklist",
            "--title=Steam Game Options",
            "--text=Paso 2/3: marca las opciones que quieres aplicar.\nDXR moderno suele venir activo; usa Ray Tracing DXR solo para forzarlo.",
            "--column=",
            "--column=Clave",
            "--column=Opcion",
            "--separator=|",
            "--width=760",
            "--height=500",
            *rows,
        ]
    )
    return [x for x in output.split("|") if x]


def choose_custom(game, config):
    custom = config.setdefault("custom", {}).setdefault(game["appid"], {})
    pre = z(
        [
            "--entry",
            "--title=Ajustes personalizados",
            "--text=Variables/comandos antes de %command%\nEjemplo: RADV_DEBUG=zerovram VKD3D_CONFIG=dxr",
            "--entry-text=" + custom.get("pre", ""),
            "--width=860",
        ]
    )
    post = z(
        [
            "--entry",
            "--title=Ajustes personalizados",
            "--text=Argumentos despues de %command%\nEjemplo: -dx12 -vulkan -USEALLAVAILABLECORES",
            "--entry-text=" + custom.get("post", ""),
            "--width=860",
        ]
    )
    custom["pre"] = pre
    custom["post"] = post
    save_app_config(config)
    return pre, post


def game_user_config_dir(root, appid):
    base = root / "steamapps/compatdata" / appid / "pfx/drive_c/users/steamuser/AppData/Local"
    if not base.exists():
        return None
    candidates = sorted(base.glob("*/Saved/Config/WindowsClient"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def set_unreal_hdr(root, appid):
    cfg_dir = game_user_config_dir(root, appid)
    if not cfg_dir:
        return "No encontre config de Unreal en compatdata para este juego."

    engine = cfg_dir / "Engine.ini"
    engine.touch(exist_ok=True)
    text = engine.read_text(errors="replace")
    if "[SystemSettings]" not in text:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n[SystemSettings]\n"

    for key, value in HDR_ENGINE_LINES.items():
        pattern = rf"(?m)^{re.escape(key)}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, text):
            text = re.sub(pattern, replacement, text)
        else:
            section = re.search(r"(?m)^\[SystemSettings\]\s*$", text)
            insert_at = text.find("\n", section.end()) + 1 if section else len(text)
            text = text[:insert_at] + replacement + "\n" + text[insert_at:]

    gus = cfg_dir / "GameUserSettings.ini"
    if gus.exists():
        gtext = gus.read_text(errors="replace")
        if re.search(r"(?m)^bUseHDRDisplayOutput=", gtext):
            gtext = re.sub(r"(?m)^bUseHDRDisplayOutput=.*$", "bUseHDRDisplayOutput=True", gtext)
        else:
            gtext += "\nbUseHDRDisplayOutput=True\n"
        gus.write_text(gtext)

    engine.write_text(text)
    return f"HDR Unreal aplicado en:\n{engine}"


def qt_main():
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except Exception:
        return None

    class NoWheelComboBox(QtWidgets.QComboBox):
        def wheelEvent(self, event):
            event.ignore()

    class NoWheelSpinBox(QtWidgets.QSpinBox):
        def wheelEvent(self, event):
            event.ignore()

    class NoWheelTabBar(QtWidgets.QTabBar):
        def wheelEvent(self, event):
            event.ignore()

    class App(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
            self.resize(1320, 780)
            self.setMinimumSize(900, 560)
            self.app_icon = first_existing(APP_ICON_CANDIDATES)
            if self.app_icon:
                self.setWindowIcon(QtGui.QIcon(str(self.app_icon)))
            self.app_config = load_app_config()
            self.root = steam_root(self.app_config)
            if not self.app_config.get("steam_root"):
                self.app_config["steam_root"] = str(self.root)
                save_app_config(self.app_config)
            self.config_path = localconfig_path(self.root)
            self.steam_config_path = steam_config_path(self.root)
            self.proton_tools = proton_tools(self.root)
            self.system = detect_system()
            self.system_recommended = system_recommended_keys(self.system)
            ensure_system_shared_preset(self.app_config, self.system)
            save_app_config(self.app_config)
            self.games = merged_games(self.root, self.app_config)
            self.checks = {}
            self.current_game = None
            self.current_applied_preset_ref = ""
            self.active_gamescope_res = display_resolution_or_empty(self.system.get("display", {}))

            self.setStyleSheet(
                """
                QWidget { font-size: 13px; }
                QLabel#appTitle { font-size: 22px; font-weight: 900; color: #17202a; }
                QLabel#version { color: #607d8b; font-weight: 700; }
                QLabel#sectionHint { color: #607d8b; }
                QFrame#infoBox {
                    background: #f8fafc;
                    border: 1px solid #cfd8dc;
                    border-radius: 8px;
                    padding: 8px;
                }
                QFrame#systemCard {
                    border-radius: 8px;
                    padding: 8px;
                    min-height: 42px;
                }
                QLabel#statusGood {
                    background: #e8f5e9;
                    color: #1b5e20;
                    border: 1px solid #81c784;
                    border-radius: 8px;
                    padding: 8px;
                    font-weight: 800;
                }
                QLabel#statusWarn {
                    background: #fff8e1;
                    color: #5f4300;
                    border: 1px solid #ffca28;
                    border-radius: 8px;
                    padding: 8px;
                    font-weight: 800;
                }
                QLabel#statusBad {
                    background: #ffebee;
                    color: #8a1c1c;
                    border: 1px solid #ef9a9a;
                    border-radius: 8px;
                    padding: 8px;
                    font-weight: 800;
                }
                QLabel#statusNeutral {
                    background: #eef3f7;
                    color: #29434e;
                    border: 1px solid #b0bec5;
                    border-radius: 8px;
                    padding: 8px;
                    font-weight: 800;
                }
                QFrame#gameInfo {
                    background: #f8fafc;
                    border: 1px solid #b0bec5;
                    border-radius: 10px;
                    padding: 8px;
                }
                QLabel#gameTitle {
                    color: #17202a;
                    font-size: 17px;
                    font-weight: 900;
                }
                QLabel#gameCommand {
                    color: #4f5b62;
                    background: #ffffff;
                    border: 1px solid #d6d9dd;
                    border-radius: 6px;
                    padding: 7px;
                }
                QLabel#dirtyStatus {
                    color: #17633a;
                    background: #e8f5e9;
                    border: 1px solid #81c784;
                    border-radius: 6px;
                    padding: 6px;
                    font-weight: 800;
                }
                QLabel#dirtyStatus[dirty="true"] {
                    color: #8a1c1c;
                    background: #ffebee;
                    border: 1px solid #ef5350;
                }
                QLabel#presetStatus {
                    color: #17633a;
                    background: #e8f5e9;
                    border: 1px solid #81c784;
                    border-radius: 6px;
                    padding: 6px;
                    font-weight: 800;
                }
                QLabel#presetStatus[pending="true"] {
                    color: #8a1c1c;
                    background: #ffebee;
                    border: 1px solid #ef5350;
                }
                QLabel#presetChoiceStatus {
                    color: #29434e;
                    background: #eef3f7;
                    border: 1px solid #b0bec5;
                    border-radius: 6px;
                    padding: 6px;
                    font-weight: 800;
                }
                QLabel#presetChoiceStatus[pending="true"] {
                    color: #8a1c1c;
                    background: #ffebee;
                    border: 1px solid #ef5350;
                }
                QLabel#presetChoiceStatus[applied="true"] {
                    color: #17633a;
                    background: #e8f5e9;
                    border: 1px solid #81c784;
                }
                QFrame#hero {
                    background: #eef7f2;
                    border: 1px solid #b7dfc5;
                    border-radius: 10px;
                    padding: 8px;
                }
                QGroupBox {
                    font-weight: 700;
                    margin-top: 18px;
                    padding-top: 12px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    left: 10px;
                    top: 4px;
                    padding: 0 4px;
                    background: #f8fafc;
                }
                QLabel#hint { color: #5f6368; }
                QListWidget#gameList::item { min-height: 34px; padding: 3px; }
                QCheckBox[recommended="true"] {
                    background: #fff8e1;
                    border: 1px solid #ffca28;
                    border-radius: 6px;
                    padding: 4px;
                    font-weight: 700;
                }
                QCheckBox[active="true"] {
                    background: #e3f2fd;
                    border: 1px solid #64b5f6;
                    border-radius: 6px;
                    padding: 4px;
                }
                QCheckBox[systemRecommended="true"] {
                    background: #fff8e1;
                    border: 1px solid #ffca28;
                    border-radius: 6px;
                    padding: 4px;
                    font-weight: 700;
                }
                QCheckBox[important="true"] {
                    background: #fff8e1;
                    border: 1px solid #ffca28;
                    border-radius: 6px;
                    padding: 4px;
                    font-weight: 800;
                }
                QCheckBox[caution="true"] {
                    background: #ffebee;
                    border: 1px solid #ef5350;
                    border-radius: 6px;
                    padding: 4px;
                    font-weight: 800;
                }
                QCheckBox#launchOption {
                    border-radius: 6px;
                    padding: 7px;
                    min-height: 24px;
                }
                QPlainTextEdit, QLineEdit, QListWidget {
                    border: 1px solid #c9cdd2;
                    border-radius: 6px;
                    padding: 4px;
                }
                QPushButton {
                    padding: 6px 10px;
                    border-radius: 6px;
                    border: 1px solid #aeb4bb;
                    background: #f7f8fa;
                }
                QPushButton:hover { background: #eef2f5; border-color: #7b8794; }
                QPushButton:disabled { color: #9aa0a6; background: #f1f3f4; border-color: #d0d4d8; }
                QPushButton#apply { font-weight: 700; }
                QPushButton#launchButton {
                    background: #1f9d55;
                    color: white;
                    border: 1px solid #157a3d;
                    font-weight: 900;
                    padding: 10px 18px;
                }
                QPushButton#launchButton:hover { background: #187f45; }
                QPushButton#saveButton {
                    background: #1f9d55;
                    color: white;
                    border: 1px solid #157a3d;
                    font-weight: 900;
                    padding: 8px 14px;
                }
                QPushButton#saveButton:hover { background: #187f45; }
                QPushButton#manualButton {
                    font-weight: 700;
                    padding: 8px 14px;
                }
                QPushButton#clearButton {
                    background: #ffe8e6;
                    color: #9f1d17;
                    border: 1px solid #ef9a9a;
                    font-weight: 800;
                    padding: 8px 14px;
                }
                QPushButton#clearButton:hover {
                    background: #ffcdd2;
                    color: #7f130f;
                }
                QLabel#optionDetail {
                    background: #f6f7f8;
                    border: 1px solid #d6d9dd;
                    border-radius: 6px;
                    padding: 8px;
                }
                QLabel#protondbBadge {
                    border-radius: 8px;
                    padding: 8px;
                    font-weight: 900;
                }
                QFrame#optionSection {
                    background: #fbfcfd;
                    border: 1px solid #ccd5dc;
                    border-radius: 8px;
                }
                QPushButton#optionSectionHeader {
                    background: #eef3f7;
                    border: 0;
                    border-bottom: 1px solid #ccd5dc;
                    border-radius: 8px;
                    padding: 9px 10px;
                    text-align: left;
                    color: #263238;
                    font-weight: 900;
                }
                QPushButton#optionSectionHeader:hover { background: #e4edf3; }
                """
            )

            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(8)
            hero = QtWidgets.QFrame()
            hero.setObjectName("hero")
            hero_layout = QtWidgets.QHBoxLayout(hero)
            hero_layout.setContentsMargins(8, 6, 8, 6)
            if self.app_icon:
                icon = QtWidgets.QLabel()
                pix = QtGui.QPixmap(str(self.app_icon)).scaled(48, 48, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                icon.setPixmap(pix)
                hero_layout.addWidget(icon)
            title_col = QtWidgets.QVBoxLayout()
            app_title = QtWidgets.QLabel(APP_NAME)
            app_title.setObjectName("appTitle")
            self.app_version_label = QtWidgets.QLabel()
            self.app_version_label.setObjectName("version")
            title_col.addWidget(app_title)
            title_col.addWidget(self.app_version_label)
            hero_layout.addLayout(title_col, 1)
            self.steam_path_btn = QtWidgets.QPushButton("Ruta Steam")
            self.steam_path_btn.setToolTip("Seleccionar manualmente la carpeta raiz de Steam y guardarla para proximas ejecuciones.")
            self.language_btn = QtWidgets.QPushButton()
            self.language_btn.setToolTip("Cambiar idioma / Change language")
            self.compact_btn = QtWidgets.QPushButton("Modo compacto")
            self.compact_btn.setCheckable(True)
            self.compact_btn.setChecked(bool(self.app_config.get("compact_mode")))
            self.compact_btn.setToolTip("Reduce texto tecnico y deja la interfaz mas ligera para pantallas pequenas.")
            self.read_only_btn = QtWidgets.QPushButton("Solo lectura")
            self.read_only_btn.setCheckable(True)
            self.read_only_btn.setChecked(bool(self.app_config.get("read_only")))
            self.read_only_btn.setToolTip("Permite revisar juegos, presets y diagnosticos sin escribir cambios en Steam ni en presets.")
            hero_layout.addWidget(self.steam_path_btn)
            hero_layout.addWidget(self.language_btn)
            hero_layout.addWidget(self.compact_btn)
            hero_layout.addWidget(self.read_only_btn)
            layout.addWidget(hero)

            splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
            splitter.setChildrenCollapsible(False)
            layout.addWidget(splitter, 1)

            left = QtWidgets.QVBoxLayout()
            left_panel = QtWidgets.QWidget()
            left_panel.setLayout(left)
            left_panel.setMinimumWidth(190)
            left_panel.setMaximumWidth(460)
            splitter.addWidget(left_panel)
            right_scroll = QtWidgets.QScrollArea()
            right_scroll.setWidgetResizable(True)
            right_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            right_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            right_panel = QtWidgets.QWidget()
            right = QtWidgets.QVBoxLayout(right_panel)
            right.setContentsMargins(2, 2, 8, 2)
            right.setSpacing(6)
            right_scroll.setWidget(right_panel)
            splitter.addWidget(right_scroll)
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setSizes([285, 980])

            self.games_title_label = QtWidgets.QLabel("1. Juegos instalados")
            self.games_title_label.setStyleSheet("font-size: 18px; font-weight: 800;")
            left.addWidget(self.games_title_label)
            self.game_list = QtWidgets.QListWidget()
            self.game_list.setObjectName("gameList")
            self.game_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.game_list.setTextElideMode(QtCore.Qt.ElideNone)
            self.game_list.setIconSize(QtCore.QSize(28, 28))
            for game in self.games:
                summary = self.cached_game_summary(game["appid"])
                item = QtWidgets.QListWidgetItem(self.game_label(game, summary))
                item.setData(QtCore.Qt.UserRole, game)
                icon_path = game_icon(self.root, game)
                if icon_path:
                    item.setIcon(QtGui.QIcon(str(icon_path)))
                self.style_game_item(item, summary)
                self.game_list.addItem(item)
            left.addWidget(self.game_list, 1)
            self.add_game_btn = QtWidgets.QPushButton("Añadir juego")
            self.edit_game_btn = QtWidgets.QPushButton("Editar manual")
            self.remove_game_btn = QtWidgets.QPushButton("Quitar manual")
            left.addWidget(self.add_game_btn)
            left.addWidget(self.edit_game_btn)
            left.addWidget(self.remove_game_btn)

            game_info = QtWidgets.QFrame()
            game_info.setObjectName("gameInfo")
            game_info_layout = QtWidgets.QVBoxLayout(game_info)
            game_info_layout.setContentsMargins(8, 8, 8, 8)
            title_row = QtWidgets.QHBoxLayout()
            self.current_title = QtWidgets.QLabel("Selecciona un juego")
            self.current_title.setObjectName("gameTitle")
            self.current_title.setWordWrap(True)
            self.launch_btn = QtWidgets.QPushButton("Iniciar juego")
            self.launch_btn.setObjectName("launchButton")
            self.launch_btn.setToolTip("Inicia el juego seleccionado. Steam usara las opciones que ya esten guardadas.")
            title_row.addWidget(self.current_title, 1)
            title_row.addWidget(self.launch_btn)
            game_info_layout.addLayout(title_row)
            self.current_label = QtWidgets.QLabel("Selecciona un juego para ver sus opciones.")
            self.current_label.setObjectName("gameCommand")
            self.current_label.setWordWrap(True)
            game_info_layout.addWidget(self.current_label)
            proton_row = QtWidgets.QGridLayout()
            proton_row.setHorizontalSpacing(6)
            proton_row.setVerticalSpacing(6)
            self.proton_status_label = QtWidgets.QLabel("Proton: sin detectar")
            self.proton_status_label.setWordWrap(True)
            self.proton_combo = NoWheelComboBox()
            self.proton_combo.setToolTip("Selecciona la version de Proton que Steam usara para este juego. Steam por defecto elimina el forzado por juego.")
            self.proton_combo.setMinimumContentsLength(18)
            self.proton_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            self.recommend_proton_btn = QtWidgets.QPushButton("Recomendada")
            self.recommend_proton_btn.setToolTip("Selecciona la version de Proton que Proton Pilot recomienda entre las instaladas.")
            self.apply_proton_btn = QtWidgets.QPushButton("Aplicar Proton")
            self.apply_proton_btn.setToolTip("Guarda la version de Proton elegida para este juego cerrando Steam si hace falta.")
            proton_row.addWidget(self.proton_status_label, 0, 0, 1, 3)
            proton_row.addWidget(self.proton_combo, 1, 0)
            proton_row.addWidget(self.recommend_proton_btn, 1, 1)
            proton_row.addWidget(self.apply_proton_btn, 1, 2)
            proton_row.setColumnStretch(0, 1)
            game_info_layout.addLayout(proton_row)
            self.dirty_label = QtWidgets.QLabel("Sin cambios pendientes.")
            self.dirty_label.setObjectName("dirtyStatus")
            self.dirty_label.setWordWrap(True)
            game_info_layout.addWidget(self.dirty_label)
            self.current_preset_label = QtWidgets.QLabel("Preset actual: sin detectar")
            self.current_preset_label.setObjectName("presetStatus")
            self.current_preset_label.setWordWrap(True)
            game_info_layout.addWidget(self.current_preset_label)
            right.addWidget(game_info)
            self.protondb_badge = QtWidgets.QLabel("ProtonDB: sin datos")
            self.protondb_badge.setObjectName("protondbBadge")
            self.protondb_badge.setWordWrap(True)
            self.protondb_badge.setVisible(False)
            right.addWidget(self.protondb_badge)

            self.tabs = QtWidgets.QTabWidget()
            self.tabs.setTabBar(NoWheelTabBar())
            overview_tab = QtWidgets.QWidget()
            presets_tab = QtWidgets.QWidget()
            options_tab = QtWidgets.QWidget()
            advanced_tab = QtWidgets.QWidget()
            overview = QtWidgets.QVBoxLayout(overview_tab)
            presets_view = QtWidgets.QVBoxLayout(presets_tab)
            options_view = QtWidgets.QVBoxLayout(options_tab)
            advanced = QtWidgets.QVBoxLayout(advanced_tab)
            for tab_layout in (overview, presets_view, options_view, advanced):
                tab_layout.setContentsMargins(6, 6, 6, 6)
                tab_layout.setSpacing(6)
            self.tabs.addTab(overview_tab, "Resumen")
            self.tabs.addTab(presets_tab, "Presets")
            self.tabs.addTab(options_tab, "Opciones")
            self.tabs.addTab(advanced_tab, "Avanzado")
            right.addWidget(self.tabs, 1)

            self.sys_box = QtWidgets.QGroupBox("Recomendaciones segun tu sistema")
            sys_layout = QtWidgets.QVBoxLayout(self.sys_box)
            sys_layout.setContentsMargins(8, 20, 8, 8)
            cards = QtWidgets.QGridLayout()
            cards.setHorizontalSpacing(6)
            cards.setVerticalSpacing(6)
            display = self.system.get("display", {})

            self.status_cards = {}

            def status_card(key, title, value, state="neutral"):
                label = QtWidgets.QLabel(f"{title}\n{value}")
                label.setObjectName({"good": "statusGood", "warn": "statusWarn", "bad": "statusBad"}.get(state, "statusNeutral"))
                label.setWordWrap(True)
                self.status_cards[key] = (label, state)
                return label

            hdr_value = "ACTIVO" if display_hdr_enabled(display) else (display.get("hdr") or "no detectado")
            hdr_state = "good" if display_hdr_enabled(display) else ("warn" if display.get("hdr") else "bad")
            vrr_value = (display.get("vrr") or "no detectado").upper()
            vrr_state = "good" if display_vrr_available(display) else ("warn" if display.get("vrr") else "bad")
            display_value = (
                f"{display.get('name') or 'monitor'} {display.get('width') or '?'}x{display.get('height') or '?'}"
                f"@{display.get('refresh') or '?'}"
            )
            tools_value = (
                f"Gamescope {'si' if self.system['tools'].get('gamescope') else 'no'} · "
                f"GameMode {'si' if self.system['tools'].get('gamemoderun') else 'no'} · "
                f"MangoHud {'si' if self.system['tools'].get('mangohud') else 'no'}"
            )
            gaming_value = "DETECTADO" if self.system.get("device", {}).get("gaming_mode") else "Desktop Mode"
            cards.addWidget(status_card("system", "Sistema", f"{self.system['os'].get('name') or 'OS'} · {self.system['session'].get('type') or 'sesion'}"), 0, 0)
            cards.addWidget(status_card("display", "Pantalla", display_value, "good" if display.get("width") else "warn"), 0, 1)
            cards.addWidget(status_card("hdr", "HDR sistema", hdr_value, hdr_state), 1, 0)
            cards.addWidget(status_card("vrr", "VRR", vrr_value, vrr_state), 1, 1)
            cards.addWidget(status_card("gpu", "GPU", self.system["gpu_name"], "neutral"), 2, 0)
            cards.addWidget(status_card("tools", "Herramientas", tools_value, "good"), 2, 1)
            cards.addWidget(status_card("mode", "Modo", gaming_value, "warn" if self.system.get("device", {}).get("gaming_mode") else "good"), 3, 0, 1, 2)
            cards.setColumnStretch(0, 1)
            cards.setColumnStretch(1, 1)
            sys_layout.addLayout(cards)
            self.sys_reasons = QtWidgets.QLabel("\n".join(f"- {r}" for r in recommendation_reasons(self.system)) or "No hay recomendaciones automaticas.")
            self.sys_reasons.setWordWrap(True)
            sys_layout.addWidget(self.sys_reasons)
            overview.addWidget(self.sys_box)

            self.action_box = QtWidgets.QGroupBox("Acciones frecuentes")
            action_layout = QtWidgets.QGridLayout(self.action_box)
            action_layout.setContentsMargins(8, 20, 8, 8)
            action_layout.setHorizontalSpacing(6)
            action_layout.setVerticalSpacing(6)
            self.recommend_btn = QtWidgets.QPushButton("Recomendaciones")
            self.open_protondb_btn = QtWidgets.QPushButton("Abrir ProtonDB")
            self.apply_system_btn = QtWidgets.QPushButton("Marcar recomendadas")
            self.apply_system_btn.setToolTip("Marca las opciones amarillas recomendadas segun tu sistema detectado. Para escribirlas en el juego, aplica un preset o guarda un comando.")
            self.assistant_btn = QtWidgets.QPushButton("Asistente perfil")
            self.assistant_btn.setToolTip("Marca opciones segun un objetivo: rendimiento, HDR, VRR estable, Ray Tracing o handheld.")
            self.apply_command_btn = QtWidgets.QPushButton("Aplicar cambios preparados")
            self.apply_command_btn.setObjectName("saveButton")
            self.apply_command_btn.setToolTip("Escribe en Steam o en el perfil externo el comando que esta preparado ahora en pantalla.")
            self.compare_btn = QtWidgets.QPushButton("Comparar")
            self.compare_btn.setToolTip("Compara las opciones guardadas con el comando preparado en pantalla.")
            self.history_btn = QtWidgets.QPushButton("Historial")
            self.history_btn.setToolTip("Muestra comandos anteriores guardados para este juego y permite restaurarlos.")
            self.display_diag_btn = QtWidgets.QPushButton("Diagnostico HDR/VRR")
            self.display_diag_btn.setToolTip("Explica por que HDR, VRR o Gamescope pueden no estar funcionando.")
            self.proton_history_btn = QtWidgets.QPushButton("Historial Proton")
            self.proton_history_btn.setToolTip("Muestra cambios anteriores de version Proton por juego y permite restaurar uno.")
            self.register_appimage_btn = QtWidgets.QPushButton("Registrar AppImage")
            self.register_appimage_btn.setToolTip("Anade Proton Pilot a Steam como juego externo si se esta ejecutando desde AppImage.")
            self.update_app_btn = QtWidgets.QPushButton("Buscar actualizacion")
            self.update_app_btn.setToolTip("Consulta la ultima release de GitHub y abre la descarga si existe.")
            self.about_btn = QtWidgets.QPushButton("Acerca de")
            for idx, button in enumerate([self.apply_command_btn, self.assistant_btn, self.apply_system_btn, self.recommend_btn]):
                action_layout.addWidget(button, idx // 4, idx % 4)
            for col in range(4):
                action_layout.setColumnStretch(col, 1)
            overview.addWidget(self.action_box)

            self.tools_box = QtWidgets.QGroupBox("Herramientas y diagnostico")
            tools_layout = QtWidgets.QGridLayout(self.tools_box)
            tools_layout.setContentsMargins(8, 20, 8, 8)
            tools_layout.setHorizontalSpacing(6)
            tools_layout.setVerticalSpacing(6)
            for idx, button in enumerate(
                [
                    self.open_protondb_btn,
                    self.compare_btn,
                    self.history_btn,
                    self.display_diag_btn,
                    self.proton_history_btn,
                    self.register_appimage_btn,
                    self.update_app_btn,
                    self.about_btn,
                ]
            ):
                tools_layout.addWidget(button, idx // 4, idx % 4)
            for col in range(4):
                tools_layout.setColumnStretch(col, 1)
            overview.addWidget(self.tools_box)
            overview.addStretch(1)

            self.preset_box = QtWidgets.QGroupBox("Presets del juego")
            preset_layout = QtWidgets.QVBoxLayout(self.preset_box)
            preset_layout.setContentsMargins(8, 20, 8, 8)
            preset_row = QtWidgets.QGridLayout()
            preset_row.setHorizontalSpacing(6)
            preset_row.setVerticalSpacing(6)
            self.preset_combo = NoWheelComboBox()
            self.preset_combo.setToolTip("Selecciona un preset para cargar automaticamente sus opciones en pantalla. La rueda del raton no cambia este selector.")
            self.preset_combo.setMinimumContentsLength(22)
            self.preset_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            self.apply_preset_btn = QtWidgets.QPushButton("Aplicar preset")
            self.apply_preset_btn.setToolTip("Guarda el preset seleccionado como opciones de lanzamiento del juego, con confirmacion.")
            self.apply_preset_btn.setEnabled(False)
            self.save_preset_btn = QtWidgets.QPushButton("Crear nuevo preset")
            self.save_preset_btn.setToolTip("Crea un preset compartido disponible para cualquier juego.")
            self.update_preset_btn = QtWidgets.QPushButton("Actualizar preset")
            self.delete_preset_btn = QtWidgets.QPushButton("Borrar preset")
            preset_row.addWidget(self.preset_combo, 0, 0, 1, 4)
            preset_row.addWidget(self.apply_preset_btn, 1, 0)
            preset_row.addWidget(self.save_preset_btn, 1, 1)
            preset_row.addWidget(self.update_preset_btn, 1, 2)
            preset_row.addWidget(self.delete_preset_btn, 1, 3)
            for col in range(4):
                preset_row.setColumnStretch(col, 1)
            preset_layout.addLayout(preset_row)
            self.preset_choice_label = QtWidgets.QLabel("Selecciona un preset para cargarlo.")
            self.preset_choice_label.setObjectName("presetChoiceStatus")
            self.preset_choice_label.setWordWrap(True)
            preset_layout.addWidget(self.preset_choice_label)
            presets_view.addWidget(self.preset_box)
            presets_view.addStretch(1)

            opts_box = QtWidgets.QGroupBox("Opciones que se aplicaran al lanzamiento")
            self.opts_box = opts_box
            opts_layout = QtWidgets.QVBoxLayout(opts_box)
            opts_layout.setContentsMargins(8, 20, 8, 8)
            opts_layout.setSpacing(6)
            option_buttons = QtWidgets.QGridLayout()
            option_buttons.setHorizontalSpacing(6)
            self.add_option_btn = QtWidgets.QPushButton("+ Opcion manual")
            self.add_option_btn.setToolTip("Crea una opcion manual reutilizable y la coloca en la categoria elegida.")
            self.delete_option_btn = QtWidgets.QPushButton("Papelera")
            self.delete_option_btn.setToolTip("Mueve una opcion manual a la papelera para poder restaurarla despues.")
            self.restore_option_btn = QtWidgets.QPushButton("Restaurar opcion")
            self.restore_option_btn.setToolTip("Recupera una opcion manual borrada previamente.")
            option_buttons.addWidget(self.add_option_btn, 0, 0)
            option_buttons.addWidget(self.delete_option_btn, 0, 1)
            option_buttons.addWidget(self.restore_option_btn, 0, 2)
            for col in range(3):
                option_buttons.setColumnStretch(col, 1)
            opts_layout.addLayout(option_buttons)
            self.options_container = QtWidgets.QWidget()
            self.options_container_layout = QtWidgets.QVBoxLayout(self.options_container)
            self.options_container_layout.setContentsMargins(0, 0, 0, 0)
            self.options_container_layout.setSpacing(6)
            self.option_group_boxes = []
            opts_layout.addWidget(self.options_container)
            self.rebuild_option_checkboxes()
            opts_layout.addStretch(1)
            options_view.addWidget(opts_box, 1)

            self.option_detail = QtWidgets.QLabel("Pasa el cursor por encima de una opcion para ver que hace y que anade al lanzamiento.")
            self.option_detail.setObjectName("optionDetail")
            self.option_detail.setWordWrap(True)
            options_view.addWidget(self.option_detail)

            self.res_box = QtWidgets.QGroupBox("Resolucion Gamescope")
            res_layout = QtWidgets.QGridLayout(self.res_box)
            res_layout.setContentsMargins(8, 20, 8, 8)
            res_layout.setHorizontalSpacing(6)
            res_layout.setVerticalSpacing(6)
            self.real_width = NoWheelSpinBox()
            self.real_width.setRange(0, 10000)
            self.real_width.setSuffix(" px")
            self.real_height = NoWheelSpinBox()
            self.real_height.setRange(0, 10000)
            self.real_height.setSuffix(" px")
            self.real_refresh = NoWheelSpinBox()
            self.real_refresh.setRange(0, 1000)
            self.real_refresh.setSuffix(" Hz")
            for spin in (self.real_width, self.real_height, self.real_refresh):
                spin.setToolTip("Edita escribiendo o con las flechas. La rueda del raton esta desactivada para no cambiar valores al desplazarte.")
            self.apply_resolution_btn = QtWidgets.QPushButton("Aplicar resolucion")
            self.apply_resolution_btn.setToolTip("Usa los valores de ancho/alto/Hz en el comando Gamescope y activa Resolucion real Gamescope.")
            self.detect_display_btn = QtWidgets.QPushButton("Usar monitor principal")
            self.detect_display_btn.setToolTip("Detecta el monitor principal, rellena la resolucion y la aplica al comando Gamescope.")
            self.width_label = QtWidgets.QLabel("Ancho")
            self.height_label = QtWidgets.QLabel("Alto")
            self.hz_label = QtWidgets.QLabel("Hz")
            res_layout.addWidget(self.width_label, 0, 0)
            res_layout.addWidget(self.real_width, 0, 1)
            res_layout.addWidget(self.height_label, 0, 2)
            res_layout.addWidget(self.real_height, 0, 3)
            res_layout.addWidget(self.hz_label, 0, 4)
            res_layout.addWidget(self.real_refresh, 0, 5)
            res_layout.addWidget(self.apply_resolution_btn, 1, 0, 1, 3)
            res_layout.addWidget(self.detect_display_btn, 1, 3, 1, 3)
            for col in (1, 3, 5):
                res_layout.setColumnStretch(col, 1)
            advanced.addWidget(self.res_box)

            self.custom_box = QtWidgets.QGroupBox("Ajustes personalizados")
            custom_layout = QtWidgets.QFormLayout(self.custom_box)
            custom_layout.setContentsMargins(8, 20, 8, 8)
            self.custom_pre = QtWidgets.QLineEdit()
            self.custom_pre.setPlaceholderText("Antes de %command%, ej: RADV_PERFTEST=rt VKD3D_CONFIG=dxr")
            self.custom_post = QtWidgets.QLineEdit()
            self.custom_post.setPlaceholderText("Despues de %command%, ej: -dx12 -NoLauncher")
            self.custom_pre.textChanged.connect(self.update_command)
            self.custom_post.textChanged.connect(self.update_command)
            self.custom_pre_label = QtWidgets.QLabel("Antes:")
            self.custom_post_label = QtWidgets.QLabel("Despues:")
            custom_layout.addRow(self.custom_pre_label, self.custom_pre)
            custom_layout.addRow(self.custom_post_label, self.custom_post)
            advanced.addWidget(self.custom_box)

            self.final_command_label = QtWidgets.QLabel("Comando final")
            advanced.addWidget(self.final_command_label)
            self.command_edit = QtWidgets.QPlainTextEdit()
            self.command_edit.setPlaceholderText("%command%")
            self.command_edit.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
            self.command_edit.setMaximumHeight(78)
            self.command_edit.setMaximumBlockCount(4)
            self.command_edit.textChanged.connect(self.update_dirty_state)
            advanced.addWidget(self.command_edit, 1)
            advanced.addStretch(1)

            buttons = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons)
            self.save_btn = QtWidgets.QPushButton("Guardar comando manual")
            self.save_btn.setObjectName("manualButton")
            self.save_btn.setToolTip("Pensado para cuando editas a mano el Comando final. Crea un preset custom del juego y guarda exactamente ese comando.")
            self.clear_btn = QtWidgets.QPushButton("Borrar opciones")
            self.clear_btn.setObjectName("clearButton")
            self.reload_btn = QtWidgets.QPushButton("Recargar")
            buttons.addWidget(self.reload_btn)
            buttons.addStretch(1)
            buttons.addWidget(self.clear_btn)
            buttons.addWidget(self.save_btn)

            self.game_list.currentItemChanged.connect(self.select_game)
            self.steam_path_btn.clicked.connect(self.choose_steam_path)
            self.language_btn.clicked.connect(self.toggle_language)
            self.compact_btn.toggled.connect(self.toggle_compact_mode)
            self.read_only_btn.toggled.connect(self.toggle_read_only)
            self.add_game_btn.clicked.connect(self.add_manual_game)
            self.edit_game_btn.clicked.connect(self.edit_manual_game)
            self.remove_game_btn.clicked.connect(self.remove_manual_game)
            self.recommend_btn.clicked.connect(self.show_recommendations)
            self.open_protondb_btn.clicked.connect(self.open_protondb)
            self.apply_system_btn.clicked.connect(self.apply_system_recommended)
            self.apply_command_btn.clicked.connect(self.apply_prepared_command)
            self.add_option_btn.clicked.connect(self.add_custom_option)
            self.delete_option_btn.clicked.connect(self.delete_custom_option)
            self.restore_option_btn.clicked.connect(self.restore_custom_option)
            self.assistant_btn.clicked.connect(self.show_profile_assistant)
            self.compare_btn.clicked.connect(self.show_compare_dialog)
            self.history_btn.clicked.connect(self.show_history_dialog)
            self.display_diag_btn.clicked.connect(self.show_display_diagnostics)
            self.proton_history_btn.clicked.connect(self.show_proton_history_dialog)
            self.register_appimage_btn.clicked.connect(self.register_appimage_shortcut)
            self.update_app_btn.clicked.connect(self.check_for_updates)
            self.recommend_proton_btn.clicked.connect(self.select_recommended_proton)
            self.apply_proton_btn.clicked.connect(self.apply_selected_proton)
            self.launch_btn.clicked.connect(self.launch_current_game)
            self.about_btn.clicked.connect(self.show_about)
            self.apply_resolution_btn.clicked.connect(self.apply_resolution_fields)
            self.detect_display_btn.clicked.connect(self.use_detected_display)
            self.preset_combo.currentIndexChanged.connect(self.on_preset_selected)
            self.apply_preset_btn.clicked.connect(self.apply_selected_preset)
            self.save_preset_btn.clicked.connect(self.save_preset)
            self.update_preset_btn.clicked.connect(self.update_preset)
            self.delete_preset_btn.clicked.connect(self.delete_preset)
            self.save_btn.clicked.connect(self.save)
            self.clear_btn.clicked.connect(self.clear)
            self.reload_btn.clicked.connect(self.reload)
            self.tabs.currentChanged.connect(self.save_ui_layout_state)

            self.apply_language()
            self.apply_compact_mode()
            self.set_action_availability()
            selected_tab = int(self.app_config.get("selected_tab", 0) or 0)
            if 0 <= selected_tab < self.tabs.count():
                self.tabs.setCurrentIndex(selected_tab)
            if self.game_list.count():
                self.game_list.setCurrentRow(0)

        def config_text(self):
            return self.config_path.read_text(errors="replace")

        def steam_config_text(self):
            return self.steam_config_path.read_text(errors="replace")

        def language(self):
            return "en" if self.app_config.get("language") == "en" else "es"

        def tr(self, key, **kwargs):
            text = UI_TEXT.get(self.language(), UI_TEXT["es"]).get(key, UI_TEXT["es"].get(key, key))
            return text.format(**kwargs) if kwargs else text

        def tx(self, es, en):
            return en if self.language() == "en" else es

        def category_label(self, title):
            if self.language() == "en":
                return CATEGORY_LABEL_EN.get(title, title)
            return title

        def option_label(self, key):
            if self.language() == "en" and key in OPTION_LABEL_EN:
                return OPTION_LABEL_EN[key]
            if is_custom_option_key(key):
                option = self.option_from_key(key)
                return option.get("label", self.tx("Opcion manual", "Custom option"))
            return OPTION_INFO.get(key, {}).get("label", key)

        def option_description(self, key):
            if self.language() == "en" and key in OPTION_DESCRIPTION_EN:
                return OPTION_DESCRIPTION_EN[key]
            return OPTION_INFO.get(key, {}).get("description", "")

        def toggle_language(self):
            self.app_config["language"] = "en" if self.language() == "es" else "es"
            save_app_config(self.app_config)
            selected = set(self.selected_keys()) if getattr(self, "checks", None) else set()
            self.apply_language()
            if getattr(self, "options_container_layout", None):
                self.rebuild_option_checkboxes(selected)
                self.update_category_headers()
            if self.current_game:
                current_ref = self.preset_combo.currentData() if getattr(self, "preset_combo", None) else ""
                self.refresh_presets()
                if current_ref:
                    index = self.preset_combo.findData(current_ref)
                    if index >= 0:
                        self.preset_combo.blockSignals(True)
                        self.preset_combo.setCurrentIndex(index)
                        self.preset_combo.blockSignals(False)
            self.refresh_game_texts()
            self.update_dirty_state()
            self.update_proton_selector()

        def apply_language(self):
            self.app_version_label.setText(self.tr("version_subtitle", version=APP_VERSION))
            self.language_btn.setText("🇬🇧 English" if self.language() == "en" else "🇪🇸 Español")
            self.steam_path_btn.setText(self.tr("steam_path"))
            self.steam_path_btn.setToolTip(self.tx(
                "Seleccionar manualmente la carpeta raiz de Steam y guardarla para proximas ejecuciones.",
                "Manually select the Steam root folder and remember it for future launches.",
            ))
            self.compact_btn.setText(self.tr("compact"))
            self.compact_btn.setToolTip(self.tx(
                "Reduce texto tecnico y deja la interfaz mas ligera para pantallas pequenas.",
                "Reduces technical text and makes the interface lighter for small screens.",
            ))
            self.read_only_btn.setText(self.tr("read_only"))
            self.read_only_btn.setToolTip(self.tx(
                "Permite revisar juegos, presets y diagnosticos sin escribir cambios en Steam ni en presets.",
                "Lets you inspect games, presets and diagnostics without writing changes to Steam or presets.",
            ))
            self.games_title_label.setText(self.tr("games_installed"))
            self.add_game_btn.setText(self.tr("add_game"))
            self.edit_game_btn.setText(self.tr("edit_manual"))
            self.remove_game_btn.setText(self.tr("remove_manual"))
            self.launch_btn.setText(self.tr("launch"))
            self.launch_btn.setToolTip(self.tr("launch_tip"))
            for index, label in enumerate(self.tr("tabs")):
                self.tabs.setTabText(index, label)
            self.sys_box.setTitle(self.tr("system_recs"))
            self.action_box.setTitle(self.tr("actions"))
            self.tools_box.setTitle(self.tr("tools"))
            self.recommend_btn.setText(self.tr("recommendations"))
            self.open_protondb_btn.setText(self.tr("open_protondb"))
            self.apply_system_btn.setText(self.tr("mark_recommended"))
            self.assistant_btn.setText(self.tr("profile_assistant"))
            self.apply_command_btn.setText(self.tr("apply_prepared"))
            self.compare_btn.setText(self.tr("compare"))
            self.history_btn.setText(self.tr("history"))
            self.display_diag_btn.setText(self.tr("display_diag"))
            self.proton_history_btn.setText(self.tr("proton_history"))
            self.register_appimage_btn.setText(self.tr("register_appimage"))
            self.update_app_btn.setText(self.tr("check_updates"))
            self.about_btn.setText(self.tr("about"))
            self.preset_box.setTitle(self.tr("presets_box"))
            self.apply_preset_btn.setText(self.tr("apply_preset"))
            self.save_preset_btn.setText(self.tr("create_preset"))
            self.update_preset_btn.setText(self.tr("update_preset"))
            self.delete_preset_btn.setText(self.tr("delete_preset"))
            self.opts_box.setTitle(self.tr("options_box"))
            self.add_option_btn.setText(self.tr("add_option"))
            self.delete_option_btn.setText(self.tr("delete_option"))
            self.restore_option_btn.setText(self.tr("restore_option"))
            self.res_box.setTitle(self.tr("resolution_box"))
            self.apply_resolution_btn.setText(self.tr("apply_resolution"))
            self.detect_display_btn.setText(self.tr("use_main_monitor"))
            self.width_label.setText(self.tr("width"))
            self.height_label.setText(self.tr("height"))
            self.hz_label.setText("Hz")
            self.custom_box.setTitle(self.tr("custom_box"))
            self.custom_pre_label.setText(self.tr("before"))
            self.custom_post_label.setText(self.tr("after"))
            self.final_command_label.setText(self.tr("final_command"))
            self.save_btn.setText(self.tr("save_manual"))
            self.clear_btn.setText(self.tr("clear_options"))
            self.reload_btn.setText(self.tr("reload"))
            self.recommend_proton_btn.setText(self.tr("proton_recommended_btn"))
            self.apply_proton_btn.setText(self.tr("apply_proton"))
            self.proton_combo.setToolTip(self.tx(
                "Selecciona la version de Proton que Steam usara para este juego. Steam por defecto elimina el forzado por juego.",
                "Select the Proton version Steam will use for this game. Steam default removes the per-game override.",
            ))
            self.recommend_proton_btn.setToolTip(self.tx(
                "Selecciona la version de Proton que Proton Pilot recomienda entre las instaladas.",
                "Selects the Proton version Proton Pilot recommends among the installed ones.",
            ))
            self.apply_proton_btn.setToolTip(self.tx(
                "Guarda la version de Proton elegida para este juego cerrando Steam si hace falta.",
                "Saves the chosen Proton version for this game, closing Steam if needed.",
            ))
            self.apply_system_btn.setToolTip(self.tx(
                "Marca las opciones amarillas recomendadas segun tu sistema detectado. Para escribirlas en el juego, aplica un preset o guarda un comando.",
                "Marks the yellow options recommended for your detected system. To write them to the game, apply a preset or save a command.",
            ))
            self.assistant_btn.setToolTip(self.tx(
                "Marca opciones segun un objetivo: rendimiento, HDR, VRR estable, Ray Tracing o handheld.",
                "Marks options for a goal: performance, HDR, stable VRR, Ray Tracing or handheld.",
            ))
            self.apply_command_btn.setToolTip(self.tx(
                "Escribe en Steam o en el perfil externo el comando que esta preparado ahora en pantalla.",
                "Writes the command currently prepared on screen to Steam or the external profile.",
            ))
            self.compare_btn.setToolTip(self.tx(
                "Compara las opciones guardadas con el comando preparado en pantalla.",
                "Compares the saved options with the prepared command on screen.",
            ))
            self.history_btn.setToolTip(self.tx(
                "Muestra comandos anteriores guardados para este juego y permite restaurarlos.",
                "Shows previous commands saved for this game and lets you restore them.",
            ))
            self.display_diag_btn.setToolTip(self.tx(
                "Explica por que HDR, VRR o Gamescope pueden no estar funcionando.",
                "Explains why HDR, VRR or Gamescope may not be working.",
            ))
            self.proton_history_btn.setToolTip(self.tx(
                "Muestra cambios anteriores de version Proton por juego y permite restaurar uno.",
                "Shows previous per-game Proton version changes and lets you restore one.",
            ))
            self.register_appimage_btn.setToolTip(self.tx(
                "Anade Proton Pilot a Steam como juego externo si se esta ejecutando desde AppImage.",
                "Adds Proton Pilot to Steam as a non-Steam game when running from AppImage.",
            ))
            self.update_app_btn.setToolTip(self.tx(
                "Consulta la ultima release de GitHub y abre la descarga si existe.",
                "Checks the latest GitHub release and opens the download when available.",
            ))
            self.preset_combo.setToolTip(self.tx(
                "Selecciona un preset para cargar automaticamente sus opciones en pantalla. La rueda del raton no cambia este selector.",
                "Select a preset to automatically load its options on screen. The mouse wheel does not change this selector.",
            ))
            self.apply_preset_btn.setToolTip(self.tx(
                "Guarda el preset seleccionado como opciones de lanzamiento del juego, con confirmacion.",
                "Saves the selected preset as the game's launch options, with confirmation.",
            ))
            self.save_preset_btn.setToolTip(self.tx(
                "Crea un preset compartido disponible para cualquier juego.",
                "Creates a shared preset available to any game.",
            ))
            self.add_option_btn.setToolTip(self.tx(
                "Crea una opcion manual reutilizable y la coloca en la categoria elegida.",
                "Creates a reusable custom option and places it in the chosen category.",
            ))
            self.delete_option_btn.setToolTip(self.tx(
                "Mueve una opcion manual a la papelera para poder restaurarla despues.",
                "Moves a custom option to the trash so it can be restored later.",
            ))
            self.restore_option_btn.setToolTip(self.tx(
                "Recupera una opcion manual borrada previamente.",
                "Restores a previously deleted custom option.",
            ))
            for spin in (self.real_width, self.real_height, self.real_refresh):
                spin.setToolTip(self.tx(
                    "Edita escribiendo o con las flechas. La rueda del raton esta desactivada para no cambiar valores al desplazarte.",
                    "Edit by typing or with the arrows. The mouse wheel is disabled to avoid accidental changes while scrolling.",
                ))
            self.apply_resolution_btn.setToolTip(self.tx(
                "Usa los valores de ancho/alto/Hz en el comando Gamescope y activa Resolucion real Gamescope.",
                "Uses the width/height/Hz values in the Gamescope command and enables native Gamescope resolution.",
            ))
            self.detect_display_btn.setToolTip(self.tx(
                "Detecta el monitor principal, rellena la resolucion y la aplica al comando Gamescope.",
                "Detects the primary monitor, fills the resolution and applies it to the Gamescope command.",
            ))
            self.custom_pre.setPlaceholderText(self.tx(
                "Antes de %command%, ej: RADV_PERFTEST=rt VKD3D_CONFIG=dxr",
                "Before %command%, e.g. RADV_PERFTEST=rt VKD3D_CONFIG=dxr",
            ))
            self.custom_post.setPlaceholderText(self.tx(
                "Despues de %command%, ej: -dx12 -NoLauncher",
                "After %command%, e.g. -dx12 -NoLauncher",
            ))
            self.save_btn.setToolTip(self.tx(
                "Pensado para cuando editas a mano el Comando final. Crea un preset custom del juego y guarda exactamente ese comando.",
                "Intended for manual edits to the Final command. It creates a custom game preset and saves that exact command.",
            ))
            self.update_system_panel_text()
            self.refresh_game_texts()
            if getattr(self, "option_detail", None):
                self.option_detail.setText(self.tr("option_detail_hint"))

        def update_system_panel_text(self):
            if not getattr(self, "status_cards", None):
                return
            display = self.system.get("display", {})
            hdr_value = self.tr("active").upper() if display_hdr_enabled(display) else (display.get("hdr") or self.tr("not_detected"))
            vrr_value = (display.get("vrr") or self.tr("not_detected")).upper()
            display_value = (
                f"{display.get('name') or self.tr('main_monitor')} {display.get('width') or '?'}x{display.get('height') or '?'}"
                f"@{display.get('refresh') or '?'}"
            )
            tools_value = (
                f"Gamescope {self.tr('yes') if self.system['tools'].get('gamescope') else self.tr('no')} · "
                f"GameMode {self.tr('yes') if self.system['tools'].get('gamemoderun') else self.tr('no')} · "
                f"MangoHud {self.tr('yes') if self.system['tools'].get('mangohud') else self.tr('no')}"
            )
            gaming_value = self.tr("detected") if self.system.get("device", {}).get("gaming_mode") else self.tr("desktop_mode")
            values = {
                "system": (self.tr("status_system"), f"{self.system['os'].get('name') or 'OS'} · {self.system['session'].get('type') or self.tr('session')}"),
                "display": (self.tr("status_display"), display_value),
                "hdr": (self.tr("status_hdr"), hdr_value),
                "vrr": ("VRR", vrr_value),
                "gpu": ("GPU", self.system["gpu_name"]),
                "tools": (self.tr("status_tools"), tools_value),
                "mode": (self.tr("status_mode"), gaming_value),
            }
            for key, (title, value) in values.items():
                card = self.status_cards.get(key)
                if card:
                    card[0].setText(f"{title}\n{value}")
            if getattr(self, "sys_reasons", None):
                self.sys_reasons.setText("\n".join(f"- {r}" for r in self.localized_recommendation_reasons()) or self.tx(
                    "No hay recomendaciones automaticas.",
                    "No automatic recommendations.",
                ))

        def localized_recommendation_reasons(self):
            if self.language() == "es":
                return recommendation_reasons(self.system)
            system = self.system
            display = system.get("display", {})
            reasons = []
            if system["tools"].get("gamemoderun"):
                reasons.append("GameMode is available: recommended for general performance.")
            if system["tools"].get("mangohud"):
                reasons.append("MangoHud is available: useful for checking FPS, frametime and load.")
            if system["session"].get("type") == "wayland":
                reasons.append("Wayland session detected: Proton Wayland may be worth testing per game.")
            if system["tools"].get("gamescope") and system["gamescope_wsi"]:
                reasons.append("Gamescope + WSI detected: Gamescope, native resolution and HDR via Gamescope are recommended for compatible games.")
            if display_hdr_enabled(display):
                reasons.append("System HDR is active: KDE reports HDR enabled on the selected monitor.")
            elif display.get("hdr"):
                reasons.append(f"System HDR detected as {display.get('hdr')}: enable HDR in KDE before using HDR presets.")
            if display_vrr_available(display):
                reasons.append(f"VRR is available: KDE reports Vrr {display.get('vrr')}; Adaptive Sync and VRR cap are worth testing per game.")
            elif display.get("vrr"):
                reasons.append(f"VRR detected as {display.get('vrr')}: Adaptive Sync may have no effect.")
            if system.get("device", {}).get("is_bazzite"):
                reasons.append("Bazzite detected: handheld and Gamescope presets fit Gaming Mode well.")
            if system.get("device", {}).get("is_steamos"):
                reasons.append("SteamOS detected: use per-game profiles and avoid changing global settings from the app.")
            if system.get("device", {}).get("is_legion_go"):
                reasons.append("Lenovo Legion Go detected: 1280x800 saves battery; 1920x1200 uses the native screen.")
            elif system.get("device", {}).get("is_handheld"):
                reasons.append("Handheld device detected: 800p + FPS limit usually improves battery and stability.")
            if system.get("device", {}).get("gaming_mode"):
                reasons.append("Gaming Mode detected: review and launch from the app, but apply Steam changes preferably in Desktop Mode.")
            if system["gpu"] == "amd":
                reasons.append("AMD GPU detected: FSR4 upgrade may be worth testing in compatible games.")
            if system["gpu"] == "nvidia":
                reasons.append("NVIDIA GPU detected: NVAPI/DLSS can be useful in compatible games.")
            return reasons

        def save_ui_layout_state(self):
            if getattr(self, "tabs", None):
                self.app_config["selected_tab"] = self.tabs.currentIndex()
            save_app_config(self.app_config)

        def closeEvent(self, event):
            self.save_ui_layout_state()
            super().closeEvent(event)

        def refresh_game_texts(self):
            if not getattr(self, "current_title", None):
                return
            if not self.current_game:
                self.current_title.setText(self.tr("select_game"))
                self.current_label.setText(self.tr("select_game_hint"))
                self.proton_status_label.setText(self.tr("proton_missing"))
                self.dirty_label.setText(self.tr("no_pending"))
                self.current_preset_label.setText(self.tr("current_preset_unknown"))
                self.protondb_badge.setText(self.tr("protondb_no_data"))
                self.set_preset_choice_status(self.tr("preset_choose"), pending=False)
                return
            source = self.tx("Externo", "External") if self.current_game.get("external") else "Steam"
            self.current_title.setText(f"{self.current_game['name']} ({self.current_game['appid']}) - {source}")
            self.current_label.setText(
                f"{self.tx('Opciones guardadas', 'Saved options')}: "
                f"{short_command(self.current_game_launch_options(), 150 if self.app_config.get('compact_mode') else 220)}"
            )

        def choose_steam_path(self):
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.tx("Selecciona la carpeta raiz de Steam", "Select the Steam root folder"),
                str(self.root),
            )
            if not path:
                return
            if not valid_steam_root(path):
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tx("Ruta no valida", "Invalid path"),
                    self.tx(
                        "Esa carpeta no parece una raiz de Steam. Debe contener la carpeta steamapps.",
                        "That folder does not look like a Steam root. It must contain the steamapps folder.",
                    ),
                )
                return
            try:
                self.root = Path(path).expanduser().resolve()
                self.app_config["steam_root"] = str(self.root)
                save_app_config(self.app_config)
                self.config_path = localconfig_path(self.root)
                self.steam_config_path = steam_config_path(self.root)
                self.proton_tools = proton_tools(self.root)
                self.populate_games()
                QtWidgets.QMessageBox.information(
                    self,
                    self.tx("Ruta Steam guardada", "Steam path saved"),
                    self.tx(
                        f"Usando Steam desde:\n\n{self.root}\n\nSe recordara en la proxima ejecucion.",
                        f"Using Steam from:\n\n{self.root}\n\nIt will be remembered next time.",
                    ),
                )
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, self.tx("Error al cambiar Steam", "Error changing Steam path"), str(exc))

        def is_external_game(self):
            return bool(self.current_game and self.current_game.get("external"))

        def current_game_launch_options(self):
            if not self.current_game:
                return ""
            if self.current_game.get("external"):
                return self.app_config.setdefault("external_launch_options", {}).get(self.current_game["appid"], "")
            return current_launch_options(self.config_text(), self.current_game["appid"])

        def is_read_only(self):
            return bool(self.app_config.get("read_only"))

        def write_guard(self, action="guardar cambios"):
            if not self.is_read_only():
                return True
            QtWidgets.QMessageBox.information(
                self,
                self.tx("Modo solo lectura", "Read-only mode"),
                self.tx(
                    f"Solo lectura esta activo. Desactivalo para {action}.",
                    f"Read-only mode is enabled. Disable it to {action}.",
                ),
            )
            return False

        def allow_steam_shutdown_write(self, action):
            if self.system.get("device", {}).get("gaming_mode") and steam_is_running():
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tx("Gaming Mode detectado", "Gaming Mode detected"),
                    self.tx(
                        f"Steam esta abierto y parece que estas en Gaming Mode. Por seguridad no voy a cerrar Steam para {action}.\n\n"
                        "Haz este cambio desde Desktop Mode o cierra Steam manualmente primero.",
                        f"Steam is open and you appear to be in Gaming Mode. For safety I will not close Steam to {action}.\n\n"
                        "Make this change from Desktop Mode or close Steam manually first.",
                    ),
                )
                return False
            return True

        def toggle_compact_mode(self, checked):
            self.app_config["compact_mode"] = bool(checked)
            save_app_config(self.app_config)
            self.apply_compact_mode()

        def apply_compact_mode(self):
            compact = bool(self.app_config.get("compact_mode"))
            for widget in (
                getattr(self, "current_label", None),
                getattr(self, "proton_status_label", None),
                getattr(self, "sys_reasons", None),
                getattr(self, "option_detail", None),
            ):
                if widget:
                    widget.setVisible(not compact)
            if getattr(self, "protondb_badge", None):
                if compact:
                    self.protondb_badge.setVisible(False)
                elif self.current_game and not self.current_game.get("external"):
                    self.update_protondb_badge(self.cached_game_summary(self.current_game["appid"]))
            if getattr(self, "command_edit", None):
                self.command_edit.setMaximumHeight(54 if compact else 78)
            if getattr(self, "tabs", None):
                self.tabs.setTabVisible(3, not compact)
            if compact:
                for group_title, widgets in getattr(self, "option_category_widgets", {}).items():
                    widgets["header"].setChecked(False)
                    widgets["content"].setVisible(False)
                    self.app_config.setdefault("option_category_expanded", {})[group_title] = False
                self.update_category_headers()
                save_app_config(self.app_config)
            if getattr(self, "current_label", None) and self.current_game:
                self.current_label.setText(f"{self.tx('Opciones guardadas', 'Saved options')}: {short_command(self.current_game_launch_options(), 150 if compact else 220)}")

        def toggle_read_only(self, checked):
            self.app_config["read_only"] = bool(checked)
            save_app_config(self.app_config)
            self.set_action_availability()

        def set_action_availability(self):
            external = self.is_external_game()
            read_only = self.is_read_only()
            self.open_protondb_btn.setEnabled(not external)
            self.recommend_btn.setEnabled(not external)
            self.launch_btn.setEnabled(bool(self.current_game))
            self.assistant_btn.setEnabled(bool(self.current_game))
            self.compare_btn.setEnabled(bool(self.current_game))
            self.history_btn.setEnabled(bool(self.current_game))
            self.display_diag_btn.setEnabled(bool(self.current_game))
            self.proton_history_btn.setEnabled(bool(self.current_game and not external))
            self.proton_combo.setEnabled(bool(self.current_game and not external))
            self.apply_proton_btn.setEnabled(bool(self.current_game and not external and not read_only))
            self.recommend_proton_btn.setEnabled(bool(self.current_game and not external and self.proton_tools))
            self.apply_command_btn.setEnabled(bool(self.current_game and not read_only))
            self.save_btn.setEnabled(bool(self.current_game and not read_only))
            self.clear_btn.setEnabled(bool(self.current_game and not read_only))
            self.apply_system_btn.setEnabled(bool(self.current_game))
            self.save_preset_btn.setEnabled(bool(self.current_game and not read_only))
            self.update_preset_btn.setEnabled(bool(self.current_game and not read_only))
            self.delete_preset_btn.setEnabled(bool(self.current_game and not read_only))
            self.add_option_btn.setEnabled(not read_only)
            self.delete_option_btn.setEnabled(bool(self.active_custom_options() and not read_only))
            self.restore_option_btn.setEnabled(bool(self.app_config.setdefault("custom_options_trash", []) and not read_only))
            self.register_appimage_btn.setEnabled(not read_only)
            manual = bool(self.current_game and self.current_game.get("manual"))
            self.edit_game_btn.setEnabled(manual and not read_only)
            self.remove_game_btn.setEnabled(manual and not read_only)
            self.add_game_btn.setEnabled(not read_only)

        def current_game_compat_tool(self):
            if not self.current_game or self.current_game.get("external"):
                return ""
            return current_compat_tool(self.steam_config_text(), self.current_game["appid"])

        def update_proton_selector(self):
            if not self.current_game:
                return
            self.proton_combo.blockSignals(True)
            self.proton_combo.clear()
            if self.current_game.get("external"):
                proton = self.current_game.get("proton", "")
                label = Path(proton).parent.name if proton else self.tx("sin Proton", "no Proton")
                self.proton_status_label.setText(f"{self.tx('Proton externo', 'External Proton')}: {label}")
                self.proton_combo.addItem(label, proton)
                self.proton_combo.blockSignals(False)
                return
            current = self.current_game_compat_tool()
            recommended = recommended_proton_tool(self.system, self.proton_tools)
            current_label = compact_proton_label(compat_tool_display_name(current, self.proton_tools))
            rec_label = compact_proton_label(compat_tool_display_name(recommended, self.proton_tools)) if recommended else self.tx("sin recomendacion", "no recommendation")
            self.proton_status_label.setText(f"{self.tx('Proton actual', 'Current Proton')}: {current_label}\n{self.tx('Recomendada', 'Recommended')}: {rec_label}")
            self.proton_combo.addItem(self.tx("Steam por defecto", "Steam default"), "")
            if current and not any(tool["compat"] == current for tool in self.proton_tools):
                self.proton_combo.addItem(f"{self.tx('Actual no detectada', 'Current not detected')}: {current}", current)
            for tool in self.proton_tools:
                suffix = f"  - {self.tx('recomendada', 'recommended')}" if tool["compat"] == recommended else ""
                version = compact_proton_label(tool.get("version", ""))
                version = f" ({version})" if version and version != tool["name"] else ""
                self.proton_combo.addItem(f"{tool['name']}{version}{suffix}", tool["compat"])
            index = self.proton_combo.findData(current)
            self.proton_combo.setCurrentIndex(index if index >= 0 else 0)
            self.proton_combo.blockSignals(False)

        def select_recommended_proton(self):
            recommended = recommended_proton_tool(self.system, self.proton_tools)
            index = self.proton_combo.findData(recommended)
            if index >= 0:
                self.proton_combo.setCurrentIndex(index)

        def apply_selected_proton(self):
            if not self.current_game or self.current_game.get("external"):
                return
            if not self.write_guard("cambiar la version de Proton"):
                return
            selected = self.proton_combo.currentData() or ""
            current = self.current_game_compat_tool()
            if selected == current:
                QtWidgets.QMessageBox.information(
                    self,
                    self.tx("Proton sin cambios", "Proton unchanged"),
                    self.tx(
                        "La version de Proton seleccionada ya esta aplicada para este juego.",
                        "The selected Proton version is already applied for this game.",
                    ),
                )
                return
            selected_label = compat_tool_display_name(selected, self.proton_tools)
            current_label = compat_tool_display_name(current, self.proton_tools)
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Aplicar Proton", "Apply Proton"),
                self.tx(
                    f"Cambiar Proton para este juego?\n\nJuego: {self.current_game['name']}\nActual: {current_label}\nNuevo: {selected_label}\n\nSteam puede cerrarse para evitar que sobrescriba config.vdf.",
                    f"Change Proton for this game?\n\nGame: {self.current_game['name']}\nCurrent: {current_label}\nNew: {selected_label}\n\nSteam may be closed to prevent it from overwriting config.vdf.",
                ),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            reopen_steam = False
            if steam_is_running():
                if not self.allow_steam_shutdown_write("aplicar Proton"):
                    return
                close_reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Cerrar Steam para aplicar Proton", "Close Steam to apply Proton"),
                    self.tx(
                        "Steam esta abierto. Para guardar la version de Proton por juego con seguridad, Proton Pilot puede cerrar Steam y volver a abrirlo.\n\nCerrar Steam y continuar?",
                        "Steam is open. To safely save the per-game Proton version, Proton Pilot can close Steam and reopen it.\n\nClose Steam and continue?",
                    ),
                )
                if close_reply != QtWidgets.QMessageBox.Yes:
                    return
                if not close_steam():
                    QtWidgets.QMessageBox.warning(
                        self,
                        self.tx("No se pudo cerrar Steam", "Could not close Steam"),
                        self.tx("Cierra Steam manualmente y vuelve a aplicar Proton.", "Close Steam manually and apply Proton again."),
                    )
                    return
                reopen_steam = True
            self.remember_proton_history(current, "antes de cambiar Proton")
            backup = set_compat_tool(self.steam_config_path, self.current_game["appid"], selected)
            reopen_note = ""
            if reopen_steam:
                reopen_note = self.tx("\n\nSteam se ha vuelto a abrir.", "\n\nSteam has been reopened.") if open_steam(self.root) else self.tx("\n\nNo he podido volver a abrir Steam. Abre Steam manualmente.", "\n\nI could not reopen Steam. Open Steam manually.")
            self.update_proton_selector()
            QtWidgets.QMessageBox.information(
                self,
                self.tx("Proton aplicado", "Proton applied"),
                self.tx(
                    f"Proton guardado para {self.current_game['name']}:\n\n{selected_label}\n\nBackup:\n{backup}{reopen_note}",
                    f"Proton saved for {self.current_game['name']}:\n\n{selected_label}\n\nBackup:\n{backup}{reopen_note}",
                ),
            )

        def prepared_command(self):
            return self.command_edit.toPlainText().strip()

        def has_pending_command_changes(self):
            if not self.current_game:
                return False
            return not launch_commands_equivalent(self.prepared_command(), self.current_game_launch_options())

        def update_dirty_state(self):
            if not getattr(self, "dirty_label", None):
                return
            dirty = self.has_pending_command_changes()
            self.dirty_label.setProperty("dirty", "true" if dirty else "false")
            self.dirty_label.style().unpolish(self.dirty_label)
            self.dirty_label.style().polish(self.dirty_label)
            if dirty:
                self.dirty_label.setText(self.tx(
                    "Cambios pendientes: el comando preparado no coincide con lo guardado para este juego.",
                    "Pending changes: the prepared command does not match what is saved for this game.",
                ))
            else:
                self.dirty_label.setText(self.tx(
                    "Sin cambios pendientes: lo preparado coincide con lo guardado.",
                    "No pending changes: the prepared command matches what is saved.",
                ))

        def remember_launch_history(self, command, reason):
            if not self.current_game or not command:
                return
            appid = self.current_game["appid"]
            history = self.app_config.setdefault("launch_history", {}).setdefault(appid, [])
            normalized = normalize_command(command)
            if history and normalize_command(history[0].get("command", "")) == normalized:
                return
            history.insert(
                0,
                {
                    "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
                    "game": self.current_game.get("name", ""),
                    "source": "externo" if self.current_game.get("external") else "steam",
                    "reason": reason,
                    "command": command,
                },
            )
            del history[12:]

        def remember_proton_history(self, compat_tool, reason):
            if not self.current_game or self.current_game.get("external"):
                return
            appid = self.current_game["appid"]
            history = self.app_config.setdefault("proton_history", {}).setdefault(appid, [])
            if history and history[0].get("compat_tool", "") == (compat_tool or ""):
                return
            history.insert(
                0,
                {
                    "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
                    "game": self.current_game.get("name", ""),
                    "reason": reason,
                    "compat_tool": compat_tool or "",
                    "label": compat_tool_display_name(compat_tool or "", self.proton_tools),
                },
            )
            del history[12:]
            save_app_config(self.app_config)

        def diagnostic_lines(self, command):
            lines = []
            system = self.system
            selected = set(self.selected_keys())
            display = system.get("display", {})
            lines.append(f"{self.tx('Juego', 'Game')}: {self.current_game['name']}")
            lines.append(f"{self.tx('Destino', 'Target')}: {self.tx('perfil externo', 'external profile') if self.current_game.get('external') else 'Steam localconfig.vdf'}")
            if self.current_game.get("external"):
                lines.append(f"Proton: {Path(self.current_game.get('proton', '')).parent.name or self.tx('no definido', 'not set')}")
            else:
                lines.append(f"{self.tx('Proton actual', 'Current Proton')}: {compat_tool_display_name(self.current_game_compat_tool(), self.proton_tools)}")
            available = self.tx("disponible", "available")
            unavailable = self.tx("no disponible", "not available")
            lines.append(f"{self.tx('Steam abierto', 'Steam open')}: {self.tr('yes') if steam_is_running() else self.tr('no')}")
            lines.append(f"{self.tx('Modo Gaming', 'Gaming Mode')}: {self.tx('detectado', 'detected') if system.get('device', {}).get('gaming_mode') else self.tr('not_detected')}")
            lines.append(f"Gamescope: {available if system['tools'].get('gamescope') else unavailable}")
            lines.append(f"GameMode: {available if system['tools'].get('gamemoderun') else unavailable}")
            lines.append(f"MangoHud: {available if system['tools'].get('mangohud') else unavailable}")
            lines.append(f"{self.tr('status_hdr')}: {self.tx('activo', 'active') if display_hdr_enabled(display) else (display.get('hdr') or self.tr('not_detected'))}")
            lines.append(f"VRR: {(display.get('vrr') or self.tr('not_detected'))}")
            if display.get("width") and display.get("height"):
                lines.append(f"{self.tx('Monitor', 'Monitor')}: {display.get('name') or self.tx('principal', 'primary')} {display.get('width')}x{display.get('height')}@{display.get('refresh') or '?'}")
            res = self.gamescope_resolution()
            if selected & {"REALRES", "CAPVRR"}:
                lines.append(f"{self.tx('Resolucion Gamescope aplicada', 'Applied Gamescope resolution')}: {res.get('width') or '?'}x{res.get('height') or '?'}@{res.get('refresh') or '?'}")
            warnings = []
            if "HDR" in selected and not display_hdr_enabled(display):
                warnings.append(self.tx("HDR esta marcado, pero el sistema no informa HDR activo.", "HDR is checked, but the system does not report active HDR."))
            if "HDR" in selected and not system.get("gamescope_wsi"):
                warnings.append(self.tx("HDR via Gamescope necesita Gamescope WSI; no lo he detectado.", "HDR via Gamescope needs Gamescope WSI; I did not detect it."))
            if selected & {"HDR", "GAMESCOPE", "REALRES", "ADAPTIVE"} and not system["tools"].get("gamescope"):
                warnings.append(self.tx("Hay opciones Gamescope marcadas, pero gamescope no esta disponible.", "Gamescope options are checked, but gamescope is not available."))
            if selected & {"REALRES", "CAPVRR"} and not int(res.get("width") or 0):
                warnings.append(self.tx("Resolucion real/VRR cap estan marcados, pero no hay resolucion aplicada.", "Native resolution/VRR cap are checked, but no resolution is applied."))
            if "GAMEMODE" in selected and not system["tools"].get("gamemoderun"):
                warnings.append(self.tx("GameMode esta marcado, pero gamemoderun no esta disponible.", "GameMode is checked, but gamemoderun is not available."))
            if {"CAPVRR", "MANGOHUD"} & selected and not system["tools"].get("mangohud"):
                warnings.append(self.tx("MangoHud/VRR cap requieren mangohud, pero no esta disponible.", "MangoHud/VRR cap require mangohud, but it is not available."))
            if "NVIDIA" in selected and system.get("gpu") != "nvidia":
                warnings.append(self.tx("NVAPI/DLSS esta marcado en una GPU no NVIDIA.", "NVAPI/DLSS is checked on a non-NVIDIA GPU."))
            if "FSR4" in selected and system.get("gpu") != "amd":
                warnings.append(self.tx("FSR4 upgrade suele tener sentido principalmente en AMD compatible.", "FSR4 upgrade usually makes sense mainly on compatible AMD hardware."))
            if "CAPVRR" in selected and not display_vrr_available(display):
                warnings.append(self.tx("VRR cap esta marcado, pero VRR no aparece disponible.", "VRR cap is checked, but VRR does not appear available."))
            if "%command%" not in command:
                warnings.append(self.tx("El comando no contiene %command%; Steam podria no lanzar el juego como esperas.", "The command does not contain %command%; Steam may not launch the game as expected."))
            if warnings:
                lines.extend(["", self.tx("Avisos:", "Warnings:")])
                lines.extend(f"- {warning}" for warning in warnings)
            else:
                lines.extend(["", self.tx("Diagnostico: no veo avisos importantes.", "Diagnostic: I do not see important warnings.")])
            return lines

        def diagnostic_text(self, command):
            return "\n".join(self.diagnostic_lines(command))

        def cached_game_summary(self, appid):
            item = self.app_config.get("protondb_cache", {}).get(str(appid), {})
            summary = item.get("summary", {})
            return summary if isinstance(summary, dict) else {}

        def game_label(self, game, summary=None):
            summary = summary or self.cached_game_summary(game["appid"])
            rating = protondb_tier_label(summary)
            label = f"{game['name']}  ({game['appid']})"
            if rating:
                label += f"  [{rating}]"
            if game.get("manual"):
                label += "  - manual"
            return label

        def style_game_item(self, item, summary):
            rating = protondb_tier(summary)
            if not rating:
                return
            bg, fg = protondb_tier_color(rating)
            item.setBackground(QtGui.QColor(bg))
            item.setForeground(QtGui.QColor(fg))
            item.setToolTip(
                f"ProtonDB: {protondb_tier_label(summary)}"
                + (f" - {summary.get('total')} reportes" if summary.get("total") is not None else "")
            )

        def update_current_item_rating(self, summary):
            item = self.game_list.currentItem()
            if not item:
                return
            game = item.data(QtCore.Qt.UserRole)
            item.setText(self.game_label(game, summary))
            self.style_game_item(item, summary)

        def update_protondb_badge(self, summary):
            rating = protondb_tier_label(summary)
            if not rating:
                self.protondb_badge.setVisible(False)
                return
            tier = protondb_tier(summary)
            bg, fg = protondb_tier_color(tier)
            total = summary.get("total")
            confidence = summary.get("confidence")
            best = summary.get("bestReportedTier")
            details = []
            if total is not None:
                details.append(f"{total} {self.tx('reportes', 'reports')}")
            if confidence:
                details.append(f"{self.tx('confianza', 'confidence')} {confidence}")
            if best and str(best).lower() != tier:
                details.append(f"{self.tx('mejor', 'best')} {str(best).upper()}")
            cache_age = protondb_cache_age_label(self.app_config, self.current_game["appid"]) if self.current_game else ""
            if cache_age:
                if self.language() == "en":
                    cache_age = (
                        cache_age.replace("cache hace menos de 1 h", "cache less than 1 h old")
                        .replace("cache hace", "cache")
                        .replace(" dias", " days old")
                    )
                    if cache_age.startswith("cache ") and cache_age.endswith(" h"):
                        cache_age = cache_age + " old"
                details.append(cache_age)
            self.protondb_badge.setText("ProtonDB  " + rating + (f"  ·  {' · '.join(details)}" if details else ""))
            self.protondb_badge.setStyleSheet(f"background: {bg}; color: {fg}; border: 1px solid {fg};")
            self.protondb_badge.setVisible(True)

        def populate_games(self, preferred_appid=None):
            self.games = merged_games(self.root, self.app_config)
            self.game_list.blockSignals(True)
            self.game_list.clear()
            preferred_row = 0
            for row, game in enumerate(self.games):
                summary = self.cached_game_summary(game["appid"])
                label = self.game_label(game, summary)
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, game)
                icon_path = game_icon(self.root, game)
                if icon_path:
                    item.setIcon(QtGui.QIcon(str(icon_path)))
                self.style_game_item(item, summary)
                self.game_list.addItem(item)
                if preferred_appid and game["appid"] == preferred_appid:
                    preferred_row = row
            self.game_list.blockSignals(False)
            if self.game_list.count():
                self.game_list.setCurrentRow(preferred_row)

        def select_game(self, item):
            if not item:
                return
            self.current_game = item.data(QtCore.Qt.UserRole)
            ensure_system_shared_preset(self.app_config, self.system)
            ensure_game_builtin_presets(self.app_config, self.current_game["appid"])
            ensure_display_preset(self.app_config, self.current_game["appid"], self.system.get("display", {}))
            save_app_config(self.app_config)
            current = self.current_game_launch_options()
            source = self.tx("Externo", "External") if self.current_game.get("external") else "Steam"
            summary = {}
            if not self.current_game.get("external"):
                summary = protondb_cached_summary(self.app_config, self.current_game["appid"])
                save_app_config(self.app_config)
                self.update_current_item_rating(summary)
                self.update_protondb_badge(summary)
            else:
                self.update_protondb_badge({})
            rating = protondb_tier_label(summary)
            self.current_title.setText(f"{self.current_game['name']} ({self.current_game['appid']}) - {source}")
            self.current_label.setText(f"{self.tx('Opciones guardadas', 'Saved options')}: {short_command(current, 150 if self.app_config.get('compact_mode') else 220)}")
            self.rebuild_option_checkboxes()
            self.set_action_availability()
            self.update_proton_selector()
            flags = detect_flags(current)
            custom = self.app_config.setdefault("custom", {}).get(self.current_game["appid"], {})
            saved_side_effects = set(custom.get("side_effect_options", []))
            for key, cb in self.checks.items():
                detected = custom_option_matches_command(self.option_from_key(key), current) if is_custom_option_key(key) else flags.get(key, False)
                cb.blockSignals(True)
                cb.setChecked(detected or key in saved_side_effects)
                cb.setProperty("active", "true" if detected else "false")
                cb.style().unpolish(cb)
                cb.style().polish(cb)
                cb.blockSignals(False)
            self.custom_pre.blockSignals(True)
            self.custom_post.blockSignals(True)
            self.custom_pre.setText(custom.get("pre", ""))
            self.custom_post.setText(custom.get("post", ""))
            self.custom_pre.blockSignals(False)
            self.custom_post.blockSignals(False)
            saved_res = custom.get("gamescope_res", {})
            display_res = display_resolution_or_empty(self.system.get("display", {}))
            res = detect_gamescope_resolution(current) if flags.get("REALRES") else saved_res
            if not int((res or {}).get("width") or 0) or not int((res or {}).get("height") or 0):
                res = display_res
            self.active_gamescope_res = display_resolution_or_empty(res)
            self.set_resolution_fields(res)
            self.refresh_presets()
            matched_ref = self.select_matching_preset(current)
            _, _, matched_preset = self.preset_from_ref(matched_ref)
            if matched_preset and "options" not in matched_preset:
                self.command_edit.setPlainText(current)
            else:
                self.update_command()
            self.update_category_headers()
            self.update_dirty_state()
            self.apply_compact_mode()

        def add_manual_game(self):
            if not self.write_guard("anadir juegos"):
                return
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tx("Añadir juego", "Add game"))
            dialog.resize(620, 260)
            outer = QtWidgets.QVBoxLayout(dialog)
            tabs = QtWidgets.QTabWidget()
            outer.addWidget(tabs)

            steam_tab = QtWidgets.QWidget()
            steam_layout = QtWidgets.QFormLayout(steam_tab)
            name_edit = QtWidgets.QLineEdit()
            appid_edit = QtWidgets.QLineEdit()
            appid_edit.setPlaceholderText("Ej: 1172710")
            steam_layout.addRow(self.tx("Nombre:", "Name:"), name_edit)
            steam_layout.addRow("AppID Steam:", appid_edit)
            tabs.addTab(steam_tab, "Steam AppID")

            external_tab = QtWidgets.QWidget()
            external_layout = QtWidgets.QFormLayout(external_tab)
            external_name = QtWidgets.QLineEdit()
            exe_row = QtWidgets.QHBoxLayout()
            exe_edit = QtWidgets.QLineEdit()
            exe_btn = QtWidgets.QPushButton(self.tx("Buscar ejecutable", "Browse executable"))
            exe_row.addWidget(exe_edit, 1)
            exe_row.addWidget(exe_btn)
            proton_combo = QtWidgets.QComboBox()
            tools = proton_tools(self.root)
            for tool in tools:
                proton_combo.addItem(tool["name"], tool["path"])
            if not tools:
                proton_combo.addItem(self.tx("No encuentro Proton instalado", "No installed Proton found"), "")
            proton_row = QtWidgets.QHBoxLayout()
            proton_btn = QtWidgets.QPushButton(self.tx("Buscar Proton", "Browse Proton"))
            proton_row.addWidget(proton_combo, 1)
            proton_row.addWidget(proton_btn)
            add_to_steam = QtWidgets.QCheckBox(self.tx("Añadir tambien a la biblioteca de Steam", "Also add to the Steam library"))
            add_to_steam.setToolTip(self.tx(
                "Crea un acceso directo en shortcuts.vdf. Steam debe reiniciarse para verlo.",
                "Creates a shortcut in shortcuts.vdf. Steam must be restarted to see it.",
            ))
            external_layout.addRow(self.tx("Nombre:", "Name:"), external_name)
            external_layout.addRow(self.tx("Ejecutable:", "Executable:"), exe_row)
            external_layout.addRow("Proton:", proton_row)
            external_layout.addRow("", add_to_steam)
            tabs.addTab(external_tab, self.tx("Ejecutable Proton", "Proton executable"))

            def browse_exe():
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    dialog,
                    self.tx("Selecciona ejecutable", "Select executable"),
                    str(HOME),
                    self.tx("Ejecutables (*.exe *.msi);;Todos los archivos (*)", "Executables (*.exe *.msi);;All files (*)"),
                )
                if path:
                    exe_edit.setText(path)
                    if not external_name.text().strip():
                        external_name.setText(Path(path).stem)

            exe_btn.clicked.connect(browse_exe)

            def browse_proton():
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    dialog,
                    self.tx("Selecciona el binario proton", "Select the proton binary"),
                    str(HOME),
                    self.tx("Proton (proton);;Todos los archivos (*)", "Proton (proton);;All files (*)"),
                )
                if not path:
                    folder = QtWidgets.QFileDialog.getExistingDirectory(dialog, self.tx("O selecciona una carpeta de Proton", "Or select a Proton folder"), str(HOME))
                    path = str(Path(folder) / "proton") if folder else ""
                if not path:
                    return
                proton_path = Path(path)
                if proton_path.is_dir():
                    proton_path = proton_path / "proton"
                if not proton_path.exists():
                    QtWidgets.QMessageBox.warning(dialog, self.tx("Proton no encontrado", "Proton not found"), self.tx("La ruta seleccionada no contiene un binario proton.", "The selected path does not contain a proton binary."))
                    return
                label = f"{self.tx('Personalizado', 'Custom')}: {proton_path.parent.name}"
                proton_combo.addItem(label, str(proton_path))
                proton_combo.setCurrentIndex(proton_combo.count() - 1)

            proton_btn.clicked.connect(browse_proton)
            buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            outer.addWidget(buttons)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return
            if tabs.currentIndex() == 0:
                name = name_edit.text().strip()
                appid = appid_edit.text().strip()
                if not name or not appid:
                    QtWidgets.QMessageBox.warning(self, self.tx("Faltan datos", "Missing data"), self.tx("Necesito nombre y AppID para añadir el juego.", "I need a name and AppID to add the game."))
                    return
                if not re.fullmatch(r"\d+", appid):
                    QtWidgets.QMessageBox.warning(self, self.tx("AppID no valido", "Invalid AppID"), self.tx("El AppID de Steam debe ser numerico.", "The Steam AppID must be numeric."))
                    return
                manual_games = self.app_config.setdefault("manual_games", [])
                for game in self.games:
                    if game["appid"] == appid:
                        QtWidgets.QMessageBox.information(self, self.tx("Ya existe", "Already exists"), self.tx("Ese AppID ya esta en la lista.", "That AppID is already in the list."))
                        self.populate_games(appid)
                        return
                manual_games.append({"appid": appid, "name": name})
                save_app_config(self.app_config)
                self.populate_games(appid)
                return

            name = external_name.text().strip()
            exe = exe_edit.text().strip()
            proton = proton_combo.currentData() or ""
            if not name or not exe or not proton:
                QtWidgets.QMessageBox.warning(self, self.tx("Faltan datos", "Missing data"), self.tx("Necesito nombre, ejecutable y una version de Proton.", "I need a name, executable and Proton version."))
                return
            if not Path(exe).exists():
                QtWidgets.QMessageBox.warning(self, self.tx("Ejecutable no encontrado", "Executable not found"), self.tx("La ruta seleccionada no existe.", "The selected path does not exist."))
                return
            game_id = external_game_id(name, exe)
            for game in self.games:
                if game["appid"] == game_id:
                    QtWidgets.QMessageBox.information(self, self.tx("Ya existe", "Already exists"), self.tx("Ese ejecutable ya esta en la lista.", "That executable is already in the list."))
                    self.populate_games(game_id)
                    return
            prefix = str(APP_CONFIG_DIR / "compatdata" / game_id)
            external_payload = {"id": game_id, "name": name, "exe": exe, "proton": proton, "prefix": prefix}
            shortcut_note = ""
            if add_to_steam.isChecked():
                reopen_steam = False
                if steam_is_running():
                    if not self.allow_steam_shutdown_write("anadir el acceso directo"):
                        return
                    reply = QtWidgets.QMessageBox.question(
                        self,
                        self.tx("Cerrar Steam para anadir acceso directo", "Close Steam to add shortcut"),
                        self.tx(
                            "Steam esta abierto. Para anadir el juego externo a la biblioteca sin que Steam sobrescriba shortcuts.vdf, Proton Pilot puede cerrarlo ahora y volver a abrirlo despues.\n\nCerrar Steam y continuar?",
                            "Steam is open. To add the external game to the library without Steam overwriting shortcuts.vdf, Proton Pilot can close Steam and reopen it afterwards.\n\nClose Steam and continue?",
                        ),
                    )
                    if reply == QtWidgets.QMessageBox.Yes:
                        if not close_steam():
                            QtWidgets.QMessageBox.warning(
                                self,
                                self.tx("No se pudo cerrar Steam", "Could not close Steam"),
                                self.tx(
                                    "No he podido cerrar Steam de forma fiable. Anado el perfil local, pero no el acceso directo de Steam.",
                                    "I could not close Steam reliably. I will add the local profile, but not the Steam shortcut.",
                                ),
                            )
                        else:
                            reopen_steam = True
                    else:
                        QtWidgets.QMessageBox.information(
                            self,
                            self.tx("Acceso directo omitido", "Shortcut skipped"),
                            self.tx(
                                "Anado el perfil local, pero no escribo shortcuts.vdf mientras Steam esta abierto.",
                                "I will add the local profile, but I will not write shortcuts.vdf while Steam is open.",
                            ),
                        )
                if not steam_is_running():
                    try:
                        result = add_steam_shortcut(self.root, name, exe, "")
                        external_payload["steam_shortcut"] = True
                        external_payload["steam_shortcut_appid"] = result.get("appid", "")
                        shortcut_note = self.tx(f"\n\nAcceso directo anadido a Steam:\n{result['path']}", f"\n\nSteam shortcut added:\n{result['path']}")
                    except Exception as exc:
                        shortcut_note = self.tx(f"\n\nNo he podido anadirlo a Steam: {exc}", f"\n\nCould not add it to Steam: {exc}")
                if reopen_steam:
                    if open_steam(self.root):
                        shortcut_note += self.tx("\nSteam se ha vuelto a abrir.", "\nSteam has been reopened.")
                    else:
                        shortcut_note += self.tx("\nNo he podido volver a abrir Steam; abrelo manualmente.", "\nI could not reopen Steam; open it manually.")
            self.app_config.setdefault("external_games", []).append(external_payload)
            save_app_config(self.app_config)
            self.populate_games(game_id)
            if shortcut_note:
                QtWidgets.QMessageBox.information(
                    self,
                    self.tx("Juego externo anadido", "External game added"),
                    self.tx(f"Perfil anadido a Proton Pilot.{shortcut_note}", f"Profile added to Proton Pilot.{shortcut_note}"),
                )

        def edit_manual_game(self):
            if not self.write_guard("editar juegos manuales"):
                return
            if not self.current_game or not self.current_game.get("manual"):
                return
            if self.current_game.get("external"):
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle(self.tx("Editar juego externo", "Edit external game"))
                layout = QtWidgets.QFormLayout(dialog)
                name_edit = QtWidgets.QLineEdit(self.current_game.get("name", ""))
                exe_row = QtWidgets.QHBoxLayout()
                exe_edit = QtWidgets.QLineEdit(self.current_game.get("exe", ""))
                exe_btn = QtWidgets.QPushButton(self.tx("Buscar", "Browse"))
                exe_row.addWidget(exe_edit, 1)
                exe_row.addWidget(exe_btn)
                proton_combo = NoWheelComboBox()
                current_proton = self.current_game.get("proton", "")
                added_current = False
                for tool in proton_tools(self.root):
                    proton_combo.addItem(tool["name"], tool["path"])
                    if tool["path"] == current_proton:
                        proton_combo.setCurrentIndex(proton_combo.count() - 1)
                        added_current = True
                if current_proton and not added_current:
                    proton_combo.addItem(f"{self.tx('Actual', 'Current')}: {Path(current_proton).parent.name}", current_proton)
                    proton_combo.setCurrentIndex(proton_combo.count() - 1)
                proton_btn = QtWidgets.QPushButton(self.tx("Buscar Proton", "Browse Proton"))
                proton_row = QtWidgets.QHBoxLayout()
                proton_row.addWidget(proton_combo, 1)
                proton_row.addWidget(proton_btn)
                layout.addRow(self.tx("Nombre:", "Name:"), name_edit)
                layout.addRow(self.tx("Ejecutable:", "Executable:"), exe_row)
                layout.addRow("Proton:", proton_row)

                def browse_exe():
                    path, _ = QtWidgets.QFileDialog.getOpenFileName(
                        dialog,
                        self.tx("Selecciona ejecutable", "Select executable"),
                        str(Path(exe_edit.text()).parent if exe_edit.text() else HOME),
                        self.tx("Ejecutables (*.exe *.msi);;Todos los archivos (*)", "Executables (*.exe *.msi);;All files (*)"),
                    )
                    if path:
                        exe_edit.setText(path)

                def browse_proton():
                    path, _ = QtWidgets.QFileDialog.getOpenFileName(dialog, self.tx("Selecciona el binario proton", "Select the proton binary"), str(HOME), self.tx("Proton (proton);;Todos los archivos (*)", "Proton (proton);;All files (*)"))
                    if not path:
                        folder = QtWidgets.QFileDialog.getExistingDirectory(dialog, self.tx("O selecciona una carpeta de Proton", "Or select a Proton folder"), str(HOME))
                        path = str(Path(folder) / "proton") if folder else ""
                    if not path:
                        return
                    proton_path = Path(path)
                    if proton_path.is_dir():
                        proton_path = proton_path / "proton"
                    if not proton_path.exists():
                        QtWidgets.QMessageBox.warning(dialog, self.tx("Proton no encontrado", "Proton not found"), self.tx("La ruta seleccionada no contiene un binario proton.", "The selected path does not contain a proton binary."))
                        return
                    proton_combo.addItem(f"{self.tx('Personalizado', 'Custom')}: {proton_path.parent.name}", str(proton_path))
                    proton_combo.setCurrentIndex(proton_combo.count() - 1)

                exe_btn.clicked.connect(browse_exe)
                proton_btn.clicked.connect(browse_proton)
                buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
                layout.addRow(buttons)
                buttons.accepted.connect(dialog.accept)
                buttons.rejected.connect(dialog.reject)
                if dialog.exec() != QtWidgets.QDialog.Accepted:
                    return
                name = name_edit.text().strip()
                exe = exe_edit.text().strip()
                proton = proton_combo.currentData() or ""
                if not name or not exe or not proton:
                    QtWidgets.QMessageBox.warning(self, self.tx("Datos no validos", "Invalid data"), self.tx("Necesito nombre, ejecutable y Proton.", "I need a name, executable and Proton."))
                    return
                if not Path(exe).exists():
                    QtWidgets.QMessageBox.warning(self, self.tx("Ejecutable no encontrado", "Executable not found"), self.tx("La ruta seleccionada no existe.", "The selected path does not exist."))
                    return
                for entry in self.app_config.setdefault("external_games", []):
                    if entry.get("id") == self.current_game["appid"]:
                        entry["name"] = name
                        entry["exe"] = exe
                        entry["proton"] = proton
                        break
                save_app_config(self.app_config)
                self.populate_games(self.current_game["appid"])
                return

            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tx("Editar juego manual", "Edit manual game"))
            layout = QtWidgets.QFormLayout(dialog)
            name_edit = QtWidgets.QLineEdit(self.current_game.get("name", ""))
            appid_edit = QtWidgets.QLineEdit(self.current_game.get("appid", ""))
            layout.addRow(self.tx("Nombre:", "Name:"), name_edit)
            layout.addRow("AppID Steam:", appid_edit)
            buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            layout.addRow(buttons)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return
            name = name_edit.text().strip()
            appid = appid_edit.text().strip()
            if not name or not re.fullmatch(r"\d+", appid):
                QtWidgets.QMessageBox.warning(self, self.tx("Datos no validos", "Invalid data"), self.tx("Necesito un nombre y un AppID numerico.", "I need a name and a numeric AppID."))
                return
            old_appid = self.current_game["appid"]
            for entry in self.app_config.setdefault("manual_games", []):
                if str(entry.get("appid")) == old_appid:
                    entry["name"] = name
                    entry["appid"] = appid
                    break
            save_app_config(self.app_config)
            self.populate_games(appid)

        def remove_manual_game(self):
            if not self.write_guard("quitar juegos manuales"):
                return
            if not self.current_game or not self.current_game.get("manual"):
                return
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Quitar juego manual", "Remove manual game"),
                self.tx(
                    f"Quitar este juego de Proton Pilot?\n\n{self.current_game['name']}\n\nNo borra archivos del juego ni desinstala nada.",
                    f"Remove this game from Proton Pilot?\n\n{self.current_game['name']}\n\nThis does not delete game files or uninstall anything.",
                ),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            appid = self.current_game["appid"]
            if self.current_game.get("external"):
                self.app_config["external_games"] = [
                    entry for entry in self.app_config.setdefault("external_games", []) if entry.get("id") != appid
                ]
                self.app_config.setdefault("external_launch_options", {}).pop(appid, None)
            else:
                self.app_config["manual_games"] = [
                    entry for entry in self.app_config.setdefault("manual_games", []) if str(entry.get("appid")) != appid
                ]
            self.app_config.setdefault("custom", {}).pop(appid, None)
            self.app_config.setdefault("presets", {}).pop(appid, None)
            save_app_config(self.app_config)
            self.populate_games()

        def active_custom_options(self):
            return [
                option for option in self.app_config.setdefault("custom_options", [])
                if option.get("id") and not option.get("deleted")
            ]

        def option_from_key(self, key):
            if not is_custom_option_key(key):
                return {}
            for option in self.active_custom_options():
                if custom_option_key(option) == key:
                    return option
            return {}

        def option_meta(self, key):
            if key in OPTION_INFO:
                meta = dict(OPTION_INFO[key])
                meta["label"] = self.option_label(key)
                meta["description"] = self.option_description(key)
                return meta
            for option in self.active_custom_options():
                if custom_option_key(option) == key:
                    label = option.get("label", self.tx("Opcion manual", "Custom option"))
                    tokens = []
                    if option.get("pre"):
                        tokens.append(f"{self.tx('antes', 'before')}: {option.get('pre')}")
                    if option.get("gamescope"):
                        tokens.append(f"gamescope: {option.get('gamescope')}")
                    if option.get("post"):
                        tokens.append(f"{self.tx('despues', 'after')}: {option.get('post')}")
                    return {
                        "label": label,
                        "description": option.get("description", ""),
                        "tokens": " · ".join(tokens) or self.tx("(sin parametros)", "(no parameters)"),
                        "recommended": False,
                        "custom": True,
                        "important": option.get("style") == "important",
                        "caution": option.get("style") == "caution",
                    }
            return {
                "label": key,
                "description": self.tx(
                    "Opcion no encontrada. Puede haber sido borrada de la lista manual.",
                    "Option not found. It may have been deleted from the custom list.",
                ),
                "tokens": "",
                "recommended": False,
                "custom": True,
            }

        def clear_layout(self, layout):
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                child_layout = item.layout()
                if widget:
                    widget.deleteLater()
                elif child_layout:
                    self.clear_layout(child_layout)

        def rebuild_option_checkboxes(self, preserve_checked=None):
            if preserve_checked is None:
                preserve_checked = set(self.selected_keys()) if getattr(self, "checks", None) else set()
            else:
                preserve_checked = set(preserve_checked)
            self.clear_layout(self.options_container_layout)
            self.checks = {}
            self.option_group_boxes = []
            self.option_category_widgets = {}
            self.option_to_group = {}
            custom_by_group = {title: [] for title in OPTION_GROUP_TITLES}
            for option in self.active_custom_options():
                custom_by_group.setdefault(normalize_option_category(option.get("category")), []).append(option)

            for group_index, (group_title, group_keys) in enumerate(OPTION_GROUPS):
                section = QtWidgets.QFrame()
                section.setObjectName("optionSection")
                section_layout = QtWidgets.QVBoxLayout(section)
                section_layout.setContentsMargins(0, 0, 0, 0)
                section_layout.setSpacing(0)
                header = QtWidgets.QPushButton()
                header.setObjectName("optionSectionHeader")
                header.setCheckable(True)
                content = QtWidgets.QWidget()
                content_layout = QtWidgets.QVBoxLayout(content)
                content_layout.setContentsMargins(8, 8, 8, 8)
                content_layout.setSpacing(5)

                for key in group_keys:
                    self.add_option_checkbox(content_layout, key, key in preserve_checked, group_title)
                for option in sorted(custom_by_group.get(group_title, []), key=lambda item: item.get("label", "").lower()):
                    key = custom_option_key(option)
                    self.add_option_checkbox(content_layout, key, key in preserve_checked, group_title)

                section_layout.addWidget(header)
                section_layout.addWidget(content)
                expanded_config = self.app_config.setdefault("option_category_expanded", {})
                if group_title in expanded_config:
                    expanded = bool(expanded_config[group_title])
                elif self.app_config.get("compact_mode"):
                    expanded = False
                else:
                    expanded = group_index < 2
                header.setChecked(expanded)
                content.setVisible(expanded)
                header.clicked.connect(lambda checked=False, g=group_title: self.toggle_option_category(g))
                self.option_category_widgets[group_title] = {"section": section, "header": header, "content": content}
                self.option_group_boxes.append(section)
                self.options_container_layout.addWidget(section)
            self.options_container_layout.addStretch(1)
            self.update_category_headers()

        def add_option_checkbox(self, layout, key, checked=False, group_title=""):
            meta = self.option_meta(key)
            label = self.option_label(key)
            recommended = meta.get("recommended", False)
            important = meta.get("important", False)
            caution = meta.get("caution", False)
            system_recommended = key in self.system_recommended
            suffix = ""
            if meta.get("custom"):
                suffix = f"  - {self.tr('manual')}"
            elif system_recommended and caution:
                suffix = f"  - {self.tr('system_recommended_suffix')} / {self.tr('try_suffix')}"
            elif system_recommended:
                suffix = f"  - {self.tr('system_recommended_suffix')}"
            elif recommended:
                suffix = f"  - {self.tr('recommended_suffix')}"
            elif caution:
                suffix = f"  - {self.tr('try_suffix')}"
            elif important:
                suffix = f"  - {self.tr('important_suffix')}"
            cb = QtWidgets.QCheckBox(label + suffix)
            cb.setObjectName("launchOption")
            cb.setToolTip(f"{meta.get('description', '')}\n\n{self.tx('Anade', 'Adds')}: {meta.get('tokens', '')}".strip())
            cb.setProperty("recommended", "true" if recommended else "false")
            cb.setProperty("systemRecommended", "true" if system_recommended else "false")
            cb.setProperty("important", "true" if important else "false")
            cb.setProperty("caution", "true" if caution else "false")
            cb.setProperty("optionKey", key)
            cb.setChecked(checked)
            cb.installEventFilter(self)
            cb.stateChanged.connect(self.update_command)
            cb.clicked.connect(lambda checked=False, k=key: self.show_option_detail(k))
            self.checks[key] = cb
            if group_title:
                self.option_to_group[key] = group_title
            layout.addWidget(cb)

        def toggle_option_category(self, group_title):
            item = self.option_category_widgets.get(group_title)
            if not item:
                return
            expanded = item["header"].isChecked()
            item["content"].setVisible(expanded)
            self.app_config.setdefault("option_category_expanded", {})[group_title] = bool(expanded)
            save_app_config(self.app_config)
            self.update_category_headers()

        def update_category_headers(self):
            if not getattr(self, "option_category_widgets", None):
                return
            selected = set(self.selected_keys())
            for group_title, widgets in self.option_category_widgets.items():
                keys = [key for key, group in self.option_to_group.items() if group == group_title]
                total = len(keys)
                active = sum(1 for key in keys if key in selected)
                recommended = sum(1 for key in keys if key in self.system_recommended)
                manual = sum(1 for key in keys if is_custom_option_key(key))
                expanded = widgets["header"].isChecked()
                arrow = "▾" if expanded else "▸"
                bits = [f"{active} {self.tr('active')} / {total} {self.tr('options')}"]
                if recommended:
                    bits.append(f"{recommended} {self.tr('recommended')}")
                if manual:
                    bits.append(f"{manual} {self.tr('manual')}")
                widgets["header"].setText(f"{arrow} {self.category_label(group_title)} · " + " · ".join(bits))
                widgets["header"].setToolTip(self.tr("collapse") if expanded else self.tr("expand"))

        def custom_option_dialog(self):
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tx("Añadir opcion manual", "Add custom option"))
            dialog.resize(760, 520)
            layout = QtWidgets.QVBoxLayout(dialog)
            form = QtWidgets.QFormLayout()
            layout.addLayout(form)
            name_edit = QtWidgets.QLineEdit()
            name_edit.setPlaceholderText(self.tx("Ej: Proton log, RADV RT, Flag experimental...", "E.g. Proton log, RADV RT, experimental flag..."))
            category_combo = NoWheelComboBox()
            for title in OPTION_GROUP_TITLES:
                category_combo.addItem(self.category_label(title), title)
            style_combo = NoWheelComboBox()
            style_combo.addItem(self.tx("Normal", "Normal"), "normal")
            style_combo.addItem(self.tx("Importante / amarillo", "Important / yellow"), "important")
            style_combo.addItem(self.tx("Experimental / rojo", "Experimental / red"), "caution")
            description = QtWidgets.QPlainTextEdit()
            description.setPlaceholderText(self.tx("Que hace, cuando usarla y riesgos conocidos.", "What it does, when to use it and known risks."))
            description.setMaximumHeight(90)
            pre_edit = QtWidgets.QLineEdit()
            pre_edit.setPlaceholderText(self.tx("Antes de %command%, ej: PROTON_LOG=1 RADV_PERFTEST=rt", "Before %command%, e.g. PROTON_LOG=1 RADV_PERFTEST=rt"))
            gamescope_edit = QtWidgets.QLineEdit()
            gamescope_edit.setPlaceholderText(self.tx("Argumentos de gamescope, ej: --expose-wayland -e", "Gamescope arguments, e.g. --expose-wayland -e"))
            post_edit = QtWidgets.QLineEdit()
            post_edit.setPlaceholderText(self.tx("Despues de %command%, ej: -dx12 -NoLauncher", "After %command%, e.g. -dx12 -NoLauncher"))
            form.addRow(self.tx("Nombre:", "Name:"), name_edit)
            form.addRow(self.tx("Categoria:", "Category:"), category_combo)
            form.addRow(self.tx("Color:", "Color:"), style_combo)
            form.addRow(self.tx("Descripcion:", "Description:"), description)
            form.addRow(self.tx("Antes:", "Before:"), pre_edit)
            form.addRow("Gamescope:", gamescope_edit)
            form.addRow(self.tx("Despues:", "After:"), post_edit)
            hint = QtWidgets.QLabel(
                self.tx(
                    "Rellena al menos uno de los campos Antes, Gamescope o Despues. "
                    "Los argumentos Gamescope activan el contenedor Gamescope si no estaba activo.",
                    "Fill at least one of Before, Gamescope or After. "
                    "Gamescope arguments enable the Gamescope container if it was not already enabled.",
                )
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)
            buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            layout.addWidget(buttons)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return None
            label = name_edit.text().strip()
            pre = pre_edit.text().strip()
            gamescope = gamescope_edit.text().strip()
            post = post_edit.text().strip()
            if not label:
                QtWidgets.QMessageBox.warning(self, self.tx("Falta nombre", "Missing name"), self.tx("Necesito un nombre para la opcion manual.", "I need a name for the custom option."))
                return None
            if not (pre or gamescope or post):
                QtWidgets.QMessageBox.warning(self, self.tx("Faltan parametros", "Missing parameters"), self.tx("Rellena Antes, Gamescope o Despues.", "Fill Before, Gamescope or After."))
                return None
            stamp = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
            return {
                "id": f"{slugify_option_label(label)}-{stamp}",
                "label": label,
                "category": normalize_option_category(category_combo.currentData()),
                "style": style_combo.currentData(),
                "description": description.toPlainText().strip(),
                "pre": pre,
                "gamescope": gamescope,
                "post": post,
                "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
            }

        def add_custom_option(self):
            if not self.write_guard("anadir opciones manuales"):
                return
            option = self.custom_option_dialog()
            if not option:
                return
            key = custom_option_key(option)
            selected = set(self.selected_keys())
            selected.add(key)
            self.app_config.setdefault("custom_options", []).append(option)
            save_app_config(self.app_config)
            self.rebuild_option_checkboxes(selected)
            self.set_action_availability()
            self.show_option_detail(key)
            self.update_command()

        def choose_custom_option(self, title, options):
            if not options:
                QtWidgets.QMessageBox.information(self, title, self.tx("No hay opciones manuales en esta lista.", "There are no custom options in this list."))
                return None
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(title)
            dialog.resize(620, 420)
            layout = QtWidgets.QVBoxLayout(dialog)
            list_widget = QtWidgets.QListWidget()
            for option in options:
                item = QtWidgets.QListWidgetItem(f"{option.get('label', 'Opcion')}  ·  {option.get('category', '')}")
                item.setData(QtCore.Qt.UserRole, option)
                list_widget.addItem(item)
            layout.addWidget(list_widget, 1)
            preview = QtWidgets.QPlainTextEdit()
            preview.setReadOnly(True)
            layout.addWidget(preview, 1)
            buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            layout.addWidget(buttons)

            def update_preview(item):
                option = item.data(QtCore.Qt.UserRole) if item else {}
                preview.setPlainText(
                    f"{option.get('label', '')}\n\n"
                    f"{option.get('description', '')}\n\n"
                    f"{self.tx('Antes', 'Before')}: {option.get('pre', '')}\n"
                    f"Gamescope: {option.get('gamescope', '')}\n"
                    f"{self.tx('Despues', 'After')}: {option.get('post', '')}"
                )

            list_widget.currentItemChanged.connect(update_preview)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            if list_widget.count():
                list_widget.setCurrentRow(0)
            if dialog.exec() != QtWidgets.QDialog.Accepted or not list_widget.currentItem():
                return None
            return list_widget.currentItem().data(QtCore.Qt.UserRole)

        def delete_custom_option(self):
            if not self.write_guard("borrar opciones manuales"):
                return
            option = self.choose_custom_option(self.tx("Borrar opcion manual", "Delete custom option"), self.active_custom_options())
            if not option:
                return
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Borrar opcion manual", "Delete custom option"),
                self.tx(
                    f"Mover esta opcion a la papelera?\n\n{option.get('label')}\n\n"
                    "Los presets que la usen no podran reconstruir ese parametro hasta que la restaures.",
                    f"Move this option to the trash?\n\n{option.get('label')}\n\n"
                    "Presets that use it will not be able to rebuild that parameter until you restore it.",
                ),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            key = custom_option_key(option)
            selected = set(self.selected_keys())
            selected.discard(key)
            self.app_config["custom_options"] = [
                item for item in self.app_config.setdefault("custom_options", []) if item.get("id") != option.get("id")
            ]
            option = dict(option)
            option["deleted_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            self.app_config.setdefault("custom_options_trash", []).insert(0, option)
            save_app_config(self.app_config)
            self.rebuild_option_checkboxes(selected)
            self.set_action_availability()
            self.update_command()

        def restore_custom_option(self):
            if not self.write_guard("restaurar opciones manuales"):
                return
            trash = self.app_config.setdefault("custom_options_trash", [])
            option = self.choose_custom_option(self.tx("Restaurar opcion manual", "Restore custom option"), trash)
            if not option:
                return
            restored = dict(option)
            restored.pop("deleted_at", None)
            selected = set(self.selected_keys())
            selected.add(custom_option_key(restored))
            self.app_config["custom_options_trash"] = [
                item for item in trash if item.get("id") != option.get("id")
            ]
            self.app_config.setdefault("custom_options", []).append(restored)
            save_app_config(self.app_config)
            self.rebuild_option_checkboxes(selected)
            self.set_action_availability()
            self.show_option_detail(custom_option_key(restored))
            self.update_command()

        def selected_keys(self):
            return [key for key, cb in self.checks.items() if cb.isChecked()]

        def eventFilter(self, obj, event):
            if event.type() == QtCore.QEvent.Enter and isinstance(obj, QtWidgets.QCheckBox):
                key = obj.property("optionKey")
                if key:
                    self.show_option_detail(key)
            return super().eventFilter(obj, event)

        def show_option_detail(self, key):
            meta = self.option_meta(key)
            if key in self.system_recommended:
                recommended = self.tx(
                    "Recomendada para tu sistema; el boton Marcar recomendadas la activara.",
                    "Recommended for your system; the Mark recommended button will enable it.",
                )
            elif meta.get("custom"):
                recommended = self.tx(
                    "Opcion manual creada por el usuario. Puedes borrarla y restaurarla desde esta pestana.",
                    "Custom option created by the user. You can delete and restore it from this tab.",
                )
            elif meta.get("recommended"):
                recommended = self.tx("Recomendada por defecto", "Recommended by default")
            elif meta.get("caution"):
                recommended = self.tx(
                    "Puede beneficiar, pero conviene probarla por juego. Por eso aparece en rojo.",
                    "May help, but should be tested per game. That is why it appears in red.",
                )
            elif meta.get("important"):
                recommended = self.tx(
                    "Opcion importante: depende del juego, monitor y objetivo.",
                    "Important option: depends on the game, monitor and goal.",
                )
            else:
                recommended = self.tx("Opcional / por juego", "Optional / per game")
            extra = ""
            if key == "GAMESCOPE":
                extra = self.tx(
                    "\nDiferencia clave: Gamescope fullscreen crea el contenedor. Resolucion real Gamescope decide que resolucion/Hz se exponen dentro de ese contenedor.",
                    "\nKey difference: Gamescope fullscreen creates the container. Native Gamescope resolution decides which resolution/Hz are exposed inside it.",
                )
            elif key == "REALRES":
                extra = self.tx(
                    "\nDiferencia clave: no sustituye a Gamescope fullscreen; le anade el modo nativo del monitor (-W/-H/-w/-h/-r).",
                    "\nKey difference: it does not replace Gamescope fullscreen; it adds the monitor's native mode (-W/-H/-w/-h/-r).",
                )
            elif key == "MANGOHUD":
                extra = self.tx(
                    "\nAtajo ingame: Shift derecho + F12 muestra u oculta el overlay. Shift izquierdo + F1 alterna el limite FPS de MangoHud.",
                    "\nIn-game shortcut: Right Shift + F12 shows or hides the overlay. Left Shift + F1 toggles MangoHud's FPS limiter.",
                )
            self.option_detail.setText(
                f"{meta['label']}\n\n"
                f"{meta['description']}\n\n"
                f"{self.tx('Anade', 'Adds')}: {meta['tokens']}\n"
                f"{self.tx('Estado', 'Status')}: {recommended}"
                f"{extra}"
            )

        def update_command(self):
            command = compose_launch(
                self.selected_keys(),
                self.custom_pre.text(),
                self.custom_post.text(),
                self.gamescope_resolution(),
                self.active_custom_options(),
            )
            self.command_edit.setPlainText(command)
            self.update_category_headers()

        def gamescope_resolution(self):
            return dict(self.active_gamescope_res)

        def set_resolution_fields(self, res):
            for widget in (self.real_width, self.real_height, self.real_refresh):
                widget.blockSignals(True)
            self.real_width.setValue(int(res.get("width") or 0))
            self.real_height.setValue(int(res.get("height") or 0))
            self.real_refresh.setValue(int(res.get("refresh") or 0))
            for widget in (self.real_width, self.real_height, self.real_refresh):
                widget.blockSignals(False)

        def resolution_fields(self):
            return {
                "width": self.real_width.value(),
                "height": self.real_height.value(),
                "refresh": self.real_refresh.value() or "",
            }

        def apply_resolution_fields(self):
            self.active_gamescope_res = self.resolution_fields()
            self.checks["REALRES"].setChecked(True)
            self.show_option_detail("REALRES")
            self.update_command()

        def use_detected_display(self):
            display = detect_primary_display()
            self.set_resolution_fields(display)
            self.apply_resolution_fields()

        def game_presets(self):
            if not self.current_game:
                return {}
            return self.app_config.setdefault("presets", {}).setdefault(self.current_game["appid"], {})

        def shared_presets(self):
            return get_shared_presets(self.app_config)

        def preset_from_ref(self, ref):
            scope, name = split_preset_ref(ref)
            if scope == "shared":
                return scope, name, self.shared_presets().get(name)
            if scope == "game":
                return scope, name, self.game_presets().get(name)
            return "", "", None

        def refresh_presets(self):
            self.preset_combo.blockSignals(True)
            self.preset_combo.clear()
            shared = self.shared_presets()
            game = self.game_presets()
            if not shared and not game:
                self.preset_combo.addItem(self.tx("Sin presets guardados", "No saved presets"), "")
            else:
                for name in sorted(shared):
                    self.preset_combo.addItem(f"{self.tx('Compartido', 'Shared')}: {name}", preset_ref("shared", name))
                for name in sorted(game):
                    self.preset_combo.addItem(f"{self.tx('Juego', 'Game')}: {name}", preset_ref("game", name))
            self.preset_combo.blockSignals(False)
            self.apply_preset_btn.setEnabled(False)
            if not shared and not game:
                self.set_preset_choice_status(self.tx("No hay presets guardados para cargar.", "No saved presets to load."), pending=False)

        def preset_command(self, preset):
            if not preset:
                return ""
            if "options" in preset:
                return compose_launch(
                    preset.get("options", []),
                    preset.get("custom_pre", ""),
                    preset.get("custom_post", ""),
                    preset.get("gamescope_res", {}),
                    self.active_custom_options(),
                )
            return preset.get("command", "")

        def set_preset_status(self, text, pending=False):
            self.current_preset_label.setProperty("pending", "true" if pending else "false")
            self.current_preset_label.style().unpolish(self.current_preset_label)
            self.current_preset_label.style().polish(self.current_preset_label)
            self.current_preset_label.setText(text)

        def set_preset_choice_status(self, text, pending=False, applied=False):
            self.preset_choice_label.setProperty("pending", "true" if pending else "false")
            self.preset_choice_label.setProperty("applied", "true" if applied else "false")
            self.preset_choice_label.style().unpolish(self.preset_choice_label)
            self.preset_choice_label.style().polish(self.preset_choice_label)
            self.preset_choice_label.setText(text)

        def current_applied_preset_name(self):
            if not self.current_applied_preset_ref:
                return ""
            _, name = split_preset_ref(self.current_applied_preset_ref)
            return name

        def preset_matches_command(self, ref, command):
            _, _, preset = self.preset_from_ref(ref)
            return bool(preset and normalize_command(self.preset_command(preset)) == normalize_command(command))

        def matching_preset_ref(self, command):
            wanted = normalize_command(command)
            if not wanted:
                return "", ""
            if self.current_game:
                custom = self.app_config.setdefault("custom", {}).get(self.current_game["appid"], {})
                preferred = custom.get("applied_preset_ref", "")
                if preferred and self.preset_matches_command(preferred, command):
                    _, name = split_preset_ref(preferred)
                    return preferred, name
            for scope, presets in (("shared", self.shared_presets()), ("game", self.game_presets())):
                for name, preset in presets.items():
                    if normalize_command(self.preset_command(preset)) == wanted:
                        return preset_ref(scope, name), name
            return "", ""

        def select_matching_preset(self, command):
            ref, name = self.matching_preset_ref(command)
            self.current_applied_preset_ref = ref
            self.preset_combo.blockSignals(True)
            if ref:
                index = self.preset_combo.findData(ref)
                if index >= 0:
                    self.preset_combo.setCurrentIndex(index)
                self.set_preset_status(f"{self.tx('Preset actual aplicado', 'Current applied preset')}: {name}", pending=False)
                self.set_preset_choice_status(f"{self.tx('Seleccionado y aplicado', 'Selected and applied')}: {name}", applied=True)
            else:
                self.preset_combo.setCurrentIndex(-1)
                if normalize_command(command):
                    self.set_preset_status(self.tx(
                        "Sin preset aplicado: las opciones actuales no coinciden con ningun preset guardado.",
                        "No applied preset: current options do not match any saved preset.",
                    ), pending=True)
                else:
                    self.set_preset_status(self.tx("Sin preset aplicado todavia.", "No preset applied yet."), pending=True)
                self.set_preset_choice_status(self.tx(
                    "Elige un preset para cargarlo. Al elegir uno distinto, aparecera como pendiente aqui.",
                    "Choose a preset to load it. Choosing a different one will show it as pending here.",
                ), pending=False)
            self.preset_combo.blockSignals(False)
            self.apply_preset_btn.setEnabled(False)
            return ref

        def current_preset_payload(self):
            command = compose_launch(
                self.selected_keys(),
                self.custom_pre.text(),
                self.custom_post.text(),
                self.gamescope_resolution(),
                self.active_custom_options(),
            )
            self.command_edit.setPlainText(command)
            return {
                "options": self.selected_keys(),
                "custom_pre": self.custom_pre.text(),
                "custom_post": self.custom_post.text(),
                "gamescope_res": self.gamescope_resolution(),
                "command": command,
            }

        def generated_command_from_controls(self):
            return compose_launch(
                self.selected_keys(),
                self.custom_pre.text(),
                self.custom_post.text(),
                self.gamescope_resolution(),
                self.active_custom_options(),
            )

        def command_was_edited_manually(self, command):
            return normalize_command(command) != normalize_command(self.generated_command_from_controls())

        def maybe_create_manual_command_preset(self, command):
            if not self.current_game or not self.command_was_edited_manually(command):
                return ""
            default_name = "Custom manual " + _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            name, ok = QtWidgets.QInputDialog.getText(
                self,
                self.tx("Crear preset custom", "Create custom preset"),
                self.tx(
                    "El Comando final fue editado a mano. Nombre para guardar este preset custom:",
                    "The Final command was edited manually. Name for this custom preset:",
                ),
                text=default_name,
            )
            name = name.strip()
            if not ok or not name:
                return None
            presets = self.game_presets()
            if name in presets:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Sobreescribir preset custom", "Overwrite custom preset"),
                    self.tx(
                        f"Ya existe un preset del juego llamado:\n\n{name}\n\nSobreescribirlo con el comando actual?",
                        f"A game preset already exists named:\n\n{name}\n\nOverwrite it with the current command?",
                    ),
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return None
            presets[name] = {
                "custom_pre": "",
                "custom_post": "",
                "gamescope_res": self.gamescope_resolution(),
                "command": command,
                "manual_command": True,
            }
            ref = preset_ref("game", name)
            custom = self.app_config.setdefault("custom", {}).setdefault(self.current_game["appid"], {})
            custom["applied_preset_ref"] = ref
            save_app_config(self.app_config)
            self.refresh_presets()
            index = self.preset_combo.findData(ref)
            if index >= 0:
                self.preset_combo.blockSignals(True)
                self.preset_combo.setCurrentIndex(index)
                self.preset_combo.blockSignals(False)
            self.current_applied_preset_ref = ref
            self.set_preset_status(f"{self.tx('Preset custom aplicado', 'Applied custom preset')}: {name}", pending=False)
            self.set_preset_choice_status(f"{self.tx('Seleccionado y aplicado', 'Selected and applied')}: {name}", applied=True)
            return name

        def confirm_manual_command_save(self, command, external=False):
            target = "perfil local de Proton Pilot" if external else "opciones de lanzamiento en Steam"
            target_en = "local Proton Pilot profile" if external else "Steam launch options"
            if self.command_was_edited_manually(command):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Guardar comando manual", "Save manual command"),
                    self.tx(
                        f"Guardar el Comando final editado a mano como preset custom y escribirlo en {target}?\n\n",
                        f"Save the manually edited Final command as a custom preset and write it to {target_en}?\n\n",
                    )
                    + self.diagnostic_text(command),
                )
                return reply == QtWidgets.QMessageBox.Yes
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Comando generado por controles", "Command generated by controls"),
                self.tx(
                    "El Comando final coincide con las casillas y campos de Proton Pilot.\n\n"
                    "Este boton esta pensado para comandos escritos a mano. Para un perfil normal suele ser mas claro usar Crear nuevo preset, Actualizar preset o Aplicar preset.\n\n"
                    f"Guardar este comando igualmente en {target}?\n\n",
                    "The Final command matches Proton Pilot's checkboxes and fields.\n\n"
                    "This button is intended for manually written commands. For a normal profile it is usually clearer to use Create new preset, Update preset or Apply preset.\n\n"
                    f"Save this command to {target_en} anyway?\n\n",
                )
                + self.diagnostic_text(command),
            )
            return reply == QtWidgets.QMessageBox.Yes

        def load_selected_preset(self):
            ref = self.preset_combo.currentData()
            if not ref:
                self.apply_preset_btn.setEnabled(False)
                self.set_preset_choice_status(self.tx("Elige un preset para cargarlo.", "Choose a preset to load it."), pending=False)
                return "", ""
            scope, name, preset = self.preset_from_ref(ref)
            if not preset:
                self.apply_preset_btn.setEnabled(False)
                self.set_preset_choice_status(self.tx("Ese preset ya no existe.", "That preset no longer exists."), pending=True)
                return "", ""
            selected = set(preset.get("options", []))
            for key, cb in self.checks.items():
                cb.blockSignals(True)
                cb.setChecked(key in selected)
                cb.blockSignals(False)
            self.custom_pre.setText(preset.get("custom_pre", ""))
            self.custom_post.setText(preset.get("custom_post", ""))
            preset_res = preset.get("gamescope_res") or {}
            self.active_gamescope_res = {
                "width": int(preset_res.get("width") or 0),
                "height": int(preset_res.get("height") or 0),
                "refresh": int(preset_res.get("refresh") or 0) or "",
            }
            self.set_resolution_fields(preset_res)
            if "options" in preset:
                self.update_command()
            else:
                command = preset.get("command", "")
                self.command_edit.setPlainText(command)
            if ref == self.current_applied_preset_ref:
                self.set_preset_status(f"{self.tx('Preset actual aplicado', 'Current applied preset')}: {name}", pending=False)
                self.set_preset_choice_status(f"{self.tx('Seleccionado y aplicado', 'Selected and applied')}: {name}", applied=True)
                self.apply_preset_btn.setEnabled(False)
            else:
                applied_name = self.current_applied_preset_name()
                if applied_name:
                    self.set_preset_status(f"{self.tx('Preset actual aplicado', 'Current applied preset')}: {applied_name}", pending=False)
                else:
                    self.set_preset_status(self.tx(
                        "Sin preset aplicado: el preset elegido aun no se ha escrito en el juego.",
                        "No applied preset: the selected preset has not been written to the game yet.",
                    ), pending=True)
                self.set_preset_choice_status(f"{self.tx('Pendiente de aplicar', 'Pending apply')}: {name}", pending=True)
                self.apply_preset_btn.setEnabled(not self.is_read_only())
            return ref, name

        def on_preset_selected(self):
            self.load_selected_preset()

        def apply_selected_preset(self):
            if not self.write_guard("aplicar presets"):
                return
            ref, name = self.load_selected_preset()
            if not ref or not self.current_game:
                return
            command = self.prepared_command()
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Aplicar preset", "Apply preset"),
                self.tx(f"Aplicar este preset como opciones de lanzamiento?\n\n{name}\n\n", f"Apply this preset as launch options?\n\n{name}\n\n")
                + self.diagnostic_text(command),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            custom = self.app_config.setdefault("custom", {}).setdefault(self.current_game["appid"], {})
            custom["applied_preset_ref"] = ref
            save_app_config(self.app_config)
            self.save(confirm=False)

        def save_preset(self):
            if not self.current_game:
                return
            if not self.write_guard("crear presets"):
                return
            name, ok = QtWidgets.QInputDialog.getText(self, self.tx("Crear nuevo preset", "Create new preset"), self.tx("Nombre del preset compartido:", "Shared preset name:"))
            name = name.strip()
            if not ok or not name:
                return
            presets = self.shared_presets()
            if name in presets:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Sobreescribir preset compartido", "Overwrite shared preset"),
                    self.tx(
                        f"Ya existe un preset compartido llamado:\n\n{name}\n\nQuieres sobreescribirlo con las opciones actuales?",
                        f"A shared preset already exists named:\n\n{name}\n\nDo you want to overwrite it with the current options?",
                    ),
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
            else:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Crear nuevo preset", "Create new preset"),
                    self.tx(
                        f"Crear un preset compartido llamado:\n\n{name}\n\ncon las opciones actuales?",
                        f"Create a shared preset named:\n\n{name}\n\nwith the current options?",
                    ),
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
            presets[name] = self.current_preset_payload()
            save_app_config(self.app_config)
            self.refresh_presets()
            index = self.preset_combo.findData(preset_ref("shared", name))
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            QtWidgets.QMessageBox.information(self, self.tx("Preset creado", "Preset created"), self.tx(f"Preset compartido creado:\n\n{name}", f"Shared preset created:\n\n{name}"))

        def update_preset(self):
            if not self.current_game:
                return
            if not self.write_guard("actualizar presets"):
                return
            ref = self.preset_combo.currentData()
            if not ref:
                return
            scope, name, preset = self.preset_from_ref(ref)
            if not preset:
                return
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Actualizar preset", "Update preset"),
                self.tx(
                    f"Actualizar el preset seleccionado con las opciones actuales?\n\n{name}\n\nOrigen: {'compartido' if scope == 'shared' else 'del juego'}\n\nSe sobreescribira su contenido.",
                    f"Update the selected preset with the current options?\n\n{name}\n\nSource: {'shared' if scope == 'shared' else 'game'}\n\nIts contents will be overwritten.",
                ),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            if scope == "shared":
                self.shared_presets()[name] = self.current_preset_payload()
            else:
                self.game_presets()[name] = self.current_preset_payload()
            save_app_config(self.app_config)
            self.refresh_presets()
            index = self.preset_combo.findData(preset_ref(scope, name))
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            QtWidgets.QMessageBox.information(self, self.tx("Preset actualizado", "Preset updated"), self.tx(f"Preset actualizado:\n\n{name}", f"Preset updated:\n\n{name}"))

        def delete_preset(self):
            if not self.write_guard("borrar presets"):
                return
            ref = self.preset_combo.currentData()
            if not ref:
                return
            scope, name, preset = self.preset_from_ref(ref)
            if not preset:
                return
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Borrar preset", "Delete preset"),
                self.tx(
                    f"Borrar definitivamente este preset?\n\n{name}\n\nOrigen: {'compartido' if scope == 'shared' else 'del juego'}\n\nEsta accion no borra las opciones ya guardadas en Steam.",
                    f"Delete this preset permanently?\n\n{name}\n\nSource: {'shared' if scope == 'shared' else 'game'}\n\nThis does not delete options already saved in Steam.",
                ),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            if scope == "shared":
                self.shared_presets().pop(name, None)
            else:
                self.game_presets().pop(name, None)
            save_app_config(self.app_config)
            self.refresh_presets()
            QtWidgets.QMessageBox.information(self, self.tx("Preset borrado", "Preset deleted"), self.tx(f"Preset borrado:\n\n{name}", f"Preset deleted:\n\n{name}"))

        def open_protondb(self):
            if self.current_game and not self.current_game.get("external"):
                open_url(f"https://www.protondb.com/app/{self.current_game['appid']}")

        def external_base_command(self):
            if not self.current_game or not self.current_game.get("external"):
                return ""
            proton = self.current_game.get("proton", "")
            exe = self.current_game.get("exe", "")
            if not proton or not exe:
                return ""
            return shell_join([proton, "run", exe])

        def external_shell_command(self):
            base = self.external_base_command()
            if not base:
                return ""
            command = self.command_edit.toPlainText().strip() or "%command%"
            if "%command%" not in command:
                command = command + " %command%"
            return command.replace("%command%", base)

        def launch_current_game(self):
            if not self.current_game:
                return
            if not self.current_game.get("external"):
                steam_cmd = shutil.which("steam")
                if steam_cmd:
                    subprocess.Popen([steam_cmd, "-applaunch", self.current_game["appid"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    open_url(f"steam://run/{self.current_game['appid']}")
                return
            command = self.external_shell_command()
            if not command:
                QtWidgets.QMessageBox.warning(self, self.tx("No se puede lanzar", "Cannot launch"), self.tx("Faltan datos del ejecutable o de Proton.", "Executable or Proton data is missing."))
                return
            prefix = Path(self.current_game.get("prefix") or APP_CONFIG_DIR / "compatdata" / self.current_game["appid"])
            prefix.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(self.root)
            env["STEAM_COMPAT_DATA_PATH"] = str(prefix)
            subprocess.Popen(command, shell=True, cwd=str(Path(self.current_game["exe"]).parent), env=env)

        def show_compare_dialog(self):
            if not self.current_game:
                return
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tx("Comparar opciones", "Compare options"))
            dialog.resize(980, 520)
            layout = QtWidgets.QVBoxLayout(dialog)
            status = QtWidgets.QLabel(
                self.tx("Hay cambios pendientes.", "There are pending changes.")
                if self.has_pending_command_changes()
                else self.tx("El comando preparado coincide con lo guardado.", "The prepared command matches what is saved.")
            )
            status.setWordWrap(True)
            layout.addWidget(status)
            cols = QtWidgets.QHBoxLayout()
            layout.addLayout(cols, 1)
            saved = QtWidgets.QPlainTextEdit()
            saved.setReadOnly(True)
            saved.setPlainText(self.current_game_launch_options() or self.tx("(sin opciones guardadas)", "(no saved options)"))
            prepared = QtWidgets.QPlainTextEdit()
            prepared.setReadOnly(True)
            prepared.setPlainText(self.prepared_command() or self.tx("(sin comando preparado)", "(no prepared command)"))
            saved_box = QtWidgets.QGroupBox(self.tx("Guardado ahora", "Saved now"))
            saved_layout = QtWidgets.QVBoxLayout(saved_box)
            saved_layout.addWidget(saved)
            prepared_box = QtWidgets.QGroupBox(self.tx("Preparado en pantalla", "Prepared on screen"))
            prepared_layout = QtWidgets.QVBoxLayout(prepared_box)
            prepared_layout.addWidget(prepared)
            cols.addWidget(saved_box)
            cols.addWidget(prepared_box)
            close_btn = QtWidgets.QPushButton(self.tx("Cerrar", "Close"))
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn, 0, QtCore.Qt.AlignRight)
            dialog.exec()

        def show_history_dialog(self):
            if not self.current_game:
                return
            appid = self.current_game["appid"]
            history = self.app_config.setdefault("launch_history", {}).get(appid, [])
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tx("Historial de opciones", "Options history"))
            dialog.resize(900, 520)
            layout = QtWidgets.QVBoxLayout(dialog)
            list_widget = QtWidgets.QListWidget()
            for entry in history:
                label = f"{entry.get('timestamp', '')} · {entry.get('reason', '')}"
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, entry)
                list_widget.addItem(item)
            layout.addWidget(list_widget, 1)
            preview = QtWidgets.QPlainTextEdit()
            preview.setReadOnly(True)
            preview.setPlaceholderText(self.tx("Selecciona una entrada para ver el comando.", "Select an entry to see the command."))
            layout.addWidget(preview, 1)
            buttons = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons)
            close_btn = QtWidgets.QPushButton(self.tx("Cerrar", "Close"))
            restore_btn = QtWidgets.QPushButton(self.tx("Restaurar seleccionado", "Restore selected"))
            restore_btn.setEnabled(False)
            buttons.addStretch(1)
            buttons.addWidget(close_btn)
            buttons.addWidget(restore_btn)

            def show_entry(item):
                entry = item.data(QtCore.Qt.UserRole) if item else None
                preview.setPlainText((entry or {}).get("command", ""))
                restore_btn.setEnabled(bool(entry))

            def restore_entry():
                item = list_widget.currentItem()
                if not item:
                    return
                entry = item.data(QtCore.Qt.UserRole)
                command = entry.get("command", "")
                if not command:
                    return
                self.command_edit.setPlainText(command)
                dialog.accept()
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Restaurar historial", "Restore history"),
                    self.tx("Restaurar este comando como opciones de lanzamiento del juego?\n\n", "Restore this command as the game's launch options?\n\n")
                    + self.diagnostic_text(command),
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    self.save(confirm=False)

            list_widget.currentItemChanged.connect(show_entry)
            close_btn.clicked.connect(dialog.reject)
            restore_btn.clicked.connect(restore_entry)
            if list_widget.count():
                list_widget.setCurrentRow(0)
            else:
                preview.setPlainText(self.tx("No hay historial guardado para este juego todavia.", "No saved history for this game yet."))
            dialog.exec()

        def apply_prepared_command(self):
            if not self.current_game:
                return
            if not self.write_guard("aplicar cambios preparados"):
                return
            command = self.prepared_command()
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Aplicar cambios preparados", "Apply prepared changes"),
                self.tx("Escribir ahora el comando preparado como opciones de lanzamiento?\n\n", "Write the prepared command as launch options now?\n\n")
                + self.diagnostic_text(command),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            self.save(confirm=False)

        def display_diagnostic_text(self):
            display = self.system.get("display", {})
            lines = [
                self.tx("Estado detectado de pantalla:", "Detected display status:"),
                f"- {self.tx('Monitor', 'Monitor')}: {display.get('name') or self.tr('not_detected')}",
                f"- {self.tx('Resolucion', 'Resolution')}: {display.get('width') or '?'}x{display.get('height') or '?'}@{display.get('refresh') or '?'}",
                f"- HDR KDE: {self.tx('activo', 'active') if display_hdr_enabled(display) else (display.get('hdr') or self.tr('not_detected'))}",
                f"- WCG: {display.get('wide_color') or self.tr('not_detected')}",
                f"- VRR KDE: {display.get('vrr') or self.tr('not_detected')}",
                f"- Gamescope: {self.tx('disponible', 'available') if self.system['tools'].get('gamescope') else self.tx('no disponible', 'not available')}",
                f"- Gamescope WSI: {self.tx('detectado', 'detected') if self.system.get('gamescope_wsi') else self.tr('not_detected')}",
                "",
                self.tx("Lectura practica:", "Practical read:"),
            ]
            if display_hdr_enabled(display) and self.system.get("gamescope_wsi"):
                lines.append(self.tx("- HDR via Gamescope deberia estar disponible para juegos compatibles.", "- HDR via Gamescope should be available for compatible games."))
            elif not display_hdr_enabled(display):
                lines.append(self.tx("- HDR no aparece activo en KDE. Activalo en la pantalla antes de usar presets HDR.", "- HDR does not appear active in KDE. Enable it on the display before using HDR presets."))
            elif not self.system.get("gamescope_wsi"):
                lines.append(self.tx("- HDR esta activo, pero no detecto Gamescope WSI; DXVK_HDR puede no exponerse al juego.", "- HDR is active, but I do not detect Gamescope WSI; DXVK_HDR may not be exposed to the game."))
            if display_vrr_available(display):
                lines.append(self.tx("- VRR aparece disponible. Adaptive Sync y VRR cap pueden ayudar, pero conviene validar por juego.", "- VRR appears available. Adaptive Sync and VRR cap can help, but should be validated per game."))
            else:
                lines.append(self.tx("- VRR no aparece disponible; Adaptive Sync puede no tener efecto.", "- VRR does not appear available; Adaptive Sync may have no effect."))
            if self.system.get("device", {}).get("gaming_mode"):
                lines.append(self.tx("- Gaming Mode detectado: evita cambios que cierren Steam desde aqui; mejor aplicar en Desktop Mode.", "- Gaming Mode detected: avoid changes that close Steam from here; Desktop Mode is better for applying them."))
            return "\n".join(lines)

        def show_display_diagnostics(self):
            QtWidgets.QMessageBox.information(self, self.tx("Diagnostico HDR/VRR", "HDR/VRR diagnostics"), self.display_diagnostic_text())

        def show_proton_history_dialog(self):
            if not self.current_game or self.current_game.get("external"):
                return
            appid = self.current_game["appid"]
            history = self.app_config.setdefault("proton_history", {}).get(appid, [])
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tx("Historial Proton", "Proton history"))
            dialog.resize(760, 420)
            layout = QtWidgets.QVBoxLayout(dialog)
            list_widget = QtWidgets.QListWidget()
            for entry in history:
                label = f"{entry.get('timestamp', '')} · {entry.get('label') or self.tx('Steam por defecto', 'Steam default')} · {entry.get('reason', '')}"
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, entry)
                list_widget.addItem(item)
            layout.addWidget(list_widget, 1)
            buttons = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons)
            close_btn = QtWidgets.QPushButton(self.tx("Cerrar", "Close"))
            restore_btn = QtWidgets.QPushButton(self.tx("Restaurar Proton", "Restore Proton"))
            restore_btn.setEnabled(False)
            buttons.addStretch(1)
            buttons.addWidget(close_btn)
            buttons.addWidget(restore_btn)

            def select_entry(item):
                restore_btn.setEnabled(bool(item and not self.is_read_only()))

            def restore_proton():
                item = list_widget.currentItem()
                if not item or not self.write_guard("restaurar Proton"):
                    return
                entry = item.data(QtCore.Qt.UserRole) or {}
                tool = entry.get("compat_tool", "")
                label = compat_tool_display_name(tool, self.proton_tools)
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Restaurar Proton", "Restore Proton"),
                    self.tx(f"Restaurar esta version para {self.current_game['name']}?\n\n{label}", f"Restore this version for {self.current_game['name']}?\n\n{label}"),
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                index = self.proton_combo.findData(tool)
                if index < 0:
                    QtWidgets.QMessageBox.warning(
                        self,
                        self.tx("Proton no disponible", "Proton unavailable"),
                        self.tx("Esa version ya no aparece instalada. Instalala o elige una version disponible.", "That version no longer appears installed. Install it or choose an available version."),
                    )
                    return
                self.proton_combo.setCurrentIndex(index)
                dialog.accept()
                self.apply_selected_proton()

            list_widget.currentItemChanged.connect(select_entry)
            close_btn.clicked.connect(dialog.reject)
            restore_btn.clicked.connect(restore_proton)
            if list_widget.count():
                list_widget.setCurrentRow(0)
            else:
                list_widget.addItem(self.tx("No hay cambios de Proton registrados para este juego.", "No Proton changes recorded for this game."))
            dialog.exec()

        def register_appimage_shortcut(self):
            if not self.write_guard("registrar Proton Pilot en Steam"):
                return
            appimage = running_appimage_path()
            if not appimage:
                QtWidgets.QMessageBox.information(
                    self,
                    self.tx("AppImage no encontrado", "AppImage not found"),
                    self.tx(
                        "No encuentro un AppImage ejecutable de Proton Pilot. Ejecuta el AppImage o genera uno con build-appimage.sh.",
                        "I cannot find an executable Proton Pilot AppImage. Run the AppImage or generate one with build-appimage.sh.",
                    ),
                )
                return
            if steam_is_running():
                if not self.allow_steam_shutdown_write("registrar Proton Pilot en Steam"):
                    return
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Cerrar Steam para registrar AppImage", "Close Steam to register AppImage"),
                    self.tx(
                        "Para escribir shortcuts.vdf con seguridad, Proton Pilot puede cerrar Steam y volver a abrirlo despues.\n\nCerrar Steam y continuar?",
                        "To safely write shortcuts.vdf, Proton Pilot can close Steam and reopen it afterwards.\n\nClose Steam and continue?",
                    ),
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                if not close_steam():
                    QtWidgets.QMessageBox.warning(self, self.tx("No se pudo cerrar Steam", "Could not close Steam"), self.tx("Cierra Steam manualmente y vuelve a intentarlo.", "Close Steam manually and try again."))
                    return
                reopen = True
            else:
                reopen = False
            try:
                result = add_steam_shortcut(self.root, APP_NAME, str(appimage), "")
                reopen_note = ""
                if reopen:
                    reopen_note = self.tx("\n\nSteam se ha vuelto a abrir.", "\n\nSteam has been reopened.") if open_steam(self.root) else self.tx("\n\nNo he podido volver a abrir Steam; abrelo manualmente.", "\n\nI could not reopen Steam; open it manually.")
                QtWidgets.QMessageBox.information(
                    self,
                    self.tx("AppImage registrado", "AppImage registered"),
                    self.tx(
                        f"Proton Pilot se ha anadido como aplicacion externa de Steam.\n\n{result['path']}{reopen_note}",
                        f"Proton Pilot has been added as a non-Steam application.\n\n{result['path']}{reopen_note}",
                    ),
                )
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, self.tx("Error al registrar AppImage", "Error registering AppImage"), str(exc))

        def check_for_updates(self):
            try:
                info = latest_release_info()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tx("No se pudo consultar GitHub", "Could not query GitHub"),
                    self.tx(f"No he podido consultar la ultima release de GitHub.\n\n{exc}", f"I could not query the latest GitHub release.\n\n{exc}"),
                )
                return
            if info.get("missing"):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Sin releases publicadas", "No published releases"),
                    self.tx(
                        "GitHub responde correctamente, pero este repo todavia no tiene ninguna Release publicada.\n\n"
                        "Cuando publiques una release con AppImage, este boton podra compararla con la version instalada.\n\n"
                        "Abrir la pagina de releases?",
                        "GitHub responded correctly, but this repository does not have any published Release yet.\n\n"
                        "Once you publish a release with an AppImage, this button can compare it with the installed version.\n\n"
                        "Open the releases page?",
                    ),
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    open_url(info.get("url"))
                return
            tag = info.get("tag") or "desconocida"
            tag_label = tag if tag != "desconocida" else self.tx("desconocida", "unknown")
            message = f"{self.tx('Version instalada', 'Installed version')}: {APP_VERSION}\n{self.tx('Ultima release', 'Latest release')}: {tag_label}"
            if info.get("asset_name"):
                message += f"\nAppImage: {info['asset_name']}"
            if tag and is_newer_version(tag, APP_VERSION):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Actualizacion disponible", "Update available"),
                    message + self.tx("\n\nAbrir la pagina de descarga?", "\n\nOpen the download page?"),
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    open_url(info.get("asset_url") or info.get("url"))
            else:
                QtWidgets.QMessageBox.information(self, self.tx("Sin actualizacion detectada", "No update detected"), message)

        def profile_options_for_goal(self, goal):
            keys = set()
            if goal in {"performance", "hdr", "vrr", "rt"}:
                keys.update(k for k in ("GAMEMODE", "GAMESCOPE", "REALRES") if k in self.system_recommended)
            if goal == "performance":
                keys.update(k for k in ("GAMEMODE", "GAMESCOPE", "REALRES", "FSR4") if k in self.system_recommended)
            elif goal == "hdr":
                keys.update(k for k in ("GAMEMODE", "GAMESCOPE", "REALRES", "HDR", "PROTONHDR", "FSR4") if k in self.system_recommended)
            elif goal == "vrr":
                keys.update(k for k in ("GAMEMODE", "GAMESCOPE", "REALRES", "ADAPTIVE", "CAPVRR") if k in self.system_recommended)
            elif goal == "rt":
                keys.update(k for k in ("GAMEMODE", "GAMESCOPE", "REALRES") if k in self.system_recommended)
                keys.update({"RT", "DX12"})
                if "FSR4" in self.system_recommended:
                    keys.add("FSR4")
                if self.system.get("gpu") == "nvidia":
                    keys.add("NVIDIA")
            elif goal == "handheld":
                keys.update(k for k in ("GAMEMODE", "GAMESCOPE", "HANDHELD800P", "CAP60") if k in OPTION_INFO)
                if "FSR4" in self.system_recommended:
                    keys.add("FSR4")
            elif goal == "desktop_hdr_vrr":
                keys.update(k for k in ("GAMEMODE", "MANGOHUD", "GAMESCOPE", "REALRES", "HDR", "PROTONHDR", "ADAPTIVE", "CAPVRR", "FSR4") if k in self.system_recommended)
            elif goal == "legion_go_2":
                keys.update({"GAMEMODE", "MANGOHUD", "HANDHELD1200P", "ADAPTIVE"})
                if display_hdr_enabled(self.system.get("display", {})) and self.system.get("gamescope_wsi"):
                    keys.update({"HDR", "PROTONHDR"})
                if "FSR4" in self.system_recommended:
                    keys.add("FSR4")
            elif goal == "legion_go_s":
                keys.update({"GAMEMODE", "MANGOHUD", "HANDHELD800P", "CAP60"})
                if "FSR4" in self.system_recommended:
                    keys.add("FSR4")
            elif goal == "safe":
                keys.update(k for k in ("GAMEMODE",) if k in self.system_recommended)
            return keys

        def show_profile_assistant(self):
            if not self.current_game:
                return
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tx("Asistente de perfil", "Profile assistant"))
            layout = QtWidgets.QVBoxLayout(dialog)
            label = QtWidgets.QLabel(self.tx(
                "Elige un objetivo. Proton Pilot marcara opciones razonables para revisarlas antes de aplicar.",
                "Choose a goal. Proton Pilot will mark reasonable options so you can review them before applying.",
            ))
            label.setWordWrap(True)
            layout.addWidget(label)
            choices = [
                ("performance", self.tx("Rendimiento equilibrado", "Balanced performance")),
                ("desktop_hdr_vrr", self.tx("Escritorio HDR/VRR", "Desktop HDR/VRR")),
                ("hdr", "HDR"),
                ("vrr", self.tx("VRR estable", "Stable VRR")),
                ("rt", "Ray Tracing / DX12"),
                ("handheld", self.tx("Handheld / bateria", "Handheld / battery")),
                ("legion_go_2", "Legion Go 2 / Bazzite"),
                ("legion_go_s", "Legion Go S / SteamOS"),
                ("safe", self.tx("Minimo seguro", "Safe minimum")),
            ]
            combo = QtWidgets.QComboBox()
            for key, text in choices:
                combo.addItem(text, key)
            layout.addWidget(combo)
            preview = QtWidgets.QPlainTextEdit()
            preview.setReadOnly(True)
            layout.addWidget(preview)
            buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            layout.addWidget(buttons)

            def update_preview():
                keys = self.profile_options_for_goal(combo.currentData())
                labels = [self.option_label(key) for key in OPTION_INFO if key in keys]
                preview.setPlainText("\n".join(labels) or self.tx("No hay opciones recomendadas detectadas para este objetivo.", "No recommended options detected for this goal."))

            def accept():
                keys = self.profile_options_for_goal(combo.currentData())
                for key, cb in self.checks.items():
                    cb.setChecked(key in keys)
                if "REALRES" in keys:
                    display = display_resolution_or_empty(self.system.get("display", {}))
                    if display["width"] and display["height"]:
                        self.active_gamescope_res = display
                        self.set_resolution_fields(display)
                self.update_command()
                dialog.accept()

            combo.currentIndexChanged.connect(update_preview)
            buttons.accepted.connect(accept)
            buttons.rejected.connect(dialog.reject)
            update_preview()
            dialog.exec()

        def apply_system_recommended(self):
            for key in self.system_recommended:
                if key in self.checks:
                    self.checks[key].setChecked(True)
            if "REALRES" in self.system_recommended:
                display = display_resolution_or_empty(self.system.get("display", {}))
                if display["width"] and display["height"]:
                    self.active_gamescope_res = display
                    self.set_resolution_fields(display)
            self.update_command()
            QtWidgets.QMessageBox.information(
                self,
                self.tx("Recomendadas marcadas", "Recommended options marked"),
                self.tx(
                    "He marcado las opciones amarillas recomendadas segun tu sistema detectado. Revisa el comando final y usa Crear/Actualizar preset o Aplicar preset para escribirlo.",
                    "I marked the yellow options recommended for your detected system. Review the final command and use Create/Update preset or Apply preset to write it.",
                ),
            )

        def show_about(self):
            history_es = [
                ("0.10.5", "Interfaz ampliada con traduccion ES/EN en paneles, estados, tooltips y dialogos principales."),
                ("0.10.4", "Acordeon de opciones sin recuadros vacios, disposicion abierta persistente, selector de idioma y documentacion EN/ES."),
                ("0.10.3", "Categorias orientadas a objetivos y titulos de opciones con verbos mas claros."),
                ("0.10.2", "Opciones manuales por categorias con papelera/restauracion, Acerca de desplazable, tabs sin rueda y modo compacto mas estricto."),
                ("0.10.1", "Buscar actualizacion tolera repos sin releases y los recuadros ganan espacio para no pisar texto."),
                ("0.10.0", "Modo compacto, solo lectura, panel redimensionable, diagnostico HDR/VRR, historial Proton y acciones AppImage/update."),
                ("0.9.1", "Layout responsive para evitar cortes en pantallas mas estrechas."),
                ("0.9.0", "Gestion de Proton por juego, recomendaciones, pestanas y builder AppImage."),
                ("0.8.9", "Cambios pendientes, comparar, diagnostico, historial y asistente de perfil."),
                ("0.8.8", "Estado de preset aplicado separado del preset seleccionado pendiente."),
                ("0.8.7", "Iconos para ejecutables externos y comandos manuales guardados como presets custom."),
                ("0.8.6", "Recuerda el preset exacto aplicado y avisa en rojo si hay uno pendiente."),
                ("0.8.5", "Selector de presets carga opciones automaticamente y aplicar pide confirmacion."),
                ("0.8.4", "Corrige listado inicial para mostrar todos los juegos detectados."),
                ("0.8.3", "Preset recomendado del sistema, panel de juego claro y gestion de manuales."),
                ("0.8.2", "Tarjetas HDR/VRR, badge ProtonDB y recomendaciones VRR/Adaptive en rojo de prueba."),
                ("0.8.1", "Recomendadas amarillas, ratings ProtonDB en juegos y accesos directos Steam externos."),
                ("0.8.0", "Presets compartidos, controles sin rueda accidental, lanzamiento Steam y resumen ProtonDB oficial."),
                ("0.7.9", "VRR cap usa limitador MangoHud porque Gamescope redondea a divisores."),
                ("0.7.8", "VRR cap automatico usando Hz aplicados."),
                ("0.7.7", "Resolucion Gamescope solo cambia al aplicarla y pruebas de presets."),
                ("0.7.6", "Presets aplican opciones reconstruidas y recuerdan acciones como HDR Unreal."),
                ("0.7.5", "Las recomendaciones ya no se autoactivan al recargar un juego."),
                ("0.7.4", "Ruta Steam configurable y guardado seguro cerrando/reabriendo Steam."),
                ("0.7.3", "Actualizar presets, confirmaciones, botones con borde y ejecutables externos con Proton detectable o manual."),
                ("0.7.2", "Opciones en lista vertical, iconos de juegos, juegos manuales y botones de accion claros."),
                ("0.7.1", "Layout de escritorio mas ancho, lista fija y opciones sin corte horizontal."),
                ("0.7.0", "Resolucion real Gamescope, deteccion de monitor y presets nativos."),
                ("0.6.0", "Bazzite/SteamOS handheld, Legion Go 2, 800p/1200p y limites FPS."),
                ("0.5.0", "Logo, nombre, recomendaciones del sistema, hover help y README."),
                ("0.4.0", "Interfaz PySide6 mas clara."),
                ("0.3.0", "ProtonDB, personalizados y presets."),
                ("0.2.0", "HDR, GameMode, MangoHud y Gamescope."),
                ("0.1.0", "Tool inicial con Zenity."),
            ]
            history_en = [
                ("0.10.5", "Expanded ES/EN interface coverage for panels, states, tooltips and main dialogs."),
                ("0.10.4", "Cleaner options accordion, persistent open layout, language selector and EN/ES documentation."),
                ("0.10.3", "Goal-oriented categories and clearer action-based option titles."),
                ("0.10.2", "Custom options by category with trash/restore, scrollable About, no-wheel tabs and stricter compact mode."),
                ("0.10.1", "Update checks tolerate repositories without releases and cards gain spacing to avoid text overlap."),
                ("0.10.0", "Compact mode, read-only mode, resizable panel, HDR/VRR diagnostics, Proton history and AppImage/update actions."),
                ("0.9.1", "Responsive layout to avoid clipping on narrower screens."),
                ("0.9.0", "Per-game Proton management, recommendations, tabs and AppImage builder."),
                ("0.8.9", "Pending changes, compare, diagnostics, history and profile assistant."),
                ("0.8.8", "Applied preset state separated from selected pending preset."),
                ("0.8.7", "External executable icons and manually edited commands saved as custom presets."),
                ("0.8.6", "Remembers the exact applied preset and warns in red when one is pending."),
                ("0.8.5", "Preset selector loads options automatically and apply asks for confirmation."),
                ("0.8.4", "Fixes initial game list to show all detected games."),
                ("0.8.3", "System recommended preset, clearer game panel and manual game management."),
                ("0.8.2", "HDR/VRR cards, ProtonDB badge and red trial recommendations for VRR/Adaptive."),
                ("0.8.1", "Yellow recommended options, ProtonDB ratings in games and Steam shortcuts for external games."),
                ("0.8.0", "Shared presets, controls protected from mouse wheel accidents, Steam launch and official ProtonDB summary."),
                ("0.7.9", "VRR cap uses MangoHud limiter because Gamescope rounds to refresh divisors."),
                ("0.7.8", "Automatic VRR cap using applied Hz."),
                ("0.7.7", "Gamescope resolution only changes when applied and preset tests."),
                ("0.7.6", "Presets apply rebuilt options and remember side effects such as Unreal HDR."),
                ("0.7.5", "Recommendations no longer auto-enable when reloading a game."),
                ("0.7.4", "Configurable Steam path and safer save by closing/reopening Steam."),
                ("0.7.3", "Preset updates, confirmations, bordered buttons and external executables with detected or manual Proton."),
                ("0.7.2", "Vertical options list, game icons, manual games and clearer action buttons."),
                ("0.7.1", "Wider desktop layout, fixed game list and options without horizontal clipping."),
                ("0.7.0", "Native Gamescope resolution, monitor detection and native presets."),
                ("0.6.0", "Bazzite/SteamOS handheld, Legion Go 2, 800p/1200p and FPS limits."),
                ("0.5.0", "Logo, name, system recommendations, hover help and README."),
                ("0.4.0", "Clearer PySide6 interface."),
                ("0.3.0", "ProtonDB, custom options and presets."),
                ("0.2.0", "HDR, GameMode, MangoHud and Gamescope."),
                ("0.1.0", "Initial Zenity tool."),
            ]
            history = history_en if self.language() == "en" else history_es
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(f"{self.tx('Acerca de', 'About')} {APP_NAME}")
            dialog.resize(760, 560)
            layout = QtWidgets.QVBoxLayout(dialog)
            text = QtWidgets.QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText(
                f"{APP_NAME} {APP_VERSION}\n\n"
                f"Config:\n{APP_CONFIG_FILE}\n\n"
                f"README:\n{APP_DIR / 'README.md'}\n\n"
                + self.tx("Historial, de mas nuevo a mas viejo:\n\n", "History, newest to oldest:\n\n")
                + "\n".join(f"{version} - {note}" for version, note in history)
            )
            layout.addWidget(text, 1)
            close_btn = QtWidgets.QPushButton(self.tx("Cerrar", "Close"))
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn, 0, QtCore.Qt.AlignRight)
            dialog.exec()

        def show_recommendations(self):
            if not self.current_game:
                return
            data = protondb_recommendation_data(self.current_game, self.app_config)
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tx("Recomendaciones ProtonDB", "ProtonDB recommendations"))
            dialog.resize(820, 560)
            layout = QtWidgets.QVBoxLayout(dialog)
            text = QtWidgets.QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText(data["text"])
            layout.addWidget(text, 1)

            combo = QtWidgets.QComboBox()
            combo.addItem(self.tx("No aplicar launch options de ProtonDB", "Do not apply ProtonDB launch options"), "")
            for hint in data["launch_hints"][:8]:
                combo.addItem(hint, hint)
            layout.addWidget(combo)

            buttons = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons)
            open_btn = QtWidgets.QPushButton(self.tx("Abrir ProtonDB", "Open ProtonDB"))
            refresh_btn = QtWidgets.QPushButton(self.tx("Actualizar datos", "Refresh data"))
            apply_btn = QtWidgets.QPushButton(self.tx("Aceptar y aplicar seleccion", "Accept and apply selection"))
            close_btn = QtWidgets.QPushButton(self.tx("Cerrar", "Close"))
            buttons.addWidget(open_btn)
            buttons.addWidget(refresh_btn)
            buttons.addStretch(1)
            buttons.addWidget(close_btn)
            buttons.addWidget(apply_btn)
            open_btn.clicked.connect(self.open_protondb)
            close_btn.clicked.connect(dialog.reject)

            def refresh_data():
                protondb_cached_summary(self.app_config, self.current_game["appid"], refresh=True)
                save_app_config(self.app_config)
                refreshed = protondb_recommendation_data(self.current_game, self.app_config)
                text.setPlainText(refreshed["text"])
                combo.clear()
                combo.addItem(self.tx("No aplicar launch options de ProtonDB", "Do not apply ProtonDB launch options"), "")
                for hint in refreshed["launch_hints"][:8]:
                    combo.addItem(hint, hint)
                self.update_current_item_rating(refreshed["summary"])
                self.update_protondb_badge(refreshed["summary"])

            refresh_btn.clicked.connect(refresh_data)

            def apply_hint():
                hint = combo.currentData()
                if hint:
                    self.command_edit.setPlainText(hint)
                dialog.accept()

            apply_btn.clicked.connect(apply_hint)
            dialog.exec()

        def save_custom(self):
            if not self.current_game:
                return
            custom = self.app_config.setdefault("custom", {}).setdefault(self.current_game["appid"], {})
            custom["pre"] = self.custom_pre.text()
            custom["post"] = self.custom_post.text()
            custom["gamescope_res"] = self.gamescope_resolution()
            custom["side_effect_options"] = [key for key in self.selected_keys() if key in SIDE_EFFECT_OPTIONS]
            command = self.command_edit.toPlainText().strip()
            current_ref = self.preset_combo.currentData() or ""
            if current_ref and self.preset_matches_command(current_ref, command):
                custom["applied_preset_ref"] = current_ref
            elif custom.get("applied_preset_ref") and not self.preset_matches_command(custom["applied_preset_ref"], command):
                custom.pop("applied_preset_ref", None)
            save_app_config(self.app_config)

        def save(self, checked=False, confirm=True):
            if not self.current_game:
                return
            if not self.write_guard("guardar opciones"):
                return
            if self.current_game.get("external"):
                command = self.command_edit.toPlainText().strip()
                if confirm:
                    if not self.confirm_manual_command_save(command, external=True):
                        return
                custom_preset_name = self.maybe_create_manual_command_preset(command) if confirm else ""
                if custom_preset_name is None:
                    return
                self.remember_launch_history(self.current_game_launch_options(), "antes de guardar")
                self.app_config.setdefault("external_launch_options", {})[self.current_game["appid"]] = command
                self.save_custom()
                shortcut_note = ""
                if self.current_game.get("steam_shortcut"):
                    reopen_steam = False
                    if steam_is_running():
                        if not self.allow_steam_shutdown_write("actualizar el acceso directo"):
                            shortcut_note = "\n\nNo se ha actualizado el acceso directo de Steam en Gaming Mode."
                            steam_running_blocked = True
                        else:
                            steam_running_blocked = False
                    else:
                        steam_running_blocked = False
                    if steam_is_running() and not steam_running_blocked:
                        reply = QtWidgets.QMessageBox.question(
                            self,
                            self.tx("Cerrar Steam para actualizar acceso directo", "Close Steam to update shortcut"),
                            self.tx(
                                "Este perfil externo tambien existe en la biblioteca de Steam. Para actualizar sus launch options sin que Steam sobrescriba shortcuts.vdf, Proton Pilot puede cerrar Steam y volver a abrirlo.\n\nCerrar Steam y continuar?",
                                "This external profile also exists in the Steam library. To update its launch options without Steam overwriting shortcuts.vdf, Proton Pilot can close Steam and reopen it.\n\nClose Steam and continue?",
                            ),
                        )
                        if reply == QtWidgets.QMessageBox.Yes:
                            if not close_steam():
                                QtWidgets.QMessageBox.warning(
                                    self,
                                    self.tx("No se pudo cerrar Steam", "Could not close Steam"),
                                    self.tx(
                                        "He guardado el perfil local, pero no he actualizado el acceso directo de Steam.",
                                        "I saved the local profile, but did not update the Steam shortcut.",
                                    ),
                                )
                            else:
                                reopen_steam = True
                        else:
                            shortcut_note = self.tx("\n\nNo se ha actualizado el acceso directo de Steam porque Steam seguia abierto.", "\n\nThe Steam shortcut was not updated because Steam was still open.")
                    if not steam_is_running():
                        try:
                            result = update_steam_shortcut_launch_options(
                                self.root,
                                self.current_game["name"],
                                self.current_game["exe"],
                                command,
                            )
                            if result:
                                shortcut_note = self.tx(f"\n\nAcceso directo de Steam actualizado:\n{result['path']}", f"\n\nSteam shortcut updated:\n{result['path']}")
                            else:
                                shortcut_note = self.tx("\n\nNo he encontrado el acceso directo en shortcuts.vdf.", "\n\nI did not find the shortcut in shortcuts.vdf.")
                        except Exception as exc:
                            shortcut_note = self.tx(f"\n\nNo he podido actualizar el acceso directo de Steam: {exc}", f"\n\nCould not update the Steam shortcut: {exc}")
                    if reopen_steam:
                        if open_steam(self.root):
                            shortcut_note += self.tx("\nSteam se ha vuelto a abrir.", "\nSteam has been reopened.")
                        else:
                            shortcut_note += self.tx("\nNo he podido volver a abrir Steam; abrelo manualmente.", "\nI could not reopen Steam; open it manually.")
                custom_note = self.tx(f"\n\nPreset custom creado: {custom_preset_name}", f"\n\nCustom preset created: {custom_preset_name}") if custom_preset_name else ""
                QtWidgets.QMessageBox.information(
                    self,
                    self.tx("Guardado", "Saved"),
                    self.tx(
                        f"Comando guardado para el perfil externo:\n\n{self.current_game['name']}",
                        f"Command saved for the external profile:\n\n{self.current_game['name']}",
                    )
                    + f"{custom_note}{shortcut_note}",
                )
                self.select_game(self.game_list.currentItem())
                return
            command = self.command_edit.toPlainText().strip()
            if confirm:
                if not self.confirm_manual_command_save(command, external=False):
                    return
            custom_preset_name = self.maybe_create_manual_command_preset(command) if confirm else ""
            if custom_preset_name is None:
                return
            self.remember_launch_history(self.current_game_launch_options(), "antes de guardar")
            reopen_steam = False
            if steam_is_running():
                if not self.allow_steam_shutdown_write("guardar opciones"):
                    return
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Cerrar Steam para guardar", "Close Steam to save"),
                    self.tx(
                        "Steam esta abierto. Para evitar que sobrescriba localconfig.vdf, Proton Pilot puede cerrarlo ahora, guardar las opciones y volver a abrirlo.\n\nCerrar Steam y continuar?",
                        "Steam is open. To prevent it from overwriting localconfig.vdf, Proton Pilot can close it now, save the options and reopen it.\n\nClose Steam and continue?",
                    ),
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                if not close_steam():
                    QtWidgets.QMessageBox.warning(
                        self,
                        self.tx("No se pudo cerrar Steam", "Could not close Steam"),
                        self.tx("No he podido cerrar Steam de forma fiable. Cierra Steam manualmente y vuelve a guardar.", "I could not close Steam reliably. Close Steam manually and save again."),
                    )
                    return
                reopen_steam = True
            backup = set_launch_options(self.config_path, self.current_game["appid"], command)
            self.save_custom()
            extra = ""
            if self.checks["UEHDR"].isChecked():
                extra = "\n\n" + set_unreal_hdr(self.root, self.current_game["appid"])
            reopen_note = ""
            if reopen_steam:
                if open_steam(self.root):
                    reopen_note = self.tx("\n\nSteam se ha vuelto a abrir.", "\n\nSteam has been reopened.")
                else:
                    reopen_note = self.tx("\n\nNo he podido volver a abrir Steam. Abre Steam manualmente.", "\n\nI could not reopen Steam. Open Steam manually.")
            custom_note = self.tx(f"\n\nPreset custom creado: {custom_preset_name}", f"\n\nCustom preset created: {custom_preset_name}") if custom_preset_name else ""
            QtWidgets.QMessageBox.information(
                self,
                self.tx("Guardado", "Saved"),
                self.tx(f"Comando guardado para {self.current_game['name']}.\n\nBackup:\n{backup}", f"Command saved for {self.current_game['name']}.\n\nBackup:\n{backup}")
                + f"{custom_note}{extra}{reopen_note}",
            )
            self.select_game(self.game_list.currentItem())

        def clear(self):
            if not self.current_game:
                return
            if not self.write_guard("borrar opciones"):
                return
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tx("Borrar opciones de lanzamiento", "Clear launch options"),
                self.tx(
                    f"Esto borrara las opciones de lanzamiento guardadas para:\n\n{self.current_game['name']}\n\nContinuar?",
                    f"This will clear the saved launch options for:\n\n{self.current_game['name']}\n\nContinue?",
                ),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            if self.current_game.get("external"):
                self.remember_launch_history(self.current_game_launch_options(), "antes de borrar")
                self.app_config.setdefault("external_launch_options", {}).pop(self.current_game["appid"], None)
                for cb in self.checks.values():
                    cb.setChecked(False)
                self.custom_pre.clear()
                self.custom_post.clear()
                self.set_resolution_fields(self.system.get("display", {}))
                self.command_edit.setPlainText("")
                self.save_custom()
                QtWidgets.QMessageBox.information(
                    self,
                    self.tx("Opciones borradas", "Options cleared"),
                    self.tx(f"Opciones locales borradas para:\n\n{self.current_game['name']}", f"Local options cleared for:\n\n{self.current_game['name']}"),
                )
                self.select_game(self.game_list.currentItem())
                return
            reopen_steam = False
            if steam_is_running():
                if not self.allow_steam_shutdown_write("borrar opciones"):
                    return
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tx("Cerrar Steam para borrar", "Close Steam to clear"),
                    self.tx(
                        "Steam esta abierto. Para evitar que sobrescriba localconfig.vdf, Proton Pilot puede cerrarlo ahora, borrar las opciones y volver a abrirlo.\n\nCerrar Steam y continuar?",
                        "Steam is open. To prevent it from overwriting localconfig.vdf, Proton Pilot can close it now, clear the options and reopen it.\n\nClose Steam and continue?",
                    ),
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                if not close_steam():
                    QtWidgets.QMessageBox.warning(
                        self,
                        self.tx("No se pudo cerrar Steam", "Could not close Steam"),
                        self.tx("No he podido cerrar Steam de forma fiable. Cierra Steam manualmente y vuelve a borrar.", "I could not close Steam reliably. Close Steam manually and clear again."),
                    )
                    return
                reopen_steam = True
            self.remember_launch_history(self.current_game_launch_options(), "antes de borrar")
            backup = set_launch_options(self.config_path, self.current_game["appid"], "")
            for cb in self.checks.values():
                cb.setChecked(False)
            self.custom_pre.clear()
            self.custom_post.clear()
            self.set_resolution_fields(self.system.get("display", {}))
            self.command_edit.setPlainText("")
            reopen_note = ""
            if reopen_steam:
                if open_steam(self.root):
                    reopen_note = self.tx("\n\nSteam se ha vuelto a abrir.", "\n\nSteam has been reopened.")
                else:
                    reopen_note = self.tx("\n\nNo he podido volver a abrir Steam. Abre Steam manualmente.", "\n\nI could not reopen Steam. Open Steam manually.")
            QtWidgets.QMessageBox.information(
                self,
                self.tx("Opciones borradas", "Options cleared"),
                self.tx(f"Opciones de lanzamiento borradas para {self.current_game['name']}.\n\nBackup:\n{backup}", f"Launch options cleared for {self.current_game['name']}.\n\nBackup:\n{backup}") + reopen_note,
            )
            self.select_game(self.game_list.currentItem())

        def reload(self):
            self.select_game(self.game_list.currentItem())

    app = QtWidgets.QApplication(sys.argv)
    win = App()
    win.show()
    return app.exec()


def zenity_main():
    if not shutil.which("zenity"):
        print("Necesitas zenity instalado.", file=sys.stderr)
        return 1

    app_config = load_app_config()
    root = steam_root(app_config)
    cfg = localconfig_path(root)
    config_text = cfg.read_text(errors="replace")
    games = installed_games(root)
    if not games:
        error("No encuentro juegos instalados en Steam.")
        return 1

    game = choose_game(games, config_text)
    current = current_launch_options(config_text, game["appid"])
    selected = choose_options(current)
    custom_pre = ""
    custom_post = ""
    if "CUSTOM" in selected:
        custom_pre, custom_post = choose_custom(game, app_config)
    if "RECOMMEND" in selected:
        rec = protondb_recommendations(game, app_config)
        z(
            [
                "--text-info",
                "--title=Recomendaciones ProtonDB",
                "--width=900",
                "--height=560",
            ],
            text=rec,
            check=False,
        )
    launch = compose_launch(selected, custom_pre, custom_post)

    edited = z(
        [
            "--entry",
            "--title=Confirmar opciones",
            "--text=Comando final para " + game["name"] + "\nPuedes editarlo antes de guardar. Dejalo vacio para borrar opciones.",
            "--entry-text=" + launch,
            "--width=900",
        ]
    )

    if steam_is_running() and not question(
        "Steam parece estar abierto.\n\n"
        "Puedes continuar, pero si Steam reescribe su configuracion al cerrar,"
        " podria perderse el cambio.\n\n"
        "Recomendado: cerrar Steam antes de guardar.\n\n"
        "Quieres continuar igualmente?"
    ):
        return 1

    backup = set_launch_options(cfg, game["appid"], edited)
    extra = ""
    if "UEHDR" in selected:
        extra = "\n\n" + set_unreal_hdr(root, game["appid"])
    if "PROTONDB" in selected:
        open_url(f"https://www.protondb.com/app/{game['appid']}")

    info(
        "Listo.\n\n"
        f"Juego: {game['name']} ({game['appid']})\n"
        f"Opciones:\n{edited or '(sin opciones)'}\n\n"
        f"Copia de seguridad:\n{backup}"
        + extra
    )
    return 0


def main():
    qt_result = qt_main()
    if qt_result is not None:
        return qt_result
    return zenity_main()


if __name__ == "__main__":
    raise SystemExit(main())
