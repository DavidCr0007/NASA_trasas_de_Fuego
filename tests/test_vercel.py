"""ADR 0016: la app completa con API en Vercel (importando el repositorio), sin red."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parent.parent


def _modulo(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_configuracion_de_vercel_coherente():
    py = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert py["tool"]["vercel"]["entrypoint"] == "vercel_app:app"
    assert py["tool"]["vercel"]["scripts"]["build"] == "python tools/construir_vercel.py"
    assert (RAIZ / "vercel_app.py").exists() and (RAIZ / "tools" / "construir_vercel.py").exists()
    # Versión de Python admitida por Vercel (3.12–3.14).
    assert (RAIZ / ".python-version").read_text(encoding="utf-8").strip().startswith(("3.12", "3.13", "3.14"))
    v = json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))
    funcion = v["functions"]["vercel_app.py"]  # clave = archivo del punto de entrada
    assert 10 <= funcion["maxDuration"] <= 300
    excluidos = funcion["excludeFiles"]
    # Nunca se excluye lo que la función necesita en ejecución.
    for necesario in ("src/api", "src/harmonize", "src/ingest", "src/ui/static/app.js", "data/processed/demo_historica",
                      "tools/construir_vercel.py", "tools/generar_historico.py"):
        patrones = re.findall(r"[^{},]+", excluidos)
        assert not any(necesario.startswith(p.rstrip("*").rstrip("/")) for p in patrones), necesario
    # Sin secretos ni claves en la configuración de despliegue.
    for archivo in ("vercel.json", "vercel_app.py"):
        texto = (RAIZ / archivo).read_text(encoding="utf-8")
        assert "MAP_KEY" not in texto and "token" not in texto.lower()


def test_construir_genera_la_muestra_procesada(tmp_path):
    destino = _modulo("construir_vercel", RAIZ / "tools" / "construir_vercel.py").construir(tmp_path / "demo")
    for archivo in ("celda_dia.parquet", "detecciones.parquet", "resumen.json"):
        assert (destino / archivo).exists(), archivo


def test_punto_de_entrada_sirve_api_e_interfaz(tmp_path, monkeypatch):
    datos = _modulo("construir_vercel", RAIZ / "tools" / "construir_vercel.py").construir(tmp_path / "demo")
    monkeypatch.setenv("HHN_DATOS", str(datos))
    monkeypatch.setenv("HHN_TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("HHN_CACHE_LIMITES", str(tmp_path / "tmp" / "limites"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    cliente = TestClient(_modulo("vercel_app", RAIZ / "vercel_app.py").app)
    assert cliente.get("/salud").json()["estado"] == "ok"
    assert cliente.get("/", follow_redirects=False).headers["location"] == "/ui/"
    assert "Harmonized Heat · Explorador global" in cliente.get("/ui/").text
    c = cliente.get("/calendario", params={"area": "huila"}).json()
    assert c["origen_datos"] == "sintetico" and c["cita"]


def test_punto_de_entrada_genera_datos_en_tmp_si_faltan(tmp_path, monkeypatch):
    monkeypatch.setenv("HHN_DATOS", str(tmp_path / "no_existe"))
    monkeypatch.setenv("HHN_TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("HHN_CACHE_LIMITES", str(tmp_path / "tmp" / "limites"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    cliente = TestClient(_modulo("vercel_app", RAIZ / "vercel_app.py").app)
    assert (tmp_path / "tmp" / "demo_historica" / "celda_dia.parquet").exists()
    assert cliente.get("/salud").json()["estado"] == "ok"


def test_cache_de_limites_configurable_para_disco_de_solo_lectura(tmp_path, monkeypatch):
    monkeypatch.setenv("HHN_CACHE_LIMITES", str(tmp_path / "cache"))
    limites = _modulo("limites_vercel", RAIZ / "src" / "api" / "limites.py")
    assert limites.CACHE == tmp_path / "cache"
    monkeypatch.delenv("HHN_CACHE_LIMITES")
    assert _modulo("limites_local", RAIZ / "src" / "api" / "limites.py").CACHE == \
        RAIZ / "data" / "processed" / "limites_globales"


@pytest.mark.parametrize("archivo", ["README.md", "docs/decisiones/0016-despliegue-vercel.md"])
def test_documentacion_del_despliegue(archivo):
    texto = (RAIZ / archivo).read_text(encoding="utf-8")
    assert "Vercel" in texto and "vercel_app" in texto
