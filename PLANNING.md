# AgroTello — Inspección agronómica autónoma con PX4

Planificación técnica: planificar y volar misiones sobre un lote, detectar problemas en el
cultivo y entregar un reporte accionable.

## 1. Visión del producto

El sistema recibe el contorno de un lote, calcula el recorrido que lo cubre, hace volar un
dron de forma autónoma, analiza lo que se ve desde arriba y entrega un mapa de dónde está el
problema.

Hay dos cosas distintas que detectar, y necesitan datos distintos:

| Qué se busca | Con qué se detecta | De dónde salen los datos |
|---|---|---|
| Zonas de bajo vigor y estrés hídrico | NDVI (necesita infrarrojo) | **Sentinel-2**, gratis, 10 m/píxel |
| Plagas, enfermedades, malezas | Visión por computadora sobre RGB | **Imágenes de dron**, resolución centimétrica |

No compiten: cubren escalas distintas. El satélite ve el lote entero y dice *dónde mirar*;
el dron baja a ver *qué está pasando ahí*. Un píxel satelital de 10 metros jamás va a mostrar
una hoja enferma, y un dron no va a cubrir 5.000 hectáreas en una tarde.

### Sobre el hardware

El proyecto nació apuntando a un DJI Tello y **esa decisión se revirtió** (2026-09-08). El
Tello es un sistema cerrado: no se le puede cambiar ni agregar la cámara, así que nunca
podría hacer NDVI. El objetivo de hardware pasó a ser un **dron PX4** (Holybro X500 V2,
~USD 550), que acepta cualquier cámara — incluida una NoIR de ~USD 30 que sí da infrarrojo.

Mientras tanto **nada está bloqueado**: Sentinel-2 da NDVI real del lote real, el simulador
de PX4 tiene una cámara (`gz_x500_mono_cam`) para construir toda la plomería de captura, y
hay datasets públicos de UAV agrícola para entrenar el detector. El dron físico es un
objetivo de mediano plazo, no un requisito.

El nombre del repo quedó de la etapa Tello. Se mantiene por continuidad del historial.

## 2. Arquitectura

```
    ┌──────────────────────┐         ┌──────────────────────────┐
    │  PX4 SITL (simulador)  │         │   Sentinel-2 (satélite)    │
    │  o dron PX4 real       │         │   NDVI del lote, gratis    │
    └──────────┬───────────┘         └────────────┬─────────────┘
               │ MAVSDK (UDP)                      │
               ▼                                   │
    ┌──────────────────────┐                      │
    │  Px4FlightController   │                      │
    └──────────┬───────────┘                      │
               │                                   │
     ┌─────────┴─────────┐                        │
     ▼                   ▼                        │
┌──────────────┐  ┌──────────────┐                │
│ MissionPlanner│  │   Telemetría   │                │
│ grilla de wp  │  │  lat/lon/alt   │                │
└──────┬───────┘  └───────┬──────┘                │
       │                   │                       │
       ▼                   │                       │
┌──────────────┐          │   ┌──────────────┐    │
│EjecutorMision │          └──►│    Mapping     │◄───┘
│ vuela y vigila│   frames      │ georreferencia │
└──────────────┘   geotaggeados└───────┬──────┘
       │                                │
       ▼                                ▼
┌──────────────┐               ┌──────────────┐
│    Visión      │──detecciones─►│   Reporting    │
│ índices + YOLO │               │      PDF       │
└──────────────┘               └──────────────┘
```

La capa de vuelo pasa por la interfaz abstracta `FlightController`, de modo que el resto del
sistema no sabe ni le importa si abajo hay un simulador o un dron físico: solo cambia la
dirección de conexión.

## 3. Estructura del repo

```
agrotello/
├── CLAUDE.md              # contexto de trabajo entre sesiones
├── PLANNING.md            # este archivo
├── README.md
├── pyproject.toml         # paquete instalable (pip install -e .)
├── requirements.txt
├── missions/              # un YAML por lote
│   └── lote_prueba.yaml
├── mapas/                 # recorridos exportados a GeoJSON, uno por corrida
├── docs/
│   ├── architecture.md
│   ├── comandos.md        # comandos por entorno y terminal
│   ├── datasets.md
│   ├── herramientas.md    # stack y flujo de datos
│   ├── mission_format.md  # formato del YAML de misión
│   └── sitl_setup.md      # cómo levantar el simulador
├── src/dronesw/
│   ├── config.py                    # (pendiente)
│   ├── flight/
│   │   ├── base.py                  # FlightController + capacidades opcionales
│   │   ├── px4_controller.py        # implementación MAVSDK
│   │   └── safety.py                # (vacío: el failsafe vive en el ejecutor)
│   ├── mission/
│   │   ├── planner.py               # grilla de waypoints con Shapely
│   │   └── executor.py              # orquestación y vigilancia de batería
│   ├── vision/                      # (pendiente)
│   ├── mapping/                     # (pendiente)
│   ├── reporting/                   # (pendiente)
│   └── api/                         # (pendiente)
├── scripts/
│   ├── sprint0_hover.py             # vuelo de prueba mínimo
│   └── run_mission.py               # planifica y vuela un lote
├── tests/unit/test_planner.py
└── .github/workflows/ci.yml
```

## 4. Stack técnico

| Capa | Herramienta | Estado |
|---|---|---|
| Simulación de vuelo | PX4 SITL + Gazebo (headless) | ✅ en uso |
| Cliente de vuelo | MAVSDK-Python | ✅ en uso |
| Geometría de misión | Shapely | ✅ en uso |
| Configuración de misión | PyYAML | ✅ en uso |
| Tests | pytest | ✅ en uso |
| Lint y formato | ruff + black, en GitHub Actions | ✅ en uso |
| NDVI satelital | Sentinel-2 (Copernicus) | ⬜ Sprint 2 |
| Cámara simulada | `gz_x500_mono_cam` | ⬜ Sprint 3 |
| Visión | OpenCV + NumPy | ⬜ Sprint 4 |
| Detección | Ultralytics YOLOv8 | ⬜ Sprint 4 |
| Reportes | fpdf2 | ⬜ Sprint 6 |
| API | FastAPI + WebSockets | ⬜ Sprint 7 |

Las dependencias de runtime se declaran en `pyproject.toml`, y se van sumando a medida que
los módulos las usan de verdad. `requirements.txt` es el entorno de desarrollo completo.

Ver `docs/herramientas.md` para el detalle de cómo se conectan.

## 5. Roadmap por sprints

### Sprint 0 — Entorno ✅

WSL2 + Ubuntu, toolchain de PX4, simulador compilado y volando headless, MAVSDK conectado.
Entregable: `scripts/sprint0_hover.py`, con failsafe de batería verificado en vuelo.

### Sprint 1 — Misión GPS ✅ *(cerrado 2026-09-13)*

- `flight/base.py`: interfaz abstracta con capacidades opcionales por protocolo.
- `flight/px4_controller.py`: implementación MAVSDK.
- `mission/planner.py`: grilla de waypoints en zigzag sobre un polígono, con Shapely.
- `mission/executor.py`: orquestación con vigilancia concurrente de batería.
- `scripts/run_mission.py`: un comando planifica y vuela; `--solo-plan` y exportación GeoJSON.
- Tests de la geometría.

**Entregable cumplido:** 22 de 22 waypoints volados sobre el lote La Florida (5,24 ha,
Gualeguaychú), con retorno automático y desarmado.

### Sprint 2 — NDVI satelital del lote

Descargar la escena de Sentinel-2 que cubre el lote, calcular NDVI, recortarlo al polígono
de la misión y generar un mapa de vigor con zonas clasificadas.

Es el primer resultado agronómico real del proyecto, sobre el campo real, sin hardware. A
10 m/píxel las 5,24 ha de La Florida son unos 520 píxeles: grueso para ver una planta,
suficiente para decidir a qué sector mandar el dron.

*Entregable*: mapa NDVI del lote con las zonas de menor vigor identificadas.

### Sprint 3 — Captura desde el dron

Suscribirse a la cámara del simulador (`gz_x500_mono_cam`), guardar los frames durante una
misión y asociar cada uno con la posición GPS del momento.

Las imágenes del simulador no sirven para analizar cultivo — no hay cultivo ahí. Lo que se
construye es la **plomería**: capturar, geotaggear y almacenar. El día que haya una cámara
real montada en un dron real, esa cañería ya está probada.

*Entregable*: una misión que aterriza dejando una carpeta de frames con coordenadas.

### Sprint 4 — Visión: índices y detección

Índices de vegetación RGB (ExG, VARI) y detector de plagas/enfermedades con YOLOv8,
entrenado sobre datasets públicos de UAV agrícola.

Acá el trabajo es sobre imágenes reales de terceros, no del simulador. La validación con
imágenes propias queda pendiente del hardware.

*Entregable*: detector con métricas de precisión y recall sobre un set de validación.

### Sprint 5 — Mapeo

Unir las piezas: mosaico del lote, detecciones ubicadas por coordenada, cruce con las zonas
de bajo vigor del NDVI satelital.

*Entregable*: mapa del lote con las anomalías posicionadas.

### Sprint 6 — Reportes

PDF con el mapa, el listado de anomalías, sus coordenadas y las estadísticas del vuelo.

*Entregable*: reporte generado end-to-end desde una misión.

### Sprint 7 — API

FastAPI para lanzar misiones, seguir la telemetría por WebSocket y descargar reportes.

### Sprint 8 — Hardening

Geofence, reconexión ante pérdida de enlace, manejo de errores, logging estructurado, tests
de integración.

### Sprint 9 — Cierre y decisión de hardware

Documentación final, demo grabada, y la decisión de comprar el dron PX4 tomada con datos
concretos: qué resolución hizo falta de verdad, a qué altura, con qué cámara.

## 6. Riesgos y consideraciones

- **Brecha simulador-realidad.** El SITL valida la lógica de misión, no el viento ni el
  comportamiento de un autopiloto físico. El primer vuelo real va a mostrar cosas que el
  simulador no mostró.
- **Los datasets públicos no son de tu zona.** Un detector entrenado con cultivos de otro
  continente puede fallar con los de Entre Ríos. Hay que revalidar con imágenes propias
  cuando haya hardware.
- **Resolución satelital.** 10 m/píxel sirve para zonificar, no para diagnosticar. El NDVI
  dice dónde hay un problema, no cuál es.
- **Altura y separación siguen desacopladas** en el formato de misión, aunque físicamente
  dependan una de la otra. Se resuelve cuando se caracterice una cámara real.
- **Regulación.** Un dron PX4 supera los 250 g y cae en categorías de ANAC más estrictas.
  Revisar antes de cualquier vuelo real sobre el campo.

## 7. Métricas de éxito

- ✅ Misión de barrido ejecutada end-to-end en simulador sin intervención manual.
- ⬜ Mapa NDVI del lote con zonas de bajo vigor identificadas (Sprint 2).
- ⬜ Frames geotaggeados con error de posición menor a la resolución de la imagen (Sprint 3).
- ⬜ Detector con precisión y recall ≥ 70% en el set de validación (Sprint 4).
- ⬜ Reporte generado en menos de 30 s desde el fin de la misión (Sprint 6).
- ⬜ Diez misiones consecutivas sin fallas de software (Sprint 8).

## 8. Próximos pasos

1. Elegir cómo acceder a Sentinel-2: Copernicus Browser para explorar a mano, o una
   biblioteca de Python para automatizarlo.
2. Descargar la escena más reciente sin nubes que cubra La Florida.
3. Calcular el NDVI y recortarlo contra el polígono que ya está en `missions/`.
