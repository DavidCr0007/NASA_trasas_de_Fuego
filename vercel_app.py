"""Punto de entrada de Vercel (ADR 0016): la app completa con API como una función de Python.

Vercel carga ``app`` (``[tool.vercel] entrypoint`` en pyproject.toml). Diferencias con ``make api``:
  - Datos: ``HHN_MODO_DATOS=demo`` usa la muestra SINTÉTICA histórica y ``firms`` el conjunto
    real generado en la construcción. Si falta, se construye en /tmp al arrancar la instancia.
    ``HHN_DATOS`` permite seleccionar otro conjunto procesado publicado.
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
    modo = os.environ.get("HHN_MODO_DATOS", "demo").lower()
    if modo not in ("demo", "firms"):
        raise RuntimeError("HHN_MODO_DATOS debe ser demo o firms")
    nombre = "vercel_firms" if modo == "firms" else "demo_historica"
    datos = Path(os.environ.get("HHN_DATOS") or RAIZ / "data" / "processed" / nombre)
    if (datos / "celda_dia.parquet").exists():
        return datos
    if os.environ.get("HHN_DATOS"):
        raise RuntimeError("HHN_DATOS no contiene el conjunto procesado configurado; no se sustituirá por una demostración sintética")
    if modo == "firms":
        from ingest.vercel_firms import construir_firms
        return construir_firms(TMP / "vercel_firms")
    sys.path.insert(0, str(RAIZ / "tools"))
    from construir_vercel import construir  # noqa: E402

    return construir(TMP / "demo_historica")


app = create_app(_datos())
