"""Áreas urbanas con nombre para el resaltado de «ciudad» (ADR 0014).

Entrada (crudo inmutable, fuera de git): Natural Earth 1:10m v5.1.2, descargado el
2026-11-15 en ``data/raw/natural_earth/20261115/`` desde
https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson
  - ne_10m_urban_areas.geojson (huella urbana, sin nombre; derivada de MODIS 2002)
  - ne_10m_populated_places_simple.geojson (nombre y población de los centros poblados)
Licencia: dominio público (https://www.naturalearthdata.com/about/terms-of-use/).

Salida: ``src/ui/static/datos/ciudades_colombia.geojson`` (versionada; sin red). Cada área
urbana que toca el recuadro de Colombia recibe el nombre del centro poblado más poblado que
contiene; si no contiene ninguno, el más cercano a menos de 0,1°; si no, se descarta (sin
nombre la tarjeta no sería útil). A 1:10m solo aparecen las ciudades con huella grande: en el
Huila, solo Neiva. Donde no hay área urbana, el visor resalta el municipio.

Uso: ``uv run python -I tools/preparar_ciudades.py [carpeta_crudo]``
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw" / "natural_earth" / "20261115"
SALIDA = RAIZ / "src" / "ui" / "static" / "datos" / "ciudades_colombia.geojson"
COLOMBIA = (-79.1, -4.3, -66.8, 12.6)
DISTANCIA_MAX = 0.1  # grados, para áreas urbanas sin centro poblado dentro


def _limites():
    """Reutiliza el punto en polígono de preparar_limites.py (con -I no se añade tools/ a sys.path)."""
    spec = importlib.util.spec_from_file_location("preparar_limites", Path(__file__).with_name("preparar_limites.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _redondear(coords):
    if coords and isinstance(coords[0], (int, float)):
        return [round(coords[0], 4), round(coords[1], 4)]
    return [_redondear(c) for c in coords]


def preparar(crudo: Path = CRUDO, salida: Path = SALIDA) -> dict:
    lim = _limites()
    urb_ruta = crudo / "ne_10m_urban_areas.geojson"
    pob_ruta = crudo / "ne_10m_populated_places_simple.geojson"
    urbanas = json.loads(urb_ruta.read_text(encoding="utf-8"))["features"]
    lugares = [f for f in json.loads(pob_ruta.read_text(encoding="utf-8"))["features"] if f.get("geometry")]
    w, s, e, n = COLOMBIA
    ciudades = []
    for f in urbanas:
        geom = f.get("geometry")
        if not geom or geom["type"] not in ("Polygon", "MultiPolygon"):
            continue
        caja = lim._bbox(geom)
        if caja[2] < w or caja[0] > e or caja[3] < s or caja[1] > n:
            continue
        cerca = [p for p in lugares
                 if caja[0] - DISTANCIA_MAX <= p["geometry"]["coordinates"][0] <= caja[2] + DISTANCIA_MAX
                 and caja[1] - DISTANCIA_MAX <= p["geometry"]["coordinates"][1] <= caja[3] + DISTANCIA_MAX]
        dentro = [p for p in cerca if lim.contiene(geom, tuple(p["geometry"]["coordinates"][:2]))]
        if dentro:
            lugar = max(dentro, key=lambda p: p["properties"].get("pop_max") or 0)
        else:
            cx, cy = (caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2
            lugar = min(cerca, default=None, key=lambda p: math.dist((cx, cy), p["geometry"]["coordinates"][:2]))
            if lugar is None or math.dist((cx, cy), lugar["geometry"]["coordinates"][:2]) > DISTANCIA_MAX + max(caja[2] - caja[0], caja[3] - caja[1]) / 2:
                continue
        props = lugar["properties"]
        ciudades.append({"type": "Feature",
                         "properties": {"shapeName": props.get("name"), "pais": props.get("adm0name"),
                                        "poblacion": props.get("pop_max"), "area_km2": f["properties"].get("area_sqkm"),
                                        "bbox": caja},
                         "geometry": {"type": geom["type"], "coordinates": _redondear(geom["coordinates"])}})
    ciudades.sort(key=lambda c: (-(c["properties"]["poblacion"] or 0), c["properties"]["shapeName"]))
    geo = {
        "type": "FeatureCollection",
        "metadatos": {
            "fuente": "Natural Earth 1:10m v5.1.2 (urban_areas; nombres de populated_places_simple)",
            "licencia": "Dominio público",
            "cita": "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com.",
            "recorte": list(COLOMBIA),
            "sha256_origen": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (urb_ruta, pob_ruta)},
            "descargado": "2026-11-15",
        },
        "features": ciudades,
    }
    salida.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return geo


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    geo = preparar(Path(args[0]) if args else CRUDO)
    print(f"{len(geo['features'])} áreas urbanas con nombre en {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
