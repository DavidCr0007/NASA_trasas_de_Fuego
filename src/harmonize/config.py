"""Configuración versionada de las reglas de armonización (H2).

Todos los valores marcados PROVISIONAL son supuestos de trabajo, no hechos
verificados contra la documentación oficial de FIRMS (ver docs/decisiones/ y
docs/limitaciones.md). Cambiar la configuración cambia `config_fingerprint`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta

from ingest import firms_schema as fs

RULES_VERSION = "armonizacion-0.3.1"  # 0.3.1: celda-día no pierde brutas; 0.3.0: R2 low/nominal/high

# Estado de cada parámetro (para informes y metadatos).
ESTADO_PARAMETROS = {
    "cell_deg": "PROVISIONAL (ADR 0001): 0.009° ≈ 1 km en latitud",
    "grid_origin": "PROVISIONAL (ADR 0001): origen (-90, -180)",
    "dedup_window": "PROVISIONAL (ADR 0003): 3 h",
    "modis_umbrales": "PROVISIONAL (ADR 0002): cortes 30 y 80 por confirmar",
    "viirs_mapa": "CONFIRMADO low/nominal/high (tabla oficial FIRMS); l/n/h por confirmar en API",
}

# Clase de cada valor de confianza VIIRS. low/nominal/high: tabla oficial de atributos
# FIRMS y CSV reales (2026-11-13). l/n/h: variante por confirmar en la API area (R-23).
# Solo se usa para los valores que firms_schema declara como dominio.
_CLASE_POR_INICIAL = {
    "low": "baja", "nominal": "nominal", "high": "alta",
    "l": "baja", "n": "nominal", "h": "alta",
}


def viirs_mapa_desde_esquema() -> dict[str, str]:
    """Mapa VIIRS derivado del dominio declarado en ingest.firms_schema.

    Se deriva de CONFIANZA_VIIRS_VALORES, sin añadir valores propios.
    """
    return {v: _CLASE_POR_INICIAL[v] for v in fs.CONFIANZA_VIIRS_VALORES if v in _CLASE_POR_INICIAL}


@dataclass(frozen=True)
class RulesConfig:
    """Parámetros de las reglas R1-R3. Congelado (los dicts no deben mutarse)."""

    cell_deg: float = 0.009                       # PROVISIONAL
    grid_origin: tuple[float, float] = (-90.0, -180.0)  # (lat, lon)
    dedup_window: timedelta = timedelta(hours=3)  # PROVISIONAL
    modis_umbrales: dict = field(default_factory=lambda: {"nominal": 30, "alta": 80})  # PROVISIONAL
    viirs_mapa: dict = field(default_factory=viirs_mapa_desde_esquema)  # PROVISIONAL


def config_fingerprint(cfg: RulesConfig) -> str:
    """SHA-256 de un JSON canónico de la configuración."""
    canon = {
        "cell_deg": cfg.cell_deg,
        "grid_origin": list(cfg.grid_origin),
        "dedup_window_s": cfg.dedup_window.total_seconds(),
        "modis_umbrales": dict(cfg.modis_umbrales),
        "viirs_mapa": dict(cfg.viirs_mapa),
    }
    texto = json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
