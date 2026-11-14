"""H8-02 (O2): métrica armonizada «celdas activas equivalentes» e intercalibración."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from harmonize.armonizada import (
    VERSION_METRICA,
    contar_por_dia,
    eras,
    factores,
    serie_armonizada,
)


def _dias(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def test_varias_detecciones_en_la_misma_celda_cuentan_una_vez():
    regs = [(date(2020, 1, 1), "c1", "Suomi NPP")] * 3 + [(date(2020, 1, 1), "c1", "Terra")]
    c = contar_por_dia(regs)
    assert c[date(2020, 1, 1)]["ref"] == 1 and c[date(2020, 1, 1)]["modis"] == 1


def test_agregar_noaa20_no_cambia_la_metrica_en_la_era_de_referencia():
    base = [(d, f"c{d.day}", "Suomi NPP") for d in _dias(date(2019, 1, 1), date(2019, 1, 31))]
    extra = [(d, f"x{d.day}", "NOAA-20") for d in _dias(date(2019, 1, 1), date(2019, 1, 31))]
    c1, c2 = contar_por_dia(base), contar_por_dia(base + extra)
    e = {"snpp": (date(2012, 1, 20), date(2025, 12, 31)), "n20": (date(2018, 1, 5), date(2025, 12, 31))}
    f = {"k_m": {m: 2.0 for m in range(1, 13)}, "k_n20": 1.5}
    s1 = serie_armonizada(c1, f, e)
    s2 = serie_armonizada(c2, f, e)
    assert {k: v[0] for k, v in s1.items()} == {k: v[0] for k, v in s2.items()}
    assert all(v[1] == "referencia" for v in s2.values())


def test_era_solo_modis_se_escala_por_mes():
    regs = [(date(2005, 3, 1), "a", "Terra"), (date(2005, 3, 1), "b", "Aqua")]
    e = {"snpp": (date(2012, 1, 20), date(2025, 12, 31)), "n20": None}
    f = {"k_m": {**{m: 1.0 for m in range(1, 13)}, 3: 2.5}, "k_n20": None}
    s = serie_armonizada(contar_por_dia(regs), f, e)
    assert s[date(2005, 3, 1)] == (5.0, "MODIS calibrado")


def test_tras_snpp_se_usa_noaa20_calibrado():
    regs = [(date(2026, 2, 1), "a", "NOAA-20"), (date(2026, 2, 1), "b", "Terra"), (date(2026, 2, 1), "z", "NOAA-21")]
    e = {"snpp": (date(2012, 1, 20), date(2025, 12, 31)), "n20": (date(2018, 1, 5), date(2026, 2, 1))}
    s = serie_armonizada(contar_por_dia(regs), {"k_m": {}, "k_n20": 2.0}, e)
    assert s[date(2026, 2, 1)] == (1.0, "NOAA-20 calibrado")  # (MODIS ∪ NOAA-20) = 2 celdas / 2,0


def test_factores_se_estiman_en_la_superposicion():
    regs = []
    for d in _dias(date(2019, 1, 1), date(2019, 12, 31)):
        regs += [(d, "m", "Terra"), (d, "v1", "Suomi NPP"), (d, "v2", "Suomi NPP")]  # ref = 3, modis = 1
        regs += [(d, "n", "NOAA-20")]  # MODIS ∪ NOAA-20 = 2
    c = contar_por_dia(regs)
    e = eras(c)
    f = factores(c, e)
    assert f["k_m"][6] == pytest.approx(3.0)
    assert f["k_n20"] == pytest.approx(2 / 3)
    assert f["anios_superposicion_modis"] == [2019]
    assert f["n_dias_superposicion_n20"] == 365


def test_eras_desde_los_datos():
    regs = [(date(2012, 1, 20), "a", "Suomi NPP"), (date(2025, 12, 31), "b", "Suomi NPP"),
            (date(2018, 1, 5), "c", "NOAA-20"), (date(2005, 1, 1), "d", "Terra")]
    e = eras(contar_por_dia(regs))
    assert e["snpp"] == (date(2012, 1, 20), date(2025, 12, 31))
    assert e["n20"] == (date(2018, 1, 5), date(2018, 1, 5))


def test_mes_sin_muestra_usa_factor_global():
    regs = [(d, "m", "Terra") for d in _dias(date(2019, 6, 1), date(2019, 6, 30))]
    regs += [(d, "v", "Suomi NPP") for d in _dias(date(2019, 6, 1), date(2019, 6, 30))]
    f = factores(contar_por_dia(regs), eras(contar_por_dia(regs)))
    assert f["k_m"][1] == f["k_m_global"] == pytest.approx(2.0)


def test_version_declarada():
    assert VERSION_METRICA == "celdas-eq-1.0.0"
