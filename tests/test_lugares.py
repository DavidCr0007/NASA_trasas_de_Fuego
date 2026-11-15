"""Búsqueda de lugares: contrato, normalización y uso acotado del proveedor, sin red."""
import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import lugares

MUESTRA = [{"place_id": 1, "name": "Chapinero", "display_name": "Chapinero, Bogotá, Colombia",
            "addresstype": "suburb", "lat": "4.64", "lon": "-74.06",
            "boundingbox": ["4.55", "4.70", "-74.1", "-74.0"]}]


@pytest.fixture
def cliente(monkeypatch):
    lugares._cache.clear()
    monkeypatch.setattr(lugares, "_ultima_consulta", float("-inf"))
    reloj = [100.0]
    monkeypatch.setattr(lugares, "reloj", lambda: reloj[0])
    app = FastAPI()
    app.include_router(lugares.router)
    yield TestClient(app), reloj
    lugares._cache.clear()


def test_busqueda_normaliza_recuadro_y_reutiliza_resultados(cliente, monkeypatch):
    api, _ = cliente
    consultas = []
    def consultar(q):
        consultas.append(q)
        return MUESTRA
    monkeypatch.setattr(lugares, "consultar_proveedor", consultar)
    r = api.get("/buscar-lugares", params={"q": "  Chapinero  Bogotá  "})
    assert r.status_code == 200
    lugar = r.json()["resultados"][0]
    assert lugar["bbox"] == [-74.1, 4.55, -74.0, 4.70]
    assert lugar["tipo"] == "Barrio o sector" and lugar["nombre"] == "Chapinero"
    assert "OpenStreetMap" in r.json()["atribucion"]
    assert api.get("/buscar-lugares", params={"q": "CHAPINERO BOGOTÁ"}).json() == r.json()
    assert consultas == ["Chapinero Bogotá"]


@pytest.mark.parametrize("q", ["", "ab", "   ", "a" * 161])
def test_consultas_invalidas_no_salen_a_internet(cliente, monkeypatch, q):
    api, _ = cliente
    monkeypatch.setattr(lugares, "consultar_proveedor", lambda _: pytest.fail("no debe consultar"))
    assert api.get("/buscar-lugares", params={"q": q}).status_code == 422


def test_limita_consultas_distintas_y_no_penaliza_cache(cliente, monkeypatch):
    api, reloj = cliente
    consultas = []
    monkeypatch.setattr(lugares, "consultar_proveedor", lambda q: consultas.append(q) or MUESTRA)
    assert api.get("/buscar-lugares", params={"q": "Bogota"}).status_code == 200
    reloj[0] += .5
    r = api.get("/buscar-lugares", params={"q": "Neiva"})
    assert r.status_code == 429 and r.headers["Retry-After"] == "2"
    assert api.get("/buscar-lugares", params={"q": "Bogota"}).status_code == 200
    reloj[0] += 1
    assert api.get("/buscar-lugares", params={"q": "Neiva"}).status_code == 200
    assert consultas == ["Bogota", "Neiva"]


def test_resultados_vencidos_se_actualizan(cliente, monkeypatch):
    api, reloj = cliente
    consultas = []
    monkeypatch.setattr(lugares, "consultar_proveedor", lambda q: consultas.append(q) or [])
    assert api.get("/buscar-lugares", params={"q": "Bogota"}).json()["resultados"] == []
    reloj[0] += lugares.TTL + 1
    api.get("/buscar-lugares", params={"q": "Bogota"})
    assert len(consultas) == 2


def test_error_del_proveedor_se_comunica_sin_afectar_otras_rutas(cliente, monkeypatch):
    api, _ = cliente
    def falla(_):
        raise OSError("sin conexión")
    monkeypatch.setattr(lugares, "consultar_proveedor", falla)
    r = api.get("/buscar-lugares", params={"q": "Bogota"})
    assert r.status_code == 503 and "no está disponible" in r.json()["detail"]


def test_conserva_resultados_ambiguos_y_descarta_coordenadas_invalidas():
    datos = MUESTRA + [{**MUESTRA[0], "place_id": 2, "name": "Chapinero",
                       "display_name": "Chapinero, otro municipio", "lat": "5"},
                      {"lat": "NaN", "lon": "0"}, MUESTRA[0]]
    salida = lugares.normalizar(datos)
    assert len(salida) == 2 and salida[0]["descripcion"] != salida[1]["descripcion"]
    assert salida[1]["bbox"][1] < 5 < salida[1]["bbox"][3]


def test_proveedor_identificado_parametros_escapados_y_endpoint_configurable(monkeypatch):
    peticiones = []
    class Respuesta:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, _): return json.dumps(MUESTRA).encode()
    monkeypatch.setattr(lugares, "urlopen", lambda req, timeout: peticiones.append(req) or Respuesta())
    monkeypatch.setenv("NOMINATIM_URL", "https://lugares.example/search")
    assert lugares.consultar_proveedor("Chapinero & Bogotá") == MUESTRA
    req = peticiones[0]
    assert urlparse(req.full_url).netloc == "lugares.example"
    assert parse_qs(urlparse(req.full_url).query)["q"] == ["Chapinero & Bogotá"]
    assert "HarmonizedHeatNeiva" in req.get_header("User-agent")
