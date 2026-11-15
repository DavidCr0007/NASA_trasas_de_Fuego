"""Hidrografía mundial para el visor de capas (ADR 0017).

Entrada (crudo inmutable, fuera de git): Natural Earth 1:10m v5.1.2, descargado el
2026-11-15 en ``data/raw/natural_earth/20261115/`` desde
https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson
  - ne_10m_rivers_lake_centerlines.geojson (ríos y ejes de lagos)
  - ne_10m_lakes.geojson (lagos y embalses)
Licencia: dominio público (https://www.naturalearthdata.com/about/terms-of-use/).

Salida: ``src/ui/static/datos/hidrografia_mundial.geojson`` (versionada, sin red).
Conserva todos los ríos, ejes de lagos y lagos del conjunto global, con coordenadas
a 4 decimales. Natural Earth es cartografía generalizada: el detalle de afluentes
se complementa en el navegador con OpenStreetMap/OpenFreeMap bajo demanda.

Uso: ``uv run python -I tools/preparar_hidrografia.py [carpeta_crudo]``
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw" / "natural_earth" / "20261115"
SALIDA = RAIZ / "src" / "ui" / "static" / "datos" / "hidrografia_mundial.geojson"
ARCHIVOS = {"rio": "ne_10m_rivers_lake_centerlines.geojson", "lago": "ne_10m_lakes.geojson"}


def _redondear(coords):
    if coords and isinstance(coords[0], (int, float)):
        return [round(coords[0], 4), round(coords[1], 4)]
    return [_redondear(c) for c in coords]


def preparar(crudo: Path = CRUDO, salida: Path = SALIDA) -> dict:
    elementos, hashes = [], {}
    for tipo, nombre in ARCHIVOS.items():
        ruta = crudo / nombre
        hashes[nombre] = hashlib.sha256(ruta.read_bytes()).hexdigest()
        for f in json.loads(ruta.read_text(encoding="utf-8"))["features"]:
            geom = f.get("geometry")
            if not geom:
                continue
            props = f.get("properties") or {}
            elementos.append({"type": "Feature",
                              "properties": {"tipo": tipo, "nombre": props.get("name") or "",
                                             "rango": props.get("scalerank"),
                                             "min_zoom": props.get("min_zoom") or 0},
                              "geometry": {"type": geom["type"], "coordinates": _redondear(geom["coordinates"])}})
    elementos.sort(key=lambda f: (f["properties"]["tipo"], f["properties"]["nombre"]))
    geo = {
        "type": "FeatureCollection",
        "metadatos": {
            "fuente": "Natural Earth 1:10m v5.1.2 (rivers_lake_centerlines, lakes)",
            "licencia": "Dominio público",
            "cita": "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com.",
            "cobertura": "Mundial, sin recorte por país",
            "alcance": "Ríos y lagos principales; cartografía generalizada a escala 1:10 millones, no una red exhaustiva de afluentes.",
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
