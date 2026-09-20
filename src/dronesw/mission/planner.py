"""Convierte el contorno de un lote en la ruta que el dron tiene que volar para relevarlo.

Recibe el lote dibujado con coordenadas de GPS y devuelve los puntos que lo cubren con
pasadas paralelas, yendo y viniendo como cuando se corta el pasto.

- `ParametrosVuelo`: altura, separación entre pasadas, velocidad, orientación y margen.
- `DefinicionMision`: el lote más sus parámetros de vuelo.
- `cargar_mision`: lee esa definición desde un archivo YAML.
- `_Proyeccion`: convierte entre coordenadas geográficas y metros.
- `planificar`: genera los waypoints que cubren el lote.
- `distancia_recorrido`: mide la longitud del trazado.
- `_aplicar_margen`: retrae el borde para no volar pegado al alambrado.
- `_barrido_zigzag`: arma las pasadas alternando el sentido.
- `_cortar_pasada`: recorta una pasada contra el contorno del lote.
- `_lineas`: normaliza los distintos tipos que devuelve una intersección de Shapely.
- `_longitud`: mide el recorrido total.

Técnico: la geometría se resuelve en un plano local en metros (aproximación de plano
tangente, válida a escala de lote) porque un grado de longitud mide distinto según la
latitud, y razonar en grados lleva a errores silenciosos. Las pasadas inclinadas se
obtienen rotando el lote, resolviendo el caso vertical y rotando el trazado de vuelta; el
ángulo se interpreta como rumbo horario desde el norte.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from shapely.affinity import rotate
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from dronesw.flight.base import Waypoint

log = logging.getLogger(__name__)


# --- Definición de la misión ----------------------------------------------


@dataclass(frozen=True)
class ParametrosVuelo:
    """Cómo se vuela el lote."""

    altura_m: float
    separacion_m: float
    velocidad_ms: float = 5.0
    angulo_grados: float = 0.0
    margen_m: float = 0.0


@dataclass(frozen=True)
class DefinicionMision:
    """Un lote y los parámetros con que se lo va a relevar."""

    nombre: str
    poligono: tuple[tuple[float, float], ...]  # vértices (lat, lon) en orden
    vuelo: ParametrosVuelo
    descripcion: str = ""


def cargar_mision(ruta: str | Path) -> DefinicionMision:
    """Lee una definición de misión desde un archivo YAML."""
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))

    vertices = tuple((float(v["lat"]), float(v["lon"])) for v in datos["poligono"])
    if len(vertices) < 3:
        raise ValueError(f"El polígono necesita al menos 3 vértices, tiene {len(vertices)}")

    return DefinicionMision(
        nombre=datos.get("nombre", Path(ruta).stem),
        descripcion=datos.get("descripcion", ""),
        poligono=vertices,
        vuelo=ParametrosVuelo(**datos["vuelo"]),
    )


# --- Proyección geográfica -------------------------------------------------


class _Proyeccion:
    """Convierte entre grados y un plano local en metros, centrado en el lote.

    Usa una aproximación de plano tangente: válida para áreas de pocos kilómetros, que es
    exactamente la escala de un lote agrícola. Para superficies mayores haría falta una
    proyección real (UTM), pero eso agregaría dependencias sin beneficio acá.
    """

    def __init__(self, lat0: float, lon0: float) -> None:
        self.lat0 = lat0
        self.lon0 = lon0

        # Series estándar para metros por grado en WGS84. La longitud se acorta con el
        # coseno de la latitud: en Gualeguaychú un grado de longitud mide ~15 km menos
        # que en el ecuador.
        phi = math.radians(lat0)
        self.m_por_grado_lat = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
        self.m_por_grado_lon = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)

    def a_metros(self, lat: float, lon: float) -> tuple[float, float]:
        """(lat, lon) -> (x este, y norte) en metros."""
        return (
            (lon - self.lon0) * self.m_por_grado_lon,
            (lat - self.lat0) * self.m_por_grado_lat,
        )

    def a_grados(self, x: float, y: float) -> tuple[float, float]:
        """(x este, y norte) en metros -> (lat, lon)."""
        return (
            self.lat0 + y / self.m_por_grado_lat,
            self.lon0 + x / self.m_por_grado_lon,
        )


# --- Planificación ---------------------------------------------------------


def planificar(mision: DefinicionMision) -> list[Waypoint]:
    """Devuelve los waypoints que cubren el lote, en orden de vuelo.

    No incluye despegue ni aterrizaje: de eso se encarga el ejecutor.
    """
    p = mision.vuelo

    if p.separacion_m <= 0:
        raise ValueError(f"La separación entre pasadas debe ser positiva, es {p.separacion_m}")

    lat0 = sum(v[0] for v in mision.poligono) / len(mision.poligono)
    lon0 = sum(v[1] for v in mision.poligono) / len(mision.poligono)
    proy = _Proyeccion(lat0, lon0)

    lote = Polygon([proy.a_metros(lat, lon) for lat, lon in mision.poligono])
    if not lote.is_valid:
        raise ValueError(
            "El polígono no es válido (probablemente los vértices se cruzan). "
            "Revisá que estén en orden, recorriendo el borde."
        )

    area_util = _aplicar_margen(lote, p.margen_m)

    puntos = _barrido_zigzag(area_util, p.separacion_m, p.angulo_grados)
    if not puntos:
        raise ValueError(
            f"No se generó ninguna pasada. La separación ({p.separacion_m} m) puede ser "
            f"mayor que el lote, o el margen ({p.margen_m} m) puede haberlo consumido entero."
        )

    waypoints = [
        Waypoint(lat=lat, lon=lon, altura_m=p.altura_m)
        for lat, lon in (proy.a_grados(x, y) for x, y in puntos)
    ]

    log.info(
        "Misión '%s': %d waypoints, %.0f m de recorrido, %.2f ha cubiertas",
        mision.nombre,
        len(waypoints),
        _longitud(puntos),
        area_util.area / 10_000,
    )
    return waypoints


def distancia_recorrido(waypoints: Sequence[Waypoint]) -> float:
    """Largo total del recorrido en metros, sumando tramo a tramo.

    Proyecta los waypoints al mismo plano local que usó el planificador, así la cuenta es
    en metros y no en grados, que no se pueden sumar entre sí.
    """
    if len(waypoints) < 2:
        return 0.0

    lat0 = sum(w.lat for w in waypoints) / len(waypoints)
    lon0 = sum(w.lon for w in waypoints) / len(waypoints)
    proy = _Proyeccion(lat0, lon0)
    return _longitud([proy.a_metros(w.lat, w.lon) for w in waypoints])


def _aplicar_margen(lote: Polygon, margen_m: float) -> Polygon:
    """Retrae el borde del lote hacia adentro."""
    if margen_m <= 0:
        return lote

    reducido = lote.buffer(-margen_m)
    if reducido.is_empty:
        raise ValueError(f"El margen de {margen_m} m consume el lote entero. Usá un margen menor.")

    # Un lote con forma de reloj de arena puede partirse en dos al retraerlo. Cubrir varias
    # piezas requiere decidir en qué orden volarlas, y eso todavía no lo resolvemos.
    if isinstance(reducido, MultiPolygon):
        piezas = sorted(reducido.geoms, key=lambda g: g.area, reverse=True)
        log.warning(
            "El margen partió el lote en %d piezas. Se releva solo la mayor (%.2f ha).",
            len(piezas),
            piezas[0].area / 10_000,
        )
        return piezas[0]

    return reducido


def _barrido_zigzag(
    area: Polygon, separacion_m: float, angulo_grados: float
) -> list[tuple[float, float]]:
    """Genera los puntos del barrido, alternando el sentido en cada pasada.

    El ángulo se mide como un rumbo: en sentido horario desde el norte. 0 deja las pasadas
    norte-sur, 90 las deja este-oeste, 45 noreste-suroeste.

    Truco: en vez de generar líneas inclinadas, se rota el lote para que las pasadas queden
    verticales, se resuelve el caso fácil, y se rota el resultado de vuelta.
    """
    centro = area.centroid
    # Se rota el lote en sentido contrario al rumbo pedido para que las pasadas queden
    # verticales; al final se deshace el giro sobre el trazado.
    girado = rotate(area, angulo_grados, origin=centro)

    minx, miny, maxx, maxy = girado.bounds
    ancho = maxx - minx

    # Las pasadas se centran sobre el lote en lugar de arrancar pegadas al borde: así el
    # sobrante se reparte en partes iguales a ambos lados.
    cantidad = max(1, math.ceil(ancho / separacion_m))
    sobrante = cantidad * separacion_m - ancho
    x = minx - sobrante / 2 + separacion_m / 2

    puntos: list[tuple[float, float]] = []
    invertir = False

    for _ in range(cantidad):
        segmentos = _cortar_pasada(girado, x, miny, maxy)
        if segmentos:
            if invertir:
                segmentos = [(fin, ini) for ini, fin in reversed(segmentos)]
            for y_ini, y_fin in segmentos:
                puntos.append((x, y_ini))
                puntos.append((x, y_fin))
            invertir = not invertir
        x += separacion_m

    if not puntos:
        return []

    # Se rota el trazado completo de vuelta a la orientación original.
    trazado = rotate(LineString(puntos), -angulo_grados, origin=centro)
    return [(x, y) for x, y in trazado.coords]


def _cortar_pasada(
    area: Polygon, x: float, y_min: float, y_max: float
) -> list[tuple[float, float]]:
    """Intersecta una pasada vertical con el lote.

    Devuelve los tramos como `(y_inicio, y_fin)` ordenados de sur a norte. Un lote cóncavo
    puede partir una misma pasada en varios tramos: la pasada entra, sale y vuelve a entrar.
    """
    linea = LineString([(x, y_min - 1), (x, y_max + 1)])
    corte = area.intersection(linea)

    tramos = []
    for tramo in _lineas(corte):
        ys = [c[1] for c in tramo.coords]
        tramos.append((min(ys), max(ys)))

    tramos.sort()
    return tramos


def _lineas(geom: BaseGeometry) -> Iterable[LineString]:
    """Extrae las líneas de una intersección, que puede venir en varias formas.

    Shapely devuelve un tipo distinto según el caso: `LineString` si la pasada cruza limpio,
    `MultiLineString` si el lote es cóncavo, `Point` si apenas roza un vértice, o vacío.
    """
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    if isinstance(geom, GeometryCollection):
        return [g for g in geom.geoms if isinstance(g, LineString)]
    return []


def _longitud(puntos: Sequence[tuple[float, float]]) -> float:
    """Distancia total del trazado, en metros."""
    return sum(math.dist(puntos[i], puntos[i + 1]) for i in range(len(puntos) - 1))
