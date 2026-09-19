# AgroTello

Inspección agronómica autónoma: planifica un relevamiento sobre un lote real, lo vuela solo,
analiza la salud del cultivo y produce un mapa georreferenciado de dónde anda bien y dónde
no.

Dos frentes que avanzan en paralelo y terminan encontrándose:

- **Vuelo** → PX4 + MAVSDK-Python sobre el simulador SITL. Planifica el recorrido que cubre
  un lote y lo ejecuta con vigilancia de batería.
- **Análisis** → NDVI de Sentinel-2, gratis y sin hardware, sobre el mismo lote que vuela el
  simulador.

Ver `PLANNING.md` para la arquitectura y el roadmap por sprints, `docs/herramientas.md` para
el stack y cómo fluyen los datos, y `docs/comandos.md` para la convención de terminales.

## Qué hace hoy

1. Define un lote en un archivo de texto: contorno en coordenadas y parámetros de vuelo
   (altura, separación entre pasadas, velocidad, orientación, margen del alambrado).
2. Calcula el recorrido en zigzag que lo cubre, recortado contra su forma real.
3. Lo vuela solo en el simulador: despega, recorre los waypoints, vuelve y aterriza,
   abortando si la batería no alcanza.
4. Le pregunta al catálogo de Sentinel-2 qué imágenes hay del lote y con cuánta nube.
5. Baja únicamente el recorte del campo, sin descargar la escena de un gigabyte.
6. Calcula el NDVI descartando nubes, sombras y lo que queda fuera del alambrado.
7. Separa el lote en zona floja, normal y vigorosa, cada una medida en hectáreas.
8. Dibuja todo eso como un mapa sobre la foto satelital, en una página que se abre con doble
   clic.

**Todavía no:** comparar dos fechas entre sí, procesar imágenes tomadas desde el dron, ni
generar reportes.

## Setup

El entorno corre sobre WSL2/Ubuntu: el simulador PX4 no se ejecuta nativo en Windows. Ver
`docs/sitl_setup.md` para levantar el simulador.

```bash
python3 -m venv ~/venvs/agrotello        # el venv vive fuera del repo, a propósito
source ~/venvs/agrotello/bin/activate
pip install -e .                          # instala el paquete y sus dependencias
```

Sin `pip install -e .` los scripts no encuentran `dronesw`.

## Uso

**Planificar y volar** — con el simulador corriendo (`HEADLESS=1 make px4_sitl gz_x500`
desde `~/PX4-Autopilot`):

```bash
python scripts/run_mission.py missions/lote_prueba.yaml --solo-plan --geojson  # solo planifica
python scripts/run_mission.py missions/lote_prueba.yaml                        # planifica y vuela
python scripts/sprint0_hover.py                                                # vuelo de prueba
```

El recorrido queda en `mapas/` y se ve arrastrándolo a geojson.io. Ver
`docs/mission_format.md` para el formato del lote.

**Analizar el cultivo** — no necesita simulador ni internet más allá del catálogo:

```bash
python scripts/buscar_escenas.py missions/lote_prueba.yaml --desde 2026-07-01 --hasta 2026-09-15
python scripts/ndvi_lote.py missions/lote_prueba.yaml --fecha 2026-08-30 --mapa
```

El mapa queda en `mapas/ndvi_AAAAMMDD.html`. Ver `docs/ndvi.md` para qué significan los
números, las trampas del dato satelital y cómo leer los resultados.

## Estado

- **Sprint 0 — cerrado.** Entorno, PX4 volando en SITL, failsafe de batería verificado en
  vuelo.
- **Sprint 1 — cerrado.** Formato de misión, `FlightController`, planificador de waypoints
  con Shapely, ejecutor con vigilancia de batería. Misión de 22 waypoints volada sobre un
  lote real de 5,23 ha.
- **Sprint 2 — cerrado.** NDVI satelital: catálogo, lectura por rangos de bytes, máscara de
  nubes, recorte al polígono, zonas de vigor y mapa.

Próximo: Sprint 3 — captura de imágenes desde el simulador. Ver `PLANNING.md` sección 5.

## Tests

```bash
pytest
```

Todo lo que se puede probar sin dron, sin simulador y sin internet: la geometría del
planificador, la aritmética del NDVI, las zonas, el coloreado del mapa y el recorte
satelital (contra imágenes fabricadas en el momento).

## Datos

Contiene información Copernicus Sentinel modificada, 2026.
