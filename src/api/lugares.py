"""Búsqueda explícita de lugares con Nominatim, caché y límite por aplicación."""
from __future__ import annotations

import json
import math
import os
import time
from collections import OrderedDict
from threading import Lock
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
_cache: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
_cerrojo = Lock()
_ultima_consulta = float("-inf")
TTL = 24 * 3600
reloj = time.monotonic
TIPOS = {"city": "Ciudad", "town": "Ciudad", "village": "Localidad", "hamlet": "Localidad",
         "suburb": "Barrio o sector", "neighbourhood": "Barrio", "quarter": "Barrio",
         "municipality": "Municipio", "county": "División administrativa", "state": "Departamento o estado",
         "country": "País", "road": "Calle", "house": "Dirección", "postcode": "Código postal"}


def consultar_proveedor(q: str) -> list:
    base = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
    if urlparse(base).scheme not in ("http", "https"):
        raise ValueError("servicio de lugares mal configurado")
    params = urlencode({"q": q, "format": "jsonv2", "addressdetails": 1, "limit": 6, "accept-language": "es"})
    req = Request(base + ("&" if "?" in base else "?") + params, headers={
        "User-Agent": "HarmonizedHeatNeiva/0.1 (https://github.com/DavidCr0007/NASA_trasas_de_Fuego)",
        "Accept": "application/json",
    })
    with urlopen(req, timeout=10) as r:
        contenido = r.read(1024 * 1024 + 1)
    if len(contenido) > 1024 * 1024:
        raise ValueError("respuesta de lugares demasiado grande")
    datos = json.loads(contenido)
    if not isinstance(datos, list):
        raise ValueError("respuesta de lugares inválida")
    return datos


def normalizar(datos: list) -> list[dict]:
    resultado = []
    vistos = set()
    for d in datos[:6]:
        try:
            lat, lon = float(d["lat"]), float(d["lon"])
            if not math.isfinite(lat + lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            tipo = d.get("addresstype") or d.get("type") or "place"
            nombre = d.get("name") or str(d.get("display_name", "Lugar")).split(",")[0]
            descripcion = str(d.get("display_name") or nombre)
            clave = (descripcion, round(lat, 6), round(lon, 6))
            if clave in vistos:
                continue
            vistos.add(clave)
            try:
                s, n, w, e = map(float, d["boundingbox"])
                if not (-180 <= w < e <= 180 and -90 <= s < n <= 90 and w <= lon <= e and s <= lat <= n):
                    raise ValueError("recuadro inválido")
            except (KeyError, TypeError, ValueError):
                w, s, e, n = max(-180, lon-.005), max(-90, lat-.005), min(180, lon+.005), min(90, lat+.005)
            resultado.append({"id": str(d.get("place_id", len(resultado))), "nombre": str(nombre),
                              "descripcion": descripcion, "tipo": TIPOS.get(tipo, "Lugar"),
                              "lat": lat, "lon": lon, "bbox": [w, s, e, n]})
        except (KeyError, TypeError, ValueError):
            continue
    return resultado


@router.get("/buscar-lugares")
def buscar_lugares(q: str = Query(min_length=3, max_length=160)):
    global _ultima_consulta
    texto = " ".join(q.split())
    if len(texto) < 3:
        raise HTTPException(422, "Escriba al menos tres caracteres")
    clave = texto.casefold()
    if not _cerrojo.acquire(timeout=.05):
        raise HTTPException(429, "Hay una búsqueda en curso. Espere un momento y vuelva a buscar", headers={"Retry-After": "2"})
    try:
        ahora = reloj()
        guardado = _cache.get(clave)
        if guardado and ahora - guardado[0] < TTL:
            _cache.move_to_end(clave)
            resultados = guardado[1]
        else:
            if ahora - _ultima_consulta < 1.1:
                raise HTTPException(429, "Espere un segundo antes de realizar otra búsqueda", headers={"Retry-After": "2"})
            _ultima_consulta = ahora
            try:
                resultados = normalizar(consultar_proveedor(texto))
            except (OSError, ValueError) as e:
                raise HTTPException(503, "El buscador de lugares no está disponible. Compruebe la conexión o vuelva a intentarlo") from e
            _cache[clave] = (ahora, resultados)
            if len(_cache) > 128:
                _cache.popitem(last=False)
        return {"resultados": resultados, "fuente": "Nominatim / OpenStreetMap", "atribucion": "© OpenStreetMap contributors"}
    finally:
        _cerrojo.release()
