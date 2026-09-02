"""Entregable del Sprint 0 — vuelo básico verificado contra PX4 SITL.

Secuencia: conectar -> chequeos previos -> armar -> despegar -> hover -> aterrizar.
Incluye logging de telemetría y un failsafe de batería que aborta o aterriza anticipadamente.

Requisitos:
    - PX4 SITL corriendo ([Ubuntu · PX4]):  HEADLESS=1 make px4_sitl gz_x500
    - venv activo ([Ubuntu · proyecto]):    source ~/venvs/agrotello/bin/activate

Uso:
    python scripts/sprint0_hover.py
"""

import asyncio
import logging
import os

from mavsdk import System

# --- Configuración (sobreescribible por variables de entorno) ---------------

MAVSDK_CONNECTION = os.getenv("MAVSDK_CONNECTION", "udpin://0.0.0.0:14540")
TAKEOFF_ALTITUDE_M = float(os.getenv("TAKEOFF_ALTITUDE_M", "5"))
HOVER_SECONDS = int(os.getenv("HOVER_SECONDS", "10"))
BATTERY_FAILSAFE_PCT = float(os.getenv("BATTERY_FAILSAFE_PCT", "15"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sprint0")


# --- Helpers ---------------------------------------------------------------


async def esperar_conexion(drone: System) -> None:
    """Bloquea hasta que MAVSDK detecta el vehículo."""
    log.info("Conectando a %s ...", MAVSDK_CONNECTION)
    await drone.connect(system_address=MAVSDK_CONNECTION)

    async for state in drone.core.connection_state():
        if state.is_connected:
            log.info("Vehículo detectado")
            return


async def esperar_posicion_valida(drone: System) -> None:
    """Espera a que el estimador tenga posición global y home fijadas.

    Sin esto, PX4 rechaza el armado: el dron no sabe dónde está ni a dónde volver.
    """
    log.info("Esperando estimación de posición...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            log.info("Posición global y home OK")
            return


async def leer_bateria_pct(drone: System) -> float:
    """Devuelve una única lectura del porcentaje de batería, en escala 0-100.

    En MAVSDK 3.x `remaining_percent` ya viene en 0-100, pero históricamente algunas
    versiones y firmwares lo reportaron como fracción 0-1. Normalizamos por las dudas:
    un valor <= 1 casi con certeza es una fracción, no una batería al 1%.
    """
    bateria = await drone.telemetry.battery().__anext__()
    pct = bateria.remaining_percent
    return pct * 100 if pct <= 1.0 else pct


async def leer_altura_m(drone: System) -> float:
    """Devuelve una única lectura de la altura relativa al punto de despegue."""
    pos = await drone.telemetry.position().__anext__()
    return pos.relative_altitude_m


# --- Fases del vuelo -------------------------------------------------------


async def chequeos_previos(drone: System) -> bool:
    """Verifica que sea seguro volar. Devuelve False si hay que abortar."""
    await esperar_posicion_valida(drone)

    bateria = await leer_bateria_pct(drone)
    log.info("Batería: %.0f%%", bateria)

    if bateria < BATTERY_FAILSAFE_PCT:
        log.error(
            "Batería %.0f%% por debajo del mínimo (%.0f%%). Se aborta el vuelo.",
            bateria,
            BATTERY_FAILSAFE_PCT,
        )
        return False

    return True


async def despegar(drone: System) -> None:
    await drone.action.set_takeoff_altitude(TAKEOFF_ALTITUDE_M)

    # Leemos de vuelta lo que quedó configurado en el autopiloto: si no coincide con lo
    # pedido, el que manda es PX4 y hay que revisar por qué.
    altura_configurada = await drone.action.get_takeoff_altitude()
    log.info(
        "Altura de despegue — pedida: %.1f m / configurada en PX4: %.1f m",
        TAKEOFF_ALTITUDE_M,
        altura_configurada,
    )

    log.info("Armando motores")
    await drone.action.arm()

    log.info("Despegando")
    await drone.action.takeoff()


async def hover(drone: System) -> None:
    """Mantiene posición, logueando telemetría y vigilando la batería."""
    log.info("Hover por %d segundos", HOVER_SECONDS)

    for segundo in range(HOVER_SECONDS):
        await asyncio.sleep(1)

        altura = await leer_altura_m(drone)
        bateria = await leer_bateria_pct(drone)
        log.info("t=%2ds  altura=%5.1f m  batería=%3.0f%%", segundo + 1, altura, bateria)

        if bateria < BATTERY_FAILSAFE_PCT:
            log.warning("Batería baja durante el vuelo. Se aterriza anticipadamente.")
            return


async def aterrizar(drone: System) -> None:
    log.info("Aterrizando")
    await drone.action.land()

    # El aterrizaje termina cuando PX4 desarma solo.
    async for armado in drone.telemetry.armed():
        if not armado:
            log.info("Dron desarmado. Vuelo completado.")
            return


# --- Punto de entrada ------------------------------------------------------


async def main() -> None:
    drone = System()
    await esperar_conexion(drone)

    if not await chequeos_previos(drone):
        return

    await despegar(drone)
    await hover(drone)
    await aterrizar(drone)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.warning("Interrumpido por el usuario")
