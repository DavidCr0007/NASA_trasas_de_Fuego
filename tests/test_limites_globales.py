"""Contrato de descarga y caché de límites; ninguna prueba necesita red."""
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import limites


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    monkeypatch.setattr(limites, "CACHE", tmp_path)
    limites.obtener.cache_clear()
    app = FastAPI()
    app.include_router(limites.router)
    yield TestClient(app)
    limites.obtener.cache_clear()


def test_descarga_con_fuente_y_reutiliza_cache_en_disco(cliente, monkeypatch, tmp_path):
    llamadas = []
    def descargar(url):
        llamadas.append(url)
        if "/api/" in url:
            return {"simplifiedGeometryGeoJSON": "https://github.com/wmgeolab/limite.geojson",
                    "boundaryISO": "ESP", "boundarySource": "IGN", "boundaryLicense": "CC BY 4.0"}
        return {"type": "FeatureCollection", "features": []}
    monkeypatch.setattr(limites, "descargar_json", descargar)
    r = cliente.get("/limites/esp/1")
    assert r.status_code == 200 and r.json()["metadatos"]["boundarySource"] == "IGN"
    assert len(llamadas) == 2
    assert json.loads((tmp_path / "ESP-ADM1.json").read_text(encoding="utf-8")) == r.json()
    limites.obtener.cache_clear()
    assert cliente.get("/limites/ESP/1").json() == r.json()
    assert len(llamadas) == 2


@pytest.mark.parametrize("ruta", ["/limites/INVALIDO/1", "/limites/123/0", "/limites/COL/3", "/limites/COL/-1"])
def test_rechaza_parametros_sin_descargar(cliente, monkeypatch, ruta):
    monkeypatch.setattr(limites, "descargar_json", lambda _: pytest.fail("no debe acceder a la red"))
    assert cliente.get(ruta).status_code == 422


def test_cobertura_ausente_es_explicita(cliente, monkeypatch):
    def ausente(url):
        raise HTTPError(url, 404, "no publicado", {}, None)
    monkeypatch.setattr(limites, "descargar_json", ausente)
    r = cliente.get("/limites/COL/2")
    assert r.status_code == 404 and "no publica ADM2" in r.json()["detail"]


def test_desconexion_no_guarda_archivo_incompleto(cliente, monkeypatch, tmp_path):
    def falla(_):
        raise OSError("sin red")
    monkeypatch.setattr(limites, "descargar_json", falla)
    assert cliente.get("/limites/COL/1").status_code == 503
    assert not list(tmp_path.iterdir())


def test_no_se_descargan_urls_arbitrarias():
    with pytest.raises(ValueError, match="no admitido"):
        limites.descargar_json("http://localhost/secreto")


def test_indice_incluye_microestados_sin_cargar_geometrias():
    indice = Path(__file__).resolve().parents[1] / "src/ui/static/datos/indice_limites.json"
    datos = json.loads(indice.read_text(encoding="utf-8"))
    assert {"AND", "LIE", "SMR", "COL", "ESP"} <= {p["iso"] for p in datos["paises"]}
    assert len(datos["paises"]) > 240 and indice.stat().st_size < 100_000
