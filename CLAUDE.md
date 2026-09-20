# Notas para Claude

Contexto que se pierde entre sesiones. Leer esto primero al retomar el proyecto.

## Cómo trabaja Rodrigo

- **El código va en el chat, no directo al repo.** Él lo copia, analiza y lo pega en sus archivos.
  Escribir archivos directamente solo si lo pide explícitamente. Los documentos (`docs/`,
  `PLANNING.md`, este archivo) sí se escriben directo.
- **Primero el código, después los imports** (pedido suyo, 2026-09-18). Su editor borra al
  guardar los imports que todavía no usa nadie, así que si los pega antes del código que los
  usa, desaparecen — y peor, el autoimport se los repone después apuntando al módulo
  equivocado. Ya pasó: `Affine` terminó importado de `rasterio.windows` en vez de `affine`.
  En cada paso, entonces: bloques de código primero, bloque de imports al final.
- **Al pasarle un bloque que va en el medio de una función, mostrar las líneas de alrededor**,
  no describir dónde va ("justo antes de tal if"). Un bloque suelto se pega con la indentación
  equivocada: ya terminó anidado dentro del `if` anterior y rompió el archivo.
- **Etiquetar siempre la terminal** antes de cada bloque de comandos. Para no confundir entre los
  cinco contextos. Las etiquetas están definidas en `docs/comandos.md`:
  `[Git Bash]`, `[Ubuntu · PX4]`, `[Ubuntu · proyecto]`, `[pxh>]`, `[apython]`.
- **Los commits los hace desde Git Bash en Windows**, nunca desde WSL (las credenciales de
  GitHub funcionan de ese lado). Ruta: `~/Escritorio/Repositorio\ Git/agrotello`.
- Responder en español, conciso y directo.
- Va paso a paso y pide confirmación entre pasos. No adelantarse varios pasos de una.
- **Pasos pocos y grandes, no muchos y chicos** (pedido suyo, 2026-09-19). El Sprint 2 tuvo
  ocho y le resultó mentalmente más largo de lo que era. Apuntar a **cuatro o cinco por
  sprint**, cada uno una unidad con sentido propio. Dentro de un paso se puede ir de a poco
  en la conversación; lo que no conviene es la lista larga de sub-pasos numerados.

## En la primera sesión del día: qué sabe hacer el sistema (pedido suyo, desde 2026-09-16)

**Al abrir la primera conversación de un día, antes de cualquier otra cosa, resumirle qué
puede hacer el código hasta ese momento.** Sirve para retomar el hilo después de días sin
tocarlo.

Cómo tiene que ser: **en capacidades, no en archivos**. "Puede calcular el recorrido que cubre
un lote y volarlo solo" sirve; "existe `planner.py`" no dice nada. Corto — la lista de abajo y
una línea de en qué paso estamos. Si un día ya hubo conversación, no repetirlo.

### Qué sabe hacer hoy

*(Mantener actualizada al cerrar cada paso.)*

1. Definir un lote en un archivo de texto: su contorno en coordenadas y cómo quiere volarse
   (altura, separación entre pasadas, velocidad, orientación, margen del alambrado).
2. Calcular el recorrido en zigzag que cubre ese lote, recortado contra su forma real.
3. Exportar ese recorrido a un mapa que se ve sobre la imagen satelital en geojson.io.
4. Volar el recorrido solo, en el simulador PX4: despega, recorre los waypoints, vuelve y
   aterriza, vigilando la batería y abortando si no alcanza.
5. Hacer un vuelo de prueba simple (despegue, hover, aterrizaje) con el mismo failsafe.
6. Preguntarle al catálogo de Sentinel-2 qué imágenes hay del lote en un rango de fechas y
   con cuánta nube tenía cada una.
7. Traer del satélite únicamente el recorte del lote (33 x 33 píxeles) de la banda roja, la
   infrarroja y la de clasificación, sin descargar la escena de un gigabyte.
8. Calcular el NDVI de ese recorte descartando los píxeles con nube, sombra o nieve, y
   resumirlo en promedio, mediana, rango, percentiles e histograma — siempre acompañado del
   porcentaje del lote que efectivamente pudo medir.
9. Recortar ese NDVI contra el contorno real del lote, descartando el campo vecino que entra
   en el rectángulo, y separar lo que queda en zona floja, normal y vigorosa, cada una medida
   en hectáreas.

10. Dibujar ese NDVI como un mapa de colores sobre la foto satelital del campo, en una página
    que se abre con doble clic, con la escala y sus límites impresos al costado.

11. Sacar una foto desde la cámara del dron en el simulador y guardarla en disco.

**Todavía no puede**, y es lo que falta del Sprint 4: usarse desde una pantalla en vez de la
terminal, definir el lote dibujándolo en un mapa, y comparar dos fechas de satélite entre sí.

**Ya no está en el plan:** capturar imágenes durante el vuelo, detectar plagas, armar el
mosaico del lote, ni el reporte en PDF. Ver `PLANNING.md`, *Fuera de alcance*.

## Antes de cada paso: describir, después codear (pedido suyo, desde 2026-09-16)

**Antes de pasarle código, explicar brevemente qué vamos a hacer en ese paso y por qué.** Dos
o tres párrafos alcanzan: qué problema resuelve, qué decisiones tiene, qué va a mirar al
probarlo. Recién después, el código.

Esto es lo que quedó en pie de aquel esquema: entiende antes de pegar. La otra mitad —las
preguntas al final— se discontinuó el 2026-09-18 (ver la sección siguiente). Al no haber
preguntas, la explicación de antes carga con todo el peso: decir qué tiene que mirar en el
resultado y por qué, para que el paso se entienda sin interrogarlo.

## Preguntas de consolidación: discontinuadas (2026-09-18)

**Ya no hacerle preguntas al terminar cada paso.** Las pidió el 2026-09-13 y las dio de baja
el 2026-09-18 ("no me hagas mas preguntas al finalizar"). No reintroducirlas.

Lo que sigue en pie es la mitad de adelante del sandwich: describir el paso antes de tirar
código (sección de arriba). El problema que las preguntas venían a resolver —que en el
Sprint 1 recibió demasiado código ya terminado y el repo no le resultaba propio— se cubre
ahora explicando bien antes, y señalando en el resultado qué mirar y por qué.

## Mapa del entorno

| Pieza | Dónde | Notas |
|---|---|---|
| Repo | Windows: `C:\Users\Rodrigo\Escritorio\Repositorio Git\agrotello` | Desde WSL: `~/agrotello` (symlink) |
| PX4-Autopilot | Ubuntu (WSL2): `~/PX4-Autopilot` | Terminal **sin** venv |
| venv | Ubuntu: `~/venvs/agrotello` | Fuera del repo a propósito (`/mnt/c` es lento) |
| SITL | Se corre headless | Con ventana gráfica va **el doble de lento** (ver `sim/README.md`) |

El venv tiene dos ajustes que no son estándar y que hay que rehacer si se lo recrea: un
`sistema_gz.pth` en su `site-packages` con la línea `/usr/lib/python3/dist-packages` (para
ver los paquetes de Gazebo, que vienen por apt), y un
`export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` al final de `bin/activate`.

Home del SITL configurado a un lote real en Gualeguaychú: `-32.695933, -58.895342`, alt 15.

## Limitaciones de mis herramientas en este proyecto

- **No puedo escribir en `.vscode/`** — Write/Edit lo bloquean. Sí puedo vía `bash`.
- **No puedo borrar archivos** (`rm` da "Operation not permitted"). Hay que pedírselo a él,
  con `git rm`.
- **No puedo acceder al filesystem de WSL.** Cowork rechaza rutas UNC, y mapear una unidad
  (`net use Z:`) tampoco sirve porque resuelve al UNC subyacente. Por eso el repo vive en
  Windows.
- **Usar siempre `git --no-optional-locks`** para inspeccionar. Los comandos git normales
  dejan un `.git/index.lock` huérfano que no puedo borrar y le rompe los commits a él.

## Decisiones tomadas (no reabrir sin motivo)

- **PX4, no ArduPilot** — MAVSDK solo soporta PX4 oficialmente; con ArduPilot habría que
  cambiar de SDK.
- **Tello descartado (2026-09-08).** Cuesta $650.000 y es un sistema cerrado: no se le puede
  cambiar ni agregar la cámara, así que nunca podría hacer NDVI. El dinero, si se gasta, va
  hacia un build PX4 (Holybro X500 V2, ~USD 550), que acepta cualquier cámara incluida una
  NoIR de ~USD 30 para NDVI real.
- **Estrategia de datos sin hardware**: Sentinel-2 (NDVI real gratis, 10 m/px) para estrés
  hídrico; `gz_x500_mono_cam` del simulador para la plomería de visión; datasets públicos de
  UAV agrícola para entrenar el detector. Con eso los Sprints 2 y 3 no dependen de comprar
  nada.
- **Shapely** para la geometría del planificador de misiones.
- **Sin hooks de pre-commit.** El lint corre en GitHub Actions (`.github/workflows/ci.yml`).
  Los hooks locales daban fricción: commitea desde Windows/Python 3.14, desarrolla en
  Linux/Python 3.10.
- Nombres de funciones y docstrings **en español**, siguiendo `scripts/sprint0_hover.py`.

## Formato del docstring de módulo

Todo archivo de código nuevo abre con un docstring de tres bloques, en este orden. Breve:
si se vuelve largo, es que el archivo hace demasiadas cosas.

1. **Una línea sin jerga** que diga qué es el archivo, seguida de dos o tres de contexto
   igual de llanas. Tiene que entenderse sin saber de drones ni de Python.
2. **Una lista con una línea por función o clase**, en el orden en que aparecen.
3. **Un párrafo que arranca con "Técnico:"** con lo que un programador necesita saber para
   tocar el archivo: decisiones de diseño, unidades, trampas.

Ejemplo de referencia: `src/dronesw/mission/planner.py`.

## Trampas ya encontradas (no repetir)

- `bateria.remaining_percent` de MAVSDK 3.x ya viene en escala 0-100. Multiplicar por 100
  rompió el failsafe silenciosamente.
- La batería del SITL no baja del 50% salvo que se setee `SIM_BAT_MIN_PCT`.
- El build de PX4 falla (`kconfiglib not found`) si el venv está activado: usa el Python del
  sistema.
- PX4 SITL rechaza armar sin GCS conectada. Se resuelve con `param set NAV_DLL_ACT 0` y
  `param set CBRK_SUPPLY_CHK 894281`.
- Pegar bloques multilínea de Python en `apython` rompe la indentación. Para pruebas rápidas,
  líneas sueltas; para algo más largo, un script.
- VS Code tiene que abrirse en modo Remote-WSL (`WSL: Reopen Folder in WSL`), si no Pylance
  no encuentra el venv de Linux.
- **Las extensiones de VS Code se instalan aparte en WSL.** Tenerlas en Windows no sirve en
  modo Remote-WSL: hay que apretar "Install in WSL: Ubuntu-22.04" en cada una.
- **Al pegar código en el chat se pierden líneas en blanco** entre funciones, y black las
  exige (dos antes de cada `def` de nivel superior). Ya rompió el CI dos veces. Recordarle
  correr `black src scripts tests` después de pegar, hasta que el formateo al guardar
  funcione.
- **En WSL2 Gazebo renderiza por software.** Headless usa EGL, y EGL no encuentra GPU porque
  no existe `/dev/dri` (solo `/dev/dxg`). Que `glxinfo` diga "D3D12 (Intel Iris Xe)" no
  significa nada acá: ese es el camino de OpenGL normal, no el de los sensores. Y **abrir la
  ventana gráfica lo empeora a la mitad**, no lo mejora. Por eso la cámara va achicada (ver
  `sim/README.md`).
- **El venv no ve los paquetes instalados por apt.** `gz.transport13` vino de apt y vive en
  `/usr/lib/python3/dist-packages`, que el venv ignora. Resuelto con un `.pth` dentro del
  venv que agrega ese directorio; como los `.pth` se anexan al final, los paquetes del venv
  siguen teniendo prioridad.
- **Gazebo y MAVSDK piden versiones incompatibles de protobuf.** Los `_pb2.py` de Gazebo se
  generaron con un `protoc` anterior a la 3.19, y la protobuf moderna que arrastra MAVSDK
  (7.36 contra la 3.12 del sistema) se niega a cargarlos. Se resuelve con
  **`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`**, que ya está agregado al `activate` del
  venv. Tiene que estar en el entorno **antes de arrancar Python**: protobuf la lee una sola
  vez al importarse, así que ponerla dentro del script solo funciona si nada importó MAVSDK
  antes. El costo de velocidad es despreciable acá (los mensajes de MAVSDK son diminutos y lo
  pesado de una imagen es el campo de bytes, que se copia de una).
- **Los módulos de Gazebo llevan la versión en el nombre** (`gz.transport13`,
  `gz.msgs10.image_pb2`). Fijar uno a mano se rompe al actualizar: `probar_camara.py` prueba
  una lista de candidatos con `_primero()`.
- **`gz topic -e` en una tubería no muestra nada si lo matás con `timeout`**: la salida queda
  en un buffer que nunca se vacía. Usar `stdbuf -o0`, o cortar con `head` en vez de
  `timeout`.
- **El conjunto de reglas por defecto de ruff cambia entre versiones.** Pasó que el CI (con
  versiones viejas fijas) daba verde mientras su máquina (con las últimas) marcaba 8 errores.
  Resuelto declarando las reglas explícitamente en `pyproject.toml`
  (`select = ["E", "F", "I", "UP", "B", "DTZ", "RUF"]`) y fijando **ruff 0.16.7 y black
  26.5.1** en los tres lugares: `pyproject.toml`, `requirements.txt` y `ci.yml`. Si alguna vez
  se suben, subirlas en los tres a la vez.

## Cómo correr el proyecto

Tres pasos, en este orden. La primera terminal queda ocupada por el simulador: hay que
dejarla abierta y trabajar en la otra.

**1. Levantar el simulador** — [Ubuntu · PX4], sin venv:

```bash
cd ~/PX4-Autopilot
export PX4_HOME_LAT=-32.695933
export PX4_HOME_LON=-58.895342
export PX4_HOME_ALT=15
HEADLESS=1 make px4_sitl gz_x500
```

Esperar a que aparezca `Ready for takeoff!`. La terminal pasa a mostrar el prompt `pxh>`.

**2. Ajustar parámetros** — [pxh>], solo la primera vez de cada instalación (con
`param save` quedan guardados):

```
param set NAV_DLL_ACT 0
param set CBRK_SUPPLY_CHK 894281
param set SIM_BAT_MIN_PCT 10
param save
```

Los dos primeros permiten armar sin estación de control; el tercero deja que la batería
simulada baje del 50%, sin lo cual los failsafes no se pueden probar.

**3. Correr el vuelo** — [Ubuntu · proyecto], con venv:

El paquete tiene que estar instalado (una sola vez, o después de clonar de nuevo):
`pip install -e .` desde la raíz del repo. Sin eso, los scripts no encuentran `dronesw`.

```bash
source ~/venvs/agrotello/bin/activate
cd ~/agrotello
python scripts/sprint0_hover.py                      # Sprint 0: despegue, hover, aterrizaje
HOVER_SECONDS=40 python scripts/sprint0_hover.py     # dispara el failsafe de batería
python scripts/run_mission.py missions/lote_prueba.yaml --solo-plan --geojson   # solo planifica
python scripts/run_mission.py missions/lote_prueba.yaml   # planifica y vuela
```

El mapa del recorrido queda en `mapas/` y se ve arrastrándolo a geojson.io.

Antes de commitear conviene correr `black src scripts tests` y `ruff check src scripts tests`,
que es lo que valida el CI.

## Estado del proyecto

**Sprint 0 — cerrado** (lado SITL). Entorno completo, PX4 volando, `scripts/sprint0_hover.py`
con failsafe de batería verificado en vuelo.

**Sprint 1 — cerrado.** Pasos:

- 1.1 ✅ Formato de misión — `missions/lote_prueba.yaml`, lote "La Florida" de 5,24 ha
- 1.2 ✅ `flight/base.py` — `FlightController` + `SoportaMisionGps` + `SoportaVideo`
- 1.3 ✅ `flight/px4_controller.py` — implementación MAVSDK
- 1.4 ✅ `mission/planner.py` — grilla de waypoints con Shapely
- 1.5 ✅ `mission/executor.py` — orquestación con vigilancia de batería
- 1.6 ✅ `scripts/run_mission.py` — planifica y vuela con un comando; `--solo-plan` y
  exportación a GeoJSON en `mapas/`
- 1.7 ✅ Tests del planner — `tests/unit/test_planner.py`, cubre proyección, carga, cobertura,
  orientación, margen y errores
- 1.8 ✅ **Misión volada en el SITL** (2026-09-13): 22/22 waypoints sobre La Florida, retorno
  automático y desarmado. ~8 min de vuelo
- 1.9 ✅ `docs/mission_format.md` — campos, cómo elegir los valores y limitaciones actuales

**Sprint 1 cerrado.**

**Sprint 2 — NDVI satelital de La Florida.** En curso:

- 2.1 ✅ Ver el lote en Copernicus Browser. Fechas sin nubes encontradas: 18/07, 07/08, 30/08
  y 04/09 de 2026. El lote se ve todo verde, con manchas de tonos distintos (sin amarillos ni
  marrones): hay variación interna para mapear, pero el rango de NDVI va a ser angosto.
- 2.2 ✅ Decidido el acceso: **Earth Search (Element 84) + COGs en AWS**, anónimo y gratis
  (`sentinel-cogs`, RequesterPays falso), con `pystac-client` y `rasterio`. Bandas: B04 (rojo),
  B08 (NIR), ambas a 10 m, más SCL para descartar nubes. Los datos de Copernicus permiten uso
  comercial con atribución ("Copernicus Sentinel data 2026"); si algún día esto se vende,
  migrar a CDSE o Sentinel Hub sería por garantía de servicio, no por licencia. Acordado:
  el acceso a imágenes va detrás de una interfaz, como `FlightController`.
- 2.3 ✅ `scripts/buscar_escenas.py` — consulta Earth Search y lista las pasadas del satélite.
  20 pasadas entre el 01/07 y el 15/09 de 2026, 6 con menos de 20% de nube. Confirmó sus
  cuatro fechas y encontró dos que se le habían escapado: **08/07 con 0,0%** (la más limpia
  del rango) y 14/09 con 4,6%. Todas las escenas caen en el tile MGRS **21HUD**.
  **Nombres de los assets en Earth Search v1** (no son B04/B08): `red`, `nir`, `scl` son los
  que necesitamos. Ojo: cada banda aparece también con sufijo `-jp2`, que son los JPEG2000
  originales — hay que usar las versiones sin sufijo, que son los COG.
- 2.4 ✅ `src/dronesw/satelite.py` (módulo nuevo: búsqueda + lectura) y `scripts/leer_lote.py`.
  `buscar_escenas.py` quedó como CLI liviano. Lee **33 x 33 px de una escena de 120.560.400**
  (1 de cada 110.707). Dos hallazgos: el **desplazamiento da 0.0**, o sea que Element 84 ya lo
  aplicó y el NDVI se puede calcular sobre los enteros crudos; y el **SCL viene a 20 m**
  (5.490² px, recorte de 17 x 16), así que **no alinea con el NDVI de 10 m** — hay que
  remuestrearlo al leer, con vecino más cercano porque son códigos de categoría, nunca
  promediando. El SCL del 08/07 dio solo valores 4 y 5 (vegetación y suelo desnudo): confirma
  que no había nubes sobre el lote.
- 2.5 ✅ `src/dronesw/vision/indices.py` (NDVI, máscara de nubes a partir del SCL y resumen
  estadístico) y `scripts/ndvi_lote.py` (CLI con histograma de texto). `leer_banda` sumó el
  parámetro `forma` para remuestrear el SCL de 20 m a la grilla de 10 m con vecino más
  cercano. Se descartan los códigos SCL 0, 1, 2, 3, 8, 9, 10 y 11; se conservan 4
  (vegetación), 5 (suelo), 6 (agua) y 7 (sin clasificar). Trampa evitada: restar bandas
  uint16 sin convertirlas a float hace underflow silencioso donde el rojo supera al
  infrarrojo, y el NDVI sale enorme y positivo en vez de negativo.
  **Primer resultado agronómico real:** 08/07 dio NDVI medio 0,476 y 30/08 dio 0,604, las dos
  con 100% de cobertura útil — el lote creció de invierno a primavera. La escena del 30/08
  figuraba con 16,6% de nube en el catálogo y aun así el lote salió entero: confirmó en la
  práctica que el porcentaje de la escena no dice nada del lote. Las distribuciones son
  unimodales (las manchas de distinto verde son un gradiente, no dos poblaciones) y hay ~8%
  de píxeles bajos que persisten en las dos fechas: primer candidato a zona real para el 2.6.
- 2.6 ✅ `src/dronesw/vision/zonas.py` (nuevo) y `mascara_del_lote` en `satelite.py`.
  **El rectángulo que se venía leyendo era el doble del lote**: el polígono de La Florida
  mide 5,23 ha y su bounding box 10,50 ha, o sea que el 50,2% de los píxeles promediados
  hasta el 2.5 eran del campo vecino. Se rasteriza el polígono con `geometry_mask`
  (`invert=True`), contando el **centro** del píxel y no el contacto con el borde:
  `all_touched=True` daba 5,93 ha contra 5,23 reales. Medido: 523 px = **5,23 ha exactas**.
  Dos consecuencias de diseño: `leer_banda` ahora devuelve también la transformación de la
  ventana, corregida por `Affine.scale` cuando se fuerza `forma` (si no, la máscara se
  dibujaría sobre una grilla de 20 m); y `resumir` recibe `dentro=` para que la cobertura se
  calcule contra los píxeles del lote y no contra el rectángulo — sin eso un lote despejado
  informaba 48% y se autodescartaba por el umbral del 80%.
  Zonas por media ± 0,5 desvío estándar, no terciles. **Corregido durante el desarrollo:**
  yo iba a justificarlo diciendo que los desvíos no parten un lote parejo en tres y los
  terciles sí; lo probé y es falso — con distribución normal dan casi lo mismo (30/38/31).
  La ventaja real es que siguen la forma de la distribución: con dos poblaciones separadas
  la zona intermedia queda en 0% en vez de llenarse. Para el lote genuinamente uniforme está
  `UMBRAL_UNIFORME = 0.03`, que dispara un aviso. Trampa: un lote constante **no** da desvío
  cero sino ~1e-7 por redondeo en float32, y sin `DESVIO_DESPRECIABLE` caía todo en
  "vigoroso".
  **Números corregidos del lote:** 07/08 da NDVI medio 0,626 y 30/08 da 0,623 (antes,
  contaminados por el vecino, daban más bajo). Los dos con 100% de cobertura. Las dos fechas
  reparten ~32/36/32 entre flojo, normal y vigoroso: **con cortes relativos las hectáreas
  por zona no son comparables entre fechas** — siempre van a dar cerca de un tercio. Lo que
  sí va a ser comparable, y necesita el mapa del 2.7, es si la zona floja cae en el mismo
  lugar del campo las dos veces.
- 2.7 ✅ `src/dronesw/vision/mapa.py` (nuevo) y bandera `--mapa` en `ndvi_lote.py` (no un
  script aparte: habría duplicado búsqueda, lectura, recorte y NDVI). Genera en `mapas/` un
  PNG con transparencia y un HTML autocontenido que lo apila sobre la capa satelital de Esri
  con `imageOverlay` de Leaflet, con el PNG incrustado en base64 — se abre con doble clic.
  El panel lleva impresa la escala y el aviso de no comparar entre fechas: la restricción
  queda escrita en el entregable, no solo en la conversación.
  **Reproyección obligatoria:** `imageOverlay` ubica la imagen por sus esquinas en grados y
  asume que sus filas corren de este a oeste. El recorte está en UTM 21S, cuyo norte de
  cuadrícula está girado 1,02° respecto del real a esta longitud — 5,9 m de corrimiento de
  punta a punta del lote. `reproyectar_a_grados` lo endereza; la matriz pasa de 33 x 33 a
  31 x 36, que es correcto y no un error.
  Trampas de matplotlib: **`cm.get_cmap` está deprecada y desaparece en 3.11**, así que con
  `matplotlib>=3.7` el CI se rompería solo el día que salga; se usa
  `colormaps.get_cmap(PALETA)` (que además Pylance tipa bien, cosa que `colormaps[PALETA]`
  no) y el piso subió a `matplotlib>=3.9`.
  **Resultado:** el patrón espacial persiste entre el 07/08 y el 30/08. Correlación píxel a
  píxel r = 0,51; el 60% del tercio más flojo de una fecha sigue en el tercio más flojo de la
  otra, contra el 33% que daría el azar. **1,05 ha quedan flojas en las dos fechas y 1,29 ha
  vigorosas en las dos**, y las dos manchas son contiguas, no salpicadas — el ruido daría sal
  y pimienta. El 40% restante no persiste. Medido a ojo sobre los PNG (invirtiendo la paleta),
  no dentro del proyecto: **comparar dos fechas es la función que falta y el próximo candidato
  natural** después del 2.8.
- 2.8 ✅ Tests y documentación. **57 tests nuevos** (`test_indices.py`, `test_zonas.py`,
  `test_mapa.py`, `test_satelite.py`), 80 en total con los del planner, todos sin red ni
  simulador: `test_satelite.py` fabrica GeoTIFFs en UTM 21S con `tmp_path` y los lee con
  `leer_banda`, así se prueba de verdad la ventana, la corrección de `Affine.scale` al
  forzar `forma` y el recorte contra el polígono. Documentación: **`docs/ndvi.md`** nuevo
  (qué es el NDVI, de dónde salen los datos, las cuatro trampas, las dos reglas de lectura,
  las zonas, resultados de La Florida y limitaciones) y **README reescrito**, que seguía
  describiendo el Tello y diciendo "Sprint 0 completado".
  Dos hallazgos al escribir los tests: `satelite.py` usaba `*=` sobre un `Affine`, que tira
  `PendingDeprecationWarning` (corregido a `@=`; rasterio lo sigue haciendo internamente,
  eso no se puede tocar); y **el borde del recorte puede comerse hasta un píxel del lote**
  porque la ventana se redondea a píxeles enteros — medido, el error sobre 5,23 ha es del
  orden del 0,05%. Los dos errores de borde conocidos (este y el estiramiento del SCL)
  quedaron con un test que fija su magnitud, para que no crezcan sin que nos enteremos.

**Sprint 2 cerrado.**

**Sprint 3 — Captura desde el dron.** En curso:

- 3.1 ✅ `scripts/probar_camara.py` — se suscribe al tópico de la cámara con
  `gz.transport13` y guarda el primer cuadro como PNG. Fue casi todo diagnóstico: el
  simulador con cámara arrancaba a **1,5% de la velocidad real** (65× más lento). Causa: la
  cámara de PX4 es de **1280 x 960 a 30 Hz** y en WSL2 Gazebo la renderiza **por software**,
  porque headless usa EGL y EGL no encuentra GPU (no hay `/dev/dri`, solo `/dev/dxg`).
  Bajándola a 320 x 240 a 5 Hz el factor sube a **0,56**, que es usable. El modelo ajustado
  vive en `sim/mono_cam/model.sdf` con el porqué en `sim/README.md`; hay que copiarlo dentro
  de PX4 y se pierde si PX4 se actualiza.
  **Tópico de la cámara:**
  `/world/default/model/x500_mono_cam_0/link/camera_link/sensor/camera/image`, tipo
  `gz.msgs.Image`.
  Dos hipótesis mías que salieron falsas y conviene no repetir: no había ningún `gz sim`
  viejo colgado, y el simulador nunca estuvo trabado (el barómetro emitía perfecto, solo que
  lentísimo). El diagnóstico que sirvió fue medir el `real_time_factor` de
  `/world/default/stats`, no inferirlo.
**Sprint 3 cortado en el 3.1 (2026-09-20), a propósito.** Los pasos 3.2 a 3.4 construían la
cañería de captura geoetiquetada, que sirve a un dron con cámara que no existe: el mundo del
simulador no tiene cultivo y las fotos salen de un piso gris. Se retoma si algún día hay
hardware. (Si se retoma: usar `x500_mono_cam_down`, que mira al piso; la del `x500_mono_cam`
mira al frente y por eso la primera foto salió con el horizonte en el medio.)

**Sprint 4 — La aplicación. El último.** Decidido con él el 2026-09-20, y es **su** idea del
producto, no la mía: un programa con pantalla donde se ingresan los datos de conexión del
dron, se dibuja el lote sobre la imagen satelital, y desde ahí se planifica, se vuela y se
analiza. Servidor FastAPI + una página con Leaflet; nada de framework de frontend. La
pantalla escribe el mismo YAML que lee la CLI, así las dos formas conviven.

- 4.1 ⬜ El servidor — exponer por HTTP lo que ya existe, sin pantalla
- 4.2 ⬜ La pantalla — dibujar el lote y ver su NDVI sin tocar la terminal
- 4.3 ⬜ El vuelo en vivo — conexión, y ver al dron moverse sobre el mapa
- 4.4 ⬜ Comparar fechas y cierre

El roadmap viejo de nueve sprints se recortó a esto. Lo descartado está en `PLANNING.md`
sección 5, *Fuera de alcance*, con el motivo de cada descarte. **No reabrir esa lista.**

**Contexto importante sobre el recorte (2026-09-20).** Estuvo a punto de abandonar el
proyecto. Dos motivos que dio: le cuesta seguir el hilo, y **no lo siente suyo**. Sobre lo
segundo le dije, y es cierto, que es en buena medida responsabilidad mía: yo escribí el
código, hice los diagnósticos, encontré los errores y tomé las decisiones de diseño, y las
dos correcciones que habíamos intentado solo cambiaban *cómo se las contaba*, no quién
decidía. Lo que lo reenganchó fue que él definiera el producto. **Ese es el criterio de acá
en más: las decisiones de qué construir son suyas; yo aporto el cómo y las consecuencias.**
Cuando haya una bifurcación de diseño, plantearla y que elija, en vez de resolverla y
explicarla después.

**Decisiones de diseño acordadas en el Sprint 2:**

- La escala de colores del mapa se estira al rango real del lote (percentiles 2 y 98), porque
  con una escala fija 0-1 su campo sale todo del mismo verde. Contra: mapas con escala
  estirada no son comparables entre fechas — para comparar hay que fijar la escala.
- **Toda estadística del lote se informa junto con la cobertura útil** ("NDVI medio 0,61 sobre
  el 62% del lote"). Las nubes tapan zonas contiguas, así que promediar solo los píxeles
  claros sesga el resultado de forma silenciosa. Por debajo del 80% de cobertura, descartar
  la fecha.

Notas del vuelo: `SIM_BAT_DRAIN 1500` descarga mucho más lento de lo esperado (terminó en 97%),
así que ese vuelo no ejercitó el failsafe de batería — ya verificado en el Sprint 0. Las
dependencias de runtime se declaran en `pyproject.toml` (`[project] dependencies`), no en
`requirements.txt`: el CI instala con `pip install -e .` y solo lee de ahí.

**Frente de visión: sin hardware, y ya no hace falta.** Se descartó el Tello (ver Decisiones).
Los Sprints 2 y 3 se hacen con satélite, simulador y datasets públicos. Un dron PX4 real es un
objetivo de mediano plazo, no un bloqueante.

**`PLANNING.md` reescrito (2026-09-13)** sin el Tello. El roadmap se reordenó: el Sprint 2 pasó
a ser NDVI satelital del lote (resultado agronómico real, sin hardware), y la captura de
imágenes desde el simulador se corrió al Sprint 3.

**Maqueta de la interfaz final** (2026-09-13): artifact `agrotello-mockup`, con la vista de
misión en vivo y la del reporte. El recorrido que dibuja es el real, recalculado en el
navegador desde `missions/lote_prueba.yaml`. Acordado: al cerrar el Sprint 2 conviene sacarle
el panel del mapa y hacerlo andar con el NDVI real, para que cada sprint le sume algo visible
a una interfaz que ya exista, en vez de acumular meses de plomería sin recompensa.

**Nota sobre motivación:** es su primer proyecto de software de drones y la etapa de
infraestructura le resultó árida. Vale la pena priorizar entregables mirables y señalar el
avance concreto cuando lo hay.

**Pendientes menores:** los `__init__.py` siguen con `# TODO: implementar` del scaffold, y
`flight/safety.py` quedó vacío porque la lógica de failsafe terminó dentro del ejecutor
(decidir si se elimina o se le da contenido).

**Los dos errores de borde conocidos** (documentados en `docs/ndvi.md` y con un test que fija
su magnitud en `TestAlineacionDeBandas` y `TestReproyectar`):

1. **El SCL se estira ~3%.** Las ventanas de 10 m y 20 m se redondean sobre el mismo bounding
   box en grados y no cubren lo mismo (340 x 320 m contra 330 x 320). La máscara de nubes
   puede errarle por un píxel en los bordes. Se arregla leyendo el SCL con los bordes exactos
   de la ventana del rojo en vez del bbox en grados.
2. **El recorte puede comerse hasta un píxel del lote.** La ventana se redondea a píxeles
   enteros, así que el vértice más al este de La Florida queda ~2 m afuera del último píxel.
   Sobre 5,23 ha el error medido es del orden del 0,05%: acotado, no vale la pena arreglarlo
   salvo que se trabaje con lotes mucho más chicos.

El roadmap completo está en `PLANNING.md` sección 5.
