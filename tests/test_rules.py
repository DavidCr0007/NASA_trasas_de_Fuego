"""Pruebas de las reglas H2: R1 (grilla), R2 (confianza), R3 (deduplicación),
R4 (procedencia), celda-día y D-05 (harmonize_ingest).

Estas pruebas se escribieron ANTES de la implementación (src/harmonize/config.py,
rules.py y pipeline.py). Los umbrales y la ventana son PROVISIONALES.
"""
import itertools
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta

import pytest

from harmonize.config import RULES_VERSION, RulesConfig, config_fingerprint
from harmonize.rules import (
    cell_1km,
    cell_centroid,
    cell_id,
    cell_index,
    celda_dia,
    classify_confidence,
    dedup,
    n_brutos_por_celda_dia,
)
from harmonize.pipeline import HarmonizeResult, harmonize_ingest
from ingest.reader import IngestResult

CFG = RulesConfig()
D = datetime(2026, 8, 1, tzinfo=UTC)


def hora(h, m=0, dias=0):
    return D + timedelta(days=dias, hours=h, minutes=m)


def reg(rid, sensor="VIIRS", calidad="NRT", t=None, lat=2.95, lon=-75.29,
        raw=None, frp=None, satelite=None, fila=1):
    if raw is None:
        raw = "n" if sensor == "VIIRS" else "50"
    if satelite is None:
        satelite = "NOAA-20" if sensor == "VIIRS" else "Terra"
    return {
        "record_id": rid, "fuente": f"{sensor}_{calidad}", "sensor": sensor,
        "satelite_codigo": "X", "satelite": satelite, "satelite_confirmado": False,
        "coleccion": "por confirmar", "version": "v", "calidad": calidad,
        "lat": lat, "lon": lon, "fecha_hora_utc": t or hora(12),
        "daynight": "D", "confianza_raw": raw, "frp": frp, "brillo": None,
        "archivo_origen": "a.csv", "sha256_origen": "ab" * 32,
        "fecha_descarga": datetime(2026, 9, 1, tzinfo=UTC), "fila": fila,
        "sintetico": True,
    }


# --------------------------------------------------------------------- config
def test_config_defaults_y_congelada():
    assert RULES_VERSION == "armonizacion-0.3.0"
    assert CFG.cell_deg == 0.009
    assert CFG.grid_origin == (-90.0, -180.0)
    assert CFG.dedup_window == timedelta(hours=3)
    assert CFG.modis_umbrales == {"nominal": 30, "alta": 80}
    assert CFG.viirs_mapa == {"low": "baja", "nominal": "nominal", "high": "alta", "l": "baja", "n": "nominal", "h": "alta"}
    with pytest.raises(FrozenInstanceError):
        CFG.cell_deg = 1.0


def test_fingerprint_estable_y_sensible_a_cfg():
    assert config_fingerprint(CFG) == config_fingerprint(RulesConfig())
    assert len(config_fingerprint(CFG)) == 64
    base = config_fingerprint(CFG)
    variantes = [
        replace(CFG, cell_deg=0.01),
        replace(CFG, grid_origin=(-90.0, -179.0)),
        replace(CFG, dedup_window=timedelta(hours=2)),
        replace(CFG, modis_umbrales={"nominal": 40, "alta": 80}),
        replace(CFG, viirs_mapa={"l": "baja", "n": "nominal", "h": "nominal"}),
    ]
    huellas = {config_fingerprint(v) for v in variantes}
    assert base not in huellas and len(huellas) == len(variantes)


# ------------------------------------------------------------------------- R1
def test_celda_frontera_exacta():
    cfg = replace(CFG, cell_deg=0.5)  # 0.5 es exacto en binario: sin ruido de float
    assert cell_index(0.0, 0.0, cfg) == (180, 360)
    assert cell_index(0.4999999, 0.4999999, cfg) == (180, 360)
    assert cell_index(0.5, 0.5, cfg) == (181, 361)  # el límite inferior pertenece a la celda
    assert cell_index(-0.0000001, -0.0000001, cfg) == (179, 359)


def test_origen_cae_en_celda_cero():
    assert cell_index(-90.0, -180.0, CFG) == (0, 0)


def test_columnas_alineadas_entre_latitudes():
    lon = -75.29
    cols = {cell_index(lat, lon, CFG)[1] for lat in (-60.0, 0.0, 1.5, 2.95, 3.9, 45.0, 80.0)}
    assert len(cols) == 1  # el prototipo con cos(lat) daba una columna distinta por latitud


def test_filas_alineadas_entre_longitudes():
    filas = {cell_index(2.95, lon, CFG)[0] for lon in (-179.0, -76.7, -75.29, -74.3, 10.0)}
    assert len(filas) == 1


def test_cell_1km_envoltorio_y_separacion_aprox_1km():
    assert cell_1km(2.95, -75.29) == cell_index(2.95, -75.29, CFG)
    a, b = cell_1km(2.95, -75.29), cell_1km(2.9595, -75.29)
    assert b[0] - a[0] == 1


def test_cell_id_y_centroide():
    assert cell_id(10, 20) == "f10_c20"
    lat, lon = cell_centroid(10, 20, CFG)
    assert lat == pytest.approx(-90.0 + 10.5 * 0.009)
    assert lon == pytest.approx(-180.0 + 20.5 * 0.009)
    # el centroide cae dentro de su propia celda
    assert cell_index(lat, lon, CFG) == (10, 20)


# ------------------------------------------------------------------------- R2
@pytest.mark.parametrize("raw,esperado", [
    (29, "baja"), (30, "nominal"), (79, "nominal"), (80, "alta"), (100, "alta"),
    ("29", "baja"), (0, "baja"),
])
def test_umbrales_modis(raw, esperado):
    assert classify_confidence("MODIS", raw, CFG) == esperado


@pytest.mark.parametrize("raw", [-1, 101, "x", None, "", float("nan")])
def test_modis_fuera_de_dominio(raw):
    assert classify_confidence("MODIS", raw, CFG) is None


@pytest.mark.parametrize("raw,esperado", [("l", "baja"), ("n", "nominal"), ("h", "alta"), (" H ", "alta")])
def test_dominio_viirs(raw, esperado):
    assert classify_confidence("VIIRS", raw, CFG) == esperado


@pytest.mark.parametrize("raw", ["z", "", None, "50", "bajo"])
def test_viirs_fuera_de_dominio(raw):
    assert classify_confidence("VIIRS", raw, CFG) is None


def test_sensor_desconocido_no_clasifica():
    assert classify_confidence("LANDSAT", 50, CFG) is None


def test_umbrales_configurables():
    cfg = replace(CFG, modis_umbrales={"nominal": 40, "alta": 90})
    assert classify_confidence("MODIS", 35, cfg) == "baja"
    assert classify_confidence("MODIS", 85, cfg) == "nominal"


# ------------------------------------------------------------------------- R3
def test_viirs_gana_a_modis():
    m = reg("m", "MODIS", t=hora(17), raw="95")  # MODIS con más confianza y más temprano
    v = reg("v", "VIIRS", t=hora(18), raw="l")
    cons, dups = dedup([m, v], CFG)
    assert [r["record_id"] for r in cons] == ["v"]
    assert dups[0]["record_id"] == "m" and dups[0]["dedup_de"] == "v"


def test_estandar_gana_a_nrt():
    nrt = reg("a_nrt", "MODIS", "NRT", t=hora(10), raw="50")  # id menor y hora más temprana
    sp = reg("b_sp", "MODIS", "estandar", t=hora(10, 5), raw="50")
    cons, dups = dedup([nrt, sp], CFG)
    assert [r["record_id"] for r in cons] == ["b_sp"]
    assert dups[0]["record_id"] == "a_nrt"
    assert dups[0]["calidad"] == "NRT"


def test_misma_deteccion_nrt_y_sp_idéntica_hora():
    nrt = reg("z_nrt", "MODIS", "NRT", t=hora(10))
    sp = reg("a_sp", "MODIS", "estandar", t=hora(10))
    cons, _ = dedup([nrt, sp], CFG)
    assert cons[0]["record_id"] == "a_sp"


def test_confianza_mayor_desempata_dentro_del_mismo_sensor():
    a = reg("a", "VIIRS", t=hora(10), raw="n")
    b = reg("b", "VIIRS", t=hora(11), raw="h")
    cons, dups = dedup([a, b], CFG)
    assert cons[0]["record_id"] == "b" and dups[0]["record_id"] == "a"


def test_hora_y_record_id_desempatan_al_final():
    a = reg("a", t=hora(11)); b = reg("b", t=hora(10)); c = reg("c", t=hora(10))
    cons, _ = dedup([a, b, c], CFG)
    assert cons[0]["record_id"] == "b"


def test_dedup_dentro_del_mismo_sensor():
    a = reg("a", "VIIRS", t=hora(10)); b = reg("b", "VIIRS", t=hora(11))
    cons, dups = dedup([a, b], CFG)
    assert len(cons) == 1 and len(dups) == 1


def test_fuera_de_ventana_no_deduplica():
    a = reg("a", t=hora(10)); b = reg("b", t=hora(13, 1))
    cons, dups = dedup([a, b], CFG)
    assert len(cons) == 2 and dups == []


def test_ventana_inclusiva_en_3h_exactas():
    a = reg("a", t=hora(10)); b = reg("b", t=hora(13))
    cons, dups = dedup([a, b], CFG)
    assert len(cons) == 1 and len(dups) == 1


def test_celdas_distintas_no_deduplican():
    a = reg("a", lat=2.95); b = reg("b", lat=3.05)
    cons, dups = dedup([a, b], CFG)
    assert len(cons) == 2 and dups == []


def test_par_que_cruza_la_medianoche_utc_se_deduplica():
    a = reg("a", "MODIS", t=hora(23, 30)); b = reg("b", "VIIRS", t=hora(0, 30, dias=1))
    cons, dups = dedup([a, b], CFG)
    assert [r["record_id"] for r in cons] == ["b"]
    assert dups[0]["delta_t_min"] == pytest.approx(60.0)


def test_contraejemplo_voraz_documentado():
    # A 10:00, B 12:30, C 14:00: C está a 1,5 h de B pero a 4 h del ancla A.
    a = reg("A", t=hora(10)); b = reg("B", t=hora(12, 30)); c = reg("C", t=hora(14))
    cons, dups = dedup([a, b, c], CFG)
    # grupo {A,B} -> representante A (empate de clave; gana la hora más temprana); grupo {C}
    assert [r["record_id"] for r in cons] == ["A", "C"]
    assert [r["record_id"] for r in dups] == ["B"]
    assert dups[0]["dedup_de"] == "A"


def test_campos_de_deduplicado_y_n_fusionados():
    v = reg("v", "VIIRS", t=hora(10)); m1 = reg("m1", "MODIS", t=hora(11)); m2 = reg("m2", "MODIS", t=hora(12, 30))
    solo = reg("s", "VIIRS", t=hora(20))
    cons, dups = dedup([v, m1, m2, solo], CFG)
    por_id = {r["record_id"]: r for r in cons}
    assert por_id["v"]["n_fusionados"] == 2
    assert por_id["s"]["n_fusionados"] == 0
    d = {r["record_id"]: r for r in dups}
    assert d["m1"]["delta_t_min"] == pytest.approx(60.0)
    assert d["m2"]["delta_t_min"] == pytest.approx(150.0)
    assert d["m1"]["motivo"] == "duplicado: misma celda y |Δt| <= 3 h"


def test_dedup_no_modifica_la_entrada():
    a = reg("a"); copia = dict(a)
    dedup([a, reg("b", t=hora(13))], CFG)
    assert a == copia


def test_dedup_independiente_de_permutaciones():
    base = [
        reg("A", "VIIRS", t=hora(10)),
        reg("B", "MODIS", "estandar", t=hora(12, 30), raw="90"),
        reg("C", "MODIS", "NRT", t=hora(14)),
        reg("D", "VIIRS", t=hora(11), lat=3.2),
        reg("E", "MODIS", t=hora(11, 30), lat=3.2),
    ]
    ref = dedup(base, CFG)
    n = 0
    for perm in itertools.permutations(base):
        assert dedup(list(perm), CFG) == ref
        n += 1
    assert n == 120


# ------------------------------------------------------------------------- R4
def test_r4_conserva_procedencia_en_conservados_y_deduplicados():
    m = reg("m", "MODIS", "NRT", t=hora(10), satelite="Aqua")
    v = reg("v", "VIIRS", "estandar", t=hora(11), satelite="NOAA-21")
    cons, dups = dedup([m, v], CFG)
    for r in cons + dups:
        for k in ("sensor", "satelite", "satelite_codigo", "fecha_hora_utc", "calidad",
                  "fuente", "archivo_origen", "sha256_origen", "fecha_descarga", "fila",
                  "coleccion", "version", "confianza_raw", "frp"):
            assert k in r
        assert r["rules_version"] == RULES_VERSION
        assert r["cell_id"] == f"f{r['cell_fila']}_c{r['cell_col']}"
        assert r["confianza_clase"] in ("baja", "nominal", "alta")
        assert r["fecha_hora_utc"].tzinfo is not None
    assert dups[0]["satelite"] == "Aqua" and dups[0]["calidad"] == "NRT"
    assert dups[0]["fecha_hora_utc"] == hora(10)


# ------------------------------------------------------------------ celda-día
def _escenario():
    regs = [
        reg("v1", "VIIRS", "NRT", hora(6), raw="h", frp=5.0, satelite="NOAA-20"),
        reg("m1", "MODIS", "NRT", hora(6, 30), raw="50", frp=3.0),
        reg("m2", "MODIS", "estandar", hora(14), raw="20", frp=2.5, satelite="Aqua"),
        reg("v2", "VIIRS", "NRT", hora(20), raw="n", frp=None, satelite="Suomi NPP"),
        reg("m3", "MODIS", "NRT", hora(10), raw="85", frp=1.0, lat=3.3),
    ]
    cons, dups = dedup(regs, CFG)
    return cons, dups


def test_celda_dia_sumas():
    cons, dups = _escenario()
    brutos = n_brutos_por_celda_dia(cons + dups)
    filas = celda_dia(cons, brutos, CFG)
    assert len(filas) == 2
    f1 = next(f for f in filas if f["n_detecciones"] == 3)
    assert f1["fecha_utc"] == date(2026, 8, 1)
    assert f1["n_brutas"] == 4
    assert (f1["n_modis"], f1["n_viirs"]) == (1, 2)
    assert f1["confianza_max"] == "alta"
    assert f1["frp_max"] == 5.0 and f1["frp_sum"] == 7.5
    assert f1["primera_hora_utc"] == hora(6) and f1["ultima_hora_utc"] == hora(20)
    assert f1["satelites"] == "Aqua,NOAA-20,Suomi NPP"
    assert f1["calidades"] == "NRT,estandar"
    assert f1["centroide_lat"] == pytest.approx(cell_centroid(f1["cell_fila"], f1["cell_col"], CFG)[0])
    assert f1["rules_version"] == RULES_VERSION
    f2 = next(f for f in filas if f["n_detecciones"] == 1)
    assert f2["n_brutas"] == 1 and f2["frp_sum"] == 1.0


def test_celda_dia_frp_todo_nulo():
    cons, dups = dedup([reg("a", frp=None)], CFG)
    f = celda_dia(cons, n_brutos_por_celda_dia(cons + dups), CFG)[0]
    assert f["frp_max"] is None and f["frp_sum"] is None


def test_celda_dia_orden_estable():
    cons, dups = _escenario()
    brutos = n_brutos_por_celda_dia(cons + dups)
    ref = celda_dia(cons, brutos, CFG)
    assert celda_dia(list(reversed(cons)), brutos, CFG) == ref
    claves = [(f["cell_id"], f["fecha_utc"]) for f in ref]
    assert claves == sorted(claves)


# ----------------------------------------------------------------------- D-05
def _ingest(registros, cuarentena=(), extra=0):
    return IngestResult(list(registros), list(cuarentena), len(registros) + len(cuarentena) + extra)


def test_harmonize_ingest_invariante_y_rules_version():
    regs = [
        reg("v1", "VIIRS", t=hora(6)),
        reg("m1", "MODIS", t=hora(7)),            # duplicado de v1
        reg("m2", "MODIS", t=hora(20), raw="150"),  # confianza fuera de dominio
        reg("v2", "VIIRS", t=hora(21), lat=3.3),
    ]
    q_previa = {"archivo_origen": "a.csv", "sha256_origen": "ab" * 32, "fila": 9,
                "motivo": "latitud fuera de rango", "datos_crudos": "{}",
                "fecha_descarga": datetime(2026, 9, 1, tzinfo=UTC)}
    res = harmonize_ingest(_ingest(regs, [q_previa]), CFG)
    assert isinstance(res, HarmonizeResult)
    assert res.n_input == 5
    assert len(res.aceptados) == 2 and len(res.deduplicados) == 1 and len(res.cuarentena) == 2
    assert res.n_input == len(res.aceptados) + len(res.cuarentena) + len(res.deduplicados)
    motivos = {q["motivo"] for q in res.cuarentena}
    assert motivos == {"latitud fuera de rango", "confianza fuera de dominio"}
    assert res.rules_version == RULES_VERSION
    assert res.config_fingerprint == config_fingerprint(CFG)
    for tabla in (res.aceptados, res.deduplicados, res.cuarentena, res.celda_dia):
        assert tabla and all(f["rules_version"] == RULES_VERSION for f in tabla)
    q = next(q for q in res.cuarentena if q["motivo"] == "confianza fuera de dominio")
    assert q["archivo_origen"] == "a.csv" and q["fila"] == 1
    assert json.loads(q["datos_crudos"])["record_id"] == "m2"
    # nada se borra: la cuarentena previa sigue ahí
    assert any(q["fila"] == 9 for q in res.cuarentena)


def test_harmonize_ingest_lanza_assertionerror_si_no_cuadra():
    regs = [reg("v1"), reg("v2", t=hora(20))]
    with pytest.raises(AssertionError, match="invariante"):
        harmonize_ingest(_ingest(regs, extra=1), CFG)


def test_harmonize_ingest_determinista_ante_permutaciones():
    regs = [reg("v1", t=hora(6)), reg("m1", "MODIS", t=hora(7)), reg("v2", t=hora(20), lat=3.3)]
    ref = harmonize_ingest(_ingest(regs), CFG)
    for perm in itertools.permutations(regs):
        r = harmonize_ingest(_ingest(perm), CFG)
        assert (r.aceptados, r.deduplicados, r.cuarentena, r.celda_dia) == \
               (ref.aceptados, ref.deduplicados, ref.cuarentena, ref.celda_dia)


def test_harmonize_ingest_n_brutas_cuenta_antes_de_deduplicar():
    regs = [reg("v1", t=hora(6)), reg("m1", "MODIS", t=hora(7))]
    res = harmonize_ingest(_ingest(regs), CFG)
    assert res.celda_dia[0]["n_detecciones"] == 1 and res.celda_dia[0]["n_brutas"] == 2


# R2 (0.3.0): el mapa VIIRS cubre todo el dominio aceptado por la validación.
def test_viirs_mapa_cubre_el_dominio_confirmado():
    from ingest import firms_schema as fs

    assert set(CFG.viirs_mapa) == set(fs.CONFIANZA_VIIRS_VALORES)
    assert CFG.viirs_mapa["low"] == "baja"
    assert CFG.viirs_mapa["nominal"] == "nominal"
    assert CFG.viirs_mapa["high"] == "alta"
