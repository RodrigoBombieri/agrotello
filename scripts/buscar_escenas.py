"""Pregunta al catálogo satelital qué imágenes hay de tu lote.

No descarga ninguna imagen: solo consulta el índice y lista qué pasadas del satélite
cubrieron el campo en un rango de fechas, con cuánta nube tenía cada una.

- `main`: procesa los argumentos, consulta el catálogo y muestra el resultado.

Técnico: la consulta en sí vive en `dronesw.satelite`; este archivo es solo la interfaz de
línea de comandos. El porcentaje de nube que informa el catálogo es el de la escena entera de
110 x 110 km, no el del lote: sirve para ordenar candidatas, no para decidir. Esa decisión se
toma después, mirando la capa de clasificación sobre el recorte del campo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dronesw.mission.planner import cargar_mision
from dronesw.satelite import buscar_escenas


def main() -> int:
    p = argparse.ArgumentParser(description="Lista las escenas satelitales disponibles del lote.")
    p.add_argument("mision", type=Path, help="Archivo YAML del lote")
    p.add_argument("--desde", default="2026-07-01", help="Fecha inicial (AAAA-MM-DD)")
    p.add_argument("--hasta", default="2026-09-15", help="Fecha final (AAAA-MM-DD)")
    p.add_argument("--nubes-max", type=float, default=100.0, help="Descarta escenas con más nube")
    args = p.parse_args()

    mision = cargar_mision(args.mision)
    escenas = buscar_escenas(mision, args.desde, args.hasta)

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

    print("\nBandas disponibles en la primera escena:")
    print("  " + ", ".join(sorted(escenas[0].assets)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
