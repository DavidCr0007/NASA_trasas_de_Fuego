"""Lector FIRMS con procedencia, validación y cuarentena (D-01, D-02, D-04)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ingest import firms_schema as fs
from ingest.manifest import ManifestError, load_manifest, verify_file
from ingest.validate import validate_row

MANIFEST_NOMBRE = "manifest.jsonl"
_VARIANTE_POR_CALIDAD = {"NRT": "api_nrt", "estandar": "api_sp"}


class InvariantError(Exception):
    """entrada != aceptados + cuarentena + deduplicados."""


@dataclass
class FileResult:
    registros: list[dict[str, Any]]
    cuarentena: list[dict[str, Any]]
    n_input: int
    columnas_extra: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)


@dataclass
class IngestResult:
    registros: list[dict[str, Any]]
    cuarentena: list[dict[str, Any]]
    n_input: int
    n_por_archivo: dict[str, int] = field(default_factory=dict)
    columnas_extra: dict[str, list[str]] = field(default_factory=dict)
    advertencias: list[str] = field(default_factory=list)


def parse_utc(texto: str | None) -> datetime:
    """'YYYY-MM-DDTHH:MM:SSZ' -> datetime con tzinfo=UTC."""
    try:
        return datetime.strptime(texto or "", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ManifestError(f"fecha_descarga inválida en el manifiesto: {texto!r}") from exc


def _crudo(cabecera: list[str], fila: list[str]) -> dict[str, Any]:
    if len(fila) == len(cabecera):
        return dict(zip(cabecera, fila))
    return {"_fila_cruda": fila}


def read_file(path: str | Path, entry: dict[str, Any] | None) -> FileResult:
    """Verifica el hash y lee el CSV. Lanza ManifestError si el crudo se alteró."""
    ruta = Path(path)
    if not entry:
        raise ManifestError(f"archivo no está en el manifiesto: {ruta}")
    try:
        verify_file(ruta, entry)
    except OSError as exc:
        raise ManifestError(f"no se puede leer {ruta}: {exc}") from exc

    sha = entry["sha256"]
    archivo = entry["archivo"]
    fecha_descarga = parse_utc(entry.get("fecha_descarga"))
    fuente = entry.get("fuente")
    calidad = entry.get("calidad")
    meta = fs.FUENTES_API.get(fuente or "")
    sensor = entry.get("sensor") or (meta or {}).get("sensor")
    if calidad not in _VARIANTE_POR_CALIDAD:
        raise ManifestError(f"{archivo}: calidad inválida {calidad!r}")
    if sensor not in ("MODIS", "VIIRS"):
        raise ManifestError(f"{archivo}: sensor inválido {sensor!r}")
    variante = entry.get("variante") or _VARIANTE_POR_CALIDAD[calidad]
    requeridas = fs.COLUMNAS_REQUERIDAS.get((sensor, variante))
    if requeridas is None:
        raise ManifestError(f"{archivo}: sin esquema para {(sensor, variante)}")

    registros: list[dict[str, Any]] = []
    cuarentena: list[dict[str, Any]] = []

    def a_cuarentena(fila: int, motivo: str, crudo: dict[str, Any]) -> None:
        cuarentena.append({
            "archivo_origen": archivo,
            "sha256_origen": sha,
            "fila": fila,
            "motivo": motivo,
            "datos_crudos": json.dumps(crudo, sort_keys=True, ensure_ascii=False),
            "fecha_descarga": fecha_descarga,
        })

    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f)
        cabecera = [c.strip() for c in next(lector, [])]
        faltan = [c for c in requeridas if c not in cabecera]
        extras = [c for c in cabecera if c not in requeridas]
        advertencias: list[str] = []
        if extras:
            advertencias.append(f"{archivo}: columnas extra toleradas {extras}")
        motivo_esquema = (
            f"esquema inválido: faltan columnas [{', '.join(faltan)}]" if faltan else None
        )

        n_input = 0
        for fila_cruda in lector:
            if not fila_cruda:  # línea en blanco: no es una fila de datos
                continue
            n_input += 1
            fila = n_input
            crudo = _crudo(cabecera, fila_cruda)
            if motivo_esquema:
                a_cuarentena(fila, motivo_esquema, crudo)
                continue
            if len(fila_cruda) != len(cabecera):
                a_cuarentena(fila, "fila malformada", crudo)
                continue
            salida = validate_row(
                crudo, fuente=fuente or "", sensor=sensor, calidad=calidad,
                fecha_descarga=fecha_descarga,
            )
            advertencias.extend(f"{archivo}:{fila}: {a}" for a in salida.advertencias)
            if salida.campos is None:
                a_cuarentena(fila, salida.motivo or "motivo desconocido", crudo)
                continue
            registros.append({
                "record_id": f"{sha[:16]}:{fila}",
                "fuente": fuente,
                "sensor": sensor,
                "coleccion": entry.get("coleccion"),
                "calidad": calidad,
                "archivo_origen": archivo,
                "sha256_origen": sha,
                "fecha_descarga": fecha_descarga,
                "fila": fila,
                "sintetico": bool(entry.get("sintetico", False)),
                **salida.campos,
            })

    return FileResult(registros, cuarentena, n_input, extras, advertencias)


def read_manifest_dir(directorio: str | Path) -> IngestResult:
    """Lee todos los archivos del manifiesto, ordenados por 'archivo'."""
    base = Path(directorio)
    entradas = load_manifest(base / MANIFEST_NOMBRE)
    if not entradas:
        raise ManifestError(f"manifiesto vacío o inexistente en {base}")

    res = IngestResult([], [], 0)
    for archivo in sorted(entradas):
        parcial = read_file(base / archivo, entradas[archivo])
        res.registros.extend(parcial.registros)
        res.cuarentena.extend(parcial.cuarentena)
        res.n_input += parcial.n_input
        res.n_por_archivo[archivo] = parcial.n_input
        if parcial.columnas_extra:
            res.columnas_extra[archivo] = parcial.columnas_extra
        res.advertencias.extend(parcial.advertencias)
    return res


def check_invariant(resultado: IngestResult, n_dedup: int = 0) -> None:
    """Exige n_input == len(registros) + len(cuarentena) + n_dedup."""
    suma = len(resultado.registros) + len(resultado.cuarentena) + n_dedup
    if resultado.n_input != suma:
        raise InvariantError(
            f"invariante roto: entrada={resultado.n_input} != "
            f"aceptados={len(resultado.registros)} + cuarentena="
            f"{len(resultado.cuarentena)} + deduplicados={n_dedup}"
        )
