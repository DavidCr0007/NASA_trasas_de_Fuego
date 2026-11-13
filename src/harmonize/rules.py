"""Reglas H2: R1 grilla fija, R2 confianza, R3 deduplicación, R4 procedencia, celda-día.

Todas las funciones son puras y deterministas: el resultado no depende del
orden de la entrada (salidas ordenadas de forma estable).
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any

from .config import RULES_VERSION, RulesConfig

DEFAULT_CFG = RulesConfig()
RANGO_CONFIANZA = {"baja": 0, "nominal": 1, "alta": 2}
CLASE_POR_RANGO = {v: k for k, v in RANGO_CONFIANZA.items()}
MOTIVO_DUPLICADO = "duplicado: misma celda y |Δt| <= 3 h"


# ------------------------------------------------------------------ R1 grilla
def cell_index(lat: float, lon: float, cfg: RulesConfig = DEFAULT_CFG) -> tuple[int, int]:
    """(fila, col) = (floor((lat-lat0)/cell_deg), floor((lon-lon0)/cell_deg)).

    Grilla fija en grados: las columnas son iguales para todas las latitudes.
    Un punto exactamente en un límite pertenece a la celda de índice mayor.
    Con valores no representables en binario, un punto a ~1e-12 del límite
    puede caer en la celda vecina (redondeo de coma flotante).
    """
    lat0, lon0 = cfg.grid_origin
    return (math.floor((lat - lat0) / cfg.cell_deg), math.floor((lon - lon0) / cfg.cell_deg))


def cell_id(fila: int, col: int) -> str:
    return f"f{fila}_c{col}"


def cell_centroid(fila: int, col: int, cfg: RulesConfig = DEFAULT_CFG) -> tuple[float, float]:
    """Centroide (lat, lon) de la celda."""
    lat0, lon0 = cfg.grid_origin
    return (lat0 + (fila + 0.5) * cfg.cell_deg, lon0 + (col + 0.5) * cfg.cell_deg)


def cell_1km(lat: float, lon: float) -> tuple[int, int]:
    """Envoltorio heredado: índice (fila, col) con la configuración por defecto."""
    return cell_index(lat, lon, DEFAULT_CFG)


# ---------------------------------------------------------------- R2 confianza
def classify_confidence(sensor: str, raw: Any, cfg: RulesConfig = DEFAULT_CFG) -> str | None:
    """'baja' | 'nominal' | 'alta' | None (fuera de dominio). Umbrales PROVISIONALES."""
    if sensor == "MODIS":
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
        if not 0 <= v <= 100:  # NaN también cae aquí
            return None
        if v >= cfg.modis_umbrales["alta"]:
            return "alta"
        if v >= cfg.modis_umbrales["nominal"]:
            return "nominal"
        return "baja"
    if sensor == "VIIRS":
        if raw is None:
            return None
        return cfg.viirs_mapa.get(str(raw).strip().lower())
    return None


# ------------------------------------------------------- enriquecimiento (R1+R2)
def enriquecer(registro: dict, cfg: RulesConfig = DEFAULT_CFG) -> dict:
    """Copia del registro con confianza_clase, cell_id/fila/col y rules_version."""
    r = dict(registro)
    fila, col = cell_index(r["lat"], r["lon"], cfg)
    r["confianza_clase"] = classify_confidence(r["sensor"], r.get("confianza_raw"), cfg)
    r["cell_fila"], r["cell_col"], r["cell_id"] = fila, col, cell_id(fila, col)
    r["rules_version"] = RULES_VERSION
    return r


# ----------------------------------------------------------- R3 deduplicación
def _clave_representante(r: dict) -> tuple:
    return (
        r["sensor"] != "VIIRS",
        r["calidad"] != "estandar",
        -RANGO_CONFIANZA.get(r["confianza_clase"], -1),
        r["fecha_hora_utc"],
        r["record_id"],
    )


def _clave_orden(r: dict) -> tuple:
    return (r["cell_id"], r["fecha_hora_utc"], r["record_id"])


def dedup(registros: list[dict], cfg: RulesConfig = DEFAULT_CFG) -> tuple[list[dict], list[dict]]:
    """Deduplicación determinista -> (conservados, deduplicados).

    1. Orden por (cell_id, fecha_hora_utc, record_id).
    2. En cada celda, el primer registro sin asignar ancla un grupo en t0; el
       grupo incluye todos los registros con t <= t0 + ventana (puede cruzar la
       medianoche UTC). Voraz y no transitivo: ver docs/limitaciones.md.
    3. Representante = mínimo de (sensor != VIIRS, calidad != estandar,
       -rango_confianza, fecha_hora_utc, record_id).
    4. El resto va a deduplicados con dedup_de, delta_t_min y motivo.
    También se aplica entre registros del mismo sensor (a propósito).
    Los registros se enriquecen (copia) si les falta cell_id/confianza_clase.
    """
    ordenados = sorted(
        (r if "cell_id" in r and "confianza_clase" in r else enriquecer(r, cfg) for r in registros),
        key=_clave_orden,
    )
    ordenados = [{**r, "rules_version": RULES_VERSION} for r in ordenados]
    por_celda: dict[str, list[dict]] = defaultdict(list)
    for r in ordenados:
        por_celda[r["cell_id"]].append(r)

    conservados: list[dict] = []
    deduplicados: list[dict] = []
    for celda in sorted(por_celda):
        regs = por_celda[celda]
        i = 0
        while i < len(regs):
            limite = regs[i]["fecha_hora_utc"] + cfg.dedup_window
            j = i
            while j < len(regs) and regs[j]["fecha_hora_utc"] <= limite:
                j += 1
            grupo = regs[i:j]
            rep = min(grupo, key=_clave_representante)
            otros = [g for g in grupo if g is not rep]
            conservados.append({**rep, "n_fusionados": len(otros)})
            for g in otros:
                delta = abs(g["fecha_hora_utc"] - rep["fecha_hora_utc"]).total_seconds() / 60.0
                deduplicados.append({
                    **g, "dedup_de": rep["record_id"], "delta_t_min": delta,
                    "motivo": MOTIVO_DUPLICADO,
                })
            i = j
    conservados.sort(key=_clave_orden)
    deduplicados.sort(key=_clave_orden)
    return conservados, deduplicados


# ------------------------------------------------------------------ celda-día
def n_brutos_por_celda_dia(registros: list[dict]) -> dict[tuple[str, date], int]:
    """Cuenta registros aceptados (antes de deduplicar) por (cell_id, fecha_utc)."""
    cuenta: dict[tuple[str, date], int] = defaultdict(int)
    for r in registros:
        cuenta[(r["cell_id"], r["fecha_hora_utc"].date())] += 1
    return dict(cuenta)


def celda_dia(conservados: list[dict], n_brutos_por_celda_dia: dict,
              cfg: RulesConfig = DEFAULT_CFG) -> list[dict]:
    """Agrega los conservados por (cell_id, fecha_utc). Ordenado por esa clave."""
    grupos: dict[tuple[str, date], list[dict]] = defaultdict(list)
    for r in conservados:
        grupos[(r["cell_id"], r["fecha_hora_utc"].date())].append(r)
    filas = []
    for (cid, fecha) in sorted(grupos):
        g = grupos[(cid, fecha)]
        frps = [r["frp"] for r in g if r.get("frp") is not None]
        horas = [r["fecha_hora_utc"] for r in g]
        fila, col = g[0]["cell_fila"], g[0]["cell_col"]
        clat, clon = cell_centroid(fila, col, cfg)
        filas.append({
            "cell_id": cid,
            "fecha_utc": fecha,
            "cell_fila": fila,
            "cell_col": col,
            "n_detecciones": len(g),
            "n_brutas": n_brutos_por_celda_dia.get((cid, fecha), len(g)),
            "n_modis": sum(1 for r in g if r["sensor"] == "MODIS"),
            "n_viirs": sum(1 for r in g if r["sensor"] == "VIIRS"),
            "confianza_max": CLASE_POR_RANGO[max(RANGO_CONFIANZA[r["confianza_clase"]] for r in g)],
            "frp_max": max(frps) if frps else None,
            "frp_sum": float(sum(sorted(frps))) if frps else None,
            "primera_hora_utc": min(horas),
            "ultima_hora_utc": max(horas),
            "satelites": ",".join(sorted({r["satelite"] for r in g})),
            "calidades": ",".join(sorted({r["calidad"] for r in g})),
            "centroide_lat": clat,
            "centroide_lon": clon,
            "rules_version": RULES_VERSION,
        })
    return filas
