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


def test_efecto_de_borde_se_explica(tmp_path):
    # Un punto dentro del bbox cuya celda de ~1 km tiene el centroide fuera: no es una pérdida.
    import csv as _csv
    import json as _json

    from ingest.manifest import append_entry, build_entry

    vc = _herramienta()
    crudo = tmp_path / "crudo"
    crudo.mkdir()
    cab = ["latitude", "longitude", "bright_ti4", "scan", "track", "acq_date", "acq_time", "satellite",
           "confidence", "version", "bright_ti5", "frp", "daynight"]
    ruta = crudo / "v.csv"
    with ruta.open("w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(cab)
        w.writerow(["2.5", "-75.0", "330", "0.4", "0.4", "2025-01-01", "1800", "N20", "n", "2", "300", "3", "D"])
        w.writerow(["1.4001", "-75.0", "330", "0.4", "0.4", "2025-01-01", "1800", "N20", "n", "2", "300", "3", "D"])
    append_entry(crudo / "manifest.jsonl", build_entry(
        ruta, crudo, fuente="PAIS_VIIRS_NOAA20_SP", sensor="VIIRS", calidad="estandar", coleccion="2",
        variante="pais", fecha_descarga="2026-11-13T00:00:00Z", url_sin_clave=None, bbox=None,
        fecha_inicio=None, fecha_fin=None, sintetico=False))
    assert pipeline_main(["--input", str(crudo), "--output", str(tmp_path / "out")]) == 0
    r = vc.comparar(crudo, tmp_path / "out", (-76.7, 1.4, -74.3, 3.9), "2025-01-01")
    assert r["crudas"]["total"] == 2 and r["pipeline"]["n_brutas"] == 1
    assert r["borde"] == 1 and r["diferencia"] == 1 and r["diferencia_sin_explicar"] == 0
    assert "borde" in vc.informe_markdown(r)
