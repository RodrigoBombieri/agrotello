"""Interfaz abstracta que deben implementar los backends de vuelo.

flight/base.py: No se ejecuta directamente, pero es el molde que define las reglas
para los controladores que se van a instanciar en este momento.

Dos implementaciones conviven en este proyecto con propósitos distintos:

- `Px4FlightController` (MAVSDK): ejecuta misiones de waypoints GPS contra PX4 SITL
  (o, a futuro, un dron PX4 real). Es el backend "de producción".
- `TelloFlightController` (djitellopy): controla el Tello EDU real en modo simple/manual,
  usado solo como sandbox para capturar video/frames reales para el pipeline de visión.

No se espera que ambos backends soporten exactamente las mismas operaciones (por ejemplo,
`fly_mission` con waypoints GPS tiene sentido para PX4 pero no para Tello, que no tiene GPS).
La interfaz define el subconjunto común (arm/conectar, takeoff, land, leer batería, leer
posición si está disponible) y cada backend documenta qué soporta.

TODO (Sprint 1): definir la interfaz concreta (métodos async, tipos de retorno) antes de
implementar los dos backends.
"""
