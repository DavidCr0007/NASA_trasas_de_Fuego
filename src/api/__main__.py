"""Arranque local: ``uv run python -m api [--datos DIR] [--puerto N] [--anios-minimos N]``."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from api.app import create_app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--datos", type=Path, default=Path("data/processed/demo"))
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--puerto", type=int, default=8000)
    p.add_argument("--anios-minimos", type=int, default=None,
                   help="mínimo de años para la línea base (por defecto: valor PROVISIONAL del ADR 0005)")
    a = p.parse_args(argv)
    uvicorn.run(create_app(a.datos, anios_minimos=a.anios_minimos), host=a.host, port=a.puerto)


if __name__ == "__main__":
    main()
