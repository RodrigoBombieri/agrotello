# Notas para Claude

Contexto que se pierde entre sesiones. Leer esto primero al retomar el proyecto.

## Cómo trabaja Rodrigo

- **El código va en el chat, no directo al repo.** Él lo copia, analiza y lo pega en sus archivos.
  Escribir archivos directamente solo si lo pide explícitamente. Los documentos (`docs/`,
  `PLANNING.md`, este archivo) sí se escriben directo.
- **Etiquetar siempre la terminal** antes de cada bloque de comandos. Para no confundir entre los
  cinco contextos. Las etiquetas están definidas en `docs/comandos.md`:
  `[Git Bash]`, `[Ubuntu · PX4]`, `[Ubuntu · proyecto]`, `[pxh>]`, `[apython]`.
- **Los commits los hace desde Git Bash en Windows**, nunca desde WSL (las credenciales de
  GitHub funcionan de ese lado). Ruta: `~/Escritorio/Repositorio\ Git/agrotello`.
- Responder en español, conciso y directo.
- Va paso a paso y pide confirmación entre pasos. No adelantarse varios pasos de una.

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

**Todavía no puede:** separar el lote en zonas ni dibujar el mapa, ni hacer nada con imágenes
tomadas desde el dron, ni generar reportes.

## Antes de cada paso: describir, después codear (pedido suyo, desde 2026-09-16)

**Antes de pasarle código, explicar brevemente qué vamos a hacer en ese paso y por qué.** Dos
o tres párrafos alcanzan: qué problema resuelve, qué decisiones tiene, qué va a mirar al
probarlo. Recién después, el código.

Junto con las preguntas de consolidación del final, esto arma el sandwich: entiende antes de
pegar, y verifica después de correr.

## Preguntas de consolidación (pedido suyo, desde 2026-09-13)

**Al terminar cada paso, antes de pasar al siguiente, hacerle dos o tres preguntas sobre lo
que se acaba de construir.** No es opcional ni se saltea porque el paso salió bien.

Cómo tienen que ser:

- Sobre el **por qué**, no sobre el qué. "¿Por qué rotamos el lote en vez de generar líneas
  inclinadas?" sirve. "¿Qué hace `_cortar_pasada`?" no: eso lo lee en el código.
- Al menos una del tipo **"¿qué se rompería si...?"**. Son las que revelan si el modelo mental
  es real o si solo quedó la forma.
- **No son un examen.** Si contesta "no sé", eso es información valiosa: significa que hay que
  volver a explicar o simplificar ese código, no seguir de largo.

El motivo: durante el Sprint 1 le entregué demasiado código ya terminado —archivos de 180
líneas con asyncio concurrente incluido— y quedó con un repo que funciona pero que no siente
suyo. Esto existe para corregir eso.

## Mapa del entorno

| Pieza | Dónde | Notas |
|---|---|---|
| Repo | Windows: `C:\Users\Rodrigo\Escritorio\Repositorio Git\agrotello` | Desde WSL: `~/agrotello` (symlink) |
| PX4-Autopilot | Ubuntu (WSL2): `~/PX4-Autopilot` | Terminal **sin** venv |
| venv | Ubuntu: `~/venvs/agrotello` | Fuera del repo a propósito (`/mnt/c` es lento) |
| SITL | Se corre headless | La GUI de Gazebo se cuelga en su WSL |

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

**Sprint 1 — en curso.** Pasos:

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
- 2.6 ⬜ Recortar al polígono y clasificar zonas
- 2.7 ⬜ Generar el mapa
- 2.8 ⬜ Tests y documentación

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

El roadmap completo está en `PLANNING.md` sección 5.
