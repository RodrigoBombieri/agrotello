"""Lleva adelante un vuelo en segundo plano y publica en qué anda, para la pantalla.

El ejecutor de misiones sabe volar de punta a punta, pero lo hace de corrido: arranca y
devuelve cuando terminó. Una pantalla necesita otra cosa — saber en todo momento dónde está
el dron, cuánta batería le queda y por qué waypoint va— y necesita poder cortar el vuelo.
Este archivo es esa capa intermedia.

- `Estado`: la foto del vuelo en un instante, tal como la ve la pantalla.
- `SesionDeVuelo.iniciar`: arranca la misión en segundo plano.
- `SesionDeVuelo.abortar`: lo manda de vuelta al punto de despegue.
- `SesionDeVuelo.estado`: la foto actual, lista para mandar al navegador.
- `._correr`: vuela la misión y registra cómo terminó.
- `._seguir_posicion`: le pregunta al dron dónde está, dos veces por segundo.
- `._esperar_regreso`: después de abortar, espera a que aterrice y desarme.
- `._anotar`: recibe los avisos del ejecutor y los vuelca al estado.

Técnico: hay una sola sesión por servidor, y `iniciar` se niega si ya hay un vuelo en curso;
dos misiones a la vez sobre el mismo dron no tienen sentido y el error tiene que ser
explícito. La posición se sondea aparte del ejecutor, que no la mira: el ejecutor vigila
batería y progreso, y para el mapa hace falta la coordenada. Abortar **no** cancela el
seguimiento de posición, porque después de ordenar el retorno el dron sigue volando y es
justo cuando más se quiere mirar. El controlador se importa dentro de la función a
propósito: así levantar el servidor no arrastra MAVSDK hasta que alguien vuela de verdad.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field

from dronesw.flight.base import Waypoint
from dronesw.mission.executor import DronDeMision, EjecutorMision

log = logging.getLogger(__name__)

INTERVALO_POSICION_S = 0.5
TIMEOUT_REGRESO_S = 300.0


def _px4(direccion: str, velocidad_ms: float) -> DronDeMision:
    """Crea el controlador real. Importa MAVSDK recién acá, la primera vez que se vuela."""
    from dronesw.flight.px4_controller import Px4FlightController

    return Px4FlightController(direccion, velocidad_ms)


@dataclass
class Estado:
    """Cómo está el vuelo ahora mismo.

    `fase` es lo que mira la pantalla para decidir qué botones habilitar:
    `inactivo`, `preparando`, `volando`, `volviendo`, `terminado` o `error`.
    """

    fase: str = "inactivo"
    mensaje: str = ""
    waypoint: int = 0
    waypoints: int = 0
    bateria_pct: float | None = None
    posicion: dict | None = None
    recorrido: list[list[float]] = field(default_factory=list)
    resultado: dict | None = None


class SesionDeVuelo:
    """El único vuelo que el servidor puede tener en curso."""

    def __init__(self, crear_dron: Callable[[str, float], DronDeMision] = _px4) -> None:
        self._crear_dron = crear_dron
        self._estado = Estado()
        self._dron: DronDeMision | None = None
        self._vuelo: asyncio.Task | None = None
        self._seguimiento: asyncio.Task | None = None

    # --- Lo que ve el servidor ---------------------------------------------

    @property
    def activa(self) -> bool:
        return self._vuelo is not None and not self._vuelo.done()

    def estado(self) -> dict:
        return asdict(self._estado)

    async def iniciar(
        self,
        direccion: str,
        waypoints: Sequence[Waypoint],
        velocidad_ms: float,
        bateria_minima_pct: float,
    ) -> None:
        if self.activa:
            raise RuntimeError("Ya hay un vuelo en curso")
        if not waypoints:
            raise ValueError("La misión no tiene waypoints")

        self._estado = Estado(
            fase="preparando",
            mensaje=f"Conectando a {direccion}",
            waypoints=len(waypoints),
        )
        dron = self._crear_dron(direccion, velocidad_ms)
        self._dron = dron
        self._seguimiento = asyncio.create_task(self._seguir_posicion(dron))
        self._vuelo = asyncio.create_task(self._correr(dron, waypoints, bateria_minima_pct))

    async def abortar(self) -> None:
        dron, vuelo = self._dron, self._vuelo
        if dron is None or vuelo is None or vuelo.done():
            raise RuntimeError("No hay ningún vuelo en curso")

        self._estado.fase = "volviendo"
        self._estado.mensaje = "Vuelo abortado: volviendo al punto de despegue"
        await dron.volver_al_despegue()

        # Se corta el ejecutor porque su misión ya no va a avanzar: el autopiloto salió del
        # modo misión. El seguimiento de posición sigue vivo a propósito.
        vuelo.cancel()
        self._vuelo = asyncio.create_task(self._esperar_regreso(dron))

    # --- Adentro -----------------------------------------------------------

    def _anotar(self, evento: str, datos: dict) -> None:
        """Traduce un hito del ejecutor a algo que la pantalla pueda mostrar."""
        if evento == "waypoint":
            self._estado.waypoint = datos["actual"]
            self._estado.waypoints = datos["total"]
        elif evento == "bateria":
            self._estado.bateria_pct = round(datos["pct"], 1)
        elif evento == "volando":
            self._estado.fase = "volando"

        textos = {
            "conectando": "Conectando con el dron",
            "esperando_posicion": "Esperando posición GPS y punto de retorno",
            "subiendo_mision": "Cargando el plan de vuelo",
            "armado": "Motores armados",
            "volando": "En vuelo",
            "volviendo": "Misión terminada: volviendo al punto de despegue",
            "aterrizando": "Aterrizando",
        }
        if evento in textos:
            self._estado.mensaje = textos[evento]
        if evento in ("volviendo", "aterrizando"):
            self._estado.fase = "volviendo"

    async def _correr(
        self, dron: DronDeMision, waypoints: Sequence[Waypoint], bateria_minima_pct: float
    ) -> None:
        ejecutor = EjecutorMision(
            dron,
            bateria_minima_pct=bateria_minima_pct,
            aviso=self._anotar,
        )
        try:
            resultado = await ejecutor.ejecutar(waypoints)
        except asyncio.CancelledError:
            raise  # abortado: `_esperar_regreso` toma la posta
        except Exception as error:
            log.exception("El vuelo falló")
            self._estado.fase = "error"
            self._estado.mensaje = str(error) or error.__class__.__name__
            self._detener_seguimiento()
        else:
            self._estado.fase = "terminado"
            self._estado.mensaje = str(resultado)
            self._estado.resultado = asdict(resultado)
            self._detener_seguimiento()

    async def _esperar_regreso(self, dron: DronDeMision) -> None:
        """Después de abortar, mira hasta que el dron desarme."""

        async def _hasta_desarmar() -> None:
            while await dron.esta_armado():
                await asyncio.sleep(1.0)

        try:
            # `asyncio.timeout` existe recién en Python 3.11 y el proyecto apunta a 3.10.
            await asyncio.wait_for(_hasta_desarmar(), timeout=TIMEOUT_REGRESO_S)
            self._estado.mensaje = "Abortado: el dron volvió y desarmó"
        except asyncio.TimeoutError:
            self._estado.mensaje = "Abortado: el retorno tardó demasiado, revisalo a mano"
        except Exception as error:
            self._estado.mensaje = f"Abortado, pero se perdió el contacto: {error}"
        finally:
            self._estado.fase = "terminado"
            self._detener_seguimiento()

    async def _seguir_posicion(self, dron: DronDeMision) -> None:
        """Le pregunta al dron dónde está, para que la pantalla lo dibuje moviéndose."""
        while True:
            try:
                posicion = await dron.posicion()
            except Exception:
                # Al principio el enlace todavía no existe: no es un error del vuelo.
                await asyncio.sleep(INTERVALO_POSICION_S)
                continue

            self._estado.posicion = {
                "lat": round(posicion.lat, 7),
                "lon": round(posicion.lon, 7),
                "altura_m": round(posicion.altura_m, 1),
            }
            self._estado.recorrido.append([posicion.lat, posicion.lon])
            await asyncio.sleep(INTERVALO_POSICION_S)

    def _detener_seguimiento(self) -> None:
        if self._seguimiento is not None:
            self._seguimiento.cancel()
            self._seguimiento = None
