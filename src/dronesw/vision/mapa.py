"""Convierte el NDVI en una imagen de colores que se puede mirar sobre el campo.

Hasta acá el resultado eran números. Este archivo los pinta: verde donde la vegetación está
vigorosa, amarillo en el medio, rojo donde anda flojo, y transparente fuera del lote. La
imagen queda guardada como PNG y también dentro de una página web que la muestra encima de
la foto satelital, para ver de una qué sector del campo es cuál.

- `colorear`: convierte la matriz de NDVI en una imagen con transparencia.
- `guardar_png`: escribe esa imagen en disco.
- `guardar_html`: arma la página que la muestra sobre el mapa.

Técnico: la escala se estira entre dos percentiles del propio lote en vez de usar el rango
-1 a 1, porque un cultivo implantado ocupa una franja angosta y con escala fija sale todo
del mismo color. Eso implica que dos mapas de fechas distintas NO son comparables entre sí:
cada uno usa su propia escala, y el panel de la página la muestra para que se note. Los
píxeles NaN quedan con alfa 0. La página apila la imagen sobre una capa satelital con
`imageOverlay`, que ubica el PNG por sus esquinas en grados, así que la imagen tiene que
venir ya reproyectada a EPSG:4326 — un arreglo en UTM saldría girado un grado.
"""

from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from PIL import Image

PALETA = "RdYlGn"


def colorear(ndvi: np.ndarray, desde: float, hasta: float) -> np.ndarray:
    """Pinta el NDVI entre `desde` y `hasta`, dejando transparente lo que no es lote.

    Los valores fuera del rango no se descartan: se pegan al extremo de la escala, así un
    par de píxeles raros no se llevan puesta toda la gama de colores.
    """
    if not hasta > desde:
        raise ValueError(f"El rango de color está al revés o vacío: {desde} a {hasta}")

    normalizado = np.clip((ndvi - desde) / (hasta - desde), 0.0, 1.0)
    imagen = colormaps.get_cmap(PALETA)(np.nan_to_num(normalizado, nan=0.0), bytes=True)
    imagen[np.isnan(ndvi), 3] = 0
    return imagen


def guardar_png(imagen: np.ndarray, destino: Path) -> None:
    """Escribe la imagen coloreada como PNG con transparencia."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(imagen, mode="RGBA").save(destino)


def guardar_html(
    png: Path,
    bordes: tuple[float, float, float, float],
    destino: Path,
    titulo: str,
    desde: float,
    hasta: float,
) -> None:
    """Arma una página autocontenida que muestra el PNG sobre la imagen satelital.

    El PNG viaja incrustado en base64 y Leaflet se trae de un CDN: el archivo se abre con
    doble clic, sin levantar ningún servidor.
    """
    oeste, sur, este, norte = bordes
    incrustado = base64.b64encode(png.read_bytes()).decode("ascii")
    escala = ", ".join(f"{desde + (hasta - desde) * i / 4:.2f}" for i in range(5))

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        _PLANTILLA.format(
            titulo=titulo,
            imagen=incrustado,
            sur=sur,
            oeste=oeste,
            norte=norte,
            este=este,
            desde=f"{desde:.3f}",
            hasta=f"{hasta:.3f}",
            escala=escala,
        ),
        encoding="utf-8",
    )


_PLANTILLA = """<!doctype html>
<html lang="es">
<meta charset="utf-8">
<title>{titulo}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body {{ margin: 0; font: 14px system-ui, sans-serif; }}
  #mapa {{ height: 100vh; }}
  .panel {{
    position: absolute; z-index: 1000; right: 12px; top: 12px; width: 220px;
    background: #fff; padding: 12px 14px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,.3);
  }}
  .barra {{
    height: 14px; border-radius: 3px; margin: 8px 0 4px;
    background: linear-gradient(to right,
      #a50026, #f46d43, #fee08b, #a6d96a, #1a9850);
  }}
  .extremos {{ display: flex; justify-content: space-between; color: #555; }}
  .aviso {{ margin-top: 10px; color: #777; font-size: 12px; line-height: 1.35; }}
</style>
<div class="panel">
  <strong>{titulo}</strong>
  <div class="barra"></div>
  <div class="extremos"><span>{desde}</span><span>{hasta}</span></div>
  <div class="aviso">
    Escala estirada a este lote y esta fecha ({escala}).
    No comparar con el mapa de otra fecha.
  </div>
</div>
<div id="mapa"></div>
<script>
  const bordes = [[{sur}, {oeste}], [{norte}, {este}]];
  const mapa = L.map('mapa');
  L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
    {{ maxZoom: 19, attribution: 'Esri' }}
  ).addTo(mapa);
  L.imageOverlay('data:image/png;base64,{imagen}', bordes, {{ opacity: 0.85 }}).addTo(mapa);
  L.rectangle(bordes, {{ color: '#fff', weight: 1, fill: false, dashArray: '4 4' }}).addTo(mapa);
  mapa.fitBounds(bordes, {{ padding: [40, 40] }});
</script>
</html>
"""
