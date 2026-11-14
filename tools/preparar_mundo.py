"""Prepara los países del mundo para el globo 3D y el resumen global (ADR 0012).

Entrada (crudo inmutable, fuera de git): Natural Earth 1:110m Admin 0 Countries v5.1.2
(dominio público), descargado el 2026-11-14 de
https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_110m_admin_0_countries.geojson
en ``data/raw/natural_earth/20261114/``.

Salida: ``src/ui/static/datos/mundo_paises.geojson`` (versionada, para la demo sin red), con
solo ``nombre`` (español), ``iso_a3`` y ``bbox`` por país, y coordenadas a 2 decimales (~1 km,
suficiente para 1:110m).

Uso: ``uv run python -I tools/preparar_mundo.py [carpeta_crudo]``
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw" / "natural_earth" / "20261114"
ARCHIVO = "ne_110m_admin_0_countries.geojson"
SALIDA = RAIZ / "src" / "ui" / "static" / "datos" / "mundo_paises.geojson"


def _redondear(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 2), round(coords[1], 2)]
    return [_redondear(c) for c in coords]


def _bbox(geom: dict) -> list[float]:
    puntos = []

    def recorrer(c):
        if isinstance(c[0], (int, float)):
            puntos.append(c)
        else:
            for x in c:
                recorrer(x)

    recorrer(geom["coordinates"])
    xs, ys = [p[0] for p in puntos], [p[1] for p in puntos]
    return [min(xs), min(ys), max(xs), max(ys)]


def preparar(crudo: Path = CRUDO, salida: Path = SALIDA) -> dict:
    origen = crudo / ARCHIVO
    datos = json.loads(origen.read_text(encoding="utf-8"))
    features = []
    for f in datos["features"]:
        p = f["properties"]
        # ISO_A3 vale -99 en algunos países (Francia, Noruega, Kosovo…): se usa ADM0_A3.
        iso = p["ISO_A3"] if p["ISO_A3"] not in ("-99", None) else p["ADM0_A3"]
        geom = {"type": f["geometry"]["type"], "coordinates": _redondear(f["geometry"]["coordinates"])}
        features.append({
            "type": "Feature",
            "properties": {"nombre": p.get("NAME_ES") or p["NAME"], "iso_a3": iso, "bbox": _bbox(geom)},
            "geometry": geom,
        })
    features.sort(key=lambda x: x["properties"]["iso_a3"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = {
        "type": "FeatureCollection",
        "fuente": "Natural Earth 1:110m Admin 0 Countries v5.1.2 (dominio público), naturalearthdata.com",
        "sha256_crudo": hashlib.sha256(origen.read_bytes()).hexdigest(),
        "features": features,
    }
    salida.write_text(json.dumps(cuerpo, ensure_ascii=False, separators=(",", ":")) + "\n",
                      encoding="utf-8", newline="\n")
    return {"paises": len(features), "bytes": salida.stat().st_size}


if __name__ == "__main__":
    print(preparar(Path(sys.argv[1]) if len(sys.argv) > 1 else CRUDO))
