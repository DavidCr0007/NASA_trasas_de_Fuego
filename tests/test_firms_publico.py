"""Ruta pública temporal sin MAP_KEY: archivo anual por país de FIRMS (B-01)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from harmonize.pipeline import main as pipeline_main
from ingest.firms_publico import construir_url, descargar_y_recortar
from ingest.manifest import sha256_file

RAIZ = Path(__file__).resolve().parent.parent
FIX = RAIZ / "tests" / "fixtures" / "firms_real"
BBOX_PRUEBA = (-80.0, -5.0, -66.0, 13.0)  # Colombia aproximada: incluye las filas de los recortes


def _fetch_simulado(llamadas: list[str]):
    contenido = {
        "modis/2023/modis_2023_Colombia.csv": FIX / "modis_2023_Colombia_head.csv",
        "viirs-snpp/2023/viirs-snpp_2023_Colombia.csv": FIX / "viirs-snpp_2023_Colombia_head.csv",
        "viirs-jpss1/2023/viirs-jpss1_2023_Colombia.csv": FIX / "viirs-jpss1_2023_Colombia_head.csv",
    }

    def fetch(url: str) -> bytes:
        llamadas.append(url)
        for sufijo, ruta in contenido.items():
            if url.endswith(sufijo):
                return ruta.read_bytes()
        raise HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    return fetch


def test_url_sigue_la_plantilla_publica():
    assert construir_url("PAIS_VIIRS_NOAA20_SP", 2023, "Colombia") == (
        "https://firms.modaps.eosdis.nasa.gov/data/country/viirs-jpss1/2023/viirs-jpss1_2023_Colombia.csv"
    )


def test_descarga_recorta_y_registra_procedencia(tmp_path):
    llamadas: list[str] = []
    res = descargar_y_recortar(
        raiz=tmp_path, pais="Colombia", anios=[2023, 2024], bbox=BBOX_PRUEBA,
        fuentes=["PAIS_MODIS_SP", "PAIS_VIIRS_SNPP_SP", "PAIS_VIIRS_NOAA20_SP"],
        salida=tmp_path / "recortes", fetch=_fetch_simulado(llamadas), ahora="2026-11-13T23:00:00Z",
    )
    # 2023 existe para los tres; 2024 devuelve 404 y se registra como no disponible.
    assert len(res["descargados"]) == 3
    assert len(res["no_disponibles"]) == 3
    crudo = [json.loads(ln) for ln in (tmp_path / "data/raw/manifest.jsonl").read_text().splitlines()]
    assert {e["fuente"] for e in crudo} == {"PAIS_MODIS_SP", "PAIS_VIIRS_SNPP_SP", "PAIS_VIIRS_NOAA20_SP"}
    for e in crudo:
        ruta = tmp_path / "data/raw" / e["archivo"]
        assert e["sha256"] == sha256_file(ruta)
        assert ruta.stat().st_mode & 0o777 == 0o444
        assert e["url_sin_clave"].startswith("https://firms.modaps.eosdis.nasa.gov/data/country/")
        assert e["sintetico"] is False and e["calidad"] == "estandar" and e["variante"] == "pais"
    recortes = [json.loads(ln) for ln in (tmp_path / "recortes/manifest.jsonl").read_text().splitlines()]
    assert len(recortes) == 3
    for r in recortes:
        assert r["origen_sha256"] in {e["sha256"] for e in crudo}
        assert r["bbox"] == list(BBOX_PRUEBA)
        assert r["sha256"] == sha256_file(tmp_path / "recortes" / r["archivo"])


def test_no_vuelve_a_descargar_ni_sobrescribe(tmp_path):
    kwargs = dict(raiz=tmp_path, pais="Colombia", anios=[2023], bbox=BBOX_PRUEBA,
                  fuentes=["PAIS_MODIS_SP"], salida=tmp_path / "recortes", ahora="2026-11-13T23:00:00Z")
    primera: list[str] = []
    descargar_y_recortar(fetch=_fetch_simulado(primera), **kwargs)
    segunda: list[str] = []
    res = descargar_y_recortar(fetch=_fetch_simulado(segunda), **kwargs)
    assert len(primera) == 1 and segunda == []
    assert len(res["reutilizados"]) == 1
    lineas = (tmp_path / "data/raw/manifest.jsonl").read_text().splitlines()
    assert len(lineas) == 1


def test_recorte_solo_conserva_filas_del_area(tmp_path):
    res = descargar_y_recortar(
        raiz=tmp_path, pais="Colombia", anios=[2023], bbox=(-76.7, 1.4, -74.3, 3.9),
        fuentes=["PAIS_MODIS_SP"], salida=tmp_path / "recortes",
        fetch=_fetch_simulado([]), ahora="2026-11-13T23:00:00Z",
    )
    recorte = tmp_path / "recortes" / res["recortes"][0]
    filas = recorte.read_text().splitlines()[1:]
    for fila in filas:
        lat, lon = float(fila.split(",")[0]), float(fila.split(",")[1])
        assert 1.4 <= lat <= 3.9 and -76.7 <= lon <= -74.3


def test_pipeline_procesa_los_recortes_sin_cuarentena(tmp_path):
    descargar_y_recortar(
        raiz=tmp_path, pais="Colombia", anios=[2023], bbox=BBOX_PRUEBA,
        fuentes=["PAIS_MODIS_SP", "PAIS_VIIRS_SNPP_SP", "PAIS_VIIRS_NOAA20_SP"],
        salida=tmp_path / "recortes", fetch=_fetch_simulado([]), ahora="2026-11-13T23:00:00Z",
    )
    assert pipeline_main(["--input", str(tmp_path / "recortes"), "--output", str(tmp_path / "out")]) == 0
    resumen = json.loads((tmp_path / "out" / "resumen.json").read_text())
    assert resumen["conteos"]["n_input"] == 75 and resumen["conteos"]["cuarentena"] == 0


def test_cabecera_invalida_no_se_guarda(tmp_path):
    def fetch(url):
        return b"<html>error</html>"

    res = descargar_y_recortar(
        raiz=tmp_path, pais="Colombia", anios=[2023], bbox=BBOX_PRUEBA, fuentes=["PAIS_MODIS_SP"],
        salida=tmp_path / "recortes", fetch=fetch, ahora="2026-11-13T23:00:00Z",
    )
    assert res["rechazados"] and not res["descargados"]
    assert not (tmp_path / "data/raw/manifest.jsonl").exists()


def test_fuente_sin_ruta_publica_falla():
    with pytest.raises(ValueError):
        construir_url("MODIS_NRT", 2023, "Colombia")
