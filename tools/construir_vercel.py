"""Compilación en Vercel (ADR 0016): genera la muestra sintética histórica y la procesa.

Es lo mismo que ``make demo`` para el conjunto que sirve la API (``data/processed/demo_historica``),
sin Make. Vercel lo ejecuta tras instalar las dependencias (``[tool.vercel.scripts] build`` en
pyproject.toml); ``vercel_app.py`` lo vuelve a llamar sobre /tmp si la compilación no dejó los datos.

Uso: ``uv run python tools/construir_vercel.py [carpeta_salida]``
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from harmonize.pipeline import main as pipeline_main  # noqa: E402

DESTINO = RAIZ / "data" / "processed" / "demo_historica"


def _generador():
    spec = importlib.util.spec_from_file_location("generar_historico", RAIZ / "tools" / "generar_historico.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def construir(destino: Path = DESTINO) -> Path:
    """Muestra SINTÉTICA 2020–2026 → parquet procesados en ``destino``. Devuelve ``destino``."""
    destino = Path(destino)
    with tempfile.TemporaryDirectory(prefix="hhn-muestra-") as tmp:
        crudo = Path(tmp) / "sample_historica"
        _generador().generar(crudo)
        if pipeline_main(["--input", str(crudo), "--output", str(destino)]) != 0:
            raise RuntimeError("el pipeline no pudo procesar la muestra sintética")
    if not (destino / "celda_dia.parquet").exists():
        raise RuntimeError(f"no se generó {destino / 'celda_dia.parquet'}")
    return destino


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    modo = os.environ.get("HHN_MODO_DATOS", "demo").lower()
    if modo == "firms":
        from ingest.vercel_firms import construir_firms
        destino = construir_firms(Path(args[0]) if args else DESTINO.parent/"vercel_firms")
        print(f"Conjunto FIRMS real procesado en {destino}")
    elif modo == "demo":
        destino = construir(Path(args[0]) if args else DESTINO)
        print(f"Muestra sintética procesada en {destino}")
    else:
        raise RuntimeError("HHN_MODO_DATOS debe ser demo o firms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
