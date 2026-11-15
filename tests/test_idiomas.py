"""Localización y contratos de idioma, sin cambiar identificadores ni datos científicos."""
import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import lugares
from api.app import create_app
from harmonize.pipeline import ejecutar

RAIZ=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("texto,idioma,esperado",[
    ("Explorador de focos","en","Heat detection explorer"),
    ("Explorador de focos","fr","Explorateur de détections thermiques"),
    ("No usar para proteger vidas ni bienes.","fr","Ne pas utiliser pour protéger des vies ou des biens."),
    ("40.824 focos de calor","en","40,824 heat detections"),
    ("2026","en","2026"),
    ("VIIRS_NOAA20_NRT","fr","VIIRS_NOAA20_NRT"),
    ("armonizacion-0.3.1","en","armonizacion-0.3.1"),
    ("Neiva","fr","Neiva"),
    ("  Clima   (reanálisis)  ","en","  Weather (reanalysis)  "),
    ("40.824 focos de calor","es","40.824 focos de calor"),
])
def test_textos_y_datos_conservados(texto,idioma,esperado):
    script="const i=require('./src/ui/static/idiomas.js');process.stdout.write(i.traducir("+json.dumps(texto)+","+json.dumps(idioma)+"));"
    r=subprocess.run(["node","-e",script],cwd=RAIZ,capture_output=True,text=True,encoding="utf-8")
    assert r.returncode==0,r.stderr
    assert r.stdout==esperado


@pytest.fixture(scope="module")
def cliente(tmp_path_factory):
    salida=tmp_path_factory.mktemp("idiomas")
    ejecutar(RAIZ/"data/sample",salida)
    return TestClient(create_app(salida))


@pytest.mark.parametrize("idioma,palabra",[("es","Metodología"),("en","Harmonization methodology"),("fr","Méthodologie")])
def test_documentos_y_selector_en_tres_idiomas(cliente,idioma,palabra):
    r=cliente.get("/metodologia",params={"idioma":idioma})
    assert r.status_code==200 and palabra in r.text
    assert r.headers["content-language"]==idioma
    assert cliente.get("/limitaciones",params={"idioma":idioma}).status_code==200
    html=cliente.get("/ui/").text
    assert f'<option value="{idioma}" lang="{idioma}">' in html


def test_idioma_invalido_no_se_usa_como_ruta(cliente):
    assert cliente.get("/metodologia",params={"idioma":"../../.env"}).status_code==422
    assert cliente.get("/buscar-lugares",params={"q":"Paris","idioma":"de"}).status_code==422


def test_busqueda_envia_idioma_al_proveedor(cliente,monkeypatch):
    peticiones=[]
    monkeypatch.setattr(lugares,"_ultima_consulta",float("-inf"))
    monkeypatch.setattr(lugares,"consultar_proveedor",lambda q,idioma:peticiones.append((q,idioma)) or [])
    assert cliente.get("/buscar-lugares",params={"q":"Paris","idioma":"fr"}).status_code==200
    assert peticiones==[("Paris","fr")]
