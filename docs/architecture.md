# Arquitectura

Ver diagrama y detalle completo en ../PLANNING.md (sección 2).

Puntos clave:
- Dos backends de vuelo con propósitos distintos: PX4/MAVSDK (misión y mapeo, contra SITL)
  y Tello EDU (captura de video real para el pipeline de visión). No son intercambiables
  para la misma tarea — ver PLANNING.md sección 1 para la justificación completa.
- `vision/`, `reporting/` y la mayor parte de `api/` son agnósticas al backend de vuelo.

Pendiente: documentar decisiones de diseño a medida que se toman (ADRs cortos acá).
