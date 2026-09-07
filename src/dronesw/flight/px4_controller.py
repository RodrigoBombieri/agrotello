"""Habla con un dron PX4, real o simulado.

Traduce las órdenes del proyecto ("despegá a 30 metros", "volá estos puntos") a llamadas de
MAVSDK, y devuelve la telemetría en las unidades que el resto del sistema espera.

- `_primera`: toma un solo valor de un stream de telemetría y lo cierra.
- `Px4FlightController.conectar`: abre el enlace y espera a que el dron responda.
- `.armar`: arma los motores.
- `.despegar`: sube a la altura pedida y espera a llegar.
- `.aterrizar`: baja y espera el desarme.
- `.bateria_pct`, `.altura_m`, `.esta_armado`: lecturas puntuales de telemetría.
- `.esperar_posicion_valida`: espera a que el GPS y el punto de retorno estén fijados.
- `.posicion`: coordenadas actuales.
- `.subir_mision` y `.iniciar_mision`: cargan y arrancan un plan de waypoints.
- `.progreso_mision`: emite el avance mientras vuela.
- `._a_mission_item`: traduce un waypoint al formato de MAVSDK.
- `._esperar_altura`: bloquea hasta alcanzar una altura, con límite de tiempo.

Técnico: implementa `FlightController` y cumple `SoportaMisionGps`. La misma clase sirve
para el simulador y para hardware real; solo cambia la dirección de conexión. Los métodos
de telemetría de MAVSDK son streams infinitos, por eso las lecturas puntuales pasan por
`_primera`, que cierra la suscripción. Los campos NaN de `MissionItem` significan "usá el
valor por defecto del autopiloto".
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Sequence, TypeVar

from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan

from dronesw.flight.base import FlightController, Posicion, Waypoint

from collections.abc import AsyncGenerator

log = logging.getLogger(__name__)

T = TypeVar("T")

# MAVSDK interpreta NaN como "usá el valor por defecto del autopiloto".
_POR_DEFECTO = float("nan")


async def _primera(stream: AsyncGenerator[T, None]) -> T:
    """Toma un único valor de un stream de telemetría y lo cierra.

    Los métodos de telemetría de MAVSDK devuelven streams infinitos. Cuando solo se
    necesita el valor actual hay que cortar la suscripción, o queda abierta consumiendo
    mensajes hasta que el recolector de basura la cierre.
    """
    try:
        return await anext(stream)
    finally:
        await stream.aclose()


class Px4FlightController(FlightController):
    """Controlador de un vehículo PX4 vía MAVSDK."""

    def __init__(
        self,
        direccion: str = "udpin://0.0.0.0:14540",
        velocidad_ms: float = 5.0,
    ) -> None:
        self._direccion = direccion
        self._velocidad_ms = velocidad_ms
        self._drone = System()

    # --- Ciclo de vida -----------------------------------------------------

    async def conectar(self) -> None:
        log.info("Conectando a %s ...", self._direccion)
        await self._drone.connect(system_address=self._direccion)

        async for estado in self._drone.core.connection_state():
            if estado.is_connected:
                log.info("Vehículo detectado")
                return

    async def armar(self) -> None:
        log.info("Armando motores")
        await self._drone.action.arm()

    async def despegar(self, altura_m: float) -> None:
        await self._drone.action.set_takeoff_altitude(altura_m)

        # PX4 puede ajustar lo pedido (mínimos del airframe, límites de parámetros).
        # Si no coincide, el que manda es el autopiloto y conviene enterarse acá.
        configurada = await self._drone.action.get_takeoff_altitude()
        if abs(configurada - altura_m) > 0.1:
            log.warning(
                "Altura de despegue ajustada por PX4: pedida %.1f m, configurada %.1f m",
                altura_m,
                configurada,
            )

        log.info("Despegando a %.1f m", configurada)
        await self._drone.action.takeoff()
        await self._esperar_altura(configurada)

    async def aterrizar(self) -> None:
        log.info("Aterrizando")
        await self._drone.action.land()

        # El aterrizaje termina cuando PX4 desarma solo.
        async for armado in self._drone.telemetry.armed():
            if not armado:
                log.info("Dron desarmado")
                return

    # --- Telemetría --------------------------------------------------------

    async def bateria_pct(self) -> float:
        bateria = await _primera(self._drone.telemetry.battery())
        pct = bateria.remaining_percent
        # MAVSDK 3.x reporta 0-100, pero versiones y firmwares antiguos usaban 0-1.
        # Un valor <= 1 es casi con certeza una fracción, no una batería al 1%.
        return pct * 100 if pct <= 1.0 else pct

    async def altura_m(self) -> float:
        pos = await _primera(self._drone.telemetry.position())
        return pos.relative_altitude_m

    async def esta_armado(self) -> bool:
        return await _primera(self._drone.telemetry.armed())

    # --- SoportaMisionGps --------------------------------------------------

    async def esperar_posicion_valida(self) -> None:
        log.info("Esperando estimación de posición...")
        async for salud in self._drone.telemetry.health():
            if salud.is_global_position_ok and salud.is_home_position_ok:
                log.info("Posición global y home OK")
                return

    async def posicion(self) -> Posicion:
        pos = await _primera(self._drone.telemetry.position())
        return Posicion(
            lat=pos.latitude_deg,
            lon=pos.longitude_deg,
            altura_m=pos.relative_altitude_m,
        )

    async def subir_mision(self, waypoints: Sequence[Waypoint]) -> None:
        if not waypoints:
            raise ValueError("La misión no tiene waypoints")

        items = [self._a_mission_item(wp) for wp in waypoints]

        # Si se pierde el enlace a mitad de misión, que vuelva solo en vez de quedarse
        # esperando órdenes que no van a llegar.
        await self._drone.mission.set_return_to_launch_after_mission(True)

        log.info("Subiendo misión de %d waypoints", len(items))
        await self._drone.mission.upload_mission(MissionPlan(items))

    async def iniciar_mision(self) -> None:
        log.info("Iniciando misión")
        await self._drone.mission.start_mission()

    async def progreso_mision(self) -> AsyncIterator[tuple[int, int]]:
        async for progreso in self._drone.mission.mission_progress():
            yield progreso.current, progreso.total

    # --- Internos ----------------------------------------------------------

    def _a_mission_item(self, wp: Waypoint) -> MissionItem:
        """Traduce un waypoint del dominio al formato de MAVSDK.

        `is_fly_through=True` hace que el dron pase por el punto sin frenar: en un barrido
        de relevamiento, detenerse en cada waypoint alarga el vuelo sin aportar nada.
        """
        return MissionItem(
            wp.lat,
            wp.lon,
            wp.altura_m,
            self._velocidad_ms,
            True,
            _POR_DEFECTO,  # gimbal_pitch_deg
            _POR_DEFECTO,  # gimbal_yaw_deg
            MissionItem.CameraAction.NONE,
            _POR_DEFECTO,  # loiter_time_s
            _POR_DEFECTO,  # camera_photo_interval_s
            _POR_DEFECTO,  # acceptance_radius_m
            _POR_DEFECTO,  # yaw_deg
            _POR_DEFECTO,  # camera_photo_distance_m
            MissionItem.VehicleAction.NONE,
        )

    async def _esperar_altura(
        self,
        objetivo_m: float,
        tolerancia: float = 0.95,
        timeout_s: float = 60.0,
    ) -> None:
        """Bloquea hasta alcanzar la altura, para que `despegar()` no vuelva antes de tiempo.

        El timeout evita quedarse colgado para siempre si el dron nunca sube (motores
        trabados, viento, un failsafe que lo frena).
        """
        limite = objetivo_m * tolerancia

        async def _subir() -> None:
            async for pos in self._drone.telemetry.position():
                if pos.relative_altitude_m >= limite:
                    return

        try:
            await asyncio.wait_for(_subir(), timeout=timeout_s)
        except asyncio.TimeoutError:
            actual = await self.altura_m()
            raise TimeoutError(
                f"No alcanzó {objetivo_m:.1f} m en {timeout_s:.0f} s (altura actual: {actual:.1f} m)"
            ) from None
