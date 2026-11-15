"""Cifrado, carga de secretos y modo real: sin red y sin credenciales personales."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from api.app import create_app
from harmonize.pipeline import ejecutar
from ingest.credenciales import ErrorCredencial, leer_clave, estado_publico
from ingest.vercel_firms import construir_firms

RAIZ=Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    for nombre in ("FIRMS_MAP_KEY","FIRMS_MAP_KEY_ENCRYPTED","FIRMS_SECRET_KEY","HHN_MODO_DATOS","HHN_DATOS","FIRMS_NRT_DIAS"):
        monkeypatch.delenv(nombre,raising=False)


def test_descifrado_y_prioridad_de_secretos(tmp_path,monkeypatch):
    archivo=tmp_path/".env";archivo.write_text("FIRMS_MAP_KEY=clave-local\n")
    maestra=Fernet.generate_key();cifrado=Fernet(maestra).encrypt(b"clave-servidor").decode()
    monkeypatch.setenv("FIRMS_MAP_KEY_ENCRYPTED",cifrado);monkeypatch.setenv("FIRMS_SECRET_KEY",maestra.decode())
    assert leer_clave(archivo)=="clave-servidor"
    assert estado_publico(archivo)=={"configurada":True,"cifrada":True,"estado":"configurada"}


def test_cifrado_invalido_no_recurre_a_clave_plana(tmp_path,monkeypatch):
    archivo=tmp_path/".env";archivo.write_text("FIRMS_MAP_KEY=clave-privada\n")
    monkeypatch.setenv("FIRMS_MAP_KEY_ENCRYPTED","cifrado-invalido")
    with pytest.raises(ErrorCredencial) as e:leer_clave(archivo)
    assert "clave-privada" not in str(e.value) and "cifrado-invalido" not in str(e.value)
    assert estado_publico(archivo)["estado"]=="cifrado_invalido"


def test_cifrar_archivo_es_reversible_e_idempotente(tmp_path):
    spec=importlib.util.spec_from_file_location("cifrar",RAIZ/"tools/cifrar_clave_firms.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    archivo=tmp_path/".env";archivo.write_text("# prueba\nFIRMS_MAP_KEY=clave-original\nOTRA=valor\n")
    m.cifrar_archivo(archivo)
    assert leer_clave(archivo)=="clave-original" and "clave-original" not in archivo.read_text()
    assert "OTRA=valor" in archivo.read_text()
    antes=archivo.read_bytes();m.cifrar_archivo(archivo);assert archivo.read_bytes()==antes


def test_conjunto_real_se_construye_y_no_filtra_la_clave(tmp_path,monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY","clave-prueba");urls=[]
    def proveedor(url):
        urls.append(url)
        if "MODIS_NRT" in url:
            return b"latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,confidence,version,bright_t31,frp,daynight\n2.93,-75.28,330,1,1,2026-11-14,1800,Terra,90,6.1NRT,300,5,D\n"
        sat="N20" if "NOAA20" in url else "N21"
        return ("latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n2.93,-75.28,330,.4,.4,2026-11-14,1800,"+sat+",n,2.0NRT,300,5,D\n").encode()
    construir_firms(tmp_path/"real",fetch=proveedor,ahora=datetime(2026,11,15,tzinfo=timezone.utc))
    assert len(urls)==3
    filas=pq.read_table(tmp_path/"real/detecciones.parquet").to_pylist()
    assert filas and all(f["sintetico"] is False for f in filas)
    for archivo in (tmp_path/"real").iterdir():assert b"clave-prueba" not in archivo.read_bytes()


def test_error_del_proveedor_no_expone_url_ni_genera_demo(tmp_path,monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY","clave-protegida")
    def proveedor(url):raise OSError(url)
    with pytest.raises(RuntimeError) as e:construir_firms(tmp_path/"real",fetch=proveedor)
    assert "clave-protegida" not in str(e.value) and not (tmp_path/"real/celda_dia.parquet").exists()


def test_diagnostico_http_no_devuelve_secretos(tmp_path,monkeypatch):
    ejecutar(RAIZ/"data/sample",tmp_path/"datos")
    maestra=Fernet.generate_key();cifrado=Fernet(maestra).encrypt(b"no-publicar-valor").decode()
    monkeypatch.setenv("FIRMS_MAP_KEY_ENCRYPTED",cifrado);monkeypatch.setenv("FIRMS_SECRET_KEY",maestra.decode())
    r=TestClient(create_app(tmp_path/"datos")).get("/estado-servicios")
    assert r.status_code==200 and r.json()["firms"]["cifrada"] is True
    assert all(v not in r.text for v in ("no-publicar-valor",maestra.decode(),cifrado))
