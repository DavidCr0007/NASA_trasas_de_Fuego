"""Arranque local: ``uv run python -m api [--datos DIR] [--datos-global DIR] [--puerto N] [--anios-minimos N]``."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import uvicorn

from api.app import create_app


def crear_bucle_windows() -> asyncio.AbstractEventLoop:
    """Evita el cierre del listener de Proactor ante desconexiones (WinError 64).

    La API local no crea subprocesos asyncio; Selector basta para sus conexiones HTTP.
    Solo se aplica al arranque CLI de Windows, sin cambiar el despliegue ASGI.
    """
    return asyncio.SelectorEventLoop()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--datos", type=Path, default=Path("data/processed/demo"))
    p.add_argument("--datos-global", type=Path, default=None,
                   help="conjunto para el globo 3D (/global); por defecto, el mismo de --datos (ADR 0012)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--puerto", type=int, default=8000)
    p.add_argument("--anios-minimos", type=int, default=None,
                   help="mínimo de años para la línea base (por defecto: 5, acordado en el ADR 0005)")
    a = p.parse_args(argv)
    bucle = "api.__main__:crear_bucle_windows" if sys.platform == "win32" else "auto"
    uvicorn.run(create_app(a.datos, datos_global=a.datos_global, anios_minimos=a.anios_minimos), host=a.host, port=a.puerto, loop=bucle)


if __name__ == "__main__":
    main()
