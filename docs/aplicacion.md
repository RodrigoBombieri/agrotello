# La aplicación

Un programa con pantalla para planificar un relevamiento sobre un lote, volarlo y analizar
el cultivo. Se levanta local y se usa desde el navegador.

```bash
python scripts/servidor.py
```

Y se abre **http://127.0.0.1:8000**. Escucha solo en `127.0.0.1`: no queda expuesta a la red.

## La pantalla

Un panel fijo a la izquierda y el mapa satelital ocupando el resto. El panel va de arriba
hacia abajo en el orden en que se usa: definir el lote, planificarlo, volarlo, analizarlo.

### Definir el lote

**Dibujar** deja marcar el contorno sobre la foto: un clic por vértice, doble clic para
cerrar. Después queda editable — se arrastran los vértices para corregirlo, y los puntos
intermedios para agregar uno nuevo. Dibujar a ojo sobre una imagen nunca sale bien a la
primera.

**Guardar lote** lo escribe en `missions/` como un YAML. Es **el mismo formato que lee la
línea de comandos**, así que las dos formas de usar el proyecto comparten los lotes: lo que
dibujás acá lo podés volar con `run_mission.py`, y al revés.

El desplegable de arriba lista lo que haya guardado.

### Volar

Los parámetros de vuelo —altura, separación entre pasadas, velocidad, ángulo, margen del
alambrado— son los que definen el recorrido. **Planificar recorrido** dibuja el zigzag en
amarillo y dice cuántos waypoints, cuántos kilómetros y cuánto va a tardar.

**La conexión del dron** es una cadena de texto que MAVSDK interpreta:

| Para | Cadena |
|---|---|
| El simulador | `udpin://0.0.0.0:14540` |
| Una radio por USB | `serial:///dev/ttyUSB0:57600` |
| Un enlace por red | `udp://IP:PUERTO` |

**Volar la misión** no despega: abre una confirmación con lo que está por pasar —waypoints,
altura, recorrido, a dónde se conecta— y recién **Confirmar despegue** arma los motores.
Esa fricción está puesta a propósito.

Durante el vuelo el panel muestra el estado, el waypoint, la batería y la altura, y el mapa
dibuja el rastro **en azul**, que es a propósito distinto del amarillo del plan: lo que
interesa mirar es dónde se separan.

**Abortar y volver** interrumpe la misión y manda el dron al punto de despegue, donde
aterriza. El color es el que avisa: **rojo solo en los dos botones que arrancan o cortan
motores**, para que en una emergencia no haya que leer.

### Analizar

**Buscar fechas** consulta el catálogo de Sentinel-2 y lista las pasadas del satélite con
su porcentaje de nube — que es de la escena entera de 110 × 110 km, no del lote; ver
`ndvi.md`. **Analizar** trae la fecha elegida y pinta el NDVI sobre el campo.

Las dos barras debajo de la escala de colores **recolorean el mapa al instante**, sin
volver a pedirle nada al servidor: el servidor manda los valores crudos y el navegador los
pinta. Y pasando el mouse por encima del lote se lee el NDVI del píxel que se apunta.

### Comparar dos fechas

Con dos fechas elegidas, **Comparar las dos fechas** cruza las dos mediciones y marca solo
lo que coincide: rojo donde el lote sale flojo **en las dos**, verde donde sale vigoroso en
las dos, gris donde no se ponen de acuerdo.

Al lado del resultado aparece siempre **cuánta superficie daría el azar**. Es la vara: si
las dos fechas no tuvieran nada que ver, coincidiría un tercio de un tercio, o sea el 11%
del lote. Un resultado cerca de ese número no significa nada; el doble o más, sí.

Ver `ndvi.md` para por qué este cruce no depende del nivel general del cultivo.

## Por dentro

Un servidor FastAPI sirve la página y expone las operaciones; la página es HTML con Leaflet
y sin ningún framework. **El servidor no calcula nada propio**: llama a los mismos módulos
que usa la línea de comandos y traduce lo que devuelven.

```
POST /api/plan       polígono + parámetros → waypoints, distancia, duración
POST /api/escenas    polígono + fechas     → pasadas del satélite con su nube
POST /api/ndvi       polígono + fecha      → grilla de NDVI, zonas, estadísticas
POST /api/comparar   polígono + 2 fechas   → mapa de lo que se repite
POST /api/vuelo      lote + conexión       → arranca la misión
POST /api/vuelo/abortar                    → vuelve al punto de despegue
WS   /api/vuelo/estado                     → posición, batería y waypoint en vivo
GET  /api/lotes      · POST /api/lotes     → los YAML de missions/
```

Todas se pueden probar a mano, apretando botones, en **http://127.0.0.1:8000/docs**: cada
una viene con el cuerpo precargado con el lote de ejemplo.

### Decisiones que conviene conocer antes de tocar

**El NDVI viaja como números y no como imagen.** El servidor manda la grilla de valores
(unos 6 KB para un lote de 5 ha) y el navegador la colorea. Cuesta tener la paleta escrita
dos veces —en Python para la línea de comandos, en JavaScript para la pantalla— y a cambio
la escala se mueve sin ida y vuelta, y se puede leer el valor de cada píxel.

**La comparación, en cambio, se calcula en Python.** No es interactiva: se calcula una vez
y se mira. Hacerla en el navegador la habría dejado sin tests.

**Hay una sola sesión de vuelo por servidor.** Dos misiones a la vez sobre el mismo dron no
tienen sentido; el segundo intento falla con un error explícito en vez de pasar
silenciosamente.

**El ejecutor de misiones no sabe que existe una pantalla.** Recibe un aviso opcional que
llama en cada hito del vuelo; la línea de comandos no se lo pasa y funciona igual.

## Límites

- **Listo para conectarse a un dron real, pero sin probar en uno.** El protocolo es el
  mismo y solo cambia la cadena de conexión, pero el simulador no ejercita viento, calidad
  de GPS, latencia de la radio ni geofence.
- **Sin autenticación.** Escucha solo en `127.0.0.1`, que es lo que la protege. Exponerla a
  una red sin agregar autenticación sería dejar que cualquiera arme motores.
- **Un solo usuario.** El estado del vuelo vive en memoria del proceso: si se reinicia el
  servidor en pleno vuelo, se pierde el seguimiento (el dron sigue volando, con su propio
  failsafe).
