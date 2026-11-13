"""D-06: el pipeline Parquet es determinista, offline y respeta el invariante."""

import hashlib
import importlib.util
import json
import shutil
import socket
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import pytest

from harmonize import RULES_VERSION
from harmonize.pipeline import ARCHIVOS_PARQUET, main

RAIZ = Path(__file__).resolve().parent.parent
MUESTRA = RAIZ / "data" / "sample"
TABLAS = ("detecciones", "deduplicados", "cuarentena", "celda_dia")


@pytest.fixture(scope="session")
def muestra(tmp_path_factory) -> Path:
    """data/sample si está completa; si no, se regenera (determinista) en un tmp."""
    if (MUESTRA / "manifest.jsonl").exists():
        return MUESTRA
    spec = importlib.util.spec_from_file_location("generar_muestra", RAIZ / "tools" / "generar_muestra.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    destino = tmp_path_factory.mktemp("muestra")
    gen.generar(destino)
    return destino


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _correr(entrada: Path, salida: Path, *extra: str) -> int:
    return main(["--input", str(entrada), "--output", str(salida), *extra])


def _hashes(salida: Path) -> dict[str, str]:
    return {n: _sha(salida / n) for n in (*ARCHIVOS_PARQUET.values(), "resumen.json")}


def test_dos_ejecuciones_mismos_hashes(muestra, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert _correr(muestra, a) == 0
    assert _correr(muestra, b) == 0
    ha, hb = _hashes(a), _hashes(b)
    assert set(ha) == {f"{t}.parquet" for t in TABLAS} | {"resumen.json"}
    assert ha == hb


def test_orden_del_manifiesto_no_cambia_la_salida(muestra, tmp_path):
    copia = tmp_path / "copia"
    shutil.copytree(muestra, copia)
    manifiesto = copia / "manifest.jsonl"
    lineas = [x for x in manifiesto.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lineas) > 1
    manifiesto.write_text("\n".join(reversed(lineas)) + "\n", encoding="utf-8")
    assert _correr(muestra, tmp_path / "orig") == 0
    assert _correr(copia, tmp_path / "perm") == 0
    ref, perm = _hashes(tmp_path / "orig"), _hashes(tmp_path / "perm")
    assert {k: v for k, v in ref.items() if k.endswith(".parquet")} == \
        {k: v for k, v in perm.items() if k.endswith(".parquet")}


def test_resumen_invariante(muestra, tmp_path):
    assert _correr(muestra, tmp_path) == 0
    r = json.loads((tmp_path / "resumen.json").read_text(encoding="utf-8"))
    c = r["conteos"]
    assert c["n_input"] == c["aceptados"] + c["cuarentena"] + c["deduplicados"]
    assert c["n_input"] > 0 and r["invariante_ok"] is True
    assert r["rules_version"] == RULES_VERSION
    assert len(r["config_fingerprint"]) == 64
    assert sum(r["cuarentena_por_motivo"].values()) == c["cuarentena"]
    assert r["archivos_entrada"] and all(len(x["sha256"]) == 64 for x in r["archivos_entrada"])
    assert set(r["parquet_sha256"]) == {f"{t}.parquet" for t in TABLAS}
    assert r["parquet_sha256"] == {n: _sha(tmp_path / n) for n in r["parquet_sha256"]}
    texto = (tmp_path / "resumen.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in texto and str(RAIZ) not in texto  # sin rutas absolutas


def test_rules_version_en_las_cuatro_tablas(muestra, tmp_path):
    assert _correr(muestra, tmp_path) == 0
    for t in TABLAS:
        tabla = pq.read_table(tmp_path / f"{t}.parquet")
        assert tabla.num_rows > 0, t
        assert set(tabla.column("rules_version").to_pylist()) == {RULES_VERSION}, t
        meta = tabla.schema.metadata or {}
        assert meta[b"rules_version"].decode() == RULES_VERSION
        assert len(meta[b"config_fingerprint"]) == 64
        assert b"pandas" not in meta


def test_esquema_y_orden(muestra, tmp_path):
    assert _correr(muestra, tmp_path) == 0
    det = pq.read_table(tmp_path / "detecciones.parquet")
    assert str(det.schema.field("fecha_hora_utc").type) == "timestamp[us, tz=UTC]"
    ids = det.column("record_id").to_pylist()
    assert ids == sorted(ids)
    cd = pq.read_table(tmp_path / "celda_dia.parquet")
    claves = list(zip(cd.column("cell_id").to_pylist(), cd.column("fecha_utc").to_pylist()))
    assert claves == sorted(claves)


def test_duckdb_coincide_con_resumen(muestra, tmp_path):
    assert _correr(muestra, tmp_path) == 0
    c = json.loads((tmp_path / "resumen.json").read_text(encoding="utf-8"))["conteos"]
    esperado = {"detecciones": c["aceptados"], "deduplicados": c["deduplicados"],
                "cuarentena": c["cuarentena"], "celda_dia": c["celda_dia"]}
    con = duckdb.connect()
    for tabla, n in esperado.items():
        ruta = (tmp_path / f"{tabla}.parquet").as_posix()
        got = con.execute(f"SELECT count(*) FROM read_parquet('{ruta}')").fetchone()[0]
        assert got == n, tabla
    con.close()


def test_rechaza_salida_dentro_de_data_raw(muestra, tmp_path, capsys):
    for destino in (RAIZ / "data" / "raw" / "salida_prueba", tmp_path / "data" / "raw" / "x"):
        assert _correr(muestra, destino) != 0
        assert not destino.exists()
        assert "data/raw" in capsys.readouterr().err


def test_sin_red(muestra, tmp_path, monkeypatch):
    def sin_red(*a, **k):
        raise AssertionError("el pipeline no debe abrir sockets")

    monkeypatch.setattr(socket, "socket", sin_red)
    assert _correr(muestra, tmp_path / "x") == 0
    assert _correr(muestra, tmp_path / "y") == 0
    assert _hashes(tmp_path / "x") == _hashes(tmp_path / "y")


def test_manifiesto_explicito(muestra, tmp_path):
    assert _correr(muestra, tmp_path / "m", "--manifest", str(muestra / "manifest.jsonl")) == 0
    assert _correr(muestra, tmp_path / "d") == 0
    assert _hashes(tmp_path / "m") == _hashes(tmp_path / "d")
