# AgroTello

Pipeline de misión, visión por computadora y reportes para detección de estrés hídrico y
plagas en cultivos. Esquema híbrido:

- **Misión y mapeo** → PX4/ArduPilot + MAVSDK-Python, sobre simulador SITL (sin hardware).
- **Visión por computadora** → DJI Tello EDU real, como sandbox de captura de imágenes.

Ver `PLANNING.md` para arquitectura completa, justificación del esquema híbrido, estructura
del repo y roadmap por sprints. Ver `docs/herramientas.md` para el stack técnico y cómo
fluyen los datos entre cada herramienta, y `docs/comandos.md` para los comandos de uso
frecuente según el entorno.

## Setup rápido

El entorno de desarrollo corre sobre WSL2/Ubuntu (el simulador PX4 no se ejecuta nativo en
Windows). Ver `docs/sitl_setup.md` para levantar el simulador y `docs/comandos.md` para la
convención de terminales y el detalle de cada comando.

```bash
python3 -m venv ~/venvs/agrotello        # el venv vive fuera del repo, a propósito
source ~/venvs/agrotello/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Estado

**Sprint 0 — completado del lado SITL.** El frente Tello queda pendiente de hardware.

Logrado:

- WSL2 + Ubuntu 22.04 con el toolchain de PX4 instalado.
- PX4 SITL compilado y volando en Gazebo (modo headless).
- MAVSDK-Python conectado al simulador, controlando el dron desde código.
- `scripts/sprint0_hover.py`: despegue → hover → aterrizaje, con logging de telemetría y
  failsafe de batería **verificado** (aterrizaje anticipado al cruzar el umbral).

Próximo: Sprint 1 — interfaz `FlightController` y generador de waypoints GPS. Ver
PLANNING.md sección 5.

### Correr el vuelo de prueba

Con el simulador ya corriendo (`HEADLESS=1 make px4_sitl gz_x500` desde `~/PX4-Autopilot`):

```bash
python scripts/sprint0_hover.py
HOVER_SECONDS=40 python scripts/sprint0_hover.py    # dispara el failsafe de batería
```

Para que el failsafe pueda dispararse hace falta bajar el piso de la batería simulada, que
por default PX4 no deja caer del 50%. En la consola `pxh>`:

```
param set SIM_BAT_MIN_PCT 10
param save
```
