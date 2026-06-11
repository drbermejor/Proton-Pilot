#!/usr/bin/env python3
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


HOME = Path.home()
APP_NAME = "Proton Pilot"
APP_VERSION = "0.7.0"
APP_DIR = Path(__file__).resolve().parent
APP_ICON_CANDIDATES = [
    APP_DIR / "assets/proton-pilot.png",
    APP_DIR / "proton-pilot-assets/proton-pilot.png",
]
APP_CONFIG_DIR = HOME / ".config/proton-pilot"
APP_CONFIG_FILE = APP_CONFIG_DIR / "config.json"
LEGACY_CONFIG_FILE = HOME / ".config/steam-game-options/config.json"
STEAM_ROOTS = [
    HOME / ".local/share/Steam",
    HOME / ".steam/root",
    HOME / ".var/app/com.valvesoftware.Steam/data/Steam",
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
    "UEHDR": "Forzar HDR Unreal Engine.ini",
    "NODXR": "Desactivar Ray Tracing DXR",
    "PROTONDB": "Abrir ProtonDB del juego",
    "RECOMMEND": "Ver recomendaciones ProtonDB",
    "CUSTOM": "Ajustes personalizados",
}

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
    "presets": {},
    "last_selected": [],
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
        "description": "Muestra overlay de FPS, frametime, GPU/CPU y temperaturas. Con Gamescope se aplica como --mangoapp.",
        "tokens": "mangohud o gamescope --mangoapp",
        "recommended": True,
    },
    "HDR": {
        "label": "HDR via Gamescope",
        "description": "Activa salida HDR en Gamescope y expone HDR a DXVK con ENABLE_GAMESCOPE_WSI=1 y DXVK_HDR=1.",
        "tokens": "ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope --hdr-enabled",
        "recommended": False,
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
        "description": "Ejecuta el juego dentro de Gamescope a pantalla completa. Necesario para HDR y util para aislar resolucion/modo de pantalla.",
        "tokens": "gamescope -f --",
        "recommended": False,
    },
    "REALRES": {
        "label": "Resolucion real Gamescope",
        "description": "Fuerza a Gamescope a exponer la resolucion fisica del monitor al juego con -W/-H y -w/-h. Util con escalado fraccional de KDE/Wayland.",
        "tokens": "gamescope -W <monitor_w> -H <monitor_h> -w <game_w> -h <game_h> -r <hz>",
        "recommended": False,
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
        gpu_name = next((line.strip() for line in lspci.splitlines() if re.search(r"VGA|3D|Display", line, re.I)), "NVIDIA")
    elif re.search(r"AMD/ATI|Radeon|amdgpu", lspci, re.I):
        gpu = "amd"
        gpu_name = next((line.strip() for line in lspci.splitlines() if re.search(r"VGA|3D|Display", line, re.I)), "AMD Radeon")
    elif re.search(r"Intel", lspci, re.I):
        gpu = "intel"
        gpu_name = next((line.strip() for line in lspci.splitlines() if re.search(r"VGA|3D|Display", line, re.I)), "Intel")

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
    is_handheld = is_bazzite or is_steamos or is_legion_go or session.get("desktop", "").lower() == "gamescope"
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
        },
    }


def detect_primary_display():
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
        return {"name": match.group(1), "width": width, "height": height, "refresh": refresh}

    kscreen = command_output(["kscreen-doctor", "-o"])
    mode = re.search(r"Modes:.*?(\d+):\x1b\[[^m]*m?(\d+)x(\d+)@([0-9.]+)\*", kscreen, re.S)
    name = re.search(r"Output:\s*\d+\s+(\S+)", re.sub(r"\x1b\[[0-9;]*m", "", kscreen))
    if mode:
        return {
            "name": name.group(1) if name else "",
            "width": int(mode.group(2)),
            "height": int(mode.group(3)),
            "refresh": round(float(mode.group(4))),
        }
    return {"name": "", "width": 0, "height": 0, "refresh": None}


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
        reasons.append("Gamescope + WSI detectados: HDR via Gamescope esta disponible.")
    if system.get("device", {}).get("is_bazzite"):
        reasons.append("Bazzite detectado: presets handheld y Gamescope encajan bien con Gaming Mode.")
    if system.get("device", {}).get("is_steamos"):
        reasons.append("SteamOS detectado: usa perfiles por juego y evita tocar ajustes globales desde la app.")
    if system.get("device", {}).get("is_legion_go"):
        reasons.append("Lenovo Legion Go detectado: 1280x800 ahorra bateria; 1920x1200 usa la pantalla nativa.")
    elif system.get("device", {}).get("is_handheld"):
        reasons.append("Dispositivo handheld detectado: 800p + limite FPS suele mejorar bateria y estabilidad.")
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


def steam_root():
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
                }
            )
    return sorted(games, key=lambda g: g["name"].casefold())


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
        "MANGOHUD": "mangohud" in current or "--mangoapp" in current,
        "GAMESCOPE": "gamescope" in current,
        "REALRES": "-W " in current and "-H " in current and "-w " in current and "-h " in current,
        "HANDHELD800P": "-w 1280" in current and "-h 800" in current,
        "HANDHELD1200P": "-w 1920" in current and "-h 1200" in current,
        "CAP60": "--framerate-limit 60" in current,
        "CAP72": "--framerate-limit 72" in current,
        "GSFSR": "-F fsr" in current,
        "GSNIS": "-F nis" in current,
        "ADAPTIVE": "--adaptive-sync" in current,
        "UEHDR": False,
        "NODXR": "VKD3D_CONFIG=nodxr" in current,
        "PROTONDB": False,
        "RECOMMEND": False,
        "CUSTOM": False,
    }


def compose_launch(selected, custom_pre="", custom_post="", gamescope_res=None):
    selected = set(selected)
    gamescope_options = {"HDR", "GAMESCOPE", "REALRES", "ADAPTIVE", "HANDHELD800P", "HANDHELD1200P", "CAP60", "CAP72", "GSFSR", "GSNIS"}
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
        if "MANGOHUD" in selected:
            flags.append("--mangoapp")
        if "ADAPTIVE" in selected:
            flags.append("--adaptive-sync")
        parts.extend(["gamescope", *flags, "--"])
    elif "MANGOHUD" in selected:
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


def open_url(url):
    if shutil.which("xdg-open"):
        subprocess.Popen([shutil.which("xdg-open"), url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
    if not reports:
        return (
            f"No he encontrado reportes via API comunitaria para {game['name']}.\n\n"
            f"Puedes revisar la pagina manualmente:\nhttps://www.protondb.com/app/{game['appid']}"
        )

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
    data = {"text": "", "launch_hints": [], "reports": len(reports)}
    if not reports:
        data["text"] = (
            f"No he encontrado reportes via API comunitaria para {game['name']}.\n\n"
            f"Puedes revisar la pagina manualmente:\nhttps://www.protondb.com/app/{game['appid']}"
        )
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

    lines = [f"ProtonDB comunitario: {game['name']} ({game['appid']})", ""]
    if ratings:
        lines.append("Ratings recientes: " + ", ".join(f"{k}: {v}" for k, v in sorted(ratings.items(), key=lambda kv: -kv[1])))
    if proton_versions:
        lines.append("Proton mencionado: " + ", ".join(k for k, _ in sorted(proton_versions.items(), key=lambda kv: -kv[1])[:5]))
    if data["launch_hints"]:
        lines.append("")
        lines.append("Launch options detectadas:")
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

    class App(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
            self.resize(1050, 640)
            self.setMinimumSize(860, 520)
            self.app_icon = first_existing(APP_ICON_CANDIDATES)
            if self.app_icon:
                self.setWindowIcon(QtGui.QIcon(str(self.app_icon)))
            self.root = steam_root()
            self.config_path = localconfig_path(self.root)
            self.app_config = load_app_config()
            self.system = detect_system()
            self.system_recommended = system_recommended_keys(self.system)
            self.games = installed_games(self.root)
            self.checks = {}
            self.current_game = None

            self.setStyleSheet(
                """
                QWidget { font-size: 13px; }
                QLabel#appTitle { font-size: 22px; font-weight: 900; color: #17202a; }
                QLabel#version { color: #607d8b; font-weight: 700; }
                QLabel#sectionHint { color: #607d8b; }
                QFrame#hero {
                    background: #eef7f2;
                    border: 1px solid #b7dfc5;
                    border-radius: 10px;
                    padding: 8px;
                }
                QGroupBox { font-weight: 700; margin-top: 8px; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
                QLabel#hint { color: #5f6368; }
                QCheckBox[recommended="true"] {
                    background: #e8f5e9;
                    border: 1px solid #6abf69;
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
                QPlainTextEdit, QLineEdit, QListWidget {
                    border: 1px solid #c9cdd2;
                    border-radius: 6px;
                    padding: 4px;
                }
                QPushButton { padding: 6px 10px; border-radius: 6px; }
                QPushButton#apply { font-weight: 700; }
                QLabel#optionDetail {
                    background: #f6f7f8;
                    border: 1px solid #d6d9dd;
                    border-radius: 6px;
                    padding: 8px;
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
            layout.addWidget(hero)

            top = QtWidgets.QHBoxLayout()
            layout.addLayout(top)

            left = QtWidgets.QVBoxLayout()
            top.addLayout(left, 2)
            right_scroll = QtWidgets.QScrollArea()
            right_scroll.setWidgetResizable(True)
            right_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            right_panel = QtWidgets.QWidget()
            right = QtWidgets.QVBoxLayout(right_panel)
            right.setContentsMargins(2, 2, 8, 2)
            right.setSpacing(6)
            right_scroll.setWidget(right_panel)
            top.addWidget(right_scroll, 3)

            title = QtWidgets.QLabel("1. Juegos instalados")
            title.setStyleSheet("font-size: 18px; font-weight: 800;")
            left.addWidget(title)
            self.game_list = QtWidgets.QListWidget()
            self.game_list.setMinimumWidth(250)
            for game in self.games:
                item = QtWidgets.QListWidgetItem(f"{game['name']}  ({game['appid']})")
                item.setData(QtCore.Qt.UserRole, game)
                self.game_list.addItem(item)
            left.addWidget(self.game_list, 1)

            self.current_label = QtWidgets.QLabel("Selecciona un juego para ver sus opciones.")
            self.current_label.setObjectName("hint")
            right.addWidget(self.current_label)

            sys_box = QtWidgets.QGroupBox("Recomendaciones segun tu sistema")
            sys_layout = QtWidgets.QVBoxLayout(sys_box)
            sys_summary = QtWidgets.QLabel(
                f"{self.system['os'].get('name') or 'OS desconocido'} - "
                f"{self.system['session'].get('type') or 'sesion desconocida'} / {self.system['session'].get('desktop') or 'desktop desconocido'}\n"
                f"{self.system['device'].get('product_name') or 'dispositivo desconocido'} - {self.system['gpu_name']}\n"
                f"Tools: gamescope={'si' if self.system['tools'].get('gamescope') else 'no'}, "
                f"gamemoderun={'si' if self.system['tools'].get('gamemoderun') else 'no'}, "
                f"mangohud={'si' if self.system['tools'].get('mangohud') else 'no'}"
            )
            sys_summary.setObjectName("sectionHint")
            sys_summary.setWordWrap(True)
            sys_layout.addWidget(sys_summary)
            sys_reasons = QtWidgets.QLabel("\n".join(f"- {r}" for r in recommendation_reasons(self.system)) or "No hay recomendaciones automaticas.")
            sys_reasons.setWordWrap(True)
            sys_layout.addWidget(sys_reasons)
            right.addWidget(sys_box)

            action_box = QtWidgets.QGroupBox("Acciones y recomendaciones")
            action_layout = QtWidgets.QHBoxLayout(action_box)
            self.recommend_btn = QtWidgets.QPushButton("Ver recomendaciones ProtonDB")
            self.open_protondb_btn = QtWidgets.QPushButton("Abrir ProtonDB")
            self.apply_system_btn = QtWidgets.QPushButton("Aplicar recomendadas del sistema")
            self.about_btn = QtWidgets.QPushButton("Acerca de / versiones")
            action_layout.addWidget(self.recommend_btn)
            action_layout.addWidget(self.open_protondb_btn)
            action_layout.addWidget(self.apply_system_btn)
            action_layout.addWidget(self.about_btn)
            action_layout.addStretch(1)
            right.addWidget(action_box)

            preset_box = QtWidgets.QGroupBox("Presets del juego")
            preset_layout = QtWidgets.QHBoxLayout(preset_box)
            self.preset_combo = QtWidgets.QComboBox()
            self.apply_preset_btn = QtWidgets.QPushButton("Aplicar preset")
            self.save_preset_btn = QtWidgets.QPushButton("Guardar como preset")
            self.delete_preset_btn = QtWidgets.QPushButton("Borrar preset")
            preset_layout.addWidget(self.preset_combo, 1)
            preset_layout.addWidget(self.apply_preset_btn)
            preset_layout.addWidget(self.save_preset_btn)
            preset_layout.addWidget(self.delete_preset_btn)
            right.addWidget(preset_box)

            opts_box = QtWidgets.QGroupBox("Opciones que se aplicaran al lanzamiento")
            opts_layout = QtWidgets.QGridLayout(opts_box)
            opts_layout.setHorizontalSpacing(8)
            opts_layout.setVerticalSpacing(6)
            row = col = 0
            option_columns = 3
            for key, meta in OPTION_INFO.items():
                label = meta["label"]
                desc = meta["description"]
                recommended = meta["recommended"]
                system_recommended = key in self.system_recommended
                suffix = ""
                if system_recommended:
                    suffix = "  - sistema"
                elif recommended:
                    suffix = "  - recomendado"
                text = label + suffix
                cb = QtWidgets.QCheckBox(text)
                cb.setToolTip(f"{desc}\n\nAnade: {meta['tokens']}")
                cb.setProperty("recommended", "true" if recommended else "false")
                cb.setProperty("systemRecommended", "true" if system_recommended else "false")
                cb.setProperty("optionKey", key)
                cb.installEventFilter(self)
                cb.stateChanged.connect(self.update_command)
                cb.clicked.connect(lambda checked=False, k=key: self.show_option_detail(k))
                self.checks[key] = cb
                opts_layout.addWidget(cb, row, col)
                col += 1
                if col == option_columns:
                    col = 0
                    row += 1
            right.addWidget(opts_box)

            self.option_detail = QtWidgets.QLabel("Pasa el cursor por encima de una opcion para ver que hace y que anade al lanzamiento.")
            self.option_detail.setObjectName("optionDetail")
            self.option_detail.setWordWrap(True)
            right.addWidget(self.option_detail)

            res_box = QtWidgets.QGroupBox("Resolucion Gamescope")
            res_layout = QtWidgets.QHBoxLayout(res_box)
            self.real_width = QtWidgets.QSpinBox()
            self.real_width.setRange(0, 10000)
            self.real_width.setSuffix(" px")
            self.real_height = QtWidgets.QSpinBox()
            self.real_height.setRange(0, 10000)
            self.real_height.setSuffix(" px")
            self.real_refresh = QtWidgets.QSpinBox()
            self.real_refresh.setRange(0, 1000)
            self.real_refresh.setSuffix(" Hz")
            self.detect_display_btn = QtWidgets.QPushButton("Usar monitor principal")
            for widget in (self.real_width, self.real_height, self.real_refresh):
                widget.valueChanged.connect(self.update_command)
            res_layout.addWidget(QtWidgets.QLabel("Ancho"))
            res_layout.addWidget(self.real_width)
            res_layout.addWidget(QtWidgets.QLabel("Alto"))
            res_layout.addWidget(self.real_height)
            res_layout.addWidget(QtWidgets.QLabel("Hz"))
            res_layout.addWidget(self.real_refresh)
            res_layout.addWidget(self.detect_display_btn)
            right.addWidget(res_box)

            custom_box = QtWidgets.QGroupBox("Ajustes personalizados")
            custom_layout = QtWidgets.QFormLayout(custom_box)
            self.custom_pre = QtWidgets.QLineEdit()
            self.custom_pre.setPlaceholderText("Antes de %command%, ej: RADV_PERFTEST=rt VKD3D_CONFIG=dxr")
            self.custom_post = QtWidgets.QLineEdit()
            self.custom_post.setPlaceholderText("Despues de %command%, ej: -dx12 -NoLauncher")
            self.custom_pre.textChanged.connect(self.update_command)
            self.custom_post.textChanged.connect(self.update_command)
            custom_layout.addRow("Antes:", self.custom_pre)
            custom_layout.addRow("Despues:", self.custom_post)
            right.addWidget(custom_box)

            right.addWidget(QtWidgets.QLabel("Comando final"))
            self.command_edit = QtWidgets.QPlainTextEdit()
            self.command_edit.setPlaceholderText("%command%")
            self.command_edit.setMaximumHeight(78)
            self.command_edit.setMaximumBlockCount(4)
            right.addWidget(self.command_edit, 1)

            buttons = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons)
            self.save_btn = QtWidgets.QPushButton("Guardar opciones")
            self.save_btn.setObjectName("apply")
            self.clear_btn = QtWidgets.QPushButton("Borrar opciones")
            self.reload_btn = QtWidgets.QPushButton("Recargar")
            buttons.addWidget(self.reload_btn)
            buttons.addStretch(1)
            buttons.addWidget(self.clear_btn)
            buttons.addWidget(self.save_btn)

            self.game_list.currentItemChanged.connect(self.select_game)
            self.recommend_btn.clicked.connect(self.show_recommendations)
            self.open_protondb_btn.clicked.connect(self.open_protondb)
            self.apply_system_btn.clicked.connect(self.apply_system_recommended)
            self.about_btn.clicked.connect(self.show_about)
            self.detect_display_btn.clicked.connect(self.use_detected_display)
            self.apply_preset_btn.clicked.connect(self.apply_preset)
            self.save_preset_btn.clicked.connect(self.save_preset)
            self.delete_preset_btn.clicked.connect(self.delete_preset)
            self.save_btn.clicked.connect(self.save)
            self.clear_btn.clicked.connect(self.clear)
            self.reload_btn.clicked.connect(self.reload)

            if self.game_list.count():
                self.game_list.setCurrentRow(0)

        def config_text(self):
            return self.config_path.read_text(errors="replace")

        def select_game(self, item):
            if not item:
                return
            self.current_game = item.data(QtCore.Qt.UserRole)
            ensure_game_builtin_presets(self.app_config, self.current_game["appid"])
            ensure_display_preset(self.app_config, self.current_game["appid"], self.system.get("display", {}))
            save_app_config(self.app_config)
            current = current_launch_options(self.config_text(), self.current_game["appid"])
            self.current_label.setText(
                f"{self.current_game['name']} ({self.current_game['appid']})\n"
                f"Actual: {current or '(sin opciones)'}"
            )
            flags = detect_flags(current)
            for key, cb in self.checks.items():
                cb.blockSignals(True)
                cb.setChecked(flags.get(key, False) or OPTION_INFO[key]["recommended"])
                cb.setProperty("active", "true" if flags.get(key, False) else "false")
                cb.style().unpolish(cb)
                cb.style().polish(cb)
                cb.blockSignals(False)
            custom = self.app_config.setdefault("custom", {}).get(self.current_game["appid"], {})
            self.custom_pre.blockSignals(True)
            self.custom_post.blockSignals(True)
            self.custom_pre.setText(custom.get("pre", ""))
            self.custom_post.setText(custom.get("post", ""))
            self.custom_pre.blockSignals(False)
            self.custom_post.blockSignals(False)
            res = custom.get("gamescope_res") or self.system.get("display", {})
            self.set_resolution_fields(res)
            self.refresh_presets()
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
            meta = OPTION_INFO[key]
            if key in self.system_recommended:
                recommended = "Recomendada para tu sistema"
            elif meta["recommended"]:
                recommended = "Recomendada por defecto"
            else:
                recommended = "Opcional / por juego"
            self.option_detail.setText(
                f"{meta['label']}\n\n"
                f"{meta['description']}\n\n"
                f"Anade: {meta['tokens']}\n"
                f"Estado: {recommended}"
            )

        def update_command(self):
            command = compose_launch(self.selected_keys(), self.custom_pre.text(), self.custom_post.text(), self.gamescope_resolution())
            self.command_edit.setPlainText(command)

        def gamescope_resolution(self):
            return {
                "width": self.real_width.value(),
                "height": self.real_height.value(),
                "refresh": self.real_refresh.value() or "",
            }

        def set_resolution_fields(self, res):
            for widget in (self.real_width, self.real_height, self.real_refresh):
                widget.blockSignals(True)
            self.real_width.setValue(int(res.get("width") or 0))
            self.real_height.setValue(int(res.get("height") or 0))
            self.real_refresh.setValue(int(res.get("refresh") or 0))
            for widget in (self.real_width, self.real_height, self.real_refresh):
                widget.blockSignals(False)

        def use_detected_display(self):
            display = detect_primary_display()
            self.set_resolution_fields(display)
            self.checks["REALRES"].setChecked(True)
            self.show_option_detail("REALRES")
            self.update_command()

        def game_presets(self):
            if not self.current_game:
                return {}
            return self.app_config.setdefault("presets", {}).setdefault(self.current_game["appid"], {})

        def refresh_presets(self):
            self.preset_combo.blockSignals(True)
            self.preset_combo.clear()
            presets = self.game_presets()
            if not presets:
                self.preset_combo.addItem("Sin presets guardados", "")
            else:
                for name in sorted(presets):
                    self.preset_combo.addItem(name, name)
            self.preset_combo.blockSignals(False)

        def current_preset_payload(self):
            return {
                "options": self.selected_keys(),
                "custom_pre": self.custom_pre.text(),
                "custom_post": self.custom_post.text(),
                "gamescope_res": self.gamescope_resolution(),
                "command": self.command_edit.toPlainText().strip(),
            }

        def apply_preset(self):
            name = self.preset_combo.currentData()
            if not name:
                return
            preset = self.game_presets().get(name)
            if not preset:
                return
            selected = set(preset.get("options", []))
            for key, cb in self.checks.items():
                cb.setChecked(key in selected)
            self.custom_pre.setText(preset.get("custom_pre", ""))
            self.custom_post.setText(preset.get("custom_post", ""))
            self.set_resolution_fields(preset.get("gamescope_res") or self.system.get("display", {}))
            command = preset.get("command", "")
            if command:
                self.command_edit.setPlainText(command)

        def save_preset(self):
            if not self.current_game:
                return
            name, ok = QtWidgets.QInputDialog.getText(self, "Guardar preset", "Nombre del preset:")
            name = name.strip()
            if not ok or not name:
                return
            self.game_presets()[name] = self.current_preset_payload()
            save_app_config(self.app_config)
            self.refresh_presets()
            index = self.preset_combo.findData(name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)

        def delete_preset(self):
            name = self.preset_combo.currentData()
            if not name:
                return
            reply = QtWidgets.QMessageBox.question(self, "Borrar preset", f"Borrar el preset '{name}'?")
            if reply != QtWidgets.QMessageBox.Yes:
                return
            self.game_presets().pop(name, None)
            save_app_config(self.app_config)
            self.refresh_presets()

        def open_protondb(self):
            if self.current_game:
                open_url(f"https://www.protondb.com/app/{self.current_game['appid']}")

        def apply_system_recommended(self):
            for key in self.system_recommended:
                if key in self.checks:
                    self.checks[key].setChecked(True)
            self.update_command()

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
                "0.7.0 - Resolucion real Gamescope, deteccion de monitor y presets nativos.\n\n"
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
            apply_btn = QtWidgets.QPushButton("Aceptar y aplicar seleccion")
            close_btn = QtWidgets.QPushButton("Cerrar")
            buttons.addWidget(open_btn)
            buttons.addStretch(1)
            buttons.addWidget(close_btn)
            buttons.addWidget(apply_btn)
            open_btn.clicked.connect(self.open_protondb)
            close_btn.clicked.connect(dialog.reject)

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
            save_app_config(self.app_config)

        def save(self):
            if not self.current_game:
                return
            if steam_is_running():
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Steam esta abierto",
                    "Steam parece estar abierto. Si reescribe su configuracion al cerrar, podria perderse el cambio.\n\nContinuar igualmente?",
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
            command = self.command_edit.toPlainText().strip()
            backup = set_launch_options(self.config_path, self.current_game["appid"], command)
            self.save_custom()
            extra = ""
            if self.checks["UEHDR"].isChecked():
                extra = "\n\n" + set_unreal_hdr(self.root, self.current_game["appid"])
            QtWidgets.QMessageBox.information(
                self,
                "Guardado",
                f"Opciones guardadas para {self.current_game['name']}.\n\nBackup:\n{backup}{extra}",
            )
            self.select_game(self.game_list.currentItem())

        def clear(self):
            if not self.current_game:
                return
            for cb in self.checks.values():
                cb.setChecked(False)
            self.custom_pre.clear()
            self.custom_post.clear()
            self.set_resolution_fields(self.system.get("display", {}))
            self.command_edit.setPlainText("")

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
    root = steam_root()
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
