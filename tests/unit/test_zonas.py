"""Verifica que las zonas de vigor midan bien y que avisen cuando no significan nada.

Separar un lote en flojo, normal y vigoroso siempre devuelve tres zonas, aunque el campo
sea perfectamente parejo. Por eso lo que más importa probar acá no es el corte en sí, sino
que la zonificación se delate cuando está partiendo ruido.

- `TestCortes`: dónde caen los límites y qué pasa en los casos degenerados.
- `TestSuperficie`: la conversión de píxeles a hectáreas y los porcentajes.
- `TestDescartados`: los píxeles sin dato no entran en ninguna zona.
- `TestErrores`: los parámetros inválidos fallan con mensajes claros.

Técnico: la prueba del lote constante es la que pilló un error real. Un arreglo lleno del
mismo valor **no** da desvío cero en `float32` sino ~1e-7, y con esa comparación exacta
todos los píxeles caían en "vigoroso". De ahí sale `DESVIO_DESPRECIABLE`.
"""

import numpy as np
import pytest

from dronesw.vision.zonas import (
    AREA_PIXEL_HA,
    FUERA,
    UMBRAL_UNIFORME,
    clasificar,
)


def _con_gradiente(alto: int = 10, ancho: int = 10) -> np.ndarray:
    """Lote con vigor creciente de izquierda a derecha."""
    _, columnas = np.mgrid[0:alto, 0:ancho]
    return (0.3 + 0.04 * columnas).astype("float32")


class TestCortes:
    def test_los_cortes_son_la_media_mas_menos_medio_desvio(self):
        ndvi = _con_gradiente()
        zonificacion = clasificar(ndvi, k=0.5)
        medio = float(np.nanmean(ndvi))
        desvio = float(np.nanstd(ndvi))
        assert zonificacion.corte_bajo == pytest.approx(medio - 0.5 * desvio)
        assert zonificacion.corte_alto == pytest.approx(medio + 0.5 * desvio)

    def test_k_mas_grande_achica_las_zonas_de_punta(self):
        ndvi = _con_gradiente()
        angosta = clasificar(ndvi, k=1.5).zonas[0].pixeles
        ancha = clasificar(ndvi, k=0.5).zonas[0].pixeles
        assert angosta < ancha

    def test_un_lote_constante_queda_todo_normal(self):
        # En float32 el desvío da ~1e-7, no cero: sin tolerancia caía todo en "vigoroso".
        zonificacion = clasificar(np.full((8, 8), 0.60, dtype="float32"))
        flojo, normal, vigoroso = zonificacion.zonas
        assert (flojo.pixeles, normal.pixeles, vigoroso.pixeles) == (0, 64, 0)

    def test_un_lote_parejo_se_declara_uniforme(self):
        assert clasificar(np.full((8, 8), 0.60, dtype="float32")).uniforme

    def test_un_lote_con_variacion_real_no_se_declara_uniforme(self):
        zonificacion = clasificar(_con_gradiente())
        assert zonificacion.desvio > UMBRAL_UNIFORME
        assert not zonificacion.uniforme

    def test_con_dos_poblaciones_la_zona_del_medio_queda_vacia(self):
        # Es la ventaja de cortar por desvíos: los terciles la llenarían igual.
        ndvi = np.full((10, 10), 0.70, dtype="float32")
        ndvi[:5] = 0.25
        assert clasificar(ndvi).zonas[1].pixeles == 0


class TestSuperficie:
    def test_cada_pixel_son_cien_metros_cuadrados(self):
        assert AREA_PIXEL_HA == pytest.approx(0.01)

    def test_las_hectareas_salen_de_los_pixeles(self):
        zonificacion = clasificar(_con_gradiente())
        for zona in zonificacion.zonas:
            assert zona.hectareas == pytest.approx(zona.pixeles * AREA_PIXEL_HA)

    def test_las_zonas_suman_el_lote_entero(self):
        ndvi = _con_gradiente()
        zonificacion = clasificar(ndvi)
        assert zonificacion.pixeles_clasificados == ndvi.size
        assert sum(zonificacion.porcentaje(z) for z in zonificacion.zonas) == pytest.approx(100.0)

    def test_cada_zona_informa_el_rango_que_realmente_contiene(self):
        zonificacion = clasificar(_con_gradiente())
        flojo, _, vigoroso = zonificacion.zonas
        assert flojo.maximo < zonificacion.corte_bajo
        assert vigoroso.minimo > zonificacion.corte_alto


class TestDescartados:
    def test_los_pixeles_sin_dato_quedan_fuera_de_toda_zona(self):
        ndvi = _con_gradiente()
        ndvi[0, :] = np.nan
        zonificacion = clasificar(ndvi)
        assert int((zonificacion.etiquetas == FUERA).sum()) == 10
        assert zonificacion.pixeles_clasificados == ndvi.size - 10

    def test_las_hectareas_no_cuentan_lo_descartado(self):
        ndvi = _con_gradiente()
        ndvi[0, :] = np.nan
        assert clasificar(ndvi).hectareas == pytest.approx(90 * AREA_PIXEL_HA)


class TestErrores:
    def test_sin_ningun_pixel_util_falla(self):
        with pytest.raises(ValueError, match="ningún píxel"):
            clasificar(np.full((4, 4), np.nan, dtype="float32"))

    @pytest.mark.parametrize("k", [0, -1.0])
    def test_k_no_positivo_falla(self, k):
        with pytest.raises(ValueError, match="mayor que cero"):
            clasificar(_con_gradiente(), k=k)
