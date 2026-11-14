"""H7-01: municipios del Huila (geoBoundaries ADM2, DANE, CC BY 4.0) servidos a la interfaz."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "src" / "ui" / "static" / "datos" / "huila_municipios.geojson"


def _herramienta():
    spec = importlib.util.spec_from_file_location("preparar_limites", RAIZ / "tools" / "preparar_limites.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_punto_en_poligono_con_hueco():
    h = _herramienta()
    exterior = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hueco = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    poligono = {"type": "Polygon", "coordinates": [exterior, hueco]}
    assert h.contiene(poligono, (2, 2))
    assert not h.contiene(poligono, (5, 5))
    assert not h.contiene(poligono, (11, 5))
    multi = {"type": "MultiPolygon", "coordinates": [[exterior], [[[20, 20], [30, 20], [30, 30], [20, 20]]]]}
    assert h.contiene(multi, (25, 22))


def test_punto_interior_cae_dentro_aunque_el_poligono_sea_concavo():
    h = _herramienta()
    en_u = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [7, 10], [7, 3], [3, 3], [3, 10], [0, 10], [0, 0]]]}
    p = h.punto_interior(en_u)
    assert h.contiene(en_u, p)


@pytest.fixture(scope="module")
def geo():
    assert SALIDA.exists(), "falta el GeoJSON de municipios; ejecute tools/preparar_limites.py"
    return json.loads(SALIDA.read_text(encoding="utf-8"))


def test_37_municipios_con_neiva(geo):
    nombres = {f["properties"]["shapeName"] for f in geo["features"]}
    assert len(geo["features"]) == 37
    assert "Neiva" in nombres


def test_procedencia_y_licencia(geo):
    meta = geo["metadatos"]
    assert meta["fuente"].startswith("geoBoundaries")
    assert "DANE" in meta["fuente_original"]
    assert meta["licencia"] == "CC BY 4.0"
    assert len(meta["sha256_origen_adm2"]) == 64
    # El polígono ADM1 (ODbL) solo se usa para seleccionar: no se redistribuye.
    assert "ADM1" not in json.dumps([f["properties"] for f in geo["features"]])


def test_cada_municipio_trae_su_bbox(geo):
    for f in geo["features"]:
        w, s, e, n = f["properties"]["bbox"]
        assert -77.5 < w < e < -73.5 and 0.5 < s < n < 4.5, f["properties"]["shapeName"]


def test_geojson_servido_por_la_interfaz():
    from fastapi.testclient import TestClient

    from api.app import create_app

    r = TestClient(create_app(RAIZ / "data" / "no-existe")).get("/ui/datos/huila_municipios.geojson")
    assert r.status_code == 200
    assert len(r.json()["features"]) == 37
