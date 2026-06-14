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
APP_VERSION = "0.10.1"
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
}

OPTION_INFO = {
    "GAMEMODE": {
        "label": "GameMode",
        "description": "Activa GameMode para pedir al sistema perfil de rendimiento mientras el juego esta abierto.",
        "tokens": "gamemoderun",
        "recommended": True,
    },
    "MANGOHUD": {
        "label": "MangoHud",
        "description": "Muestra overlay de FPS, frametime, GPU/CPU y temperaturas. Con Gamescope se aplica como --mangoapp. Atajo ingame: Shift derecho + F12 muestra u oculta el overlay.",
        "tokens": "mangohud o gamescope --mangoapp",
        "recommended": True,
    },
    "HDR": {
        "label": "HDR via Gamescope",
        "description": "Activa salida HDR dentro de Gamescope y expone HDR a DXVK con ENABLE_GAMESCOPE_WSI=1 y DXVK_HDR=1. Necesita que Gamescope HDR/WSI este disponible.",
        "tokens": "ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope --hdr-enabled",
        "recommended": False,
        "important": True,
    },
    "WAYLAND": {
        "label": "Wine/Proton Wayland",
        "description": "Fuerza el driver Wayland de Wine/Proton. Puede mejorar integracion en Wayland, pero en algunos juegos rompe overlay o entrada.",
        "tokens": "PROTON_ENABLE_WAYLAND=1",
        "recommended": False,
    },
    "PROTONHDR": {
        "label": "Proton HDR flag",
        "description": "Activa el flag HDR propio de Proton si tu build lo soporta. Complementa, no sustituye, Gamescope HDR.",
        "tokens": "PROTON_ENABLE_HDR=1",
        "recommended": False,
        "important": True,
    },
    "FSR4": {
        "label": "FSR4 upgrade",
        "description": "Intenta actualizar FSR 3.1 a FSR 4 en builds Proton/GE/Cachy que lo soportan. Requiere juego compatible y GPU/driver adecuados; no es universal.",
        "tokens": "PROTON_FSR4_UPGRADE=1",
        "recommended": False,
    },
    "FSR4IND": {
        "label": "FSR4 indicador",
        "description": "Muestra un indicador/overlay para comprobar si el upgrade FSR4 esta funcionando, si tu Proton lo soporta.",
        "tokens": "PROTON_FSR4_INDICATOR=1",
        "recommended": False,
    },
    "GAMESCOPE": {
        "label": "Gamescope fullscreen",
        "description": "Mete el juego dentro de Gamescope a pantalla completa. Es el contenedor/compositor: habilita HDR, VRR, escalado y control de pantalla. Por si solo no fuerza una resolucion concreta.",
        "tokens": "gamescope -f --",
        "recommended": False,
        "important": True,
    },
    "REALRES": {
        "label": "Resolucion real Gamescope",
        "description": "Anade -W/-H/-w/-h/-r para que Gamescope exponga al juego la resolucion y Hz reales del monitor. Requiere Gamescope; es el ajuste de modo/resolucion, no el contenedor.",
        "tokens": "gamescope -W <monitor_w> -H <monitor_h> -w <game_w> -h <game_h> -r <hz>",
        "recommended": False,
        "important": True,
    },
    "HANDHELD800P": {
        "label": "Handheld 800p",
        "description": "Ejecuta el juego a 1280x800 dentro de Gamescope. Perfil util para Legion Go 2, SteamOS/Bazzite y juegos pesados.",
        "tokens": "gamescope -f -w 1280 -h 800 --",
        "recommended": False,
    },
    "HANDHELD1200P": {
        "label": "Handheld 1200p nativo",
        "description": "Ejecuta el juego a 1920x1200 dentro de Gamescope, pensado para la pantalla 16:10 de Legion Go 2.",
        "tokens": "gamescope -f -w 1920 -h 1200 --",
        "recommended": False,
    },
    "CAP60": {
        "label": "Limite 60 FPS",
        "description": "Anade limite simple de 60 FPS en Gamescope para bajar consumo y estabilizar frametime.",
        "tokens": "gamescope --framerate-limit 60",
        "recommended": False,
    },
    "CAP72": {
        "label": "Limite 72 FPS",
        "description": "Anade limite simple de 72 FPS en Gamescope. Encaja bien con pantallas de 144 Hz al dividir por dos.",
        "tokens": "gamescope --framerate-limit 72",
        "recommended": False,
    },
    "CAPVRR": {
        "label": "VRR cap automatico",
        "description": "Limita FPS unos pocos frames por debajo de los Hz aplicados para evitar tocar el techo VRR. Usa MangoHud porque Gamescope redondea su limitador a divisores del refresco.",
        "tokens": "MANGOHUD_CONFIG=fps_limit=<Hz-3> mangohud",
        "recommended": False,
        "caution": True,
    },
    "GSFSR": {
        "label": "Escalado Gamescope FSR",
        "description": "Usa el escalador FSR 1.0 de Gamescope para subir desde una resolucion menor. No es FSR2/3/4 del juego.",
        "tokens": "gamescope -F fsr --sharpness 5",
        "recommended": False,
    },
    "GSNIS": {
        "label": "Escalado Gamescope NIS",
        "description": "Usa NVIDIA Image Scaling en Gamescope. Puede gustar mas o menos que FSR segun juego/pantalla.",
        "tokens": "gamescope -F nis --sharpness 5",
        "recommended": False,
    },
    "ADAPTIVE": {
        "label": "Adaptive Sync",
        "description": "Pide VRR/Adaptive Sync a Gamescope si tu pantalla y sesion lo soportan.",
        "tokens": "gamescope --adaptive-sync",
        "recommended": False,
        "caution": True,
    },
    "RT": {
        "label": "Ray Tracing DXR",
        "description": "Fuerza DXR en VKD3D-Proton incluso si se considera inseguro. Hoy DXR suele activarse solo; usalo si el juego no lo expone.",
        "tokens": "VKD3D_CONFIG=dxr",
        "recommended": False,
    },
    "NODXR": {
        "label": "Desactivar DXR",
        "description": "Desactiva DXR en VKD3D-Proton. Util si el ray tracing causa cuelgues, glitches o bajones fuertes.",
        "tokens": "VKD3D_CONFIG=nodxr",
        "recommended": False,
    },
    "DX12": {
        "label": "Forzar DX12 (-dx12)",
        "description": "Anade -dx12 despues de %command%. Solo algunos juegos o motores lo reconocen.",
        "tokens": "%command% -dx12",
        "recommended": False,
    },
    "NVIDIA": {
        "label": "NVIDIA NVAPI/DLSS",
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
    ("Rendimiento y monitorizacion", ("GAMEMODE", "MANGOHUD", "CAPVRR", "CAP60", "CAP72")),
    ("Pantalla, HDR y Gamescope", ("GAMESCOPE", "REALRES", "HDR", "PROTONHDR", "ADAPTIVE")),
    ("Escalado y handheld", ("HANDHELD800P", "HANDHELD1200P", "GSFSR", "GSNIS")),
    ("Compatibilidad Proton", ("WAYLAND", "FSR4", "FSR4IND", "RT", "NODXR", "DX12", "NVIDIA", "UEHDR")),
]


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
            "command": "ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope -f --hdr-enabled --mangoapp -- gamemoderun %command%",
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
            "command": "PROTON_FSR4_UPGRADE=1 PROTON_ENABLE_WAYLAND=1 PROTON_ENABLE_HDR=1 ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope -f --hdr-enabled --mangoapp -- gamemoderun %command%",
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
            "command": "PROTON_ENABLE_HDR=1 ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope -f -w 1920 -h 1200 --hdr-enabled --mangoapp --adaptive-sync -- gamemoderun %command%",
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


def compose_launch(selected, custom_pre="", custom_post="", gamescope_res=None):
    selected = set(selected)
    gamescope_options = {"HDR", "GAMESCOPE", "REALRES", "ADAPTIVE", "HANDHELD800P", "HANDHELD1200P", "CAP60", "CAP72", "CAPVRR", "GSFSR", "GSNIS"}
    use_gamescope = bool(gamescope_options & selected)
    parts = []
    post_args = []
    if custom_pre.strip():
        parts.extend(custom_pre.strip().split())

    if "WAYLAND" in selected:
        parts.append("PROTON_ENABLE_WAYLAND=1")
    if "PROTONHDR" in selected:
        parts.append("PROTON_ENABLE_HDR=1")
    if "FSR4" in selected:
        parts.append("PROTON_FSR4_UPGRADE=1")
    if "FSR4IND" in selected:
        parts.append("PROTON_FSR4_INDICATOR=1")
    if "HDR" in selected:
        parts.extend(["ENABLE_GAMESCOPE_WSI=1", "DXVK_HDR=1"])
    if "NODXR" in selected:
        parts.append("VKD3D_CONFIG=nodxr")
    elif "RT" in selected:
        parts.append("VKD3D_CONFIG=dxr")
    if "NVIDIA" in selected:
        parts.extend(["PROTON_ENABLE_NVAPI=1", "PROTON_HIDE_NVIDIA_GPU=0", "PROTON_ENABLE_NGX_UPDATER=1"])
    if "DX12" in selected:
        post_args.append("-dx12")

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
        parts.extend(custom_post.strip().split())
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
                QGroupBox#optionGroup {
                    background: #fbfcfd;
                    border: 1px solid #d5dbe0;
                    border-radius: 8px;
                    margin-top: 18px;
                    padding-top: 12px;
                }
                QGroupBox#optionGroup::title {
                    color: #263238;
                    font-weight: 900;
                }
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
            app_version = QtWidgets.QLabel(f"Version {APP_VERSION} - perfiles de lanzamiento para Steam/Proton")
            app_version.setObjectName("version")
            title_col.addWidget(app_title)
            title_col.addWidget(app_version)
            hero_layout.addLayout(title_col, 1)
            self.steam_path_btn = QtWidgets.QPushButton("Ruta Steam")
            self.steam_path_btn.setToolTip("Seleccionar manualmente la carpeta raiz de Steam y guardarla para proximas ejecuciones.")
            self.compact_btn = QtWidgets.QPushButton("Modo compacto")
            self.compact_btn.setCheckable(True)
            self.compact_btn.setChecked(bool(self.app_config.get("compact_mode")))
            self.compact_btn.setToolTip("Reduce texto tecnico y deja la interfaz mas ligera para pantallas pequenas.")
            self.read_only_btn = QtWidgets.QPushButton("Solo lectura")
            self.read_only_btn.setCheckable(True)
            self.read_only_btn.setChecked(bool(self.app_config.get("read_only")))
            self.read_only_btn.setToolTip("Permite revisar juegos, presets y diagnosticos sin escribir cambios en Steam ni en presets.")
            hero_layout.addWidget(self.steam_path_btn)
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

            title = QtWidgets.QLabel("1. Juegos instalados")
            title.setStyleSheet("font-size: 18px; font-weight: 800;")
            left.addWidget(title)
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

            sys_box = QtWidgets.QGroupBox("Recomendaciones segun tu sistema")
            sys_layout = QtWidgets.QVBoxLayout(sys_box)
            sys_layout.setContentsMargins(8, 20, 8, 8)
            cards = QtWidgets.QGridLayout()
            cards.setHorizontalSpacing(6)
            cards.setVerticalSpacing(6)
            display = self.system.get("display", {})

            def status_card(title, value, state="neutral"):
                label = QtWidgets.QLabel(f"{title}\n{value}")
                label.setObjectName({"good": "statusGood", "warn": "statusWarn", "bad": "statusBad"}.get(state, "statusNeutral"))
                label.setWordWrap(True)
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
            cards.addWidget(status_card("Sistema", f"{self.system['os'].get('name') or 'OS'} · {self.system['session'].get('type') or 'sesion'}"), 0, 0)
            cards.addWidget(status_card("Pantalla", display_value, "good" if display.get("width") else "warn"), 0, 1)
            cards.addWidget(status_card("HDR sistema", hdr_value, hdr_state), 1, 0)
            cards.addWidget(status_card("VRR", vrr_value, vrr_state), 1, 1)
            cards.addWidget(status_card("GPU", self.system["gpu_name"], "neutral"), 2, 0)
            cards.addWidget(status_card("Herramientas", tools_value, "good"), 2, 1)
            cards.addWidget(status_card("Modo", gaming_value, "warn" if self.system.get("device", {}).get("gaming_mode") else "good"), 3, 0, 1, 2)
            cards.setColumnStretch(0, 1)
            cards.setColumnStretch(1, 1)
            sys_layout.addLayout(cards)
            self.sys_reasons = QtWidgets.QLabel("\n".join(f"- {r}" for r in recommendation_reasons(self.system)) or "No hay recomendaciones automaticas.")
            self.sys_reasons.setWordWrap(True)
            sys_layout.addWidget(self.sys_reasons)
            overview.addWidget(sys_box)

            action_box = QtWidgets.QGroupBox("Acciones frecuentes")
            action_layout = QtWidgets.QGridLayout(action_box)
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
            overview.addWidget(action_box)

            tools_box = QtWidgets.QGroupBox("Herramientas y diagnostico")
            tools_layout = QtWidgets.QGridLayout(tools_box)
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
            overview.addWidget(tools_box)
            overview.addStretch(1)

            preset_box = QtWidgets.QGroupBox("Presets del juego")
            preset_layout = QtWidgets.QVBoxLayout(preset_box)
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
            presets_view.addWidget(preset_box)
            presets_view.addStretch(1)

            opts_box = QtWidgets.QGroupBox("Opciones que se aplicaran al lanzamiento")
            opts_layout = QtWidgets.QVBoxLayout(opts_box)
            opts_layout.setContentsMargins(8, 20, 8, 8)
            opts_layout.setSpacing(6)
            self.option_group_boxes = []
            for group_index, (group_title, group_keys) in enumerate(OPTION_GROUPS):
                group = QtWidgets.QGroupBox(group_title)
                group.setObjectName("optionGroup")
                group.setCheckable(True)
                group.setChecked(group_index < 2)
                group_layout = QtWidgets.QVBoxLayout(group)
                group_layout.setContentsMargins(8, 20, 8, 8)
                group_layout.setSpacing(5)
                content = QtWidgets.QWidget()
                content_layout = QtWidgets.QVBoxLayout(content)
                content_layout.setContentsMargins(2, 2, 2, 2)
                content_layout.setSpacing(5)
                for key in group_keys:
                    meta = OPTION_INFO[key]
                    label = meta["label"]
                    desc = meta["description"]
                    recommended = meta["recommended"]
                    important = meta.get("important", False)
                    caution = meta.get("caution", False)
                    system_recommended = key in self.system_recommended
                    suffix = ""
                    if system_recommended and caution:
                        suffix = "  - sistema / probar"
                    elif system_recommended:
                        suffix = "  - sistema"
                    elif recommended:
                        suffix = "  - recomendado"
                    elif caution:
                        suffix = "  - probar"
                    elif important:
                        suffix = "  - importante"
                    text = label + suffix
                    cb = QtWidgets.QCheckBox(text)
                    cb.setObjectName("launchOption")
                    cb.setToolTip(f"{desc}\n\nAnade: {meta['tokens']}")
                    cb.setProperty("recommended", "true" if recommended else "false")
                    cb.setProperty("systemRecommended", "true" if system_recommended else "false")
                    cb.setProperty("important", "true" if important else "false")
                    cb.setProperty("caution", "true" if caution else "false")
                    cb.setProperty("optionKey", key)
                    cb.installEventFilter(self)
                    cb.stateChanged.connect(self.update_command)
                    cb.clicked.connect(lambda checked=False, k=key: self.show_option_detail(k))
                    self.checks[key] = cb
                    content_layout.addWidget(cb)
                group_layout.addWidget(content)
                group.toggled.connect(content.setVisible)
                content.setVisible(group.isChecked())
                self.option_group_boxes.append(group)
                opts_layout.addWidget(group)
            opts_layout.addStretch(1)
            options_view.addWidget(opts_box, 1)

            self.option_detail = QtWidgets.QLabel("Pasa el cursor por encima de una opcion para ver que hace y que anade al lanzamiento.")
            self.option_detail.setObjectName("optionDetail")
            self.option_detail.setWordWrap(True)
            options_view.addWidget(self.option_detail)

            res_box = QtWidgets.QGroupBox("Resolucion Gamescope")
            res_layout = QtWidgets.QGridLayout(res_box)
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
            res_layout.addWidget(QtWidgets.QLabel("Ancho"), 0, 0)
            res_layout.addWidget(self.real_width, 0, 1)
            res_layout.addWidget(QtWidgets.QLabel("Alto"), 0, 2)
            res_layout.addWidget(self.real_height, 0, 3)
            res_layout.addWidget(QtWidgets.QLabel("Hz"), 0, 4)
            res_layout.addWidget(self.real_refresh, 0, 5)
            res_layout.addWidget(self.apply_resolution_btn, 1, 0, 1, 3)
            res_layout.addWidget(self.detect_display_btn, 1, 3, 1, 3)
            for col in (1, 3, 5):
                res_layout.setColumnStretch(col, 1)
            advanced.addWidget(res_box)

            custom_box = QtWidgets.QGroupBox("Ajustes personalizados")
            custom_layout = QtWidgets.QFormLayout(custom_box)
            custom_layout.setContentsMargins(8, 20, 8, 8)
            self.custom_pre = QtWidgets.QLineEdit()
            self.custom_pre.setPlaceholderText("Antes de %command%, ej: RADV_PERFTEST=rt VKD3D_CONFIG=dxr")
            self.custom_post = QtWidgets.QLineEdit()
            self.custom_post.setPlaceholderText("Despues de %command%, ej: -dx12 -NoLauncher")
            self.custom_pre.textChanged.connect(self.update_command)
            self.custom_post.textChanged.connect(self.update_command)
            custom_layout.addRow("Antes:", self.custom_pre)
            custom_layout.addRow("Despues:", self.custom_post)
            advanced.addWidget(custom_box)

            advanced.addWidget(QtWidgets.QLabel("Comando final"))
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
            self.compact_btn.toggled.connect(self.toggle_compact_mode)
            self.read_only_btn.toggled.connect(self.toggle_read_only)
            self.add_game_btn.clicked.connect(self.add_manual_game)
            self.edit_game_btn.clicked.connect(self.edit_manual_game)
            self.remove_game_btn.clicked.connect(self.remove_manual_game)
            self.recommend_btn.clicked.connect(self.show_recommendations)
            self.open_protondb_btn.clicked.connect(self.open_protondb)
            self.apply_system_btn.clicked.connect(self.apply_system_recommended)
            self.apply_command_btn.clicked.connect(self.apply_prepared_command)
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

            self.apply_compact_mode()
            self.set_action_availability()
            if self.game_list.count():
                self.game_list.setCurrentRow(0)

        def config_text(self):
            return self.config_path.read_text(errors="replace")

        def steam_config_text(self):
            return self.steam_config_path.read_text(errors="replace")

        def choose_steam_path(self):
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Selecciona la carpeta raiz de Steam",
                str(self.root),
            )
            if not path:
                return
            if not valid_steam_root(path):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Ruta no valida",
                    "Esa carpeta no parece una raiz de Steam. Debe contener la carpeta steamapps.",
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
                    "Ruta Steam guardada",
                    f"Usando Steam desde:\n\n{self.root}\n\nSe recordara en la proxima ejecucion.",
                )
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, "Error al cambiar Steam", str(exc))

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
                "Modo solo lectura",
                f"Solo lectura esta activo. Desactivalo para {action}.",
            )
            return False

        def allow_steam_shutdown_write(self, action):
            if self.system.get("device", {}).get("gaming_mode") and steam_is_running():
                QtWidgets.QMessageBox.warning(
                    self,
                    "Gaming Mode detectado",
                    f"Steam esta abierto y parece que estas en Gaming Mode. Por seguridad no voy a cerrar Steam para {action}.\n\n"
                    "Haz este cambio desde Desktop Mode o cierra Steam manualmente primero.",
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
                getattr(self, "sys_reasons", None),
                getattr(self, "option_detail", None),
            ):
                if widget:
                    widget.setVisible(not compact)
            if getattr(self, "command_edit", None):
                self.command_edit.setMaximumHeight(54 if compact else 78)
            if getattr(self, "current_label", None) and self.current_game:
                self.current_label.setText(f"Opciones guardadas: {short_command(self.current_game_launch_options(), 150 if compact else 220)}")

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
                label = Path(proton).parent.name if proton else "sin Proton"
                self.proton_status_label.setText(f"Proton externo: {label}")
                self.proton_combo.addItem(label, proton)
                self.proton_combo.blockSignals(False)
                return
            current = self.current_game_compat_tool()
            recommended = recommended_proton_tool(self.system, self.proton_tools)
            current_label = compact_proton_label(compat_tool_display_name(current, self.proton_tools))
            rec_label = compact_proton_label(compat_tool_display_name(recommended, self.proton_tools)) if recommended else "sin recomendacion"
            self.proton_status_label.setText(f"Proton actual: {current_label}\nRecomendada: {rec_label}")
            self.proton_combo.addItem("Steam por defecto", "")
            if current and not any(tool["compat"] == current for tool in self.proton_tools):
                self.proton_combo.addItem(f"Actual no detectada: {current}", current)
            for tool in self.proton_tools:
                suffix = "  - recomendada" if tool["compat"] == recommended else ""
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
                QtWidgets.QMessageBox.information(self, "Proton sin cambios", "La version de Proton seleccionada ya esta aplicada para este juego.")
                return
            selected_label = compat_tool_display_name(selected, self.proton_tools)
            current_label = compat_tool_display_name(current, self.proton_tools)
            reply = QtWidgets.QMessageBox.question(
                self,
                "Aplicar Proton",
                f"Cambiar Proton para este juego?\n\nJuego: {self.current_game['name']}\nActual: {current_label}\nNuevo: {selected_label}\n\nSteam puede cerrarse para evitar que sobrescriba config.vdf.",
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            reopen_steam = False
            if steam_is_running():
                if not self.allow_steam_shutdown_write("aplicar Proton"):
                    return
                close_reply = QtWidgets.QMessageBox.question(
                    self,
                    "Cerrar Steam para aplicar Proton",
                    "Steam esta abierto. Para guardar la version de Proton por juego con seguridad, Proton Pilot puede cerrar Steam y volver a abrirlo.\n\nCerrar Steam y continuar?",
                )
                if close_reply != QtWidgets.QMessageBox.Yes:
                    return
                if not close_steam():
                    QtWidgets.QMessageBox.warning(self, "No se pudo cerrar Steam", "Cierra Steam manualmente y vuelve a aplicar Proton.")
                    return
                reopen_steam = True
            self.remember_proton_history(current, "antes de cambiar Proton")
            backup = set_compat_tool(self.steam_config_path, self.current_game["appid"], selected)
            reopen_note = ""
            if reopen_steam:
                reopen_note = "\n\nSteam se ha vuelto a abrir." if open_steam(self.root) else "\n\nNo he podido volver a abrir Steam. Abre Steam manualmente."
            self.update_proton_selector()
            QtWidgets.QMessageBox.information(
                self,
                "Proton aplicado",
                f"Proton guardado para {self.current_game['name']}:\n\n{selected_label}\n\nBackup:\n{backup}{reopen_note}",
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
                self.dirty_label.setText("Cambios pendientes: el comando preparado no coincide con lo guardado para este juego.")
            else:
                self.dirty_label.setText("Sin cambios pendientes: lo preparado coincide con lo guardado.")

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
            lines.append(f"Juego: {self.current_game['name']}")
            lines.append(f"Destino: {'perfil externo' if self.current_game.get('external') else 'Steam localconfig.vdf'}")
            if self.current_game.get("external"):
                lines.append(f"Proton: {Path(self.current_game.get('proton', '')).parent.name or 'no definido'}")
            else:
                lines.append(f"Proton actual: {compat_tool_display_name(self.current_game_compat_tool(), self.proton_tools)}")
            lines.append(f"Steam abierto: {'si' if steam_is_running() else 'no'}")
            lines.append(f"Modo Gaming: {'detectado' if system.get('device', {}).get('gaming_mode') else 'no detectado'}")
            lines.append(f"Gamescope: {'disponible' if system['tools'].get('gamescope') else 'no disponible'}")
            lines.append(f"GameMode: {'disponible' if system['tools'].get('gamemoderun') else 'no disponible'}")
            lines.append(f"MangoHud: {'disponible' if system['tools'].get('mangohud') else 'no disponible'}")
            lines.append(f"HDR sistema: {'activo' if display_hdr_enabled(display) else (display.get('hdr') or 'no detectado')}")
            lines.append(f"VRR: {(display.get('vrr') or 'no detectado')}")
            if display.get("width") and display.get("height"):
                lines.append(f"Monitor: {display.get('name') or 'principal'} {display.get('width')}x{display.get('height')}@{display.get('refresh') or '?'}")
            res = self.gamescope_resolution()
            if selected & {"REALRES", "CAPVRR"}:
                lines.append(f"Resolucion Gamescope aplicada: {res.get('width') or '?'}x{res.get('height') or '?'}@{res.get('refresh') or '?'}")
            warnings = []
            if "HDR" in selected and not display_hdr_enabled(display):
                warnings.append("HDR esta marcado, pero el sistema no informa HDR activo.")
            if "HDR" in selected and not system.get("gamescope_wsi"):
                warnings.append("HDR via Gamescope necesita Gamescope WSI; no lo he detectado.")
            if selected & {"HDR", "GAMESCOPE", "REALRES", "ADAPTIVE"} and not system["tools"].get("gamescope"):
                warnings.append("Hay opciones Gamescope marcadas, pero gamescope no esta disponible.")
            if selected & {"REALRES", "CAPVRR"} and not int(res.get("width") or 0):
                warnings.append("Resolucion real/VRR cap estan marcados, pero no hay resolucion aplicada.")
            if "GAMEMODE" in selected and not system["tools"].get("gamemoderun"):
                warnings.append("GameMode esta marcado, pero gamemoderun no esta disponible.")
            if {"CAPVRR", "MANGOHUD"} & selected and not system["tools"].get("mangohud"):
                warnings.append("MangoHud/VRR cap requieren mangohud, pero no esta disponible.")
            if "NVIDIA" in selected and system.get("gpu") != "nvidia":
                warnings.append("NVAPI/DLSS esta marcado en una GPU no NVIDIA.")
            if "FSR4" in selected and system.get("gpu") != "amd":
                warnings.append("FSR4 upgrade suele tener sentido principalmente en AMD compatible.")
            if "CAPVRR" in selected and not display_vrr_available(display):
                warnings.append("VRR cap esta marcado, pero VRR no aparece disponible.")
            if "%command%" not in command:
                warnings.append("El comando no contiene %command%; Steam podria no lanzar el juego como esperas.")
            if warnings:
                lines.extend(["", "Avisos:"])
                lines.extend(f"- {warning}" for warning in warnings)
            else:
                lines.extend(["", "Diagnostico: no veo avisos importantes."])
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
                details.append(f"{total} reportes")
            if confidence:
                details.append(f"confianza {confidence}")
            if best and str(best).lower() != tier:
                details.append(f"mejor {str(best).upper()}")
            cache_age = protondb_cache_age_label(self.app_config, self.current_game["appid"]) if self.current_game else ""
            if cache_age:
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
            source = "Externo" if self.current_game.get("external") else "Steam"
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
            self.current_label.setText(f"Opciones guardadas: {short_command(current, 150 if self.app_config.get('compact_mode') else 220)}")
            self.set_action_availability()
            self.update_proton_selector()
            flags = detect_flags(current)
            custom = self.app_config.setdefault("custom", {}).get(self.current_game["appid"], {})
            saved_side_effects = set(custom.get("side_effect_options", []))
            for key, cb in self.checks.items():
                cb.blockSignals(True)
                cb.setChecked(flags.get(key, False) or key in saved_side_effects)
                cb.setProperty("active", "true" if flags.get(key, False) else "false")
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
            self.update_dirty_state()

        def add_manual_game(self):
            if not self.write_guard("anadir juegos"):
                return
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Añadir juego")
            dialog.resize(620, 260)
            outer = QtWidgets.QVBoxLayout(dialog)
            tabs = QtWidgets.QTabWidget()
            outer.addWidget(tabs)

            steam_tab = QtWidgets.QWidget()
            steam_layout = QtWidgets.QFormLayout(steam_tab)
            name_edit = QtWidgets.QLineEdit()
            appid_edit = QtWidgets.QLineEdit()
            appid_edit.setPlaceholderText("Ej: 1172710")
            steam_layout.addRow("Nombre:", name_edit)
            steam_layout.addRow("AppID Steam:", appid_edit)
            tabs.addTab(steam_tab, "Steam AppID")

            external_tab = QtWidgets.QWidget()
            external_layout = QtWidgets.QFormLayout(external_tab)
            external_name = QtWidgets.QLineEdit()
            exe_row = QtWidgets.QHBoxLayout()
            exe_edit = QtWidgets.QLineEdit()
            exe_btn = QtWidgets.QPushButton("Buscar ejecutable")
            exe_row.addWidget(exe_edit, 1)
            exe_row.addWidget(exe_btn)
            proton_combo = QtWidgets.QComboBox()
            tools = proton_tools(self.root)
            for tool in tools:
                proton_combo.addItem(tool["name"], tool["path"])
            if not tools:
                proton_combo.addItem("No encuentro Proton instalado", "")
            proton_row = QtWidgets.QHBoxLayout()
            proton_btn = QtWidgets.QPushButton("Buscar Proton")
            proton_row.addWidget(proton_combo, 1)
            proton_row.addWidget(proton_btn)
            add_to_steam = QtWidgets.QCheckBox("Añadir tambien a la biblioteca de Steam")
            add_to_steam.setToolTip("Crea un acceso directo en shortcuts.vdf. Steam debe reiniciarse para verlo.")
            external_layout.addRow("Nombre:", external_name)
            external_layout.addRow("Ejecutable:", exe_row)
            external_layout.addRow("Proton:", proton_row)
            external_layout.addRow("", add_to_steam)
            tabs.addTab(external_tab, "Ejecutable Proton")

            def browse_exe():
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    dialog,
                    "Selecciona ejecutable",
                    str(HOME),
                    "Ejecutables (*.exe *.msi);;Todos los archivos (*)",
                )
                if path:
                    exe_edit.setText(path)
                    if not external_name.text().strip():
                        external_name.setText(Path(path).stem)

            exe_btn.clicked.connect(browse_exe)

            def browse_proton():
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    dialog,
                    "Selecciona el binario proton",
                    str(HOME),
                    "Proton (proton);;Todos los archivos (*)",
                )
                if not path:
                    folder = QtWidgets.QFileDialog.getExistingDirectory(dialog, "O selecciona una carpeta de Proton", str(HOME))
                    path = str(Path(folder) / "proton") if folder else ""
                if not path:
                    return
                proton_path = Path(path)
                if proton_path.is_dir():
                    proton_path = proton_path / "proton"
                if not proton_path.exists():
                    QtWidgets.QMessageBox.warning(dialog, "Proton no encontrado", "La ruta seleccionada no contiene un binario proton.")
                    return
                label = f"Personalizado: {proton_path.parent.name}"
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
                    QtWidgets.QMessageBox.warning(self, "Faltan datos", "Necesito nombre y AppID para añadir el juego.")
                    return
                if not re.fullmatch(r"\d+", appid):
                    QtWidgets.QMessageBox.warning(self, "AppID no valido", "El AppID de Steam debe ser numerico.")
                    return
                manual_games = self.app_config.setdefault("manual_games", [])
                for game in self.games:
                    if game["appid"] == appid:
                        QtWidgets.QMessageBox.information(self, "Ya existe", "Ese AppID ya esta en la lista.")
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
                QtWidgets.QMessageBox.warning(self, "Faltan datos", "Necesito nombre, ejecutable y una version de Proton.")
                return
            if not Path(exe).exists():
                QtWidgets.QMessageBox.warning(self, "Ejecutable no encontrado", "La ruta seleccionada no existe.")
                return
            game_id = external_game_id(name, exe)
            for game in self.games:
                if game["appid"] == game_id:
                    QtWidgets.QMessageBox.information(self, "Ya existe", "Ese ejecutable ya esta en la lista.")
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
                        "Cerrar Steam para anadir acceso directo",
                        "Steam esta abierto. Para anadir el juego externo a la biblioteca sin que Steam sobrescriba shortcuts.vdf, Proton Pilot puede cerrarlo ahora y volver a abrirlo despues.\n\nCerrar Steam y continuar?",
                    )
                    if reply == QtWidgets.QMessageBox.Yes:
                        if not close_steam():
                            QtWidgets.QMessageBox.warning(
                                self,
                                "No se pudo cerrar Steam",
                                "No he podido cerrar Steam de forma fiable. Anado el perfil local, pero no el acceso directo de Steam.",
                            )
                        else:
                            reopen_steam = True
                    else:
                        QtWidgets.QMessageBox.information(
                            self,
                            "Acceso directo omitido",
                            "Anado el perfil local, pero no escribo shortcuts.vdf mientras Steam esta abierto.",
                        )
                if not steam_is_running():
                    try:
                        result = add_steam_shortcut(self.root, name, exe, "")
                        external_payload["steam_shortcut"] = True
                        external_payload["steam_shortcut_appid"] = result.get("appid", "")
                        shortcut_note = f"\n\nAcceso directo anadido a Steam:\n{result['path']}"
                    except Exception as exc:
                        shortcut_note = f"\n\nNo he podido anadirlo a Steam: {exc}"
                if reopen_steam:
                    if open_steam(self.root):
                        shortcut_note += "\nSteam se ha vuelto a abrir."
                    else:
                        shortcut_note += "\nNo he podido volver a abrir Steam; abrelo manualmente."
            self.app_config.setdefault("external_games", []).append(external_payload)
            save_app_config(self.app_config)
            self.populate_games(game_id)
            if shortcut_note:
                QtWidgets.QMessageBox.information(self, "Juego externo anadido", f"Perfil anadido a Proton Pilot.{shortcut_note}")

        def edit_manual_game(self):
            if not self.write_guard("editar juegos manuales"):
                return
            if not self.current_game or not self.current_game.get("manual"):
                return
            if self.current_game.get("external"):
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle("Editar juego externo")
                layout = QtWidgets.QFormLayout(dialog)
                name_edit = QtWidgets.QLineEdit(self.current_game.get("name", ""))
                exe_row = QtWidgets.QHBoxLayout()
                exe_edit = QtWidgets.QLineEdit(self.current_game.get("exe", ""))
                exe_btn = QtWidgets.QPushButton("Buscar")
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
                    proton_combo.addItem(f"Actual: {Path(current_proton).parent.name}", current_proton)
                    proton_combo.setCurrentIndex(proton_combo.count() - 1)
                proton_btn = QtWidgets.QPushButton("Buscar Proton")
                proton_row = QtWidgets.QHBoxLayout()
                proton_row.addWidget(proton_combo, 1)
                proton_row.addWidget(proton_btn)
                layout.addRow("Nombre:", name_edit)
                layout.addRow("Ejecutable:", exe_row)
                layout.addRow("Proton:", proton_row)

                def browse_exe():
                    path, _ = QtWidgets.QFileDialog.getOpenFileName(
                        dialog,
                        "Selecciona ejecutable",
                        str(Path(exe_edit.text()).parent if exe_edit.text() else HOME),
                        "Ejecutables (*.exe *.msi);;Todos los archivos (*)",
                    )
                    if path:
                        exe_edit.setText(path)

                def browse_proton():
                    path, _ = QtWidgets.QFileDialog.getOpenFileName(dialog, "Selecciona el binario proton", str(HOME), "Proton (proton);;Todos los archivos (*)")
                    if not path:
                        folder = QtWidgets.QFileDialog.getExistingDirectory(dialog, "O selecciona una carpeta de Proton", str(HOME))
                        path = str(Path(folder) / "proton") if folder else ""
                    if not path:
                        return
                    proton_path = Path(path)
                    if proton_path.is_dir():
                        proton_path = proton_path / "proton"
                    if not proton_path.exists():
                        QtWidgets.QMessageBox.warning(dialog, "Proton no encontrado", "La ruta seleccionada no contiene un binario proton.")
                        return
                    proton_combo.addItem(f"Personalizado: {proton_path.parent.name}", str(proton_path))
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
                    QtWidgets.QMessageBox.warning(self, "Datos no validos", "Necesito nombre, ejecutable y Proton.")
                    return
                if not Path(exe).exists():
                    QtWidgets.QMessageBox.warning(self, "Ejecutable no encontrado", "La ruta seleccionada no existe.")
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
            dialog.setWindowTitle("Editar juego manual")
            layout = QtWidgets.QFormLayout(dialog)
            name_edit = QtWidgets.QLineEdit(self.current_game.get("name", ""))
            appid_edit = QtWidgets.QLineEdit(self.current_game.get("appid", ""))
            layout.addRow("Nombre:", name_edit)
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
                QtWidgets.QMessageBox.warning(self, "Datos no validos", "Necesito un nombre y un AppID numerico.")
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
                "Quitar juego manual",
                f"Quitar este juego de Proton Pilot?\n\n{self.current_game['name']}\n\nNo borra archivos del juego ni desinstala nada.",
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

        def selected_keys(self):
            return [key for key, cb in self.checks.items() if cb.isChecked()]

        def eventFilter(self, obj, event):
            if event.type() == QtCore.QEvent.Enter and isinstance(obj, QtWidgets.QCheckBox):
                key = obj.property("optionKey")
                if key:
                    self.show_option_detail(key)
            return super().eventFilter(obj, event)

        def show_option_detail(self, key):
            meta = OPTION_INFO[key]
            if key in self.system_recommended:
                recommended = "Recomendada para tu sistema; el boton Marcar recomendadas la activara."
            elif meta["recommended"]:
                recommended = "Recomendada por defecto"
            elif meta.get("caution"):
                recommended = "Puede beneficiar, pero conviene probarla por juego. Por eso aparece en rojo."
            elif meta.get("important"):
                recommended = "Opcion importante: depende del juego, monitor y objetivo."
            else:
                recommended = "Opcional / por juego"
            extra = ""
            if key == "GAMESCOPE":
                extra = "\nDiferencia clave: Gamescope fullscreen crea el contenedor. Resolucion real Gamescope decide que resolucion/Hz se exponen dentro de ese contenedor."
            elif key == "REALRES":
                extra = "\nDiferencia clave: no sustituye a Gamescope fullscreen; le anade el modo nativo del monitor (-W/-H/-w/-h/-r)."
            elif key == "MANGOHUD":
                extra = "\nAtajo ingame: Shift derecho + F12 muestra u oculta el overlay. Shift izquierdo + F1 alterna el limite FPS de MangoHud."
            self.option_detail.setText(
                f"{meta['label']}\n\n"
                f"{meta['description']}\n\n"
                f"Anade: {meta['tokens']}\n"
                f"Estado: {recommended}"
                f"{extra}"
            )

        def update_command(self):
            command = compose_launch(self.selected_keys(), self.custom_pre.text(), self.custom_post.text(), self.gamescope_resolution())
            self.command_edit.setPlainText(command)

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
                self.preset_combo.addItem("Sin presets guardados", "")
            else:
                for name in sorted(shared):
                    self.preset_combo.addItem(f"Compartido: {name}", preset_ref("shared", name))
                for name in sorted(game):
                    self.preset_combo.addItem(f"Juego: {name}", preset_ref("game", name))
            self.preset_combo.blockSignals(False)
            self.apply_preset_btn.setEnabled(False)
            if not shared and not game:
                self.set_preset_choice_status("No hay presets guardados para cargar.", pending=False)

        def preset_command(self, preset):
            if not preset:
                return ""
            if "options" in preset:
                return compose_launch(
                    preset.get("options", []),
                    preset.get("custom_pre", ""),
                    preset.get("custom_post", ""),
                    preset.get("gamescope_res", {}),
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
                self.set_preset_status(f"Preset actual aplicado: {name}", pending=False)
                self.set_preset_choice_status(f"Seleccionado y aplicado: {name}", applied=True)
            else:
                self.preset_combo.setCurrentIndex(-1)
                if normalize_command(command):
                    self.set_preset_status("Sin preset aplicado: las opciones actuales no coinciden con ningun preset guardado.", pending=True)
                else:
                    self.set_preset_status("Sin preset aplicado todavia.", pending=True)
                self.set_preset_choice_status("Elige un preset para cargarlo. Al elegir uno distinto, aparecera como pendiente aqui.", pending=False)
            self.preset_combo.blockSignals(False)
            self.apply_preset_btn.setEnabled(False)
            return ref

        def current_preset_payload(self):
            command = compose_launch(self.selected_keys(), self.custom_pre.text(), self.custom_post.text(), self.gamescope_resolution())
            self.command_edit.setPlainText(command)
            return {
                "options": self.selected_keys(),
                "custom_pre": self.custom_pre.text(),
                "custom_post": self.custom_post.text(),
                "gamescope_res": self.gamescope_resolution(),
                "command": command,
            }

        def generated_command_from_controls(self):
            return compose_launch(self.selected_keys(), self.custom_pre.text(), self.custom_post.text(), self.gamescope_resolution())

        def command_was_edited_manually(self, command):
            return normalize_command(command) != normalize_command(self.generated_command_from_controls())

        def maybe_create_manual_command_preset(self, command):
            if not self.current_game or not self.command_was_edited_manually(command):
                return ""
            default_name = "Custom manual " + _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            name, ok = QtWidgets.QInputDialog.getText(
                self,
                "Crear preset custom",
                "El Comando final fue editado a mano. Nombre para guardar este preset custom:",
                text=default_name,
            )
            name = name.strip()
            if not ok or not name:
                return None
            presets = self.game_presets()
            if name in presets:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Sobreescribir preset custom",
                    f"Ya existe un preset del juego llamado:\n\n{name}\n\nSobreescribirlo con el comando actual?",
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
            self.set_preset_status(f"Preset custom aplicado: {name}", pending=False)
            self.set_preset_choice_status(f"Seleccionado y aplicado: {name}", applied=True)
            return name

        def confirm_manual_command_save(self, command, external=False):
            target = "perfil local de Proton Pilot" if external else "opciones de lanzamiento en Steam"
            if self.command_was_edited_manually(command):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Guardar comando manual",
                    f"Guardar el Comando final editado a mano como preset custom y escribirlo en {target}?\n\n"
                    f"{self.diagnostic_text(command)}",
                )
                return reply == QtWidgets.QMessageBox.Yes
            reply = QtWidgets.QMessageBox.question(
                self,
                "Comando generado por controles",
                "El Comando final coincide con las casillas y campos de Proton Pilot.\n\n"
                "Este boton esta pensado para comandos escritos a mano. Para un perfil normal suele ser mas claro usar Crear nuevo preset, Actualizar preset o Aplicar preset.\n\n"
                f"Guardar este comando igualmente en {target}?\n\n{self.diagnostic_text(command)}",
            )
            return reply == QtWidgets.QMessageBox.Yes

        def load_selected_preset(self):
            ref = self.preset_combo.currentData()
            if not ref:
                self.apply_preset_btn.setEnabled(False)
                self.set_preset_choice_status("Elige un preset para cargarlo.", pending=False)
                return "", ""
            scope, name, preset = self.preset_from_ref(ref)
            if not preset:
                self.apply_preset_btn.setEnabled(False)
                self.set_preset_choice_status("Ese preset ya no existe.", pending=True)
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
                self.set_preset_status(f"Preset actual aplicado: {name}", pending=False)
                self.set_preset_choice_status(f"Seleccionado y aplicado: {name}", applied=True)
                self.apply_preset_btn.setEnabled(False)
            else:
                applied_name = self.current_applied_preset_name()
                if applied_name:
                    self.set_preset_status(f"Preset actual aplicado: {applied_name}", pending=False)
                else:
                    self.set_preset_status("Sin preset aplicado: el preset elegido aun no se ha escrito en el juego.", pending=True)
                self.set_preset_choice_status(f"Pendiente de aplicar: {name}", pending=True)
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
                "Aplicar preset",
                f"Aplicar este preset como opciones de lanzamiento?\n\n{name}\n\n{self.diagnostic_text(command)}",
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
            name, ok = QtWidgets.QInputDialog.getText(self, "Crear nuevo preset", "Nombre del preset compartido:")
            name = name.strip()
            if not ok or not name:
                return
            presets = self.shared_presets()
            if name in presets:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Sobreescribir preset compartido",
                    f"Ya existe un preset compartido llamado:\n\n{name}\n\nQuieres sobreescribirlo con las opciones actuales?",
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
            else:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Crear nuevo preset",
                    f"Crear un preset compartido llamado:\n\n{name}\n\ncon las opciones actuales?",
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
            presets[name] = self.current_preset_payload()
            save_app_config(self.app_config)
            self.refresh_presets()
            index = self.preset_combo.findData(preset_ref("shared", name))
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            QtWidgets.QMessageBox.information(self, "Preset creado", f"Preset compartido creado:\n\n{name}")

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
                "Actualizar preset",
                f"Actualizar el preset seleccionado con las opciones actuales?\n\n{name}\n\nOrigen: {'compartido' if scope == 'shared' else 'del juego'}\n\nSe sobreescribira su contenido.",
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
            QtWidgets.QMessageBox.information(self, "Preset actualizado", f"Preset actualizado:\n\n{name}")

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
                "Borrar preset",
                f"Borrar definitivamente este preset?\n\n{name}\n\nOrigen: {'compartido' if scope == 'shared' else 'del juego'}\n\nEsta accion no borra las opciones ya guardadas en Steam.",
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            if scope == "shared":
                self.shared_presets().pop(name, None)
            else:
                self.game_presets().pop(name, None)
            save_app_config(self.app_config)
            self.refresh_presets()
            QtWidgets.QMessageBox.information(self, "Preset borrado", f"Preset borrado:\n\n{name}")

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
                QtWidgets.QMessageBox.warning(self, "No se puede lanzar", "Faltan datos del ejecutable o de Proton.")
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
            dialog.setWindowTitle("Comparar opciones")
            dialog.resize(980, 520)
            layout = QtWidgets.QVBoxLayout(dialog)
            status = QtWidgets.QLabel(
                "Hay cambios pendientes." if self.has_pending_command_changes() else "El comando preparado coincide con lo guardado."
            )
            status.setWordWrap(True)
            layout.addWidget(status)
            cols = QtWidgets.QHBoxLayout()
            layout.addLayout(cols, 1)
            saved = QtWidgets.QPlainTextEdit()
            saved.setReadOnly(True)
            saved.setPlainText(self.current_game_launch_options() or "(sin opciones guardadas)")
            prepared = QtWidgets.QPlainTextEdit()
            prepared.setReadOnly(True)
            prepared.setPlainText(self.prepared_command() or "(sin comando preparado)")
            saved_box = QtWidgets.QGroupBox("Guardado ahora")
            saved_layout = QtWidgets.QVBoxLayout(saved_box)
            saved_layout.addWidget(saved)
            prepared_box = QtWidgets.QGroupBox("Preparado en pantalla")
            prepared_layout = QtWidgets.QVBoxLayout(prepared_box)
            prepared_layout.addWidget(prepared)
            cols.addWidget(saved_box)
            cols.addWidget(prepared_box)
            close_btn = QtWidgets.QPushButton("Cerrar")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn, 0, QtCore.Qt.AlignRight)
            dialog.exec()

        def show_history_dialog(self):
            if not self.current_game:
                return
            appid = self.current_game["appid"]
            history = self.app_config.setdefault("launch_history", {}).get(appid, [])
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Historial de opciones")
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
            preview.setPlaceholderText("Selecciona una entrada para ver el comando.")
            layout.addWidget(preview, 1)
            buttons = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons)
            close_btn = QtWidgets.QPushButton("Cerrar")
            restore_btn = QtWidgets.QPushButton("Restaurar seleccionado")
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
                    "Restaurar historial",
                    "Restaurar este comando como opciones de lanzamiento del juego?\n\n"
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
                preview.setPlainText("No hay historial guardado para este juego todavia.")
            dialog.exec()

        def apply_prepared_command(self):
            if not self.current_game:
                return
            if not self.write_guard("aplicar cambios preparados"):
                return
            command = self.prepared_command()
            reply = QtWidgets.QMessageBox.question(
                self,
                "Aplicar cambios preparados",
                "Escribir ahora el comando preparado como opciones de lanzamiento?\n\n"
                + self.diagnostic_text(command),
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            self.save(confirm=False)

        def display_diagnostic_text(self):
            display = self.system.get("display", {})
            lines = [
                "Estado detectado de pantalla:",
                f"- Monitor: {display.get('name') or 'no detectado'}",
                f"- Resolucion: {display.get('width') or '?'}x{display.get('height') or '?'}@{display.get('refresh') or '?'}",
                f"- HDR KDE: {'activo' if display_hdr_enabled(display) else (display.get('hdr') or 'no detectado')}",
                f"- WCG: {display.get('wide_color') or 'no detectado'}",
                f"- VRR KDE: {display.get('vrr') or 'no detectado'}",
                f"- Gamescope: {'disponible' if self.system['tools'].get('gamescope') else 'no disponible'}",
                f"- Gamescope WSI: {'detectado' if self.system.get('gamescope_wsi') else 'no detectado'}",
                "",
                "Lectura practica:",
            ]
            if display_hdr_enabled(display) and self.system.get("gamescope_wsi"):
                lines.append("- HDR via Gamescope deberia estar disponible para juegos compatibles.")
            elif not display_hdr_enabled(display):
                lines.append("- HDR no aparece activo en KDE. Activalo en la pantalla antes de usar presets HDR.")
            elif not self.system.get("gamescope_wsi"):
                lines.append("- HDR esta activo, pero no detecto Gamescope WSI; DXVK_HDR puede no exponerse al juego.")
            if display_vrr_available(display):
                lines.append("- VRR aparece disponible. Adaptive Sync y VRR cap pueden ayudar, pero conviene validar por juego.")
            else:
                lines.append("- VRR no aparece disponible; Adaptive Sync puede no tener efecto.")
            if self.system.get("device", {}).get("gaming_mode"):
                lines.append("- Gaming Mode detectado: evita cambios que cierren Steam desde aqui; mejor aplicar en Desktop Mode.")
            return "\n".join(lines)

        def show_display_diagnostics(self):
            QtWidgets.QMessageBox.information(self, "Diagnostico HDR/VRR", self.display_diagnostic_text())

        def show_proton_history_dialog(self):
            if not self.current_game or self.current_game.get("external"):
                return
            appid = self.current_game["appid"]
            history = self.app_config.setdefault("proton_history", {}).get(appid, [])
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Historial Proton")
            dialog.resize(760, 420)
            layout = QtWidgets.QVBoxLayout(dialog)
            list_widget = QtWidgets.QListWidget()
            for entry in history:
                label = f"{entry.get('timestamp', '')} · {entry.get('label') or 'Steam por defecto'} · {entry.get('reason', '')}"
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, entry)
                list_widget.addItem(item)
            layout.addWidget(list_widget, 1)
            buttons = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons)
            close_btn = QtWidgets.QPushButton("Cerrar")
            restore_btn = QtWidgets.QPushButton("Restaurar Proton")
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
                    "Restaurar Proton",
                    f"Restaurar esta version para {self.current_game['name']}?\n\n{label}",
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                index = self.proton_combo.findData(tool)
                if index < 0:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Proton no disponible",
                        "Esa version ya no aparece instalada. Instalala o elige una version disponible.",
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
                list_widget.addItem("No hay cambios de Proton registrados para este juego.")
            dialog.exec()

        def register_appimage_shortcut(self):
            if not self.write_guard("registrar Proton Pilot en Steam"):
                return
            appimage = running_appimage_path()
            if not appimage:
                QtWidgets.QMessageBox.information(
                    self,
                    "AppImage no encontrado",
                    "No encuentro un AppImage ejecutable de Proton Pilot. Ejecuta el AppImage o genera uno con build-appimage.sh.",
                )
                return
            if steam_is_running():
                if not self.allow_steam_shutdown_write("registrar Proton Pilot en Steam"):
                    return
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Cerrar Steam para registrar AppImage",
                    "Para escribir shortcuts.vdf con seguridad, Proton Pilot puede cerrar Steam y volver a abrirlo despues.\n\nCerrar Steam y continuar?",
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                if not close_steam():
                    QtWidgets.QMessageBox.warning(self, "No se pudo cerrar Steam", "Cierra Steam manualmente y vuelve a intentarlo.")
                    return
                reopen = True
            else:
                reopen = False
            try:
                result = add_steam_shortcut(self.root, APP_NAME, str(appimage), "")
                reopen_note = ""
                if reopen:
                    reopen_note = "\n\nSteam se ha vuelto a abrir." if open_steam(self.root) else "\n\nNo he podido volver a abrir Steam; abrelo manualmente."
                QtWidgets.QMessageBox.information(
                    self,
                    "AppImage registrado",
                    f"Proton Pilot se ha anadido como aplicacion externa de Steam.\n\n{result['path']}{reopen_note}",
                )
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, "Error al registrar AppImage", str(exc))

        def check_for_updates(self):
            try:
                info = latest_release_info()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No se pudo consultar GitHub",
                    f"No he podido consultar la ultima release de GitHub.\n\n{exc}",
                )
                return
            if info.get("missing"):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Sin releases publicadas",
                    "GitHub responde correctamente, pero este repo todavia no tiene ninguna Release publicada.\n\n"
                    "Cuando publiques una release con AppImage, este boton podra compararla con la version instalada.\n\n"
                    "Abrir la pagina de releases?",
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    open_url(info.get("url"))
                return
            tag = info.get("tag") or "desconocida"
            message = f"Version instalada: {APP_VERSION}\nUltima release: {tag}"
            if info.get("asset_name"):
                message += f"\nAppImage: {info['asset_name']}"
            if normalize_command(tag) and tag != APP_VERSION:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Actualizacion disponible",
                    message + "\n\nAbrir la pagina de descarga?",
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    open_url(info.get("asset_url") or info.get("url"))
            else:
                QtWidgets.QMessageBox.information(self, "Sin actualizacion detectada", message)

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
            dialog.setWindowTitle("Asistente de perfil")
            layout = QtWidgets.QVBoxLayout(dialog)
            label = QtWidgets.QLabel("Elige un objetivo. Proton Pilot marcara opciones razonables para revisarlas antes de aplicar.")
            label.setWordWrap(True)
            layout.addWidget(label)
            choices = [
                ("performance", "Rendimiento equilibrado"),
                ("desktop_hdr_vrr", "Escritorio HDR/VRR"),
                ("hdr", "HDR"),
                ("vrr", "VRR estable"),
                ("rt", "Ray Tracing / DX12"),
                ("handheld", "Handheld / bateria"),
                ("legion_go_2", "Legion Go 2 / Bazzite"),
                ("legion_go_s", "Legion Go S / SteamOS"),
                ("safe", "Minimo seguro"),
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
                labels = [OPTION_INFO[key]["label"] for key in OPTION_INFO if key in keys]
                preview.setPlainText("\n".join(labels) or "No hay opciones recomendadas detectadas para este objetivo.")

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
                "Recomendadas marcadas",
                "He marcado las opciones amarillas recomendadas segun tu sistema detectado. Revisa el comando final y usa Crear/Actualizar preset o Aplicar preset para escribirlo.",
            )

        def show_about(self):
            QtWidgets.QMessageBox.information(
                self,
                f"Acerca de {APP_NAME}",
                f"{APP_NAME} {APP_VERSION}\n\n"
                "Historial:\n"
                "0.1.0 - Tool inicial con Zenity.\n"
                "0.2.0 - HDR, GameMode, MangoHud y Gamescope.\n"
                "0.3.0 - ProtonDB, personalizados y presets.\n"
                "0.4.0 - Interfaz PySide6 mas clara.\n"
                "0.5.0 - Logo, nombre, recomendaciones del sistema, hover help y README.\n"
                "0.6.0 - Bazzite/SteamOS handheld, Legion Go 2, 800p/1200p y limites FPS.\n"
                "0.7.0 - Resolucion real Gamescope, deteccion de monitor y presets nativos.\n"
                "0.7.1 - Layout de escritorio mas ancho, lista fija y opciones sin corte horizontal.\n"
                "0.7.2 - Opciones en lista vertical, iconos de juegos, juegos manuales y botones de accion claros.\n"
                "0.7.3 - Actualizar presets, confirmaciones, botones con borde y ejecutables externos con Proton detectable o manual.\n"
                "0.7.4 - Ruta Steam configurable y guardado seguro cerrando/reabriendo Steam.\n"
                "0.7.5 - Las recomendaciones ya no se autoactivan al recargar un juego.\n"
                "0.7.6 - Presets aplican opciones reconstruidas y recuerdan acciones como HDR Unreal.\n"
                "0.7.7 - Resolucion Gamescope solo cambia al aplicarla y pruebas de presets.\n"
                "0.7.8 - VRR cap automatico usando Hz aplicados.\n"
                "0.7.9 - VRR cap usa limitador MangoHud porque Gamescope redondea a divisores.\n"
                "0.8.0 - Presets compartidos, controles sin rueda accidental, lanzamiento Steam y resumen ProtonDB oficial.\n"
                "0.8.1 - Recomendadas amarillas, ratings ProtonDB en juegos y accesos directos Steam externos.\n"
                "0.8.2 - Tarjetas HDR/VRR, badge ProtonDB y recomendaciones VRR/Adaptive en rojo de prueba.\n"
                "0.8.3 - Preset recomendado del sistema, panel de juego claro y gestion de manuales.\n"
                "0.8.4 - Corrige listado inicial para mostrar todos los juegos detectados.\n"
                "0.8.5 - Selector de presets carga opciones automaticamente y aplicar pide confirmacion.\n"
                "0.8.6 - Recuerda el preset exacto aplicado y avisa en rojo si hay uno pendiente.\n"
                "0.8.7 - Iconos para ejecutables externos y comandos manuales guardados como presets custom.\n"
                "0.8.8 - Estado de preset aplicado separado del preset seleccionado pendiente.\n"
                "0.8.9 - Cambios pendientes, comparar, diagnostico, historial y asistente de perfil.\n"
                "0.9.0 - Gestion de Proton por juego, recomendaciones, pestanas y builder AppImage.\n"
                "0.9.1 - Layout responsive para evitar cortes en pantallas mas estrechas.\n"
                "0.10.0 - Modo compacto, solo lectura, panel redimensionable, diagnostico HDR/VRR, historial Proton y acciones AppImage/update.\n"
                "0.10.1 - Buscar actualizacion tolera repos sin releases y los recuadros ganan espacio para no pisar texto.\n\n"
                f"Config:\n{APP_CONFIG_FILE}\n\n"
                f"README:\n{APP_DIR / 'README.md'}"
            )

        def show_recommendations(self):
            if not self.current_game:
                return
            data = protondb_recommendation_data(self.current_game, self.app_config)
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Recomendaciones ProtonDB")
            dialog.resize(820, 560)
            layout = QtWidgets.QVBoxLayout(dialog)
            text = QtWidgets.QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText(data["text"])
            layout.addWidget(text, 1)

            combo = QtWidgets.QComboBox()
            combo.addItem("No aplicar launch options de ProtonDB", "")
            for hint in data["launch_hints"][:8]:
                combo.addItem(hint, hint)
            layout.addWidget(combo)

            buttons = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons)
            open_btn = QtWidgets.QPushButton("Abrir ProtonDB")
            refresh_btn = QtWidgets.QPushButton("Actualizar datos")
            apply_btn = QtWidgets.QPushButton("Aceptar y aplicar seleccion")
            close_btn = QtWidgets.QPushButton("Cerrar")
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
                combo.addItem("No aplicar launch options de ProtonDB", "")
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
                            "Cerrar Steam para actualizar acceso directo",
                            "Este perfil externo tambien existe en la biblioteca de Steam. Para actualizar sus launch options sin que Steam sobrescriba shortcuts.vdf, Proton Pilot puede cerrar Steam y volver a abrirlo.\n\nCerrar Steam y continuar?",
                        )
                        if reply == QtWidgets.QMessageBox.Yes:
                            if not close_steam():
                                QtWidgets.QMessageBox.warning(
                                    self,
                                    "No se pudo cerrar Steam",
                                    "He guardado el perfil local, pero no he actualizado el acceso directo de Steam.",
                                )
                            else:
                                reopen_steam = True
                        else:
                            shortcut_note = "\n\nNo se ha actualizado el acceso directo de Steam porque Steam seguia abierto."
                    if not steam_is_running():
                        try:
                            result = update_steam_shortcut_launch_options(
                                self.root,
                                self.current_game["name"],
                                self.current_game["exe"],
                                command,
                            )
                            if result:
                                shortcut_note = f"\n\nAcceso directo de Steam actualizado:\n{result['path']}"
                            else:
                                shortcut_note = "\n\nNo he encontrado el acceso directo en shortcuts.vdf."
                        except Exception as exc:
                            shortcut_note = f"\n\nNo he podido actualizar el acceso directo de Steam: {exc}"
                    if reopen_steam:
                        if open_steam(self.root):
                            shortcut_note += "\nSteam se ha vuelto a abrir."
                        else:
                            shortcut_note += "\nNo he podido volver a abrir Steam; abrelo manualmente."
                custom_note = f"\n\nPreset custom creado: {custom_preset_name}" if custom_preset_name else ""
                QtWidgets.QMessageBox.information(
                    self,
                    "Guardado",
                    f"Comando guardado para el perfil externo:\n\n{self.current_game['name']}"
                    f"{custom_note}{shortcut_note}",
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
                    "Cerrar Steam para guardar",
                    "Steam esta abierto. Para evitar que sobrescriba localconfig.vdf, Proton Pilot puede cerrarlo ahora, guardar las opciones y volver a abrirlo.\n\nCerrar Steam y continuar?",
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                if not close_steam():
                    QtWidgets.QMessageBox.warning(
                        self,
                        "No se pudo cerrar Steam",
                        "No he podido cerrar Steam de forma fiable. Cierra Steam manualmente y vuelve a guardar.",
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
                    reopen_note = "\n\nSteam se ha vuelto a abrir."
                else:
                    reopen_note = "\n\nNo he podido volver a abrir Steam. Abre Steam manualmente."
            custom_note = f"\n\nPreset custom creado: {custom_preset_name}" if custom_preset_name else ""
            QtWidgets.QMessageBox.information(
                self,
                "Guardado",
                f"Comando guardado para {self.current_game['name']}.\n\nBackup:\n{backup}"
                f"{custom_note}{extra}{reopen_note}",
            )
            self.select_game(self.game_list.currentItem())

        def clear(self):
            if not self.current_game:
                return
            if not self.write_guard("borrar opciones"):
                return
            reply = QtWidgets.QMessageBox.question(
                self,
                "Borrar opciones de lanzamiento",
                f"Esto borrara las opciones de lanzamiento guardadas para:\n\n{self.current_game['name']}\n\nContinuar?",
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
                    "Opciones borradas",
                    f"Opciones locales borradas para:\n\n{self.current_game['name']}",
                )
                self.select_game(self.game_list.currentItem())
                return
            reopen_steam = False
            if steam_is_running():
                if not self.allow_steam_shutdown_write("borrar opciones"):
                    return
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Cerrar Steam para borrar",
                    "Steam esta abierto. Para evitar que sobrescriba localconfig.vdf, Proton Pilot puede cerrarlo ahora, borrar las opciones y volver a abrirlo.\n\nCerrar Steam y continuar?",
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                if not close_steam():
                    QtWidgets.QMessageBox.warning(
                        self,
                        "No se pudo cerrar Steam",
                        "No he podido cerrar Steam de forma fiable. Cierra Steam manualmente y vuelve a borrar.",
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
                    reopen_note = "\n\nSteam se ha vuelto a abrir."
                else:
                    reopen_note = "\n\nNo he podido volver a abrir Steam. Abre Steam manualmente."
            QtWidgets.QMessageBox.information(
                self,
                "Opciones borradas",
                f"Opciones de lanzamiento borradas para {self.current_game['name']}.\n\nBackup:\n{backup}{reopen_note}",
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
