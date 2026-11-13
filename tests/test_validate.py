"""Pruebas de validación por registro (D-03)."""

from datetime import UTC, datetime

import pytest

from ingest import firms_schema as fs
from ingest.validate import validate_row

DESCARGA = datetime(2026, 11, 13, 0, 0, 0, tzinfo=UTC)

MODIS = {
    "latitude": "2.93", "longitude": "-75.28", "brightness": "330.5",
    "scan": "1.0", "track": "1.0", "acq_date": "2026-11-10",
    "acq_time": "1705", "satellite": "Terra", "instrument": "MODIS",
    "confidence": "85", "version": "6.1NRT", "bright_t31": "295.0",
    "frp": "12.5", "daynight": "D",
}
VIIRS = {
    "latitude": "2.93", "longitude": "-75.28", "bright_ti4": "340.1",
    "scan": "0.4", "track": "0.4", "acq_date": "2026-11-10",
    "acq_time": "1830", "satellite": "N20", "instrument": "VIIRS",
    "confidence": "n", "version": "2.0NRT", "bright_ti5": "300.0",
    "frp": "3.2", "daynight": "D",
}


def validar(raw, fuente="MODIS_NRT", sensor="MODIS", calidad="NRT", descarga=DESCARGA):
    return validate_row(
        raw, fuente=fuente, sensor=sensor, calidad=calidad, fecha_descarga=descarga
    )


def validar_viirs(raw, **kw):
    kw.setdefault("fuente", "VIIRS_NOAA20_NRT")
    return validar(raw, sensor="VIIRS", **kw)


def con(base, **cambios):
    return {**base, **cambios}


def test_fila_valida_modis():
    out = validar(MODIS)
    assert out.motivo is None
    c = out.campos
    assert c["lat"] == 2.93 and c["lon"] == -75.28
    assert c["fecha_hora_utc"] == datetime(2026, 11, 10, 17, 5, tzinfo=UTC)
    assert c["fecha_hora_utc"].tzinfo is UTC
    assert c["brillo"] == 330.5
    assert c["frp"] == 12.5
    assert c["satelite"] == "Terra"
    assert c["satelite_codigo"] == "Terra"
    assert c["confianza_raw"] == "85"


def test_fila_valida_viirs_usa_bright_ti4():
    out = validar_viirs(VIIRS)
    assert out.motivo is None
    assert out.campos["brillo"] == 340.1
    assert out.campos["satelite"] == "NOAA-20"


def test_frp_vacio_es_none():
    out = validar(con(MODIS, frp=""))
    assert out.motivo is None
    assert out.campos["frp"] is None


@pytest.mark.parametrize("lat", ["95", "-90.0001", "nan", "inf", "-inf"])
def test_latitud_fuera_de_rango(lat):
    assert validar(con(MODIS, latitude=lat)).motivo == "latitud fuera de rango"


@pytest.mark.parametrize("lon", ["181", "-180.5", "nan", "inf"])
def test_longitud_fuera_de_rango(lon):
    assert validar(con(MODIS, longitude=lon)).motivo == "longitud fuera de rango"


@pytest.mark.parametrize("campo,valor", [
    ("latitude", "abc"), ("latitude", ""), ("longitude", "x1"), ("longitude", ""),
])
def test_coordenada_no_numerica(campo, valor):
    assert validar(con(MODIS, **{campo: valor})).motivo == "coordenada no numérica"


@pytest.mark.parametrize("cambios", [
    {"acq_date": "2026-13-45"},
    {"acq_date": "10/11/2026"},
    {"acq_date": ""},
    {"acq_time": "2460"},
    {"acq_time": "1299"},
    {"acq_time": "abc"},
    {"acq_time": ""},
    {"acq_time": "12345"},
])
def test_fecha_hora_invalida(cambios):
    assert validar(con(MODIS, **cambios)).motivo == "fecha/hora inválida"


def test_fecha_posterior_a_la_descarga():
    out = validar(con(MODIS, acq_date="2026-11-13", acq_time="0100"))
    assert out.motivo == "fecha posterior a la descarga"


def test_fecha_igual_a_la_descarga_es_valida():
    out = validar(con(MODIS, acq_date="2026-11-13", acq_time="0"))
    assert out.motivo is None


@pytest.mark.parametrize("conf", ["101", "-1", "alta", "", "h", "50.5"])
def test_confianza_modis_fuera_de_dominio(conf):
    assert validar(con(MODIS, confidence=conf)).motivo == "confianza fuera de dominio"


@pytest.mark.parametrize("conf", ["0", "50", "100"])
def test_confianza_modis_valida(conf):
    assert validar(con(MODIS, confidence=conf)).motivo is None


@pytest.mark.parametrize("conf", ["x", "", "50", "H", "high"])
def test_confianza_viirs_fuera_de_dominio(conf):
    out = validar_viirs(con(VIIRS, confidence=conf))
    assert out.motivo == "confianza fuera de dominio"


@pytest.mark.parametrize("conf", list(fs.CONFIANZA_VIIRS_VALORES))
def test_confianza_viirs_valida(conf):
    assert validar_viirs(con(VIIRS, confidence=conf)).motivo is None


def test_satelite_no_reconocido():
    assert validar(con(MODIS, satellite="ZZ")).motivo == "satélite no reconocido"


def test_satelite_inconsistente_por_sensor():
    # Código de VIIRS en un archivo MODIS.
    out = validar(con(MODIS, satellite="N20"))
    assert out.motivo == "satélite inconsistente con la fuente"


def test_satelite_inconsistente_por_fuente():
    # "N" (Suomi NPP) dentro de la fuente NOAA-20.
    out = validar_viirs(con(VIIRS, satellite="N"))
    assert out.motivo == "satélite inconsistente con la fuente"


def test_satelite_no_confirmado_se_acepta_con_marca():
    assert fs.SATELITES["Terra"]["confirmado"] is False
    out = validar(MODIS)
    assert out.motivo is None
    assert out.campos["satelite_confirmado"] is False


def test_satelite_confirmado_lleva_marca_true(monkeypatch):
    monkeypatch.setitem(fs.SATELITES, "Terra", {**fs.SATELITES["Terra"], "confirmado": True})
    assert validar(MODIS).campos["satelite_confirmado"] is True


def test_calidad_vs_version_sin_confirmar_solo_advierte():
    assert fs.PATRONES_VERSION_ESTADO == "por confirmar"
    out = validar(con(MODIS, version="6.1"))  # versión estándar en fuente NRT
    assert out.motivo is None
    assert out.campos is not None
    assert any("versión" in a for a in out.advertencias)


def test_calidad_vs_version_confirmada_rechaza(monkeypatch):
    monkeypatch.setattr(fs, "PATRONES_VERSION_ESTADO", "confirmado")
    out = validar(con(MODIS, version="6.1"))
    assert out.motivo == "calidad inconsistente con la versión"
    assert out.campos is None
    out = validar(MODIS, fuente="MODIS_SP", calidad="estandar")  # 6.1NRT en estándar
    assert out.motivo == "calidad inconsistente con la versión"


def test_calidad_vs_version_confirmada_acepta_coherente(monkeypatch):
    monkeypatch.setattr(fs, "PATRONES_VERSION_ESTADO", "confirmado")
    assert validar(MODIS).motivo is None
    assert validar(con(MODIS, version="6.1"), fuente="MODIS_SP", calidad="estandar").motivo is None
    assert validar(MODIS).advertencias == []
