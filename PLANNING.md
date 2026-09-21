# AgroTello — Inspección agronómica autónoma con PX4

Planificación técnica: planificar y volar misiones sobre un lote, detectar problemas en el
cultivo y entregar un reporte accionable.

## 1. Visión del producto

Un programa con una pantalla. Se ingresan los datos de conexión del dron, se dibuja el
contorno del lote sobre la imagen satelital, y desde ahí el sistema calcula el recorrido que
lo cubre, lo hace volar solo, y muestra dónde el cultivo anda flojo y dónde bien, medido en
hectáreas.

Un mismo polígono alimenta las dos mitades: **el plan de vuelo** y **el análisis satelital**.

### Qué se detecta y con qué

| Qué se busca | Con qué se detecta | De dónde salen los datos | Estado |
|---|---|---|---|
| Zonas de bajo vigor y estrés hídrico | NDVI (necesita infrarrojo) | **Sentinel-2**, gratis, 10 m/píxel | ✅ funciona |
| Plagas, enfermedades, malezas | Visión por computadora sobre RGB | **Imágenes de dron**, resolución centimétrica | ⛔ fuera de alcance |

No compiten: cubren escalas distintas. El satélite ve el lote entero y dice *dónde mirar*;
el dron bajaría a ver *qué está pasando ahí*. Un píxel satelital de 10 metros jamás va a
mostrar una hoja enferma, y un dron no va a cubrir 5.000 hectáreas en una tarde.

La segunda fila quedó **fuera de alcance** porque necesita imágenes aéreas propias, y sin un
dron con cámara lo único disponible es el mundo vacío del simulador. Ver *Fuera de alcance*
en el roadmap.

### Sobre el hardware

El proyecto nació apuntando a un DJI Tello y **esa decisión se revirtió** (2026-09-08). El
Tello es un sistema cerrado: no se le puede cambiar ni agregar la cámara, así que nunca
podría hacer NDVI. El objetivo de hardware pasó a ser un **dron PX4** (Holybro X500 V2,
~USD 550), que acepta cualquier cámara — incluida una NoIR de ~USD 30 que sí da infrarrojo.

**El sistema queda listo para conectarse a un dron real, pero sin probar en uno.** La capa de
vuelo pasa por la interfaz `FlightController` y el backend de PX4 se conecta con una cadena de
texto: `udpin://0.0.0.0:14540` apunta al simulador y `serial:///dev/ttyUSB0:57600` apuntaría a una
radio. El protocolo es el mismo. Lo que el simulador no ejercita es todo lo demás: latencia
del enlace, calidad de GPS, viento, geofence, regulación.

El nombre del repo quedó de la etapa Tello. Se mantiene por continuidad del historial.

## 2. Arquitectura

```
                    ┌────────────────────────────────┐
                    │           Navegador              │
                    │  dibujar el lote · ver el plan   │
                    │  volar en vivo · ver el NDVI     │
                    └───────────────┬────────────────┘
                                    │  HTTP + WebSocket
                    ┌───────────────▼────────────────┐
                    │        Servidor (Python)         │
                    └───────┬───────────────┬────────┘
                            │               │
         ─── vuelo ─────────┘               └───────── análisis ───
                            │                                │
                ┌───────────▼──────────┐        ┌────────────▼───────────┐
                │   mission/planner      │        │      satelite.py         │
                │   zigzag sobre el lote │        │  busca escenas y recorta │
                └───────────┬──────────┘        └────────────┬───────────┘
                            │                                │
                ┌───────────▼──────────┐        ┌────────────▼───────────┐
                │   mission/executor     │        │  vision/indices  NDVI    │
                │   vuela y vigila       │        │  vision/zonas    ha      │
                └───────────┬──────────┘        │  vision/mapa     dibujo  │
                            │                    └────────────────────────┘
                ┌───────────▼──────────┐
                │  flight/base  (ABC)    │
                │  px4_controller        │
                └───────────┬──────────┘
                            │  MAVSDK
                ┌───────────▼──────────┐
                │  PX4 SITL o dron real  │
                └──────────────────────┘
```

Las dos mitades son independientes y se cruzan solo en el polígono del lote: el análisis
satelital no necesita que haya un dron, y el vuelo no necesita que haya imágenes.

La capa de vuelo pasa por la interfaz abstracta `FlightController`, de modo que el resto del
sistema no sabe ni le importa si abajo hay un simulador o un dron físico: solo cambia la
cadena de conexión.

## 3. Estructura del repo

```
agrotello/
├── CLAUDE.md              # contexto de trabajo entre sesiones
├── PLANNING.md            # este archivo
├── README.md
├── pyproject.toml         # paquete instalable (pip install -e .)
├── missions/              # un YAML por lote (lo escribe la pantalla y lo lee la CLI)
├── mapas/                 # recorridos y mapas de NDVI, uno por corrida
├── capturas/              # fotos del simulador (ignorado por git)
├── sim/                   # ajustes al simulador que van copiados dentro de PX4
├── docs/
│   ├── comandos.md        # comandos por entorno y terminal
│   ├── herramientas.md    # stack y flujo de datos
│   ├── mission_format.md  # formato del YAML de misión
│   ├── ndvi.md            # el análisis satelital, sus trampas y cómo leerlo
│   └── sitl_setup.md      # cómo levantar el simulador
├── src/dronesw/
│   ├── satelite.py                  # catálogo Sentinel-2, lectura y recorte
│   ├── flight/
│   │   ├── base.py                  # FlightController + capacidades opcionales
│   │   └── px4_controller.py        # implementación MAVSDK
│   ├── mission/
│   │   ├── planner.py               # grilla de waypoints con Shapely
│   │   └── executor.py              # orquestación y vigilancia de batería
│   ├── vision/
│   │   ├── indices.py               # NDVI y máscara de nubes
│   │   ├── zonas.py                 # zonas de vigor en hectáreas
│   │   ├── mapa.py                  # PNG + página con el mapa
│   │   └── comparar.py              # cruce de persistencia entre dos fechas
│   └── web/
│       ├── servidor.py              # FastAPI: la API y la pantalla
│       ├── vuelo.py                 # la sesión de vuelo en vivo
│       └── estatico/                # index.html, estilo.css, app.js
├── scripts/                         # entradas de línea de comandos
└── tests/unit/                      # 93 tests, sin red ni simulador
```

## 4. Stack técnico

| Capa | Herramienta | Estado |
|---|---|---|
| Simulación de vuelo | PX4 SITL + Gazebo (headless) | ✅ en uso |
| Cliente de vuelo | MAVSDK-Python | ✅ en uso |
| Geometría de misión | Shapely | ✅ en uso |
| Configuración de misión | PyYAML | ✅ en uso |
| Catálogo satelital | pystac-client (Earth Search) | ✅ en uso |
| Lectura raster | rasterio (COG por rangos de bytes) | ✅ en uso |
| NDVI y zonas | NumPy | ✅ en uso |
| Mapas | matplotlib + Pillow + Leaflet | ✅ en uso |
| Cámara del simulador | `gz_x500_mono_cam` + gz-transport | ✅ leída (Sprint 3 cortado ahí) |
| Tests | pytest | ✅ en uso |
| Lint y formato | ruff + black, en GitHub Actions | ✅ en uso |
| Servidor de la aplicación | FastAPI + WebSocket | ✅ en uso |
| Pantalla | HTML + Leaflet-Geoman, sin framework | ✅ en uso |

Las dependencias de runtime se declaran en `pyproject.toml`, y se van sumando a medida que
los módulos las usan de verdad.

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

### Sprint 2 — NDVI satelital del lote ✅ *(cerrado 2026-09-19)*

Catálogo de Sentinel-2, lectura del recorte del lote por rangos de bytes, NDVI con máscara de
nubes, recorte contra el polígono real, zonas de vigor en hectáreas y mapa sobre la imagen
satelital. Más 57 tests y `docs/ndvi.md`.

**Entregable cumplido, y con resultado agronómico real:** el lote creció de 0,48 a 0,63 de
NDVI medio entre julio y agosto, y hay **1,05 ha que quedan flojas en las dos fechas**, en una
mancha contigua. A 10 m/píxel las 5,23 ha de La Florida son 523 píxeles: grueso para ver una
planta, suficiente para decidir a qué sector ir.

### Sprint 3 — Captura desde el dron ⏸ *(cortado en 3.1, 2026-09-19)*

Se completó el 3.1: `scripts/probar_camara.py` lee la cámara del simulador desde Python y
guarda un cuadro en disco. Funciona y está commiteado.

**Se discontinuó ahí, a propósito.** Los pasos que seguían —capturar durante el vuelo,
geoetiquetar cada foto, integrarlo a la misión— construyen una cañería para imágenes aéreas
propias, y el mundo del simulador no tiene cultivo: las fotos salen de un piso gris vacío.
Es infraestructura para un hardware que todavía no existe. Se retoma el día que haya una
cámara real montada en un dron real, no antes.

Lo que sí dejó, y queda: el modelo de cámara ajustado para que el simulador sea usable en
WSL2 (`sim/`), y el entorno destrabado —protobuf, venv, renderizado— documentado en
`CLAUDE.md`.

### Sprint 4 — La aplicación ✅ *(cerrado 2026-09-21)*

Hoy el sistema funciona por línea de comandos, con el lote definido en un YAML escrito a
mano, y los resultados desparramados entre un GeoJSON, una página HTML y texto de terminal.

El producto terminado es **un programa con una pantalla**: se ingresan los datos de conexión
del dron, se dibuja el lote sobre la imagen satelital, y desde ahí se planifica, se vuela y
se analiza. Un solo polígono alimenta las dos mitades del sistema —el plan de vuelo y el
análisis satelital— que hoy funcionan por separado y no se hablan.

Se resuelve con un servidor HTTP en Python y una página en el navegador. El navegador aporta
el mapa (Leaflet, que ya se usa en los mapas de NDVI) y el aspecto; Python sigue haciendo
todo lo que ya hace. **Nada de lo construido se tira:** la pantalla escribe el mismo YAML que
lee la línea de comandos, así que las dos formas de usarlo conviven.

- **4.1 ✅ El servidor.** Exponer por HTTP lo que ya existe: planificar un recorrido, buscar
  qué fechas de satélite hay, analizar un lote. Sin pantalla todavía.
  *Entregable: los endpoints responden desde el navegador.*

- **4.2 ✅ La pantalla.** El mapa sobre la imagen satelital, dibujar el lote encima, los
  parámetros de vuelo al costado, y los resultados del análisis al otro.
  *Entregable: dibujar un lote y ver su NDVI y sus zonas sin tocar la terminal.*

- **4.3 ✅ El vuelo en vivo.** Los datos de conexión al dron, y volar la misión desde la
  pantalla viendo la posición moverse sobre el mapa, con la batería y el progreso.
  *Entregable: una misión completa volada desde el navegador.*

- **4.4 ✅ Comparar fechas y cierre.** El cruce de persistencia: marca lo que sale flojo (o
  vigoroso) en las dos fechas, contra la vara de lo que daría el azar. Ordena cada fecha
  contra sí misma, así que no depende del nivel del cultivo ni de la escala de colores.
  Más `docs/aplicacion.md`, la sección de comparación en `docs/ndvi.md` y el README final.
  *Entregable cumplido: el proyecto terminado, con 93 tests.*

### Fuera de alcance

Lo que estaba en el roadmap original y se descarta. El roadmap se escribió el segundo día,
antes de saber lo que costaba cada pieza:

| Lo que era | Por qué se cae |
|---|---|
| Detector de plagas con YOLOv8 | Necesita imágenes aéreas propias. Es un proyecto de visión por computadora aparte, no software de drones. |
| Mosaico del lote con las detecciones ubicadas | Depende del anterior, y el mosaico por sí solo es un problema grande (correspondencia de rasgos, ajuste de haces). |
| API REST | La aplicación del Sprint 4 ya es la interfaz. Envolverla otra vez en HTTP no le agrega nada a un proyecto de portfolio. |
| Hardening: geofence, reconexión, logging estructurado | Tiene sentido para un dron real volando sobre un campo real. Contra un simulador, no se ejercita. |
| Reporte PDF | Absorbido por la pantalla del Sprint 4, que muestra lo mismo y además es interactiva. |

Nada de esto está perdido: queda escrito acá por si algún día hay hardware y ganas.

## 6. Riesgos y consideraciones

- **Brecha simulador-realidad.** El SITL valida la lógica de misión, no el viento ni el
  comportamiento de un autopiloto físico. El primer vuelo real va a mostrar cosas que el
  simulador no mostró.
- **Resolución satelital.** 10 m/píxel sirve para zonificar, no para diagnosticar. El NDVI
  dice dónde hay un problema, no cuál es.
- **Altura y separación siguen desacopladas** en el formato de misión, aunque físicamente
  dependan una de la otra. Se resuelve cuando se caracterice una cámara real.
- **Dos fechas de satélite no son una tendencia.** El patrón de zonas flojas se confirmó
  entre dos pasadas; con más fechas puede afinarse o caerse.
- **Regulación.** Un dron PX4 supera los 250 g y cae en categorías de ANAC más estrictas.
  Revisar antes de cualquier vuelo real sobre el campo.

## 7. Métricas de éxito

- ✅ Misión de barrido ejecutada end-to-end en simulador sin intervención manual.
- ✅ Mapa NDVI del lote con las zonas de bajo vigor identificadas y medidas en hectáreas.
- ✅ Un resultado agronómico real y verificable sobre el campo real.
- ⬜ Un lote dibujado en pantalla se planifica, se vuela y se analiza sin tocar la terminal.
- ⬜ La aplicación acepta la cadena de conexión de un dron físico sin cambiar código.
- ⬜ Un tercero puede clonar el repo, seguir el README y llegar a un mapa de NDVI.

## 8. Estado final

**El proyecto está terminado.** Los cuatro sprints del plan están cerrados y lo que quedó
afuera está en *Fuera de alcance*, arriba, con el motivo de cada descarte.

Lo que se podría retomar algún día, en orden de valor:

1. **Más fechas de satélite.** Dos pasadas no son una tendencia. El mismo cruce sobre cinco
   o seis fechas del ciclo diría bastante más, y no requiere escribir casi nada nuevo.
2. **El Sprint 3, el día que haya un dron con cámara.** La captura geoetiquetada quedó
   empezada en el 3.1 y el entorno destrabado.
3. **Los dos errores de borde** listados abajo, si alguna vez se trabaja con lotes mucho
   más chicos que estas 5 ha.
