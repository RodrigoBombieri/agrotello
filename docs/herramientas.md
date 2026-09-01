# Herramientas, tecnologías y frameworks

Referencia del stack completo del proyecto: qué hace cada pieza, por qué está y cómo se
conecta con las demás. Para la justificación arquitectónica de fondo ver `../PLANNING.md`.

## Resumen por capa

| Capa | Herramienta | Rol en el proyecto |
|---|---|---|
| Lenguaje | **Python 3.10+** | Todo el código del proyecto |
| Firmware de vuelo | **PX4 Autopilot** | El "cerebro" del dron: estabiliza, ejecuta misiones, reporta telemetría |
| Simulador | **PX4 SITL** (+ Gazebo o jMAVSim) | Corre PX4 en la PC sin hardware; permite desarrollar misiones sin dron |
| Protocolo | **MAVLink** | Idioma común entre el dron (o simulador) y cualquier software externo |
| Cliente de vuelo | **MAVSDK-Python** | Librería con la que nuestro código manda comandos y lee telemetría |
| Estación de control | **QGroundControl** | GUI para ver el dron volar, inspeccionar la misión y depurar visualmente |
| Dron de visión | **DJI Tello EDU** + **djitellopy** | Hardware real para capturar imágenes de cultivo |
| Visión (base) | **OpenCV** + **NumPy** | Lectura de video, procesamiento de frames, cálculo de índices, stitching |
| Visión (modelo) | **Ultralytics YOLOv8** | Detección de plagas/enfermedades en las imágenes |
| API | **FastAPI** + **Uvicorn** | Orquestación: lanzar misiones, exponer telemetría y reportes |
| Config | **pydantic-settings** | Carga y valida la configuración desde `.env` |
| Logging | **loguru** | Registro estructurado de vuelos y procesamiento |
| Reportes | **fpdf2** | Genera el PDF final con mapa y anomalías |
| Entorno (Windows) | **WSL2** + Ubuntu | Donde corre el SITL; PX4 no se desarrolla nativo en Windows |
| Contenedores | **Docker** | Forma más simple de levantar el SITL sin compilar PX4 |
| Editor | **VS Code** (+ Remote-WSL) | IDE, editando desde Windows contra el entorno WSL |
| Calidad | **ruff**, **black**, **pre-commit** | Lint y formato automático antes de cada commit |
| Tests | **pytest** (+ asyncio, mock) | Tests unitarios e integración, con MAVSDK/djitellopy mockeados |
| CI | **GitHub Actions** | Corre lint y tests en cada push/PR |

## Cómo se interconectan

El sistema tiene **dos flujos de datos que corren por separado y confluyen recién en el
reporte final**. Esto es consecuencia directa del esquema híbrido (ver PLANNING.md sección 1):
la misión se desarrolla contra PX4 simulado, la visión se alimenta de imágenes reales del Tello.

### Flujo A — Misión y posición (PX4 / MAVSDK)

```
  PX4 SITL (dentro de WSL2/Docker)
        │
        │  MAVLink sobre UDP  (puerto 14540)
        ▼
  MAVSDK-Python  ──►  Px4FlightController  ──►  MissionExecutor
        │                                              │
        │  telemetría (lat/lon/alt, batería, estado)    │  waypoints
        ▼                                              ▼
  mapping/geolocate.py                          MissionPlanner
        │                                    (genera grilla GPS)
        │  posiciones con timestamp
        ▼
   [se cruza con el Flujo B]
```

1. **PX4 SITL** simula el dron y el mundo físico. Expone MAVLink por UDP.
2. **MAVSDK-Python** se conecta a ese puerto (`udpin://0.0.0.0:14540`, configurado en `.env`
   como `MAVSDK_CONNECTION`) y traduce el protocolo MAVLink a llamadas Python legibles
   (`drone.action.takeoff()`, `drone.mission.upload_mission()`, `drone.telemetry.position()`).
3. **`MissionPlanner`** toma el polígono del lote (lat/lon) y genera la grilla de waypoints.
4. **`MissionExecutor`** sube esos waypoints vía MAVSDK y arranca la misión.
5. Durante el vuelo, **`geolocate.py`** se suscribe al stream de telemetría y va guardando la
   posición GPS real con timestamp — esta es la base para georreferenciar las detecciones.
6. **QGroundControl** se conecta al mismo SITL en paralelo, solo para mirar: no participa del
   flujo de datos del programa, es una herramienta de depuración visual.

### Flujo B — Imágenes y detección (Tello / visión)

```
  Tello EDU (hardware real)
        │
        │  WiFi propio del dron, stream de video UDP
        ▼
  djitellopy  ──►  TelloFlightController  ──►  vision/capture.py
                                                     │
                                                     │  frames (numpy arrays vía OpenCV)
                                    ┌────────────────┴────────────────┐
                                    ▼                                 ▼
                          vision/indices.py                  vision/detector.py
                         (ExG / VARI con NumPy)              (YOLOv8 / Ultralytics)
                                    │                                 │
                                    │  zonas de estrés hídrico         │  bounding boxes de plagas
                                    └────────────────┬────────────────┘
                                                     ▼
                                              [detecciones]
```

1. El **Tello EDU** crea su propia red WiFi; la laptop se conecta a ella.
2. **djitellopy** manda comandos por UDP y recibe el stream de video.
3. **`capture.py`** usa **OpenCV** para leer ese stream frame por frame. Cada frame es un array
   de **NumPy** — este es el formato común que atraviesa toda la capa de visión.
4. El mismo frame se procesa por dos caminos independientes:
   - **`indices.py`** calcula ExG/VARI con operaciones NumPy sobre los canales RGB, y devuelve
     un mapa de vigor/estrés de la vegetación.
   - **`detector.py`** pasa el frame por el modelo **YOLOv8** entrenado, y devuelve detecciones
     de plagas/enfermedades con su confianza.

### Confluencia — Mapa y reporte

```
  [posiciones GPS del Flujo A]  +  [detecciones del Flujo B]
                        │
                        ▼
              mapping/geolocate.py          vision/stitching.py
           (asocia detección ↔ coordenada)   (mosaico del lote con OpenCV)
                        │                            │
                        └──────────┬─────────────────┘
                                   ▼
                        reporting/pdf_report.py
                             (fpdf2)
                                   │
                                   ▼
                          Reporte PDF final
                    (mapa + anomalías + estadísticas)
```

Cada detección se asocia con la posición GPS más cercana en el tiempo, quedando
georreferenciada. **`stitching.py`** arma el mosaico visual del lote con OpenCV, y
**`pdf_report.py`** compone todo en el PDF con **fpdf2**.

### Capa de orquestación (transversal)

**FastAPI** (servido por **Uvicorn**) envuelve todo lo anterior y lo expone:

- `POST` para lanzar una misión, eligiendo backend (`sitl` o `tello`).
- **WebSocket** que reenvía la telemetría de MAVSDK y/o el video del Tello en vivo al cliente.
- `GET` para listar y descargar los reportes generados.

**pydantic-settings** carga la configuración desde `.env` (dirección de MAVSDK, IP del Tello,
umbrales de batería, geofence) y la valida con tipos, así que un valor mal escrito falla al
arrancar y no en medio de un vuelo. **loguru** registra todo el recorrido — comandos enviados,
telemetría recibida, detecciones — para poder reconstruir qué pasó después de cada misión.

## Entorno de desarrollo (Windows)

```
  Windows
    ├── VS Code ──(Remote-WSL)──┐
    ├── QGroundControl          │   observa el SITL
    └── WSL2 / Ubuntu ◄─────────┘
          └── Docker
                └── PX4 SITL  ──MAVLink/UDP──►  código Python del proyecto
```

PX4 no se desarrolla nativo en Windows: el simulador y el toolchain viven dentro de **WSL2**.
**VS Code** corre en Windows pero edita y ejecuta contra WSL mediante la extensión Remote-WSL,
así que la experiencia es la de trabajar local. **Docker** (dentro de WSL) es la vía más simple
para levantar el SITL sin compilar PX4 desde fuente. Ver `sitl_setup.md` para el paso a paso.

## Calidad y automatización

- **ruff** (lint) y **black** (formato) corren automáticamente al guardar en VS Code, y otra vez
  vía **pre-commit** antes de cada commit — el código no llega al repo sin formatear.
- **pytest** con **pytest-asyncio** (MAVSDK es async) y **pytest-mock** para simular el dron:
  ni el SITL ni el Tello son reproducibles en CI, así que se mockean.
- **GitHub Actions** repite lint y tests en cada push, para que nada roto quede en `main`.


Fase A: Preparación e Inicio (Ocurre en secuencia)
(1) config.py: Es lo primero que se ejecuta en milisegundos. Lee el archivo .env para saber las credenciales, puertos de conexión del simulador y rutas del modelo de IA. Si esto falla, nada arranca.
(2) api/main.py (y api/routes/): Levanta el servidor FastAPI. Se queda "escuchando" hasta que el usuario le da al botón virtual de Iniciar Misión.
(3) mission/planner.py: Cuando el usuario inicia la misión, este script toma las coordenadas del polígono del campo y calcula matemáticamente la grilla de puntos (waypoints) en zigzag. Crea el mapa de ruta en papel antes de volar.

Fase B: El Vuelo (Todo ocurre EN PARALELO) Una vez que la ruta está lista, se dispara el vuelo. Los siguientes scripts corren de forma simultánea interactuando entre sí:
(4) flight/base.py: No se ejecuta directamente, pero es el molde que define las reglas para los controladores que se van a instanciar en este momento.
(5) flight/px4_controller.py O flight/tello_controller.py: Se inicializa el controlador elegido. Abre los puertos de comunicación (UDP o WiFi) para empezar a mandar comandos físicos al dron.
(6) mission/executor.py: Toma el control. Agarra la ruta de planner.py y le empieza a decir al controlador seleccionado: "Muévete al punto 1... ahora al punto 2...".
(7) flight/safety.py: Un hilo en segundo plano que corre en paralelo a la par del ejecutor. Vigila cada segundo el nivel de batería y el rango de señal. Si algo sale mal, interrumpe al ejecutor y fuerza un aterrizaje.
(8) api/websocket.py: Transmite en vivo hacia tu pantalla la telemetría (altura, velocidad, batería) que va escupiendo el controlador en tiempo real.

Fase C: El Pipeline de Visión y Mapeo (En tiempo real durante el vuelo)Mientras el dron se mueve gracias a los pasos anteriores, la cámara empieza a escupir datos:
(9) vision/capture.py: Captura el stream de video crudo del DJI Tello (o la cámara simulada) frame por frame.
(10) vision/indices.py y vision/detector.py: Reciben los frames de capture.py. indices.py calcula el estrés hídrico (ExG/VARI) y detector.py le pasa YOLOv8 para buscar manchas o bichos.
(11) mapping/geolocate.py: En el milisegundo exacto en que el paso 10 encuentra una plaga, este script interrumpe al controlador de vuelo, le pide la coordenada GPS actual, y amarra la foto con la ubicación exacta en el espacio real.
Fase D: El Cierre y Post-Procesamiento (Ocurre al aterrizar)Cuando el dron termina la ruta completa y aterriza, se apagan los motores y entran en acción los últimos operarios:
(12) vision/stitching.py: Toma todas las fotos de referencia limpias acumuladas durante el viaje y las "cose" mediante OpenCV para armar la foto satelital gigante (ortomosaico) de todo el lote.
(13) reporting/pdf_report.py (usando reporting/templates/): Toma el mapa del paso 12, la lista de plagas georreferenciadas del paso 11, diseña los gráficos y exporta el reporte PDF final.
