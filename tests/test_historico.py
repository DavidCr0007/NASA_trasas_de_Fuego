"""H4-04: muestra histórica sintética 2020-2026 y detección de la anomalía inyectada."""

from __future__ import annotations

import hashlib
import importlib.util
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from harmonize.pipeline import main as pipeline_main
from ingest.firms_schema import HUILA_BBOX

RAIZ = Path(__file__).resolve().parent.parent
BBOX = ",".join(str(v) for v in HUILA_BBOX)


def _generador():
    spec = importlib.util.spec_from_file_location("generar_historico", RAIZ / "tools" / "generar_historico.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def historico(tmp_path_factory):
    gen = _generador()
    crudo = tmp_path_factory.mktemp("hist_crudo")
    gen.generar(crudo)
    salida = tmp_path_factory.mktemp("hist_salida")
    assert pipeline_main(["--input", str(crudo), "--output", str(salida)]) == 0
    return gen, crudo, salida


def _hashes(carpeta: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(carpeta.glob("*.csv"))}


def test_generador_determinista(historico, tmp_path):
    gen, crudo, _ = historico
    gen.generar(tmp_path)
    assert _hashes(tmp_path) == _hashes(crudo)


def test_archivos_marcados_como_sinteticos(historico):
    _, crudo, _ = historico
    assert all(p.name.startswith("SINTETICO_") for p in crudo.glob("*.csv"))
    assert '"sintetico":true' in (crudo / "manifest.jsonl").read_text()


def test_pipeline_sin_cuarentena(historico):
    import json

    _, _, salida = historico
    resumen = json.loads((salida / "resumen.json").read_text())
    assert resumen["invariante_ok"] is True
    assert resumen["conteos"]["cuarentena"] == 0
    assert resumen["conteos"]["aceptados"] > 1000


def test_api_detecta_la_anomalia_inyectada(historico):
    gen, _, salida = historico
    cliente = TestClient(create_app(salida))
    cuerpo = cliente.get(f"/calendario?bbox={BBOX}&desde=2026-01-01&hasta=2026-11-12").json()
    assert cuerpo["linea_base"]["estado"] == "suficiente"
    ini, fin = gen.ANOMALIA
    periodos = cuerpo["periodos_inusuales"]
    assert any(date.fromisoformat(p["inicio"]) <= fin and date.fromisoformat(p["fin"]) >= ini
               for p in periodos), periodos
    dias_anomalia = [d for d in cuerpo["dias"] if ini.isoformat() <= d["fecha_utc"] <= fin.isoformat()]
    assert sum(d["inusual"] for d in dias_anomalia) >= len(dias_anomalia) // 2


def test_tasa_de_falsos_positivos_cercana_al_percentil(historico):
    # Con P95 sobre una serie estacionaria se espera ~5 % de días sobre el umbral.
    # La serie sintética es ruidosa (Poisson): se exige media <= 6 % en 2021-2025
    # (años sin anomalía) y ningún año por encima del 10 %.
    _, _, salida = historico
    cliente = TestClient(create_app(salida))
    tasas = []
    for anio in range(2021, 2026):
        dias = cliente.get(f"/calendario?bbox={BBOX}&desde={anio}-01-01&hasta={anio}-12-31").json()["dias"]
        tasas.append(sum(bool(d["inusual"]) for d in dias) / len(dias))
    assert sum(tasas) / len(tasas) <= 0.06, tasas
    assert max(tasas) <= 0.10, tasas


def test_meses_pico_reflejan_la_estacionalidad_sintetica(historico):
    gen, _, salida = historico
    cuerpo = TestClient(create_app(salida)).get(f"/calendario?bbox={BBOX}").json()
    assert gen.MES_PICO_PRINCIPAL in cuerpo["meses_pico"]
