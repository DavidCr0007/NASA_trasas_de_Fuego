"""API de solo lectura sobre las salidas Parquet de la armonización (H3).

Requisitos: D-02 (calidad NRT/estándar visible), D-05 (versión de reglas),
D-07 (metadatos de incertidumbre), D-08 (mínimo de años de base) y D-10 (cita).
No recibe ni guarda datos personales (D-09).
H6-01: /calendario, /detecciones y la cabecera de /calendario.csv (`# origen_datos: ...`) llevan
`origen_datos` ("sintetico", "real", "mixto" o null) según la columna `sintetico` de todo el conjunto.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.area import contiene, resolver_area
from api.cita import AVISO, CITA
from api import mundo
from harmonize import armonizada as arm
from harmonize import linea_base as lb
from harmonize.config import RulesConfig
from harmonize.pipeline import ARCHIVOS_PARQUET

# D-08 / ADR 0005: mínimo de años con dato para calcular la línea base (acordado 2026-11-13).
ANIOS_MINIMOS_DEFECTO = 5
# R5 / ADR 0004: percentil de la climatología por día del año (por defecto 95).
PERCENTIL_DEFECTO = 95
# ADR 0004: ventana ±días alrededor del día del año. PROVISIONAL.
VENTANA_DIAS_DEFECTO = 7

# Resolución nominal en nadir: tabla oficial de atributos FIRMS (docs/esquema_firms.md).
RESOLUCION_M = {"MODIS": 1000, "VIIRS": 375}
SEMILADO_NOMINAL_M = {s: r / 2 for s, r in RESOLUCION_M.items()}
CLASES = ("baja", "nominal", "alta")
LIMITE_DETECCIONES = 50_000
# ADR 0012: lado (grados) de la celda de agregación del globo. 0,25° ≈ 28 km en el ecuador.
RESOLUCIONES_GLOBAL = (0.25, 0.5, 1.0)
UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "static"


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
    datos_global: Path | None = None,
    anios_minimos: int | None = None,
    percentil: int = PERCENTIL_DEFECTO,
    ventana_dias: int = VENTANA_DIAS_DEFECTO,
) -> FastAPI:
    datos = Path(datos)
    minimo_por_defecto = anios_minimos is None
    minimo = ANIOS_MINIMOS_DEFECTO if anios_minimos is None else anios_minimos
    cfg = RulesConfig()
    app = FastAPI(
        title="Harmonized Heat Neiva",
        description="Calendario armonizado de focos de calor MODIS y VIIRS (NASA FIRMS). " + CITA,
        version="0.1.0",
    )

    ruta = {nombre.removesuffix(".parquet"): datos / nombre for nombre in ARCHIVOS_PARQUET.values()}
    # ADR 0012: el globo puede leer un conjunto aparte (p. ej. NRT global reciente) o el mismo.
    datos_g = Path(datos_global) if datos_global else datos
    ruta_g = {nombre.removesuffix(".parquet"): datos_g / nombre for nombre in ARCHIVOS_PARQUET.values()}

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

    # ------------------------------------------------ H8-02: métrica armonizada (ADR 0011)
    _cache_global: dict[str, Any] = {}

    def registros_sql(where: str, params: list, fd: str):
        cols = "cast(fecha_hora_utc at time zone 'UTC' as date), cell_id, satelite"
        q = (f"select {cols} from read_parquet('{ruta['detecciones']}') where {where}{fd}"
             f" union all select {cols} from read_parquet('{ruta['deduplicados']}') where {where}{fd}")
        return q, params + params

    def armonizacion_global(con):
        """Factores de intercalibración sobre TODO el conjunto (cacheados por versión de archivos)."""
        clave = tuple(p.stat().st_mtime_ns for p in ruta.values())
        if _cache_global.get("clave") != clave:
            q, p = registros_sql("true", [], "")
            cont = arm.contar_por_dia(con.execute(q, p).fetchall())
            er = arm.eras(cont)
            _cache_global.update(clave=clave, eras=er, factores=arm.factores(cont, er))
        return _cache_global["factores"], _cache_global["eras"]

    def serie_area(con, bbox, fd):
        w, s, e, n = bbox
        q, p = registros_sql("lat between ? and ? and lon between ? and ?", [s, n, w, e], fd)
        cont = arm.contar_por_dia(con.execute(q, p).fetchall())
        f, er = armonizacion_global(con)
        return arm.serie_armonizada(cont, f, er), f, er

    def describir_armonizacion(metrica: str, f: dict, er: dict) -> dict:
        r = lambda x: None if x is None else round(x, 4)
        return {
            "metrica": metrica,
            "version": arm.VERSION_METRICA,
            "definicion": ("celdas de ~1 km con al menos una detección de la constelación de referencia "
                           "MODIS (Terra, Aqua) ∪ Suomi NPP; fuera de su era, MODIS × k_M[mes] o "
                           "(MODIS ∪ NOAA-20) / k_N20 (ADR 0011)"),
            "factores": {
                "k_m": {str(m): r(v) for m, v in (f.get("k_m") or {}).items()},
                "k_m_global": r(f.get("k_m_global")),
                "k_n20": r(f.get("k_n20")),
                "anios_superposicion_modis": f.get("anios_superposicion_modis"),
                "n_dias_superposicion_n20": f.get("n_dias_superposicion_n20"),
            },
            "eras": {k: None if v is None else [v[0].isoformat(), v[1].isoformat()] for k, v in er.items()},
        }

    def caja_y_area(bbox_txt: str | None, area: str | None):
        """R-40: un área con forma (huila, mun:<id>) o un recuadro W,S,E,N."""
        if area:
            try:
                info = resolver_area(area)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            return info["bbox"], info
        if bbox_txt:
            return _parse_bbox(bbox_txt), None
        raise HTTPException(422, "indique bbox=W,S,E,N o area=huila|mun:<id>")

    def conectar(info: dict | None, bbox):
        """Conexión DuckDB. Con área, registra la tabla celdas_area (celdas de ~1 km cuyo
        centroide cae en el polígono) y devuelve el filtro SQL para celda_dia y detecciones.
        Calendario y mapa usan así exactamente las mismas celdas."""
        con = duckdb.connect()
        if info is None:
            return con, "", ""
        w, s, e, n = bbox
        filas = con.execute(
            f"select distinct cell_id, centroide_lat, centroide_lon from read_parquet('{ruta['celda_dia']}')"
            " where centroide_lat between ? and ? and centroide_lon between ? and ?", [s, n, w, e],
        ).fetchall()
        geoms = info["geometrias"]
        ids = [cid for cid, la, lo in filas if contiene(geoms, lo, la)]
        con.register("celdas_area", pa.table({"cell_id": pa.array(ids, pa.string())}))
        filtro = " and cell_id in (select cell_id from celdas_area)"
        return con, filtro, filtro

    def describir_area(info: dict | None) -> dict:
        if info is None:
            return {"id": None, "nombre": None, "filtro": "recuadro"}
        return {"id": info["id"], "nombre": info["nombre"], "filtro": "poligono",
                "fuente": "geoBoundaries ADM2 (DANE, CC BY 4.0)"}

    def rango(con, bbox, desde: date | None, hasta: date | None) -> tuple[date | None, date | None]:
        """Recorta el rango pedido a la cobertura de los datos [primer día, último día].

        Fuera de la cobertura no hay observaciones: esos días no son «días sin focos».
        """
        if desde and hasta and desde > hasta:
            raise HTTPException(422, "desde debe ser anterior o igual a hasta")
        lo, hi = con.execute(
            f"select min(fecha_utc), max(fecha_utc) from read_parquet('{ruta['celda_dia']}')"
        ).fetchone()
        if lo is None:
            return None, None
        return max(desde or lo, lo), min(hasta or hi, hi)

    def incertidumbre(con, bbox, desde, hasta, dias: list[dict] | None, fc: str = "", fd: str = "") -> dict[str, Any]:
        w, s, e, n = bbox
        filtro = ("lat between ? and ? and lon between ? and ? and cast(fecha_hora_utc at time zone 'UTC' as date) between ? and ?"
                  + fd)
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
            " where centroide_lat between ? and ? and centroide_lon between ? and ?" + fc + " order by 1",
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
            "metodo": "climatología por día del año (R5), excluyendo el año evaluado",
            "version_r5": lb.VERSION_R5,
            "nota_cobertura": "La referencia usa la cobertura del conjunto de datos: los días sin focos del área cuentan como 0.",
            "ventana_dias": ventana_dias,
            "nota_ventana": "Ventana ±días PROVISIONAL (ADR 0004).",
            "nota": (
                (f"Mínimo de {minimo} años acordado (ADR 0005). " if minimo_por_defecto
                 else f"Mínimo de {minimo} años fijado en la configuración. ")
                + ("Un día es inusual si n_brutas supera el umbral; un día con menos años de "
                   "referencia que el mínimo queda sin umbral." if suficiente
                   else "No se calculan días inusuales con menos años que el mínimo.")
            ),
        }

    def origen(con) -> str | None:
        """H6-01: 'sintetico', 'real', 'mixto' o None según la columna `sintetico` de TODO el conjunto."""
        n_sint, n_real = con.execute(
            "select count(*) filter (where sintetico), count(*) filter (where not sintetico)"
            f" from read_parquet('{ruta['detecciones']}')"
        ).fetchone()
        if n_sint and n_real:
            return "mixto"
        if n_sint:
            return "sintetico"
        return "real" if n_real else None

    def calendario(bbox_txt: str | None, desde: date | None, hasta: date | None,
                   area: str | None = None, metrica: str = "armonizada") -> dict[str, Any]:
        if metrica not in ("armonizada", "n_brutas"):
            raise HTTPException(422, "metrica debe ser 'armonizada' o 'n_brutas'")
        bbox, info_area = caja_y_area(bbox_txt, area)
        desde_sol, hasta_sol = desde, hasta
        cuerpo = base()
        w, s, e, n = bbox
        con, fc, fd = conectar(info_area, bbox)
        try:
            desde, hasta = rango(con, bbox, desde, hasta)
            filas = {} if desde is None else {
                f: (nd, nb, nm, nv, cal, frp_max, frp_sum)
                for f, nd, nb, nm, nv, cal, frp_max, frp_sum in con.execute(
                    f"select fecha_utc, sum(n_detecciones), sum(n_brutas), sum(n_modis), sum(n_viirs),"
                    f" string_agg(calidades, ','), max(frp_max), sum(frp_sum)"
                    f" from read_parquet('{ruta['celda_dia']}')"
                    " where centroide_lat between ? and ? and centroide_lon between ? and ?"
                    " and fecha_utc between ? and ?" + fc + " group by 1",
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
            inc = incertidumbre(con, bbox, desde, hasta, dias, fc, fd)
            historia = {
                f: int(v) for f, v in con.execute(
                    f"select fecha_utc, sum(n_brutas) from read_parquet('{ruta['celda_dia']}')"
                    " where centroide_lat between ? and ? and centroide_lon between ? and ?" + fc + " group by 1",
                    [s, n, w, e],
                ).fetchall()
            }
            serie, fact, er = serie_area(con, bbox, fd)
            origen_datos = origen(con)
            cobertura = con.execute(
                f"select min(fecha_utc), max(fecha_utc) from read_parquet('{ruta['celda_dia']}')"
            ).fetchone()
        finally:
            con.close()
        cobertura = cobertura if cobertura[0] is not None else None
        for d in dias:
            dia_ = date.fromisoformat(d["fecha_utc"])
            valor, metodo = serie.get(dia_, (0.0, arm.metodo_del_dia(dia_, fact, er)))
            d["celdas_eq"] = round(valor, 2)
            d["metodo"] = metodo
            d["valor"] = d["celdas_eq"] if metrica == "armonizada" else d["n_brutas"]
        if metrica == "armonizada":
            historia = {f_: v for f_, (v, _m) in serie.items()}
        estado_base = linea_base(inc["anios_con_dato"])
        estado_base["metrica"] = "celdas activas equivalentes" if metrica == "armonizada" else "n_brutas"
        periodos = meses_pico = clima = None
        if estado_base["estado"] == "suficiente":
            calc = lb.calcular(historia, percentil=percentil, anios_minimos=minimo, ventana_dias=ventana_dias,
                               cobertura=cobertura)
            for d in dias:
                info = calc.dias.get(date.fromisoformat(d["fecha_utc"]))
                d["umbral"] = None if info is None or info.umbral is None else round(info.umbral, 2)
                d["inusual"] = None if info is None else info.inusual
                d["n_anios_base"] = None if info is None else info.n_anios
            periodos = lb.periodos_inusuales(calc, desde, hasta) if desde else []
            for p_ in periodos:
                m_ = round(float(p_["maximo"]), 2)
                p_["maximo"] = int(m_) if m_.is_integer() else m_
            clima = lb.climatologia_mensual(historia, cobertura=cobertura)
            meses_pico = sorted(clima, key=lambda m: (-clima[m]["media"], m))[:3]
            estado_base["anios_usados"] = inc["anios_con_dato"]
        else:
            for d in dias:
                d.update(umbral=None, inusual=None, n_anios_base=None)
        cuerpo.update({
            "bbox": list(bbox),
            "area": describir_area(info_area),
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
            "desde_solicitado": desde_sol.isoformat() if desde_sol else None,
            "hasta_solicitado": hasta_sol.isoformat() if hasta_sol else None,
            "nota_rango": "El rango se recorta a la cobertura de los datos; fuera de ella no hay observaciones.",
            "calidad": _calidad(calidades_global),
            "preliminar": "NRT" in calidades_global,
            "origen_datos": origen_datos,
            "nota_conteos": (
                "n_detecciones cuenta representantes tras deduplicar (R3); n_brutas, las detecciones "
                "originales. Para comparar con el visor de FIRMS use n_brutas."
            ),
            "dias": dias,
            "armonizacion": describir_armonizacion(metrica, fact, er),
            "incertidumbre": inc,
            "linea_base": estado_base,
            "periodos_inusuales": periodos,
            "climatologia_mensual": None if clima is None else {str(m): v for m, v in clima.items()},
            "meses_pico": meses_pico,
        })
        return cuerpo

    @app.get("/", include_in_schema=False)
    def raiz():
        return RedirectResponse("/ui/")

    @app.middleware("http")
    async def revalidar_interfaz(request, call_next):
        # La interfaz cambia con cada versión: el navegador debe revalidar (ETag) y no
        # reutilizar un app.js o styles.css viejos de su caché.
        respuesta = await call_next(request)
        if request.url.path.startswith("/ui"):
            respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta

    app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

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
        bbox: str | None = Query(None, description="W,S,E,N en grados"),
        desde: date | None = None,
        hasta: date | None = None,
        area: str | None = Query(None, description="huila o mun:<shapeID> (filtro por polígono)"),
        metrica: str = Query("armonizada", description="armonizada (ADR 0011) o n_brutas"),
    ):
        return calendario(bbox, desde, hasta, area, metrica)

    @app.get("/calendario.csv")
    def get_calendario_csv(bbox: str | None = None, desde: date | None = None, hasta: date | None = None,
                           area: str | None = None, metrica: str = "armonizada"):
        cuerpo = calendario(bbox, desde, hasta, area, metrica)
        buf = io.StringIO()
        for linea in (
            cuerpo["cita"], cuerpo["aviso"],
            f"rules_version: {cuerpo['rules_version']} config_fingerprint: {cuerpo['config_fingerprint']}",
            f"calidad: {cuerpo['calidad']}; preliminar: {str(cuerpo['preliminar']).lower()}"
            + (" (contiene datos NRT preliminares)" if cuerpo["preliminar"] else ""),
            f"bbox: {','.join(str(v) for v in cuerpo['bbox'])} desde: {cuerpo['desde']} hasta: {cuerpo['hasta']}",
            f"linea_base: {cuerpo['linea_base']['estado']}",
            f"origen_datos: {cuerpo['origen_datos']}",
            f"area: {cuerpo['area']['nombre'] or 'recuadro'} ({cuerpo['area']['filtro']})",
            f"metrica: {cuerpo['armonizacion']['metrica']} ({cuerpo['armonizacion']['version']}); "
            "valor = celdas activas equivalentes (ADR 0011) o n_brutas",
        ):
            buf.write(f"# {linea}\n")
        campos = ["fecha_utc", "valor", "celdas_eq", "metodo", "n_detecciones", "n_brutas", "n_modis", "n_viirs",
                  "frp_max", "frp_sum", "calidad", "preliminar", "umbral", "inusual"]
        escritor = csv.DictWriter(buf, fieldnames=campos, lineterminator="\n", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(cuerpo["dias"])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8")

    @app.get("/resumen")
    def get_resumen(
        bbox: str | None = None,
        area: str | None = None,
        metrica: str = Query("armonizada", description="armonizada (ADR 0011) o n_brutas"),
    ):
        """H8-04: totales anuales, matriz año × mes, mediana mensual y anomalía del mes reciente."""
        import calendar as _cal
        from statistics import median

        if metrica not in ("armonizada", "n_brutas"):
            raise HTTPException(422, "metrica debe ser 'armonizada' o 'n_brutas'")
        caja, info_area = caja_y_area(bbox, area)
        cuerpo = base()
        w, s, e, n = caja
        con, fc, fd = conectar(info_area, caja)
        try:
            brutas = dict(con.execute(
                f"select fecha_utc, sum(n_brutas) from read_parquet('{ruta['celda_dia']}')"
                " where centroide_lat between ? and ? and centroide_lon between ? and ?" + fc + " group by 1",
                [s, n, w, e],
            ).fetchall())
            serie, fact, er = serie_area(con, caja, fd)
            lo, hi = con.execute(f"select min(fecha_utc), max(fecha_utc) from read_parquet('{ruta['celda_dia']}')").fetchone()
        finally:
            con.close()
        if lo is None:
            raise HTTPException(503, "sin datos procesados")
        valor = {d: v for d, (v, _m) in serie.items()} if metrica == "armonizada" else {d: float(v) for d, v in brutas.items()}
        celdas: dict[tuple[int, int], dict] = {}
        dia = lo
        while dia <= hi:
            k = (dia.year, dia.month)
            c = celdas.setdefault(k, {"anio": dia.year, "mes": dia.month, "valor": 0.0, "n_brutas": 0, "dias": 0})
            c["valor"] += valor.get(dia, 0.0)
            c["n_brutas"] += int(brutas.get(dia, 0))
            c["dias"] += 1
            dia += timedelta(days=1)
        for c in celdas.values():
            c["completo"] = c["dias"] == _cal.monthrange(c["anio"], c["mes"])[1]
            c["valor"] = round(c["valor"], 2)
        matriz = sorted(celdas.values(), key=lambda c: (c["anio"], c["mes"]))
        anios: dict[int, dict] = {}
        for c in matriz:
            a = anios.setdefault(c["anio"], {"anio": c["anio"], "valor": 0.0, "n_brutas": 0, "meses": 0})
            a["valor"] = round(a["valor"] + c["valor"], 2)
            a["n_brutas"] += c["n_brutas"]
            a["meses"] += 1
        for a in anios.values():
            a["completo"] = a["meses"] == 12 and all(c["completo"] for c in matriz if c["anio"] == a["anio"])
        mediana = {}
        for m in range(1, 13):
            vals = [c["valor"] for c in matriz if c["mes"] == m and c["completo"]]
            mediana[str(m)] = {"mediana": round(median(vals), 2) if vals else None, "n_anios": len(vals)}
        ult = matriz[-1]
        if ult["completo"]:
            ref = [c["valor"] for c in matriz if c["mes"] == ult["mes"] and c["completo"] and c["anio"] != ult["anio"]]
            nota = "mes completo frente a la mediana del mismo mes en los otros años"
        else:
            # Mes en curso: se compara con los mismos días (1..n) del mismo mes en los otros años.
            ref = []
            for c in matriz:
                if c["mes"] == ult["mes"] and c["anio"] != ult["anio"] and c["completo"]:
                    ini = date(c["anio"], c["mes"], 1)
                    ref.append(sum(valor.get(ini + timedelta(days=i), 0.0) for i in range(ult["dias"])))
            nota = f"mes en curso ({ult['dias']} días) frente a la mediana de los mismos días en los otros años"
        med = median(ref) if ref else None
        mes_reciente = {
            "anio": ult["anio"], "mes": ult["mes"], "valor": ult["valor"], "completo": ult["completo"],
            "dias": ult["dias"], "mediana": None if med is None else round(med, 2), "n_anios_ref": len(ref),
            "anomalia_pct": None if not med else round(100 * (ult["valor"] - med) / med, 1), "nota": nota,
        }
        cuerpo.update({
            "bbox": list(caja), "area": describir_area(info_area),
            "desde": lo.isoformat(), "hasta": hi.isoformat(),
            "anios": list(anios.values()), "matriz": matriz, "mediana_mensual": mediana,
            "mes_reciente": mes_reciente, "armonizacion": describir_armonizacion(metrica, fact, er),
        })
        return cuerpo

    @app.get("/detecciones.csv")
    def get_detecciones_csv(bbox: str | None = None, desde: date | None = None, hasta: date | None = None,
                            area: str | None = None):
        """H8-01 (O9): focos de la búsqueda, uno por fila, con cita y procedencia."""
        cuerpo = get_detecciones(bbox=bbox, desde=desde, hasta=hasta, limite=LIMITE_DETECCIONES, area=area)
        buf = io.StringIO()
        for linea in (
            cuerpo["cita"], cuerpo["aviso"],
            f"rules_version: {cuerpo['rules_version']} config_fingerprint: {cuerpo['config_fingerprint']}",
            f"area: {cuerpo['area']['nombre'] or 'recuadro'} ({cuerpo['area']['filtro']}); "
            f"bbox: {','.join(str(v) for v in cuerpo['bbox'])} desde: {cuerpo['desde']} hasta: {cuerpo['hasta']}",
            f"origen_datos: {cuerpo['origen_datos']}; truncado: {str(cuerpo['truncado']).lower()}",
            "Cada fila es un foco representante tras deduplicar (R3); preliminar=true si es NRT. "
            "Los focos son detecciones térmicas, no incendios confirmados.",
        ):
            buf.write(f"# {linea}\n")
        campos = ["fecha_hora_utc", "lat", "lon", "sensor", "satelite", "confianza_clase", "confianza_raw",
                  "frp", "calidad", "preliminar", "version", "cell_id", "semilado_nominal_m", "n_fusionados", "record_id"]
        escritor = csv.DictWriter(buf, fieldnames=campos, lineterminator="\n", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(cuerpo["detecciones"])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8")

    @app.get("/detecciones")
    def get_detecciones(
        bbox: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        limite: int = Query(5000, ge=1, le=LIMITE_DETECCIONES),
        area: str | None = None,
    ):
        caja, info_area = caja_y_area(bbox, area)
        cuerpo = base()
        w, s, e, n = caja
        con, fc, fd = conectar(info_area, caja)
        try:
            desde, hasta = rango(con, caja, desde, hasta)
            filas = [] if desde is None or desde > hasta else con.execute(
                f"select record_id, sensor, satelite, fecha_hora_utc at time zone 'UTC', calidad,"
                f" confianza_clase, confianza_raw, lat, lon, frp, cell_id, version, n_fusionados"
                f" from read_parquet('{ruta['detecciones']}')"
                " where lat between ? and ? and lon between ? and ?"
                " and cast(fecha_hora_utc at time zone 'UTC' as date) between ? and ?" + fd +
                " order by fecha_hora_utc, record_id limit ?",
                [s, n, w, e, desde, hasta, limite + 1],
            ).fetchall()
            inc = incertidumbre(con, caja, desde, hasta, None, fc, fd) if desde and desde <= hasta else {}
            origen_datos = origen(con)
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
            "area": describir_area(info_area),
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
            "origen_datos": origen_datos,
            "truncado": len(filas) > limite,
            "detecciones": detecciones,
            "incertidumbre": inc,
        })
        return cuerpo

    @app.get("/global")
    def get_global(
        dias: int = Query(2, ge=1, le=31, description="días que terminan en el último dato (o en «hasta»)"),
        res: float = Query(0.5, description="lado de la celda de agregación en grados: 0.25, 0.5 o 1"),
        hasta: date | None = None,
    ):
        """ADR 0012: focos de todo el conjunto agregados en celdas para el globo 3D, con el
        reparto por país (Natural Earth 1:110m) y la serie diaria. No filtra por área."""
        if res not in RESOLUCIONES_GLOBAL:
            raise HTTPException(422, "res debe ser 0.25, 0.5 o 1")
        det = ruta_g["detecciones"]
        if not det.exists():
            raise HTTPException(503, f"falta detecciones.parquet en {datos_g}; ejecute el pipeline global")
        meta = pq.read_metadata(det).metadata or {}
        fecha = "cast(fecha_hora_utc at time zone 'UTC' as date)"
        con = duckdb.connect()
        try:
            lo, hi = con.execute(f"select min({fecha}), max({fecha}) from read_parquet('{det}')").fetchone()
            ini = fin = None
            filas, serie, cals, sint = [], [], set(), (0, 0)
            if hi is not None:
                fin = min(hasta, hi) if hasta else hi
                ini = max(lo, fin - timedelta(days=dias - 1))
                filas = con.execute(
                    "select floor(lat / ?)::int, floor(lon / ?)::int, count(*), max(frp), sum(frp),"
                    " count(*) filter (where confianza_clase = 'alta'),"
                    " count(*) filter (where sensor = 'VIIRS'),"
                    " max(fecha_hora_utc at time zone 'UTC'), avg(lat), avg(lon)"
                    f" from read_parquet('{det}') where {fecha} between ? and ?"
                    " group by 1, 2 order by 1, 2", [res, res, ini, fin],
                ).fetchall()
                serie = con.execute(
                    f"select {fecha} as f, count(*), count(*) filter (where confianza_clase = 'alta')"
                    f" from read_parquet('{det}') where {fecha} between ? and ? group by f order by f",
                    [ini, fin],
                ).fetchall()
                cals = {c for (c,) in con.execute(
                    f"select distinct calidad from read_parquet('{det}') where {fecha} between ? and ?",
                    [ini, fin]).fetchall()}
                sint = con.execute(
                    "select count(*) filter (where sintetico), count(*) filter (where not sintetico)"
                    f" from read_parquet('{det}')").fetchone()
        finally:
            con.close()
        por_pais: dict[str, dict[str, Any]] = {}
        celdas = []
        for fi, co, n, frp_max, frp_sum, n_alta, n_viirs, ultimo, la, lon_media in filas:
            # El país se decide en el centro de masa redondeado (clave cacheable entre peticiones).
            pais = mundo.pais_de(round(lon_media, 2), round(la, 2))
            iso, nombre = pais or ("", "Fuera de país (mar o costa)")
            p = por_pais.setdefault(iso, {"iso_a3": iso or None, "nombre": nombre, "n": 0, "n_alta": 0,
                                          "frp_max": 0.0, "celdas": 0})
            p["n"] += n
            p["n_alta"] += n_alta
            p["celdas"] += 1
            p["frp_max"] = round(max(p["frp_max"], frp_max or 0.0), 1)
            celdas.append([round(la, 3), round(lon_media, 3), n, None if frp_max is None else round(frp_max, 1),
                           round(frp_sum or 0.0, 1), n_alta, n_viirs, ultimo.strftime("%Y-%m-%dT%H:%MZ"), iso])
        ranking = sorted(por_pais.values(), key=lambda x: (-x["n"], x["nombre"]))
        n_sint, n_real = sint
        return {
            "rules_version": meta.get(b"rules_version", b"").decode(),
            "config_fingerprint": meta.get(b"config_fingerprint", b"").decode(),
            "cita": CITA,
            "aviso": AVISO,
            "origen_datos": "mixto" if n_sint and n_real else "sintetico" if n_sint else "real" if n_real else None,
            "calidad": _calidad(cals),
            "preliminar": "NRT" in cals,
            "desde": ini.isoformat() if ini else None,
            "hasta": fin.isoformat() if fin else None,
            "cobertura": {"desde": lo.isoformat() if lo else None, "hasta": hi.isoformat() if hi else None},
            "res_grados": res,
            "total_detecciones": sum(c[2] for c in celdas),
            "total_alta": sum(c[5] for c in celdas),
            "n_paises": sum(1 for p in por_pais.values() if p["iso_a3"]),
            "campos_celda": ["lat", "lon", "n", "frp_max", "frp_sum", "n_alta", "n_viirs", "ultimo_utc", "iso_a3"],
            "celdas": celdas,
            "paises": ranking[:25],
            "serie_diaria": [{"fecha_utc": f.isoformat(), "n": n, "n_alta": a} for f, n, a in serie],
            "fuente_paises": mundo.FUENTE,
            "nota": ("Detecciones tras quitar duplicados entre satélites, agregadas en celdas de "
                     f"{res}°; posición = centro de masa de los focos de la celda. País según Natural Earth "
                     "1:110m: cerca de costas y fronteras puede asignarse al vecino."),
        }

    return app
