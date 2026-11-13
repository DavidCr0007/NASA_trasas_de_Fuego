from datetime import datetime
import pytest
from harmonize import harmonize, cell_1km, classify_confidence, validate, RULES_VERSION

NEIVA = (2.95, -75.29)

def row(sensor="VIIRS", sat="N", lat=2.95, lon=-75.29, t="2026-08-01T18:00:00", conf="h", **kw):
    d = {"sensor": sensor, "satellite": sat, "lat": lat, "lon": lon, "when_utc": t, "confidence": conf}
    d.update(kw)
    return d

# R1 grilla
def test_cell_is_about_1km_apart():
    a = cell_1km(2.95, -75.29)
    b = cell_1km(2.95 + 0.0095, -75.29)   # ~1,05 km al norte
    assert b[0] - a[0] == 1

def test_same_point_same_cell():
    assert cell_1km(*NEIVA) == cell_1km(*NEIVA)

# R2 confianza
@pytest.mark.parametrize("raw,expected", [(10, "baja"), (30, "nominal"), (79.9, "nominal"), (80, "alta"), (100, "alta")])
def test_modis_confidence_thresholds(raw, expected):
    assert classify_confidence("MODIS", raw) == expected

def test_modis_confidence_out_of_domain():
    assert classify_confidence("MODIS", 150) is None
    assert classify_confidence("MODIS", "x") is None

@pytest.mark.parametrize("raw,expected", [("l", "baja"), ("n", "nominal"), ("H", "alta")])
def test_viirs_class_mapping(raw, expected):
    assert classify_confidence("VIIRS", raw) == expected

def test_viirs_unknown_class_quarantined():
    res = harmonize([row(conf="z")])
    assert res.accepted == [] and res.quarantine[0][1] == "confianza fuera de dominio"

# D-03 validación
@pytest.mark.parametrize("bad,motivo", [
    (row(lat=95), "latitud fuera de rango"),
    (row(lon=-200), "longitud fuera de rango"),
    (row(sensor="LANDSAT"), "sensor desconocido"),
    (row(sat="X"), "satélite no reconocido"),
    (row(t="no-es-fecha"), "campo inválido: ValueError"),
    (row(lat=None), "campo inválido: TypeError"),
])
def test_invalid_rows_are_quarantined_with_reason(bad, motivo):
    res = harmonize([bad])
    assert res.accepted == []
    assert res.quarantine == [(bad, motivo)]

# D-04 balance de conteos
def test_counts_balance():
    rows = [row(), row(lat=50), row(sensor="X"), row(t="2026-08-02T10:00:00", sat="T", sensor="MODIS", conf=50)]
    res = harmonize(rows)
    assert res.n_input == len(res.accepted) + len(res.quarantine) + res.n_dedup_removed

# R3 deduplicación
def test_dedup_keeps_viirs_when_same_cell_and_window():
    modis = row(sensor="MODIS", sat="T", t="2026-08-01T17:00:00", conf=90)
    viirs = row(sensor="VIIRS", sat="N", t="2026-08-01T18:00:00", conf="n")
    res = harmonize([modis, viirs])
    assert len(res.accepted) == 1 and res.accepted[0].sensor == "VIIRS"
    assert res.n_dedup_removed == 1

def test_no_dedup_outside_window():
    a = row(sensor="MODIS", sat="T", t="2026-08-01T10:00:00", conf=90)
    b = row(sensor="VIIRS", sat="N", t="2026-08-01T18:00:00", conf="h")
    assert len(harmonize([a, b]).accepted) == 2

def test_no_dedup_different_cell():
    a = row(lat=2.95); b = row(lat=2.95 + 0.05, sensor="MODIS", sat="T", conf=90)
    assert len(harmonize([a, b]).accepted) == 2

# D-06 reproducibilidad: el orden de entrada no cambia el resultado
def test_output_independent_of_input_order():
    rows = [row(sensor="MODIS", sat="T", t="2026-08-01T17:00:00", conf=90), row(), row(lat=40)]
    r1 = harmonize(rows); r2 = harmonize(list(reversed(rows)))
    key = lambda r: [(d.sensor, d.satellite, d.when_utc) for d in r.accepted]
    assert key(r1) == key(r2)

def test_rules_version_declared():
    assert RULES_VERSION.startswith("armonizacion-")