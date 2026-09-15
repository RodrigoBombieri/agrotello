"""Vuela un lote entero con un solo comando.

Lee el archivo del lote, calcula el recorrido, se conecta al dron y lo hace volar. Es el
punto de entrada del proyecto: todo lo demás son piezas que este archivo ordena.

- `_parsear_argumentos`: define las opciones de la línea de comandos.
- `_configurar_logging`: ajusta el detalle de los mensajes en pantalla.
- `_distancia_m`: distancia entre dos coordenadas, en metros.
- `_resumen_plan`: arma el resumen del recorrido antes de volar.
- `_exportar_geojson`: guarda el recorrido para verlo en un mapa.
- `_volar`: ejecuta la misión contra el dron.
- `_ruta_geojson`: decide dónde guardar el mapa del recorrido.
- `main`: encadena todo y devuelve el código de salida.

Técnico: `--solo-plan` calcula y muestra el recorrido sin conectarse a nada, así se puede
iterar sobre el YAML del lote sin levantar el simulador. El código de salida distingue misión
completada (0), interrumpida (1) y error (2), para poder encadenarlo en scripts. Las
distancias del resumen se calculan con haversine acá mismo, sin usar la proyección interna
del planificador, para no depender de su API privada. Los mapas se guardan en `mapas/` con
nombre y fecha, para poder comparar planes entre corridas.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import re
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from dronesw.flight.base import Waypoint
from dronesw.flight.px4_controller import Px4FlightController
from dronesw.mission.executor import EjecutorMision
from dronesw.mission.planner import DefinicionMision, cargar_mision, planificar

log = logging.getLogger("run_mission")

RADIO_TIERRA_M = 6_371_000
DIR_MAPAS = Path("mapas")


def _parsear_argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Planifica y vuela una misión de barrido sobre un lote.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("mision", type=Path, help="Archivo YAML con la definición del lote")
    p.add_argument(
        "--solo-plan",
        action="store_true",
        help="Calcula el recorrido y lo muestra, sin conectarse al dron",
    )
    p.add_argument(
        "--conexion",
        default="udpin://0.0.0.0:14540",
        help="Dirección MAVSDK del vehículo",
    )
    p.add_argument(
        "--bateria-minima",
        type=float,
        default=20.0,
        help="Porcentaje de batería por debajo del cual se aborta el vuelo",
    )
    p.add_argument(
        "--geojson",
        nargs="?",
        const="auto",
        default=None,
        help=(
            "Guarda el recorrido para verlo en un mapa (geojson.io). Sin valor, lo nombra "
            f"solo dentro de {DIR_MAPAS}/"
        ),
    )
    p.add_argument("-v", "--verboso", action="store_true", help="Muestra el detalle de MAVSDK")
    return p.parse_args()


def _configurar_logging(verboso: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


def _distancia_m(a: Waypoint, b: Waypoint) -> float:
    """Distancia sobre la superficie terrestre entre dos waypoints."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(h))


def _resumen_plan(mision: DefinicionMision, waypoints: Sequence[Waypoint]) -> str:
    recorrido = sum(_distancia_m(waypoints[i], waypoints[i + 1]) for i in range(len(waypoints) - 1))
    minutos = recorrido / mision.vuelo.velocidad_ms / 60

    return (
        f"\n  Lote:       {mision.nombre}"
        f"\n  Waypoints:  {len(waypoints)} ({len(waypoints) // 2} pasadas)"
        f"\n  Altura:     {mision.vuelo.altura_m:.0f} m"
        f"\n  Separación: {mision.vuelo.separacion_m:.0f} m"
        f"\n  Recorrido:  {recorrido:,.0f} m"
        f"\n  Duración:   ~{minutos:.1f} min a {mision.vuelo.velocidad_ms:.0f} m/s"
        f"\n              (sin contar ascenso, giros ni retorno)\n"
    )


def _ruta_geojson(nombre_lote: str, valor: str) -> Path:
    """Resuelve dónde guardar el mapa.

    Con `--geojson` a secas arma el nombre solo, a partir del lote y la fecha, para que cada
    corrida quede archivada y se puedan comparar planes. Con una ruta explícita, la respeta.
    """
    if valor != "auto":
        return Path(valor)

    slug = re.sub(r"[^a-z0-9]+", "_", nombre_lote.lower()).strip("_") or "mision"
    return DIR_MAPAS / f"{slug}_{datetime.now().astimezone():%Y%m%d_%H%M}.geojson"


def _exportar_geojson(waypoints: Sequence[Waypoint], ruta: Path) -> None:
    """Guarda el recorrido como GeoJSON, para pegarlo en geojson.io y verlo sobre el mapa.

    Es la forma más simple de validar visualmente un plan sin depender de la interfaz del
    simulador, que en WSL no siempre arranca.
    """
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"nombre": "recorrido"},
                "geometry": {
                    "type": "LineString",
                    # GeoJSON usa (lon, lat), al revés de como lo escribimos nosotros.
                    "coordinates": [[w.lon, w.lat] for w in waypoints],
                },
            }
        ],
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(geojson, indent=2), encoding="utf-8")
    log.info("Recorrido exportado a %s", ruta)


async def _volar(
    waypoints: Sequence[Waypoint], args: argparse.Namespace, velocidad_ms: float
) -> int:
    dron = Px4FlightController(direccion=args.conexion, velocidad_ms=velocidad_ms)
    ejecutor = EjecutorMision(dron, bateria_minima_pct=args.bateria_minima)

    resultado = await ejecutor.ejecutar(waypoints)
    log.info("%s", resultado)
    return 0 if resultado.completada else 1


def main() -> int:
    args = _parsear_argumentos()
    _configurar_logging(args.verboso)

    try:
        mision = cargar_mision(args.mision)
        waypoints = planificar(mision)
    except (OSError, ValueError, KeyError) as e:
        log.error("No se pudo preparar la misión: %s", e)
        return 2

    log.info("Plan de vuelo:%s", _resumen_plan(mision, waypoints))

    if args.geojson:
        _exportar_geojson(waypoints, _ruta_geojson(mision.nombre, args.geojson))

    if args.solo_plan:
        log.info("Modo --solo-plan: no se vuela nada")
        return 0

    try:
        return asyncio.run(_volar(waypoints, args, mision.vuelo.velocidad_ms))
    except KeyboardInterrupt:
        log.warning("Interrumpido por el usuario. El dron sigue con su última orden.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
