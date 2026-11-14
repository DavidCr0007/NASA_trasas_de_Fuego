"""Prepara los municipios del Huila para la interfaz (H7-01).

Entrada (crudo inmutable, fuera de git): geoBoundaries gbOpen COL, versión simplificada,
descargada el 2026-11-14 en ``data/raw/geoboundaries/20261114/``:
  - ADM1 (departamentos; fuente OpenStreetMap, licencia ODbL 1.0): SOLO se usa para
    seleccionar qué municipios pertenecen al Huila. No se redistribuye.
  - ADM2 (municipios; fuente DANE, licencia CC BY 4.0): se publican los 37 del Huila.

Salida: ``src/ui/static/datos/huila_municipios.geojson`` (versionada, para la demo sin red).

Uso: ``uv run python -I tools/preparar_limites.py [carpeta_crudo]``
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw" / "geoboundaries" / "20261114"
SALIDA = RAIZ / "src" / "ui" / "static" / "datos" / "huila_municipios.geojson"
DEPARTAMENTO = "Huila"


def _anillos(geom: dict) -> list[list[list[list[float]]]]:
    """Lista de polígonos; cada uno es [exterior, huecos...]."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    raise ValueError(f"geometría no soportada: {geom['type']}")


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


def contiene(geom: dict, punto: tuple[float, float]) -> bool:
    x, y = punto
    for poligono in _anillos(geom):
        if _en_anillo(poligono[0], x, y) and not any(_en_anillo(h, x, y) for h in poligono[1:]):
            return True
    return False


def punto_interior(geom: dict) -> tuple[float, float]:
    """Punto garantizado dentro del polígono mayor (barrido horizontal por su latitud media).

    El centroide puede caer fuera en polígonos cóncavos; por eso se busca el tramo interior
    más ancho de una línea horizontal a media altura.
    """
    mayor = max(_anillos(geom), key=lambda p: len(p[0]))
    exterior = mayor[0]
    ys = [p[1] for p in exterior]
    for fraccion in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8):
        y = min(ys) + (max(ys) - min(ys)) * fraccion
        cortes = []
        for anillo in mayor:
            for (x1, y1), (x2, y2) in zip(anillo, anillo[1:]):
                if (y1 > y) != (y2 > y):
                    cortes.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        cortes.sort()
        tramos = [(cortes[i], cortes[i + 1]) for i in range(0, len(cortes) - 1, 2)]
        if tramos:
            a, b = max(tramos, key=lambda t: t[1] - t[0])
            p = ((a + b) / 2, y)
            if contiene(geom, p):
                return p
    raise ValueError("no se encontró un punto interior")


def _bbox(geom: dict) -> list[float]:
    xs = [p[0] for pol in _anillos(geom) for p in pol[0]]
    ys = [p[1] for pol in _anillos(geom) for p in pol[0]]
    return [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)]


def _redondear(geom: dict) -> dict:
    def r(anillo):
        salida = []
        for x, y, *_ in anillo:
            p = [round(x, 4), round(y, 4)]
            if not salida or salida[-1] != p:
                salida.append(p)
        return salida

    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [r(a) for a in geom["coordinates"]]}
    return {"type": "MultiPolygon", "coordinates": [[r(a) for a in pol] for pol in geom["coordinates"]]}


def preparar(crudo: Path = CRUDO, salida: Path = SALIDA) -> int:
    adm1_ruta = crudo / "geoBoundaries-COL-ADM1_simplified.geojson"
    adm2_ruta = crudo / "geoBoundaries-COL-ADM2_simplified.geojson"
    adm1 = json.loads(adm1_ruta.read_text(encoding="utf-8"))
    adm2 = json.loads(adm2_ruta.read_text(encoding="utf-8"))
    huila = next(f["geometry"] for f in adm1["features"] if f["properties"]["shapeName"] == DEPARTAMENTO)
    municipios = []
    for f in adm2["features"]:
        if contiene(huila, punto_interior(f["geometry"])):
            props = f["properties"]
            municipios.append({
                "type": "Feature",
                "properties": {"shapeName": props["shapeName"], "shapeID": props["shapeID"],
                               "bbox": _bbox(f["geometry"])},
                "geometry": _redondear(f["geometry"]),
            })
    municipios.sort(key=lambda f: f["properties"]["shapeName"])
    geo = {
        "type": "FeatureCollection",
        "metadatos": {
            "fuente": "geoBoundaries gbOpen COL ADM2 (simplificado), commit 9469f09",
            "fuente_original": "Departamento Administrativo Nacional de Estadística (DANE), 2020",
            "licencia": "CC BY 4.0",
            "cita": "Runfola, D. et al. (2020) geoBoundaries: A global database of political "
                    "administrative boundaries. PLoS ONE 15(4): e0231866.",
            "seleccion": "Municipios cuyo punto interior cae en el Huila (geoBoundaries ADM1, "
                         "OpenStreetMap, ODbL 1.0; usado solo para seleccionar, no redistribuido).",
            "sha256_origen_adm2": hashlib.sha256(adm2_ruta.read_bytes()).hexdigest(),
            "descargado": "2026-11-14",
        },
        "features": municipios,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(municipios)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    n = preparar(Path(args[0]) if args else CRUDO)
    print(f"{n} municipios del {DEPARTAMENTO} en {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
