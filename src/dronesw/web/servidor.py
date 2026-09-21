"""Expone por HTTP todo lo que el proyecto sabe hacer, para que lo use una pantalla.

Hasta acá el sistema se manejaba por línea de comandos. Este archivo pone lo mismo detrás
de direcciones web: pedirle el recorrido de un lote, preguntarle qué fotos de satélite hay,
o pedirle el análisis de una fecha. No calcula nada nuevo — llama a los módulos que ya
existen y traduce lo que devuelven.

- `ParametrosVueloEntrada` y `LoteEntrada`: lo que llega desde afuera, ya validado.
- `ConsultaEscenas` y `ConsultaNdvi`: un lote más la fecha o el rango que se consulta.
- `_ruta_de`: traduce el nombre de un lote a un archivo, rechazando nombres tramposos.
- `_grilla`: pasa la matriz de NDVI a listas, cambiando los huecos por `null`.
- `_a_dict`: devuelve un lote en la misma forma en que se recibe.
- `listar_lotes`, `leer_lote`, `guardar_lote`: los lotes guardados en `missions/`.
- `planificar_recorrido`: el zigzag que cubre un lote, con su largo y su duración.
- `buscar_fechas`: qué pasadas del satélite hay y con cuánta nube.
- `analizar`: el NDVI de una fecha, con sus zonas y la grilla de valores.
- `volar`, `abortar_vuelo` y `seguir_vuelo`: lanzar la misión, cortarla, y seguirla en vivo.

Técnico: las entradas se validan con Pydantic y las salidas son diccionarios comunes; la
validación importa donde el dato viene de afuera, no donde lo produce este código. El NDVI
viaja como números y no como imagen, así el navegador puede recolorearlo sin volver a
preguntar — y como **JSON no admite NaN**, los píxeles sin dato se mandan como `null`. La
grilla va reproyectada a grados, porque los mapas web ubican las imágenes por sus esquinas
en latitud y longitud. Todo responde de forma sincrónica: el análisis tarda segundos, no
minutos, y un trabajo en segundo plano sería maquinaria sin beneficio. Las rutas relativas
(`missions/`) son las mismas que usa la línea de comandos: el servidor se corre desde la
raíz del repo.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import numpy as np
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dronesw.mission.planner import (
    DefinicionMision,
    ParametrosVuelo,
    cargar_mision,
    distancia_recorrido,
    planificar,
)
from dronesw.satelite import (
    BANDA_CLASIFICACION,
    BANDA_INFRARROJO,
    BANDA_ROJO,
    buscar_escenas,
    leer_banda,
    mascara_del_lote,
    reproyectar_a_grados,
)
from dronesw.vision.indices import calcular_ndvi, mascara_utilizable, resumir
from dronesw.vision.zonas import clasificar
from dronesw.web.vuelo import INTERVALO_POSICION_S, SesionDeVuelo

ESTATICO = Path(__file__).parent / "estatico"
MISIONES = Path("missions")
DIRECCION_SIMULADOR = "udpin://0.0.0.0:14540"
NOMBRE_VALIDO = re.compile(r"[\w-]{1,64}")

# La Florida, el lote real del proyecto. Sirve de ejemplo en la página de documentación.
EJEMPLO_LOTE = {
    "nombre": "La Florida",
    "descripcion": "Lote de prueba para la misión de vuelo autónomo.",
    "poligono": [
        [-32.69586457654833, -58.893566719996926],
        [-32.69448276232639, -58.89525380397006],
        [-32.69602401527439, -58.897067193695214],
        [-32.6973678446678, -58.895479349956126],
    ],
    "vuelo": {
        "altura_m": 80.0,
        "separacion_m": 30.0,
        "velocidad_ms": 8.0,
        "angulo_grados": 0.0,
        "margen_m": 2.0,
    },
}

app = FastAPI(
    title="AgroTello",
    description="Planificar, volar y analizar un lote.",
    version="0.1.0",
)


# --- Lo que llega desde afuera ---------------------------------------------


class ParametrosVueloEntrada(BaseModel):
    """Cómo quiere volarse el lote. Los valores por defecto son los de La Florida."""

    altura_m: float = Field(default=80.0, gt=0)
    separacion_m: float = Field(default=30.0, gt=0)
    velocidad_ms: float = Field(default=8.0, gt=0)
    angulo_grados: float = 0.0
    margen_m: float = Field(default=2.0, ge=0)


class LoteEntrada(BaseModel):
    """Un lote: su contorno en grados y cómo quiere volarse."""

    model_config = {"json_schema_extra": {"examples": [EJEMPLO_LOTE]}}

    nombre: str = "lote"
    descripcion: str = ""
    poligono: list[tuple[float, float]] = Field(..., min_length=3)
    vuelo: ParametrosVueloEntrada = ParametrosVueloEntrada()

    def a_mision(self) -> DefinicionMision:
        """Traduce la entrada al tipo que usa el resto del proyecto."""
        return DefinicionMision(
            nombre=self.nombre,
            descripcion=self.descripcion,
            poligono=tuple(self.poligono),
            vuelo=ParametrosVuelo(**self.vuelo.model_dump()),
        )


class ConsultaVuelo(BaseModel):
    """Un lote ya planificable, más a dónde conectarse y con cuánta batería no despegar."""

    model_config = {
        "json_schema_extra": {
            "examples": [{"lote": EJEMPLO_LOTE, "direccion": DIRECCION_SIMULADOR}]
        }
    }

    lote: LoteEntrada
    direccion: str = DIRECCION_SIMULADOR
    bateria_minima_pct: float = Field(default=20.0, ge=0, le=100)


class ConsultaEscenas(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [{"lote": EJEMPLO_LOTE, "desde": "2026-07-01", "hasta": "2026-09-15"}]
        }
    }

    lote: LoteEntrada
    desde: str
    hasta: str


class ConsultaNdvi(BaseModel):
    model_config = {
        "json_schema_extra": {"examples": [{"lote": EJEMPLO_LOTE, "fecha": "2026-08-30"}]}
    }

    lote: LoteEntrada
    fecha: str


# --- Ayudantes --------------------------------------------------------------


def _ruta_de(nombre: str) -> Path:
    """Archivo de un lote, rechazando nombres que se escapen de la carpeta.

    Sin este control, un nombre como `../../algo` dejaría leer o escribir cualquier archivo
    de la máquina: el servidor recibe ese texto de afuera y lo pegaría a una ruta.
    """
    if not NOMBRE_VALIDO.fullmatch(nombre):
        raise HTTPException(400, f"Nombre de lote inválido: {nombre!r}")
    return MISIONES / f"{nombre}.yaml"


def _grilla(valores: np.ndarray) -> list[list[float | None]]:
    """Pasa la matriz de NDVI a listas anidadas, con `null` donde no hay dato.

    JSON no tiene forma de escribir NaN: la especificación directamente no lo contempla. Si
    se mandara igual, el navegador fallaría al interpretar la respuesta.

    El redondeo se hace sobre el float de Python y no sobre el arreglo: `np.round` sobre
    `float32` deja el número redondeado en esa precisión, y al pasarlo a JSON reaparece la
    cola larga (0.4909999966621399 en vez de 0.491).
    """
    return [[None if np.isnan(v) else round(float(v), 3) for v in fila] for fila in valores]


def _a_dict(mision: DefinicionMision) -> dict:
    """Devuelve un lote en la misma forma en que se recibe."""
    return {
        "nombre": mision.nombre,
        "descripcion": mision.descripcion,
        "poligono": [list(v) for v in mision.poligono],
        "vuelo": {
            "altura_m": mision.vuelo.altura_m,
            "separacion_m": mision.vuelo.separacion_m,
            "velocidad_ms": mision.vuelo.velocidad_ms,
            "angulo_grados": mision.vuelo.angulo_grados,
            "margen_m": mision.vuelo.margen_m,
        },
    }


# --- Los lotes guardados ----------------------------------------------------


@app.get("/api/lotes", summary="Los lotes guardados en missions/")
def listar_lotes() -> list[dict]:
    if not MISIONES.is_dir():
        return []
    nombres = sorted(p.stem for p in MISIONES.glob("*.yaml"))
    return [{"archivo": n, **_a_dict(cargar_mision(MISIONES / f"{n}.yaml"))} for n in nombres]


@app.get("/api/lotes/{nombre}", summary="Un lote guardado")
def leer_lote(nombre: str) -> dict:
    ruta = _ruta_de(nombre)
    if not ruta.is_file():
        raise HTTPException(404, f"No existe el lote {nombre!r}")
    return _a_dict(cargar_mision(ruta))


@app.post("/api/lotes", summary="Guardar un lote como YAML")
def guardar_lote(lote: LoteEntrada) -> dict:
    """Escribe el mismo formato que lee la línea de comandos: los dos usan los mismos lotes."""
    ruta = _ruta_de(lote.nombre)
    MISIONES.mkdir(parents=True, exist_ok=True)
    contenido = {
        "poligono": [{"lat": lat, "lon": lon} for lat, lon in lote.poligono],
        "vuelo": lote.vuelo.model_dump(),
        "nombre": lote.nombre,
        "descripcion": lote.descripcion,
    }
    ruta.write_text(yaml.safe_dump(contenido, allow_unicode=True, sort_keys=False), "utf-8")
    return {"archivo": ruta.stem, "guardado": True}


# --- Vuelo ------------------------------------------------------------------


@app.post("/api/plan", summary="El recorrido en zigzag que cubre el lote")
def planificar_recorrido(lote: LoteEntrada) -> dict:
    mision = lote.a_mision()
    try:
        waypoints = planificar(mision)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    metros = distancia_recorrido(waypoints)
    return {
        "waypoints": [{"lat": w.lat, "lon": w.lon, "altura_m": w.altura_m} for w in waypoints],
        "cantidad": len(waypoints),
        "distancia_m": round(metros, 1),
        "duracion_s": round(metros / mision.vuelo.velocidad_ms),
    }


# --- Satélite ---------------------------------------------------------------


@app.post("/api/escenas", summary="Qué pasadas del satélite hay sobre el lote")
def buscar_fechas(consulta: ConsultaEscenas) -> list[dict]:
    escenas = buscar_escenas(consulta.lote.a_mision(), consulta.desde, consulta.hasta)
    return [
        {
            "fecha": e.datetime.strftime("%Y-%m-%d"),
            "id": e.id,
            "nube_pct": round(e.properties.get("eo:cloud_cover", 0.0), 1),
        }
        for e in escenas
        if e.datetime is not None
    ]


@app.post("/api/ndvi", summary="El NDVI del lote en una fecha, con sus zonas")
def analizar(consulta: ConsultaNdvi) -> dict:
    mision = consulta.lote.a_mision()
    escenas = buscar_escenas(mision, consulta.fecha, consulta.fecha)
    if not escenas:
        raise HTTPException(404, f"No hay ninguna escena del {consulta.fecha} sobre el lote")

    escena = escenas[0]
    rojo, info = leer_banda(escena.assets[BANDA_ROJO].href, mision)
    infrarrojo, _ = leer_banda(escena.assets[BANDA_INFRARROJO].href, mision)
    clasificacion, _ = leer_banda(escena.assets[BANDA_CLASIFICACION].href, mision, forma=rojo.shape)

    dentro = mascara_del_lote(mision, info["crs"], info["transformacion"], rojo.shape)
    ndvi = calcular_ndvi(rojo, infrarrojo, mascara=mascara_utilizable(clasificacion) & dentro)
    resumen = resumir(ndvi, dentro=dentro)
    zonificacion = clasificar(ndvi)

    grados, bordes = reproyectar_a_grados(ndvi, info["crs"], info["transformacion"])
    oeste, sur, este, norte = bordes

    return {
        "fecha": escena.datetime.strftime("%Y-%m-%d") if escena.datetime else consulta.fecha,
        "escena": escena.id,
        "bordes": {"oeste": oeste, "sur": sur, "este": este, "norte": norte},
        "valores": _grilla(grados),
        "resumen": {
            "medio": round(resumen.medio, 3),
            "mediana": round(resumen.mediana, 3),
            "minimo": round(resumen.minimo, 3),
            "maximo": round(resumen.maximo, 3),
            "p2": round(resumen.p2, 3),
            "p98": round(resumen.p98, 3),
            "cobertura_pct": round(resumen.cobertura_pct, 1),
            "pixeles_utiles": resumen.pixeles_utiles,
            "pixeles_totales": resumen.pixeles_totales,
        },
        "hectareas": round(zonificacion.hectareas, 2),
        "uniforme": zonificacion.uniforme,
        "cortes": {
            "bajo": round(zonificacion.corte_bajo, 3),
            "alto": round(zonificacion.corte_alto, 3),
        },
        "zonas": [
            {
                "nombre": z.nombre,
                "hectareas": round(z.hectareas, 2),
                "porcentaje": round(zonificacion.porcentaje(z), 1),
                "ndvi_medio": None if np.isnan(z.ndvi_medio) else round(z.ndvi_medio, 3),
            }
            for z in zonificacion.zonas
        ],
    }


# --- Vuelo ------------------------------------------------------------------
#
# Hay una sola sesión por servidor: dos misiones a la vez sobre el mismo dron no tienen
# sentido, y que el segundo intento falle con un error claro es mejor que dejarlo pasar.

SESION = SesionDeVuelo()


@app.post("/api/vuelo", summary="Planificar y volar el lote")
async def volar(consulta: ConsultaVuelo) -> dict:
    mision = consulta.lote.a_mision()
    try:
        waypoints = planificar(mision)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    try:
        await SESION.iniciar(
            consulta.direccion,
            waypoints,
            mision.vuelo.velocidad_ms,
            consulta.bateria_minima_pct,
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(409, str(error)) from error
    return SESION.estado()


@app.post("/api/vuelo/abortar", summary="Volver al punto de despegue")
async def abortar_vuelo() -> dict:
    try:
        await SESION.abortar()
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from error
    return SESION.estado()


@app.websocket("/api/vuelo/estado")
async def seguir_vuelo(conexion: WebSocket) -> None:
    """Manda el estado del vuelo dos veces por segundo mientras el navegador escuche."""
    await conexion.accept()
    try:
        while True:
            await conexion.send_json(SESION.estado())
            await asyncio.sleep(INTERVALO_POSICION_S)
    except WebSocketDisconnect:
        pass


# --- La pantalla ------------------------------------------------------------
#
# Va al final a propósito: monta la carpeta en la raíz y atrapa todo lo que no haya
# coincidido antes, así que tiene que declararse después de las operaciones de la API.

app.mount("/", StaticFiles(directory=ESTATICO, html=True), name="pantalla")
