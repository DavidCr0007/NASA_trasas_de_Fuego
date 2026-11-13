"""Prototipo de armonización MODIS/VIIRS (datos sintéticos).

Reglas (versión 0.1.0):
  R1 grilla de ~1 km por celda (aproximación plana local)
  R2 confianza en clases baja / nominal / alta (umbrales PROVISIONALES)
  R3 deduplicación: mismo día, misma celda, |Δt| <= 3 h -> conserva VIIRS
  R4 registros con horario UTC y satélite conservados
  D-03/D-04 validación de esquema y cuarentena con motivo
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

RULES_VERSION = "armonizacion-0.1.0"
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQ = 111.320
DEDUP_WINDOW = timedelta(hours=3)

# Umbrales provisionales: deben validarse con documentación del producto.
MODIS_CONF_THRESHOLDS = {"nominal": 30, "alta": 80}   # 0-100 %
VIIRS_CLASS_MAP = {"l": "baja", "n": "nominal", "h": "alta"}  # clases tipo FIRMS (por confirmar)
VIIRS_SATS = {"N": "Suomi NPP", "1": "NOAA-20", "2": "NOAA-21"}
MODIS_SATS = {"T": "Terra", "A": "Aqua"}


def cell_1km(lat: float, lon: float) -> tuple[int, int]:
    """Índice de celda de ~1 km. Aproximación plana: válida para áreas pequeñas."""
    y = math.floor(lat * KM_PER_DEG_LAT)
    x = math.floor(lon * KM_PER_DEG_LON_EQ * math.cos(math.radians(lat)))
    return (y, x)


def classify_confidence(sensor: str, raw) -> str | None:
    if sensor == "MODIS":
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
        if not 0 <= v <= 100:
            return None
        if v >= MODIS_CONF_THRESHOLDS["alta"]:
            return "alta"
        if v >= MODIS_CONF_THRESHOLDS["nominal"]:
            return "nominal"
        return "baja"
    if sensor == "VIIRS":
        return VIIRS_CLASS_MAP.get(str(raw).strip().lower())
    return None


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
    valid.sort(key=lambda d: (d.cell, d.when_utc, d.sensor != "VIIRS", d.satellite))
    kept: list[Detection] = []
    for d in valid:
        dup = None
        for k in reversed(kept):
            if k.cell != d.cell:
                continue
            if abs(k.when_utc - d.when_utc) <= DEDUP_WINDOW:
                dup = k
                break
        if dup is None:
            kept.append(d)
        else:
            res.n_dedup_removed += 1
            # Prioridad VIIRS (mejor resolución); si ambos son del mismo sensor, se conserva el primero
            if d.sensor == "VIIRS" and dup.sensor == "MODIS":
                kept[kept.index(dup)] = d
    res.accepted = kept
    return res