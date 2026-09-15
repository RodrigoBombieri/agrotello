"""Verifica que el planificador arme recorridos correctos sobre cualquier lote.

La geometría es la parte del proyecto que se puede probar sin dron ni simulador: se le da un
lote de forma conocida y se revisa que el recorrido lo cubra bien y no se salga del borde.

- `_cuadrado` y `_ele`: arman lotes de prueba con formas conocidas.
- `_mision`: arma una definición de misión con valores por defecto razonables.
- `_rumbo`: mide la orientación de una pasada, en grados.
- `TestProyeccion`: conversión entre grados y metros.
- `TestCarga`: lectura del YAML de misión.
- `TestCobertura`: los waypoints caen dentro del lote y lo cubren.
- `TestOrientacion`: el ángulo pedido se respeta.
- `TestMargen`: el retiro del borde se aplica.
- `TestErrores`: los parámetros inválidos fallan con mensajes claros.

Técnico: los lotes de prueba se definen en metros y se convierten a coordenadas geográficas
con la misma proyección que usa el planificador, para que las afirmaciones se puedan escribir
en metros y sean legibles. La prueba clave es la del punto medio de cada pasada: un lote
cóncavo puede hacer que una pasada atraviese un hueco, y eso solo se detecta mirando el
tramo entre waypoints, no los waypoints sueltos.
"""

import math
from itertools import pairwise

import pytest
from shapely.geometry import Point, Polygon

from dronesw.mission.planner import (
    DefinicionMision,
    ParametrosVuelo,
    _Proyeccion,
    cargar_mision,
    planificar,
)

LAT_REF = -32.6959
LON_REF = -58.8953


def _cuadrado(lado_m: float = 200.0) -> tuple[tuple[float, float], ...]:
    """Lote cuadrado centrado en el punto de referencia."""
    proy = _Proyeccion(LAT_REF, LON_REF)
    h = lado_m / 2
    esquinas = [(-h, -h), (h, -h), (h, h), (-h, h)]
    return tuple(proy.a_grados(x, y) for x, y in esquinas)


def _ele() -> tuple[tuple[float, float], ...]:
    """Lote en forma de L: obliga a que alguna pasada se parta en dos tramos."""
    proy = _Proyeccion(LAT_REF, LON_REF)
    vertices = [(0, 0), (200, 0), (200, 60), (60, 60), (60, 200), (0, 200)]
    return tuple(proy.a_grados(x, y) for x, y in vertices)


def _mision(poligono=None, **parametros) -> DefinicionMision:
    valores = {"altura_m": 50.0, "separacion_m": 40.0}
    valores.update(parametros)
    return DefinicionMision(
        nombre="lote de prueba",
        poligono=poligono or _cuadrado(),
        vuelo=ParametrosVuelo(**valores),
    )


def _poligono_en_metros(mision: DefinicionMision) -> tuple[Polygon, _Proyeccion]:
    """Reconstruye el lote en metros, como lo ve el planificador."""
    lat0 = sum(v[0] for v in mision.poligono) / len(mision.poligono)
    lon0 = sum(v[1] for v in mision.poligono) / len(mision.poligono)
    proy = _Proyeccion(lat0, lon0)
    return Polygon([proy.a_metros(lat, lon) for lat, lon in mision.poligono]), proy


def _rumbo(proy: _Proyeccion, a, b) -> float:
    """Orientación del tramo a->b en grados, medida como rumbo desde el norte."""
    x1, y1 = proy.a_metros(a.lat, a.lon)
    x2, y2 = proy.a_metros(b.lat, b.lon)
    return math.degrees(math.atan2(x2 - x1, y2 - y1)) % 180


class TestProyeccion:
    def test_ida_y_vuelta_conserva_el_punto(self):
        proy = _Proyeccion(LAT_REF, LON_REF)
        lat, lon = proy.a_grados(*proy.a_metros(LAT_REF + 0.001, LON_REF - 0.002))
        assert lat == pytest.approx(LAT_REF + 0.001, abs=1e-9)
        assert lon == pytest.approx(LON_REF - 0.002, abs=1e-9)

    def test_cien_metros_al_este_dan_cien_metros(self):
        proy = _Proyeccion(LAT_REF, LON_REF)
        lat, lon = proy.a_grados(100.0, 0.0)
        x, y = proy.a_metros(lat, lon)
        assert x == pytest.approx(100.0, abs=0.01)
        assert y == pytest.approx(0.0, abs=0.01)

    def test_un_grado_de_longitud_se_acorta_lejos_del_ecuador(self):
        # Es la razón por la que el planificador trabaja en metros y no en grados.
        assert _Proyeccion(-32.7, 0).m_por_grado_lon < _Proyeccion(0.0, 0).m_por_grado_lon


class TestCarga:
    def test_lee_un_yaml_completo(self, tmp_path):
        archivo = tmp_path / "lote.yaml"
        archivo.write_text(
            "nombre: La Florida\n"
            "poligono:\n"
            "  - {lat: -32.1, lon: -58.1}\n"
            "  - {lat: -32.2, lon: -58.1}\n"
            "  - {lat: -32.2, lon: -58.2}\n"
            "vuelo:\n"
            "  altura_m: 80\n"
            "  separacion_m: 30\n"
            "  velocidad_ms: 8\n",
            encoding="utf-8",
        )
        mision = cargar_mision(archivo)

        assert mision.nombre == "La Florida"
        assert len(mision.poligono) == 3
        assert mision.vuelo.altura_m == 80
        assert mision.vuelo.velocidad_ms == 8

    def test_rechaza_poligono_de_menos_de_tres_vertices(self, tmp_path):
        archivo = tmp_path / "lote.yaml"
        archivo.write_text(
            "poligono:\n"
            "  - {lat: -32.1, lon: -58.1}\n"
            "  - {lat: -32.2, lon: -58.1}\n"
            "vuelo: {altura_m: 50, separacion_m: 30}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="al menos 3"):
            cargar_mision(archivo)


class TestCobertura:
    def test_todos_los_waypoints_caen_dentro_del_lote(self):
        mision = _mision()
        lote, proy = _poligono_en_metros(mision)

        for wp in planificar(mision):
            punto = Point(*proy.a_metros(wp.lat, wp.lon))
            assert lote.buffer(0.5).contains(punto)

    def test_ninguna_pasada_se_sale_del_lote(self):
        # Con un lote cóncavo, una pasada mal recortada cruzaría el hueco de la L.
        mision = _mision(poligono=_ele(), separacion_m=25.0)
        lote, proy = _poligono_en_metros(mision)
        waypoints = planificar(mision)

        for i in range(0, len(waypoints) - 1, 2):
            x1, y1 = proy.a_metros(waypoints[i].lat, waypoints[i].lon)
            x2, y2 = proy.a_metros(waypoints[i + 1].lat, waypoints[i + 1].lon)
            medio = Point((x1 + x2) / 2, (y1 + y2) / 2)
            assert lote.buffer(0.5).contains(medio)

    def test_los_waypoints_vienen_de_a_pares(self):
        # Cada pasada aporta su punto de entrada y el de salida.
        assert len(planificar(_mision())) % 2 == 0

    def test_todos_a_la_altura_pedida(self):
        assert {wp.altura_m for wp in planificar(_mision(altura_m=73.0))} == {73.0}

    def test_mas_separacion_implica_menos_pasadas(self):
        juntas = planificar(_mision(separacion_m=20.0))
        separadas = planificar(_mision(separacion_m=60.0))
        assert len(juntas) > len(separadas)

    def test_zigzag_alterna_el_sentido(self):
        waypoints = planificar(_mision())
        sentidos = [
            waypoints[i + 1].lat > waypoints[i].lat for i in range(0, len(waypoints) - 1, 2)
        ]
        assert all(a != b for a, b in pairwise(sentidos))

    def test_una_separacion_enorme_deja_al_menos_una_pasada(self):
        assert len(planificar(_mision(separacion_m=5_000.0))) >= 2


class TestOrientacion:
    @pytest.mark.parametrize("angulo", [0.0, 30.0, 45.0, 90.0, 135.0])
    def test_las_pasadas_siguen_el_rumbo_pedido(self, angulo):
        mision = _mision(angulo_grados=angulo)
        _, proy = _poligono_en_metros(mision)
        waypoints = planificar(mision)

        assert _rumbo(proy, waypoints[0], waypoints[1]) == pytest.approx(angulo % 180, abs=0.5)


class TestMargen:
    def test_los_waypoints_respetan_el_retiro_del_borde(self):
        margen = 15.0
        mision = _mision(margen_m=margen)
        lote, proy = _poligono_en_metros(mision)

        for wp in planificar(mision):
            punto = Point(*proy.a_metros(wp.lat, wp.lon))
            assert lote.exterior.distance(punto) >= margen - 0.5

    def test_sin_margen_las_pasadas_llegan_al_borde(self):
        mision = _mision(margen_m=0.0)
        lote, proy = _poligono_en_metros(mision)
        waypoints = planificar(mision)

        distancias = [
            lote.exterior.distance(Point(*proy.a_metros(wp.lat, wp.lon))) for wp in waypoints
        ]
        assert min(distancias) < 0.5


class TestErrores:
    @pytest.mark.parametrize("separacion", [0.0, -10.0])
    def test_separacion_no_positiva(self, separacion):
        with pytest.raises(ValueError, match="positiva"):
            planificar(_mision(separacion_m=separacion))

    def test_margen_que_consume_el_lote(self):
        with pytest.raises(ValueError, match="consume el lote"):
            planificar(_mision(margen_m=500.0))

    def test_poligono_con_lados_cruzados(self):
        proy = _Proyeccion(LAT_REF, LON_REF)
        mono = tuple(proy.a_grados(x, y) for x, y in [(0, 0), (100, 100), (100, 0), (0, 100)])
        with pytest.raises(ValueError, match="no es válido"):
            planificar(_mision(poligono=mono))
