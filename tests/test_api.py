"""H3: API de solo lectura (D-02, D-05, D-07, D-08, D-10).

Las expectativas se calculan aparte, leyendo los Parquet con pyarrow, para no
reutilizar la lógica de la API.
"""

from __future__ import annotations

import csv
import io
import re
import shutil
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from harmonize import RULES_VERSION
from harmonize.pipeline import main as pipeline_main
from ingest.firms_schema import HUILA_BBOX

RAIZ = Path(__file__).resolve().parent.parent
BBOX = ",".join(str(v) for v in HUILA_BBOX)


@pytest.fixture(scope="module")
def salida(tmp_path_factory) -> Path:
    destino = tmp_path_factory.mktemp("demo_api")
    assert pipeline_main(["--input", str(RAIZ / "data" / "sample"), "--output", str(destino)]) == 0
    return destino


@pytest.fixture(scope="module")
def cliente(salida) -> TestClient:
    return TestClient(create_app(salida, anios_minimos=5))


def _tabla(salida: Path, nombre: str) -> list[dict]:
    return pq.read_table(salida / f"{nombre}.parquet").to_pylist()


def _cita_literal() -> tuple[str, str]:
    texto = (RAIZ / "docs" / "cita.md").read_text(encoding="utf-8")

    def bloque(titulo: str) -> str:
        sec = texto.split(f"## {titulo}", 1)[1]
        citas = re.findall(r"^> ?(.*)$", sec.split("\n## ", 1)[0], flags=re.M)
        return " ".join(c.strip() for c in citas)

    return bloque("Cita obligatoria (FIRMS, LANCE y ESDIS)"), bloque("Aviso «as is»")


# ---------------------------------------------------------------- H3-01
def test_salud_ok(cliente):
    r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_salud_sin_parquet_responde_503(tmp_path):
    r = TestClient(create_app(tmp_path)).get("/salud")
    assert r.status_code == 503
    assert "falta" in r.json()["detalle"]


# ---------------------------------------------------------------- H3-04 (D-05)
@pytest.mark.parametrize("ruta", ["/salud", "/cita", f"/calendario?bbox={BBOX}", f"/detecciones?bbox={BBOX}"])
def test_version_de_reglas_en_cada_respuesta(cliente, salida, ruta):
    meta = pq.read_metadata(salida / "celda_dia.parquet").metadata
    cuerpo = cliente.get(ruta).json()
    assert cuerpo["rules_version"] == RULES_VERSION
    assert cuerpo["config_fingerprint"] == meta[b"config_fingerprint"].decode()


# ---------------------------------------------------------------- H3-06 (D-10)
@pytest.mark.parametrize("ruta", ["/salud", "/cita", f"/calendario?bbox={BBOX}", f"/detecciones?bbox={BBOX}"])
def test_cita_literal_en_cada_respuesta(cliente, ruta):
    cita, aviso = _cita_literal()
    cuerpo = cliente.get(ruta).json()
    assert cuerpo["cita"] == cita
    assert cuerpo["aviso"] == aviso
    assert "FIRMS" in cita and "LANCE" in cita and "ESDIS" in cita
    assert '"as is"' in aviso


def test_exportacion_csv_lleva_cita_aviso_y_version(cliente):
    cita, aviso = _cita_literal()
    r = cliente.get(f"/calendario.csv?bbox={BBOX}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lineas = r.text.splitlines()
    comentarios = [ln[2:] for ln in lineas if ln.startswith("# ")]
    assert cita in comentarios and aviso in comentarios
    assert any(RULES_VERSION in c for c in comentarios)
    assert any("preliminar" in c.lower() for c in comentarios)
    datos = list(csv.DictReader(io.StringIO("\n".join(ln for ln in lineas if not ln.startswith("#")))))
    assert datos and {"fecha_utc", "n_detecciones", "n_brutas", "calidad", "preliminar"} <= set(datos[0])


# ---------------------------------------------------------------- calendario
def test_calendario_cuenta_lo_mismo_que_celda_dia(cliente, salida):
    filas = _tabla(salida, "celda_dia")
    W, S, E, N = HUILA_BBOX
    dentro = [f for f in filas if S <= f["centroide_lat"] <= N and W <= f["centroide_lon"] <= E]
    esperado = Counter()
    for f in dentro:
        esperado[f["fecha_utc"].isoformat()] += f["n_detecciones"]
    dias = {d["fecha_utc"]: d for d in cliente.get(f"/calendario?bbox={BBOX}").json()["dias"]}
    assert {k: v["n_detecciones"] for k, v in dias.items() if v["n_detecciones"]} == dict(esperado)
    assert sum(d["n_brutas"] for d in dias.values()) == sum(f["n_brutas"] for f in dentro)


def test_calendario_rellena_dias_sin_dato(cliente):
    # Dentro de la cobertura (2026-11-10..12) un área sin focos da ceros explícitos.
    cuerpo = cliente.get("/calendario?bbox=10,10,11,11").json()
    assert [d["fecha_utc"] for d in cuerpo["dias"]] == ["2026-11-10", "2026-11-11", "2026-11-12"]
    vacio = cuerpo["dias"][0]
    assert vacio["n_detecciones"] == 0 and vacio["calidad"] is None and vacio["preliminar"] is False


def test_area_sin_focos_devuelve_ceros(cliente):
    cuerpo = cliente.get("/calendario?bbox=10,10,11,11&desde=2026-11-10&hasta=2026-11-12").json()
    assert [d["n_detecciones"] for d in cuerpo["dias"]] == [0, 0, 0]
    assert cuerpo["incertidumbre"]["porcentaje_dias_con_dato"] == 0.0


# ---------------------------------------------------------------- H3-02 (D-07)
def test_incertidumbre_resolucion_y_clases(cliente, salida):
    inc = cliente.get(f"/calendario?bbox={BBOX}").json()["incertidumbre"]
    assert inc["resolucion_m"] == {"MODIS": 1000, "VIIRS": 375}
    assert inc["grilla_deg"] == 0.009
    W, S, E, N = HUILA_BBOX
    det = [d for d in _tabla(salida, "detecciones") if S <= d["lat"] <= N and W <= d["lon"] <= E]
    assert inc["clases_confianza"] == {c: sum(d["confianza_clase"] == c for d in det)
                                       for c in ("baja", "nominal", "alta")}


def test_incertidumbre_horario_de_pasada(cliente, salida):
    pasadas = cliente.get(f"/calendario?bbox={BBOX}").json()["incertidumbre"]["horario_pasada_utc"]
    det = _tabla(salida, "detecciones")
    for sat in {d["satelite"] for d in det}:
        horas = sorted(d["fecha_hora_utc"].strftime("%H:%M") for d in det if d["satelite"] == sat)
        assert pasadas[sat] == {"min": horas[0], "max": horas[-1], "n": len(horas)}


def test_incertidumbre_anios_y_porcentaje_dias(cliente):
    cuerpo = cliente.get("/calendario?bbox=-75.33,2.4,-75.2,2.7&desde=2026-11-10&hasta=2026-11-12").json()
    inc = cuerpo["incertidumbre"]
    assert inc["anios_con_dato"] == [2026]
    con_dato = sum(1 for d in cuerpo["dias"] if d["n_detecciones"] > 0)
    assert inc["porcentaje_dias_con_dato"] == round(100 * con_dato / 3, 1)


def test_detecciones_traen_semilado_nominal(cliente):
    cuerpo = cliente.get(f"/detecciones?bbox={BBOX}").json()
    assert cuerpo["detecciones"]
    for d in cuerpo["detecciones"]:
        assert d["semilado_nominal_m"] == {"MODIS": 500.0, "VIIRS": 187.5}[d["sensor"]]
        assert {"satelite", "fecha_hora_utc", "calidad", "confianza_clase", "lat", "lon"} <= set(d)
    assert "incertidumbre" in cuerpo


def test_detecciones_filtradas_por_fecha(cliente):
    cuerpo = cliente.get(f"/detecciones?bbox={BBOX}&desde=2026-11-11&hasta=2026-11-11").json()
    assert cuerpo["detecciones"]
    assert {d["fecha_hora_utc"][:10] for d in cuerpo["detecciones"]} == {"2026-11-11"}


# ---------------------------------------------------------------- H3-03 (D-02)
def test_calidad_mixta_es_preliminar(cliente):
    cuerpo = cliente.get(f"/calendario?bbox={BBOX}").json()
    assert cuerpo["calidad"] == "mixta"
    assert cuerpo["preliminar"] is True
    for d in cuerpo["dias"]:
        if d["n_detecciones"]:
            assert d["preliminar"] == ("NRT" in d["calidad"] or d["calidad"] == "mixta")


def test_solo_estandar_no_es_preliminar(salida, tmp_path):
    # Subconjunto con solo registros estándar: se reescribe celda_dia y detecciones.
    import pyarrow.compute as pc

    for nombre in ("detecciones", "deduplicados", "cuarentena"):
        shutil.copy(salida / f"{nombre}.parquet", tmp_path)
    cd = pq.read_table(salida / "celda_dia.parquet")
    pq.write_table(cd.filter(pc.equal(cd["calidades"], "estandar")), tmp_path / "celda_dia.parquet")
    det = pq.read_table(salida / "detecciones.parquet")
    pq.write_table(det.filter(pc.equal(det["calidad"], "estandar")), tmp_path / "detecciones.parquet")
    cuerpo = TestClient(create_app(tmp_path)).get(f"/calendario?bbox={BBOX}").json()
    assert cuerpo["calidad"] == "estandar"
    assert cuerpo["preliminar"] is False


# ---------------------------------------------------------------- H3-05 (D-08)
def test_base_insuficiente_con_pocos_anios(cliente):
    base = cliente.get(f"/calendario?bbox={BBOX}").json()["linea_base"]
    assert base["estado"] == "base insuficiente"
    assert base["anios_disponibles"] == 1
    assert base["anios_minimos"] == 5
    assert base["percentil"] == 95


def test_base_suficiente_con_minimo_bajo(salida):
    base = TestClient(create_app(salida, anios_minimos=1)).get(f"/calendario?bbox={BBOX}").json()["linea_base"]
    assert base["estado"] == "suficiente"
    assert base["anios_minimos"] == 1


def test_minimo_por_defecto_es_cinco_anios_acordado(salida):
    # ADR 0005: valor acordado con el equipo el 2026-11-13 (ya no es provisional).
    base = TestClient(create_app(salida)).get(f"/calendario?bbox={BBOX}").json()["linea_base"]
    assert base["anios_minimos"] == 5
    assert "PROVISIONAL" not in base["nota"]
    assert "ADR 0005" in base["nota"]


# ---------------------------------------------------------------- H3-07
@pytest.mark.parametrize("consulta", [
    "bbox=1,2,3", "bbox=a,b,c,d", "bbox=-75,2,-76,3", "bbox=-76,3,-75,2",
    "bbox=-200,2,-75,3", "bbox=-76,-95,-75,3",
    f"bbox={BBOX}&desde=2026-11-12&hasta=2026-11-10", f"bbox={BBOX}&desde=no-fecha",
])
def test_parametros_invalidos_responden_422(cliente, consulta):
    for ruta in ("/calendario", "/detecciones", "/calendario.csv"):
        r = cliente.get(f"{ruta}?{consulta}")
        assert r.status_code == 422, (ruta, consulta)


def test_bbox_obligatorio(cliente):
    assert cliente.get("/calendario").status_code == 422


# ---------------------------------------------------------------- H4-03
def test_base_insuficiente_deja_nulos_los_campos_de_r5(cliente):
    cuerpo = cliente.get(f"/calendario?bbox={BBOX}").json()
    assert cuerpo["linea_base"]["estado"] == "base insuficiente"
    assert all(d["umbral"] is None and d["inusual"] is None for d in cuerpo["dias"])
    assert cuerpo["periodos_inusuales"] is None
    assert cuerpo["meses_pico"] is None


def test_linea_base_declara_parametros_de_r5(cliente):
    base = cliente.get(f"/calendario?bbox={BBOX}").json()["linea_base"]
    assert base["ventana_dias"] == 7
    assert base["metrica"] == "celdas activas equivalentes"  # H8-02 (ADR 0011)


def test_csv_exporta_umbral_e_inusual(cliente):
    texto = cliente.get(f"/calendario.csv?bbox={BBOX}").text
    cabecera = next(ln for ln in texto.splitlines() if not ln.startswith("#"))
    assert cabecera.endswith(",umbral,inusual")


# ---------------------------------------------------------------- H4-05 (interfaz)
def test_raiz_redirige_a_la_interfaz(cliente):
    r = cliente.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/ui/"


def test_interfaz_servida_sin_recursos_externos(cliente):
    html = cliente.get("/ui/").text
    assert "Harmonized Heat Neiva" in html
    # Funciona sin internet: ningún script ni hoja de estilos remotos (las teselas son opcionales).
    assert not re.search(r'<script[^>]+src="https?://', html)
    assert not re.search(r'<link[^>]+href="https?://', html)
    for recurso in ("vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "app.js", "styles.css"):
        assert recurso in html
        assert cliente.get(f"/ui/{recurso}").status_code == 200


def test_interfaz_muestra_la_cita_en_el_mapa(cliente):
    # Mapa: forma corta «NASA FIRMS» con enlace (FAQ de FIRMS) en la atribución.
    # Pie: la cita completa y el aviso tal como los entrega la API.
    js = cliente.get("/ui/app.js").text
    assert "addAttribution" in js and "NASA FIRMS" in js and "LANCE" in js
    assert '$("cita").textContent = c.cita' in js and '$("aviso").textContent = c.aviso' in js


def test_rango_se_recorta_a_la_cobertura_de_datos(cliente):
    # Días fuera de la cobertura no son «días sin focos»: no se cuentan ni se rellenan.
    cuerpo = cliente.get(f"/calendario?bbox={BBOX}&desde=2026-11-01&hasta=2026-12-31").json()
    assert cuerpo["desde"] == "2026-11-10" and cuerpo["hasta"] == "2026-11-12"
    assert cuerpo["desde_solicitado"] == "2026-11-01" and cuerpo["hasta_solicitado"] == "2026-12-31"
    assert len(cuerpo["dias"]) == 3
    assert cuerpo["incertidumbre"]["porcentaje_dias_con_dato"] == 100.0


def test_rango_sin_solapamiento_con_la_cobertura(cliente):
    cuerpo = cliente.get(f"/calendario?bbox={BBOX}&desde=2020-01-01&hasta=2020-12-31").json()
    assert cuerpo["dias"] == []
    assert cuerpo["incertidumbre"]["porcentaje_dias_con_dato"] == 0.0


# ---------------------------------------------------------------- H6-01 (origen de los datos)
def _copia_con_sintetico(salida: Path, destino: Path, valores: list[bool]) -> Path:
    """Copia la salida y reescribe la columna `sintetico` conservando esquema y metadatos."""
    import pyarrow as pa

    shutil.copytree(salida, destino)
    tabla = pq.read_table(destino / "detecciones.parquet")
    assert len(valores) == tabla.num_rows
    pos = tabla.schema.get_field_index("sintetico")
    tabla = tabla.set_column(pos, tabla.schema.field(pos), pa.array(valores, type=tabla.schema.field(pos).type))
    pq.write_table(tabla.replace_schema_metadata(tabla.schema.metadata), destino / "detecciones.parquet")
    return destino


def test_origen_datos_sintetico_en_calendario_y_detecciones(cliente, salida):
    assert all(f["sintetico"] is True for f in _tabla(salida, "detecciones"))
    assert cliente.get(f"/calendario?bbox={BBOX}").json()["origen_datos"] == "sintetico"
    assert cliente.get(f"/detecciones?bbox={BBOX}").json()["origen_datos"] == "sintetico"


def test_origen_datos_sintetico_tambien_en_area_sin_focos(cliente):
    c = cliente.get("/calendario?bbox=10,10,11,11&desde=2026-11-10&hasta=2026-11-12").json()
    d = cliente.get("/detecciones?bbox=10,10,11,11&desde=2026-11-10&hasta=2026-11-12").json()
    assert c["origen_datos"] == "sintetico" and d["origen_datos"] == "sintetico"
    assert d["detecciones"] == []


def test_origen_datos_real_si_ninguna_fila_es_sintetica(salida, tmp_path):
    n = pq.read_table(salida / "detecciones.parquet").num_rows
    copia = _copia_con_sintetico(salida, tmp_path / "real", [False] * n)
    cl = TestClient(create_app(copia))
    assert cl.get(f"/calendario?bbox={BBOX}").json()["origen_datos"] == "real"
    assert cl.get(f"/detecciones?bbox={BBOX}").json()["origen_datos"] == "real"


def test_origen_datos_mixto_si_hay_filas_de_ambos_tipos(salida, tmp_path):
    n = pq.read_table(salida / "detecciones.parquet").num_rows
    assert n >= 2
    copia = _copia_con_sintetico(salida, tmp_path / "mixto", [False] + [True] * (n - 1))
    cl = TestClient(create_app(copia))
    assert cl.get(f"/calendario?bbox={BBOX}").json()["origen_datos"] == "mixto"
    assert cl.get(f"/detecciones?bbox={BBOX}").json()["origen_datos"] == "mixto"


def test_csv_lleva_la_linea_origen_datos(cliente):
    lineas = cliente.get(f"/calendario.csv?bbox={BBOX}").text.splitlines()
    assert "# origen_datos: sintetico" in lineas


def test_interfaz_se_revalida_tras_cada_actualizacion(cliente):
    # Sin esto, el navegador puede seguir usando un app.js viejo después de actualizar.
    for ruta in ("/ui/", "/ui/app.js", "/ui/styles.css"):
        assert "no-cache" in cliente.get(ruta).headers.get("cache-control", ""), ruta


# ---------------------------------------------------------------- R-40: filtro por polígono
def test_area_huila_filtra_por_poligono_y_no_suma_mas_que_el_recuadro(cliente):
    por_recuadro = cliente.get(f"/calendario?bbox={BBOX}").json()
    por_area = cliente.get("/calendario?area=huila").json()
    assert por_area["area"]["filtro"] == "poligono" and por_area["area"]["nombre"] == "Huila"
    assert sum(d["n_brutas"] for d in por_area["dias"]) <= sum(d["n_brutas"] for d in por_recuadro["dias"])
    assert por_recuadro["area"]["filtro"] == "recuadro"


def test_area_municipio_y_area_desconocida(cliente):
    import json as _json

    geo = _json.loads((RAIZ / "src/ui/static/datos/huila_municipios.geojson").read_text(encoding="utf-8"))
    neiva = next(f for f in geo["features"] if f["properties"]["shapeName"] == "Neiva")
    r = cliente.get(f"/calendario?area=mun:{neiva['properties']['shapeID']}")
    assert r.status_code == 200 and r.json()["area"]["nombre"] == "Neiva"
    assert cliente.get("/calendario?area=mun:no-existe").status_code == 422
    assert cliente.get("/calendario").status_code == 422  # sin bbox ni area


def test_detecciones_por_area_estan_en_celdas_del_poligono(cliente):
    # Se filtra por celda de ~1 km (centroide en el polígono), igual que el calendario.
    from api.area import contiene, resolver_area
    from harmonize.config import RulesConfig
    from harmonize.rules import cell_centroid

    geom = resolver_area("huila")
    cuerpo = cliente.get("/detecciones?area=huila").json()
    assert cuerpo["detecciones"]
    cfg = RulesConfig()
    for d in cuerpo["detecciones"]:
        f_txt, c_txt = d["cell_id"].split("_")  # formato f<fila>_c<col>
        fila, col = int(f_txt[1:]), int(c_txt[1:])
        lat, lon = cell_centroid(fila, col, cfg)
        assert contiene(geom["geometrias"], lon, lat)


def test_calendario_y_mapa_cuentan_lo_mismo_con_area(cliente):
    cal = cliente.get("/calendario?area=huila").json()
    det = cliente.get("/detecciones?area=huila&limite=50000").json()
    assert sum(d["n_detecciones"] for d in cal["dias"]) == len(det["detecciones"])


def test_punto_fuera_del_poligono_pero_dentro_del_recuadro_se_excluye():
    from api.area import contiene, resolver_area

    a = resolver_area("huila")
    w, s, e, n = a["bbox"]
    # Esquina del recuadro: dentro del rectángulo, fuera del departamento.
    assert not contiene(a["geometrias"], w + 0.001, s + 0.001)
    # Centro de Neiva: dentro.
    assert contiene(a["geometrias"], -75.28, 2.93)


def test_csv_respeta_el_area(cliente):
    texto = cliente.get("/calendario.csv?area=huila").text
    assert "# area: Huila (poligono)" in texto


# ---------------------------------------------------------------- H8: brechas del reto
def test_calendario_trae_metrica_armonizada(cliente):
    c = cliente.get(f"/calendario?bbox={BBOX}").json()
    a = c["armonizacion"]
    assert a["metrica"] == "armonizada" and a["version"] == "celdas-eq-1.0.0"
    assert {"k_m", "k_n20", "anios_superposicion_modis"} <= set(a["factores"])
    for d in c["dias"]:
        assert {"celdas_eq", "metodo", "valor"} <= set(d)
        assert d["valor"] == d["celdas_eq"]
    assert c["linea_base"]["metrica"] == "celdas activas equivalentes"


def test_metrica_n_brutas_sigue_disponible(cliente):
    c = cliente.get(f"/calendario?bbox={BBOX}&metrica=n_brutas").json()
    assert all(d["valor"] == d["n_brutas"] for d in c["dias"])
    assert cliente.get(f"/calendario?bbox={BBOX}&metrica=otra").status_code == 422


def test_detecciones_csv_lista_los_focos_con_cita(cliente):
    cita, aviso = _cita_literal()
    r = cliente.get(f"/detecciones.csv?bbox={BBOX}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lineas = r.text.splitlines()
    comentarios = [ln[2:] for ln in lineas if ln.startswith("# ")]
    assert cita in comentarios and aviso in comentarios
    filas = list(csv.DictReader(io.StringIO("\n".join(ln for ln in lineas if not ln.startswith("#")))))
    n = len(cliente.get(f"/detecciones?bbox={BBOX}&limite=50000").json()["detecciones"])
    assert len(filas) == n > 0
    assert {"fecha_hora_utc", "lat", "lon", "sensor", "satelite", "confianza_clase", "frp", "calidad",
            "cell_id", "semilado_nominal_m"} <= set(filas[0])


def test_resumen_plurianual(cliente):
    r = cliente.get(f"/resumen?bbox={BBOX}").json()
    assert {"anios", "matriz", "mediana_mensual", "mes_reciente", "armonizacion", "cita"} <= set(r)
    assert r["matriz"] and all({"anio", "mes", "valor", "n_brutas", "completo"} <= set(c) for c in r["matriz"])
    assert sum(x["valor"] for x in r["anios"]) == pytest.approx(sum(c["valor"] for c in r["matriz"]))
