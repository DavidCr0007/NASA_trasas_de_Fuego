"""Límites geoBoundaries gbOpen bajo demanda, con caché local por país y nivel."""
from __future__ import annotations

import json
import re
import tempfile
from threading import Lock
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException

router = APIRouter()
CACHE = Path(__file__).resolve().parents[2] / "data/processed/limites_globales"
MAX_BYTES = 48 * 1024 * 1024


def descargar_json(url: str) -> dict | list:
    sitio = urlparse(url)
    if sitio.scheme != "https" or sitio.hostname not in {
        "www.geoboundaries.org", "geoboundaries.org", "github.com",
        "raw.githubusercontent.com", "media.githubusercontent.com",
    }:
        raise ValueError("origen de límites no admitido")
    with urlopen(Request(url, headers={"User-Agent": "HarmonizedHeat/0.1"}), timeout=25) as r:
        contenido = r.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise ValueError("el archivo excede el límite de descarga")
    return json.loads(contenido)


@lru_cache(maxsize=512)
def bloqueo(iso: str, nivel: int):
    return Lock()


@lru_cache(maxsize=8)
def obtener(iso: str, nivel: int) -> dict:
    with bloqueo(iso, nivel):
        return obtener_archivo(iso, nivel)


def obtener_archivo(iso: str, nivel: int) -> dict:
    archivo = CACHE / f"{iso}-ADM{nivel}.json"
    if archivo.exists():
        return json.loads(archivo.read_text(encoding="utf-8"))
    meta = descargar_json(f"https://www.geoboundaries.org/api/current/gbOpen/{iso}/ADM{nivel}/")
    if isinstance(meta, list):
        if not meta:
            raise FileNotFoundError("nivel no publicado")
        meta = meta[0]
    if not isinstance(meta, dict):
        raise ValueError("metadatos de límites inválidos")
    enlace = meta.get("simplifiedGeometryGeoJSON") or meta.get("gjDownloadURL")
    if not enlace:
        raise FileNotFoundError("geometría no publicada")
    geo = descargar_json(enlace)
    if not isinstance(geo, dict) or geo.get("type") != "FeatureCollection" or not isinstance(geo.get("features"), list):
        raise ValueError("geometría inválida")
    geo["metadatos"] = {k: meta.get(k) for k in (
        "boundaryID", "boundaryISO", "boundaryType", "boundaryYearRepresented",
        "boundarySource", "boundaryLicense", "licenseDetail", "sourceDataUpdateDate",
    )}
    CACHE.mkdir(parents=True, exist_ok=True)
    # Escritura atómica: una consulta nunca lee un archivo parcialmente escrito.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CACHE, delete=False) as f:
        json.dump(geo, f, ensure_ascii=False, separators=(",", ":"))
        temporal = Path(f.name)
    temporal.replace(archivo)
    return geo


@router.get("/limites/{iso}/{nivel}")
def limites(iso: str, nivel: int):
    iso = iso.upper()
    if not re.fullmatch(r"[A-Z]{3}", iso) or nivel not in (0, 1, 2):
        raise HTTPException(422, "indique un país ISO-3 y un nivel 0, 1 o 2")
    try:
        return obtener(iso, nivel)
    except (FileNotFoundError, HTTPError) as e:
        if isinstance(e, FileNotFoundError) or e.code == 404:
            raise HTTPException(404, f"geoBoundaries no publica ADM{nivel} para {iso}") from e
        raise HTTPException(503, "No se pudo consultar geoBoundaries; vuelva a intentar") from e
    except (OSError, ValueError, KeyError) as e:
        raise HTTPException(503, "Límites no disponibles sin conexión o respuesta inválida") from e
