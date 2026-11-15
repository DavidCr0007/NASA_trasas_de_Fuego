"""Linaje público del conjunto; distingue declaración de origen de verificación científica.

El identificador representa entradas, configuración y hashes declarados por el pipeline.
La comprobación de esos hashes se hace aparte durante la auditoría, nunca se presupone.
No se publican rutas absolutas, URLs de descarga ni credenciales.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import duckdb
import pyarrow.parquet as pq


def describir(datos: Path) -> dict:
    nombres = ("detecciones.parquet", "deduplicados.parquet", "celda_dia.parquet", "cuarentena.parquet", "resumen.json")
    huellas = tuple((n, (datos / n).stat().st_mtime_ns, (datos / n).stat().st_size)
                    for n in nombres if (datos / n).exists())
    return _describir(str(datos.resolve()), huellas)


def estado_origen(origen, calidad):
    if origen == "real":
        return "real_preliminar_nrt" if calidad in ("NRT", "mixta") else "real_declarado"
    return {"sintetico": "sintetico_demostracion", "mixto": "mixto"}.get(origen, "no_verificado")


@lru_cache(maxsize=8)
def _describir(directorio: str, huellas: tuple) -> dict:
    datos = Path(directorio)
    tablas = [datos / n for n in ("detecciones.parquet", "deduplicados.parquet") if (datos / n).exists()]
    consulta = " union all ".join("select * from read_parquet(?)" for _ in tablas)
    with duckdb.connect() as con:
        # UNION BY NAME admite que deduplicados tenga columnas adicionales de R3.
        consulta = consulta.replace(" union all ", " union all by name ")
        filas = con.execute(
            "select fuente, coleccion, archivo_origen, sha256_origen, sintetico, calidad, count(*) as n, "
            "min(fecha_hora_utc at time zone 'UTC'), max(fecha_hora_utc at time zone 'UTC'), "
            "min(fecha_descarga at time zone 'UTC'), max(fecha_descarga at time zone 'UTC'), "
            "count(*) filter(where fila is null or fila < 1 or sha256_origen is null "
            "or not regexp_full_match(sha256_origen, '[0-9a-f]{64}') or archivo_origen is null or archivo_origen = '' "
            "or fuente is null or fuente = '' or fecha_descarga is null) "
            f"from ({consulta}) group by 1,2,3,4,5,6 order by 3,1,2,5,6", [str(p) for p in tablas],
        ).fetchall()
    fuentes = []
    for fuente, coleccion, archivo, sha, sintetico, calidad, n, ini, fin, desc_ini, desc_fin, incompletos in filas:
        fuentes.append({"fuente": fuente, "coleccion": coleccion, "archivo": archivo, "sha256": sha,
                        "sintetico": sintetico, "calidad": calidad, "registros": n,
                        "desde": ini.isoformat()+"Z" if ini else None, "hasta": fin.isoformat()+"Z" if fin else None,
                        "descarga_desde": desc_ini.isoformat()+"Z" if desc_ini else None,
                        "descarga_hasta": desc_fin.isoformat()+"Z" if desc_fin else None,
                        "registros_sin_linaje": incompletos})
    tipos = {f["sintetico"] for f in fuentes}
    origen = "mixto" if True in tipos and False in tipos else "sintetico" if tipos == {True} else "real" if tipos == {False} else None
    calidades = {f["calidad"] for f in fuentes}
    calidad = next(iter(calidades)) if len(calidades) == 1 else "mixta" if calidades else None
    meta = pq.read_metadata(datos / "celda_dia.parquet").metadata or {}
    resumen = json.loads((datos / "resumen.json").read_text(encoding="utf-8")) if (datos / "resumen.json").exists() else {}
    identidad = {k: resumen.get(k) for k in ("archivos_entrada", "parquet_sha256", "rules_version", "config_fingerprint")}
    ident = hashlib.sha256(json.dumps(identidad, sort_keys=True).encode()).hexdigest() if resumen else None
    return {"dataset_id": ident, "rules_version": meta.get(b"rules_version", b"").decode(),
            "config_fingerprint": meta.get(b"config_fingerprint", b"").decode(),
            "origen_datos": origen, "calidad": calidad, "estado_procedencia": estado_origen(origen, calidad),
            "fuentes": fuentes, "registros": sum(f["registros"] for f in fuentes),
            "registros_sin_linaje": sum(f["registros_sin_linaje"] for f in fuentes),
            "convencion_fila": "Registro CSV desde 1, sin contar la cabecera; no es un número de línea física si hay campos multilínea.",
            "conteos_pipeline": resumen.get("conteos"), "invariante_declarado": resumen.get("invariante_ok"),
            "archivos_entrada_declarados": [{"archivo":e.get("archivo"), "sha256":e.get("sha256")} for e in resumen.get("archivos_entrada",[])],
            "parquet_sha256_declarados": resumen.get("parquet_sha256", {}),
            "verificacion": "Linaje declarado por el pipeline; este endpoint no verifica los archivos crudos ni certifica los resultados científicos.",
            "metodologia": "/metodologia", "limitaciones": "/limitaciones"}
