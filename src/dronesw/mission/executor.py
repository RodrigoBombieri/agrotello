"""Vuela la misión de principio a fin y la corta si la batería no alcanza.

Hace de director de orquesta: recibe el plan, se lo entrega al dron, y vigila el avance y
la carga mientras vuela para decidir si sigue o baja.

- `DronDeMision`: lo que el ejecutor necesita que un dron sepa hacer.
- `ResultadoMision`: cómo terminó el vuelo.
- `EjecutorMision.ejecutar`: corre la misión completa.
- `._volar_vigilando`: sigue el avance y la batería en paralelo.
- `._seguir_progreso`: escucha en qué waypoint va.
- `._vigilar_bateria`: revisa la carga cada tanto.
- `._esperar_desarme`: espera el fin del aterrizaje, con límite de tiempo.
- `._resultado`: arma el informe final.

Técnico: no conoce MAVSDK ni geometría, solo coordina, y por eso funciona con cualquier
dron que cumpla el protocolo. El progreso y la batería corren como tareas concurrentes
resueltas con `asyncio.wait(FIRST_COMPLETED)`: mirar solo el progreso dejaría una batería
agotándose sin interrumpir nada hasta el último waypoint. Una misión abortada devuelve un
resultado, no una excepción, porque es el sistema haciendo lo correcto.
Acepta un `aviso` opcional que se llama en cada hito del vuelo: la línea de comandos
no lo pasa y solo mira el log, mientras que la pantalla lo usa para mostrar el avance
en vivo sin que el ejecutor sepa que existe una pantalla.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from dronesw.flight.base import SoportaMisionGps, Waypoint

log = logging.getLogger(__name__)


@runtime_checkable
class DronDeMision(SoportaMisionGps, Protocol):
    """Lo que el ejecutor necesita de un dron.

    Declarar el requisito acá, y no reutilizar `FlightController` entero, sigue el principio
    de que la interfaz la define quien la consume: el ejecutor pide exactamente lo que usa,
    ni más ni menos. `Px4FlightController` lo cumple sin declararlo, por tipado estructural.
    """

    async def conectar(self) -> None: ...

    async def bateria_pct(self) -> float: ...

    async def esta_armado(self) -> bool: ...

    async def armar(self) -> None: ...

    async def aterrizar(self) -> None: ...


@dataclass(frozen=True)
class ResultadoMision:
    """Cómo terminó el vuelo."""

    completada: bool
    motivo: str
    waypoints_alcanzados: int
    waypoints_totales: int
    bateria_final_pct: float

    def __str__(self) -> str:
        cabecera = (
            "Misión completada" if self.completada else f"Misión interrumpida ({self.motivo})"
        )
        return (
            f"{cabecera}: {self.waypoints_alcanzados}/{self.waypoints_totales} waypoints, "
            f"batería final {self.bateria_final_pct:.0f}%"
        )


class EjecutorMision:
    """Corre una misión de waypoints y la aborta si la batería no alcanza."""

    def __init__(
        self,
        dron: DronDeMision,
        bateria_minima_pct: float = 20.0,
        intervalo_bateria_s: float = 2.0,
        timeout_retorno_s: float = 300.0,
        aviso: Callable[[str, dict], None] | None = None,
    ) -> None:
        self._dron = dron
        self._avisar = aviso or (lambda evento, datos: None)
        self._bateria_minima_pct = bateria_minima_pct
        self._intervalo_bateria_s = intervalo_bateria_s
        self._timeout_retorno_s = timeout_retorno_s
        self._alcanzados = 0
        self._totales = 0

    async def ejecutar(self, waypoints: Sequence[Waypoint]) -> ResultadoMision:
        """Vuela la misión completa. Devuelve cómo terminó en vez de lanzar excepción.

        Una misión abortada por batería baja no es un error del programa: es el sistema
        haciendo lo correcto. Quien llama decide qué hacer con ese resultado.
        """
        if not waypoints:
            raise ValueError("La misión no tiene waypoints")

        self._totales = len(waypoints)
        self._alcanzados = 0

        self._avisar("conectando", {})
        await self._dron.conectar()
        self._avisar("esperando_posicion", {})
        await self._dron.esperar_posicion_valida()

        bateria = await self._dron.bateria_pct()
        log.info("Batería: %.0f%%", bateria)
        self._avisar("bateria", {"pct": bateria})
        if bateria < self._bateria_minima_pct:
            return await self._resultado(
                False, f"batería insuficiente para despegar ({bateria:.0f}%)"
            )

        self._avisar("subiendo_mision", {"waypoints": len(waypoints)})
        await self._dron.subir_mision(waypoints)
        await self._dron.armar()
        self._avisar("armado", {})
        await self._dron.iniciar_mision()
        self._avisar("volando", {})

        motivo = await self._volar_vigilando()
        completada = motivo == "misión completada"

        if completada:
            # El plan se subió con retorno automático al punto de despegue, así que PX4 ya
            # está volviendo solo: solo hay que esperar a que aterrice y desarme.
            log.info("Misión terminada, esperando el retorno automático")
            self._avisar("volviendo", {})
            if not await self._esperar_desarme(self._timeout_retorno_s):
                # El retorno no terminó a tiempo: puede haber quedado flotando por viento,
                # un failsafe o un home mal fijado. Se baja donde esté antes de gastar el
                # resto de la batería esperando.
                log.warning(
                    "El retorno excedió %.0f s, se aterriza en el lugar", self._timeout_retorno_s
                )
                await self._dron.aterrizar()
        else:
            # Ante batería baja se aterriza donde está, no se vuelve al home: el regreso
            # puede ser más largo que la carga restante.
            log.warning("Aterrizando por: %s", motivo)
            self._avisar("aterrizando", {"motivo": motivo})
            await self._dron.aterrizar()

        return await self._resultado(completada, motivo)

    async def _volar_vigilando(self) -> str:
        """Sigue el avance de la misión y la batería en paralelo.

        Las dos cosas hay que mirarlas a la vez: si solo siguiéramos el progreso, una batería
        agotándose no interrumpiría nada hasta el último waypoint. Se lanzan como tareas
        concurrentes y gana la primera que termine.
        """
        progreso = asyncio.create_task(self._seguir_progreso())
        bateria = asyncio.create_task(self._vigilar_bateria())

        terminadas, pendientes = await asyncio.wait(
            {progreso, bateria}, return_when=asyncio.FIRST_COMPLETED
        )

        for tarea in pendientes:
            tarea.cancel()
        await asyncio.gather(*pendientes, return_exceptions=True)

        return next(iter(terminadas)).result()

    async def _seguir_progreso(self) -> str:
        async for actual, total in self._dron.progreso_mision():
            if total <= 0:
                continue
            # PX4 puede sumar ítems propios al plan (el retorno automático), así que el
            # total real lo dice el autopiloto, no la cantidad de waypoints que subimos.
            self._totales = total
            if actual > self._alcanzados:
                self._alcanzados = actual
                log.info("Waypoint %d/%d", actual, total)
                self._avisar("waypoint", {"actual": actual, "total": total})
            if actual >= total:
                return "misión completada"
        return "el stream de progreso se cortó"

    async def _vigilar_bateria(self) -> str:
        while True:
            pct = await self._dron.bateria_pct()
            self._avisar("bateria", {"pct": pct})
            if pct < self._bateria_minima_pct:
                return f"batería baja ({pct:.0f}%)"
            await asyncio.sleep(self._intervalo_bateria_s)

    async def _esperar_desarme(self, timeout_s: float) -> bool:
        """Espera a que el dron desarme. Devuelve False si se acaba el tiempo.

        Sin este límite, un retorno que nunca termina deja el programa colgado para siempre.
        """

        async def _esperar() -> None:
            while await self._dron.esta_armado():
                await asyncio.sleep(1.0)

        try:
            await asyncio.wait_for(_esperar(), timeout=timeout_s)
            log.info("Dron desarmado")
            return True
        except asyncio.TimeoutError:
            return False

    async def _resultado(self, completada: bool, motivo: str) -> ResultadoMision:
        return ResultadoMision(
            completada=completada,
            motivo=motivo,
            waypoints_alcanzados=self._alcanzados,
            waypoints_totales=self._totales,
            bateria_final_pct=await self._dron.bateria_pct(),
        )
