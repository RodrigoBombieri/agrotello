# NDVI satelital del lote

Cómo el proyecto averigua, sin volar nada, qué sectores de un campo andan bien y cuáles no.

## Qué es el NDVI y por qué sirve

Una hoja sana absorbe casi toda la luz roja que le llega —la usa para la fotosíntesis— y
refleja mucho infrarrojo cercano, que le rebota en la estructura interna del mesófilo.
Cuando la planta se estresa, esa estructura interna se desarma antes de que las hojas
cambien de color a simple vista. El NDVI mide ese contraste:

```
NDVI = (infrarrojo - rojo) / (infrarrojo + rojo)
```

Va de −1 a 1. Arriba de 0,6 suele ser vegetación vigorosa; alrededor de 0,2, suelo casi
pelado; negativo, agua. La ventaja práctica es que **se adelanta a lo que se ve**: el
infrarrojo cae antes que el verde.

## De dónde salen los datos

Sentinel-2 son dos satélites de la Agencia Espacial Europea que fotografían la Tierra
entera cada cinco días, con píxeles de 10 m en las bandas que nos interesan. Los datos son
gratis y permiten uso comercial con atribución (`Copernicus Sentinel data 2026`).

No se bajan del portal de Copernicus sino de **Earth Search**, el catálogo STAC de
Element 84, que indexa copias en formato COG alojadas en AWS con acceso anónimo. Dos
consecuencias buenas: no hace falta cuenta ni clave, y no hace falta descargar la escena
entera.

**COG** quiere decir *Cloud-Optimized GeoTIFF*: el archivo lleva adentro un índice que dice
en qué byte empieza cada mosaico de la imagen. Con eso, `rasterio` pide por HTTP solo el
rango de bytes del pedazo que necesita. En la práctica, para La Florida se leen **33 × 33
píxeles de una escena de 120.560.400** — uno de cada 110.707.

### Nombres de las bandas

En Earth Search v1 los assets **no** se llaman B04/B08 como en el producto original:

| Lo que necesitamos | Asset | Resolución |
|---|---|---|
| Rojo | `red` | 10 m |
| Infrarrojo cercano | `nir` | 10 m |
| Clasificación de escena | `scl` | **20 m** |

Cada banda aparece además con sufijo `-jp2`, que son los JPEG2000 originales. Hay que usar
las versiones **sin** sufijo, que son los COG: son las únicas que permiten leer por partes.

## El recorrido de los datos

```
missions/lote_prueba.yaml
        │  contorno del lote en lat/lon
        ▼
buscar_escenas()          → qué pasadas hay y con cuánta nube
        ▼
leer_banda() × 3          → recortes de rojo, infrarrojo y clasificación
        ▼
mascara_utilizable()      → descarta nubes, sombras y nieve
mascara_del_lote()        → descarta lo que está fuera del alambrado
        ▼
calcular_ndvi()           → una matriz de NDVI, con NaN en lo descartado
        ├── resumir()     → promedio, mediana, percentiles, cobertura
        ├── clasificar()  → zona floja / normal / vigorosa, en hectáreas
        └── colorear()    → PNG + página HTML sobre la foto satelital
```

## Las cuatro trampas que ya nos mordieron

**1. El recorte rectangular no es el lote.** `leer_banda` trae el rectángulo que encierra al
campo. La Florida es un rombo de 5,23 ha cuyo rectángulo mide 10,50 ha: **el 50% de esos
píxeles son del vecino**. Sin `mascara_del_lote`, todas las estadísticas están contaminadas.
La máscara cuenta el **centro** del píxel, no el contacto con el borde: un píxel que el
alambrado cruza por la mitad es mitad de cada campo.

**2. La clasificación viene a 20 m y no alinea.** Hay que remuestrearla a la grilla de 10 m
al leerla (`forma=`), **con vecino más cercano**: son códigos de categoría, y promediar nube
(9) con vegetación (4) daría 6, que significa agua. Al forzar la forma también hay que
corregir la transformación, o la máscara del lote se dibujaría sobre una grilla que no
existe.

**3. Las bandas son enteros sin signo.** Restar `uint16` donde el rojo supera al infrarrojo
hace que el resultado se dé vuelta y salga un número enorme en vez de negativo. El NDVI sale
positivo justo donde el campo está peor. No falla: miente. Por eso se convierte a float
antes de operar.

**4. El porcentaje de nube del catálogo no habla de tu lote.** Una escena cubre 110 × 110
km. El 30/08/2026 figuraba con 16,6% de nube y La Florida salió entera, con 100% de
cobertura útil. Al revés también pasa. La única medida que vale es la cobertura sobre el
lote, y por eso **toda estadística se informa junto con ella**.

## Dos reglas de lectura

**La cobertura siempre acompaña al promedio.** "NDVI medio 0,61 sobre el 62% del lote" es un
dato; "NDVI medio 0,61" a secas puede ser el promedio del pedazo despejado de un campo
tapado. Por debajo del **80% de cobertura** la fecha se descarta.

**La escala del mapa está estirada y eso lo hace incomparable.** Los colores se reparten
entre los percentiles 2 y 98 *de esa fecha*, porque con una escala fija 0–1 un cultivo
implantado sale todo del mismo verde. La contra es que "verde oscuro" significa un valor
distinto en cada mapa: dos fechas lado a lado se ven parecidas aunque no lo sean. Por eso la
página imprime su propia escala y lo advierte. **Para comparar fechas hay que fijar la
escala**, y esa función todavía no existe.

## Las zonas de vigor

Los cortes son la media del lote ± medio desvío estándar, no terciles ni umbrales absolutos.

Los umbrales absolutos (NDVI < 0,3 = flojo) no sirven en un campo implantado: todo cae en
una sola bolsa. Los terciles y los desvíos, sobre una distribución normal, reparten casi
igual (~31/38/31), así que la ventaja de los desvíos **no** es que un lote parejo quede sin
zonas. Es que los cortes siguen la forma real de la distribución: si el campo tiene dos
poblaciones separadas, la zona intermedia queda vacía y eso se ve, mientras que los terciles
la llenan igual.

Para el lote genuinamente uniforme está el aviso de `UMBRAL_UNIFORME`: por debajo de 0,03 de
desvío, las zonas están separando ruido y el programa lo dice.

**Consecuencia importante:** como los cortes son relativos a cada fecha, **las hectáreas por
zona no se comparan entre fechas** — siempre van a dar cerca de un tercio. Lo que sí
significa algo es si la zona floja cae en el mismo lugar del campo.

## Cómo correrlo

Desde la raíz del repo, con el venv activado:

```bash
# qué imágenes hay del lote en un rango de fechas
python scripts/buscar_escenas.py missions/lote_prueba.yaml --desde 2026-07-01 --hasta 2026-09-15

# los valores crudos de las bandas para una fecha
python scripts/leer_lote.py missions/lote_prueba.yaml --fecha 2026-08-30

# el NDVI, las zonas y el histograma
python scripts/ndvi_lote.py missions/lote_prueba.yaml --fecha 2026-08-30

# lo mismo, y además el mapa en mapas/
python scripts/ndvi_lote.py missions/lote_prueba.yaml --fecha 2026-08-30 --mapa
```

El mapa queda en `mapas/ndvi_AAAAMMDD.html` y se abre con doble clic: es autocontenido, con
la imagen incrustada, y trae la foto satelital de fondo.

`ndvi_lote.py` devuelve **2** si la cobertura quedó por debajo del umbral, para que se pueda
encadenar en un script sin mirar la salida.

## Resultados sobre La Florida

| Fecha | Satélite | NDVI medio | Cobertura |
|---|---|---|---|
| 08/07/2026 | — | 0,476 * | 100% |
| 07/08/2026 | S2A | 0,626 | 100% |
| 30/08/2026 | S2B | 0,623 | 100% |

\* medido antes de recortar contra el polígono: incluye el campo vecino.

El lote creció fuerte entre principios de julio y principios de agosto, y después se
planchó. Las dos fechas de agosto, tomadas por satélites distintos con 23 días de
diferencia, coinciden dentro de 0,003 — lo que da una idea de cuánto vale la calibración
entre pasadas.

El patrón espacial persiste: la correlación píxel a píxel entre el 07/08 y el 30/08 es
r ≈ 0,51, y el 60% del tercio más flojo de una fecha sigue en el tercio más flojo de la otra
(contra el 33% que daría el azar). Hay alrededor de **1 ha que queda floja en las dos
fechas**, en una mancha contigua, que es el primer candidato concreto a ir a caminar.

## Limitaciones conocidas

- **La clasificación se estira ~3%.** Las ventanas de 10 m y 20 m se redondean sobre el
  mismo rectángulo en grados y no cubren exactamente lo mismo (340 × 320 m contra
  330 × 320 m). La máscara de nubes puede errarle por un píxel en los bordes. Se arregla
  leyendo el SCL con los bordes exactos de la ventana del rojo.
- **El borde del recorte puede comerse hasta un píxel del lote.** La ventana se redondea a
  píxeles enteros, así que el extremo del campo puede quedar afuera por unos metros. Sobre
  5,23 ha el error medido es del orden del 0,05%.
- **No se comparan dos fechas.** Es la función que falta para que las zonas signifiquen algo
  en el tiempo.
- **Una nube fina no siempre la marca el SCL.** Si una fecha da un valor raro y la cobertura
  dice 100%, vale mirar la imagen antes de creerle.
