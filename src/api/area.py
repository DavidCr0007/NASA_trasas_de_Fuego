"""Áreas con forma real (R-40): Huila y sus municipios, desde el GeoJSON local de geoBoundaries.

El filtro «punto en polígono» se registra como función de DuckDB (``en_area``) para que todas
las consultas de la API usen la misma forma, no solo el recuadro.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GEOJSON = Path(__file__).resolve().parent.parent / "ui" / "static" / "datos" / "huila_municipios.geojson"


def _poligonos(geom: dict) -> list:
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def _en_anillo(anillo, x: float, y: float) -> bool:
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def contiene(geometrias: list[tuple[list[float], dict]], lon: float, lat: float) -> bool:
    """True si (lon, lat) cae en alguna geometría; cada una lleva su recuadro para descartar rápido."""
    for (w, s, e, n), geom in geometrias:
        if not (w <= lon <= e and s <= lat <= n):
            continue
        for pol in _poligonos(geom):
            if _en_anillo(pol[0], lon, lat) and not any(_en_anillo(h, lon, lat) for h in pol[1:]):
                return True
    return False


@lru_cache(maxsize=1)
def _municipios() -> list[dict]:
    return json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]


def resolver_area(area: str) -> dict:
    """Devuelve {id, nombre, bbox, geometrias}. Lanza ValueError si el área no existe."""
    feats = _municipios()
    if area == "huila":
        elegidos, nombre = feats, "Huila"
    elif area.startswith("mun:"):
        elegidos = [f for f in feats if f["properties"]["shapeID"] == area[4:]]
        if not elegidos:
            raise ValueError(f"municipio desconocido: {area[4:]}")
        nombre = elegidos[0]["properties"]["shapeName"]
    else:
        raise ValueError(f"área desconocida: {area}")
    geometrias = [(f["properties"]["bbox"], f["geometry"]) for f in elegidos]
    cajas = [g[0] for g in geometrias]
    bbox = (min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas))
    return {"id": area, "nombre": nombre, "bbox": bbox, "geometrias": geometrias}
