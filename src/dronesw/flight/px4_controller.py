"""Backend de vuelo sobre MAVSDK-Python, contra PX4 SITL (o dron PX4 real a futuro).

Responsabilidades (Sprint 1):
- Conectar vía `mavsdk.System().connect(system_address=settings.MAVSDK_CONNECTION)`.
- arm() / takeoff() / land() / return_to_launch().
- Ejecutar un `MissionPlan` de waypoints GPS generado por `mission/planner.py`
  (`drone.mission.upload_mission(...)`, `drone.mission.start_mission()`).
- Exponer telemetría de posición real (`drone.telemetry.position()`) para `mapping/geolocate.py`.

Ver docs/sitl_setup.md para levantar el simulador antes de implementar/probar esto.

TODO (Sprint 1): implementar sobre la interfaz definida en flight/base.py.
"""
