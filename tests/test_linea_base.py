"""R5: línea base por día del año, días inusuales, periodos críticos y climatología."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from harmonize.linea_base import (
    calcular,
    clave_dia,
    climatologia_mensual,
    percentil_lineal,
    periodos_inusuales,
)


def _rango(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


# ------------------------------------------------------------- utilidades
@pytest.mark.parametrize("valores,p,esperado", [
    ([1, 2, 3, 4, 5], 50, 3.0),
    ([1, 2, 3, 4, 5], 95, 4.8),          # 0.95 * 4 = 3.8 -> 4 + 0.8 * (5 - 4)
    ([0, 0, 0, 10], 95, 8.5),
    ([7], 95, 7.0),
    ([3, 1, 2], 0, 1.0),
    ([3, 1, 2], 100, 3.0),
])
def test_percentil_lineal(valores, p, esperado):
    assert percentil_lineal(valores, p) == pytest.approx(esperado)


def test_percentil_vacio_falla():
    with pytest.raises(ValueError):
        percentil_lineal([], 95)


def test_29_febrero_cuenta_como_28():
    assert clave_dia(date(2024, 2, 29)) == clave_dia(date(2023, 2, 28)) == (2, 28)
    assert clave_dia(date(2024, 3, 1)) == (3, 1)


# ------------------------------------------------------------- calcular
def _serie_constante(anios, valor=1):
    return {d: valor for a in anios for d in _rango(date(a, 1, 1), date(a, 12, 31))}


def test_dia_inusual_se_detecta_y_el_propio_anio_se_excluye():
    serie = _serie_constante(range(2019, 2026), valor=2)
    serie[date(2025, 8, 15)] = 9
    res = calcular(serie, percentil=95, anios_minimos=5, ventana_dias=0)
    dia = res.dias[date(2025, 8, 15)]
    # Referencia: los otros 6 años valen 2 -> umbral 2; 9 > 2 -> inusual.
    assert dia.umbral == pytest.approx(2.0)
    assert dia.n_anios == 6
    assert dia.inusual is True
    # En los otros años, la referencia incluye el 9 de 2025 pero el P95 de seis valores
    # [2, 2, 2, 2, 2, 9] es 7.25: 2 no supera el umbral.
    otro = res.dias[date(2020, 8, 15)]
    assert otro.umbral == pytest.approx(7.25) and otro.inusual is False


def test_dias_sin_foco_valen_cero_dentro_de_la_cobertura():
    serie = {date(a, 6, 1): 3 for a in range(2019, 2026)}  # solo un día por año con focos
    res = calcular(serie, percentil=95, anios_minimos=5, ventana_dias=0)
    # Cobertura: 2019-06-01 .. 2025-06-01; el 2 de junio vale 0 en todos los años cubiertos.
    assert res.dias[date(2022, 6, 2)].valor == 0
    assert res.dias[date(2022, 6, 2)].inusual is False
    assert res.cobertura == (date(2019, 6, 1), date(2025, 6, 1))
    # 2025-06-02 está fuera de cobertura: no hay día evaluado.
    assert date(2025, 6, 2) not in res.dias


def test_base_insuficiente_por_dia():
    serie = _serie_constante(range(2022, 2026))  # 4 años -> 3 de referencia
    res = calcular(serie, percentil=95, anios_minimos=5, ventana_dias=0)
    dia = res.dias[date(2024, 3, 10)]
    assert dia.umbral is None and dia.inusual is None and dia.n_anios == 3


def test_ventana_circular_en_fin_de_anio():
    anios = range(2018, 2026)
    serie = _serie_constante(anios, valor=0)
    for a in anios:
        if a != 2025:
            serie[date(a, 1, 2)] = 10  # pico el 2 de enero en los demás años
    serie[date(2025, 12, 31)] = 5
    sin_ventana = calcular(serie, percentil=95, anios_minimos=5, ventana_dias=0)
    con_ventana = calcular(serie, percentil=95, anios_minimos=5, ventana_dias=2)
    assert sin_ventana.dias[date(2025, 12, 31)].inusual is True
    # Con ±2 días, el 31 de diciembre ve el 2 de enero de los otros años: el umbral sube.
    assert con_ventana.dias[date(2025, 12, 31)].umbral > 5
    assert con_ventana.dias[date(2025, 12, 31)].inusual is False


def test_ventana_cuenta_anios_no_muestras():
    serie = _serie_constante(range(2022, 2026))
    res = calcular(serie, percentil=95, anios_minimos=5, ventana_dias=7)
    assert res.dias[date(2024, 3, 10)].n_anios == 3  # 3 años de referencia, no 45 valores


def test_serie_vacia():
    res = calcular({}, percentil=95, anios_minimos=5, ventana_dias=7)
    assert res.dias == {} and res.cobertura is None


@pytest.mark.parametrize("kw", [dict(percentil=101), dict(percentil=-1),
                                dict(anios_minimos=0), dict(ventana_dias=-1)])
def test_parametros_invalidos(kw):
    args = dict(percentil=95, anios_minimos=5, ventana_dias=7) | kw
    with pytest.raises(ValueError):
        calcular({date(2020, 1, 1): 1}, **args)


# ------------------------------------------------------------- periodos y climatología
def test_periodos_inusuales_agrupan_dias_consecutivos():
    serie = _serie_constante(range(2019, 2026), valor=1)
    for d, v in ((date(2025, 8, 15), 9), (date(2025, 8, 16), 7), (date(2025, 8, 18), 8)):
        serie[d] = v
    res = calcular(serie, percentil=95, anios_minimos=5, ventana_dias=0)
    periodos = periodos_inusuales(res, date(2025, 8, 1), date(2025, 8, 31))
    assert [(p["inicio"], p["fin"], p["dias"], p["maximo"]) for p in periodos] == [
        ("2025-08-15", "2025-08-16", 2, 9),
        ("2025-08-18", "2025-08-18", 1, 8),
    ]


def test_climatologia_mensual_solo_meses_completos():
    serie = {d: (2 if d.month == 8 else 1) for d in _rango(date(2020, 1, 15), date(2021, 12, 31))}
    clima = climatologia_mensual(serie)
    # Enero de 2020 está incompleto: solo cuenta enero de 2021 (31 días con 1).
    assert clima[1] == {"media": 31.0, "anios": 1}
    assert clima[8] == {"media": 62.0, "anios": 2}
    assert set(clima) == set(range(1, 13))
