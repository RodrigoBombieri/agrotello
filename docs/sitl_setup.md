# Levantar PX4 SITL local

Requisito para todo el desarrollo de `mission/` y `mapping/` (Sprint 1 en adelante). No
requiere hardware, corre en tu PC.

## 1. Simulador (elegir una opción)

**Opción headless con Docker (más simple para desarrollo, sin interfaz gráfica):**
Ver el proyecto [px4-gazebo-headless](https://github.com/jonasvautherin/px4-gazebo-headless)
para el comando exacto de `docker run` — expone el puerto UDP `14540` que usa MAVSDK.

**Opción con interfaz gráfica (jMAVSim o Gazebo)**, útil para ver el dron volando durante el
desarrollo: seguir la guía oficial de [PX4 Simulation](https://docs.px4.io/main/en/simulation/).

En cualquiera de las dos, el SITL corriendo abre una consola `pxh>` — probar ahí antes de
tocar código propio:

```
pxh> commander takeoff
pxh> commander land
```

Si el dron simulado despega y aterriza, el SITL está listo.

## 2. Instalar MAVSDK-Python

```bash
pip install mavsdk aioconsole
```

## 3. Probar la conexión desde Python

```bash
apython
```

```python
from mavsdk import System
drone = System()
await drone.connect()          # se conecta a udpin://0.0.0.0:14540 por default
await drone.action.arm()
await drone.action.takeoff()
await drone.action.land()
```

Si el `arm()` tira `COMMAND_DENIED`, generalmente es porque el SITL todavía no tiene "GPS fix"
simulado — esperar unos segundos después de arrancar el simulador y reintentar.

## 4. Variable de entorno del proyecto

`MAVSDK_CONNECTION` en `.env` apunta a la misma dirección (`udpin://0.0.0.0:14540` por
default). El día que haya un dron PX4 físico, esta es la única variable que cambia (por la
conexión serial/radio del hardware real) — el resto del código de misión no se toca.
