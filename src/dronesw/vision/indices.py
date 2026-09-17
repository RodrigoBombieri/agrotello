"""Calcula qué tan sana está la vegetación a partir de las bandas del satélite.

El NDVI compara cuánta luz roja absorbe la planta contra cuánto infrarrojo refleja. Una hoja
sana absorbe casi todo el rojo y devuelve mucho infrarrojo; una estresada, o el suelo desnudo,
no marcan ese contraste. El resultado va de -1 a 1: arriba de 0,6 suele ser vegetación
vigorosa, alrededor de 0,2 suelo casi pelado, y negativo, agua.

- `mascara_utilizable`: marca qué píxeles sirven, según la clasificación del satélite.
- `calcular_ndvi`: aplica la fórmula y deja en blanco los píxeles que no sirven.
- `ResumenNdvi`: las estadísticas del lote, siempre junto con cuánto se pudo ver.
- `resumir`: calcula ese resumen ignorando los píxeles en blanco.

Técnico: las bandas llegan como enteros sin signo, y restarlos así hace que un valor negativo
dé la vuelta y se convierta en uno gigante — por eso se convierte a float antes de operar. El
factor de escala se cancela en el cociente, así que no hace falta pasar a reflectancia. Los
píxeles descartados quedan como NaN, lo que permite usar las funciones `nan*` de NumPy sin
arrastrarlos a las cuentas. El agua **no** se descarta: un sector anegado es un hallazgo
agronómico, no un defecto de la imagen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Códigos de la capa de clasificación de Sentinel-2 en los que no se puede confiar.
# Se conservan 4 (vegetación), 5 (suelo desnudo), 6 (agua) y 7 (sin clasificar).
SIN_DATO = 0
DEFECTUOSO = 1
ZONA_OSCURA = 2
SOMBRA_DE_NUBE = 3
NUBE_PROBABLE = 8
NUBE_SEGURA = 9
CIRRO = 10
NIEVE = 11

CODIGOS_DESCARTADOS = frozenset(
    {SIN_DATO, DEFECTUOSO, ZONA_OSCURA, SOMBRA_DE_NUBE, NUBE_PROBABLE, NUBE_SEGURA, CIRRO, NIEVE}
)


def mascara_utilizable(clasificacion: np.ndarray) -> np.ndarray:
    """Devuelve True en los píxeles cuyo valor se puede usar."""
    return ~np.isin(clasificacion, list(CODIGOS_DESCARTADOS))


def calcular_ndvi(
    rojo: np.ndarray, infrarrojo: np.ndarray, mascara: np.ndarray | None = None
) -> np.ndarray:
    """Calcula el NDVI píxel a píxel. Los que no sirven quedan como NaN.

    La conversión a float no es un detalle de estilo: con enteros sin signo, un píxel donde el
    rojo supera al infrarrojo daría un número enorme en vez de un valor negativo.
    """
    if rojo.shape != infrarrojo.shape:
        raise ValueError(
            f"Las bandas no coinciden: rojo {rojo.shape}, infrarrojo {infrarrojo.shape}"
        )

    r = rojo.astype("float32")
    n = infrarrojo.astype("float32")
    suma = n + r

    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where(suma > 0, (n - r) / suma, np.nan).astype("float32")

    if mascara is not None:
        if mascara.shape != ndvi.shape:
            raise ValueError(f"La máscara no coincide: {mascara.shape} contra {ndvi.shape}")
        ndvi = np.where(mascara, ndvi, np.nan)

    return ndvi


@dataclass(frozen=True)
class ResumenNdvi:
    """Estadísticas del lote, siempre acompañadas de cuánto se pudo ver."""

    medio: float
    mediana: float
    minimo: float
    maximo: float
    p2: float
    p98: float
    pixeles_totales: int
    pixeles_utiles: int

    @property
    def cobertura_pct(self) -> float:
        return 100.0 * self.pixeles_utiles / self.pixeles_totales

    def __str__(self) -> str:
        return (
            f"NDVI medio {self.medio:.3f} (mediana {self.mediana:.3f}, "
            f"rango {self.minimo:.3f} a {self.maximo:.3f}) "
            f"sobre el {self.cobertura_pct:.0f} % del lote"
        )


def resumir(ndvi: np.ndarray) -> ResumenNdvi:
    """Resume el NDVI del lote ignorando los píxeles descartados."""
    utiles = int(np.count_nonzero(~np.isnan(ndvi)))
    if utiles == 0:
        raise ValueError("No quedó ningún píxel utilizable: la fecha no sirve para este lote")

    return ResumenNdvi(
        medio=float(np.nanmean(ndvi)),
        mediana=float(np.nanmedian(ndvi)),
        minimo=float(np.nanmin(ndvi)),
        maximo=float(np.nanmax(ndvi)),
        p2=float(np.nanpercentile(ndvi, 2)),
        p98=float(np.nanpercentile(ndvi, 98)),
        pixeles_totales=int(ndvi.size),
        pixeles_utiles=utiles,
    )
