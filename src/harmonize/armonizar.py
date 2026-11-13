"""D-05: armonización completa de un IngestResult (H1) con las reglas R1-R4."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .config import RULES_VERSION, RulesConfig, config_fingerprint
from .rules import (
    DEFAULT_CFG,
    celda_dia,
    dedup,
    enriquecer,
    n_brutos_por_celda_dia,
)

MOTIVO_CONFIANZA = "confianza fuera de dominio"


@dataclass
class HarmonizeResult:
    aceptados: list[dict[str, Any]] = field(default_factory=list)
    cuarentena: list[dict[str, Any]] = field(default_factory=list)
    deduplicados: list[dict[str, Any]] = field(default_factory=list)
    celda_dia: list[dict[str, Any]] = field(default_factory=list)
    n_input: int = 0
    rules_version: str = RULES_VERSION
    config_fingerprint: str = ""


def _a_cuarentena(registro: dict, motivo: str) -> dict:
    """Fila de cuarentena con el mismo contrato de H1 (nada se borra)."""
    return {
        "archivo_origen": registro.get("archivo_origen"),
        "sha256_origen": registro.get("sha256_origen"),
        "fila": registro.get("fila"),
        "motivo": motivo,
        "datos_crudos": json.dumps(registro, sort_keys=True, ensure_ascii=False, default=str),
        "fecha_descarga": registro.get("fecha_descarga"),
        "rules_version": RULES_VERSION,
    }


def _clave_cuarentena(q: dict) -> tuple:
    fila = q.get("fila")
    return (str(q.get("archivo_origen") or ""), fila if isinstance(fila, int) else -1,
            q.get("motivo") or "", q.get("datos_crudos") or "")


def harmonize_ingest(ingest_result, cfg: RulesConfig = DEFAULT_CFG) -> HarmonizeResult:
    """Clasifica, deduplica y agrega. Lanza AssertionError si el invariante falla."""
    cuarentena = [{**q, "rules_version": RULES_VERSION} for q in ingest_result.cuarentena]
    candidatos: list[dict] = []
    for r in ingest_result.registros:
        e = enriquecer(r, cfg)
        if e["confianza_clase"] is None:
            cuarentena.append(_a_cuarentena(r, MOTIVO_CONFIANZA))
        else:
            candidatos.append(e)

    conservados, deduplicados = dedup(candidatos, cfg)
    brutos = n_brutos_por_celda_dia(conservados + deduplicados)
    agregado = celda_dia(conservados, brutos, cfg, deduplicados)
    cuarentena.sort(key=_clave_cuarentena)

    n_ok = len(conservados) + len(cuarentena) + len(deduplicados)
    if ingest_result.n_input != n_ok:
        raise AssertionError(
            "invariante roto: n_input="
            f"{ingest_result.n_input} != aceptados({len(conservados)}) + "
            f"cuarentena({len(cuarentena)}) + deduplicados({len(deduplicados)}) = {n_ok}"
        )
    return HarmonizeResult(
        aceptados=conservados, cuarentena=cuarentena, deduplicados=deduplicados,
        celda_dia=agregado, n_input=ingest_result.n_input, rules_version=RULES_VERSION,
        config_fingerprint=config_fingerprint(cfg),
    )
