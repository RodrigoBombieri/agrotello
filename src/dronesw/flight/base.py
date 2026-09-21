"""Define qué sabe hacer un dron, sin atarse a ninguno en particular.

El proyecto usa dos drones con roles distintos: uno vuela las misiones y otro filma. Este
archivo describe el contrato que cumplen, para que el resto del sistema no dependa de cuál
está conectado.

- `Posicion`: dónde está el dron.
- `Waypoint`: un punto de paso de una misión.
- `FlightController`: lo que todo dron sabe hacer (conectar, armar, despegar, aterrizar,
  informar batería y altura).
- `SoportaMisionGps`: capacidad extra de volar waypoints por GPS. Solo PX4.
- `SoportaVideo`: capacidad extra de entregar video. Solo Tello.

Técnico: `FlightController` es una ABC con métodos abstractos; las capacidades son
`Protocol` de tipado estructural, así una implementación las cumple sin heredarlas y el
type checker avisa en tiempo de escritura si a una función le pasan un dron sin la
capacidad que necesita. Todo es async porque MAVSDK lo es, y la batería se expresa siempre
en escala 0-100.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# --- Tipos del dominio -----------------------------------------------------
#
# Viven acá, y no en `mission/`, porque los necesitan tanto la capa de vuelo como la de
# misión. Ponerlos en el medio evita un import circular entre ambas.


@dataclass(frozen=True)
class Posicion:
    """Posición del dron en un instante.

    `altura_m` es relativa al punto de despegue, no sobre el nivel del mar: es la
    referencia que importa para volar y la que reportan ambos backends.
    """

    lat: float
    lon: float
    altura_m: float


@dataclass(frozen=True)
class Waypoint:
    """Punto de paso de una misión, en coordenadas geográficas."""

    lat: float
    lon: float
    altura_m: float


# --- Contrato común --------------------------------------------------------


class FlightController(ABC):
    """Operaciones que cualquier dron del proyecto sabe hacer.

    Deliberadamente mínima: si algo no lo cumplen los dos backends, no va acá sino en una
    capacidad opcional.
    """

    @abstractmethod
    async def conectar(self) -> None:
        """Establece el enlace y espera a que el vehículo responda.

        Debe bloquear hasta que la conexión esté confirmada, no solo iniciada.
        """

    @abstractmethod
    async def bateria_pct(self) -> float:
        """Carga restante en escala 0-100.

        Cada backend normaliza internamente: hacia afuera hay un solo criterio. MAVSDK
        y djitellopy no coinciden en unidades, y esa ambigüedad ya causó un bug real.
        """

    @abstractmethod
    async def altura_m(self) -> float:
        """Altura actual relativa al punto de despegue, en metros."""

    @abstractmethod
    async def esta_armado(self) -> bool:
        """True si los motores están armados."""

    @abstractmethod
    async def armar(self) -> None:
        """Arma los motores. Puede fallar si el dron no pasa sus chequeos previos."""

    @abstractmethod
    async def despegar(self, altura_m: float) -> None:
        """Despega hasta la altura indicada, relativa al punto de despegue."""

    @abstractmethod
    async def aterrizar(self) -> None:
        """Aterriza y espera a que el dron quede desarmado."""


# --- Capacidades opcionales ------------------------------------------------


@runtime_checkable
class SoportaMisionGps(Protocol):
    """Backends que conocen su posición absoluta y ejecutan misiones de waypoints.

    Lo cumple PX4. El Tello no: no tiene GPS.
    """

    async def esperar_posicion_valida(self) -> None:
        """Espera a que el estimador tenga posición global y home fijadas.

        Sin esto el autopiloto rechaza el armado: no sabe dónde está ni a dónde volver.
        """
        ...

    async def posicion(self) -> Posicion:
        """Posición actual del dron."""
        ...

    async def subir_mision(self, waypoints: Sequence[Waypoint]) -> None:
        """Carga el plan de vuelo en el autopiloto, sin iniciarlo."""
        ...

    async def iniciar_mision(self) -> None:
        """Arranca la misión previamente cargada."""
        ...

    def progreso_mision(self) -> AsyncIterator[tuple[int, int]]:
        """Emite `(waypoint_actual, total)` a medida que avanza la misión."""
        ...

    async def volver_al_despegue(self) -> None:
        """Interrumpe lo que esté haciendo y lo manda de vuelta al punto de despegue.

        Sube a una altura segura, vuelve y aterriza ahí. Es lo que se espera de un botón de
        abortar: termina en un lugar conocido, aunque cruzando el campo y gastando batería.
        """
        ...


@runtime_checkable
class SoportaVideo(Protocol):
    """Backends con cámara accesible desde código.

    Lo cumple el Tello. En nuestro setup PX4 no: el SITL no entrega video usable.
    """

    def frames(self) -> Iterator[Any]:
        """Emite los cuadros del video como arrays de OpenCV (alto, ancho, 3)."""
        ...
