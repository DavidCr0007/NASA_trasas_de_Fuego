"""Cifra la clave existente en .env sin imprimir secretos ni cambiarlos en Vercel."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ingest.credenciales import leer_clave, leer_entorno


def cifrar_archivo(archivo: Path) -> None:
    valores = leer_entorno(archivo)
    if valores.get("FIRMS_MAP_KEY_ENCRYPTED") and not valores.get("FIRMS_MAP_KEY"):
        # Verificar la pareja del archivo, sin depender de secretos distintos del proceso.
        from ingest.credenciales import descifrar
        descifrar(valores["FIRMS_MAP_KEY_ENCRYPTED"], valores.get("FIRMS_SECRET_KEY", ""))
        return
    clave = valores.get("FIRMS_MAP_KEY", "").strip()
    if not clave:
        raise ValueError("El archivo no contiene una clave FIRMS para cifrar.")
    maestra = Fernet.generate_key()
    cifrado = Fernet(maestra).encrypt(clave.encode()).decode()
    quitar = {"FIRMS_MAP_KEY", "FIRMS_MAP_KEY_ENCRYPTED", "FIRMS_SECRET_KEY"}
    lineas = [l for l in archivo.read_text(encoding="utf-8-sig").splitlines() if l.split("=", 1)[0].strip() not in quitar]
    texto = "\n".join(lineas).rstrip()+"\nFIRMS_MAP_KEY_ENCRYPTED="+cifrado+"\nFIRMS_SECRET_KEY="+maestra.decode()+"\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=archivo.resolve().parent, delete=False) as f:
        f.write(texto)
        temporal = Path(f.name)
    try:
        os.replace(temporal, archivo)
    finally:
        temporal.unlink(missing_ok=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archivo", type=Path, default=Path(".env"))
    a = p.parse_args()
    try:
        cifrar_archivo(a.archivo)
    except (OSError, ValueError):
        raise SystemExit("No se pudo cifrar la configuración FIRMS; revise el archivo local. No se imprimieron credenciales.")
    print("Clave cifrada y verificada. El archivo local contiene FIRMS_MAP_KEY_ENCRYPTED y FIRMS_SECRET_KEY. Configure sus valores como Secret en Vercel; no publique este archivo.")
