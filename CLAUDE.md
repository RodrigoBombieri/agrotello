# Notas para Claude

Contexto que se pierde entre sesiones. Leer esto primero al retomar el proyecto.

## Cómo trabaja Rodrigo

- **El código va en el chat, no directo al repo.** Él lo copia, analiza y lo pega en sus archivos.
  Escribir archivos directamente solo si lo pide explícitamente. Los documentos (`docs/`,
  `PLANNING.md`, este archivo) sí se escriben directo.
- **Etiquetar siempre la terminal** antes de cada bloque de comandos. Para no confundir entre los
  cinco contextos. Las etiquetas están definidas en `docs/comandos.md`:
  `[Git Bash]`, `[Ubuntu · PX4]`, `[Ubuntu · proyecto]`, `[pxh>]`, `[apython]`.
- **Los commits los hace desde Git Bash en Windows**, nunca desde WSL (las credenciales de
  GitHub funcionan de ese lado). Ruta: `~/Escritorio/Repositorio\ Git/agrotello`.
- Responder en español, conciso y directo.
- Va paso a paso y pide confirmación entre pasos. No adelantarse varios pasos de una.

## Mapa del entorno

| Pieza | Dónde | Notas |
|---|---|---|
| Repo | Windows: `C:\Users\Rodrigo\Escritorio\Repositorio Git\agrotello` | Desde WSL: `~/agrotello` (symlink) |
| PX4-Autopilot | Ubuntu (WSL2): `~/PX4-Autopilot` | Terminal **sin** venv |
| venv | Ubuntu: `~/venvs/agrotello` | Fuera del repo a propósito (`/mnt/c` es lento) |
| SITL | Se corre headless | La GUI de Gazebo se cuelga en su WSL |

Home del SITL configurado a un lote real en Gualeguaychú: `-32.695933, -58.895342`, alt 15.

## Limitaciones de mis herramientas en este proyecto

- **No puedo escribir en `.vscode/`** — Write/Edit lo bloquean. Sí puedo vía `bash`.
- **No puedo borrar archivos** (`rm` da "Operation not permitted"). Hay que pedírselo a él,
  con `git rm`.
- **No puedo acceder al filesystem de WSL.** Cowork rechaza rutas UNC, y mapear una unidad
  (`net use Z:`) tampoco sirve porque resuelve al UNC subyacente. Por eso el repo vive en
  Windows.
- **Usar siempre `git --no-optional-locks`** para inspeccionar. Los comandos git normales
  dejan un `.git/index.lock` huérfano que no puedo borrar y le rompe los commits a él.

## Decisiones tomadas (no reabrir sin motivo)

- **PX4, no ArduPilot** — MAVSDK solo soporta PX4 oficialmente; con ArduPilot habría que
  cambiar de SDK.
- **Tello descartado (2026-09-08).** Cuesta $650.000 y es un sistema cerrado: no se le puede
  cambiar ni agregar la cámara, así que nunca podría hacer NDVI. El dinero, si se gasta, va
  hacia un build PX4 (Holybro X500 V2, ~USD 550), que acepta cualquier cámara incluida una
  NoIR de ~USD 30 para NDVI real.
- **Estrategia de datos sin hardware**: Sentinel-2 (NDVI real gratis, 10 m/px) para estrés
  hídrico; `gz_x500_mono_cam` del simulador para la plomería de visión; datasets públicos de
  UAV agrícola para entrenar el detector. Con eso los Sprints 2 y 3 no dependen de comprar
  nada.
- **Shapely** para la geometría del planificador de misiones.
- **Sin hooks de pre-commit.** El lint corre en GitHub Actions (`.github/workflows/ci.yml`).
  Los hooks locales daban fricción: commitea desde Windows/Python 3.14, desarrolla en
  Linux/Python 3.10.
- Nombres de funciones y docstrings **en español**, siguiendo `scripts/sprint0_hover.py`.

## Formato del docstring de módulo

Todo archivo de código nuevo abre con un docstring de tres bloques, en este orden. Breve:
si se vuelve largo, es que el archivo hace demasiadas cosas.

1. **Una línea sin jerga** que diga qué es el archivo, seguida de dos o tres de contexto
   igual de llanas. Tiene que entenderse sin saber de drones ni de Python.
2. **Una lista con una línea por función o clase**, en el orden en que aparecen.
3. **Un párrafo que arranca con "Técnico:"** con lo que un programador necesita saber para
   tocar el archivo: decisiones de diseño, unidades, trampas.

Ejemplo de referencia: `src/dronesw/mission/planner.py`.

## Trampas ya encontradas (no repetir)

- `bateria.remaining_percent` de MAVSDK 3.x ya viene en escala 0-100. Multiplicar por 100
  rompió el failsafe silenciosamente.
- La batería del SITL no baja del 50% salvo que se setee `SIM_BAT_MIN_PCT`.
- El build de PX4 falla (`kconfiglib not found`) si el venv está activado: usa el Python del
  sistema.
- PX4 SITL rechaza armar sin GCS conectada. Se resuelve con `param set NAV_DLL_ACT 0` y
  `param set CBRK_SUPPLY_CHK 894281`.
- Pegar bloques multilínea de Python en `apython` rompe la indentación. Para pruebas rápidas,
  líneas sueltas; para algo más largo, un script.
- VS Code tiene que abrirse en modo Remote-WSL (`WSL: Reopen Folder in WSL`), si no Pylance
  no encuentra el venv de Linux.

## Cómo correr el proyecto

Tres pasos, en este orden. La primera terminal queda ocupada por el simulador: hay que
dejarla abierta y trabajar en la otra.

**1. Levantar el simulador** — [Ubuntu · PX4], sin venv:

```bash
cd ~/PX4-Autopilot
export PX4_HOME_LAT=-32.695933
export PX4_HOME_LON=-58.895342
export PX4_HOME_ALT=15
HEADLESS=1 make px4_sitl gz_x500
```

Esperar a que aparezca `Ready for takeoff!`. La terminal pasa a mostrar el prompt `pxh>`.

**2. Ajustar parámetros** — [pxh>], solo la primera vez de cada instalación (con
`param save` quedan guardados):

```
param set NAV_DLL_ACT 0
param set CBRK_SUPPLY_CHK 894281
param set SIM_BAT_MIN_PCT 10
param save
```

Los dos primeros permiten armar sin estación de control; el tercero deja que la batería
simulada baje del 50%, sin lo cual los failsafes no se pueden probar.

**3. Correr el vuelo** — [Ubuntu · proyecto], con venv:

El paquete tiene que estar instalado (una sola vez, o después de clonar de nuevo):
`pip install -e .` desde la raíz del repo. Sin eso, los scripts no encuentran `dronesw`.

```bash
source ~/venvs/agrotello/bin/activate
cd ~/agrotello
python scripts/sprint0_hover.py                      # Sprint 0: despegue, hover, aterrizaje
HOVER_SECONDS=40 python scripts/sprint0_hover.py     # dispara el failsafe de batería
python scripts/run_mission.py missions/lote_prueba.yaml --solo-plan --geojson   # solo planifica
python scripts/run_mission.py missions/lote_prueba.yaml   # planifica y vuela
```

El mapa del recorrido queda en `mapas/` y se ve arrastrándolo a geojson.io.

Antes de commitear conviene correr `black src scripts tests` y `ruff check src scripts tests`,
que es lo que valida el CI.

## Estado del proyecto

**Sprint 0 — cerrado** (lado SITL). Entorno completo, PX4 volando, `scripts/sprint0_hover.py`
con failsafe de batería verificado en vuelo.

**Sprint 1 — en curso.** Pasos:

- 1.1 ✅ Formato de misión — `missions/lote_prueba.yaml`, lote "La Florida" de 5,24 ha
- 1.2 ✅ `flight/base.py` — `FlightController` + `SoportaMisionGps` + `SoportaVideo`
- 1.3 ✅ `flight/px4_controller.py` — implementación MAVSDK
- 1.4 ✅ `mission/planner.py` — grilla de waypoints con Shapely
- 1.5 ✅ `mission/executor.py` — orquestación con vigilancia de batería
- 1.6 ✅ `scripts/run_mission.py` — planifica y vuela con un comando; `--solo-plan` y
  exportación a GeoJSON en `mapas/`
- 1.7 ⬜ Tests del planner — `tests/` todavía está vacío
- 1.8 ⬜ **Volar la misión en el SITL** — el entregable del sprint es el barrido ejecutado,
  no el código escrito
- 1.9 ⬜ `docs/mission_format.md` — sigue con el texto "pendiente" del scaffold

**Frente de visión: sin hardware, y ya no hace falta.** Se descartó el Tello (ver Decisiones).
Los Sprints 2 y 3 se hacen con satélite, simulador y datasets públicos. Un dron PX4 real es un
objetivo de mediano plazo, no un bloqueante.

**Pendiente de reescritura:** `PLANNING.md` todavía describe el esquema híbrido con el Tello
como pieza central (secciones 1, 2, 4 y el roadmap). Hay que actualizarlo cuando se cierre el
Sprint 1.

**Pendientes menores:** los `__init__.py` siguen con `# TODO: implementar` del scaffold, y
`flight/safety.py` quedó vacío porque la lógica de failsafe terminó dentro del ejecutor
(decidir si se elimina o se le da contenido cuando entre el Tello).

El roadmap completo está en `PLANNING.md` sección 5.
