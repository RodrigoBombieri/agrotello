"""Saca una foto desde la cámara del simulador y la guarda en disco.

Es la prueba de que se puede llegar a las imágenes del dron desde Python. Se conecta al
simulador, espera a que la cámara mande un cuadro, y lo escribe como PNG. No vuela nada ni
analiza nada: solo confirma que la cañería existe.

- `_tipo_imagen`: encuentra el módulo de mensajes de Gazebo, que cambia de nombre según la versión.
- `esperar_frame`: se suscribe al tópico de la cámara y devuelve el primer cuadro que llegue.
- `a_imagen`: convierte el mensaje crudo de Gazebo en una imagen guardable.
- `main`: encadena la espera, la conversión y el guardado.
- `_primero`: importa el primero de varios módulos candidatos, porque el nombre lleva la versión.
- `_gazebo`: devuelve las clases de Gazebo con protobuf ya puesto en modo compatible.
- `esperar_frame`: se suscribe al tópico de la cámara y devuelve el primer cuadro que llegue.
- `a_imagen`: convierte el mensaje crudo de Gazebo en una imagen guardable.
- `main`: encadena la espera, la conversión y el guardado.

Técnico: Gazebo entrega los cuadros por `gz-transport`, invocando un callback en un hilo
propio; por eso la espera se hace con un `Event` y no con un bucle de sondeo. La cantidad de
canales se deduce de `step / width` en vez de asumir RGB, así el código sobrevive a que la
cámara cambie de formato. El tópico por defecto es el del `x500_mono_cam`; si se usa otro
modelo, el nombre cambia y se pasa por `--topico`. Para que esto funcione el simulador tiene
que estar corriendo: sin publicador, la suscripción no falla, simplemente nunca llega nada.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import threading
from pathlib import Path

import numpy as np
from PIL import Image as ImagenPil

TOPICO = "/world/default/model/x500_mono_cam_0/link/camera_link/sensor/camera/image"
ESPERA_S = 30.0

MODULOS_DE_MENSAJES = ("gz.msgs10.image_pb2", "gz.msgs.image_pb2", "gz.msgs9.image_pb2")
MODULOS_DE_TRANSPORTE = (
    "gz.transport13",
    "gz.transport14",
    "gz.transport12",
    "gz.transport11",
    "gz.transport",
)


def _primero(modulos: tuple[str, ...], atributo: str):
    """Importa el primero de `modulos` que exista y devuelve el atributo pedido.

    Los paquetes de Gazebo llevan el número de versión en el nombre y cambia entre
    releases, así que se prueban los conocidos en vez de fijar uno solo.
    """
    for modulo in modulos:
        try:
            return getattr(importlib.import_module(modulo), atributo)
        except (ImportError, AttributeError):
            continue
    raise SystemExit(
        f"No encontré `{atributo}` en ninguno de: "
        + ", ".join(modulos)
        + "\nFijate qué hay instalado con:  dpkg -l | grep python3-gz"
    )


def _gazebo() -> tuple[type, type]:
    """Devuelve las clases `Node` e `Image` de Gazebo, listas para usar.

    Los imports son perezosos por un tema de orden. Los `_pb2.py` de Gazebo se generaron con
    un protoc viejo, y la protobuf moderna que arrastra MAVSDK se niega a cargarlos; la
    variable de entorno la obliga a usar su implementación en Python puro, que sí los acepta.
    Protobuf lee esa variable una sola vez, al importarse, así que tiene que estar puesta
    antes — y con los imports arriba del archivo, ya sería tarde.

    Igual esto es solo una red: lo que corresponde es tenerla en el entorno, porque si el
    programa importa MAVSDK primero, acá ya no hay nada que hacer.
    """
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    return _primero(MODULOS_DE_TRANSPORTE, "Node"), _primero(MODULOS_DE_MENSAJES, "Image")


def esperar_frame(topico: str, espera_s: float = ESPERA_S):
    """Se suscribe a la cámara y devuelve el primer cuadro, o None si no llega ninguno.

    El callback lo dispara `gz-transport` en un hilo propio, así que el cuadro se guarda en
    una lista y se avisa con un `Event`. Suscribirse a un tópico sin publicador no da error:
    por eso hace falta el plazo máximo, o el programa esperaría para siempre.
    """
    Nodo, tipo = _gazebo()
    recibido: list = []
    listo = threading.Event()

    def al_llegar(mensaje) -> None:
        if not listo.is_set():
            recibido.append(mensaje)
            listo.set()

    nodo = Nodo()
    if not nodo.subscribe(tipo, topico, al_llegar):
        raise SystemExit(f"No me pude suscribir a {topico}")

    print(f"Esperando un cuadro de {topico} (hasta {espera_s:.0f} s)...")
    listo.wait(timeout=espera_s)
    return recibido[0] if recibido else None


def a_imagen(mensaje) -> ImagenPil.Image:
    """Convierte el mensaje de Gazebo en una imagen, deduciendo el formato de los bytes."""
    canales = mensaje.step // mensaje.width
    if canales not in (1, 3, 4):
        raise ValueError(f"Formato inesperado: {canales} bytes por píxel")

    datos = np.frombuffer(mensaje.data, dtype=np.uint8)
    esperados = mensaje.height * mensaje.step
    if datos.size != esperados:
        raise ValueError(f"Llegaron {datos.size} bytes y esperaba {esperados}")

    matriz = datos.reshape(mensaje.height, mensaje.width, canales)
    return ImagenPil.fromarray(matriz.squeeze() if canales == 1 else matriz)


def main() -> int:
    p = argparse.ArgumentParser(description="Guarda un cuadro de la cámara del simulador.")
    p.add_argument("--topico", default=TOPICO, help="Tópico de Gazebo de la cámara")
    p.add_argument("--salida", type=Path, default=Path("capturas/prueba.png"))
    p.add_argument("--espera", type=float, default=ESPERA_S, help="Segundos a esperar")
    args = p.parse_args()

    mensaje = esperar_frame(args.topico, args.espera)
    if mensaje is None:
        print("\nNo llegó ningún cuadro. ¿Está corriendo el simulador con el modelo de cámara?")
        return 1

    imagen = a_imagen(mensaje)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(args.salida)

    print(f"\n  {imagen.width} x {imagen.height} px, {imagen.mode}")
    print(f"  guardada en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
