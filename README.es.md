# Proton Pilot

Proton Pilot es una aplicacion de escritorio para Linux que gestiona perfiles de
lanzamiento de Steam/Proton por juego. Ayuda a configurar Gamescope, GameMode,
MangoHud, HDR, VRR, versiones de Proton, informacion de ProtonDB, perfiles
handheld y opciones de lanzamiento personalizadas.

Version actual: 0.11.0

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
proton-pilot-process-selector
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
- El boton `Archivos guardados` busca ubicaciones de Steam Cloud, el prefijo
  Proton y carpetas Linux habituales, y abre la carpeta elegida.
- Incluye un selector independiente de procesos colgados que resalta bloqueos
  detectados por Linux o KWin, preselecciona Gamescope y puede cerrar todo su
  arbol de procesos hijo.
- Propone recomendaciones segun GPU, pantalla, sesion grafica y herramientas
  instaladas.
- Incluye toggles para resolucion Gamescope, HDR, VRR, limite FPS, handheld,
  RT/DXR, FSR4, Wayland, MangoHud y GameMode.
- Separa `ENABLE_GAMESCOPE_WSI=1` como opcion propia relacionada con HDR y avisa
  al combinar FSR4 con HDR/WSI, porque algunos juegos pueden mostrar color mal.
- El diagnostico HDR/VRR explica que opciones marcar para HDR segun lo detectado
  en KDE, Gamescope, Gamescope WSI y el monitor.
- Añade una opcion experimental para saltar intro/splash con
  `-nosplash -nostartupscreen`.
- Agrupa las opciones en categorias orientadas a objetivos:
  - Base y rendimiento
  - Gamescope, pantalla y VRR
  - HDR
  - Escalado y handheld
  - Compatibilidad avanzada
  - Personalizadas / otros
- Permite crear opciones de lanzamiento personalizadas, asignarlas a categorias,
  borrarlas a una papelera recuperable y restaurarlas mas adelante.
- Guarda perfiles y configuracion en `~/.config/proton-pilot/config.json`.
- Rediseña el flujo por perfiles: distingue comando real de Steam, perfil
  aplicado, perfil seleccionado pendiente y cambios preparados.
- Detecta comandos manuales en Steam que no coinciden con ningun perfil y permite
  importarlos como perfil, sobrescribirlos con un perfil elegido o comparar
  diferencias.
- Muestra el estado de cada juego en la lista: sin perfil, perfil aplicado,
  cambios pendientes o comando manual.
- Incluye modo compacto, modo solo lectura y preferencia persistente de idioma
  entre español e ingles.
- La interfaz puede alternar entre español e ingles y cubre paneles, botones,
  tooltips, descripciones de opciones, diagnosticos y dialogos habituales.

## Escritura Segura En Steam

Steam puede sobrescribir `localconfig.vdf` al cerrarse. Proton Pilot puede cerrar
Steam antes de escribir opciones de lanzamiento en Desktop Mode y volver a
abrirlo despues. Si detecta Steam Gaming Mode, evita cerrar Steam automaticamente
y pide aplicar los cambios desde Desktop Mode o tras cerrar Steam manualmente.

## Notas Handheld

Proton Pilot incluye perfiles para Bazzite, sesiones tipo SteamOS y dispositivos
tipo Lenovo Legion Go. El soporte handheld actual esta orientado a perfiles. Una
interfaz handheld pensada para mando queda documentada como trabajo futuro.

## Releases De GitHub

Las versiones estables se publican en GitHub Releases como AppImage:

https://github.com/drbermejor/Proton-Pilot/releases
