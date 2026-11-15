"""ADR 0012: vista global (endpoint /global, globo 3D, países de Natural Earth, descarga aparte)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from api import mundo
from api.app import create_app
from harmonize.pipeline import main as pipeline_main
from ingest.firms_download import download
from ingest.firms_schema import COLUMNAS_REQUERIDAS

RAIZ = Path(__file__).resolve().parent.parent
ESTATICOS = RAIZ / "src" / "ui" / "static"
HTML = (ESTATICOS / "index.html").read_text(encoding="utf-8")
JS = (ESTATICOS / "app.js").read_text(encoding="utf-8")
GLOBO = (ESTATICOS / "globo.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def salida(tmp_path_factory) -> Path:
    destino = tmp_path_factory.mktemp("demo_global")
    assert pipeline_main(["--input", str(RAIZ / "data" / "sample"), "--output", str(destino)]) == 0
    return destino


@pytest.fixture(scope="module")
def cliente(salida) -> TestClient:
    return TestClient(create_app(salida, anios_minimos=5))


# ------------------------------------------------------------------ API /global
def test_global_agrega_todas_las_detecciones_del_periodo(cliente, salida):
    d = cliente.get("/global", params={"dias": 31, "res": 1}).json()
    filas = pq.read_table(salida / "detecciones.parquet").to_pylist()
    fin = max(f["fecha_hora_utc"].date() for f in filas)
    esperadas = [f for f in filas if (fin - f["fecha_hora_utc"].date()).days < 31]
    assert d["hasta"] == fin.isoformat()
    assert d["total_detecciones"] == len(esperadas) == sum(c[2] for c in d["celdas"])
    assert d["total_alta"] == sum(1 for f in esperadas if f["confianza_clase"] == "alta")
    assert d["campos_celda"][:3] == ["lat", "lon", "n"]
    assert sum(s["n"] for s in d["serie_diaria"]) == d["total_detecciones"]
    assert d["cita"] and d["aviso"] and d["rules_version"]
    assert d["origen_datos"] == "sintetico"
    assert d["detalle_mismo_conjunto"] is True
    assert d["actualizado_hasta_utc"].startswith(fin.isoformat())


def test_global_reparte_por_pais(cliente):
    d = cliente.get("/global", params={"dias": 31}).json()
    # La muestra sintética está en el Huila: todo cae en Colombia.
    con_pais = [p for p in d["paises"] if p["iso_a3"]]
    assert con_pais and con_pais[0]["iso_a3"] == "COL" and con_pais[0]["nombre"] == "Colombia"
    assert sum(p["n"] for p in d["paises"]) == d["total_detecciones"]
    assert d["n_paises"] == len(con_pais)


def test_global_periodo_y_resolucion(cliente):
    uno = cliente.get("/global", params={"dias": 1}).json()
    assert uno["desde"] == uno["hasta"]
    assert cliente.get("/global", params={"res": 0.3}).status_code == 422
    assert cliente.get("/global", params={"dias": 0}).status_code == 422
    assert cliente.get("/global", params={"dias": 40}).status_code == 422


def test_global_usa_su_propio_conjunto(salida, tmp_path):
    vacio = tmp_path / "sin_datos"
    vacio.mkdir()
    # El conjunto principal no existe; el global sí: /global responde, /calendario no.
    c = TestClient(create_app(vacio, datos_global=salida))
    respuesta = c.get("/global")
    assert respuesta.status_code == 200
    assert respuesta.json()["detalle_mismo_conjunto"] is False
    assert c.get("/calendario", params={"area": "huila"}).status_code == 503
    sin_global = TestClient(create_app(salida, datos_global=vacio))
    assert sin_global.get("/global").status_code == 503


def test_pais_de_puntos_conocidos():
    assert mundo.pais_de(-75.3, 2.9)[0] == "COL"      # Neiva
    assert mundo.pais_de(-47.9, -15.8)[0] == "BRA"    # Brasilia
    assert mundo.pais_de(133.0, -25.0)[0] == "AUS"
    assert mundo.pais_de(-30.0, 0.0) is None          # Atlántico


def test_mundo_paises_ligero_y_con_fuente():
    geo = json.loads((ESTATICOS / "datos" / "mundo_paises.geojson").read_text(encoding="utf-8"))
    assert len(geo["features"]) >= 170
    assert "Natural Earth" in geo["fuente"]
    assert set(geo["features"][0]["properties"]) == {"nombre", "iso_a3", "bbox"}
    assert (ESTATICOS / "datos" / "mundo_paises.geojson").stat().st_size < 400_000


# ------------------------------------------------------------------ descarga global aparte
def test_descarga_con_manifiesto_propio(tmp_path):
    cuerpo = (",".join(COLUMNAS_REQUERIDAS[("MODIS", "api_nrt")]) + "\n").encode()
    manifiesto = tmp_path / "data" / "raw" / "global" / "manifest.jsonl"
    rutas = download(
        sources=["MODIS_NRT"], start=date(2026, 11, 1), end=date(2026, 11, 1), bbox=(-180, -90, 180, 90),
        out=tmp_path / "data" / "raw" / "global" / "firms_api", root=tmp_path, map_key="clave-prueba",
        fetch=lambda _: cuerpo, now=lambda: datetime(2026, 11, 14, tzinfo=timezone.utc), pause=0, max_days=5,
        manifest=manifiesto,
    )
    assert len(rutas) == 1
    entrada = json.loads(manifiesto.read_text(encoding="utf-8").splitlines()[0])
    assert entrada["archivo"].startswith("firms_api/MODIS_NRT/")
    assert not (tmp_path / "data" / "raw" / "manifest.jsonl").exists()


# ------------------------------------------------------------------ interfaz del globo
@pytest.mark.parametrize("ruta", ["globo.js", "vendor/maplibre/maplibre-gl.js", "vendor/maplibre/maplibre-gl.css",
                                  "vendor/maplibre/LICENSE", "datos/mundo_paises.geojson"])
def test_recursos_del_globo_locales(cliente, ruta):
    assert cliente.get(f"/ui/{ruta}").status_code == 200


def test_maplibre_va_antes_de_globo_y_de_app():
    orden = [HTML.index(f'src="{s}"') for s in ("vendor/maplibre/maplibre-gl.js", "globo.js", "app.js")]
    assert orden == sorted(orden)
    assert "MapLibre GL JS" in (ESTATICOS / "vendor" / "maplibre" / "maplibre-gl.js").read_text(encoding="utf-8")[:200]


def test_globo_solo_carga_remotos_autorizados():
    for m in re.finditer(r"https?://[^\s\"'`)<>]+", GLOBO):
        url = m.group(0)
        antes = GLOBO[max(0, m.start() - 8): m.start()]
        # ADR 0014: además de GIBS, solo las teselas de OpenStreetMap de la base mínima «Vías e
        # infraestructura» (GIBS no publica vías); el proveedor ya estaba en REMOTOS_PERMITIDOS (ADR 0008).
        # ADR 0017: detalle hidrográfico mundial mediante OpenFreeMap/OpenStreetMap.
        permitido = url.startswith(("https://gibs.earthdata.nasa.gov/wmts/", "https://tile.openstreetmap.org/", "https://tiles.openfreemap.org/"))
        assert permitido or antes.endswith('href="'), url
    assert "NASA FIRMS" in GLOBO and "LANCE" in GLOBO          # D-10 también en el globo
    assert "geoBoundaries" in GLOBO and "NASA GIBS" in GLOBO
    assert "import(" not in GLOBO


def test_planeta_con_proyeccion_continua_y_estilo_fijo():
    assert 'projection: { type: "globe" }' in GLOBO
    assert 'maxZoom: 17' in GLOBO
    assert 'opciones.alExplorar(c.lng' not in GLOBO
    assert '"raster-opacity": 1, "raster-saturation": 0' in GLOBO
    assert "Black_Marble" not in GLOBO
    assert "prefers-reduced-motion" in GLOBO


def test_simbologia_por_frp_y_sin_textos_falsos():
    assert "misma escala que el calendario" not in JS
    assert "const CORTES_FRP = [5, 20, 100, 500];" in JS and "CORTES_FRP = [5, 20, 100, 500]" in GLOBO
    assert "confianza_clase" in GLOBO and "Rombo" not in JS
    assert "Guía de colores, temperatura y precisión" in HTML
    assert 'id="aviso-truncado"' in HTML and 'role="alert"' in HTML
    assert "&limite=50000" in JS


def test_globo_js_sintaxis_valida():
    node = shutil.which("node")
    if not node:
        pytest.skip("node no está instalado")
    r = subprocess.run([node, "--check", str(ESTATICOS / "globo.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
