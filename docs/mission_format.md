# Formato de misión

Pendiente (Sprint 1): definir el esquema (YAML/JSON) que describe una misión de barrido en
grilla sobre un polígono georreferenciado: vértices del lote (lat/lon), altura de vuelo (m),
velocidad, overlap entre pasadas. Se convierte a una lista de `mavsdk.mission.MissionItem`
para ejecutar contra PX4 SITL (o el dron real a futuro).
