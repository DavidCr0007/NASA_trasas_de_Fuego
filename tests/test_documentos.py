"""§10: la presentación y los documentos se mantienen sincronizados con el código."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import ANIOS_MINIMOS_DEFECTO, PERCENTIL_DEFECTO, create_app
from api.cita import AVISO, CITA
from harmonize import RULES_VERSION
from harmonize.pipeline import main as pipeline_main
from ingest.firms_schema import HUILA_BBOX

RAIZ = Path(__file__).resolve().parent.parent
BBOX = ",".join(str(v) for v in HUILA_BBOX)


@pytest.mark.parametrize("doc", ["README.md", "docs/pitch.md", "docs/metodologia.md"])
def test_version_de_reglas_vigente_en_documentos(doc):
    texto = (RAIZ / doc).read_text(encoding="utf-8")
    assert RULES_VERSION in texto, doc


def test_readme_lleva_cita_y_aviso_literales():
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert CITA in texto and AVISO in texto


def test_pitch_cifras_de_parametros():
    texto = (RAIZ / "docs" / "pitch.md").read_text(encoding="utf-8")
    assert f"percentil {PERCENTIL_DEFECTO}" in texto
    assert f"{ANIOS_MINIMOS_DEFECTO} años" in texto


def test_pitch_periodo_critico_coincide_con_la_api(tmp_path):
    spec_path = RAIZ / "tools" / "generar_historico.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("generar_historico", spec_path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    gen.generar(tmp_path / "crudo")
    assert pipeline_main(["--input", str(tmp_path / "crudo"), "--output", str(tmp_path / "out")]) == 0
    cuerpo = TestClient(create_app(tmp_path / "out")).get(
        f"/calendario?bbox={BBOX}&desde=2026-01-01&hasta=2026-12-31").json()
    p = sorted(cuerpo["periodos_inusuales"], key=lambda p: (-p["dias"], -p["maximo"]))[0]
    texto = (RAIZ / "docs" / "pitch.md").read_text(encoding="utf-8")
    assert f"**{p['inicio']} al {p['fin']}**" in texto
    # Desde H8 la métrica es «celdas activas equivalentes» (ADR 0011); el pitch la redondea.
    assert f"{p['dias']} días con un máximo de {round(p['maximo'])} celdas activas por día" in texto


def test_guion_cabe_en_dos_minutos():
    texto = (RAIZ / "docs" / "pitch.md").read_text(encoding="utf-8")
    guion = texto.split("## Guion", 1)[1].split("## Cifras", 1)[0]
    palabras = len(re.findall(r"\w+", guion))
    assert 200 <= palabras <= 320, palabras  # ~130-160 palabras por minuto
