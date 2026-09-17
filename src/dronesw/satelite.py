"""Le pide imágenes al satélite: qué hay disponible de tu lote y cómo traer solo ese pedazo.

Sentinel-2 fotografía la Tierra entera cada cinco días. Este módulo se ocupa de dos cosas:
averiguar qué pasadas cubrieron un lote en un rango de fechas, y traer de una de esas
imágenes únicamente los píxeles del campo, sin descargar el resto.

- `poligono_geojson`: traduce el lote al formato que espera el catálogo.
- `buscar_escenas`: lista las pasadas disponibles, ordenadas por fecha.
- `bordes_del_lote`: calcula el rectángulo que encierra el lote, en grados.
- `leer_banda`: abre una imagen remota y devuelve solo el recorte del lote.

Técnico: el catálogo es la API STAC de Earth Search (Element 84), que indexa las copias en
formato COG del archivo de Sentinel-2 en AWS; el acceso es anónimo. Las imágenes están en
coordenadas UTM y el lote en grados, así que hay que reproyectar los bordes antes de pedir la
ventana — `transform_bounds` lo hace leyendo el CRS del propio archivo, sin hardcodear la
zona. Los valores son enteros escalados (reflectancia x 10000); desde 2022 traen además un
desplazamiento de -1000 que **no se cancela** en el NDVI, y por eso `leer_banda` devuelve la
escala y el desplazamiento declarados junto con los datos.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

import numpy as np
import rasterio
from pystac.item import Item
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds as ventana_desde_bordes

from dronesw.mission.planner import DefinicionMision

CATALOGO = "https://earth-search.aws.element84.com/v1"
COLECCION = "sentinel-2-l2a"

BANDA_ROJO = "red"
BANDA_INFRARROJO = "nir"
BANDA_CLASIFICACION = "scl"


def poligono_geojson(mision: DefinicionMision) -> dict:
    """Arma el polígono del lote en el formato GeoJSON que espera el catálogo.

    GeoJSON usa (lon, lat) y exige que el anillo cierre repitiendo el primer vértice.
    """
    anillo = [[lon, lat] for lat, lon in mision.poligono]
    anillo.append(anillo[0])
    return {"type": "Polygon", "coordinates": [anillo]}


def buscar_escenas(mision: DefinicionMision, desde: str, hasta: str) -> list[Item]:
    """Devuelve las pasadas del satélite sobre el lote, de la más vieja a la más nueva."""
    catalogo = Client.open(CATALOGO)
    resultado = catalogo.search(
        collections=[COLECCION],
        intersects=poligono_geojson(mision),
        datetime=f"{desde}/{hasta}",
    )
    escenas = [escena for escena in resultado.items() if escena.datetime is not None]
    return sorted(escenas, key=lambda escena: cast("datetime", escena.datetime))


def bordes_del_lote(mision: DefinicionMision) -> tuple[float, float, float, float]:
    """Rectángulo que encierra el lote, como (oeste, sur, este, norte) en grados."""
    lats = [lat for lat, _ in mision.poligono]
    lons = [lon for _, lon in mision.poligono]
    return min(lons), min(lats), max(lons), max(lats)


def leer_banda(
    url: str, mision: DefinicionMision, forma: tuple[int, int] | None = None
) -> tuple[np.ndarray, dict]:
    """Abre la imagen remota y devuelve solo los píxeles del lote, más datos de la escena.

    La imagen nunca viaja entera: al pedir una ventana, rasterio traduce el pedido en
    pedidos de rangos de bytes sobre HTTP y trae únicamente los mosaicos que hacen falta.

    `forma` fuerza el tamaño del recorte, para poder alinear bandas de distinta resolución:
    la clasificación viene a 20 m y las bandas de color a 10, así que sin esto las matrices
    no coinciden. Se remuestrea con vecino más cercano porque son códigos de categoría —
    promediar nube (9) con vegetación (4) daría 6, que significa agua.
    """
    with rasterio.open(url) as imagen:
        bordes = transform_bounds("EPSG:4326", imagen.crs, *bordes_del_lote(mision))
        ventana = ventana_desde_bordes(*bordes, transform=imagen.transform)
        ventana = ventana.round_offsets().round_lengths()
        recorte = imagen.read(1, window=ventana, out_shape=forma, resampling=Resampling.nearest)

        info = {
            "crs": str(imagen.crs),
            "escena_px": imagen.width * imagen.height,
            "escala": imagen.scales[0],
            "desplazamiento": imagen.offsets[0],
        }
    return recorte, info
