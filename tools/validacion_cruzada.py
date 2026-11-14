"""Validación cruzada (H5-01): conteo independiente del CSV oficial frente al pipeline.

Cuenta, con el módulo ``csv`` y sin reutilizar el lector del proyecto, las filas
de cada archivo crudo del manifiesto que caen en el bbox y el día UTC pedidos.
Luego compara con la salida del pipeline:

    crudas = n_brutas (celda_dia) + cuarentena (misma área y día) + borde

«borde» son los puntos dentro del bbox cuya celda de ~1 km tiene el centroide fuera: el
pipeline filtra celdas-día por centroide. Se calcula con la grilla del proyecto (R1) solo
como diagnóstico; el resto del conteo es independiente.

Uso:
    uv run python -I tools/validacion_cruzada.py CRUDO PROCESADO W,S,E,N AAAA-MM-DD
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from harmonize.config import RulesConfig  # noqa: E402
from harmonize.rules import cell_centroid, cell_index  # noqa: E402


def _en_area(lat: str, lon: str, bbox) -> bool:
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    w, s, e, n = bbox
    return s <= la <= n and w <= lo <= e


def _centroide_fuera(lat: str, lon: str, bbox, cfg: RulesConfig) -> bool:
    w, s, e, n = bbox
    cla, clo = cell_centroid(*cell_index(float(lat), float(lon), cfg), cfg)
    return not (s <= cla <= n and w <= clo <= e)


def comparar(crudo: Path, procesado: Path, bbox, fecha: str) -> dict:
    crudo, procesado = Path(crudo), Path(procesado)
    cfg = RulesConfig()
    borde = 0
    entradas = [json.loads(ln) for ln in (crudo / "manifest.jsonl").read_text().splitlines() if ln.strip()]
    por_sensor: Counter = Counter()
    por_fuente: Counter = Counter()
    archivos = []
    for e in entradas:
        with (crudo / e["archivo"]).open(encoding="utf-8-sig", newline="") as f:
            n = 0
            for fila in csv.DictReader(f):
                if fila.get("acq_date") == fecha and _en_area(fila.get("latitude"), fila.get("longitude"), bbox):
                    n += 1
                    if _centroide_fuera(fila["latitude"], fila["longitude"], bbox, cfg):
                        borde += 1
        por_sensor[e["sensor"]] += n
        por_fuente[e["fuente"]] += n
        archivos.append({k: e.get(k) for k in ("archivo", "sha256", "fuente", "calidad", "fecha_descarga", "sintetico")})

    con = duckdb.connect()
    w, s, e_, n_ = bbox
    nd, nb = con.execute(
        f"select coalesce(sum(n_detecciones), 0), coalesce(sum(n_brutas), 0)"
        f" from read_parquet('{procesado / 'celda_dia.parquet'}')"
        " where fecha_utc = cast(? as date) and centroide_lat between ? and ? and centroide_lon between ? and ?",
        [fecha, s, n_, w, e_],
    ).fetchone()
    cuarentena = 0
    for (crudos,) in con.execute(f"select datos_crudos from read_parquet('{procesado / 'cuarentena.parquet'}')").fetchall():
        fila = json.loads(crudos)
        if fila.get("acq_date") == fecha and _en_area(fila.get("latitude"), fila.get("longitude"), bbox):
            cuarentena += 1
    con.close()
    total = sum(por_sensor.values())
    return {
        "fecha_utc": fecha,
        "bbox": list(bbox),
        "archivos": archivos,
        "crudas": {"total": total, "por_sensor": dict(por_sensor), "por_fuente": dict(por_fuente)},
        "pipeline": {"n_brutas": int(nb), "n_detecciones": int(nd)},
        "cuarentena": cuarentena,
        "borde": borde,
        "diferencia": total - int(nb) - cuarentena,
        "diferencia_sin_explicar": total - int(nb) - cuarentena - borde,
    }


def informe_markdown(r: dict) -> str:
    sintetico = any(a.get("sintetico") for a in r["archivos"])
    calidades = sorted({a["calidad"] for a in r["archivos"] if a.get("calidad")})
    lineas = [
        f"Día UTC **{r['fecha_utc']}**, bbox `{','.join(str(v) for v in r['bbox'])}`. "
        f"Datos {'**sintético**s' if sintetico else 'reales de FIRMS'}; calidad de los archivos: {', '.join(calidades)}.",
        "",
        "| magnitud | valor |",
        "|---|---|",
        f"| filas crudas en el área y el día (conteo independiente con `csv`) | {r['crudas']['total']} |",
    ]
    for fuente, n in sorted(r["crudas"]["por_fuente"].items()):
        lineas.append(f"| — {fuente} | {n} |")
    lineas += [
        f"| `n_brutas` del pipeline (celda_dia) | {r['pipeline']['n_brutas']} |",
        f"| filas en cuarentena en el área y el día | {r['cuarentena']} |",
        f"| `n_detecciones` (representantes tras R3) | {r['pipeline']['n_detecciones']} |",
        f"| diferencia: crudas − n_brutas − cuarentena | {r['diferencia']} |",
        f"| — por efecto de borde (punto dentro, centroide de celda fuera) | {r['borde']} |",
        f"| — sin explicar | {r['diferencia_sin_explicar']} |",
        "",
        "Archivos fuente:",
        "",
    ]
    for a in r["archivos"]:
        lineas.append(f"- `{a['archivo']}` ({a['fuente']}, {a['calidad']}, descargado {a['fecha_descarga']}), "
                      f"sha256 `{a['sha256'][:16]}…`")
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    crudo, procesado, bbox_txt, fecha = args
    bbox = tuple(float(v) for v in bbox_txt.split(","))
    r = comparar(Path(crudo), Path(procesado), bbox, fecha)
    print(informe_markdown(r))
    return 0 if r["diferencia_sin_explicar"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
