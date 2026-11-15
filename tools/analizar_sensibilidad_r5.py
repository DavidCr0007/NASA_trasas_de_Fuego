"""Experimento SINTÉTICO del P95: ilustra sensibilidad, no estima precisión científica."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from harmonize.linea_base import calcular


def experimento():
    objetivo=date(2026,8,15)
    serie={date(a,8,16):10 for a in range(2020,2026)}
    serie[objetivo]=1
    casos=[]
    for ventana in (0,7):
        d=calcular(serie,cobertura=(date(2020,1,1),date(2026,12,31)),anios_minimos=5,ventana_dias=ventana).dias[objetivo]
        casos.append({"caso":"seis años con un pico al día siguiente", "ventana_dias":ventana,
                      "valor":d.valor,"umbral":d.umbral,"n_anios_referencia":d.n_anios,"inusual":d.inusual})
    for inicio in (2020,2023):
        d=calcular({objetivo:1},cobertura=(date(inicio,1,1),date(2026,12,31)),anios_minimos=5,ventana_dias=7).dias[objetivo]
        casos.append({"caso":"referencia rellenada con ceros", "inicio":inicio,"valor":d.valor,
                      "umbral":d.umbral,"n_anios_referencia":d.n_anios,"inusual":d.inusual})
    return {"naturaleza":"Experimento sintético; no son observaciones FIRMS ni una medición de exactitud", "objetivo":objetivo.isoformat(),
            "configuracion":{"percentil":95,"minimo_anios":5,"excluye_anio_objetivo":True},"casos":casos,
            "limite":"Los ceros se derivan de la cobertura declarada; no verifican pasadas válidas. No se estima tasa de falsos positivos sin referencia independiente."}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--salida",type=Path,required=True);a=p.parse_args()
    a.salida.parent.mkdir(parents=True,exist_ok=True)
    a.salida.write_text(json.dumps(experimento(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(a.salida)
