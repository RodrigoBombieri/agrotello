"""Calcula qué tan sana está la vegetación del lote, según el satélite.

Busca la imagen de una fecha, trae el recorte del campo, aplica la fórmula del NDVI y descarta
los píxeles tapados por nubes. Informa el resultado junto con qué parte del lote se pudo ver
de verdad.

- `_histograma`: dibuja la distribución de valores con caracteres de texto.
- `main`: encadena la búsqueda, la lectura, el cálculo, la zonificación, el mapa y el informe.

Técnico: la clasificación se lee forzando la forma de las bandas de color, porque viene a 20 m
y ellas a 10. Si la cobertura útil baja del umbral, la fecha se descarta: un promedio calculado
sobre la mitad despejada del lote parece válido pero no representa el campo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from dronesw.mission.planner import cargar_mision
from dronesw.satelite import (
    BANDA_CLASIFICACION,
    BANDA_INFRARROJO,
    BANDA_ROJO,
    buscar_escenas,
    leer_banda,
    mascara_del_lote,
    reproyectar_a_grados,
)
from dronesw.vision.indices import calcular_ndvi, mascara_utilizable, resumir
from dronesw.vision.mapa import colorear, guardar_html, guardar_png
from dronesw.vision.zonas import clasificar

COBERTURA_MINIMA_PCT = 80.0


def _histograma(ndvi: np.ndarray, columnas: int = 10) -> str:
    """Dibuja la distribución del NDVI, para ver de un vistazo si el lote es parejo."""
    valores = ndvi[~np.isnan(ndvi)]
    cuentas, bordes = np.histogram(valores, bins=columnas)
    tope = cuentas.max() or 1

    lineas = []
    for i, cuenta in enumerate(cuentas):
        barra = "#" * int(30 * cuenta / tope)
        lineas.append(f"    {bordes[i]:5.2f} a {bordes[i + 1]:5.2f}  {barra} {cuenta}")
    return "\n".join(lineas)


def main() -> int:
    p = argparse.ArgumentParser(description="Calcula el NDVI del lote para una fecha.")
    p.add_argument("mision", type=Path, help="Archivo YAML del lote")
    p.add_argument("--fecha", required=True, help="Día de la escena (AAAA-MM-DD)")
    p.add_argument("--mapa", action="store_true", help="Generar también el mapa en mapas/")
    args = p.parse_args()

    mision = cargar_mision(args.mision)
    escenas = buscar_escenas(mision, args.fecha, args.fecha)
    if not escenas:
        print(f"No hay ninguna escena del {args.fecha} sobre el lote.")
        return 1

    escena = escenas[0]
    print(f"\nLote {mision.nombre} — {escena.datetime:%d/%m/%Y}")
    print(f"Escena {escena.id}")

    rojo, info = leer_banda(escena.assets[BANDA_ROJO].href, mision)
    infrarrojo, _ = leer_banda(escena.assets[BANDA_INFRARROJO].href, mision)
    # La clasificación viene a 20 m: se fuerza a la forma de las bandas de color.
    clasificacion, _ = leer_banda(escena.assets[BANDA_CLASIFICACION].href, mision, forma=rojo.shape)

    dentro = mascara_del_lote(mision, info["crs"], info["transformacion"], rojo.shape)
    ndvi = calcular_ndvi(rojo, infrarrojo, mascara=mascara_utilizable(clasificacion) & dentro)
    resumen = resumir(ndvi, dentro=dentro)
    zonificacion = clasificar(ndvi)

    print(f"\n  {resumen}")
    print(
        f"  recorte {rojo.shape[0]} x {rojo.shape[1]} px, {resumen.pixeles_totales} dentro del lote"
    )
    print(f"  superficie medida  {zonificacion.hectareas:.2f} ha")
    print(f"  percentiles 2 y 98  {resumen.p2:.3f} a {resumen.p98:.3f}")
    print(f"\n  distribución:\n{_histograma(ndvi)}")

    print(f"\n  zonas (cortes en {zonificacion.corte_bajo:.3f} y {zonificacion.corte_alto:.3f}):")
    for zona in zonificacion.zonas:
        print(
            f"    {zona.nombre:9} {zona.hectareas:5.2f} ha "
            f"{zonificacion.porcentaje(zona):5.1f} %   NDVI medio {zona.ndvi_medio:.3f}"
        )

    if zonificacion.uniforme:
        print(
            f"\n  AVISO: el lote varía muy poco (desvío {zonificacion.desvio:.3f}). "
            f"Las zonas están separando ruido, no vigor."
        )

    if args.mapa:
        grados, bordes = reproyectar_a_grados(ndvi, info["crs"], info["transformacion"])
        imagen = colorear(grados, resumen.p2, resumen.p98)
        titulo = f"{mision.nombre} — {escena.datetime:%d/%m/%Y}"
        base = Path("mapas") / f"ndvi_{escena.datetime:%Y%m%d}"
        guardar_png(imagen, base.with_suffix(".png"))
        guardar_html(
            base.with_suffix(".png"),
            bordes,
            base.with_suffix(".html"),
            titulo,
            resumen.p2,
            resumen.p98,
        )
        print(f"\n  mapa  {base.with_suffix('.html')}")

    if resumen.cobertura_pct < COBERTURA_MINIMA_PCT:
        print(
            f"\n  AVISO: solo se vio el {resumen.cobertura_pct:.0f} % del lote. "
            f"Por debajo del {COBERTURA_MINIMA_PCT:.0f} % el promedio no lo representa."
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
