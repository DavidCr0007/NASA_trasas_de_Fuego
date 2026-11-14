"""Pruebas del lector FIRMS con procedencia (D-01, D-02, D-04)."""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest import firms_schema as fs
from ingest.manifest import ManifestError, append_entry, build_entry, sha256_file
from ingest.reader import (
    InvariantError,
    IngestResult,
    check_invariant,
    read_file,
    read_manifest_dir,
)

CAMPOS = {
    "fuente": "MODIS_NRT",
    "sensor": "MODIS",
    "calidad": "NRT",
    "coleccion": "6.1",
    "fecha_descarga": "2026-11-13T00:00:00Z",
    "url_sin_clave": None,
    "bbox": list(fs.HUILA_BBOX),
    "fecha_inicio": "2026-11-10",
    "fecha_fin": "2026-11-12",
    "sintetico": True,
}
CAB_MODIS = list(fs.COLUMNAS_REQUERIDAS[("MODIS", "api_nrt")])
CAB_VIIRS = list(fs.COLUMNAS_REQUERIDAS[("VIIRS", "api_nrt")])

MODIS = {
    "latitude": "2.93", "longitude": "-75.28", "brightness": "330.5",
    "scan": "1.0", "track": "1.0", "acq_date": "2026-11-10",
    "acq_time": "1705", "satellite": "T",
    "confidence": "85", "version": "6.1NRT", "bright_t31": "295.0",
    "frp": "12.5", "daynight": "D",
}
VIIRS = {
    "latitude": "2.93", "longitude": "-75.28", "bright_ti4": "340.1",
    "scan": "0.4", "track": "0.4", "acq_date": "2026-11-10",
    "acq_time": "1830", "satellite": "N20",
    "confidence": "nominal", "version": "2.0NRT", "bright_ti5": "300.0",
    "frp": "3.2", "daynight": "D",
}


def escribir(base: Path, nombre: str, cabecera, filas) -> Path:
    ruta = base / nombre
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cabecera)
        for fila in filas:
            w.writerow(fila)
    return ruta


def como_fila(cabecera, d):
    return [d[c] for c in cabecera]


def preparar(base: Path, nombre="a.csv", filas=None, cabecera=CAB_MODIS, **campos):
    filas = filas if filas is not None else [como_fila(CAB_MODIS, MODIS)]
    ruta = escribir(base, nombre, cabecera, filas)
    entrada = build_entry(ruta, base, **{**CAMPOS, **campos})
    return ruta, entrada


def test_hash_alterado_aborta(tmp_path):
    ruta, entrada = preparar(tmp_path)
    with ruta.open("a", encoding="utf-8") as f:
        f.write("0,0\n")
    with pytest.raises(ManifestError):
        read_file(ruta, entrada)


def test_archivo_fuera_del_manifiesto_aborta(tmp_path):
    ruta, _ = preparar(tmp_path)
    with pytest.raises(ManifestError):
        read_file(ruta, None)


def test_manifest_dir_con_hash_alterado_aborta(tmp_path):
    ruta, entrada = preparar(tmp_path)
    append_entry(tmp_path / "manifest.jsonl", entrada)
    ruta.write_text(ruta.read_text(encoding="utf-8") + "\n#\n", encoding="utf-8")
    with pytest.raises(ManifestError):
        read_manifest_dir(tmp_path)


def test_contrato_exacto_del_registro(tmp_path):
    ruta, entrada = preparar(tmp_path)
    res = read_file(ruta, entrada)
    assert len(res.registros) == 1
    assert set(res.registros[0]) == {
        "record_id", "fuente", "sensor", "satelite_codigo", "satelite",
        "satelite_confirmado", "coleccion", "version", "calidad", "lat", "lon",
        "fecha_hora_utc", "daynight", "confianza_raw", "frp", "brillo",
        "archivo_origen", "sha256_origen", "fecha_descarga", "fila", "sintetico",
    }


def test_procedencia_completa(tmp_path):
    ruta, entrada = preparar(tmp_path, nombre="sub_a.csv")
    r = read_file(ruta, entrada).registros[0]
    sha = sha256_file(ruta)
    assert r["record_id"] == f"{sha[:16]}:1"
    assert r["fuente"] == "MODIS_NRT"
    assert r["sensor"] == "MODIS"
    assert r["satelite_codigo"] == "T"
    assert r["satelite"] == "Terra"
    assert r["satelite_confirmado"] is True
    assert r["coleccion"] == "6.1"
    assert r["version"] == "6.1NRT"
    assert r["calidad"] == "NRT"
    assert (r["lat"], r["lon"]) == (2.93, -75.28)
    assert r["daynight"] == "D"
    assert r["confianza_raw"] == "85"
    assert r["frp"] == 12.5
    assert r["brillo"] == 330.5
    assert r["archivo_origen"] == "sub_a.csv"
    assert r["sha256_origen"] == sha
    assert r["fila"] == 1
    assert r["sintetico"] is True


def test_fecha_descarga_viene_del_manifiesto(tmp_path):
    ruta, entrada = preparar(tmp_path, fecha_descarga="2026-11-12T08:30:15Z")
    r = read_file(ruta, entrada).registros[0]
    assert r["fecha_descarga"] == datetime(2026, 11, 12, 8, 30, 15, tzinfo=UTC)
    assert r["fecha_descarga"].tzinfo is UTC


def test_numero_de_fila_empieza_en_1(tmp_path):
    filas = [como_fila(CAB_MODIS, {**MODIS, "acq_time": t}) for t in ("0100", "0200", "0300")]
    ruta, entrada = preparar(tmp_path, filas=filas)
    regs = read_file(ruta, entrada).registros
    assert [r["fila"] for r in regs] == [1, 2, 3]
    assert len({r["record_id"] for r in regs}) == 3


@pytest.mark.parametrize("acq_time,hora,minuto", [
    ("1705", 17, 5), ("0035", 0, 35), ("35", 0, 35), ("905", 9, 5),
    ("0", 0, 0), ("5", 0, 5), ("2359", 23, 59),
])
def test_acq_time_con_y_sin_ceros(tmp_path, acq_time, hora, minuto):
    fila = como_fila(CAB_MODIS, {**MODIS, "acq_time": acq_time})
    ruta, entrada = preparar(tmp_path, filas=[fila])
    r = read_file(ruta, entrada).registros[0]
    assert r["fecha_hora_utc"] == datetime(2026, 11, 10, hora, minuto, tzinfo=UTC)
    assert r["fecha_hora_utc"].utcoffset().total_seconds() == 0


def test_viirs_lee_bright_ti4(tmp_path):
    ruta, entrada = preparar(
        tmp_path, filas=[como_fila(CAB_VIIRS, VIIRS)], cabecera=CAB_VIIRS,
        fuente="VIIRS_NOAA20_NRT", sensor="VIIRS",
    )
    res = read_file(ruta, entrada)
    assert res.cuarentena == []
    assert res.registros[0]["brillo"] == 340.1
    assert res.registros[0]["satelite"] == "NOAA-20"


def test_esquema_invalido_manda_todas_las_filas_a_cuarentena(tmp_path):
    cab = [c for c in CAB_MODIS if c not in ("confidence", "frp")]
    filas = [[MODIS[c] for c in cab] for _ in range(3)]
    ruta, entrada = preparar(tmp_path, filas=filas, cabecera=cab)
    res = read_file(ruta, entrada)
    assert res.registros == []
    assert res.n_input == 3
    assert len(res.cuarentena) == 3
    assert {q["motivo"] for q in res.cuarentena} == {
        "esquema inválido: faltan columnas [confidence, frp]"
    }
    check_invariant(IngestResult(res.registros, res.cuarentena, 3, {"a.csv": 3}))


def test_columnas_extra_se_toleran_y_se_registran(tmp_path):
    cab = CAB_MODIS + ["extra_col"]
    ruta, entrada = preparar(tmp_path, filas=[como_fila(CAB_MODIS, MODIS) + ["z"]], cabecera=cab)
    res = read_file(ruta, entrada)
    assert len(res.registros) == 1 and res.cuarentena == []
    assert res.columnas_extra == ["extra_col"]


def test_fila_malformada(tmp_path):
    buena = como_fila(CAB_MODIS, MODIS)
    ruta, entrada = preparar(tmp_path, filas=[buena, buena[:-3], buena + ["x"], buena])
    res = read_file(ruta, entrada)
    assert [r["fila"] for r in res.registros] == [1, 4]
    assert [(q["fila"], q["motivo"]) for q in res.cuarentena] == [
        (2, "fila malformada"), (3, "fila malformada"),
    ]
    assert res.n_input == 4


def test_contrato_de_cuarentena(tmp_path):
    mala = {**MODIS, "latitude": "95", "frp": "ñandú"}
    ruta, entrada = preparar(tmp_path, filas=[como_fila(CAB_MODIS, mala)])
    res = read_file(ruta, entrada)
    assert res.registros == []
    (q,) = res.cuarentena
    assert set(q) == {
        "archivo_origen", "sha256_origen", "fila", "motivo", "datos_crudos", "fecha_descarga",
    }
    assert q["archivo_origen"] == "a.csv"
    assert q["sha256_origen"] == sha256_file(ruta)
    assert q["fila"] == 1
    assert q["motivo"] == "latitud fuera de rango"
    assert q["datos_crudos"] == json.dumps(mala, sort_keys=True, ensure_ascii=False)
    assert "ñandú" in q["datos_crudos"]
    assert q["fecha_descarga"] == datetime(2026, 11, 13, tzinfo=UTC)


def test_invariante_se_cumple_y_se_viola(tmp_path):
    filas = [
        como_fila(CAB_MODIS, MODIS),
        como_fila(CAB_MODIS, {**MODIS, "latitude": "95"}),
        como_fila(CAB_MODIS, {**MODIS, "confidence": "999"}),
    ]
    ruta, entrada = preparar(tmp_path, filas=filas)
    append_entry(tmp_path / "manifest.jsonl", entrada)
    res = read_manifest_dir(tmp_path)
    assert res.n_input == 3
    assert len(res.registros) == 1 and len(res.cuarentena) == 2
    assert res.n_por_archivo == {"a.csv": 3}
    check_invariant(res)
    check_invariant(IngestResult(res.registros, res.cuarentena, 4, {}), n_dedup=1)
    with pytest.raises(InvariantError):
        check_invariant(res, n_dedup=1)
    with pytest.raises(InvariantError):
        check_invariant(IngestResult(res.registros[:0], res.cuarentena, 3, {}))


def test_resultado_independiente_del_orden_del_manifiesto(tmp_path):
    ruta_b, ent_b = preparar(
        tmp_path, nombre="b.csv", fuente="MODIS_SP", calidad="estandar",
        filas=[como_fila(CAB_MODIS, {**MODIS, "version": "6.1"})],
    )
    ruta_a, ent_a = preparar(
        tmp_path, nombre="a.csv",
        filas=[como_fila(CAB_MODIS, {**MODIS, "latitude": "99"}), como_fila(CAB_MODIS, MODIS)],
    )
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    for d, orden in ((d1, (ent_b, ent_a)), (d2, (ent_a, ent_b))):
        d.mkdir()
        for e in orden:
            (d / e["archivo"]).write_bytes((tmp_path / e["archivo"]).read_bytes())
            append_entry(d / "manifest.jsonl", e)
    r1, r2 = read_manifest_dir(d1), read_manifest_dir(d2)
    assert r1 == r2
    assert [r["archivo_origen"] for r in r1.registros] == ["a.csv", "b.csv"]
    assert list(r1.n_por_archivo) == ["a.csv", "b.csv"]


def test_manifest_dir_vacio_aborta(tmp_path):
    with pytest.raises(ManifestError):
        read_manifest_dir(tmp_path)


def test_recortes_reales_sin_cuarentena_por_esquema(tmp_path):
    carpeta = Path(__file__).parent / "fixtures" / "firms_real"
    recortes = sorted(carpeta.glob("*.csv"))
    if not recortes:
        pytest.skip("fixture real no disponible")
    for recorte in recortes:
        copia = tmp_path / recorte.name
        copia.write_bytes(recorte.read_bytes())
        with copia.open(encoding="utf-8-sig", newline="") as f:
            cabecera = next(csv.reader(f))
        sensor = "VIIRS" if "bright_ti4" in cabecera else "MODIS"
        # Archivo anual por país (estándar, variante "pais") frente a archivo de 24 h (NRT).
        es_pais = "_Colombia_" in recorte.name
        if es_pais:
            fuente = {"modis": "PAIS_MODIS_SP", "viirs-snpp": "PAIS_VIIRS_SNPP_SP",
                      "viirs-jpss1": "PAIS_VIIRS_NOAA20_SP"}[recorte.name.split("_")[0]]
        else:
            fuente = f"FIRMS_24H_{recorte.stem}"
        entrada = build_entry(
            copia, tmp_path, fuente=fuente, sensor=sensor,
            calidad="estandar" if es_pais else "NRT", coleccion="por confirmar",
            variante="pais" if es_pais else "24h",
            fecha_descarga="2099-01-01T00:00:00Z", url_sin_clave=None,
            bbox=None, fecha_inicio=None, fecha_fin=None, sintetico=False,
        )
        res = read_file(copia, entrada)
        por_esquema = [q for q in res.cuarentena if q["motivo"].startswith("esquema inválido")]
        assert por_esquema == [], recorte.name
        # Los recortes son datos reales de FIRMS (24 h, 2026-11-13): ninguna fila
        # debe ir a cuarentena y los satélites deben resolverse a nombres oficiales.
        assert res.cuarentena == [], (recorte.name, res.cuarentena[:1])
        assert res.n_input == 25, recorte.name
        esperados = {"MODIS": {"Terra", "Aqua"}, "VIIRS": {"NOAA-20", "NOAA-21", "Suomi NPP"}}[sensor]
        assert {r["satelite"] for r in res.registros} <= esperados, recorte.name
        assert all(r["satelite_confirmado"] for r in res.registros), recorte.name
        check_invariant(IngestResult(res.registros, res.cuarentena, res.n_input, {}))


def test_codigos_refutados_no_se_aceptan():
    # "1"/"2" (prototipo) no aparecen en ninguna fuente: se rechazan.
    for codigo in ("1", "2"):
        assert codigo not in fs.SATELITES, codigo
    for codigo in ("N", "N20", "N21", "T", "A"):
        assert fs.SATELITES[codigo]["confirmado"] is True, codigo
    # "Terra"/"Aqua" solo aparecen en el archivo anual por país [K].
    for codigo in ("Terra", "Aqua"):
        assert fs.SATELITES[codigo]["confirmado"] is True and "K" in fs.SATELITES[codigo]["fuente"]


def test_variante_pais_declara_fuentes_estandar():
    for fuente in ("PAIS_MODIS_SP", "PAIS_VIIRS_SNPP_SP", "PAIS_VIIRS_NOAA20_SP"):
        meta = fs.FUENTES_API[fuente]
        assert meta["calidad"] == "estandar" and meta["variante"] == "pais"
    assert ("MODIS", "pais") in fs.COLUMNAS_REQUERIDAS and ("VIIRS", "pais") in fs.COLUMNAS_REQUERIDAS
