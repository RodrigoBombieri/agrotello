# SoftwareDrones — Inspección Agro Autónoma con DJI Tello

Planificación técnica del proyecto: dron DJI Tello + visión por computadora para detección
de estrés hídrico y plagas en cultivos, con mapa del lote y reporte automático.

## 1. Visión del producto

Un dron Tello vuela un patrón de barrido sobre una parcela (o maceta/invernadero para pruebas),
captura video, y un pipeline de visión detecta zonas con estrés hídrico (vía índices de
vegetación RGB) y posibles plagas/enfermedades (vía un modelo de detección entrenado). El
sistema arma un mosaico del lote con las anomalías ubicadas espacialmente y genera un reporte
PDF descargable.

**Limitación conocida y honesta**: el Tello tiene cámara RGB, no multiespectral ni NIR, así que
no puede calcular NDVI real. El proyecto usa índices RGB (ExG, VARI) como proxy de estrés
hídrico/vigor vegetal — están validados en literatura agro pero son menos precisos que NDVI.
El roadmap deja un punto de extensión para migrar a un sensor NoIR o a un dron con cámara
multiespectral más adelante.

Tampoco tiene GPS, así que la ubicación de las anomalías en el mapa del lote se resuelve por
dead-reckoning (integración de los comandos de vuelo relativos) + stitching de imágenes, no por
coordenadas GPS absolutas.

## 2. Arquitectura

```
┌─────────────┐     comandos UDP      ┌──────────────┐
│   Tello EDU  │◄──────────────────────│ FlightController │
│  (hardware)  │──video stream (UDP)──►│  (djitellopy)    │
└─────────────┘                        └────────┬─────────┘
                                                 │ frames + posición relativa
                                                 ▼
                                        ┌──────────────────┐
                                        │  Vision Pipeline   │
                                        │ - índices ExG/VARI │
                                        │ - detector YOLOv8   │
                                        └────────┬───────────┘
                                                 │ detecciones + posición
                                                 ▼
                                        ┌──────────────────┐
                                        │  Mapping Module   │
                                        │ - dead reckoning   │
                                        │ - stitching mosaico│
                                        └────────┬───────────┘
                                                 │
                                                 ▼
                                        ┌──────────────────┐
                                        │  Reporting (PDF)  │
                                        └──────────────────┘

                          ┌────────────────────────────┐
                          │   FastAPI (orquestación)     │
                          │ start_mission / telemetry WS │
                          │ /reports                     │
                          └────────────────────────────┘
```

Todos los módulos de vuelo pasan por una interfaz `FlightController` abstracta, para poder
reemplazar Tello por MAVSDK (PX4/ArduPilot) o un puente DJI Mobile SDK sin tocar el resto del
sistema.

## 3. Estructura del repo

```
software-drones/
├── README.md
├── PLANNING.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── mission_format.md
│   └── datasets.md
├── src/
│   └── dronesw/
│       ├── __init__.py
│       ├── config.py                # pydantic Settings, carga .env
│       ├── flight/
│       │   ├── base.py              # interfaz abstracta FlightController
│       │   ├── tello_controller.py  # implementación djitellopy
│       │   └── safety.py            # failsafes: batería, geofence, timeout
│       ├── mission/
│       │   ├── planner.py           # genera patrón de barrido (grid scan)
│       │   └── executor.py          # ejecuta el plan, loguea posición relativa
│       ├── vision/
│       │   ├── capture.py           # lectura del stream de video
│       │   ├── indices.py           # ExG / VARI sobre frames
│       │   ├── detector.py          # wrapper YOLOv8 (plagas/enfermedades)
│       │   └── stitching.py         # mosaico del lote (OpenCV Stitcher)
│       ├── mapping/
│       │   └── geolocate.py         # dead reckoning -> coordenadas locales
│       ├── reporting/
│       │   ├── pdf_report.py
│       │   └── templates/
│       └── api/
│           ├── main.py              # app FastAPI
│           ├── routes/
│           └── websocket.py         # telemetría/video en vivo
├── models/          # pesos entrenados (gitignored; DVC/LFS a futuro)
├── datasets/         # subset PlantVillage + fotos propias (gitignored)
├── notebooks/        # exploración y entrenamiento del detector
├── tests/
│   ├── unit/
│   └── integration/
├── scripts/
│   ├── run_mission.py
│   └── train_detector.py
└── .github/
    └── workflows/
        └── ci.yml
```

## 4. Stack técnico

| Capa | Herramienta | Motivo |
|---|---|---|
| Control de vuelo | `djitellopy` | Único SDK Python maduro para Tello, sin licencias |
| Visión | OpenCV + `ultralytics` (YOLOv8n) | Liviano, corre bien en CPU para prototipo |
| Detección de plagas | YOLOv8n fine-tuned sobre PlantVillage + datos propios | Dataset público de arranque, barato reentrenar |
| API/orquestación | FastAPI + WebSockets | Async nativo, bueno para telemetría en vivo |
| Reportes | `fpdf2` o `reportlab` | Generación de PDF sin dependencias pesadas |
| Config | `pydantic-settings` + `.env` | Type-safe, estándar |
| Logging | `loguru` | Configuración mínima, buen output estructurado |
| Tests | `pytest` + mocks de `djitellopy` | Vuelo real no es reproducible en CI |
| CI | GitHub Actions (`ruff`, `black`, `pytest`) | Gratis, integración directa con GitHub |

## 5. Roadmap por sprints (2 semanas c/u, salvo Sprint 0)

**Sprint 0 — Setup (1 semana)**
Scaffold del repo, entorno virtual, CI básico (lint + test vacío). Conexión al Tello, comandos
básicos (`takeoff`, `land`, lectura de batería/altura). Failsafe mínimo: auto-land si batería
< 15%.
*Entregable*: script que despega, hace hover 5s, aterriza, con logging de telemetría.

**Sprint 1 — Vuelo y captura**
Interfaz `FlightController` abstracta + implementación Tello. `MissionPlanner` que genera un
patrón de barrido en grilla (usando `go x y z speed`, relativo). Captura de video, guardado de
frames con timestamp y posición relativa estimada.
*Entregable*: misión de barrido sobre un área de prueba, frames guardados y taggeados.

**Sprint 2 — Índices de vegetación**
Cálculo de ExG/VARI sobre frames capturados, generación de heatmap de estrés hídrico,
umbral configurable para marcar zonas anómalas. Tests unitarios con imágenes de muestra.
*Entregable*: heatmap superpuesto sobre frames de una parcela real o maceta de prueba.

**Sprint 3 — Detección de plagas/enfermedades**
Curado de dataset (subset PlantVillage + fotos propias), fine-tuning de YOLOv8n, pipeline de
inferencia con umbral de confianza configurable. Tests con imágenes mockeadas.
*Entregable*: detector corriendo sobre frames guardados, con métricas de precisión/recall.

**Sprint 4 — Mapeo del lote**
Dead reckoning a partir de los comandos de vuelo ejecutados (posición local acumulada).
Stitching de frames en un mosaico del lote (OpenCV Stitcher). Anomalías (índices + detecciones)
ubicadas sobre el mosaico.
*Entregable*: imagen del lote completo con marcadores de anomalías posicionados.

**Sprint 5 — Reportes**
Modelo de datos del reporte (anomalías, coordenadas locales, thumbnails, confianza, timestamp).
Generación de PDF con mapa, listado y estadísticas del vuelo (área cubierta, batería usada,
duración).
*Entregable*: PDF de reporte end-to-end a partir de una misión completa.

**Sprint 6 — API y orquestación**
FastAPI: endpoint para lanzar misión, WebSocket de telemetría/video en vivo, endpoint para
listar/descargar reportes. Config vía `.env`.
*Entregable*: API funcional, misión disparable vía HTTP, telemetría visible por WS.

**Sprint 7 — Dashboard mínimo (opcional/stretch)**
UI web simple (o mejora de CLI si se prioriza tiempo) para disparar misiones y ver
feed en vivo + mapa de anomalías.
*Entregable*: interfaz usable sin tocar código para operar una misión.

**Sprint 8 — Hardening**
Geofence (límite de distancia/altura), auto-land por pérdida de conexión, reintentos y manejo
de errores de comandos UDP, logging estructurado en toda la app, tests de integración con
checklist de hardware.
*Entregable*: el sistema no se cae ni deja el dron "colgado" ante fallos comunes (batería baja,
señal débil, timeout de comando).

**Sprint 9 — Documentación, demo y cierre**
Documentación final (README, docs/architecture.md, docs/datasets.md), video de demo de una
misión real, definición del camino de upgrade (sensor NoIR/NDVI real, dron con GPS/RTK,
swarm de varios Tello para cubrir más área).
*Entregable*: repo listo para mostrar en portafolio o iterar hacia un piloto real.

## 6. Riesgos y consideraciones

- **Autonomía de vuelo**: el Tello vuela ~10-13 min por batería. El planner de misión tiene que
  dimensionar el área de barrido según batería disponible, o prever cambios de batería entre
  pasadas del mismo lote.
- **Precisión de posición**: sin GPS, el dead-reckoning acumula error con cada comando. Para
  lotes grandes esto degrada el mapeo — mitigar con pasadas cortas y recalibración visual
  (matching de frames consecutivos) en vez de confiar solo en los comandos enviados.
- **Regulación de vuelo**: si esto se prueba fuera de espacio privado cerrado, conviene revisar
  la normativa de drones de ANAC (Argentina) antes de volar sobre terrenos de terceros o cerca
  de zonas restringidas.
- **Dataset de plagas/enfermedades**: PlantVillage es un buen punto de partida pero son fotos de
  hoja individual en estudio, no vistas aéreas — hay que validar que el modelo generalice a
  imágenes tomadas desde el dron, y probablemente etiquetar un set propio en Sprint 3.
- **Viento/exteriores**: el Tello es liviano y sensible al viento; las pruebas iniciales conviene
  hacerlas en interior o días de viento calmo.

## 7. Métricas de éxito (referencia, ajustables por sprint)

- Precisión/recall del detector de plagas ≥ 70% en set de validación propio (Sprint 3).
- Cobertura de área por batería documentada (m² cubiertos en un vuelo completo).
- Tiempo de generación del reporte < 30s desde el fin de la misión hasta el PDF.
- Cero crasheos de vuelo por fallas de software en 10 misiones de prueba consecutivas
  (Sprint 8).

## 8. Próximos pasos inmediatos

1. Conseguir el Tello (EDU si se puede, tiene mejor SDK de misión que el básico) y confirmar
   que arranca el Sprint 0 esta semana.
2. Elegir 1-2 plantas/cultivo de prueba accesibles (maceta, invernadero, patio) para no
   depender de un lote real desde el día uno.
3. Bajar un subset de PlantVillage para arrancar a explorar el modelo en paralelo al desarrollo
   de vuelo (no hace falta esperar al Sprint 3 para tocar el dataset).
