# Ajustes al simulador

Archivos que **no** viven en este repo cuando se usan: hay que copiarlos dentro de
`PX4-Autopilot`. Están acá porque una actualización de PX4 los pisa y entonces hay que
volver a aplicarlos, y porque explican una decisión que si no queda invisible.

## `mono_cam/model.sdf` — la cámara, aligerada

### El problema

El `x500_mono_cam` de PX4 trae una cámara de **1280 × 960 a 30 Hz**. Son 3,7 MB de píxeles
por cuadro, 110 MB por segundo.

En WSL2 eso es inviable. Gazebo, corriendo headless, renderiza por **EGL**, y en WSL2 EGL no
encuentra la GPU: no existe `/dev/dri`, solo `/dev/dxg`, que es la vía propia de Windows.
Resultado, cada cuadro se dibuja por software.

Medido sobre un i7-1165G7 con Iris Xe:

| Configuración | `real_time_factor` |
|---|---|
| Original, headless | **0,015** |
| Original, con ventana gráfica | 0,0075 |
| 320 × 240 a 5 Hz, headless | **0,56** |

O sea que el simulador iba **65 veces más lento que el tiempo real**: un minuto de vuelo
costaba más de una hora.

Detalle contraintuitivo: **abrir la ventana gráfica lo empeora a la mitad.** `glxinfo`
reporta D3D12 acelerado, pero ese es el camino de OpenGL normal, no el de EGL que usan los
sensores. La ventana agrega su propio renderizado sin acelerar el que importa.

### La solución

Bajar la cámara a **320 × 240 a 5 Hz**: 16 veces menos píxeles por cuadro y 6 veces menos
cuadros. El simulador pasa a 0,56 — usable.

No perdemos nada real. Estas imágenes no se usan para analizar cultivo: el mundo del
simulador no tiene cultivo. Sirven para construir la cañería de captura y geoetiquetado.
La resolución va a importar el día que haya una cámara de verdad montada en un dron de
verdad, y ese día el número sale del hardware, no de este archivo.

Se mantienen el `horizontal_fov` y la relación 4:3, así que el encuadre es idéntico.

### Cómo aplicarlo

```bash
MODELO=~/PX4-Autopilot/Tools/simulation/gz/models/mono_cam/model.sdf
cp "$MODELO" "$MODELO.bak"          # por las dudas, una sola vez
cp ~/agrotello/sim/mono_cam/model.sdf "$MODELO"
grep -E "<width>|<height>|<update_rate>" "$MODELO"
```

Tiene que decir 320, 240 y 5. Después hay que reiniciar el simulador.

### Si hiciera falta más velocidad

El `x500_mono_cam` arrastra también un sensor de flujo óptico de 100 × 100 a 50 Hz y dos
lidar, que también renderizan. Sacándoselos al modelo se gana bastante más. No se hizo
porque con 0,56 alcanza y porque implica operar más modelos de PX4.
