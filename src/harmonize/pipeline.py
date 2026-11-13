"""D-06: pipeline Parquet reproducible (ingesta -> armonización -> Parquet).

Uso: ``python -m harmonize.pipeline --input DIR --output DIR [--manifest RUTA]``.

Determinismo: sin pandas, sin relojes ni rutas absolutas en datos o metadatos,
filas ordenadas por clave estable y parámetros de escritura fijos. La garantía
de hash idéntico vale con las mismas versiones de dependencias (uv.lock).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ingest.manifest import ManifestError, load_manifest
from ingest.reader import IngestResult, read_file

from .armonizar import HarmonizeResult, harmonize_ingest
from .config import RULES_VERSION, RulesConfig

__all__ = ["ARCHIVOS_PARQUET", "HarmonizeResult", "harmonize_ingest", "ejecutar", "main"]

MANIFEST_NOMBRE = "manifest.jsonl"
ARCHIVOS_PARQUET = {
    "aceptados": "detecciones.parquet",
    "deduplicados": "deduplicados.parquet",
    "cuarentena": "cuarentena.parquet",
    "celda_dia": "celda_dia.parquet",
}

# Parámetros de escritura FIJOS (parte de la garantía de reproducibilidad).
_ESCRITURA = {
    "compression": "zstd",
    "compression_level": 3,
    "row_group_size": 65536,
    "write_statistics": True,
    "version": "2.6",
    "data_page_version": "1.0",
}

_TS = pa.timestamp("us", tz="UTC")
_S, _F, _I, _B = pa.string(), pa.float64(), pa.int64(), pa.bool_()

_COLUMNAS_ACEPTADOS = [
    ("record_id", _S), ("fuente", _S), ("sensor", _S), ("satelite_codigo", _S),
    ("satelite", _S), ("satelite_confirmado", _B), ("coleccion", _S), ("version", _S),
    ("calidad", _S), ("lat", _F), ("lon", _F), ("fecha_hora_utc", _TS),
    ("daynight", _S), ("confianza_raw", _S), ("frp", _F), ("brillo", _F),
    ("archivo_origen", _S), ("sha256_origen", _S), ("fecha_descarga", _TS),
    ("fila", _I), ("sintetico", _B),
    ("confianza_clase", _S), ("cell_id", _S), ("cell_fila", _I), ("cell_col", _I),
    ("rules_version", _S),
]
_COLUMNAS_DEDUP_EXTRA = [("dedup_de", _S), ("delta_t_min", _F), ("motivo", _S)]

ESQUEMAS_CAMPOS: dict[str, list[tuple[str, pa.DataType]]] = {
    "aceptados": _COLUMNAS_ACEPTADOS + [("n_fusionados", _I)],
    "deduplicados": _COLUMNAS_ACEPTADOS + _COLUMNAS_DEDUP_EXTRA,
    "cuarentena": [
        ("archivo_origen", _S), ("sha256_origen", _S), ("fila", _I), ("motivo", _S),
        ("datos_crudos", _S), ("fecha_descarga", _TS), ("rules_version", _S),
    ],
    "celda_dia": [
        ("cell_id", _S), ("fecha_utc", pa.date32()), ("cell_fila", _I), ("cell_col", _I),
        ("n_detecciones", _I), ("n_brutas", _I), ("n_modis", _I), ("n_viirs", _I),
        ("confianza_max", _S), ("frp_max", _F), ("frp_sum", _F),
        ("primera_hora_utc", _TS), ("ultima_hora_utc", _TS), ("satelites", _S),
        ("calidades", _S), ("centroide_lat", _F), ("centroide_lon", _F),
        ("rules_version", _S),
    ],
}

_CLAVES_ORDEN = {
    "aceptados": lambda r: r["record_id"],
    "deduplicados": lambda r: r["record_id"],
    "cuarentena": lambda r: (str(r.get("archivo_origen") or ""),
                             r.get("fila") if r.get("fila") is not None else -1,
                             r.get("motivo") or "", r.get("datos_crudos") or ""),
    "celda_dia": lambda r: (r["cell_id"], r["fecha_utc"]),
}


class SalidaProhibida(Exception):
    """La ruta de salida cae dentro de data/raw (inmutable)."""


def _validar_salida(salida: Path) -> Path:
    destino = salida.resolve()
    partes = destino.parts
    if any(partes[i] == "data" and partes[i + 1] == "raw" for i in range(len(partes) - 1)):
        raise SalidaProhibida(
            f"la salida {salida} está dentro de data/raw, que es inmutable; elija otro directorio"
        )
    return destino


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _ingerir(entrada: Path, manifiesto: Path) -> tuple[IngestResult, list[dict[str, str]]]:
    entradas = load_manifest(manifiesto)
    if not entradas:
        raise ManifestError(f"manifiesto vacío o inexistente: {manifiesto.name}")
    res = IngestResult([], [], 0)
    for archivo in sorted(entradas):
        parcial = read_file(entrada / archivo, entradas[archivo])
        res.registros.extend(parcial.registros)
        res.cuarentena.extend(parcial.cuarentena)
        res.n_input += parcial.n_input
        res.n_por_archivo[archivo] = parcial.n_input
        res.advertencias.extend(parcial.advertencias)
    archivos = [{"archivo": a, "sha256": entradas[a]["sha256"]} for a in sorted(entradas)]
    return res, archivos


def _tabla(nombre: str, filas: list[dict[str, Any]], meta: dict[str, str]) -> pa.Table:
    esquema = pa.schema(ESQUEMAS_CAMPOS[nombre]).with_metadata(meta)
    ordenadas = sorted(filas, key=_CLAVES_ORDEN[nombre])
    return pa.Table.from_pylist(ordenadas, schema=esquema)


def _escribir_atomico(destino: Path, escribir) -> None:
    tmp = destino.with_name(f".{destino.name}.tmp")
    try:
        escribir(tmp)
        os.replace(tmp, destino)
    finally:
        tmp.unlink(missing_ok=True)


def ejecutar(entrada: Path, salida: Path, manifiesto: Path | None = None,
             cfg: RulesConfig | None = None) -> dict[str, Any]:
    """Corre el pipeline completo y devuelve el contenido de resumen.json."""
    cfg = cfg or RulesConfig()
    salida = _validar_salida(salida)
    manifiesto = manifiesto or entrada / MANIFEST_NOMBRE
    ingesta, archivos = _ingerir(entrada, manifiesto)
    res = harmonize_ingest(ingesta, cfg)

    salida.mkdir(parents=True, exist_ok=True)
    meta = {"rules_version": res.rules_version, "config_fingerprint": res.config_fingerprint}
    parquet_sha: dict[str, str] = {}
    for nombre, archivo in ARCHIVOS_PARQUET.items():
        tabla = _tabla(nombre, getattr(res, nombre), meta)
        destino = salida / archivo
        _escribir_atomico(destino, lambda tmp, t=tabla: pq.write_table(t, tmp, **_ESCRITURA))
        parquet_sha[archivo] = _sha256(destino)

    n_a, n_q, n_d = len(res.aceptados), len(res.cuarentena), len(res.deduplicados)
    resumen = {
        "conteos": {
            "n_input": res.n_input, "aceptados": n_a, "cuarentena": n_q,
            "deduplicados": n_d, "celda_dia": len(res.celda_dia),
        },
        "invariante_ok": res.n_input == n_a + n_q + n_d,
        "rules_version": res.rules_version,
        "config_fingerprint": res.config_fingerprint,
        "archivos_entrada": archivos,
        "parquet_sha256": parquet_sha,
        "cuarentena_por_motivo": dict(sorted(Counter(q["motivo"] for q in res.cuarentena).items())),
    }
    texto = json.dumps(resumen, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    _escribir_atomico(salida / "resumen.json",
                      lambda tmp: tmp.write_text(texto, encoding="utf-8", newline="\n"))
    return resumen


def _imprimir(resumen: dict[str, Any], salida: Path) -> None:
    c = resumen["conteos"]
    print(f"Pipeline {resumen['rules_version']} (config {resumen['config_fingerprint'][:12]})")
    print(f"  entrada:      {c['n_input']}")
    print(f"  aceptados:    {c['aceptados']}")
    print(f"  deduplicados: {c['deduplicados']}")
    print(f"  cuarentena:   {c['cuarentena']}")
    print(f"  celda-día:    {c['celda_dia']}")
    print(f"  invariante:   {'OK' if resumen['invariante_ok'] else 'ROTO'}")
    for motivo, n in resumen["cuarentena_por_motivo"].items():
        print(f"    cuarentena [{n}] {motivo}")
    for archivo, sha in resumen["parquet_sha256"].items():
        print(f"  {archivo}  sha256={sha[:16]}…")
    print(f"Salida en {salida}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harmonize.pipeline", description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="directorio con CSV y manifest.jsonl")
    parser.add_argument("--output", required=True, type=Path, help="directorio de salida (no data/raw)")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="ruta del manifiesto (por defecto INPUT/manifest.jsonl)")
    args = parser.parse_args(argv)
    try:
        resumen = ejecutar(args.input, args.output, args.manifest)
    except SalidaProhibida as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ManifestError, OSError, AssertionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _imprimir(resumen, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
