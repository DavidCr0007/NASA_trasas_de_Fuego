"""Punto de entrada de Vercel (ADR 0016): la app completa con API como una función de Python.

Vercel carga ``app`` (``[tool.vercel] entrypoint`` en pyproject.toml). Diferencias con ``make api``:
  - Datos: la muestra SINTÉTICA histórica que generó la compilación (tools/construir_vercel.py).
    Si falta, se genera una vez en /tmp al arrancar la instancia. ``HHN_DATOS`` apunta a otro
    conjunto procesado, si se publica uno.
  - Disco de solo lectura salvo /tmp: la caché de límites de geoBoundaries va a /tmp.
Localmente: ``uv run uvicorn vercel_app:app`` (o ``make api``, que no usa este archivo).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
TMP = Path(os.environ.get("HHN_TMP", "/tmp/hhn"))
os.environ.setdefault("HHN_CACHE_LIMITES", str(TMP / "limites_globales"))

from api.app import create_app  # noqa: E402


def _datos() -> Path:
    datos = Path(os.environ.get("HHN_DATOS") or RAIZ / "data" / "processed" / "demo_historica")
    if (datos / "celda_dia.parquet").exists():
        return datos
    sys.path.insert(0, str(RAIZ / "tools"))
    from construir_vercel import construir  # noqa: E402

    return construir(TMP / "demo_historica")


app = create_app(_datos())
