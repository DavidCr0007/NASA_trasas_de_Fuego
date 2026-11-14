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
    ["", "vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "app.js", "styles.css"],
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
    assert "addAttribution" in JS
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
def test_imagen_gibs_en_panel_propio_sin_filtro_oscuro():
    assert 'createPane("imagen")' in JS and 'pane: "imagen"' in JS
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
    assert "geoBoundaries" in JS and "DANE, CC BY 4.0" in JS


def test_area_y_limites_en_svg_para_conservar_el_tema():
    # Canvas ignora las clases CSS: el área y los límites deben usar el renderizador SVG.
    assert re.search(r"L\.rectangle\([^;]*renderer:\s*svgVector", JS)
    assert re.search(r"L\.geoJSON\([^;]*renderer:\s*svgVector", JS, flags=re.S)


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
