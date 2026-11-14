"""Ruta pública temporal sin MAP_KEY (B-01): archivo anual por país de FIRMS.

Descarga los CSV anuales por país (calidad estándar) desde
``https://firms.modaps.eosdis.nasa.gov/data/country/<ruta>/<año>/<ruta>_<año>_<País>.csv``,
los guarda inmutables en ``data/raw/firms_pais/<País>/`` con su SHA-256 en
``data/raw/manifest.jsonl`` y escribe un **recorte** por bbox (derivado, regenerable) con
su propio manifiesto, listo para ``harmonize.pipeline``.

Es una ruta temporal mientras se valida la MAP_KEY de la API area. No cubre el año en
curso: el archivo por país de 2026 aún no estaba publicado el 2026-11-13.

Uso:
    uv run python -m ingest.firms_publico --pais Colombia --desde 2016 --hasta 2025 \\
        --bbox -76.7 1.4 -74.3 3.9 --salida data/processed/recortes_pais/huila
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

from ingest.firms_download import _default_fetch, _write_immutable
from ingest.firms_schema import COLUMNAS_REQUERIDAS, FUENTES_API, HUILA_BBOX, URL_FUENTES
from ingest.manifest import append_entry, build_entry, sha256_file

FUENTES_PAIS = tuple(f for f, m in FUENTES_API.items() if m.get("variante") == "pais")
Fetch = Callable[[str], bytes]


def construir_url(fuente: str, anio: int, pais: str) -> str:
    meta = FUENTES_API.get(fuente, {})
    if meta.get("variante") != "pais":
        raise ValueError(f"{fuente} no tiene ruta pública por país")
    ruta = meta["ruta"]
    return f"{URL_FUENTES['archivo_pais']}{ruta}/{anio}/{ruta}_{anio}_{pais}.csv"


def _cabecera_valida(payload: bytes, sensor: str) -> bool:
    try:
        primera = payload.splitlines()[0].decode("utf-8-sig") if payload else ""
    except UnicodeDecodeError:
        return False
    columnas = {c.strip() for c in primera.split(",")}
    return set(COLUMNAS_REQUERIDAS[(sensor, "pais")]) <= columnas


def _manifiesto(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _recortar(origen: Path, destino: Path, bbox: Sequence[float]) -> int:
    """Copia la cabecera y las filas dentro del bbox, byte a byte por línea."""
    w, s, e, n = bbox
    destino.parent.mkdir(parents=True, exist_ok=True)
    texto = origen.read_text(encoding="utf-8-sig")
    lineas = texto.splitlines(keepends=True)
    if not lineas:
        destino.write_text("", encoding="utf-8")
        return 0
    cabecera = next(csv.reader(io.StringIO(lineas[0])))
    i_lat, i_lon = cabecera.index("latitude"), cabecera.index("longitude")
    salida = [lineas[0]]
    for linea in lineas[1:]:
        campos = linea.rstrip("\r\n").split(",")
        try:
            lat, lon = float(campos[i_lat]), float(campos[i_lon])
        except (IndexError, ValueError):
            salida.append(linea)  # filas dudosas se conservan: el lector las pondrá en cuarentena
            continue
        if s <= lat <= n and w <= lon <= e:
            salida.append(linea)
    destino.write_text("".join(salida), encoding="utf-8")
    return len(salida) - 1


def descargar_y_recortar(
    *,
    raiz: Path,
    pais: str,
    anios: Sequence[int],
    bbox: Sequence[float],
    fuentes: Sequence[str] = FUENTES_PAIS,
    salida: Path,
    fetch: Fetch = _default_fetch,
    ahora: str | None = None,
) -> dict:
    raiz = Path(raiz)
    dir_raw = raiz / "data" / "raw"
    manifiesto_raw = dir_raw / "manifest.jsonl"
    salida = Path(salida)
    res: dict[str, list] = {"descargados": [], "reutilizados": [], "no_disponibles": [],
                            "rechazados": [], "recortes": []}
    existentes = {e["archivo"]: e for e in _manifiesto(manifiesto_raw)}
    crudos: list[tuple[str, dict, Path]] = []
    for fuente in fuentes:
        meta = FUENTES_API[fuente]
        for anio in anios:
            if anio < meta.get("desde_anio", 0):
                continue
            url = construir_url(fuente, anio, pais)
            ruta = dir_raw / "firms_pais" / pais / Path(url).name
            relativo = ruta.relative_to(dir_raw).as_posix()
            if relativo in existentes and ruta.exists():
                if sha256_file(ruta) != existentes[relativo]["sha256"]:
                    raise RuntimeError(f"hash distinto al del manifiesto: {ruta}")
                res["reutilizados"].append(relativo)
                crudos.append((fuente, existentes[relativo], ruta))
                continue
            try:
                payload = fetch(url)
            except HTTPError as exc:
                if exc.code == 404:
                    res["no_disponibles"].append(url)
                    continue
                raise
            if not _cabecera_valida(payload, meta["sensor"]):
                res["rechazados"].append(url)
                continue
            _write_immutable(ruta, payload)
            entrada = build_entry(
                ruta, dir_raw, fuente=fuente, sensor=meta["sensor"], calidad=meta["calidad"],
                coleccion=meta["coleccion"], variante="pais",
                fecha_descarga=ahora or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                url_sin_clave=url, bbox=None, fecha_inicio=f"{anio}-01-01", fecha_fin=f"{anio}-12-31",
                sintetico=False,
            )
            append_entry(manifiesto_raw, entrada)
            existentes[relativo] = entrada
            res["descargados"].append(relativo)
            crudos.append((fuente, entrada, ruta))

    # Recortes derivados: se regeneran completos en cada ejecución.
    salida.mkdir(parents=True, exist_ok=True)
    manifiesto_rec = salida / "manifest.jsonl"
    manifiesto_rec.unlink(missing_ok=True)
    for fuente, entrada, ruta in sorted(crudos, key=lambda t: t[1]["archivo"]):
        destino = salida / f"{ruta.stem}_recorte.csv"
        _recortar(ruta, destino, bbox)
        append_entry(manifiesto_rec, build_entry(
            destino, salida, fuente=fuente, sensor=entrada["sensor"], calidad=entrada["calidad"],
            coleccion=entrada["coleccion"], variante="pais", fecha_descarga=entrada["fecha_descarga"],
            url_sin_clave=entrada["url_sin_clave"], bbox=list(bbox),
            fecha_inicio=entrada["fecha_inicio"], fecha_fin=entrada["fecha_fin"], sintetico=False,
            origen_archivo=entrada["archivo"], origen_sha256=entrada["sha256"],
        ))
        res["recortes"].append(destino.name)
    return res


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pais", default="Colombia")
    p.add_argument("--desde", type=int, default=2016)
    p.add_argument("--hasta", type=int, default=2025)
    p.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"), default=HUILA_BBOX)
    p.add_argument("--fuentes", nargs="+", choices=FUENTES_PAIS, default=FUENTES_PAIS)
    p.add_argument("--salida", type=Path, default=Path("data/processed/recortes_pais/huila"))
    a = p.parse_args(argv)
    res = descargar_y_recortar(raiz=Path.cwd(), pais=a.pais, anios=range(a.desde, a.hasta + 1),
                               bbox=a.bbox, fuentes=a.fuentes, salida=a.salida)
    print(f"Ruta pública (sin MAP_KEY), calidad estándar: {len(res['descargados'])} descargados, "
          f"{len(res['reutilizados'])} reutilizados, {len(res['no_disponibles'])} no disponibles (404), "
          f"{len(res['rechazados'])} rechazados. Recortes en {a.salida}.")
    for url in res["rechazados"]:
        print(f"  rechazado (cabecera inválida): {url}", file=sys.stderr)
    return 3 if res["rechazados"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
