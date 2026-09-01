"""Generador de misiones de barrido en grilla, en coordenadas GPS (lat/lon).

mission/planner.py: Cuando el usuario inicia la misión, este script toma las coordenadas
del polígono del campo y calcula matemáticamente la grilla de puntos (waypoints) en zigzag.
Crea el mapa de ruta en papel antes de volar.

A diferencia del enfoque original (movimientos relativos sobre Tello), el planner ahora
recibe el polígono del lote en coordenadas GPS reales y genera una lista de waypoints
(MissionItem de MAVSDK) que cubre el área con el overlap configurado entre pasadas.

Se prueba contra PX4 SITL (ver docs/sitl_setup.md) — no depende de hardware.

TODO (Sprint 1):
- Definir el esquema de entrada (polígono del lote, altura de vuelo, overlap) — ver
  docs/mission_format.md.
- Generar la grilla de waypoints (lat/lon) a partir del polígono.
- Convertir a `mavsdk.mission.MissionItem` / `MissionPlan`.
"""
