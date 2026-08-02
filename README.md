# AgroTello

Pipeline de misión, visión por computadora y reportes para detección de estrés hídrico y
plagas en cultivos. Esquema híbrido:

- **Misión y mapeo** → PX4/ArduPilot + MAVSDK-Python, sobre simulador SITL (sin hardware).
- **Visión por computadora** → DJI Tello EDU real, como sandbox de captura de imágenes.

Ver `PLANNING.md` para arquitectura completa, justificación del esquema híbrido, estructura
del repo y roadmap por sprints.

## Setup rápido

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Para levantar el simulador PX4 antes de programar misiones, ver `docs/sitl_setup.md`.

## Estado

Sprint 0 en curso — ver PLANNING.md sección 5.
