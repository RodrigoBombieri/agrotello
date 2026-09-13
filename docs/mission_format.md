# Formato de misión

Una misión es un archivo de texto que describe **qué lote relevar y cómo volarlo**. El
planificador lo lee y calcula el recorrido en zigzag que cubre el campo.

Los archivos viven en `missions/`, uno por lote.

## Ejemplo completo

```yaml
nombre: "La Florida"
descripcion: "Lote de prueba para la misión de vuelo autónomo."

poligono:
  - lat: -32.69586457654833
    lon: -58.893566719996926
  - lat: -32.69448276232639
    lon: -58.89525380397006
  - lat: -32.69602401527439
    lon: -58.897067193695214
  - lat: -32.6973678446678
    lon: -58.895479349956126

vuelo:
  altura_m: 80
  separacion_m: 30
  velocidad_ms: 8
  angulo_grados: 0
  margen_m: 2
```

## Campos

| Campo | Obligatorio | Por defecto | Qué hace |
|---|---|---|---|
| `nombre` | no | el nombre del archivo | Identifica el lote en los logs, los mapas y los reportes |
| `descripcion` | no | vacío | Texto libre, para referencia humana |
| `poligono` | **sí** | — | Vértices del lote, en grados decimales. Mínimo 3 |
| `vuelo.altura_m` | **sí** | — | Altura de vuelo sobre el punto de despegue |
| `vuelo.separacion_m` | **sí** | — | Distancia entre pasadas paralelas |
| `vuelo.velocidad_ms` | no | 5 | Velocidad de crucero |
| `vuelo.angulo_grados` | no | 0 | Orientación de las pasadas |
| `vuelo.margen_m` | no | 0 | Cuánto retirarse del borde hacia adentro |

### El polígono

Los vértices se escriben **en orden, recorriendo el borde** del lote: cada par consecutivo
forma un lado. Si se listan salteados, los lados se cruzan y el planificador rechaza la
misión con un error explícito.

Para obtener las coordenadas, en Google Maps se hace clic derecho sobre cada esquina del
campo y se copia el par que aparece. El primer número es la latitud, el segundo la longitud.

### La orientación

`angulo_grados` se interpreta como un **rumbo: en sentido horario desde el norte**.

| Valor | Pasadas |
|---|---|
| 0 | norte-sur |
| 45 | noreste-suroeste |
| 90 | este-oeste |

Conviene alinear las pasadas con el lado largo del lote: menos giros, menos tiempo perdido.
En campos con surcos marcados, seguir la dirección de siembra también reduce el efecto de
las sombras entre líneas.

### La altura

Define cuánto terreno entra en cada imagen y con cuánto detalle. Más alto cubre más rápido
pero se ve menos: para zonificar vigor alcanza, para distinguir una hoja enferma no.

### La separación

Determina cuántas pasadas salen y, por lo tanto, cuánto dura el vuelo. Debería derivarse del
ancho que ve la cámara a la altura elegida, menos el solapamiento deseado — pero **hoy es un
número directo**: altura y separación se escriben por separado y nada verifica que sean
coherentes entre sí. Cuando se caracterice la cámara, el planificador va a poder calcularla.

### El margen

Retira el recorrido del alambrado. Es una decisión de seguridad con un costo: en un lote de
220 m de lado, un margen de 10 m deja sin relevar el 17% del área — y los bordes suelen ser
justo donde primero aparecen malezas y plagas que entran desde afuera.

## Verificar antes de volar

Conviene revisar el plan sin conectarse al dron:

```bash
python scripts/run_mission.py missions/lote_prueba.yaml --solo-plan --geojson
```

Eso imprime el resumen (cantidad de pasadas, recorrido, duración estimada) y guarda el
recorrido en `mapas/`. Arrastrando ese archivo a [geojson.io](https://geojson.io) se ve
dibujado sobre el mapa satelital, que es la forma más rápida de confirmar que el zigzag cae
sobre el campo correcto y lo cubre entero.

## Limitaciones actuales

- **El polígono no puede tener agujeros.** Una laguna o un galpón en el medio del lote se
  sobrevuela igual.
- **Si el margen parte el lote en dos**, por ejemplo en un campo con forma de reloj de arena,
  se releva solo la parte más grande y se avisa por log.
- **La altura es la misma para toda la misión.** No hay pasadas de reconocimiento y detalle.
- **Altura y separación son independientes**, como se explicó arriba.
