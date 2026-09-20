"""Levanta el servidor de la aplicación.

Se corre desde la raíz del repo y queda escuchando hasta que lo cortes con Ctrl-C. Mientras
tanto, la dirección que imprime abre la página de documentación, donde se puede probar cada
operación apretando botones.

- `main`: lee los argumentos y arranca el servidor.

Técnico: escucha solo en `127.0.0.1`, o sea que únicamente se puede abrir desde esta misma
máquina; no queda expuesto a la red. `--recargar` reinicia el servidor solo cuando se
guarda un archivo, útil mientras se programa y molesto si no.
"""

from __future__ import annotations

import argparse
import sys

import uvicorn

PUERTO = 8000


def main() -> int:
    p = argparse.ArgumentParser(description="Levanta el servidor de AgroTello.")
    p.add_argument("--puerto", type=int, default=PUERTO)
    p.add_argument("--recargar", action="store_true", help="Reiniciar al guardar un archivo")
    args = p.parse_args()

    print(f"\n  Probá las operaciones en  http://127.0.0.1:{args.puerto}/docs\n")
    uvicorn.run(
        "dronesw.web.servidor:app",
        host="127.0.0.1",
        port=args.puerto,
        reload=args.recargar,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
