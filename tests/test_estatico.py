"""ADR 0015: demo estática para GitHub Pages.

El exportador guarda respuestas EXACTAS de la API (no las recalcula) y la página publicada las
sirve con estatico.js. Se prueba con la muestra pequeña de data/sample, sin red.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from harmonize.pipeline import main as pipeline_main

RAIZ = Path(__file__).resolve().parent.parent
ESTATICO_JS = (RAIZ / "src" / "ui" / "static" / "estatico.js").read_text(encoding="utf-8")
APP_JS = (RAIZ / "src" / "ui" / "static" / "app.js").read_text(encoding="utf-8")
GLOBO_JS = (RAIZ / "src" / "ui" / "static" / "globo.js").read_text(encoding="utf-8")


def _exportador():
    spec = importlib.util.spec_from_file_location("exportar_estatico", RAIZ / "tools" / "exportar_estatico.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sitio(tmp_path_factory):
    datos = tmp_path_factory.mktemp("demo_estatica")
    assert pipeline_main(["--input", str(RAIZ / "data" / "sample"), "--output", str(datos)]) == 0
    salida = tmp_path_factory.mktemp("sitio") / "_site"
    indice = _exportador().exportar(datos, salida, anios_minimos=5)
    return datos, salida, indice


def test_sitio_con_interfaz_y_estatico_js_antes_que_todo(sitio):
    _, salida, _ = sitio
    html = (salida / "index.html").read_text(encoding="utf-8")
    assert html.index('src="estatico.js"') < html.index('src="vendor/maplibre/maplibre-gl.js"') < html.index('src="app.js"')
    for archivo in ("app.js", "globo.js", "capas.js", "zonas.js", "estatico.js", "datos/huila_municipios.geojson", ".nojekyll"):
        assert (salida / archivo).exists(), archivo
    # El index.html del repositorio no carga estatico.js: la app con API no cambia.
    assert "estatico.js" not in (RAIZ / "src" / "ui" / "static" / "index.html").read_text(encoding="utf-8")


def test_respuestas_precalculadas_iguales_a_la_api(sitio):
    datos, salida, indice = sitio
    api = TestClient(create_app(datos, anios_minimos=5))
    municipios = json.loads((salida / "datos" / "huila_municipios.geojson").read_text(encoding="utf-8"))["features"]
    assert len(indice["areas"]) == 1 + len(municipios) == 38
    anio = indice["anios"][-1]
    rango = {"desde": f"{anio}-01-01", "hasta": f"{anio}-12-31"}
    guardado = json.loads((salida / "api" / "calendario" / "huila" / f"{anio}.json").read_text(encoding="utf-8"))
    assert guardado == api.get("/calendario", params={"area": "huila", **rango}).json()
    mun = municipios[0]["properties"]["shapeID"]
    guardado = json.loads((salida / "api" / "resumen" / f"mun-{mun}.json").read_text(encoding="utf-8"))
    assert guardado == api.get("/resumen", params={"area": f"mun:{mun}"}).json()
    assert json.loads((salida / "api" / "global" / "2_0.5.json").read_text(encoding="utf-8")) == \
        api.get("/global", params={"dias": 2, "res": 0.5}).json()
    assert (salida / "api" / "csv" / f"calendario_huila_{anio}.csv").read_text(encoding="utf-8") == \
        api.get("/calendario.csv", params={"area": "huila", **rango}).text


def test_detecciones_completas_por_columnas(sitio):
    datos, salida, _ = sitio
    d = json.loads((salida / "api" / "detecciones.json").read_text(encoding="utf-8"))
    todas = TestClient(create_app(datos)).get("/detecciones", params={"bbox": "-180,-90,180,90", "limite": 50000}).json()
    assert not todas["truncado"] and len(d["filas"]) == len(todas["detecciones"]) > 0
    primera = dict(zip(d["campos"], d["filas"][0]))
    assert primera == {k: todas["detecciones"][0][k] for k in d["campos"]}
    assert d["base"]["cita"] == todas["cita"] and d["origen_datos"] == todas["origen_datos"]


def test_estatico_js_cubre_las_rutas_de_la_interfaz_y_no_inventa_datos():
    rutas = set(re.findall(r"""(?:pedir|fetch)\(\s*[`'"]/([a-z-]+)""", APP_JS + GLOBO_JS))
    rutas |= set(re.findall(r"`/([a-z-]+)\?", APP_JS))
    rutas -= {"ui"}
    patron = re.search(r"const RUTAS_API = (/.*?/);", ESTATICO_JS).group(1)
    for ruta in rutas:
        assert re.search(ruta, patron), f"/{ruta} sin respuesta en la demo estática"
    # Lo que necesita servidor responde con aviso (404/503), nunca con datos inventados.
    assert 'noDisponible("ver límites administrativos fuera del Huila")' in ESTATICO_JS
    assert "buscar lugares en internet" in ESTATICO_JS and "make api" in ESTATICO_JS
    assert "Demo publicada sin servidor: datos SINTÉTICOS" in ESTATICO_JS
    # MapLibre carga los GeoJSON del estilo sin window.fetch: deben pasar por recurso().
    assert 'data: recurso("/ui/datos/hidrografia_mundial.geojson")' in GLOBO_JS
    assert 'data: recurso("/ui/datos/mundo_paises.geojson")' in GLOBO_JS
    assert not re.search(r'data: "/ui/', GLOBO_JS)


def test_flujo_de_pages_prueba_construye_y_publica():
    flujo = (RAIZ / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "branches: [main]" in flujo and "workflow_dispatch" in flujo
    assert flujo.index("run: uv run pytest -q") < flujo.index("run: uv run python tools/exportar_estatico.py") < flujo.index("uses: actions/deploy-pages")
    assert "pages: write" in flujo and "id-token: write" in flujo
    assert "secrets." not in flujo and "MAP_KEY" not in flujo.split("\n", 3)[3]
    assert "_site/" in (RAIZ / ".gitignore").read_text(encoding="utf-8")
