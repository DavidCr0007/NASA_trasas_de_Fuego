"""Validación por registro de filas crudas FIRMS (D-03).

Solo usa códigos y rangos de ``firms_schema`` (todos "por confirmar" mientras
no se verifiquen contra la fuente oficial). Se devuelve el primer motivo de
rechazo, en el orden: coordenadas, fecha/hora, confianza, satélite, calidad.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ingest import firms_schema as fs

LAT_FUERA = "latitud fuera de rango"
LON_FUERA = "longitud fuera de rango"
COORD_NO_NUMERICA = "coordenada no numérica"
FECHA_INVALIDA = "fecha/hora inválida"
FECHA_POSTERIOR = "fecha posterior a la descarga"
CONFIANZA_FUERA = "confianza fuera de dominio"
SAT_NO_RECONOCIDO = "satélite no reconocido"
SAT_INCONSISTENTE = "satélite inconsistente con la fuente"
CALIDAD_VERSION = "calidad inconsistente con la versión"

COLUMNA_BRILLO = {"MODIS": "brightness", "VIIRS": "bright_ti4"}

_RE_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_RE_HORA = re.compile(r"\d{1,4}", re.ASCII)
_RE_ENTERO = re.compile(r"\d+", re.ASCII)


@dataclass
class ValidationOutcome:
    """``campos`` es None si la fila se rechaza (entonces ``motivo`` no es None)."""

    campos: dict[str, Any] | None
    motivo: str | None
    advertencias: list[str] = field(default_factory=list)


def _num(texto: str | None) -> float | None:
    try:
        return float((texto or "").strip())
    except ValueError:
        return None


def parse_fecha_hora(acq_date: str | None, acq_time: str | None) -> datetime | None:
    """acq_date 'YYYY-MM-DD' y acq_time HHMM (con o sin ceros a la izquierda) -> UTC."""
    fecha = (acq_date or "").strip()
    hora = (acq_time or "").strip()
    if not _RE_FECHA.fullmatch(fecha) or not _RE_HORA.fullmatch(hora):
        return None
    hora = hora.zfill(4)
    h, m = int(hora[:2]), int(hora[2:])
    if h > 23 or m > 59:
        return None
    try:
        base = datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        return None
    return base.replace(hour=h, minute=m, tzinfo=UTC)


def _confianza_valida(sensor: str, valor: str) -> bool:
    if sensor == "MODIS":
        if not _RE_ENTERO.fullmatch(valor):
            return False
        bajo, alto = fs.CONFIANZA_MODIS_RANGO
        return bajo <= int(valor) <= alto
    return valor in fs.CONFIANZA_VIIRS_VALORES


def _version_encaja(version: str, calidad: str) -> bool:
    es_nrt = re.fullmatch(fs.PATRONES_VERSION["NRT"], version) is not None
    if calidad == "NRT":
        return es_nrt
    return (not es_nrt) and re.fullmatch(fs.PATRONES_VERSION["estandar"], version) is not None


def validate_row(
    raw: dict[str, str],
    *,
    fuente: str,
    sensor: str,
    calidad: str,
    fecha_descarga: datetime,
) -> ValidationOutcome:
    adv: list[str] = []

    def rechazo(motivo: str) -> ValidationOutcome:
        return ValidationOutcome(None, motivo, adv)

    # Coordenadas
    lat = _num(raw.get("latitude"))
    lon = _num(raw.get("longitude"))
    if lat is None or lon is None:
        return rechazo(COORD_NO_NUMERICA)
    if not math.isfinite(lat) or not -90.0 <= lat <= 90.0:
        return rechazo(LAT_FUERA)
    if not math.isfinite(lon) or not -180.0 <= lon <= 180.0:
        return rechazo(LON_FUERA)

    # Fecha y hora
    fecha_hora = parse_fecha_hora(raw.get("acq_date"), raw.get("acq_time"))
    if fecha_hora is None:
        return rechazo(FECHA_INVALIDA)
    if fecha_hora > fecha_descarga:
        return rechazo(FECHA_POSTERIOR)

    # Confianza
    confianza = (raw.get("confidence") or "").strip()
    if not _confianza_valida(sensor, confianza):
        return rechazo(CONFIANZA_FUERA)

    # Satélite
    codigo = (raw.get("satellite") or "").strip()
    info = fs.SATELITES.get(codigo)
    if info is None:
        return rechazo(SAT_NO_RECONOCIDO)
    meta = fs.FUENTES_API.get(fuente)
    if info["sensor"] != sensor or (
        meta is not None and info["nombre"] not in meta["satelite"]
    ):
        return rechazo(SAT_INCONSISTENTE)

    # Calidad vs versión
    version = (raw.get("version") or "").strip()
    if not _version_encaja(version, calidad):
        if fs.PATRONES_VERSION_ESTADO != "por confirmar":
            return rechazo(CALIDAD_VERSION)
        adv.append(
            f"{CALIDAD_VERSION} (patrones por confirmar): "
            f"version={version!r}, calidad={calidad}"
        )

    frp = _num(raw.get("frp"))
    brillo = _num(raw.get(COLUMNA_BRILLO[sensor]))
    campos = {
        "satelite_codigo": codigo,
        "satelite": info["nombre"],
        "satelite_confirmado": bool(info.get("confirmado", False)),
        "version": version,
        "lat": lat,
        "lon": lon,
        "fecha_hora_utc": fecha_hora,
        "daynight": (raw.get("daynight") or "").strip(),
        "confianza_raw": confianza,
        "frp": frp if frp is not None and math.isfinite(frp) else None,
        "brillo": brillo if brillo is not None and math.isfinite(brillo) else None,
    }
    return ValidationOutcome(campos, None, adv)
