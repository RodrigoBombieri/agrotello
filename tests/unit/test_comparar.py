"""Verifica que cruzar dos fechas encuentre lo que se repite y no invente coincidencias.

Cruzar dos mediciones es fácil de hacer mal de una forma que no se nota: si el método
encuentra patrones donde no los hay, el mapa igual sale lindo y con hectáreas. Estas
pruebas fijan las dos propiedades que lo hacen confiable — que el nivel general de cada
fecha no influya, y que dos fechas sin relación den cerca de lo que daría el azar.

- `_con_patron`: fabrica dos fechas que comparten el mismo mapa de vigor.
- `TestLoQueSeRepite`: detecta el patrón cuando existe.
- `TestSinPatron`: no lo inventa cuando no existe.
- `TestNivelGeneral`: la subida estacional no altera el resultado.
- `TestPixelesSinDato`: un píxel tapado en una fecha sale de la comparación.
- `TestErrores`: las entradas imposibles fallan con un mensaje claro.

Técnico: `ESPERADO_POR_AZAR` es un tercio de un tercio, o sea el 11%: esa es la vara contra
la que hay que leer cualquier resultado. Una coincidencia del 11% no significa nada.
"""

import numpy as np
import pytest

from dronesw.vision.comparar import (
    ESPERADO_POR_AZAR,
    FLOJA,
    FUERA,
    NINGUNA,
    VIGOROSA,
    persistencia,
)

LADO = 30


def _con_patron(ruido: float = 0.02, desplazamiento: float = 0.0):
    """Dos fechas con el mismo mapa de vigor, más ruido, y una corrida de nivel."""
    generador = np.random.default_rng(0)
    fondo = generador.normal(0.6, 0.12, (LADO, LADO))
    primera = (fondo + generador.normal(0, ruido, (LADO, LADO))).astype("float32")
    segunda = (fondo + desplazamiento + generador.normal(0, ruido, (LADO, LADO))).astype("float32")
    return primera, segunda


class TestLoQueSeRepite:
    def test_encuentra_bastante_mas_que_el_azar(self):
        cruce = persistencia(*_con_patron())
        assert cruce.hectareas_flojas > cruce.hectareas_por_azar * 2

    def test_dos_fechas_iguales_repiten_el_tercio_entero(self):
        matriz = _con_patron()[0]
        cruce = persistencia(matriz, matriz)
        assert cruce.correlacion == pytest.approx(1.0)
        assert cruce.pixeles_flojos == pytest.approx(cruce.pixeles_comparables / 3, rel=0.05)

    def test_las_hectareas_salen_de_los_pixeles(self):
        cruce = persistencia(*_con_patron())
        assert cruce.hectareas_flojas == pytest.approx(cruce.pixeles_flojos * 0.01)
        assert cruce.hectareas_comparables == pytest.approx(LADO * LADO * 0.01)

    def test_el_azar_es_un_tercio_de_un_tercio(self):
        assert ESPERADO_POR_AZAR == pytest.approx(1 / 9, rel=0.02)


class TestSinPatron:
    def test_dos_fechas_sin_relacion_dan_cerca_del_azar(self):
        generador = np.random.default_rng(7)
        primera = generador.normal(0.6, 0.12, (LADO, LADO)).astype("float32")
        segunda = generador.normal(0.6, 0.12, (LADO, LADO)).astype("float32")

        cruce = persistencia(primera, segunda)
        assert abs(cruce.correlacion) < 0.2
        assert cruce.hectareas_flojas < cruce.hectareas_por_azar * 1.5

    def test_una_fecha_constante_no_rompe_la_correlacion(self):
        # Sin variación no hay nada que correlacionar, y NumPy devolvería NaN, que no se
        # puede mandar en JSON.
        plana = np.full((LADO, LADO), 0.6, dtype="float32")
        assert persistencia(plana, _con_patron()[0]).correlacion == 0.0


class TestNivelGeneral:
    def test_una_subida_pareja_no_cambia_nada(self):
        """Es la propiedad que hace comparable julio con agosto.

        En primavera todo el lote sube de NDVI. Si el método usara umbrales fijos, en la
        fecha alta no habría zona floja y la comparación no diría nada.
        """
        sin_subida = persistencia(*_con_patron(desplazamiento=0.0))
        con_subida = persistencia(*_con_patron(desplazamiento=0.25))
        assert con_subida.pixeles_flojos == sin_subida.pixeles_flojos
        assert con_subida.correlacion == pytest.approx(sin_subida.correlacion)


class TestPixelesSinDato:
    def test_un_pixel_tapado_en_una_fecha_queda_afuera(self):
        primera, segunda = _con_patron()
        primera[0, :] = np.nan

        cruce = persistencia(primera, segunda)
        assert cruce.pixeles_comparables == LADO * LADO - LADO
        assert (cruce.etiquetas[0, :] == FUERA).all()

    def test_cada_pixel_queda_en_una_sola_categoria(self):
        cruce = persistencia(*_con_patron())
        etiquetas = cruce.etiquetas
        assert set(np.unique(etiquetas)) <= {FUERA, NINGUNA, FLOJA, VIGOROSA}
        assert int(np.count_nonzero(etiquetas == FLOJA)) == cruce.pixeles_flojos
        assert int(np.count_nonzero(etiquetas == VIGOROSA)) == cruce.pixeles_vigorosos

    def test_ningun_pixel_es_flojo_y_vigoroso_a_la_vez(self):
        cruce = persistencia(*_con_patron())
        assert not ((cruce.etiquetas == FLOJA) & (cruce.etiquetas == VIGOROSA)).any()


class TestErrores:
    def test_grillas_de_distinto_tamano_fallan(self):
        with pytest.raises(ValueError, match="grillas distintas"):
            persistencia(np.zeros((4, 4), "float32"), np.zeros((5, 5), "float32"))

    def test_sin_ningun_pixel_en_comun_falla(self):
        primera, segunda = _con_patron()
        primera[:] = np.nan
        with pytest.raises(ValueError, match="ningún píxel"):
            persistencia(primera, segunda)

    def test_si_no_se_pisan_los_datos_tampoco_hay_nada_que_cruzar(self):
        primera, segunda = _con_patron()
        primera[: LADO // 2] = np.nan
        segunda[LADO // 2 :] = np.nan
        with pytest.raises(ValueError, match="ningún píxel"):
            persistencia(primera, segunda)
