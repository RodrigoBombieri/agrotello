"""Cruza dos fechas del mismo lote y marca lo que se repite en las dos.

Una sola medición no distingue un problema de fondo de un mal día de la imagen. Dos sí:
si un sector sale flojo en dos pasadas separadas por semanas, es del campo. Este archivo
hace ese cruce y devuelve cuánta superficie se repite.

- `Persistencia`: el resultado del cruce, con su mapa y sus superficies.
- `persistencia`: cruza dos matrices de NDVI del mismo lote.

Técnico: cada fecha se ordena **contra sí misma** —el tercio más flojo de esa fecha, no un
umbral fijo— y después se cruzan los dos rankings. Por eso el resultado no depende de la
escala de colores ni del nivel general del cultivo, que sube y baja con la estación: en
agosto todo el lote tiene más NDVI que en julio, pero el tercio flojo de cada una sigue
siendo comparable. `ESPERADO_POR_AZAR` es la superficie que coincidiría sola si las dos
fechas fueran independientes (un tercio de un tercio); informarla al lado del resultado es
lo que permite saber si el patrón significa algo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dronesw.vision.zonas import AREA_PIXEL_HA

CUANTIL_PCT = 33.3
ESPERADO_POR_AZAR = (CUANTIL_PCT / 100.0) ** 2

FUERA = -1
NINGUNA = 0
FLOJA = 1
VIGOROSA = 2


@dataclass(frozen=True)
class Persistencia:
    """Qué partes del lote se repiten entre dos fechas."""

    etiquetas: np.ndarray
    pixeles_flojos: int
    pixeles_vigorosos: int
    pixeles_comparables: int
    correlacion: float

    @property
    def hectareas_flojas(self) -> float:
        return self.pixeles_flojos * AREA_PIXEL_HA

    @property
    def hectareas_vigorosas(self) -> float:
        return self.pixeles_vigorosos * AREA_PIXEL_HA

    @property
    def hectareas_comparables(self) -> float:
        return self.pixeles_comparables * AREA_PIXEL_HA

    @property
    def hectareas_por_azar(self) -> float:
        """Cuánta superficie coincidiría sola si las dos fechas no tuvieran relación."""
        return self.hectareas_comparables * ESPERADO_POR_AZAR

    def __str__(self) -> str:
        return (
            f"{self.hectareas_flojas:.2f} ha flojas en las dos fechas "
            f"(el azar daría {self.hectareas_por_azar:.2f}), "
            f"correlación {self.correlacion:.2f}"
        )


def persistencia(primera: np.ndarray, segunda: np.ndarray) -> Persistencia:
    """Cruza dos fechas del mismo lote y marca los sectores que coinciden.

    Solo entran los píxeles que tienen dato en **las dos** fechas: si una estaba tapada por
    una nube ahí, no hay nada que cruzar.
    """
    if primera.shape != segunda.shape:
        raise ValueError(
            f"Las dos fechas tienen grillas distintas: {primera.shape} contra {segunda.shape}. "
            "No se pueden cruzar píxel a píxel."
        )

    comparables = ~np.isnan(primera) & ~np.isnan(segunda)
    if not comparables.any():
        raise ValueError("No hay ningún píxel con dato en las dos fechas")

    a = primera[comparables]
    b = segunda[comparables]

    etiquetas = np.full(primera.shape, FUERA, dtype="int8")
    etiquetas[comparables] = NINGUNA
    etiquetas[comparables & _flojos(primera, a) & _flojos(segunda, b)] = FLOJA
    etiquetas[comparables & _vigorosos(primera, a) & _vigorosos(segunda, b)] = VIGOROSA

    return Persistencia(
        etiquetas=etiquetas,
        pixeles_flojos=int(np.count_nonzero(etiquetas == FLOJA)),
        pixeles_vigorosos=int(np.count_nonzero(etiquetas == VIGOROSA)),
        pixeles_comparables=int(np.count_nonzero(comparables)),
        correlacion=_correlacion(a, b),
    )


def _flojos(matriz: np.ndarray, valores: np.ndarray) -> np.ndarray:
    """Los píxeles que están en el tercio más flojo **de su propia fecha**."""
    return matriz <= np.percentile(valores, CUANTIL_PCT)


def _vigorosos(matriz: np.ndarray, valores: np.ndarray) -> np.ndarray:
    return matriz >= np.percentile(valores, 100 - CUANTIL_PCT)


def _correlacion(a: np.ndarray, b: np.ndarray) -> float:
    """Qué tanto se parecen las dos fechas, píxel a píxel.

    Devuelve 0 si alguna de las dos es constante: ahí no hay variación que correlacionar y
    NumPy devolvería NaN, que no se puede mandar en JSON.
    """
    if a.size < 2 or a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])
