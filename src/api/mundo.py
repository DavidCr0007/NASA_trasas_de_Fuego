"""Países del mundo para la vista global (ADR 0012).

Natural Earth 1:110m (dominio público), servido localmente desde
``ui/static/datos/mundo_paises.geojson`` (generado con ``tools/preparar_mundo.py``).
A esa escala la costa se simplifica: un foco en la orilla o en una isla pequeña puede
quedar «fuera de país»; se informa como tal, no se adivina.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from api.area import contiene

GEOJSON = Path(__file__).resolve().parent.parent / "ui" / "static" / "datos" / "mundo_paises.geojson"
FUENTE = "Natural Earth 1:110m Admin 0 (dominio público)"


@lru_cache(maxsize=1)
def paises() -> list[dict]:
    return json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]


@lru_cache(maxsize=1)
def _geometrias() -> list[tuple[str, str, list]]:
    return [(f["properties"]["iso_a3"], f["properties"]["nombre"],
             [(f["properties"]["bbox"], f["geometry"])]) for f in paises()]


@lru_cache(maxsize=200_000)
def pais_de(lon: float, lat: float) -> tuple[str, str] | None:
    """(iso_a3, nombre) del país que contiene el punto, o None (mar, costa simplificada)."""
    for iso, nombre, geoms in _geometrias():
        if contiene(geoms, lon, lat):
            return iso, nombre
    return None
