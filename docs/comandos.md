# Comandos del proyecto

Registro de los comandos que vamos usando, agrupados por **entorno** y **carpeta de
ejecución**. Se actualiza a medida que aparecen comandos nuevos.

## Cómo está organizado el entorno

El código vive en **Windows**, pero se ejecuta desde **Ubuntu (WSL2)**, porque el simulador
PX4 corre ahí. Las piezas quedan así:

| Pieza | Ubicación real | Cómo se accede desde WSL |
|---|---|---|
| Repo `agrotello` | Windows: `C:\Users\Rodrigo\Escritorio\Repositorio Git\agrotello` | `~/agrotello` (enlace simbólico) |
| PX4-Autopilot | Ubuntu: `~/PX4-Autopilot` | directo |
| Entorno virtual | Ubuntu: `~/venvs/agrotello` | directo — **fuera del repo**, a propósito |

El venv está fuera del repo porque instalarlo sobre `/mnt/c` sería muy lento (miles de
archivos chicos cruzando entre los dos sistemas de archivos).

## La regla de las dos terminales

Cada terminal tiene un propósito y **no comparten entorno**. Mezclarlas rompe cosas.

| Terminal | venv | Carpeta | Para qué |
|---|---|---|---|
| **1 — PX4** | ❌ sin venv | `~/PX4-Autopilot` | Compilar y correr el simulador. Usa el Python del sistema, con las dependencias que instaló `ubuntu.sh` |
| **2 — proyecto** | ✅ con venv | `~/agrotello` | Correr tu código con `mavsdk`. Usa el venv aislado |

> Si el build de PX4 falla con `ModuleNotFoundError: No module named 'menuconfig'` o
> `kconfiglib is not installed`, es porque tenías el venv activado. Corré `deactivate` y
> reintentá. **No** instales las dependencias de PX4 dentro del venv.

---

## 1. Windows (PowerShell o cmd)

Gestión de WSL. Se corren desde una terminal de Windows, no desde adentro de Ubuntu.

| Comando | Qué hace |
|---|---|
| `wsl --list --verbose` | Lista las distribuciones instaladas y su versión de WSL (1 o 2) |
| `wsl --install -d Ubuntu-22.04` | Instala WSL2 con Ubuntu 22.04. **Requiere cmd como administrador**. Única vez |
| `wsl -d Ubuntu-22.04` | Entra a la terminal de Ubuntu. Arranca en la carpeta de Windows donde estabas parado |
| `wsl --shutdown` | Apaga la máquina virtual de WSL por completo. Para reiniciarla tras instalar dependencias |
| `net use Z: \\wsl.localhost\Ubuntu-22.04 /persistent:yes` | Monta el filesystem de Ubuntu como unidad `Z:` en Windows. Útil para explorarlo desde el Explorador |

> Al entrar con `wsl -d` quedás parado en `/mnt/c/...`. Casi siempre querés `cd ~` o
> `cd ~/agrotello`.

---

## 2. WSL / Ubuntu — cualquier carpeta

| Comando | Qué hace |
|---|---|
| `lsb_release -a` | Muestra la versión de Ubuntu instalada |
| `cd ~` | Va al home de Ubuntu (`/home/rodrigo`) |
| `exit` | Sale de la terminal de Ubuntu y vuelve al prompt de Windows |
| `code .` | Abre VS Code sobre la carpeta actual en modo Remote-WSL: la interfaz corre en Windows pero edita y ejecuta dentro de Ubuntu. Verificá que abajo a la izquierda diga `WSL: Ubuntu-22.04` |
| `deactivate` | Sale del entorno virtual y vuelve al Python del sistema |
| `sudo apt update` | Actualiza la lista de paquetes disponibles |
| `sudo apt install <paquete> -y` | Instala un paquete del sistema |
| `ip addr \| grep eth0` | Muestra la IP de la máquina virtual de WSL. Necesaria para conectar QGroundControl desde Windows |

---

## 3. WSL / Ubuntu — instalación inicial (carpeta `~`)

Comandos de única vez.

| Comando | Qué hace |
|---|---|
| `git clone https://github.com/PX4/PX4-Autopilot.git --recursive` | Descarga PX4 con todos sus submódulos (~1-2 GB) |
| `bash ./PX4-Autopilot/Tools/setup/ubuntu.sh` | Instala el toolchain completo: compiladores, Python, Gazebo y dependencias. Tarda 10-30 min |
| `sudo apt install python3.10-venv -y` | Instala el módulo de entornos virtuales. Ubuntu lo separa del Python base |
| `ln -s "/mnt/c/Users/Rodrigo/Escritorio/Repositorio Git/agrotello" ~/agrotello` | Crea el atajo a la carpeta del repo en Windows, para no escribir la ruta larga con espacios |
| `python3 -m venv ~/venvs/agrotello` | Crea el entorno virtual del proyecto, fuera del repo |

---

## 4. WSL / Ubuntu — carpeta `~/PX4-Autopilot` (Terminal 1, sin venv)

| Comando | Qué hace |
|---|---|
| `make px4_sitl` | Compila PX4 para simulación. La primera vez tarda 10-30 min |
| `make px4_sitl gz_x500` | Levanta el simulador completo: PX4 SITL + Gazebo con un cuadricóptero x500 |
| `HEADLESS=1 make px4_sitl gz_x500` | Igual pero sin interfaz gráfica. Más liviano, no depende de OpenGL |
| `make distclean` | Borra los artefactos de compilación. Útil si un target no se reconoce o el build quedó a medias |
| `ls ~/PX4-Autopilot/build/px4_sitl_default/bin/px4` | Verifica que el binario del simulador se haya generado |

### Variables de entorno útiles

| Comando | Qué hace |
|---|---|
| `PX4_HOME_LAT`, `PX4_HOME_LON`, `PX4_HOME_ALT` | Definen las coordenadas de despegue del dron simulado. Se exportan antes de lanzar |
| `PX4_GZ_WORLD=windy make px4_sitl gz_x500` | Lanza el simulador en un mundo específico (acá, con viento) |

---

## 5. Consola de PX4 (`pxh>`)

Con el simulador corriendo, la terminal queda en el prompt `pxh>`. **No son comandos de
shell**: son del autopiloto y solo funcionan ahí adentro.

| Comando | Qué hace |
|---|---|
| `commander takeoff` | Ordena al dron simulado que despegue |
| `commander land` | Ordena al dron que aterrice |
| `commander status` | Muestra el estado del autopiloto (modo de vuelo, armado, etc.) |
| `commander check` | Corre los chequeos de prevuelo. Primer comando ante un "Arming denied" |
| `listener vehicle_local_position` | Muestra en vivo la posición del dron. Útil para depurar |
| `param set NAV_DLL_ACT 0` | Desactiva el failsafe por pérdida de enlace con la estación de control. Necesario en SITL, donde no hay GCS conectada |
| `param set CBRK_SUPPLY_CHK 894281` | Desactiva el chequeo del módulo de alimentación, que no existe en simulación. El número es un valor mágico que PX4 exige para confirmar que es intencional |
| `param save` | Guarda los parámetros para que persistan entre reinicios del simulador |

> Los dos `param set` son **solo para simulación**. En un dron real esos chequeos existen por
> buenas razones y no se tocan.

---

## 6. WSL / Ubuntu — carpeta `~/agrotello` (Terminal 2, con venv)

### Entorno de Python

| Comando | Qué hace |
|---|---|
| `source ~/venvs/agrotello/bin/activate` | Activa el entorno virtual. El prompt pasa a mostrar `(agrotello)` |
| `pip install --upgrade pip` | Actualiza pip |
| `pip install mavsdk aioconsole` | Instala el SDK de vuelo y la consola interactiva async |
| `pip install -r requirements.txt` | Instala todas las dependencias del proyecto (pesado: incluye torch y opencv) |
| `pip show mavsdk` | Muestra la versión y ubicación de un paquete instalado |
| `pre-commit install` | Activa los hooks que corren ruff y black antes de cada commit |

### Sesión interactiva con el dron

`apython` es una consola de Python que acepta `await` directamente, sin envolver todo en
funciones `async`. Requiere el simulador ya corriendo en la Terminal 1.

```python
apython                          # abre la consola (desde la shell, con el venv activo)

from mavsdk import System
drone = System()
await drone.connect()            # conecta a udpin://0.0.0.0:14540 por default
await drone.action.arm()         # arma los motores
await drone.action.takeoff()     # despega — mandarlo pocos segundos después del arm()
await drone.action.land()        # aterriza
```

> Si tardás mucho entre `arm()` y `takeoff()`, PX4 desarma solo por seguridad.

### Git

| Comando | Qué hace |
|---|---|
| `git status` | Muestra qué archivos se modificaron y cuáles faltan commitear |
| `git add -A` | Agrega todos los cambios al área de staging |
| `git commit -m "mensaje"` | Confirma los cambios en el historial local |
| `git push` | Sube los commits a GitHub |
| `git pull` | Trae los commits que estén en GitHub y no tengas localmente |
| `git log --oneline` | Muestra el historial de commits resumido |
| `git config core.filemode false` | Evita que git reporte cambios de permisos falsos al trabajar sobre `/mnt/c` |

### Calidad y tests

| Comando | Qué hace |
|---|---|
| `ruff check src tests` | Corre el linter sobre el código |
| `black src tests` | Formatea el código automáticamente |
| `pytest` | Corre la suite de tests |
