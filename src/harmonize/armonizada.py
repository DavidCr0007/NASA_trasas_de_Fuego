"""H8-02 (O2): métrica armonizada «celdas activas equivalentes» (ADR 0011).

Problema: el conteo de detecciones crece con el número de satélites y con la resolución
(VIIRS 375 m detecta varios píxeles por celda de 1 km). Con datos reales del Huila, la
entrada de NOAA-20 en 2018 casi duplica el conteo anual sin que haya más fuego.

Métrica diaria: número de **celdas de ~1 km** con al menos una detección de la
**constelación de referencia** R = MODIS (Terra, Aqua) ∪ Suomi NPP. Contar celdas (no
píxeles) elimina el efecto de resolución; fijar R elimina los saltos de constelación.

Fuera de la era de R se usan factores estimados donde las fuentes se superponen:
- era solo MODIS (antes de Suomi NPP): MODIS × k_M[mes], con
  k_M[mes] = Σ R / Σ MODIS en los días de la era Suomi NPP de ese mes del año;
- después de Suomi NPP: (MODIS ∪ NOAA-20) / k_N20, con
  k_N20 = Σ (MODIS ∪ NOAA-20) / Σ R en los días en que ambas eras coinciden.

Los factores se estiman sobre **todo el conjunto procesado** (más muestra que un área) y se
informan con sus años y su número de días.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

VERSION_METRICA = "celdas-eq-1.0.0"
MODIS = frozenset({"Terra", "Aqua"})
REFERENCIA = MODIS | {"Suomi NPP"}
MODIS_N20 = MODIS | {"NOAA-20"}
MIN_CELDAS_MES = 30  # por debajo, el factor mensual usa el global


def contar_por_dia(registros) -> dict[date, dict[str, int]]:
    """registros: iterable de (fecha_utc, cell_id, satelite) de TODAS las detecciones aceptadas
    (representantes y deduplicadas). Devuelve, por día, celdas distintas por grupo."""
    celdas: dict[date, dict[str, set]] = defaultdict(lambda: {"ref": set(), "modis": set(), "mn20": set(),
                                                             "snpp": set(), "n20": set()})
    for fecha, cell, sat in registros:
        c = celdas[fecha]
        if sat in REFERENCIA:
            c["ref"].add(cell)
        if sat in MODIS:
            c["modis"].add(cell)
        if sat in MODIS_N20:
            c["mn20"].add(cell)
        if sat == "Suomi NPP":
            c["snpp"].add(cell)
        if sat == "NOAA-20":
            c["n20"].add(cell)
    return {f: {k: len(v) for k, v in c.items()} for f, c in celdas.items()}


def eras(conteos: dict[date, dict[str, int]]) -> dict[str, tuple[date, date] | None]:
    """Primer y último día con datos de Suomi NPP y de NOAA-20 en el conjunto."""
    def rango(clave):
        dias = [f for f, c in conteos.items() if c.get(clave, 0) > 0]
        return (min(dias), max(dias)) if dias else None
    return {"snpp": rango("snpp"), "n20": rango("n20")}


def _en(era, f: date) -> bool:
    return era is not None and era[0] <= f <= era[1]


def factores(conteos: dict[date, dict[str, int]], e: dict) -> dict:
    ref_mes: dict[int, int] = defaultdict(int)
    mod_mes: dict[int, int] = defaultdict(int)
    anios = set()
    sum_mn20 = sum_ref_n20 = n_dias_n20 = 0
    for f, c in conteos.items():
        if _en(e["snpp"], f):
            ref_mes[f.month] += c["ref"]
            mod_mes[f.month] += c["modis"]
            anios.add(f.year)
            if _en(e["n20"], f):
                sum_mn20 += c["mn20"]
                sum_ref_n20 += c["ref"]
                n_dias_n20 += 1
    tot_ref, tot_mod = sum(ref_mes.values()), sum(mod_mes.values())
    k_global = tot_ref / tot_mod if tot_mod else None
    k_m = {}
    for m in range(1, 13):
        if mod_mes[m] >= MIN_CELDAS_MES:
            k_m[m] = ref_mes[m] / mod_mes[m]
        else:
            k_m[m] = k_global
    # Los días sin focos no cuentan en n_dias (solo los presentes en conteos).
    if e["snpp"] and e["n20"]:
        ini = max(e["snpp"][0], e["n20"][0])
        fin = min(e["snpp"][1], e["n20"][1])
        n_dias_n20 = (fin - ini).days + 1 if fin >= ini else 0
    return {
        "k_m": k_m,
        "k_m_global": k_global,
        "k_n20": (sum_mn20 / sum_ref_n20) if sum_ref_n20 else None,
        "anios_superposicion_modis": sorted(anios),
        "n_dias_superposicion_n20": n_dias_n20,
        "celdas_ref_superposicion": tot_ref,
        "celdas_modis_superposicion": tot_mod,
    }


def serie_armonizada(conteos: dict[date, dict[str, int]], f: dict, e: dict) -> dict[date, tuple[float, str]]:
    """Valor armonizado y método por día (solo días presentes en ``conteos``)."""
    salida = {}
    for dia, c in conteos.items():
        if _en(e["snpp"], dia):
            salida[dia] = (float(c["ref"]), "referencia")
        elif e["snpp"] and dia > e["snpp"][1] and f.get("k_n20"):
            salida[dia] = (round(c["mn20"] / f["k_n20"], 4), "NOAA-20 calibrado")
        else:
            k = (f.get("k_m") or {}).get(dia.month) or f.get("k_m_global") or 1.0
            salida[dia] = (round(c["modis"] * k, 4), "MODIS calibrado")
    return salida


def metodo_del_dia(dia: date, f: dict, e: dict) -> str:
    if _en(e["snpp"], dia):
        return "referencia"
    if e["snpp"] and dia > e["snpp"][1] and f.get("k_n20"):
        return "NOAA-20 calibrado"
    return "MODIS calibrado"
