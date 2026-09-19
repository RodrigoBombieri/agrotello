"""Verifica que el mapa pinte los valores correctos y no esconda su propia escala.

Un mapa de colores es fácil de mirar y difícil de auditar: si la escala está mal, el mapa
igual se ve lindo. Estas pruebas fijan qué color le toca a cada valor, que lo que no es
lote quede transparente, y que la página diga con qué escala fue dibujada.

- `TestColorear`: los extremos, el recorte del rango y la transparencia.
- `TestPng`: el archivo que queda en disco conserva el canal alfa.
- `TestHtml`: la página lleva los bordes, la imagen y la escala impresa.

Técnico: la escala estirada hace que dos mapas de fechas distintas no sean comparables, así
que la advertencia y los números de la escala forman parte del entregable. Que estén se
prueba acá: si alguien los saca del HTML, el mapa pasa a mentir por omisión.
"""

import base64

import numpy as np
import pytest

from dronesw.vision.mapa import colorear, guardar_html, guardar_png

ROJO_EXTREMO = (165, 0, 38)
VERDE_EXTREMO = (0, 104, 55)


def _rgb(imagen: np.ndarray, fila: int, columna: int) -> tuple[int, ...]:
    return tuple(int(c) for c in imagen[fila, columna, :3])


class TestColorear:
    def test_devuelve_rgba_de_ocho_bits(self):
        imagen = colorear(np.array([[0.5]], dtype="float32"), 0.0, 1.0)
        assert imagen.shape == (1, 1, 4)
        assert imagen.dtype == np.uint8

    def test_el_minimo_va_rojo_y_el_maximo_verde(self):
        imagen = colorear(np.array([[0.3, 0.7]], dtype="float32"), 0.3, 0.7)
        assert _rgb(imagen, 0, 0) == ROJO_EXTREMO
        assert _rgb(imagen, 0, 1) == VERDE_EXTREMO

    def test_los_valores_fuera_del_rango_se_pegan_al_extremo(self):
        # No se descartan: un par de píxeles raros no pueden comerse toda la gama.
        imagen = colorear(np.array([[-0.5, 0.95]], dtype="float32"), 0.3, 0.7)
        assert _rgb(imagen, 0, 0) == ROJO_EXTREMO
        assert _rgb(imagen, 0, 1) == VERDE_EXTREMO

    def test_lo_que_no_es_lote_queda_transparente(self):
        imagen = colorear(np.array([[0.5, np.nan]], dtype="float32"), 0.3, 0.7)
        assert imagen[0, 0, 3] == 255
        assert imagen[0, 1, 3] == 0

    def test_estirar_la_escala_cambia_el_color_del_mismo_valor(self):
        # El fondo de por qué dos mapas de fechas distintas no se pueden comparar.
        valor = np.array([[0.5]], dtype="float32")
        assert _rgb(colorear(valor, 0.0, 1.0), 0, 0) != _rgb(colorear(valor, 0.5, 0.9), 0, 0)

    @pytest.mark.parametrize(("desde", "hasta"), [(0.5, 0.5), (0.7, 0.4)])
    def test_un_rango_vacio_o_invertido_falla(self, desde, hasta):
        with pytest.raises(ValueError, match="al revés o vacío"):
            colorear(np.array([[0.5]], dtype="float32"), desde, hasta)


class TestPng:
    def test_guarda_un_png_con_transparencia(self, tmp_path):
        from PIL import Image

        imagen = colorear(np.array([[0.4, np.nan]], dtype="float32"), 0.3, 0.7)
        destino = tmp_path / "sub" / "mapa.png"
        guardar_png(imagen, destino)

        assert destino.exists()
        guardado = np.array(Image.open(destino))
        assert guardado.shape == imagen.shape
        assert guardado[0, 1, 3] == 0


class TestHtml:
    def _pagina(self, tmp_path, desde=0.44, hasta=0.80):
        png = tmp_path / "mapa.png"
        guardar_png(colorear(np.array([[0.5]], dtype="float32"), desde, hasta), png)
        html = tmp_path / "mapa.html"
        guardar_html(png, (-58.9, -32.7, -58.89, -32.69), html, "La Florida", desde, hasta)
        return html.read_text(encoding="utf-8")

    def test_lleva_los_bordes_del_lote(self, tmp_path):
        pagina = self._pagina(tmp_path)
        assert "-58.9" in pagina and "-32.69" in pagina

    def test_la_imagen_viaja_incrustada(self, tmp_path):
        pagina = self._pagina(tmp_path)
        incrustado = pagina.split("base64,")[1].split("'")[0]
        assert base64.b64decode(incrustado)[:4] == b"\x89PNG"

    def test_imprime_la_escala_y_avisa_que_no_se_compara(self, tmp_path):
        pagina = self._pagina(tmp_path, desde=0.44, hasta=0.80)
        assert "0.440" in pagina and "0.800" in pagina
        assert "No comparar" in pagina

    def test_la_plantilla_de_mosaicos_llega_entera(self, tmp_path):
        # Las llaves de {z}/{y}/{x} las usa Leaflet: format() no debe consumirlas.
        assert "{z}/{y}/{x}" in self._pagina(tmp_path)
