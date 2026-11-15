"""Prepara los municipios del Huila para la interfaz (H7-01).

Entrada (crudo inmutable, fuera de git): geoBoundaries gbOpen COL, versión simplificada,
descargada el 2026-11-14 en ``data/raw/geoboundaries/20261114/``:
  - ADM1 (departamentos; fuente OpenStreetMap, licencia ODbL 1.0): SOLO se usa para
    seleccionar qué municipios pertenecen al Huila. No se redistribuye.
  - ADM2 (municipios; fuente DANE, licencia CC BY 4.0): se publican los 37 del Huila.

Salida: ``src/ui/static/datos/huila_municipios.geojson`` (versionada, para la demo sin red).

ADR 0013: también escribe ``huila_departamento.geojson``, el límite del departamento como
UNIÓN de los 37 municipios DANE (CC BY 4.0). El ADM1 de geoBoundaries para COL existe
(33 unidades, OpenStreetMap 2017) pero su licencia es ODbL 1.0, con obligación de compartir
igual las bases derivadas; por eso no se redistribuye. Sin el crudo, se reutiliza el
GeoJSON de municipios ya versionado.

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
SALIDA_DEPARTAMENTO = SALIDA.with_name("huila_departamento.geojson")
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


def _area(anillo) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anillo, anillo[1:])) / 2


def disolver(features: list[dict]) -> dict:
    """Contorno de la unión de polígonos que comparten aristas idénticas (sin shapely).

    geoBoundaries simplifica con topología compartida y el redondeo a 4 decimales es igual
    en ambos lados, así que una arista interior aparece exactamente dos veces y se descarta;
    las que aparecen una vez forman el contorno. Falla si la topología no es limpia.
    """
    cuenta: dict[tuple, int] = {}
    dirigidas: list[tuple] = []
    for f in features:
        for poligono in _anillos(f["geometry"]):
            for anillo in poligono:
                for a, b in zip(anillo, anillo[1:]):
                    a, b = tuple(a), tuple(b)
                    if a == b:
                        continue
                    clave = (a, b) if a < b else (b, a)
                    cuenta[clave] = cuenta.get(clave, 0) + 1
                    dirigidas.append((a, b))
    siguiente: dict[tuple, tuple] = {}
    for a, b in dirigidas:
        if cuenta[(a, b) if a < b else (b, a)] == 1:
            if a in siguiente:
                raise ValueError(f"topología no limpia en {a}: el contorno se bifurca")
            siguiente[a] = b
    anillos = []
    while siguiente:
        inicio, actual = next(iter(siguiente.items()))
        del siguiente[inicio]
        anillo = [list(inicio), list(actual)]
        while actual != inicio:
            if actual not in siguiente:
                raise ValueError(f"topología no limpia en {actual}: el contorno no cierra")
            actual = siguiente.pop(actual)
            anillo.append(list(actual))
        anillos.append(anillo)
    # Exteriores: los que no están dentro de otro anillo; huecos: los contenidos.
    exteriores = [a for a in anillos if not any(o is not a and _en_anillo(o, *a[0]) for o in anillos)]
    poligonos = []
    for ext in sorted(exteriores, key=lambda a: -abs(_area(a))):
        if _area(ext) < 0:
            ext = ext[::-1]  # RFC 7946: exterior en sentido antihorario
        huecos = [h if _area(h) < 0 else h[::-1] for h in anillos
                  if h not in exteriores and _en_anillo(ext, *h[0])]
        poligonos.append([ext, *huecos])
    if len(poligonos) == 1:
        return {"type": "Polygon", "coordinates": poligonos[0]}
    return {"type": "MultiPolygon", "coordinates": poligonos}


def preparar_departamento(municipios: Path = SALIDA, salida: Path = SALIDA_DEPARTAMENTO) -> dict:
    """Límite del Huila como unión de sus 37 municipios (DANE, CC BY 4.0), no del ADM1 (ODbL)."""
    geo = json.loads(municipios.read_text(encoding="utf-8"))
    geom = disolver(geo["features"])
    meta = geo["metadatos"]
    salida_geo = {
        "type": "FeatureCollection",
        "metadatos": {
            "fuente": meta["fuente"],
            "fuente_original": meta["fuente_original"],
            "licencia": meta["licencia"],
            "cita": meta["cita"],
            "metodo": f"Unión de los {len(geo['features'])} municipios de huila_municipios.geojson "
                      "(se descartan las aristas compartidas). No deriva del ADM1 de geoBoundaries "
                      "(OpenStreetMap, ODbL 1.0, verificado el 2026-11-15 en la API de geoBoundaries).",
            "sha256_municipios": hashlib.sha256(municipios.read_bytes()).hexdigest(),
        },
        "features": [{"type": "Feature",
                      "properties": {"shapeName": DEPARTAMENTO, "shapeID": "huila", "bbox": _bbox(geom)},
                      "geometry": geom}],
    }
    salida.write_text(json.dumps(salida_geo, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return salida_geo


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    crudo = Path(args[0]) if args else CRUDO
    if (crudo / "geoBoundaries-COL-ADM2_simplified.geojson").exists():
        n = preparar(crudo)
        print(f"{n} municipios del {DEPARTAMENTO} en {SALIDA}")
    else:
        print(f"Sin crudo en {crudo}: se reutiliza {SALIDA.name} ya versionado.")
    preparar_departamento()
    print(f"Límite departamental (unión de municipios) en {SALIDA_DEPARTAMENTO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
