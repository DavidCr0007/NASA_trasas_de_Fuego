"""API de solo lectura sobre las salidas Parquet de la armonización (H3).

Requisitos: D-02 (calidad NRT/estándar visible), D-05 (versión de reglas),
D-07 (metadatos de incertidumbre), D-08 (mínimo de años de base) y D-10 (cita).
No recibe ni guarda datos personales (D-09).
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from api.cita import AVISO, CITA
from harmonize.config import RulesConfig
from harmonize.pipeline import ARCHIVOS_PARQUET

# D-08 / ADR 0005: mínimo de años con dato para calcular la línea base. PROVISIONAL.
ANIOS_MINIMOS_DEFECTO = 5
# R5 / ADR 0004: percentil de la climatología por día del año (por defecto 95).
PERCENTIL_DEFECTO = 95

# Resolución nominal en nadir: tabla oficial de atributos FIRMS (docs/esquema_firms.md).
RESOLUCION_M = {"MODIS": 1000, "VIIRS": 375}
SEMILADO_NOMINAL_M = {s: r / 2 for s, r in RESOLUCION_M.items()}
CLASES = ("baja", "nominal", "alta")
LIMITE_DETECCIONES = 50_000


def _calidad(valores: set[str]) -> str | None:
    if not valores:
        return None
    if valores == {"NRT"}:
        return "NRT"
    if valores == {"estandar"}:
        return "estandar"
    return "mixta"


def _parse_bbox(texto: str) -> tuple[float, float, float, float]:
    partes = texto.split(",")
    if len(partes) != 4:
        raise HTTPException(422, "bbox debe tener 4 valores: W,S,E,N")
    try:
        w, s, e, n = (float(p) for p in partes)
    except ValueError:
        raise HTTPException(422, "bbox debe ser numérico: W,S,E,N") from None
    if not (-180 <= w <= 180 and -180 <= e <= 180 and -90 <= s <= 90 and -90 <= n <= 90):
        raise HTTPException(422, "bbox fuera de rango (longitud ±180, latitud ±90)")
    if w >= e or s >= n:
        raise HTTPException(422, "bbox inválido: se requiere W < E y S < N")
    return w, s, e, n


def create_app(
    datos: Path,
    *,
    anios_minimos: int | None = None,
    percentil: int = PERCENTIL_DEFECTO,
) -> FastAPI:
    datos = Path(datos)
    minimo_provisional = anios_minimos is None
    minimo = ANIOS_MINIMOS_DEFECTO if anios_minimos is None else anios_minimos
    cfg = RulesConfig()
    app = FastAPI(
        title="Harmonized Heat Neiva",
        description="Calendario armonizado de focos de calor MODIS y VIIRS (NASA FIRMS). " + CITA,
        version="0.1.0",
    )

    ruta = {nombre.removesuffix(".parquet"): datos / nombre for nombre in ARCHIVOS_PARQUET.values()}

    def faltantes() -> list[str]:
        return [p.name for p in ruta.values() if not p.exists()]

    def base() -> dict[str, Any]:
        """Campos comunes a toda respuesta: versión de reglas (D-05) y cita (D-10)."""
        falta = faltantes()
        if falta:
            raise HTTPException(503, f"falta(n) {', '.join(falta)} en {datos}; ejecute make demo")
        meta = pq.read_metadata(ruta["celda_dia"]).metadata or {}
        return {
            "rules_version": meta.get(b"rules_version", b"").decode(),
            "config_fingerprint": meta.get(b"config_fingerprint", b"").decode(),
            "cita": CITA,
            "aviso": AVISO,
        }

    def rango(con, bbox, desde: date | None, hasta: date | None) -> tuple[date | None, date | None]:
        if desde and hasta and desde > hasta:
            raise HTTPException(422, "desde debe ser anterior o igual a hasta")
        if desde is None or hasta is None:
            lo, hi = con.execute(
                f"select min(fecha_utc), max(fecha_utc) from read_parquet('{ruta['celda_dia']}')"
            ).fetchone()
            desde, hasta = desde or lo, hasta or hi
            if desde and hasta and desde > hasta:
                raise HTTPException(422, "desde debe ser anterior o igual a hasta")
        return desde, hasta

    def incertidumbre(con, bbox, desde, hasta, dias: list[dict] | None) -> dict[str, Any]:
        w, s, e, n = bbox
        filtro = "lat between ? and ? and lon between ? and ? and cast(fecha_hora_utc at time zone 'UTC' as date) between ? and ?"
        params = [s, n, w, e, desde, hasta]
        det = f"read_parquet('{ruta['detecciones']}')"
        pasadas = {
            sat: {"min": hmin, "max": hmax, "n": cnt}
            for sat, hmin, hmax, cnt in con.execute(
                f"select satelite, min(strftime(fecha_hora_utc at time zone 'UTC', '%H:%M')),"
                f" max(strftime(fecha_hora_utc at time zone 'UTC', '%H:%M')), count(*)"
                f" from {det} where {filtro} group by 1 order by 1", params,
            ).fetchall()
        }
        clases = dict.fromkeys(CLASES, 0)
        for clase, cnt in con.execute(
            f"select confianza_clase, count(*) from {det} where {filtro} group by 1", params
        ).fetchall():
            clases[clase] = cnt
        anios = [r[0] for r in con.execute(
            f"select distinct year(fecha_utc) from read_parquet('{ruta['celda_dia']}')"
            " where centroide_lat between ? and ? and centroide_lon between ? and ? order by 1",
            [s, n, w, e],
        ).fetchall()]
        out: dict[str, Any] = {
            "resolucion_m": dict(RESOLUCION_M),
            "semilado_nominal_m": dict(SEMILADO_NOMINAL_M),
            "nota_resolucion": (
                "Cada foco es el centro de un píxel; el tamaño real crece hacia el borde del barrido."
            ),
            "grilla_deg": cfg.cell_deg,
            "horario_pasada_utc": pasadas,
            "clases_confianza": clases,
            "anios_con_dato": anios,
        }
        if dias is not None:
            total = len(dias)
            con_dato = sum(1 for d in dias if d["n_detecciones"] > 0)
            out["dias_en_rango"] = total
            out["porcentaje_dias_con_dato"] = round(100 * con_dato / total, 1) if total else 0.0
        return out

    def linea_base(anios: list[int]) -> dict[str, Any]:
        suficiente = len(anios) >= minimo
        return {
            "estado": "suficiente" if suficiente else "base insuficiente",
            "anios_disponibles": len(anios),
            "anios_minimos": minimo,
            "percentil": percentil,
            "metodo": "climatología por día del año (R5)",
            "nota": (
                ("Mínimo de años PROVISIONAL (ADR 0005). " if minimo_provisional else "")
                + ("El cálculo de días inusuales llega en H4." if suficiente
                   else "No se calculan días inusuales con menos años que el mínimo.")
            ),
        }

    def calendario(bbox_txt: str, desde: date | None, hasta: date | None) -> dict[str, Any]:
        bbox = _parse_bbox(bbox_txt)
        cuerpo = base()
        w, s, e, n = bbox
        con = duckdb.connect()
        try:
            desde, hasta = rango(con, bbox, desde, hasta)
            filas = {} if desde is None else {
                f: (nd, nb, nm, nv, cal, frp_max, frp_sum)
                for f, nd, nb, nm, nv, cal, frp_max, frp_sum in con.execute(
                    f"select fecha_utc, sum(n_detecciones), sum(n_brutas), sum(n_modis), sum(n_viirs),"
                    f" string_agg(calidades, ','), max(frp_max), sum(frp_sum)"
                    f" from read_parquet('{ruta['celda_dia']}')"
                    " where centroide_lat between ? and ? and centroide_lon between ? and ?"
                    " and fecha_utc between ? and ? group by 1",
                    [s, n, w, e, desde, hasta],
                ).fetchall()
            }
            dias = []
            calidades_global: set[str] = set()
            dia = desde
            while dia is not None and dia <= hasta:
                nd, nb, nm, nv, cal, frp_max, frp_sum = filas.get(dia, (0, 0, 0, 0, None, None, None))
                cals = {c for c in (cal or "").split(",") if c}
                calidades_global |= cals
                dias.append({
                    "fecha_utc": dia.isoformat(),
                    "n_detecciones": int(nd), "n_brutas": int(nb),
                    "n_modis": int(nm), "n_viirs": int(nv),
                    "frp_max": None if frp_max is None else round(frp_max, 2),
                    "frp_sum": None if frp_sum is None else round(frp_sum, 2),
                    "calidad": _calidad(cals), "preliminar": "NRT" in cals,
                })
                dia += timedelta(days=1)
            inc = incertidumbre(con, bbox, desde, hasta, dias)
        finally:
            con.close()
        cuerpo.update({
            "bbox": list(bbox),
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
            "calidad": _calidad(calidades_global),
            "preliminar": "NRT" in calidades_global,
            "nota_conteos": (
                "n_detecciones cuenta representantes tras deduplicar (R3); n_brutas, las detecciones "
                "originales. Para comparar con el visor de FIRMS use n_brutas."
            ),
            "dias": dias,
            "incertidumbre": inc,
            "linea_base": linea_base(inc["anios_con_dato"]),
        })
        return cuerpo

    @app.get("/salud")
    def salud():
        falta = faltantes()
        if falta:
            return JSONResponse(
                status_code=503,
                content={"estado": "sin datos", "detalle": f"falta(n) {', '.join(falta)} en {datos}"},
            )
        return {"estado": "ok", **base()}

    @app.get("/cita")
    def cita():
        return base()

    @app.get("/calendario")
    def get_calendario(
        bbox: str = Query(..., description="W,S,E,N en grados"),
        desde: date | None = None,
        hasta: date | None = None,
    ):
        return calendario(bbox, desde, hasta)

    @app.get("/calendario.csv")
    def get_calendario_csv(bbox: str = Query(...), desde: date | None = None, hasta: date | None = None):
        cuerpo = calendario(bbox, desde, hasta)
        buf = io.StringIO()
        for linea in (
            cuerpo["cita"], cuerpo["aviso"],
            f"rules_version: {cuerpo['rules_version']} config_fingerprint: {cuerpo['config_fingerprint']}",
            f"calidad: {cuerpo['calidad']}; preliminar: {str(cuerpo['preliminar']).lower()}"
            + (" (contiene datos NRT preliminares)" if cuerpo["preliminar"] else ""),
            f"bbox: {','.join(str(v) for v in cuerpo['bbox'])} desde: {cuerpo['desde']} hasta: {cuerpo['hasta']}",
            f"linea_base: {cuerpo['linea_base']['estado']}",
        ):
            buf.write(f"# {linea}\n")
        campos = ["fecha_utc", "n_detecciones", "n_brutas", "n_modis", "n_viirs",
                  "frp_max", "frp_sum", "calidad", "preliminar"]
        escritor = csv.DictWriter(buf, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(cuerpo["dias"])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8")

    @app.get("/detecciones")
    def get_detecciones(
        bbox: str = Query(...),
        desde: date | None = None,
        hasta: date | None = None,
        limite: int = Query(5000, ge=1, le=LIMITE_DETECCIONES),
    ):
        caja = _parse_bbox(bbox)
        cuerpo = base()
        w, s, e, n = caja
        con = duckdb.connect()
        try:
            desde, hasta = rango(con, caja, desde, hasta)
            filas = [] if desde is None else con.execute(
                f"select record_id, sensor, satelite, fecha_hora_utc at time zone 'UTC', calidad,"
                f" confianza_clase, confianza_raw, lat, lon, frp, cell_id, version, n_fusionados"
                f" from read_parquet('{ruta['detecciones']}')"
                " where lat between ? and ? and lon between ? and ?"
                " and cast(fecha_hora_utc at time zone 'UTC' as date) between ? and ?"
                " order by fecha_hora_utc, record_id limit ?",
                [s, n, w, e, desde, hasta, limite + 1],
            ).fetchall()
            inc = incertidumbre(con, caja, desde, hasta, None) if desde else {}
        finally:
            con.close()
        columnas = ["record_id", "sensor", "satelite", "fecha_hora_utc", "calidad", "confianza_clase",
                    "confianza_raw", "lat", "lon", "frp", "cell_id", "version", "n_fusionados"]
        detecciones = []
        for fila in filas[:limite]:
            d = dict(zip(columnas, fila))
            d["fecha_hora_utc"] = d["fecha_hora_utc"].strftime("%Y-%m-%dT%H:%M:%SZ")
            d["semilado_nominal_m"] = SEMILADO_NOMINAL_M[d["sensor"]]
            d["preliminar"] = d["calidad"] == "NRT"
            detecciones.append(d)
        cuerpo.update({
            "bbox": list(caja),
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
            "truncado": len(filas) > limite,
            "detecciones": detecciones,
            "incertidumbre": inc,
        })
        return cuerpo

    return app
