"""Pregunta al catálogo satelital qué imágenes hay de tu lote.

No descarga ninguna imagen: solo consulta el índice y lista qué pasadas del satélite
cubrieron el campo en un rango de fechas, con cuánta nube tenía cada una.

- `_poligono_geojson`: traduce el lote del archivo de misión al formato que espera el catálogo.
- `buscar`: consulta el catálogo y devuelve las escenas ordenadas por fecha.
- `main`: procesa los argumentos y muestra el resultado.

Técnico: usa la API STAC de Earth Search (Element 84), que indexa las copias en formato COG
del archivo de Sentinel-2 en AWS. El acceso es anónimo. El porcentaje de nube que informa el
catálogo es el de la escena entera de 110 x 110 km, no el del lote: sirve para ordenar
candidatas, no para decidir. Esa decisión la vamos a tomar después, mirando la capa SCL sobre
el recorte del campo.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from pystac_client import Client

from dronesw.mission.planner import DefinicionMision, cargar_mision

CATALOGO = "https://earth-search.aws.element84.com/v1"
COLECCION = "sentinel-2-l2a"


def _poligono_geojson(mision: DefinicionMision) -> dict:
    """Arma el polígono en el formato GeoJSON que espera el catálogo.

    GeoJSON usa (lon, lat) y exige que el anillo cierre repitiendo el primer vértice.
    """
    anillo = [[lon, lat] for lat, lon in mision.poligono]
    anillo.append(anillo[0])
    return {"type": "Polygon", "coordinates": [anillo]}


def buscar(mision: DefinicionMision, desde: str, hasta: str) -> list:
    """Devuelve las escenas que cubren el lote en el rango, ordenadas de vieja a nueva."""
    catalogo = Client.open(CATALOGO)
    resultado = catalogo.search(
        collections=[COLECCION],
        intersects=_poligono_geojson(mision),
        datetime=f"{desde}/{hasta}",
    )
    return sorted(
        resultado.items(),
        key=lambda escena: escena.datetime or datetime.min.replace(tzinfo=timezone.utc),
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Lista las escenas satelitales disponibles del lote.")
    p.add_argument("mision", type=Path, help="Archivo YAML del lote")
    p.add_argument("--desde", default="2026-07-01", help="Fecha inicial (AAAA-MM-DD)")
    p.add_argument("--hasta", default="2026-09-15", help="Fecha final (AAAA-MM-DD)")
    p.add_argument("--nubes-max", type=float, default=100.0, help="Descarta escenas con más nube")
    args = p.parse_args()

    mision = cargar_mision(args.mision)
    escenas = buscar(mision, args.desde, args.hasta)

    print(f"\nLote {mision.nombre} — {args.desde} a {args.hasta}")
    print(f"{len(escenas)} pasadas del satélite\n")

    mostradas = 0
    for escena in escenas:
        nubes = escena.properties.get("eo:cloud_cover")
        if nubes is not None and nubes > args.nubes_max:
            continue
        mostradas += 1
        print(f"  {escena.datetime:%d/%m/%Y}   nubes {nubes:5.1f} %   {escena.id}")

    if not mostradas:
        print("  (ninguna escena pasó el filtro de nubes)")
        return 1

    # Los nombres de las bandas son lo que vamos a necesitar en el paso siguiente.
    print("\nBandas disponibles en la primera escena:")
    print("  " + ", ".join(sorted(escenas[0].assets)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
