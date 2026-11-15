"""Auditoría repetible de endpoints y artefactos, sin modificar datos ni desplegar.

Ejemplo: uv run python tools/auditar_plataforma.py --url https://sitio/ui/ --salida informe.json
Local sin servidor: --datos data/processed/global_nrt [--crudos data/raw/global].
Los fallos quedan en JSON; el código de salida 1 significa que hay criterios no conformes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))


def auditar(obtener, datos: Path | None = None, crudos: Path | None = None):
    pruebas, resumen = [], {}
    def comprobar(codigo, ok, detalle):
        pruebas.append({"criterio": codigo, "estado": "conforme" if ok else "no_conforme", "evidencia": detalle})
    def leer(ruta, parametros=None, json_=True):
        estado, texto = obtener(ruta + ("?"+urlencode(parametros) if parametros else ""))
        return estado, json.loads(texto) if json_ and estado == 200 else texto
    def filas_csv(texto):
        return list(csv.DictReader(io.StringIO("\n".join(l for l in texto.splitlines() if not l.startswith("#")))))
    s, salud = leer("/salud")
    comprobar("API disponible", s == 200, {"http": s, "rules_version": salud.get("rules_version") if isinstance(salud,dict) else None})
    s, global_ = leer("/global", {"dias": 31})
    if s != 200:
        comprobar("Globo disponible", False, {"http": s}); return {"pruebas": pruebas}
    fin = date.fromisoformat(global_["hasta"])
    params = {"area": "huila", "desde": (fin-timedelta(days=30)).isoformat(), "hasta": fin.isoformat()}
    sc, cal = leer("/calendario", params)
    sd, det = leer("/detecciones", {**params, "limite": 50000})
    comprobar("Calendario y detecciones disponibles", sc == sd == 200, {"calendario":sc, "detecciones":sd})
    if sc != 200 or sd != 200: return {"pruebas":pruebas}
    resumen.update(origen_analisis=cal["origen_datos"], origen_global=global_["origen_datos"],
                   periodo={"desde": cal["desde"], "hasta": cal["hasta"]},
                   metrica=cal["armonizacion"]["metrica"], metodos=sorted({d["metodo"] for d in cal["dias"]}),
                   detecciones=len(det["detecciones"]), truncado=det["truncado"])
    comprobar("Origen explícito de ambos conjuntos", all(o in ("real","sintetico","mixto") for o in (cal["origen_datos"],global_["origen_datos"])), resumen)
    comprobar("Globo conserva sus sumas", global_["total_detecciones"] == sum(c[2] for c in global_["celdas"]) == sum(d["n"] for d in global_["serie_diaria"]), {"total":global_["total_detecciones"]})
    comprobar("Rango UTC de detecciones", all(params["desde"]<=d["fecha_hora_utc"][:10]<=params["hasta"] for d in det["detecciones"]), resumen["periodo"])
    for ruta, cuerpo, clave in (("/calendario.csv",cal,"dias"),("/detecciones.csv",det,"detecciones")):
        s, texto = leer(ruta,params,json_=False)
        filas = filas_csv(texto) if s==200 else []
        if clave=="dias":
            esperado = {d["fecha_utc"]: (float(d["valor"]),int(d["n_detecciones"]),int(d["n_brutas"])) for d in cuerpo[clave]}
            recibido = {d["fecha_utc"]: (float(d["valor"]),int(d["n_detecciones"]),int(d["n_brutas"])) for d in filas}
        else:
            esperado = {d["record_id"]:(d["fecha_hora_utc"],float(d["lat"]),float(d["lon"]),d["frp"]) for d in cuerpo[clave]}
            recibido = {d["record_id"]:(d["fecha_hora_utc"],float(d["lat"]),float(d["lon"]),float(d["frp"]) if d["frp"] else None) for d in filas}
        comprobar("CSV reproduce JSON "+ruta, s==200 and recibido==esperado, {"http":s,"filas":len(filas)})
        comprobar("CSV declara naturaleza y versión "+ruta, f"origen_datos: {cal['origen_datos']}" in texto and cal["rules_version"] in texto, {"origen":cal["origen_datos"]})
    por_dia = Counter(d["fecha_hora_utc"][:10] for d in det["detecciones"])
    diferencias = [{"fecha":d["fecha_utc"],"calendario":d["n_detecciones"],"mapa":por_dia[d["fecha_utc"]]} for d in cal["dias"] if d["n_detecciones"]!=por_dia[d["fecha_utc"]]]
    comprobar("Representantes del área coinciden por día", not det["truncado"] and not diferencias, {"diferencias":diferencias,"nota":"No se compara valor armonizado con número de puntos. Un efecto de borde requiere revisar la definición espacial."})
    campos = ("fuente","archivo_origen","sha256_origen","fila","fecha_descarga","sintetico","rules_version","dataset_id")
    faltantes = sorted({c for d in det["detecciones"] for c in campos if d.get(c) is None})
    comprobar("Linaje de detecciones público", bool(det["detecciones"]) and not faltantes, {"campos_ausentes":faltantes})
    sp, p = leer("/procedencia")
    comprobar("Linaje de los datasets público", sp==200, {"http":sp,"dataset_id":p.get("analisis",{}).get("dataset_id") if isinstance(p,dict) else None})
    if sp==200:
        a=p["analisis"];declaradas={(e["archivo"],e["sha256"]) for e in a["archivos_entrada_declarados"]}
        fuera=[f["archivo"] for f in a["fuentes"] if (f["archivo"],f["sha256"]) not in declaradas]
        comprobar("Todos los registros tienen vínculo al manifiesto", a["registros_sin_linaje"]==0 and not fuera,
                  {"registros":a["registros"],"sin_linaje":a["registros_sin_linaje"],"fuentes_fuera_del_manifiesto":fuera})
    for ruta in ("/metodologia","/limitaciones"):
        s, texto=leer(ruta,json_=False)
        comprobar("Documento público "+ruta,s==200 and len(texto)>500,{"http":s})
    s, vacio=leer("/detecciones",{"bbox":"10,10,10.001,10.001","desde":"1900-01-01","hasta":"1900-01-02"})
    comprobar("Fuera de cobertura no inventa observaciones",s==200 and vacio.get("detecciones")==[],{"http":s,"registros":len(vacio.get("detecciones",[])) if isinstance(vacio,dict) else None})
    if datos:
        r=json.loads((datos/"resumen.json").read_text(encoding="utf-8"))
        hashes={n:hashlib.sha256((datos/n).read_bytes()).hexdigest()==h for n,h in r["parquet_sha256"].items()}
        comprobar("Hashes de Parquet verificados",all(hashes.values()),hashes)
        c=r["conteos"]
        comprobar("Conservación de registros",c["n_input"]==c["aceptados"]+c["deduplicados"]+c["cuarentena"],c)
        if crudos:
            hashes_entrada={e["archivo"]:(crudos/e["archivo"]).exists() and hashlib.sha256((crudos/e["archivo"]).read_bytes()).hexdigest()==e["sha256"] for e in r["archivos_entrada"]}
            comprobar("Hashes de entradas verificados",all(hashes_entrada.values()),hashes_entrada)
    return {"resumen":resumen,"pruebas":pruebas}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    grupo=parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--url");grupo.add_argument("--datos",type=Path)
    parser.add_argument("--crudos",type=Path);parser.add_argument("--salida",type=Path,required=True)
    a=parser.parse_args(argv)
    if a.url:
        base=a.url.removesuffix("/").removesuffix("/ui")
        def obtener(ruta):
            try:
                with urlopen(Request(base+ruta,headers={"User-Agent":"HarmonizedHeat-Auditoria/1.0"}),timeout=45) as r:
                    return r.status,r.read().decode("utf-8")
            except HTTPError as e: return e.code,e.read().decode("utf-8")
    else:
        from fastapi.testclient import TestClient
        from api.app import create_app
        cliente=TestClient(create_app(a.datos))
        def obtener(ruta):
            r=cliente.get(ruta);return r.status_code,r.text
    informe={"capturado_utc":datetime.now(timezone.utc).isoformat(),"objetivo":a.url or str(a.datos),**auditar(obtener,a.datos,a.crudos)}
    a.salida.parent.mkdir(parents=True,exist_ok=True)
    a.salida.write_text(json.dumps(informe,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pruebas=informe["pruebas"];correctas=sum(p["estado"]=="conforme" for p in pruebas)
    print(f"{correctas}/{len(pruebas)} criterios conformes. Evidencia: {a.salida}")
    for p in pruebas:
        if p["estado"]!="conforme": print("NO CONFORME:",p["criterio"],json.dumps(p["evidencia"],ensure_ascii=False))
    return int(correctas!=len(pruebas))


if __name__=="__main__": raise SystemExit(main())
