"""H5-01: conteo independiente del CSV oficial frente a la salida del pipeline."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from harmonize.pipeline import main as pipeline_main
from ingest.firms_schema import HUILA_BBOX

RAIZ = Path(__file__).resolve().parent.parent


def _herramienta():
    spec = importlib.util.spec_from_file_location("validacion_cruzada", RAIZ / "tools" / "validacion_cruzada.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def salida(tmp_path_factory):
    destino = tmp_path_factory.mktemp("vc")
    assert pipeline_main(["--input", str(RAIZ / "data" / "sample"), "--output", str(destino)]) == 0
    return destino


@pytest.mark.parametrize("fecha", ["2026-11-10", "2026-11-11", "2026-11-12"])
def test_crudas_igual_a_brutas_mas_cuarentena(salida, fecha):
    vc = _herramienta()
    r = vc.comparar(RAIZ / "data" / "sample", salida, HUILA_BBOX, fecha)
    assert r["crudas"]["total"] > 0
    assert r["crudas"]["total"] == r["pipeline"]["n_brutas"] + r["cuarentena"]
    assert r["crudas"]["total"] == sum(r["crudas"]["por_sensor"].values())
    assert r["diferencia"] == 0


def test_conteo_independiente_por_sensor(salida):
    vc = _herramienta()
    r = vc.comparar(RAIZ / "data" / "sample", salida, HUILA_BBOX, "2026-11-10")
    assert set(r["crudas"]["por_sensor"]) <= {"MODIS", "VIIRS"}
    assert r["pipeline"]["n_detecciones"] <= r["pipeline"]["n_brutas"]


def test_informe_markdown_lleva_fuente_fecha_y_calidad(salida):
    vc = _herramienta()
    r = vc.comparar(RAIZ / "data" / "sample", salida, HUILA_BBOX, "2026-11-10")
    md = vc.informe_markdown(r)
    for texto in ("2026-11-10", "sintético", "NRT", "estandar", "n_brutas", "cuarentena"):
        assert texto in md, texto
