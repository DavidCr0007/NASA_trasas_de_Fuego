"""H6-07: pruebas estáticas de la interfaz (sin red, sin navegador).

Se leen index.html, app.js y styles.css tal como están y se comprueba, con
regex, lo que la interfaz promete: sin recursos remotos obligatorios, temas
claro/oscuro coherentes, contraste AA calculado, Leaflet tematizado, selector
de tema, cita D-10, insignia de origen y robustez de pedir().
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ingest.firms_schema import HUILA_BBOX
from fastapi.testclient import TestClient

from api.app import create_app
from harmonize.pipeline import main as pipeline_main

RAIZ = Path(__file__).resolve().parent.parent
ESTATICOS = RAIZ / "src" / "ui" / "static"
HTML = (ESTATICOS / "index.html").read_text(encoding="utf-8")
JS = (ESTATICOS / "app.js").read_text(encoding="utf-8")
CSS = (ESTATICOS / "styles.css").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cliente(tmp_path_factory) -> TestClient:
    destino = tmp_path_factory.mktemp("demo_interfaz")
    assert pipeline_main(["--input", str(RAIZ / "data" / "sample"), "--output", str(destino)]) == 0
    return TestClient(create_app(destino, anios_minimos=5))


# ------------------------------------------------------------ utilidades CSS
def _tokens(cuerpo: str) -> dict[str, str]:
    return {k: v.strip().lower() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", cuerpo)}


def _bloque(patron: str) -> dict[str, str]:
    m = re.search(patron + r"\s*\{([^{}]*)\}", CSS)
    assert m, f"no se encontró el bloque {patron}"
    return _tokens(m.group(1))


def _temas() -> dict[str, dict[str, str]]:
    claro = _bloque(r"(?m)^:root")
    oscuro = _bloque(r':root\[data-tema="oscuro"\]')
    medios = _bloque(r'@media \(prefers-color-scheme: dark\)\s*\{\s*:root:not\(\[data-tema="claro"\]\)')
    return {"claro": claro, "oscuro": oscuro, "sistema-oscuro": medios}


def _luminancia(hexa: str) -> float:
    h = hexa.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    canales = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        canales.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * canales[0] + 0.7152 * canales[1] + 0.0722 * canales[2]


def _contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------------------------------------------------------------- 1. sin red
def test_html_sin_recursos_remotos():
    for src in re.findall(r"<script[^>]*\bsrc\s*=\s*[\"']([^\"']+)", HTML):
        assert not re.match(r"(https?:)?//", src), src
    for href in re.findall(r"<link[^>]*\bhref\s*=\s*[\"']([^\"']+)", HTML):
        assert not re.match(r"(https?:)?//", href), href
    assert not re.search(r"<(img|iframe|source|video|audio)[^>]*\bsrc\s*=\s*[\"'](https?:)?//", HTML)


def test_css_sin_recursos_remotos():
    assert "@import" not in CSS
    assert not re.search(r"url\(\s*[\"']?(https?:)?//", CSS)
    assert "@font-face" not in CSS
    assert "fonts.googleapis" not in CSS and "fonts.gstatic" not in CSS


@pytest.mark.parametrize(
    "ruta",
    ["", "vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "app.js", "styles.css",
     "zonas.js", "capas.js", "datos/huila_departamento.geojson", "datos/hidrografia_mundial.geojson",
     "datos/ciudades_colombia.geojson"],
)
def test_recursos_locales_responden(cliente, ruta):
    r = cliente.get(f"/ui/{ruta}")
    assert r.status_code == 200, ruta


# Recursos remotos permitidos, todos OPCIONALES (la demo funciona sin red):
# teselas OSM, imagen del día de NASA GIBS (H7-02) y clima de Open-Meteo (H7-03).
REMOTOS_PERMITIDOS = (
    "https://tile.openstreetmap.org/",
    "https://gibs.earthdata.nasa.gov/wmts/",
    "https://archive-api.open-meteo.com/v1/archive",
    "https://tiles.openfreemap.org/",
)


def test_app_js_solo_carga_recursos_remotos_permitidos():
    for m in re.finditer(r"https?://[^\s\"'`)<>]+", JS):
        url = m.group(0)
        antes = JS[max(0, m.start() - 8) : m.start()]
        if url.startswith(REMOTOS_PERMITIDOS):
            continue
        # Enlaces de navegación (los abre el usuario; no se cargan solos): atributo href o a.href = `…`.
        es_enlace = antes.endswith(('href="', "href='", "href = `"))
        assert es_enlace, f"recurso remoto inesperado: {url}"
    # El único fetch remoto es el del clima, y su fallo no bloquea la interfaz.
    remotos = re.findall(r"fetch\(\s*([^,)]+)", JS)
    assert all(not r.strip().startswith(("'http", '"http', "`http")) for r in remotos)
    assert "No se pudo consultar el clima" in JS
    assert "import(" not in JS and not re.search(r"^\s*import\s", JS, flags=re.M)


# ----------------------------------------------------------------- 2. temas
def test_existen_los_tres_bloques_de_tema():
    t = _temas()
    assert t["claro"] and t["oscuro"] and t["sistema-oscuro"]
    assert t["claro"]["--tinta"] != t["oscuro"]["--tinta"]


def test_tema_oscuro_manual_y_del_sistema_son_identicos():
    t = _temas()
    assert t["oscuro"] == t["sistema-oscuro"]


def test_cada_token_de_color_claro_se_redefine_en_oscuro():
    t = _temas()
    color = re.compile(r"^#[0-9a-f]{3,8}$")
    colores = [k for k, v in t["claro"].items() if color.match(v)]
    assert len(colores) > 20
    # Excepciones por diseño: puntos NRT idénticos (blanco con borde oscuro) en ambos temas.
    for k in colores:
        assert k in t["oscuro"], f"{k} sin redefinir en oscuro"


def test_filtro_de_teselas_solo_en_teselas():
    t = _temas()
    assert t["claro"]["--filtro-teselas"] == "none"
    assert t["oscuro"]["--filtro-teselas"] not in ("", "none")
    reglas = [
        (sel, cuerpo)
        for sel, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS)
        if "var(--filtro-teselas)" in cuerpo
    ]
    assert reglas, "ninguna regla aplica --filtro-teselas"
    # Un solo selector: si se filtran el panel y la capa a la vez, la doble inversión
    # devuelve las teselas a sus colores claros.
    selectores = [s.strip() for sel, _ in reglas for s in sel.split(",")]
    assert len(selectores) == 1, selectores
    for sel, _ in reglas:
        assert "tile" in sel or "teselas" in sel, sel
        for prohibido in ("marker", "overlay", "path", "foco", "popup", "leaflet-container"):
            assert prohibido not in sel, sel
    # y ninguna regla de marcadores usa el filtro
    assert "filter" not in "".join(
        c for s, c in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS) if "path.foco" in s
    )


# ------------------------------------------------------------- 3. contraste
PARES_TEXTO = [
    ("tinta", "fondo"), ("tinta", "tarjeta"), ("tenue", "fondo"), ("tenue", "tarjeta"),
    ("enlace", "tarjeta"), ("enlace", "fondo"),
    ("aviso-tinta", "aviso-fondo"), ("ok-tinta", "ok-fondo"), ("info-tinta", "info-fondo"),
    ("error-tinta", "error-fondo"), ("barra-tinta", "barra-fondo"), ("barra-tenue", "barra-fondo"),
    ("insignia-tinta", "insignia-fondo"), ("prel-tinta", "prel-fondo"), ("est-tinta", "est-fondo"),
    ("sint-tinta", "sint-fondo"), ("real-tinta", "real-fondo"), ("mixto-tinta", "mixto-fondo"),
    ("tooltip-tinta", "tooltip-fondo"), ("boton-tinta", "boton-fondo"),
]
PARES_GRAFICO = [
    ("inusual", "tarjeta"), ("foco", "tarjeta"), ("sel", "tarjeta"),
    ("e1", "tarjeta"), ("e2", "tarjeta"), ("e3", "tarjeta"), ("e4", "tarjeta"),
    ("modis", "mapa-fondo"), ("viirs", "mapa-fondo"),
]


def _tema(nombre: str) -> dict[str, str]:
    return _temas()[nombre]


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
@pytest.mark.parametrize("par", PARES_TEXTO, ids=lambda p: "-".join(p))
def test_contraste_texto_aa(tema, par):
    t = _tema(tema)
    primero, segundo = (f"--{n}" for n in par)
    assert primero in t and segundo in t
    assert _contraste(t[primero], t[segundo]) >= 4.5, (tema, par, t[primero], t[segundo])


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
@pytest.mark.parametrize("par", PARES_GRAFICO, ids=lambda p: "-".join(p))
def test_contraste_grafico_aa(tema, par):
    t = _tema(tema)
    primero, segundo = (f"--{n}" for n in par)
    assert _contraste(t[primero], t[segundo]) >= 3.0, (tema, par, t[primero], t[segundo])


@pytest.mark.parametrize("tema, sentido", [("claro", -1), ("oscuro", 1)])
def test_escala_del_calendario_monotona(tema, sentido):
    t = _tema(tema)
    lum = [_luminancia(t[f"--e{i}"]) for i in range(5)]
    for a, b in zip(lum, lum[1:]):
        assert (b - a) * sentido > 0, (tema, lum)


# ------------------------------------------------------------- 4. Leaflet
@pytest.mark.parametrize(
    "selector",
    [".leaflet-popup-content-wrapper", ".leaflet-popup-tip", ".leaflet-bar a",
     ".leaflet-bar a:focus", ".leaflet-container a.leaflet-popup-close-button:focus",
     # Misma o mayor especificidad que leaflet.css, para que el tema oscuro gane:
     ".leaflet-container .leaflet-control-attribution",
     ".leaflet-container a.leaflet-popup-close-button", ".leaflet-bar a.leaflet-disabled",
     ".leaflet-container"],
)
def test_leaflet_tematizado(selector):
    for sel, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        lista = [s.strip() for s in sel.split(",")]
        if selector in lista and "var(--" in cuerpo:
            return
    pytest.fail(f"{selector} no usa variables de tema")


# --------------------------------------------------------- 5. selector tema
def test_selector_de_tema_en_html():
    m = re.search(r'<select[^>]*id="sel-tema"[^>]*>(.*?)</select>', HTML, flags=re.S)
    assert m
    assert set(re.findall(r'<option value="([^"]+)"', m.group(1))) >= {"sistema", "claro", "oscuro"}


def test_script_en_linea_antes_de_styles():
    head = HTML.split("</head>")[0]
    pos_css = head.index('href="styles.css"')
    scripts = [m for m in re.finditer(r"<script>(.*?)</script>", head, flags=re.S) if m.start() < pos_css]
    assert scripts, "falta el script en línea antes de styles.css"
    cuerpo = scripts[0].group(1)
    assert "localStorage" in cuerpo and re.search(r"\btry\s*\{", cuerpo)
    assert cuerpo.index("try") < cuerpo.index("localStorage")
    assert "data-tema" in cuerpo


def test_app_js_guarda_tema_con_try_catch():
    assert '"hhn-tema"' in JS
    assert re.search(r"try\s*\{[^}]*localStorage", JS)
    assert re.search(r"catch\s*(\([^)]*\))?\s*\{", JS)
    assert 'setAttribute("data-tema"' in JS
    assert 'removeAttribute("data-tema"' in JS


# ------------------------------------------------------------ 6. cita D-10
def test_cita_d10_en_app_js_e_index():
    globo = (ESTATICOS / "globo.js").read_text(encoding="utf-8")
    assert "customAttribution" in globo and "LANCE / ESDIS" in globo
    assert "NASA FIRMS" in JS and "LANCE" in JS
    assert '$("cita").textContent = c.cita' in JS
    assert '$("aviso").textContent = c.aviso' in JS
    assert 'id="cita"' in HTML and 'id="aviso"' in HTML


def test_calendario_devuelve_cita_y_aviso(cliente):
    c = cliente.get("/calendario", params={"bbox": ",".join(map(str, HUILA_BBOX))}).json()
    assert c["cita"] and c["aviso"]


# -------------------------------------------------- 7. insignia de origen
def test_insignia_de_origen(cliente):
    assert 'id="insignia-origen"' in HTML
    assert "origen_datos" in JS
    assert "DATOS SINTÉTICOS (demostración)" in JS
    assert "Datos reales NASA FIRMS" in JS
    assert "PRELIMINAR" in JS  # D-02


def test_calendario_de_la_muestra_es_sintetico(cliente):
    c = cliente.get("/calendario", params={"bbox": ",".join(map(str, HUILA_BBOX))}).json()
    assert c["origen_datos"] == "sintetico"


# ------------------------------------------------- 8. aviso de emergencia
def test_aviso_de_emergencia_citado_y_traducido():
    assert "Do not use for the preservation of life or property" in HTML
    assert "No usar para proteger vidas ni bienes" in HTML


# ------------------------------------------------------------ 9. robustez
def test_pedir_lee_la_respuesta_una_sola_vez():
    m = re.search(r"async function pedir\b.*?\n\}\n", JS, flags=re.S)
    assert m, "no se encontró pedir()"
    assert m.group(0).count(".json()") <= 1
    assert "r.text()" in m.group(0)


def test_hay_reintento():
    assert 'id="btn-reintentar"' in HTML or "Reintentar" in HTML or "Reintentar" in JS


# ------------------------------------------------------------ 10. sintaxis
def test_app_js_sintaxis_valida():
    node = shutil.which("node")
    if not node:
        pytest.skip("node no está instalado")
    r = subprocess.run([node, "--check", str(ESTATICOS / "app.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_seleccion_distinta_de_inusual_en_ambos_temas():
    # La selección no debe confundirse con el borde de día inusual (revisión H6).
    for tema in ("claro", "oscuro"):
        t = _temas()[tema]
        assert t["--sel"].lower() != t["--inusual"].lower()
        assert _contraste(t["--sel"], t["--inusual"]) >= 1.8, tema


def test_estado_vacio_no_ocupa_espacio():
    assert re.search(r"\.estado:not\(\.cargando\):not\(\.vacio\):not\(\.error\)\s*\{[^}]*display:\s*none", CSS)


# ------------------------------------------------- H7: fuentes complementarias
def test_imagen_gibs_en_capa_propia_sin_filtro_oscuro():
    globo = (ESTATICOS / "globo.js").read_text(encoding="utf-8")
    assert 'globo.imagen(' in JS and 'id:"imagen",type:"raster"' in globo
    assert "NASA GIBS" in JS
    # El filtro del tema oscuro solo actúa sobre .leaflet-tile-pane (ver
    # test_filtro_de_teselas_solo_en_teselas); la imagen va en otro panel y no se invierte.
    assert 'id="sel-imagen"' in HTML and "disabled" in re.search(r'<select id="sel-imagen"[^>]*>', HTML).group(0)


def test_clima_rotulado_como_reanalisis_con_credito():
    assert "Clima (reanálisis)" in HTML
    assert "Open-Meteo.com" in HTML and "CC BY 4.0" in HTML
    assert "no observaciones" in HTML


def test_limites_locales_con_credito():
    assert "/ui/datos/huila_municipios.geojson" in JS
    globo = (ESTATICOS / "globo.js").read_text(encoding="utf-8")
    assert "geoBoundaries" in globo and "DANE, CC BY 4.0 para COL ADM2" in globo


def test_un_solo_lienzo_y_limites_vectoriales():
    globo = (ESTATICOS / "globo.js").read_text(encoding="utf-8")
    assert "L.map(" not in JS and "vendor/leaflet/leaflet.js" not in HTML
    assert 'id: "area-seleccion", type: "line"' in globo
    assert 'source: `adm${nivel}`' in globo


def test_conexion_con_nasa_firms():
    # Enlaces oficiales de la sección «Discover FIRMS» (earthdata.nasa.gov/data/tools/firms).
    for url in ("https://firms.modaps.eosdis.nasa.gov/map/", "https://firms.modaps.eosdis.nasa.gov/active_fire/",
                "https://firms.modaps.eosdis.nasa.gov/download/", "https://firms.modaps.eosdis.nasa.gov/web-services/",
                "https://firms.modaps.eosdis.nasa.gov/alerts/", "https://www.earthdata.nasa.gov/data/tools/firms/faq"):
        assert url in HTML, url
    assert 'id="enlace-firms"' in HTML and 'rel="noopener"' in HTML
    assert "function actualizarEnlaceFirms" in JS


def test_huila_y_municipios_consultan_por_forma():
    assert "area=${encodeURIComponent(estado.area)}" in JS
    assert 'area: "huila"' in JS


# ------------------------------------------------- H8-07 (C3): rampa apta para daltonismo
# Matrices de Machado, Oliveira y Fernandes (2009), severidad 1,0, sobre RGB lineal.
MACHADO = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def _lineal(h: str) -> list[float]:
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def _l_estrella(rgb_lineal: list[float]) -> float:
    y = 0.2126 * rgb_lineal[0] + 0.7152 * rgb_lineal[1] + 0.0722 * rgb_lineal[2]
    return 116 * (y ** (1 / 3)) - 16 if y > 0.008856 else 903.3 * y


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
@pytest.mark.parametrize("vision", ["normal", "protanopia", "deuteranopia", "tritanopia"])
def test_rampa_monotona_y_distinguible_con_daltonismo(tema, vision):
    t = _temas()[tema]
    ls = []
    for paso in ("--e0", "--e1", "--e2", "--e3", "--e4"):
        rgb = _lineal(t[paso])
        if vision != "normal":
            m = MACHADO[vision]
            rgb = [min(1.0, max(0.0, sum(m[i][j] * rgb[j] for j in range(3)))) for i in range(3)]
        ls.append(_l_estrella(rgb))
    difs = [b - a for a, b in zip(ls, ls[1:])]
    # Monótona (todos los pasos en el mismo sentido) y cada paso a ≥ 5 unidades de L*.
    assert all(d > 0 for d in difs) or all(d < 0 for d in difs), (tema, vision, [round(x, 1) for x in ls])
    assert min(abs(d) for d in difs) >= 5, (tema, vision, [round(x, 1) for x in ls])


# ================================================= ADR 0013: visor de capas
# Las funciones puras de zonas.js y capas.js se ejecutan con node (sin navegador ni red);
# el comportamiento en el mapa real lo recorre tools/recorrido_capas.mjs.
import json  # noqa: E402

CAPAS_JS = (ESTATICOS / "capas.js").read_text(encoding="utf-8")
ZONAS_JS = (ESTATICOS / "zonas.js").read_text(encoding="utf-8")
GLOBO_JS = (ESTATICOS / "globo.js").read_text(encoding="utf-8")
BUSQUEDA_JS = (ESTATICOS / "busqueda.js").read_text(encoding="utf-8")
DATOS = ESTATICOS / "datos"
NEIVA = (-75.2819, 2.9273)


def _node(cuerpo: str):
    """Ejecuta `cuerpo` en node con Zonas, Capas y los límites locales; devuelve su JSON."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node no está instalado")
    preambulo = (
        "const fs = require('fs');"
        f"const Zonas = require({json.dumps(str(ESTATICOS / 'zonas.js'))});"
        f"const Capas = require({json.dumps(str(ESTATICOS / 'capas.js'))});"
        f"const municipios = JSON.parse(fs.readFileSync({json.dumps(str(DATOS / 'huila_municipios.geojson'))}, 'utf8')).features;"
        f"const departamentos = JSON.parse(fs.readFileSync({json.dumps(str(DATOS / 'huila_departamento.geojson'))}, 'utf8')).features;"
        f"const ciudades = JSON.parse(fs.readFileSync({json.dumps(str(DATOS / 'ciudades_colombia.geojson'))}, 'utf8')).features;"
    )
    r = subprocess.run([node, "-e", preambulo + f"console.log(JSON.stringify((() => {{ {cuerpo} }})()));"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ---------------------------------------------------------- capas por defecto
def test_capas_por_defecto():
    d = _node("return { def: Capas.POR_DEFECTO, preajuste: Capas.preajusteActivo(Capas.POR_DEFECTO),"
              " catalogo: Capas.CATALOGO.map(c => [c.grupo, c.id]), resumen: Capas.resumen(Capas.POR_DEFECTO) };")
    k = d["def"]["capas"]
    assert d["def"]["base"] == "relieve" and d["preajuste"] == "mapa"
    assert k["sombra"] == {"on": True, "opacidad": 0.45, "mezcla": "multiplicar"}
    assert k["rios"]["on"] and k["rios"]["mezcla"] == "normal"
    assert all(k[s]["on"] for s in ("modis", "noaa20", "noaa21", "snpp", "armonizados", "limites"))
    assert k["clima"]["on"] is False
    grupos = {}
    for g, i in d["catalogo"]:
        grupos.setdefault(g, []).append(i)
    assert grupos["base"] == ["relieve", "satelital", "hidrografia", "vias", "ninguna"]
    assert grupos["focos"] == ["modis", "noaa20", "noaa21", "snpp", "armonizados"]
    assert grupos["contexto"] == ["limites", "clima"]
    assert "Relieve" in d["resumen"] and "Límites" in d["resumen"]


def test_estado_guardado_se_valida_y_los_preajustes_cambian_la_base():
    d = _node(
        "const malo = Capas.normalizar({version: 1, base: 'lava', capas: {rios: {on: false, opacidad: 7, mezcla: 'multiplicar'},"
        " sombra: {mezcla: 'trama'}}});"
        "const viejo = Capas.normalizar({version: 0, base: 'satelital'});"
        "const p = Object.fromEntries(['mapa','fuego','agua','vias'].map(id => [id, Capas.aplicarPreajuste(Capas.POR_DEFECTO, id)]));"
        "return { malo, viejo, p, activo: Capas.preajusteActivo(p.agua) };")
    assert d["malo"]["base"] == "relieve"
    assert d["malo"]["capas"]["rios"] == {"on": False, "opacidad": 1, "mezcla": "normal"}  # mezcla no admitida
    assert d["malo"]["capas"]["sombra"]["mezcla"] == "trama"
    assert d["viejo"]["base"] == "relieve"  # otra versión: valores por defecto
    assert d["p"]["fuego"]["base"] == "satelital" and d["p"]["fuego"]["capas"]["sombra"]["mezcla"] == "multiplicar"
    assert d["p"]["agua"]["base"] == "hidrografia" and d["p"]["agua"]["capas"]["rios"]["on"]
    assert d["activo"] == "agua"
    # Preajuste mínimo (ADR 0014): vías en grises, sin sombreado ni ríos.
    vias = d["p"]["vias"]
    assert vias["base"] == "vias" and not vias["capas"]["sombra"]["on"] and not vias["capas"]["rios"]["on"]
    assert vias["capas"]["limites"]["on"] and vias["capas"]["modis"]["opacidad"] == 1


def test_capas_en_localstorage_con_try_catch_y_sin_servidor():
    assert '"hhn-capas"' in CAPAS_JS
    usos = list(re.finditer(r"localStorage\.(getItem|setItem)", CAPAS_JS))
    assert len(usos) == 2
    for m in usos:
        linea = CAPAS_JS[CAPAS_JS.rfind("\n", 0, m.start()): m.start()]
        assert re.search(r"\btry\s*\{", linea), "localStorage fuera de try"
    assert len(re.findall(r"catch\s*\{", CAPAS_JS)) >= 2
    assert "fetch(" not in CAPAS_JS and "XMLHttpRequest" not in CAPAS_JS


def test_panel_de_capas_accesible_por_teclado():
    assert re.search(r'<button id="btn-capas"[^>]*aria-expanded="true"[^>]*aria-controls="panel-capas"', HTML)
    assert 'id="panel-capas"' in HTML and 'aria-label="Capas del mapa"' in HTML
    # Grupos y ajustes colapsables con aria-expanded/aria-controls; cada capa con nombre visible.
    assert 'class="grupo-alternar" aria-expanded="true" aria-controls="grupo-' in CAPAS_JS
    assert 'class="capa-ajustar" aria-expanded="false" aria-controls="ajustes-' in CAPAS_JS
    assert 'aria-label="Opacidad y mezcla de' in CAPAS_JS
    assert 'type="radio" name="capa-base"' in CAPAS_JS  # una sola base activa
    assert re.search(r'if \(ev\.key === "Escape"\)[^\n]*boton\.focus\(\)', JS)
    assert re.search(r":focus-visible[^{]*\{[^}]*outline: 3px solid var\(--foco\)", CSS)


def test_mezcla_real_solo_donde_el_motor_la_admite():
    # Sombreado: multiplicar = negro con alfa 1 − g; trama = blanco con alfa g (globo.js).
    assert 'mezclas: ["multiplicar", "normal", "trama"]' in CAPAS_JS
    assert "multiplicar ? 1 - g : g" in GLOBO_JS
    assert 'maplibregl.addProtocol("sombra"' in GLOBO_JS
    # Las demás capas muestran el selector desactivado con una explicación.
    assert "Este motor dibuja esta capa solo en modo normal" in CAPAS_JS


# ------------------------------------------------------ límites siempre visibles
def test_limites_siempre_visibles_sobre_cualquier_base():
    ids = [a or b for a, b in re.findall(r'\{ id: "([\w-]+)"|id: `(limites-adm)\$', GLOBO_JS)]
    for base in ("fondo", "satelital", "sombra", "lagos", "rios", "zona-mascara"):
        assert ids.index(base) < ids.index("limites-municipio"), base
    assert ids.index("limites-departamento") < ids.index("detalle-focos") < ids.index("area-seleccion")
    # Sin minzoom: las líneas no dependen del zoom; solo las etiquetas (zonas.etiquetasVisibles).
    for capa in ("limites-municipio", "limites-departamento"):
        definicion = re.search(r'\{ id: "%s".*?\} \},' % capa, GLOBO_JS, flags=re.S).group(0)
        assert "zoom" not in definicion, capa
    # Su visibilidad depende solo de la casilla «Límites», nunca de la base.
    assert 'visible("limites-municipio", k.limites.on)' in GLOBO_JS
    assert 'visible("limites-departamento", k.limites.on)' in GLOBO_JS
    assert not re.search(r'visible\(\s*"limites-[\w-]+",[^)]*base', GLOBO_JS)
    assert "/ui/datos/huila_departamento.geojson" in JS and "globo.limitesLocales(" in JS


def test_etiquetas_cambian_con_el_zoom():
    d = _node("return [4, 6, Zonas.UMBRAL_ZOOM_MUNICIPIO - 0.01, Zonas.UMBRAL_ZOOM_MUNICIPIO, 12].map(Zonas.etiquetasVisibles);")
    assert d[0] == {"departamento": False, "municipio": False}
    assert d[1] == d[2] == {"departamento": True, "municipio": False}
    assert d[3] == d[4] == {"departamento": False, "municipio": True}


# -------------------------------------- resaltado: municipio contra departamento
def test_umbral_de_zoom_documentado():
    m = re.search(r"((?://[^\n]*\n\s*)+)const UMBRAL_ZOOM_MUNICIPIO = (\d+(?:\.\d+)?);", ZONAS_JS)
    assert m, "falta la constante comentada"
    assert "PROVISIONAL" in m.group(1) and "prueba visual" in m.group(1)
    assert 5 <= float(m.group(2)) <= 12


GARZON_RURAL = (-75.5628, 2.1630)  # municipio de Garzón, fuera de toda área urbana de Natural Earth


@pytest.mark.parametrize("punto, umbral, delta, nivel, nombre, contexto", [
    (NEIVA, "MUNICIPIO", -0.1, "departamento", "Huila", None),
    (NEIVA, "MUNICIPIO", 0, "municipio", "Neiva", "Huila"),
    (NEIVA, "CIUDAD", -0.1, "municipio", "Neiva", "Huila"),
    (NEIVA, "CIUDAD", 0, "ciudad", "Neiva", "Neiva"),  # área urbana con su municipio como contexto
    (GARZON_RURAL, "CIUDAD", 2, "municipio", "Garzón", "Huila"),  # sin área urbana: baja al municipio
])
def test_resaltado_de_ciudad_municipio_o_departamento_segun_zoom(punto, umbral, delta, nivel, nombre, contexto):
    d = _node(f"const s = Zonas.zonaSeleccionada({punto[0]}, {punto[1]}, Zonas.UMBRAL_ZOOM_{umbral} + ({delta}),"
              " {departamentos, municipios, ciudades});"
              "return { nivel: s.nivel, nombre: s.zona.properties.shapeName, contexto: s.contexto?.properties.shapeName ?? null };")
    assert d == {"nivel": nivel, "nombre": nombre, "contexto": contexto}


def test_umbral_de_ciudad_documentado_y_mayor_que_el_municipal():
    m = re.search(r"((?://[^\n]*\n\s*)+)const UMBRAL_ZOOM_CIUDAD = (\d+(?:\.\d+)?);", ZONAS_JS)
    assert m and "PROVISIONAL" in m.group(1) and "prueba visual" in m.group(1)
    assert float(m.group(2)) > float(re.search(r"const UMBRAL_ZOOM_MUNICIPIO = (\d+)", ZONAS_JS).group(1))


def test_zona_se_recalcula_al_cruzar_un_umbral_y_fuera_del_huila_se_pide_el_pais():
    assert 'mapa.on("zoomend", reevaluarZonaPorZoom)' in JS
    assert re.search(r"function reevaluarZonaPorZoom\(\).*?nivelResaltado\(mapa\.getZoom\(\)\)", JS, flags=re.S)
    # País del punto con los países locales (Natural Earth) y sus ADM1/ADM2 vía /limites (geoBoundaries).
    assert "window.Zonas.zonaDe(lon, lat, paisesMundo)" in JS and "globo.limitesDe(iso, n)" in JS
    assert "fetch(`/limites/${iso}/${nivel}`)" in GLOBO_JS
    # El nombre de la zona resaltada se dibuja sobre el mapa, y la tarjeta encuadra la zona completa.
    assert '"etiqueta-zona"' in GLOBO_JS and 'id="zona-encuadrar"' in HTML and "Ver zona completa" in HTML
    # Nombres de ADM1/ADM2 cargados para la vista, acotados.
    assert "MAX_ETIQUETAS_ADM = 60" in GLOBO_JS


def test_punto_fuera_de_zona_y_mascara_con_hueco():
    d = _node("const fuera = Zonas.zonaSeleccionada(-74.08, 4.6, 10, {departamentos, municipios});"
              "const m = Zonas.mascara(departamentos[0].geometry);"
              "return { fuera, anillos: m.geometry.coordinates.length,"
              " dentro: Zonas.contiene(m.geometry, -75.28, 2.93), lejos: Zonas.contiene(m.geometry, 0, 0) };")
    assert d["fuera"] is None  # Bogotá no está en el Huila
    assert d["anillos"] == 2 and d["dentro"] is False and d["lejos"] is True


def test_pertenencia_en_el_cliente_cuenta_focos_y_celdas():
    d = _node("const det = [{lon: -75.28, lat: 2.93, confianza_clase: 'alta', cell_id: 'f10325_c11635', frp: 3},"
              " {lon: -75.281, lat: 2.931, confianza_clase: 'baja', cell_id: 'f10325_c11635', frp: 40},"
              " {lon: -74.08, lat: 4.6, confianza_clase: 'alta', cell_id: 'f10511_c11769', frp: 1}];"
              "const neiva = municipios.find(m => m.properties.shapeName === 'Neiva');"
              "const c = Zonas.celdasActivas(det);"
              "return { cuenta: Zonas.contarEn(neiva.geometry, det), celdas: c.features.length,"
              " frp: c.features[0].properties.frp_max, esquina: c.features[0].geometry.coordinates[0][0] };")
    assert d["cuenta"] == {"n": 2, "alta": 1}
    assert d["celdas"] == 2 and d["frp"] == 40
    # Celda f10325_c11635 de la grilla R1: origen (-90, -180), lado 0,009°.
    assert d["esquina"] == pytest.approx([-180 + 11635 * 0.009, -90 + 10325 * 0.009])


def test_tarjeta_de_zona_con_las_cifras_pedidas():
    for id_ in ("zona-titulo", "zona-focos", "zona-alta", "zona-origen", "zona-fecha"):
        assert f'id="{id_}"' in HTML, id_
    assert "Focos en el periodo" in HTML and "Confianza alta" in HTML and "Fecha (UTC)" in HTML
    assert "/calendario?area=${encodeURIComponent(area)}" in JS  # agregados con la ruta existente
    assert "Sintético (demostración)" in JS and "alSeleccionarPunto" in GLOBO_JS


# ------------------------------------------------------------------ búsqueda
@pytest.mark.parametrize("consulta, primero, nivel", [
    ("garzon", "Garzón", "municipio"), ("GARZÓN", "Garzón", "municipio"),
    ("Neiva, Huila", "Neiva", "municipio"), ("municipio de La Plata", "La Plata", "municipio"),
    ("Huila", "Huila", "departamento"), ("pital", "Pital", "municipio"),
])
def test_busqueda_local_por_municipio_o_departamento(consulta, primero, nivel):
    d = _node(f"return Zonas.buscarLocal({json.dumps(consulta)}, {{municipios, departamentos}}).map(r => [r.nombre, r.nivel]);")
    assert d and d[0] == [primero, nivel], d


def test_busqueda_local_primero_y_remota_acotada():
    assert _node("return Zonas.buscarLocal('ab', {municipios, departamentos}).length;") == 0
    assert _node("return Zonas.buscarLocal('Bogotá', {municipios, departamentos}).length;") == 0
    envio = BUSQUEDA_JS[BUSQUEDA_JS.index('form.addEventListener("submit"'):]
    envio = envio[: envio.index("\n  });")]
    assert envio.index("buscarLocal(q)") < envio.index("buscarRemoto(q)")
    assert "INTERVALO_MS = 1000" in BUSQUEDA_JS and "navigator.onLine === false" in BUSQUEDA_JS
    assert "cache.get(claveCache)" in BUSQUEDA_JS and 'claveCache=idioma+":"+clave(q)' in BUSQUEDA_JS
    # La caché vive en memoria de la pestaña: nada de almacenamiento persistente.
    assert "localStorage" not in BUSQUEDA_JS and "sessionStorage" not in BUSQUEDA_JS
    assert "fetch(`/buscar-lugares?q=" in BUSQUEDA_JS


@pytest.mark.parametrize("consulta,niveles", [
    ("Colombia", ["pais", "municipio"]),
    ("país Colombia", ["pais"]),
    ("country Colombia", ["pais"]),
    ("municipio de Colombia", ["municipio"]),
    ("Colombia, Huila", ["municipio"]),
    ("Colombia, Huila, Colombia", ["municipio"]),
])
def test_colombia_distingue_pais_municipio_y_contexto(consulta, niveles):
    d = _node("const paises = [{properties:{nombre:'Colombia',iso_a3:'COL'}}];"
              f"return Zonas.buscarLocal({json.dumps(consulta)}, {{municipios,departamentos,paises}}).map(r=>r.nivel);")
    assert d == niveles


def test_busqueda_respeta_otro_departamento_y_muestra_jerarquia():
    d = _node("return {otro:Zonas.buscarLocal('Colombia, Antioquia',{municipios,departamentos}),"
              "local:Zonas.buscarLocal('Neiva, Huila, Colombia',{municipios,departamentos})[0].descripcion};")
    assert d["otro"] == []
    assert d["local"].startswith("Neiva, Huila, Colombia")


# ------------------------------------------------- contraste y color de acento
@pytest.mark.parametrize("tema", ["claro", "oscuro"])
@pytest.mark.parametrize("par", [("acento", "tarjeta"), ("acento", "fondo"), ("tarjeta", "acento")],
                         ids=lambda p: "-".join(p))
def test_contraste_del_acento_aa(tema, par):
    t = _tema(tema)
    assert _contraste(t[f"--{par[0]}"], t[f"--{par[1]}"]) >= 4.5, (tema, par)


def test_un_solo_color_de_acento_en_el_visor():
    nuevo = CSS[CSS.index("/* ADR 0013"):]
    colores = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", nuevo))
    # Solo sombras y las etiquetas del mapa (blanco con halo negro, fijas en ambos temas).
    # #062a26d9: fondo de la etiqueta de la zona = borde de la zona en el mapa (MAPA.zonaBorde, fijo).
    assert colores <= {"#ffffff", "#000", "#0003", "#0004", "#062a26d9"}, colores
    for selector in ('.capa[data-activa="true"]', '.capas-preajustes button[aria-pressed="true"]', ".tarjeta-zona"):
        regla = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", nuevo).group(1)
        assert "var(--acento)" in regla, selector


# ------------------------------------------ leyenda apta para daltonismo
def _lab(rgb):
    x = 0.4124 * rgb[0] + 0.3576 * rgb[1] + 0.1805 * rgb[2]
    y = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    z = 0.0193 * rgb[0] + 0.1192 * rgb[1] + 0.9505 * rgb[2]

    def f(v):
        return v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116

    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


@pytest.mark.parametrize("vision", ["normal", "protanopia", "deuteranopia", "tritanopia"])
def test_escala_frp_distinguible_con_daltonismo(vision):
    t = _temas()["claro"]
    labs = []
    for k in range(1, 6):
        rgb = _lineal(t[f"--f{k}"])
        if vision != "normal":
            m = MACHADO[vision]
            rgb = [min(1.0, max(0.0, sum(m[i][j] * rgb[j] for j in range(3)))) for i in range(3)]
        labs.append(_lab(rgb))
    # ΔE*76 ≥ 10 entre clases vecinas (mínimo medido: 12,3 en deuteranopía, f2–f3).
    for a, b in zip(labs, labs[1:]):
        assert sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5 >= 10, vision
    assert _temas()["oscuro"]["--f1"] == t["--f1"]  # misma escala en ambos temas


def test_leyenda_minima_con_frp_y_confianza_sin_depender_del_color():
    assert 'id="leyenda-mapa" class="leyenda-mapa flotante"' in HTML
    m = re.search(r"function pintarLeyendaMapa\(\).*?\n\}\n", JS, flags=re.S).group(0)
    assert "FRP (MW)" in m and "Confianza" in m and 'class="escala-frp"' in m
    # Confianza: opacidad y borde, los mismos valores que el mapa.
    assert '["alta", 0.95, 2], ["nominal", 0.8, 1], ["baja", 0.5, 0.5]' in m
    assert '"alta", 0.95, "baja", 0.5, 0.8' in GLOBO_JS
    assert '"circle-stroke-width": ["match", ["get", "confianza_clase"], "alta", 2, "baja", 0.5, 1]' in GLOBO_JS


# ------------------------------------------------------------------- pie
def test_pie_con_cita_avisos_utc_y_advertencia_sintetica():
    pie = HTML[HTML.index('<footer class="pie">'):]
    assert 'id="cita"' in pie and 'id="aviso"' in pie
    assert "No usar para proteger vidas ni bienes" in pie
    assert "Los focos son detecciones térmicas, no incendios confirmados" in pie
    assert "UTC" in pie
    assert re.search(r'id="pie-sintetico"[^>]*role="alert"[^>]*hidden', pie)
    assert "Advertencia: DATOS SINTÉTICOS de demostración" in JS
    for credito in ("NASA FIRMS", "NASA GIBS", "ASTER GDEM", "Natural Earth", "geoBoundaries", "DANE, CC BY 4.0", "Open-Meteo",
                    "© OpenStreetMap contributors"):
        assert credito in pie, credito


# ------------------------------------------ recursos remotos en todo el JS propio
JS_PROPIOS = sorted(ESTATICOS.glob("*.js"))


@pytest.mark.parametrize("archivo", JS_PROPIOS, ids=lambda p: p.name)
def test_js_propio_solo_carga_recursos_remotos_permitidos(archivo):
    texto = archivo.read_text(encoding="utf-8")
    for m in re.finditer(r"https?://[^\s\"'`)<>]+", texto):
        url = m.group(0)
        antes = texto[max(0, m.start() - 8): m.start()]
        es_enlace = antes.endswith(('href="', "href='", "href = `"))
        assert url.startswith(REMOTOS_PERMITIDOS) or es_enlace, f"{archivo.name}: {url}"
    for r in re.findall(r"fetch\(\s*([^,)]+)", texto):
        assert not r.strip().startswith(("'http", '"http', "`http")), f"{archivo.name}: fetch remoto literal {r}"
    assert "import(" not in texto and "importScripts" not in texto and "new Worker(" not in texto


def test_datos_locales_de_capas_con_licencia():
    depto = json.loads((DATOS / "huila_departamento.geojson").read_text(encoding="utf-8"))
    assert depto["metadatos"]["licencia"] == "CC BY 4.0" and "ODbL" in depto["metadatos"]["metodo"]
    urbes = json.loads((DATOS / "ciudades_colombia.geojson").read_text(encoding="utf-8"))
    assert urbes["metadatos"]["licencia"] == "Dominio público"
    assert {"Neiva", "Bogota", "Medellín"} <= {f["properties"]["shapeName"] for f in urbes["features"]}
    hidro = json.loads((DATOS / "hidrografia_mundial.geojson").read_text(encoding="utf-8"))
    assert hidro["metadatos"]["licencia"] == "Dominio público"
    assert any(f["properties"]["nombre"] == "Magdalena" for f in hidro["features"])


# ------------------------------------------------- ADR 0014: base mínima de vías
def test_base_minima_de_vias_en_grises_y_con_creditos():
    assert 'vias: "https://tile.openstreetmap.org/{z}/{x}/{y}.png"' in GLOBO_JS
    assert "https://tile.openstreetmap.org/" in REMOTOS_PERMITIDOS  # proveedor ya permitido (ADR 0008)
    capa = re.search(r'\{ id: "vias".*?\} \},', GLOBO_JS, flags=re.S).group(0)
    assert '"raster-saturation": -1' in capa and 'visibility: "none"' in capa
    assert "OpenStreetMap</a> contributors" in GLOBO_JS
    # Va bajo el sombreado, el agua y los límites: los límites y los focos quedan encima.
    ids = [a or b for a, b in re.findall(r'\{ id: "([\w-]+)"|id: `(limites-adm)\$', GLOBO_JS)]
    assert ids.index("satelital") < ids.index("vias") < ids.index("sombra") < ids.index("limites-municipio")
    assert 'visible("vias", base === "vias")' in GLOBO_JS
