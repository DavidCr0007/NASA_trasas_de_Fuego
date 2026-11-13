"""El generador de muestra sintética es determinista y produce los casos esperados."""

import importlib.util
from collections import Counter
from pathlib import Path

from ingest import firms_schema as fs
from ingest.manifest import load_manifest
from ingest.reader import check_invariant, read_manifest_dir

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("generar_muestra", RAIZ / "tools" / "generar_muestra.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def test_generador_determinista(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    gen.generar(a)
    gen.generar(b)
    for p in sorted(a.iterdir()):
        assert p.read_bytes() == (b / p.name).read_bytes()


def test_muestra_cabecera_filas_bbox_y_manifiesto(tmp_path):
    gen.generar(tmp_path)
    entradas = load_manifest(tmp_path / "manifest.jsonl")
    assert len(entradas) == 5
    for e in entradas.values():
        assert e["sintetico"] is True and e["url_sin_clave"] is None
        assert e["fecha_descarga"] == "2026-11-13T00:00:00Z"
    res = read_manifest_dir(tmp_path)
    for archivo, n in res.n_por_archivo.items():
        assert 20 <= n <= 60, archivo
    assert not res.columnas_extra
    w, s, e, n = fs.HUILA_BBOX
    assert all(s <= r["lat"] <= n and w <= r["lon"] <= e for r in res.registros)


def test_muestra_casos_esperados(tmp_path):
    gen.generar(tmp_path)
    res = read_manifest_dir(tmp_path)
    check_invariant(res)
    assert res.n_input == 132
    assert len(res.registros) == 126
    assert Counter(q["motivo"] for q in res.cuarentena) == {
        "latitud fuera de rango": 1,
        "satélite no reconocido": 1,
        "confianza fuera de dominio": 2,
        "fecha/hora inválida": 1,
        "satélite inconsistente con la fuente": 1,
    }
