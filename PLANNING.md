# AgroTello — Inspección Agro Autónoma (esquema híbrido: PX4/MAVSDK + DJI Tello)

Planificación técnica del proyecto: pipeline de misión, visión por computadora y reportes para
detección de estrés hídrico y plagas en cultivos.

## 1. Visión del producto

El proyecto se desarrolla en **dos frentes que conviven en paralelo**, no en una sola plataforma
de dron:

- **Misión y mapeo → PX4/ArduPilot + MAVSDK-Python, contra un simulador SITL.** Acá se construye
  la arquitectura real: waypoints GPS, telemetría de posición real, geofence. No requiere comprar
  hardware — corre en la PC. Es el código que eventualmente va a volar en un dron físico real.

- **Visión por computadora → DJI Tello EDU (hardware real).** El Tello se usa como una "cámara
  voladora" barata para capturar imágenes/video reales de cultivo y entrenar/validar el pipeline
  de detección (índices de vegetación + modelo de plagas). No importa que no tenga GPS ni
  telemetría de largo alcance para esto — solo necesitamos que vuele y filme.

**Por qué este esquema y no uno solo:**
Si desarrollábamos todo sobre Tello, el `MissionPlanner` y el `mapping` iban a estar basados en
movimientos relativos y dead-reckoning (sin GPS) — algo que hay que tirar y rehacer cuando se
pasa a un dron real de campo. Programando la misión/mapeo directo contra PX4 (aunque sea
simulado) evitamos ese trabajo descartable: el código de waypoints GPS es el mismo que se usa
después con un dron físico. A cambio, perdemos "hardware real" en esa parte hasta que se decida
comprar un dron PX4 — por eso el Tello cubre la parte de visión, que sí necesita imágenes reales
desde el día uno.

Cuando el pipeline esté validado en simulador + con datos reales del Tello, se evalúa la compra
de un dron PX4 físico para el piloto de campo (ver sección 8).

## 2. Arquitectura

```
                    ┌─────────────────────────┐        ┌──────────────────────────┐
                    │   PX4 SITL (simulador)    │        │      Tello EDU (real)      │
                    │   o dron PX4 real a futuro│        │                            │
                    └────────────┬─────────────┘        └─────────────┬──────────────┘
                                 │ MAVSDK (UDP, waypoints GPS)         │ djitellopy (UDP, cmds relativos)
                                 ▼                                    ▼
                    ┌─────────────────────────┐        ┌──────────────────────────┐
                    │   PX4FlightController      │        │   TelloFlightController    │
                    └────────────┬─────────────┘        └─────────────┬──────────────┘
                                 │                                    │
                                 ▼                                    ▼
                    ┌─────────────────────────┐        ┌──────────────────────────┐
                    │  MissionPlanner (GPS)      │        │   Captura de video/frames  │
                    │  grilla de waypoints        │        │   (para dataset de visión) │
                    └────────────┬─────────────┘        └─────────────┬──────────────┘
                                 │                                    │
                                 ▼                                    ▼
                    ┌─────────────────────────┐        ┌──────────────────────────┐
                    │  Mapping (geolocate.py)    │        │   Vision Pipeline           │
                    │  posición real vía telemetry│◄──────│   ExG/VARI + YOLOv8         │
                    └────────────┬─────────────┘  frames  └──────────────────────────┘
                                 │  + detecciones
                                 ▼
                    ┌─────────────────────────┐
                    │   Reporting (PDF)          │
                    └─────────────────────────┘

                          ┌────────────────────────────┐
                          │   FastAPI (orquestación)     │
                          │ start_mission (SITL o Tello)  │
                          │ telemetry WS / reports         │
                          └────────────────────────────┘
```

Ambos backends de vuelo (`PX4FlightController`, `TelloFlightController`) implementan la misma
interfaz abstracta `FlightController`, pero **no se usan para la misma tarea**: PX4/SITL corre
misiones de barrido con waypoints GPS; Tello se usa en modo manual/simple para capturar video
sobre un cultivo real.

## 3. Estructura del repo

```
agrotello/
├── README.md
├── PLANNING.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── mission_format.md
│   ├── datasets.md
│   └── sitl_setup.md         # cómo levantar PX4 SITL local
├── src/
│   └── dronesw/
│       ├── __init__.py
│       ├── config.py                 (1)
│       ├── flight/
│       │   ├── base.py              # interfaz abstracta FlightController (4)
│       │   ├── px4_controller.py    # MAVSDK — waypoints GPS, contra SITL o dron real(5)
│       │   ├── tello_controller.py  # djitellopy — captura de video real(5)
│       │   └── safety.py            # failsafes: batería, geofence, timeout (7)
│       ├── mission/
│       │   ├── planner.py           # genera waypoints GPS (grilla sobre polígono del lote) (3)
│       │   └── executor.py          # ejecuta el plan vía MAVSDK, loguea progreso (6)
│       ├── vision/
│       │   ├── capture.py           # lectura del stream de video (Tello)(9)
│       │   ├── indices.py           # ExG / VARI sobre frames(10)
│       │   ├── detector.py          # wrapper YOLOv8 (plagas/enfermedades)(10)
│       │   └── stitching.py         # mosaico del lote (OpenCV Stitcher)(12)
│       ├── mapping/
│       │   └── geolocate.py         # posición real vía MAVSDK telemetry -> mapa georreferenciado(11)
│       ├── reporting/
│       │   ├── pdf_report.py         (13)
│       │   └── templates/            (13)
│       └── api/
│           ├── main.py              # FastAPI app (2)
│           ├── routes/               (2)
│           └── websocket.py         # telemetría/video en vivo (8)
├── models/          # pesos entrenados (gitignored)
├── datasets/         # frames del Tello + PlantVillage (gitignored)
├── notebooks/
├── tests/
│   ├── unit/
│   └── integration/
├── scripts/
│   ├── run_mission.py       # --backend sitl|px4|tello
│   └── train_detector.py
└── .github/workflows/ci.yml
```

## 4. Stack técnico

| Capa | Herramienta | Motivo |
|---|---|---|
| Misión/vuelo simulado | **PX4 SITL** (Docker, headless Gazebo o jMAVSim) | Corre en la PC, $0 hardware, es el target real de producción |
| Cliente de misión | **MAVSDK-Python** (`pip install mavsdk`) | SDK oficial async, waypoints GPS, telemetría, mismo código para SITL y dron real |
| Vuelo con hardware real (visión) | `djitellopy` | Único SDK maduro para Tello, usado solo para capturar video real |
| Visión | OpenCV + `ultralytics` (YOLOv8n) | Liviano, corre bien en CPU |
| Detección de plagas | YOLOv8n fine-tuned sobre PlantVillage + fotos propias del Tello | Dataset público de arranque |
| API/orquestación | FastAPI + WebSockets | Async nativo, telemetría en vivo desde SITL o Tello |
| Reportes | `fpdf2` | PDF sin dependencias pesadas |
| Config | `pydantic-settings` + `.env` | Type-safe |
| Logging | `loguru` | Configuración mínima |
| Tests | `pytest` + mocks de MAVSDK/djitellopy | Ni SITL ni hardware real son reproducibles en CI |
| CI | GitHub Actions | Lint + tests, sin SITL corriendo (se mockea) |

## 5. Roadmap por sprints (2 semanas c/u, salvo Sprint 0)

**Sprint 0 — Setup (1 semana), dos frentes en paralelo** — ✅ *frente SITL completado; frente Tello pendiente de hardware*
*Frente SITL*: levantar PX4 SITL local (Docker, ver `docs/sitl_setup.md`), instalar
`mavsdk` + `aioconsole`, confirmar `arm()` / `takeoff()` / `land()` contra el simulador.
*Frente Tello*: conectar al Tello EDU real, comandos básicos (`takeoff`, `land`, batería).
Failsafe mínimo de batería en ambos backends.
*Entregable*: script que despega y aterriza tanto en SITL como en el Tello real.

> **Resultado (SITL)**: `scripts/sprint0_hover.py` — conecta, espera estimación de posición,
> chequea batería, despega a altura configurable, hace hover logueando telemetría y aterriza.
> El failsafe de batería fue verificado en vuelo, no solo escrito: con `SIM_BAT_MIN_PCT 10` el
> hover se corta y aterriza al cruzar el umbral. Nota: el chequeo corre una vez por segundo, y
> como el SITL descarga ~3%/s el disparo ocurre hasta un 3% por debajo del umbral nominal —
> irrelevante con tasas de descarga reales, pero a tener en cuenta si se ajusta la frecuencia
> de muestreo.

**Sprint 1 — Misión GPS + captura real**
`FlightController` abstracto + `Px4FlightController` (MAVSDK) + `TelloFlightController`.
`MissionPlanner` que genera waypoints GPS en grilla sobre un polígono (lat/lon), probado
contra SITL. En paralelo, captura de video real con el Tello sobre una planta/maceta de
prueba, frames guardados con timestamp.
*Entregable*: misión de barrido con waypoints ejecutada en SITL + primer dataset de frames
reales del Tello.

**Sprint 2 — Índices de vegetación**
Cálculo de ExG/VARI sobre los frames reales capturados con el Tello, heatmap de estrés
hídrico, umbral configurable. Tests unitarios con imágenes de muestra.
*Entregable*: heatmap sobre frames reales de una planta/maceta/invernadero de prueba.

**Sprint 3 — Detección de plagas/enfermedades**
Dataset (PlantVillage + fotos propias del Tello), fine-tuning YOLOv8n, pipeline de
inferencia con umbral de confianza. Tests con imágenes mockeadas.
*Entregable*: detector corriendo sobre frames reales, con métricas de precisión/recall.

**Sprint 4 — Mapeo georreferenciado (SITL)**
`geolocate.py` usa `telemetry.position()` de MAVSDK (lat/lon reales, no dead-reckoning) para
ubicar detecciones sobre un mapa del "lote" simulado. Stitching de frames de referencia
(pueden ser los del Tello, usados como si fueran capturas de la misión) sobre ese mapa.
*Entregable*: mapa georreferenciado con anomalías posicionadas por coordenadas reales de SITL.

**Sprint 5 — Reportes**
Modelo de datos del reporte (anomalías, coordenadas GPS, thumbnails, confianza, timestamp).
PDF con mapa georreferenciado, listado y estadísticas de la misión.
*Entregable*: PDF end-to-end combinando misión SITL + detecciones reales del Tello.

**Sprint 6 — API y orquestación**
FastAPI: endpoint para lanzar misión (`backend=sitl|tello`), WebSocket de telemetría/video
en vivo, endpoint de reportes. Config vía `.env`.
*Entregable*: API funcional para ambos backends.

**Sprint 7 — Dashboard mínimo (opcional/stretch)**
UI simple para disparar misiones y ver feed/mapa.

**Sprint 8 — Hardening**
Geofence (nativo de PX4 + custom para Tello), reconexión ante pérdida de señal MAVSDK/UDP,
manejo de errores de comandos, logging estructurado, tests de integración.

**Sprint 9 — Documentación, demo y decisión de hardware real**
Documentar resultados de SITL + pipeline de visión validado con datos reales del Tello.
Con eso ya evaluado, decidir si se compra un dron PX4 físico (peso, autonomía, cámara/gimbal
necesarios) para el piloto de campo real.
*Entregable*: repo documentado, demo grabada, decisión de hardware justificada con datos.

## 6. Riesgos y consideraciones

- **Brecha simulador-realidad**: SITL valida la lógica de misión y mapeo, pero no reproduce
  viento, RF real, ni comportamiento exacto de un autopiloto físico. El piloto de campo (cuando
  haya dron PX4 real) va a exponer cosas que el simulador no mostró — dejarlo previsto, no asumir
  que "andar en SITL" es lo mismo que "andar en campo".
- **Dataset de visión con Tello ≠ altura/ángulo de un dron de campo real**: las fotos del Tello
  (vuelo bajo, indoor/patio) pueden no generalizar directamente a vistas aéreas de mayor altura de
  un dron real sobre un lote — hay que revalidar el modelo cuando cambie la plataforma de captura.
- **Tello sigue teniendo las limitaciones ya conocidas** (WiFi ~30-100m, batería ~13min, sin
  GPS) — pero ahora estas limitaciones solo afectan al sandbox de visión, no a la arquitectura de
  misión/mapeo, que ya está diseñada para el caso real desde el principio.
- **Regulación**: un dron PX4 real (>250g típicamente) cae en categorías de ANAC más estrictas
  que el Tello — revisar normativa antes de planear vuelos de campo reales.
- **Dataset de plagas/enfermedades**: PlantVillage es fotos de estudio, no vistas aéreas —
  validar generalización, etiquetar set propio en Sprint 3.

## 7. Métricas de éxito

- Misión de barrido con waypoints GPS ejecutada end-to-end en SITL sin intervención manual
  (Sprint 1).
- Precisión/recall del detector de plagas ≥ 70% en set de validación propio (Sprint 3).
- Error de geolocalización de anomalías en SITL < 1-2m respecto a la posición real simulada
  (Sprint 4) — mucho mejor que lo que hubiera dado dead-reckoning en Tello.
- Tiempo de generación del reporte < 30s.
- Cero crasheos de software en 10 misiones SITL consecutivas + 10 vuelos Tello consecutivos
  (Sprint 8).

## 8. Próximos pasos inmediatos

1. Instalar Docker + levantar PX4 SITL local (ver `docs/sitl_setup.md`), confirmar
   `arm()`/`takeoff()`/`land()` desde `apython` con MAVSDK antes de escribir código propio.
2. Comprar el Tello EDU (ya confirmado el listado en MercadoLibre) — conseguir 2-3 baterías
   extra para las sesiones de captura de video.
3. Elegir 1-2 plantas/cultivo de prueba accesibles para el sandbox de visión (no depende del
   simulador ni de un lote real).
4. Bajar un subset de PlantVillage en paralelo para arrancar a explorar el modelo.
5. Recién en Sprint 9, con datos concretos de ambos frentes, evaluar la compra de un dron PX4
   físico — no antes.
