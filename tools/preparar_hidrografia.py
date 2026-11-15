"""Hidrografía local para el visor de capas (ADR 0013).

Entrada (crudo inmutable, fuera de git): Natural Earth 1:10m v5.1.2, descargado el
2026-11-15 en ``data/raw/natural_earth/20261115/`` desde
https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson
  - ne_10m_rivers_lake_centerlines.geojson (ríos y ejes de lagos)
  - ne_10m_lakes.geojson (lagos y embalses)
Licencia: dominio público (https://www.naturalearthdata.com/about/terms-of-use/).

Salida: ``src/ui/static/datos/hidrografia_colombia.geojson`` (versionada; la capa
«Hidrografía» funciona sin red). Se conservan los elementos cuyo recuadro toca Colombia,
con coordenadas a 4 decimales. A 1:10m solo aparecen los ríos principales (en el Huila,
el Magdalena); HydroRIVERS daría más detalle, pero su licencia incluye restricciones de
redistribución que no se han revisado (pendiente en el ADR 0013).

Uso: ``uv run python -I tools/preparar_hidrografia.py [carpeta_crudo]``
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw" / "natural_earth" / "20261115"
SALIDA = RAIZ / "src" / "ui" / "static" / "datos" / "hidrografia_colombia.geojson"
COLOMBIA = (-79.1, -4.3, -66.8, 12.6)  # recuadro de recorte (oeste, sur, este, norte)
ARCHIVOS = {"rio": "ne_10m_rivers_lake_centerlines.geojson", "lago": "ne_10m_lakes.geojson"}


def _puntos(coords):
    if coords and isinstance(coords[0], (int, float)):
        yield coords
        return
    for c in coords:
        yield from _puntos(c)


def _redondear(coords):
    if coords and isinstance(coords[0], (int, float)):
        return [round(coords[0], 4), round(coords[1], 4)]
    return [_redondear(c) for c in coords]


def toca(geom: dict, caja=COLOMBIA) -> bool:
    w, s, e, n = caja
    return any(w <= x <= e and s <= y <= n for x, y, *_ in _puntos(geom["coordinates"]))


def preparar(crudo: Path = CRUDO, salida: Path = SALIDA) -> dict:
    elementos, hashes = [], {}
    for tipo, nombre in ARCHIVOS.items():
        ruta = crudo / nombre
        hashes[nombre] = hashlib.sha256(ruta.read_bytes()).hexdigest()
        for f in json.loads(ruta.read_text(encoding="utf-8"))["features"]:
            geom = f.get("geometry")
            if not geom or not toca(geom):
                continue
            props = f.get("properties") or {}
            elementos.append({"type": "Feature",
                              "properties": {"tipo": tipo, "nombre": props.get("name") or "",
                                             "rango": props.get("scalerank")},
                              "geometry": {"type": geom["type"], "coordinates": _redondear(geom["coordinates"])}})
    elementos.sort(key=lambda f: (f["properties"]["tipo"], f["properties"]["nombre"]))
    geo = {
        "type": "FeatureCollection",
        "metadatos": {
            "fuente": "Natural Earth 1:10m v5.1.2 (rivers_lake_centerlines, lakes)",
            "licencia": "Dominio público",
            "cita": "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com.",
            "recorte": list(COLOMBIA),
            "sha256_origen": hashes,
            "descargado": "2026-11-15",
        },
        "features": elementos,
    }
    salida.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return geo


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    geo = preparar(Path(args[0]) if args else CRUDO)
    print(f"{len(geo['features'])} elementos hidrográficos en {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
