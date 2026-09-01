# Comandos del proyecto

Registro de los comandos que vamos usando, agrupados por **entorno** y **carpeta de
ejecución**. Este archivo se actualiza a medida que aparecen comandos nuevos.

Recordá que hay dos sistemas de archivos separados: el de **Windows** y el de **Ubuntu
(dentro de WSL2)**. Un comando corrido en el lugar equivocado puede fallar o ser muy lento —
por eso cada sección aclara dónde se ejecuta.

---

## 1. Windows (PowerShell o cmd)

Comandos de gestión de WSL. Se corren desde una terminal de Windows, **no** desde adentro de
Ubuntu. La carpeta desde donde los corras no importa.

| Comando | Qué hace |
|---|---|
| `wsl --list --verbose` | Lista las distribuciones instaladas y su versión de WSL (1 o 2) |
| `wsl --install -d Ubuntu-22.04` | Instala WSL2 con Ubuntu 22.04. **Requiere cmd como administrador**. Solo se corre una vez |
| `wsl -d Ubuntu-22.04` | Entra a la terminal de Ubuntu. Arranca en la carpeta de Windows donde estabas parado |
| `wsl --shutdown` | Apaga la máquina virtual de WSL por completo. Útil para reiniciarla tras instalar dependencias |

> Al entrar con `wsl -d`, quedás parado en `/mnt/c/...` (el disco de Windows visto desde
> Ubuntu). Casi siempre querés hacer `cd ~` para pasarte al filesystem de Ubuntu.

---

## 2. WSL / Ubuntu — cualquier carpeta

Comandos generales, una vez adentro de la terminal de Ubuntu.

| Comando | Qué hace |
|---|---|
| `lsb_release -a` | Muestra la versión de Ubuntu instalada. Sirve para verificar la instalación |
| `cd ~` | Va al home de Ubuntu (`/home/tu-usuario`). **Importante**: es donde debe vivir el código, no en `/mnt/c` |
| `exit` | Sale de la terminal de Ubuntu y vuelve al prompt de Windows |
| `ip addr \| grep eth0` | Muestra la IP de la máquina virtual de WSL. Necesaria para conectar QGroundControl desde Windows |

---

## 3. WSL / Ubuntu — carpeta `~` (home)

Instalación inicial de PX4. Son comandos de única vez.

| Comando | Qué hace |
|---|---|
| `git clone https://github.com/PX4/PX4-Autopilot.git --recursive` | Descarga el código de PX4 con todos sus submódulos (~1-2 GB) |
| `bash ./PX4-Autopilot/Tools/setup/ubuntu.sh` | Instala todo el toolchain: compiladores, Python, Gazebo y dependencias. Tarda 10-30 min |
| `ls ~/PX4-Autopilot` | Verifica que el repo de PX4 se haya clonado correctamente |

---

## 4. WSL / Ubuntu — carpeta `~/PX4-Autopilot`

Compilación y ejecución del simulador.

| Comando | Qué hace |
|---|---|
| `make px4_sitl` | Compila PX4 para simulación (SITL). La primera vez tarda 10-30 min |
| `ls ~/PX4-Autopilot/build/px4_sitl_default/bin/px4` | Verifica que el binario del simulador se haya generado |
| `make px4_sitl gz_x500` | Levanta el simulador completo: PX4 SITL + Gazebo con un cuadricóptero x500 |
| `HEADLESS=1 make px4_sitl gz_x500` | Igual que el anterior pero sin interfaz gráfica. Más liviano y no depende de OpenGL |
| `make distclean` | Borra los artefactos de compilación. Útil si un target no se reconoce |

### Variables de entorno útiles

| Comando | Qué hace |
|---|---|
| `PX4_HOME_LAT`, `PX4_HOME_LON`, `PX4_HOME_ALT` | Definen las coordenadas de despegue del dron simulado. Se exportan antes de lanzar el simulador |
| `PX4_GZ_WORLD=windy make px4_sitl gz_x500` | Lanza el simulador en un mundo específico (en este caso, con viento) |

---

## 5. Consola de PX4 (`pxh>`)

Cuando el simulador está corriendo, la terminal queda en el prompt `pxh>`. **No son comandos
de shell**: son del propio autopiloto PX4 y solo funcionan ahí adentro.

| Comando | Qué hace |
|---|---|
| `commander takeoff` | Ordena al dron simulado que despegue |
| `commander land` | Ordena al dron que aterrice |
| `commander status` | Muestra el estado del autopiloto (modo de vuelo, armado, etc.) |
| `commander check` | Corre los chequeos de prevuelo y lista qué impide armar el dron. Primer comando a usar ante un "Arming denied" |
| `param set COM_RC_IN_MODE 4` | Desactiva la exigencia de radiocontrol. Útil en simulación, donde no hay RC físico |
| `listener vehicle_local_position` | Muestra en vivo la posición del dron. Útil para depurar |

---

## 6. Repo `agrotello` — comandos del proyecto

> **Nota**: la ubicación definitiva del repo (Windows vs. dentro de WSL) se define en el
> paso 4 del Sprint 0. Los comandos de abajo se corrieron hasta ahora desde Windows.

### Entorno de Python

| Comando | Qué hace |
|---|---|
| `python -m venv .venv` | Crea el entorno virtual de Python aislado del sistema |
| `.venv\Scripts\activate` | Activa el entorno virtual (sintaxis Windows). En Linux/WSL es `source .venv/bin/activate` |
| `pip install -r requirements.txt` | Instala todas las dependencias del proyecto |
| `pre-commit install` | Activa los hooks que corren ruff y black antes de cada commit |

### Git

| Comando | Qué hace |
|---|---|
| `git status` | Muestra qué archivos se modificaron y cuáles faltan commitear |
| `git add -A` | Agrega todos los cambios al área de staging |
| `git commit -m "mensaje"` | Confirma los cambios en el historial local |
| `git push` | Sube los commits a GitHub |
| `git log --oneline` | Muestra el historial de commits resumido |

### Calidad y tests

| Comando | Qué hace |
|---|---|
| `ruff check src tests` | Corre el linter sobre el código |
| `black src tests` | Formatea el código automáticamente |
| `pytest` | Corre la suite de tests |
