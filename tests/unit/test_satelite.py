"""Verifica el acceso a las imágenes: qué pedazo se lee y dónde cae exactamente.

Todo lo que hace este módulo termina en una matriz de píxeles que después se promedia y se
dibuja. Si el recorte cae corrido, o si la máscara del lote se apoya en una grilla que no
es la de los datos, nada falla: los números salen mal y parecen bien. Estas pruebas usan
imágenes chiquitas creadas en el momento, así no hace falta internet.

- `_mision`: el lote real de La Florida, para que las superficies sean comprobables.
- `geotiff`: fabrica una imagen local en UTM con la resolución que se le pida.
- `TestPoligono`: la traducción del lote al formato del catálogo.
- `TestLeerBanda`: el recorte, y la corrección de la transformación al forzar la forma.
- `TestMascaraDelLote`: el recorte contra el contorno real y su superficie.
- `TestReproyectar`: el pase de UTM a grados.
- `TestAlineacionDeBandas`: fija cuánto se desalinea la clasificación, que es un error
  conocido y acotado.

Técnico: La Florida entra en un rectángulo del doble de su superficie, así que sirve para
probar que la máscara descarta la mitad. Las imágenes se fabrican en EPSG:32721 (UTM 21S),
la zona real del lote, porque el código lee el CRS del archivo en vez de asumirlo.
"""

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.warp import transform_bounds

from dronesw.mission.planner import DefinicionMision, ParametrosVuelo
from dronesw.satelite import (
    bordes_del_lote,
    leer_banda,
    mascara_del_lote,
    poligono_geojson,
    reproyectar_a_grados,
)

CRS_LOTE = "EPSG:32721"
HECTAREAS_REALES = 5.23
VERTICES = (
    (-32.69586457654833, -58.893566719996926),
    (-32.69448276232639, -58.89525380397006),
    (-32.69602401527439, -58.897067193695214),
    (-32.6973678446678, -58.895479349956126),
)


def _mision() -> DefinicionMision:
    """El lote real del proyecto: un rombo de 5,23 ha en Gualeguaychú."""
    return DefinicionMision(
        nombre="La Florida",
        poligono=VERTICES,
        vuelo=ParametrosVuelo(80.0, 30.0, 8.0, 0.0, 2.0),
    )


@pytest.fixture
def geotiff(tmp_path):
    """Fabrica una imagen local en UTM que cubre el lote, con la resolución pedida."""

    def crear(nombre: str, metros_por_pixel: float, valor: int = 1000) -> str:
        en_utm = transform_bounds("EPSG:4326", CRS_LOTE, *bordes_del_lote(_mision()))
        oeste, norte = en_utm[0], en_utm[3]
        lado = 200
        transformacion = Affine.translation(
            oeste - 50 * metros_por_pixel, norte + 50 * metros_por_pixel
        ) @ Affine.scale(metros_por_pixel, -metros_por_pixel)
        datos = np.full((lado, lado), valor, dtype="uint16")
        ruta = tmp_path / nombre
        with rasterio.open(
            ruta,
            "w",
            driver="GTiff",
            height=lado,
            width=lado,
            count=1,
            dtype="uint16",
            crs=CRS_LOTE,
            transform=transformacion,
        ) as destino:
            destino.write(datos, 1)
        return str(ruta)

    return crear


class TestPoligono:
    def test_el_anillo_cierra_repitiendo_el_primer_vertice(self):
        anillo = poligono_geojson(_mision())["coordinates"][0]
        assert anillo[0] == anillo[-1]
        assert len(anillo) == len(VERTICES) + 1

    def test_usa_el_orden_longitud_latitud(self):
        # GeoJSON invierte el orden respecto del YAML de misión, y confundirlos manda el
        # pedido del otro lado del planeta.
        primero = poligono_geojson(_mision())["coordinates"][0][0]
        assert primero == [VERTICES[0][1], VERTICES[0][0]]

    def test_los_bordes_encierran_todos_los_vertices(self):
        oeste, sur, este, norte = bordes_del_lote(_mision())
        for lat, lon in VERTICES:
            assert oeste <= lon <= este
            assert sur <= lat <= norte


class TestLeerBanda:
    def test_lee_solo_la_ventana_del_lote(self, geotiff):
        recorte, info = leer_banda(geotiff("rojo.tif", 10.0), _mision())
        assert recorte.shape == (33, 33)
        assert info["crs"] == CRS_LOTE

    def test_forzar_la_forma_alinea_bandas_de_distinta_resolucion(self, geotiff):
        rojo, _ = leer_banda(geotiff("rojo.tif", 10.0), _mision())
        clasificacion, _ = leer_banda(geotiff("scl.tif", 20.0), _mision(), forma=rojo.shape)
        assert clasificacion.shape == rojo.shape

    def test_al_forzar_la_forma_la_transformacion_la_acompana(self, geotiff):
        # Sin esto la transformación seguiría diciendo 20 m por píxel, y la máscara del
        # lote se dibujaría sobre una grilla del doble de tamaño que la real.
        sin_forzar, info_20 = leer_banda(geotiff("scl.tif", 20.0), _mision())
        _, info_10 = leer_banda(geotiff("scl.tif", 20.0), _mision(), forma=(33, 33))

        ancho_original = info_20["transformacion"].a * sin_forzar.shape[1]
        ancho_forzado = info_10["transformacion"].a * 33
        assert ancho_forzado == pytest.approx(ancho_original)
        assert info_10["transformacion"].a == pytest.approx(10.3, abs=0.5)


class TestMascaraDelLote:
    def _mascara(self, geotiff):
        recorte, info = leer_banda(geotiff("rojo.tif", 10.0), _mision())
        return mascara_del_lote(_mision(), info["crs"], info["transformacion"], recorte.shape)

    def test_la_superficie_coincide_con_la_del_lote(self, geotiff):
        hectareas = int(self._mascara(geotiff).sum()) * 0.01
        assert hectareas == pytest.approx(HECTAREAS_REALES, abs=0.1)

    def test_descarta_alrededor_de_la_mitad_del_recorte(self, geotiff):
        # El rombo entra en un rectángulo del doble de superficie: sin recortar, la mitad
        # de lo que se promedia es el campo del vecino.
        mascara = self._mascara(geotiff)
        assert 0.45 < mascara.sum() / mascara.size < 0.55

    def test_las_esquinas_del_recorte_quedan_afuera(self, geotiff):
        mascara = self._mascara(geotiff)
        assert not mascara[0, 0]
        assert not mascara[-1, -1]


class TestReproyectar:
    def test_devuelve_bordes_en_grados(self, geotiff):
        recorte, info = leer_banda(geotiff("rojo.tif", 10.0), _mision())
        datos = recorte.astype("float32")
        _, bordes = reproyectar_a_grados(datos, info["crs"], info["transformacion"])

        oeste, sur, este, norte = bordes
        assert -59 < oeste < este < -58
        assert -33 < sur < norte < -32

    def test_los_bordes_caen_sobre_el_lote_con_menos_de_un_pixel_de_error(self, geotiff):
        # No se puede exigir que contengan todos los vértices: la ventana se redondea a
        # píxeles enteros, así que el borde del mapa puede quedar hasta un píxel adentro
        # del lote. Con 10 m por píxel eso es lo que se admite.
        recorte, info = leer_banda(geotiff("rojo.tif", 10.0), _mision())
        mapa = reproyectar_a_grados(recorte.astype("float32"), info["crs"], info["transformacion"])[
            1
        ]
        for del_lote, del_mapa in zip(bordes_del_lote(_mision()), mapa, strict=True):
            assert abs(del_lote - del_mapa) * 111_000 < 15.0

    def test_conserva_los_pixeles_sin_dato(self, geotiff):
        recorte, info = leer_banda(geotiff("rojo.tif", 10.0), _mision())
        datos = recorte.astype("float32")
        datos[:5] = np.nan
        salida, _ = reproyectar_a_grados(datos, info["crs"], info["transformacion"])
        assert np.isnan(salida).any()
        assert not np.isnan(salida).all()


class TestAlineacionDeBandas:
    def test_la_clasificacion_se_desalinea_menos_de_un_pixel(self, geotiff):
        # Limitación conocida: las ventanas de 10 m y de 20 m se redondean sobre el mismo
        # rectángulo en grados, así que no cubren exactamente lo mismo. Esta prueba fija
        # cuánto, para que no crezca sin que nos enteremos.
        _, info_rojo = leer_banda(geotiff("rojo.tif", 10.0), _mision())
        _, info_scl = leer_banda(geotiff("scl.tif", 20.0), _mision(), forma=(33, 33))

        corrimiento = abs(info_scl["transformacion"].c - info_rojo["transformacion"].c)
        estiramiento = abs(info_scl["transformacion"].a - info_rojo["transformacion"].a) * 33
        assert corrimiento <= 10.0
        assert estiramiento <= 10.0
