# Proton Pilot

Proton Pilot es una aplicacion de escritorio para Linux que gestiona perfiles de
lanzamiento de Steam/Proton por juego. Ayuda a configurar Gamescope, GameMode,
MangoHud, HDR, VRR, versiones de Proton, informacion de ProtonDB, perfiles
handheld y opciones de lanzamiento personalizadas.

## Instalacion

```bash
./install.sh --deps
```

Para omitir la instalacion de dependencias:

```bash
./install.sh --no-deps
```

El comando instalado es:

```bash
proton-pilot
```

## AppImage

Puedes crear un AppImage con:

```bash
./build-appimage.sh
```

El resultado se crea en `dist/`.

## Funciones Principales

- Detecta juegos instalados de Steam y juegos añadidos manualmente.
- Lee y escribe opciones de lanzamiento de Steam por juego.
- Muestra y cambia la version de Proton/compatibility tool usada por cada juego.
- Propone recomendaciones segun GPU, pantalla, sesion grafica y herramientas
  instaladas.
- Incluye toggles para resolucion Gamescope, HDR, VRR, limite FPS, handheld,
  RT/DXR, FSR4, Wayland, MangoHud y GameMode.
- Agrupa las opciones en categorias orientadas a objetivos:
  - Base y rendimiento
  - Gamescope, pantalla y VRR
  - HDR
  - Escalado y handheld
  - Compatibilidad avanzada
  - Personalizadas / otros
- Permite crear opciones de lanzamiento personalizadas, asignarlas a categorias,
  borrarlas a una papelera recuperable y restaurarlas mas adelante.
- Guarda presets y configuracion en `~/.config/proton-pilot/config.json`.
- Incluye modo compacto, modo solo lectura y preferencia persistente de idioma
  entre español e ingles.

## Escritura Segura En Steam

Steam puede sobrescribir `localconfig.vdf` al cerrarse. Proton Pilot puede cerrar
Steam antes de escribir opciones de lanzamiento en Desktop Mode y volver a
abrirlo despues. Si detecta Steam Gaming Mode, evita cerrar Steam automaticamente
y pide aplicar los cambios desde Desktop Mode o tras cerrar Steam manualmente.

## Notas Handheld

Proton Pilot incluye presets para Bazzite, sesiones tipo SteamOS y dispositivos
tipo Lenovo Legion Go. El soporte handheld actual esta orientado a perfiles. Una
interfaz handheld pensada para mando queda documentada como trabajo futuro.

## Releases De GitHub

Las versiones estables se publican en GitHub Releases como AppImage:

https://github.com/drbermejor/Proton-Pilot/releases

