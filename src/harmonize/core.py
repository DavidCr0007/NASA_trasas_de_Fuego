"""API heredada del prototipo (datos sintéticos) como adaptador sobre las reglas H2.

Las reglas viven en config.py / rules.py / pipeline.py (armonizacion-0.2.0):
  R1 grilla fija en grados (floor), R2 confianza, R3 deduplicación determinista,
  R4 procedencia. Este módulo conserva `harmonize(rows)`, `validate` y los tipos
  `Detection`/`Result` para las pruebas originales. Los códigos de satélite del
  prototipo (N/1/2, T/A) siguen "por confirmar" (ver ingest.firms_schema).
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime

from .config import RULES_VERSION
from .rules import DEFAULT_CFG, cell_1km, classify_confidence, dedup

# Constantes heredadas (PROVISIONALES / por confirmar).
MODIS_CONF_THRESHOLDS = DEFAULT_CFG.modis_umbrales
VIIRS_CLASS_MAP = DEFAULT_CFG.viirs_mapa
VIIRS_SATS = {"N": "Suomi NPP", "1": "NOAA-20", "2": "NOAA-21"}
MODIS_SATS = {"T": "Terra", "A": "Aqua"}


@dataclass
class Detection:
    sensor: str          # "MODIS" | "VIIRS"
    satellite: str
    lat: float
    lon: float
    when_utc: datetime
    confidence_raw: object
    frp: float | None = None
    confidence: str | None = None
    cell: tuple[int, int] | None = None


@dataclass
class Result:
    accepted: list[Detection] = field(default_factory=list)
    quarantine: list[tuple[dict, str]] = field(default_factory=list)
    n_input: int = 0
    n_dedup_removed: int = 0


def validate(raw: dict) -> tuple[Detection | None, str | None]:
    try:
        sensor = raw["sensor"]
        if sensor not in ("MODIS", "VIIRS"):
            return None, "sensor desconocido"
        lat, lon = float(raw["lat"]), float(raw["lon"])
        if not -90 <= lat <= 90:
            return None, "latitud fuera de rango"
        if not -180 <= lon <= 180:
            return None, "longitud fuera de rango"
        when = datetime.fromisoformat(raw["when_utc"])
        sat = str(raw["satellite"])
        allowed = VIIRS_SATS if sensor == "VIIRS" else MODIS_SATS
        if sat not in allowed:
            return None, "satélite no reconocido"
        conf = classify_confidence(sensor, raw.get("confidence"))
        if conf is None:
            return None, "confianza fuera de dominio"
        det = Detection(sensor, sat, lat, lon, when, raw.get("confidence"),
                        frp=raw.get("frp"), confidence=conf, cell=cell_1km(lat, lon))
        return det, None
    except (KeyError, ValueError, TypeError) as e:
        return None, f"campo inválido: {type(e).__name__}"


def harmonize(rows: list[dict]) -> Result:
    res = Result(n_input=len(rows))
    valid: list[Detection] = []
    for r in rows:
        det, why = validate(r)
        if det is None:
            res.quarantine.append((r, why))
        else:
            valid.append(det)
    # R3 deduplicación: ordenar para que el resultado no dependa del orden de entrada
    # Adaptador: R3 nueva (ventana anclada, determinista). El record_id se deriva
    # del contenido para que el resultado no dependa del orden de entrada.
    pendientes: dict[str, list[Detection]] = {}
    registros = []
    for d in valid:
        contenido = json.dumps(
            [d.sensor, d.satellite, d.lat, d.lon, d.when_utc.isoformat(),
             str(d.confidence_raw), d.frp], default=str)
        rid = hashlib.sha256(contenido.encode()).hexdigest()[:16]
        pendientes.setdefault(rid, []).append(d)
        registros.append({
            "record_id": rid, "sensor": d.sensor, "satelite": d.satellite,
            "calidad": "estandar",  # el prototipo no distingue NRT/estándar
            "lat": d.lat, "lon": d.lon, "fecha_hora_utc": d.when_utc,
            "confianza_raw": d.confidence_raw, "frp": d.frp,
        })
    conservados, deduplicados = dedup(registros, DEFAULT_CFG)
    res.accepted = [pendientes[r["record_id"]].pop(0) for r in conservados]
    res.n_dedup_removed = len(deduplicados)
    return res