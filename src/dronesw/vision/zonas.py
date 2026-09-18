"""Separa el lote en zonas de vigor y mide cuánta superficie ocupa cada una.

Un promedio no sirve para decidir dónde ir: dice cómo está el campo en conjunto, no qué
sector anda mal. Este archivo divide el lote en tres categorías —flojo, normal y vigoroso—
tomando como referencia el propio campo, y convierte cada una en hectáreas.

- `Zona`: una categoría, con su rango de NDVI, su cantidad de píxeles y su superficie.
- `Zonificacion`: las tres zonas juntas, más el mapa de a qué zona pertenece cada píxel.
- `clasificar`: calcula los cortes y arma la zonificación.

Técnico: los cortes son la media del lote más y menos `k` desvíos estándar, no terciles.
La ventaja no es que evite marcar zonas en un campo parejo —con una distribución normal
los dos métodos parten el lote en tres pedazos parecidos— sino que los cortes siguen la
forma real de la distribución: si hay dos poblaciones separadas, la zona intermedia queda
casi vacía y eso se ve, mientras que los terciles siempre la llenan. Para el lote
genuinamente uniforme está `UMBRAL_UNIFORME`: por debajo de ese desvío las zonas están
partiendo ruido, y hay que avisarlo en vez de dibujar un mapa que promete precisión que no
existe. Los píxeles descartados llegan como NaN y quedan etiquetados `FUERA`, sin entrar en
ninguna cuenta. Cada píxel de Sentinel-2 mide 10 x 10 m, o sea 0,01 ha.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

AREA_PIXEL_HA = 0.01

# Por debajo de este desvío el lote es parejo y las zonas separan ruido, no vigor.
UMBRAL_UNIFORME = 0.03

# Un lote sin variación real no da desvío exactamente cero: el promedio en float32 arrastra
# un error de redondeo de ~1e-7, suficiente para que todos los píxeles caigan de un lado.
DESVIO_DESPRECIABLE = 1e-6

FUERA = -1
NOMBRES = ("flojo", "normal", "vigoroso")


@dataclass(frozen=True)
class Zona:
    """Una categoría de vigor, con lo que realmente se encontró dentro de ella."""

    nombre: str
    minimo: float
    maximo: float
    ndvi_medio: float
    pixeles: int

    @property
    def hectareas(self) -> float:
        return self.pixeles * AREA_PIXEL_HA


@dataclass(frozen=True)
class Zonificacion:
    """Las tres zonas del lote, más el mapa que dice a cuál pertenece cada píxel."""

    etiquetas: np.ndarray
    zonas: tuple[Zona, ...]
    corte_bajo: float
    corte_alto: float
    desvio: float

    @property
    def uniforme(self) -> bool:
        """True si el lote varía tan poco que separarlo en zonas no significa nada."""
        return self.desvio < UMBRAL_UNIFORME

    @property
    def pixeles_clasificados(self) -> int:
        return sum(zona.pixeles for zona in self.zonas)

    @property
    def hectareas(self) -> float:
        return self.pixeles_clasificados * AREA_PIXEL_HA

    def porcentaje(self, zona: Zona) -> float:
        """Qué parte del lote medido ocupa esta zona."""
        return 100.0 * zona.pixeles / self.pixeles_clasificados


def clasificar(ndvi: np.ndarray, k: float = 0.5) -> Zonificacion:
    """Parte el lote en zona floja, normal y vigorosa, según su propia dispersión.

    `k` es cuántos desvíos estándar se aparta cada corte de la media. Más chico, zonas de
    punta más grandes y más sensibles; más grande, solo se marcan los extremos francos.
    """
    if k <= 0:
        raise ValueError(f"k tiene que ser mayor que cero, se recibió {k}")

    validos = ~np.isnan(ndvi)
    if not validos.any():
        raise ValueError("No quedó ningún píxel utilizable para zonificar")

    medio = float(np.nanmean(ndvi))
    desvio = float(np.nanstd(ndvi))
    corte_bajo = medio - k * desvio
    corte_alto = medio + k * desvio

    etiquetas = np.full(ndvi.shape, FUERA, dtype="int8")
    if desvio < DESVIO_DESPRECIABLE:
        # Lote sin variación medible: no hay nada que separar, va todo a "normal".
        etiquetas[validos] = 1
    else:
        etiquetas[validos & (ndvi < corte_bajo)] = 0
        etiquetas[validos & (ndvi >= corte_bajo) & (ndvi <= corte_alto)] = 1
        etiquetas[validos & (ndvi > corte_alto)] = 2

    zonas = []
    for codigo, nombre in enumerate(NOMBRES):
        valores = ndvi[etiquetas == codigo]
        vacia = valores.size == 0
        zonas.append(
            Zona(
                nombre=nombre,
                minimo=float("nan") if vacia else float(valores.min()),
                maximo=float("nan") if vacia else float(valores.max()),
                ndvi_medio=float("nan") if vacia else float(valores.mean()),
                pixeles=int(valores.size),
            )
        )

    return Zonificacion(
        etiquetas=etiquetas,
        zonas=tuple(zonas),
        corte_bajo=corte_bajo,
        corte_alto=corte_alto,
        desvio=desvio,
    )
