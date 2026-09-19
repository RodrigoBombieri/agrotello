"""Verifica que el NDVI se calcule bien y que nunca mienta sobre cuánto vio.

El NDVI es una división entre dos bandas del satélite, y las dos trampas que tiene son de
tipos, no de fórmula: los datos llegan como enteros sin signo, y los píxeles descartados
tienen que quedar fuera de las cuentas sin arrastrar el promedio.

- `TestMascaraUtilizable`: qué códigos de la clasificación se conservan y cuáles no.
- `TestCalculoNdvi`: la fórmula, el desbordamiento de enteros y la máscara.
- `TestResumen`: las estadísticas y, sobre todo, el denominador de la cobertura.

Técnico: la prueba del desbordamiento es la importante. Con `uint16`, restarle al
infrarrojo un rojo mayor da un número enorme en vez de negativo, y el NDVI sale positivo
justo donde el suelo está peor. Es un error silencioso: no falla, miente.
"""

import numpy as np
import pytest

from dronesw.vision.indices import (
    CODIGOS_DESCARTADOS,
    ResumenNdvi,
    calcular_ndvi,
    mascara_utilizable,
    resumir,
)


class TestMascaraUtilizable:
    def test_conserva_los_codigos_de_suelo_vegetacion_y_agua(self):
        clasificacion = np.array([[4, 5, 6, 7]], dtype="uint8")
        assert mascara_utilizable(clasificacion).all()

    def test_descarta_nubes_sombras_y_defectos(self):
        clasificacion = np.array([sorted(CODIGOS_DESCARTADOS)], dtype="uint8")
        assert not mascara_utilizable(clasificacion).any()

    def test_el_agua_no_se_descarta(self):
        # Un sector anegado es un hallazgo agronómico, no un defecto de la imagen.
        assert 6 not in CODIGOS_DESCARTADOS


class TestCalculoNdvi:
    def test_valor_conocido(self):
        rojo = np.array([[1000]], dtype="uint16")
        infrarrojo = np.array([[3000]], dtype="uint16")
        assert calcular_ndvi(rojo, infrarrojo)[0, 0] == pytest.approx(0.5)

    def test_el_factor_de_escala_se_cancela(self):
        crudo = calcular_ndvi(np.array([[972]], "uint16"), np.array([[2718]], "uint16"))
        escalado = calcular_ndvi(np.array([[9720]], "uint16"), np.array([[27180]], "uint16"))
        assert crudo[0, 0] == pytest.approx(escalado[0, 0])

    def test_rojo_mayor_que_infrarrojo_da_negativo(self):
        # Con enteros sin signo la resta se da vuelta y el resultado saldría enorme.
        ndvi = calcular_ndvi(np.array([[3000]], "uint16"), np.array([[1000]], "uint16"))
        assert ndvi[0, 0] == pytest.approx(-0.5)

    def test_ambas_bandas_en_cero_no_divide_por_cero(self):
        ndvi = calcular_ndvi(np.zeros((1, 1), "uint16"), np.zeros((1, 1), "uint16"))
        assert np.isnan(ndvi[0, 0])

    def test_la_mascara_deja_en_blanco_los_descartados(self):
        rojo = np.full((2, 2), 1000, dtype="uint16")
        infrarrojo = np.full((2, 2), 3000, dtype="uint16")
        mascara = np.array([[True, False], [False, True]])
        ndvi = calcular_ndvi(rojo, infrarrojo, mascara=mascara)
        assert np.isnan(ndvi[0, 1]) and np.isnan(ndvi[1, 0])
        assert ndvi[0, 0] == pytest.approx(0.5)

    def test_bandas_de_distinto_tamano_fallan(self):
        with pytest.raises(ValueError, match="no coinciden"):
            calcular_ndvi(np.zeros((2, 2), "uint16"), np.zeros((3, 3), "uint16"))

    def test_mascara_de_distinto_tamano_falla(self):
        with pytest.raises(ValueError, match="máscara"):
            calcular_ndvi(
                np.zeros((2, 2), "uint16"),
                np.zeros((2, 2), "uint16"),
                mascara=np.ones((3, 3), bool),
            )


class TestResumen:
    def test_estadisticas_basicas(self):
        ndvi = np.array([[0.2, 0.4, 0.6, 0.8]], dtype="float32")
        resumen = resumir(ndvi)
        assert resumen.medio == pytest.approx(0.5)
        assert resumen.minimo == pytest.approx(0.2)
        assert resumen.maximo == pytest.approx(0.8)
        assert resumen.pixeles_utiles == 4

    def test_ignora_los_descartados(self):
        ndvi = np.array([[0.4, np.nan, 0.6]], dtype="float32")
        resumen = resumir(ndvi)
        assert resumen.medio == pytest.approx(0.5)
        assert resumen.pixeles_utiles == 2
        assert resumen.cobertura_pct == pytest.approx(200 / 3)

    def test_la_cobertura_se_mide_contra_el_lote_no_contra_el_recorte(self):
        # Lo de afuera del alambrado no es lote sin ver: simplemente no es lote.
        ndvi = np.array([[0.5, 0.5, np.nan, np.nan]], dtype="float32")
        dentro = np.array([[True, True, False, False]])
        assert resumir(ndvi).cobertura_pct == pytest.approx(50.0)
        assert resumir(ndvi, dentro=dentro).cobertura_pct == pytest.approx(100.0)

    def test_las_nubes_sobre_el_lote_si_bajan_la_cobertura(self):
        ndvi = np.array([[0.5, np.nan, np.nan, np.nan]], dtype="float32")
        dentro = np.array([[True, True, False, False]])
        assert resumir(ndvi, dentro=dentro).cobertura_pct == pytest.approx(50.0)

    def test_sin_ningun_pixel_util_falla(self):
        with pytest.raises(ValueError, match="ningún píxel"):
            resumir(np.full((2, 2), np.nan, dtype="float32"))

    def test_mascara_del_lote_de_distinto_tamano_falla(self):
        with pytest.raises(ValueError, match="no coincide"):
            resumir(np.zeros((2, 2), "float32"), dentro=np.ones((3, 3), bool))

    def test_el_texto_informa_la_cobertura(self):
        resumen = ResumenNdvi(0.6, 0.6, 0.4, 0.8, 0.45, 0.75, 100, 62)
        assert "62 %" in str(resumen)
