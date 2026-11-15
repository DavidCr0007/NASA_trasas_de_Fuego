"""Construcción del conjunto NRT para Vercel. Solo se activa con HHN_MODO_DATOS=firms."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

from harmonize.pipeline import ejecutar
from ingest.credenciales import leer_clave
from ingest.firms_download import download

FUENTES = ("MODIS_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")


def construir_firms(destino: Path, *, fetch=None, ahora=None) -> Path:
    clave = leer_clave()
    if not clave:
        raise RuntimeError("Faltan las credenciales FIRMS del servidor. Configure los secretos de producción antes de activar el modo firms.")
    try:
        dias = int(os.environ.get("FIRMS_NRT_DIAS", "1"))
        if not 1 <= dias <= 3:
            raise ValueError()
    except ValueError:
        raise RuntimeError("FIRMS_NRT_DIAS debe estar entre 1 y 3.") from None
    ahora = ahora or datetime.now(timezone.utc)
    fin = ahora.date() - timedelta(days=1)  # día UTC completo; el último dato conserva su hora real
    inicio = fin-timedelta(days=dias-1)
    def descargar(url):
        with urlopen(url, timeout=15) as r:
            contenido = r.read(32*1024*1024+1)
        if len(contenido)>32*1024*1024:
            raise ValueError("Descarga demasiado grande")
        return contenido
    try:
        with tempfile.TemporaryDirectory(prefix="hhn-firms-") as tmp:
            crudos = Path(tmp)
            rechazadas = []
            archivos = download(sources=FUENTES, start=inicio, end=fin, bbox=(-180,-90,180,90),
                                out=crudos/"firms", root=crudos, map_key=clave, manifest=crudos/"manifest.jsonl",
                                fetch=fetch or descargar, now=lambda:ahora, pause=0.2, rejected=rechazadas)
            if rechazadas or len(archivos)!=len(FUENTES):
                raise RuntimeError("FIRMS no devolvió todos los productos esperados")
            ejecutar(crudos, destino)
    except Exception:
        # Las URLs FIRMS incluyen la clave; las excepciones del proveedor nunca salen al log.
        raise RuntimeError("No se pudo construir el conjunto FIRMS real. Revise la clave, la conexión y la disponibilidad de los productos; no se sustituirá por datos sintéticos.") from None
    (destino/"conexion_firms.json").write_text(json.dumps({"consultado_utc":ahora.isoformat(),"desde":inicio.isoformat(),"hasta":fin.isoformat(),"fuentes":FUENTES}),encoding="utf-8")
    return destino
