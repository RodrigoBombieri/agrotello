"""Ubicación de anomalías detectadas sobre un mapa georreferenciado del lote.

A diferencia del enfoque original (dead-reckoning sobre comandos relativos de Tello, sin
GPS), este módulo usa la posición real reportada por MAVSDK (`telemetry.position()`,
lat/lon/alt) durante la misión SITL para asociar cada detección de la visión con una
coordenada real. Mucho más preciso que estimar posición por comandos enviados.

TODO (Sprint 4):
- Suscribirse a `drone.telemetry.position()` durante la misión y taggear cada frame
  procesado con la posición más cercana en el tiempo.
- Construir el mapa del lote (mosaico o grilla simple) con las anomalías posicionadas.
"""
