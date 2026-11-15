"""Linaje público coherente con el pipeline y clasificación conservadora del origen."""
import csv
import io
import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from harmonize.pipeline import ejecutar

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def datos(tmp_path_factory):
    salida = tmp_path_factory.mktemp("linaje")
    ejecutar(RAIZ / "data/sample", salida)
    return salida


def test_linaje_conserva_entradas_conteos_e_identidad(datos, tmp_path):
    p = TestClient(create_app(datos)).get("/procedencia").json()
    a = p["analisis"]
    resumen = json.loads((datos/"resumen.json").read_text(encoding="utf-8"))
    assert p["mismo_conjunto"] and a == p["global"]
    assert a["origen_datos"] == "sintetico" and a["registros_sin_linaje"] == 0
    assert a["registros"] == resumen["conteos"]["aceptados"]+resumen["conteos"]["deduplicados"]
    assert len(a["dataset_id"]) == 64 and "no verifica" in a["verificacion"]
    assert {f["sha256"] for f in a["fuentes"]} == {f["sha256"] for f in resumen["archivos_entrada"]}
    shutil.copytree(datos,tmp_path/"copia")
    assert TestClient(create_app(tmp_path/"copia")).get("/procedencia").json()["analisis"]["dataset_id"] == a["dataset_id"]
    assert str(datos) not in json.dumps(p)


def test_registro_y_csv_permiten_volver_al_crudo(datos):
    cliente=TestClient(create_app(datos))
    parametros={"area":"huila"}
    cuerpo=cliente.get("/detecciones",params=parametros).json()
    d=cuerpo["detecciones"][0]
    origen=next(r for r in pq.read_table(datos/"detecciones.parquet").to_pylist() if r["record_id"]==d["record_id"])
    for campo in ("fuente","coleccion","archivo_origen","sha256_origen","fila","sintetico","rules_version"):
        assert d[campo]==origen[campo]
    assert d["fecha_descarga"].endswith("Z") and d["dataset_id"]==cuerpo["dataset_id"]
    texto=cliente.get("/detecciones.csv",params=parametros).text
    contenido="\n".join(l for l in texto.splitlines() if not l.startswith("#"))
    fila=next(csv.DictReader(io.StringIO(contenido)))
    assert fila["sha256_origen"]==d["sha256_origen"] and fila["record_id"]==d["record_id"]
    assert f"dataset_id: {cuerpo['dataset_id']}" in texto


def test_sinteticos_deduplicados_no_quedan_ocultos_por_representantes_reales(datos,tmp_path):
    shutil.copytree(datos,tmp_path/"mixto")
    tabla=pq.read_table(datos/"detecciones.parquet")
    pos=tabla.schema.get_field_index("sintetico")
    pq.write_table(tabla.set_column(pos,tabla.schema.field(pos),pa.array([False]*tabla.num_rows)),tmp_path/"mixto/detecciones.parquet")
    cliente=TestClient(create_app(tmp_path/"mixto"))
    for ruta in ("/salud","/calendario?area=huila","/global"):
        assert cliente.get(ruta).json()["origen_datos"]=="mixto"


def test_sin_manifiesto_no_inventa_identificador(datos,tmp_path):
    shutil.copytree(datos,tmp_path/"incompleto")
    (tmp_path/"incompleto/resumen.json").unlink()
    p=TestClient(create_app(tmp_path/"incompleto")).get("/procedencia").json()["analisis"]
    assert p["dataset_id"] is None and p["conteos_pipeline"] is None


def test_metodo_y_limitaciones_son_publicos_y_la_nota_usa_la_metrica_activa(datos):
    cliente=TestClient(create_app(datos,anios_minimos=1))
    assert "celdas activas equivalentes" in cliente.get("/calendario?area=huila").json()["linea_base"]["nota"]
    assert "n_brutas" in cliente.get("/calendario?area=huila&metrica=n_brutas").json()["linea_base"]["nota"]
    for ruta in ("/metodologia","/limitaciones"):
        r=cliente.get(ruta)
        assert r.status_code==200 and len(r.text)>1000 and r.headers["content-type"].startswith("text/plain")
