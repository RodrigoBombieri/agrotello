"""Trae del satélite solo el pedacito de imagen que cubre tu lote.

Una escena de Sentinel-2 cubre 110 x 110 km y pesa cerca de un gigabyte. Tu campo ocupa una
porción diminuta de eso. Este script busca la imagen de una fecha, calcula qué recuadro le
corresponde al lote y descarga únicamente esos píxeles.

- `_describir`: resume los valores leídos y cuánto se ahorró.
- `main`: elige la escena de una fecha y lee las tres bandas que necesitamos.

Técnico: la lectura vive en `dronesw.satelite`; este archivo es solo la interfaz de línea de
comandos y el informe. Sirve para comprobar en números la ventaja del formato COG: se leen
unos 1.100 píxeles de una escena de 120 millones.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from dronesw.mission.planner import cargar_mision
from dronesw.satelite import (
    BANDA_CLASIFICACION,
    BANDA_INFRARROJO,
    BANDA_ROJO,
    buscar_escenas,
    leer_banda,
)

BANDAS = (BANDA_ROJO, BANDA_INFRARROJO, BANDA_CLASIFICACION)


def _describir(nombre: str, datos: np.ndarray, info: dict, segundos: float) -> None:
    alto, ancho = datos.shape
    leidos = alto * ancho
    proporcion = info["escena_px"] // leidos

    print(f"\n  {nombre}")
    print(f"    recorte        {ancho} x {alto} px  ({leidos:,} de {info['escena_px']:,})")
    print(f"    proporción     1 de cada {proporcion:,} píxeles de la escena")
    print(f"    valores        min {datos.min()}  max {datos.max()}  medio {datos.mean():.0f}")
    print(f"    escala {info['escala']}   desplazamiento {info['desplazamiento']}")
    print(f"    tardó          {segundos:.1f} s")


def main() -> int:
    p = argparse.ArgumentParser(description="Lee del satélite solo el recorte del lote.")
    p.add_argument("mision", type=Path, help="Archivo YAML del lote")
    p.add_argument("--fecha", required=True, help="Día de la escena (AAAA-MM-DD)")
    args = p.parse_args()

    mision = cargar_mision(args.mision)
    escenas = buscar_escenas(mision, args.fecha, args.fecha)
    if not escenas:
        print(f"No hay ninguna escena del {args.fecha} sobre el lote.")
        return 1

    escena = escenas[0]
    print(f"\nEscena {escena.id}")
    print(f"Lote {mision.nombre}")

    for banda in BANDAS:
        if banda not in escena.assets:
            print(f"\n  {banda}: no está en esta escena")
            continue
        inicio = time.perf_counter()
        datos, info = leer_banda(escena.assets[banda].href, mision)
        _describir(banda, datos, info, time.perf_counter() - inicio)

    return 0


if __name__ == "__main__":
    sys.exit(main())
