"""R5: línea base por día del año y días inusuales (ADR 0004 y 0005).

Para cada día evaluado ``t`` de la cobertura:

- referencia: los valores de los **otros** años (se excluye el año de ``t``) en
  los días del año ``clave(t) ± ventana_dias`` (circular sobre 365 claves);
- umbral: percentil ``percentil`` de esa referencia, con interpolación lineal;
- inusual: ``valor(t) > umbral``;
- si la referencia tiene menos de ``anios_minimos`` años, el umbral es nulo
  («base insuficiente» para ese día).

Dentro de la cobertura, un día sin entrada vale 0. La cobertura es la del **conjunto de
datos** (parámetro ``cobertura``); si no se da, se usa ``[min(serie), max(serie)]``.

Versiones de R5 (independientes de RULES_VERSION, que versiona el pipeline):
  r5-1.0.0  cobertura = primer y último día con focos del área.
  r5-1.1.0  cobertura explícita del conjunto (2026-11-14): en áreas con pocos focos, los
            días previos al primer foco cuentan como 0 en la referencia.
El 29 de febrero se evalúa con la clave del 28 y no se usa como referencia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# 365 claves (mes, día), sin el 29 de febrero.
VERSION_R5 = "r5-1.1.0"

_CLAVES = [(d.month, d.day) for d in (date(2001, 1, 1) + timedelta(days=i) for i in range(365))]
_INDICE = {k: i for i, k in enumerate(_CLAVES)}


def clave_dia(d: date) -> tuple[int, int]:
    return (2, 28) if (d.month, d.day) == (2, 29) else (d.month, d.day)


def percentil_lineal(valores, p: float) -> float:
    """Percentil con interpolación lineal entre rangos (método «linear» de numpy)."""
    if not valores:
        raise ValueError("percentil de una lista vacía")
    orden = sorted(valores)
    pos = (len(orden) - 1) * p / 100
    bajo = int(pos)
    alto = min(bajo + 1, len(orden) - 1)
    return float(orden[bajo] + (orden[alto] - orden[bajo]) * (pos - bajo))


@dataclass(frozen=True)
class DiaBase:
    valor: int
    umbral: float | None
    n_anios: int
    inusual: bool | None


@dataclass(frozen=True)
class LineaBase:
    dias: dict[date, DiaBase]
    cobertura: tuple[date, date] | None
    percentil: float
    anios_minimos: int
    ventana_dias: int


def calcular(
    serie: dict[date, int],
    *,
    percentil: float = 95,
    anios_minimos: int = 5,
    ventana_dias: int = 7,
    cobertura: tuple[date, date] | None = None,
) -> LineaBase:
    if not 0 <= percentil <= 100:
        raise ValueError("percentil debe estar entre 0 y 100")
    if anios_minimos < 1:
        raise ValueError("anios_minimos debe ser al menos 1")
    if ventana_dias < 0:
        raise ValueError("ventana_dias no puede ser negativa")
    if not serie and not cobertura:
        return LineaBase({}, None, percentil, anios_minimos, ventana_dias)

    inicio, fin = cobertura if cobertura else (min(serie), max(serie))

    def valor(d: date) -> int | None:
        return serie.get(d, 0) if inicio <= d <= fin else None

    anios = range(inicio.year, fin.year + 1)
    # valores[año][índice de clave] = valor o None (fuera de cobertura)
    valores: dict[int, list[int | None]] = {}
    for a in anios:
        valores[a] = [valor(date(a, m, d)) for m, d in _CLAVES]

    desplazamientos = range(-ventana_dias, ventana_dias + 1)
    dias: dict[date, DiaBase] = {}
    t = inicio
    while t <= fin:
        i = _INDICE[clave_dia(t)]
        muestra: list[int] = []
        n_anios = 0
        for a in anios:
            if a == t.year:
                continue
            fila = valores[a]
            aporte = [v for k in desplazamientos if (v := fila[(i + k) % 365]) is not None]
            if aporte:
                n_anios += 1
                muestra.extend(aporte)
        v = valor(t)
        if n_anios >= anios_minimos:
            umbral = percentil_lineal(muestra, percentil)
            dias[t] = DiaBase(v, umbral, n_anios, v > umbral)
        else:
            dias[t] = DiaBase(v, None, n_anios, None)
        t += timedelta(days=1)
    return LineaBase(dias, (inicio, fin), percentil, anios_minimos, ventana_dias)


def periodos_inusuales(base: LineaBase, desde: date, hasta: date) -> list[dict]:
    """Agrupa días inusuales consecutivos dentro de [desde, hasta]."""
    periodos: list[dict] = []
    actual: dict | None = None
    d = desde
    while d <= hasta:
        dia = base.dias.get(d)
        if dia is not None and dia.inusual:
            if actual is None:
                actual = {"inicio": d.isoformat(), "fin": d.isoformat(), "dias": 0, "maximo": 0}
                periodos.append(actual)
            actual["fin"] = d.isoformat()
            actual["dias"] += 1
            actual["maximo"] = max(actual["maximo"], dia.valor)
        else:
            actual = None
        d += timedelta(days=1)
    return periodos


def climatologia_mensual(serie: dict[date, int], cobertura: tuple[date, date] | None = None) -> dict[int, dict]:
    """Media de la suma mensual en los meses completos de la cobertura."""
    if not serie and not cobertura:
        return {}
    inicio, fin = cobertura if cobertura else (min(serie), max(serie))
    sumas: dict[int, list[int]] = {m: [] for m in range(1, 13)}
    for a in range(inicio.year, fin.year + 1):
        for m in range(1, 13):
            primero = date(a, m, 1)
            ultimo = (date(a + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)
            if primero < inicio or ultimo > fin:
                continue
            total = 0
            d = primero
            while d <= ultimo:
                total += serie.get(d, 0)
                d += timedelta(days=1)
            sumas[m].append(total)
    return {m: {"media": round(sum(v) / len(v), 2), "anios": len(v)} for m, v in sumas.items() if v}
