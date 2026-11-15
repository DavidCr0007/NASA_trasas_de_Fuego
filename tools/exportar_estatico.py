"""Demo estática para GitHub Pages (ADR 0015).

Pages solo sirve archivos: no hay API de Python. Este script levanta la MISMA API en proceso
(``TestClient``), guarda sus respuestas exactas como JSON y copia la interfaz. En la página
publicada, ``estatico.js`` intercepta ``fetch`` y responde desde esos archivos. Así no se
duplica la lógica de armonización, línea base ni calendario en el navegador.

Qué se precalcula (área del análisis = Huila o cada uno de sus 37 municipios):
  - /calendario inicial y de cada año con datos; /resumen.
  - /global para 1, 2 y 7 días con resolución 0,25°, 0,5° y 1°.
  - todas las detecciones en un archivo por columnas (el navegador filtra por área, recuadro
    y fechas, y deriva los periodos parciales del calendario).
  - /calendario.csv y /detecciones.csv del Huila por año.
Lo que necesita servidor (búsqueda en internet, áreas dibujadas o por coordenadas, límites fuera
del Huila) responde con un aviso claro.

Uso: ``uv run python tools/exportar_estatico.py --datos data/processed/demo_historica --salida _site``
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from api.app import LIMITE_DETECCIONES, create_app  # noqa: E402

ESTATICOS = RAIZ / "src" / "ui" / "static"
DIAS_GLOBAL = (1, 2, 7)
RES_GLOBAL = (0.25, 0.5, 1)
CAMPOS_DETECCION = ["record_id", "sensor", "satelite", "fecha_hora_utc", "calidad", "confianza_clase", "confianza_raw",
                    "lat", "lon", "frp", "cell_id", "version", "n_fusionados", "brillo", "semilado_nominal_m", "preliminar"]


def slug(area: str) -> str:
    """«mun:COL-ADM2-…» → «mun-COL-ADM2-…»: nombre de archivo seguro y reversible en estatico.js."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", area)


def _escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = datos if isinstance(datos, str) else json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    ruta.write_text(texto, encoding="utf-8")


def _pedir(cliente: TestClient, ruta: str, **params):
    r = cliente.get(ruta, params=params)
    if r.status_code != 200:
        raise RuntimeError(f"{ruta} {params}: HTTP {r.status_code} {r.text[:200]}")
    return r


def exportar(datos: Path, salida: Path, anios_minimos: int | None = None) -> dict:
    cliente = TestClient(create_app(datos, anios_minimos=anios_minimos))
    if salida.exists():
        shutil.rmtree(salida)
    shutil.copytree(ESTATICOS, salida)
    api = salida / "api"

    municipios = json.loads((ESTATICOS / "datos" / "huila_municipios.geojson").read_text(encoding="utf-8"))["features"]
    areas = ["huila"] + [f"mun:{m['properties']['shapeID']}" for m in municipios]
    inicial = _pedir(cliente, "/calendario", area="huila").json()
    anios = inicial["incertidumbre"]["anios_con_dato"]
    archivos = 0
    # El calendario sin fechas (toda la serie, ~620 kB) solo lo pide la carga inicial del Huila;
    # para un municipio, estatico.js usa el del último año (trae los mismos años con dato).
    _escribir(api / "calendario" / "huila" / "inicial.json", inicial)
    for area in areas:
        s = slug(area)
        _escribir(api / "resumen" / f"{s}.json", _pedir(cliente, "/resumen", area=area).json())
        for anio in anios:
            _escribir(api / "calendario" / s / f"{anio}.json",
                      _pedir(cliente, "/calendario", area=area, desde=f"{anio}-01-01", hasta=f"{anio}-12-31").json())
        archivos += 1 + len(anios)
    archivos += 1
    for anio in anios:
        rango = {"area": "huila", "desde": f"{anio}-01-01", "hasta": f"{anio}-12-31"}
        _escribir(api / "csv" / f"calendario_huila_{anio}.csv", _pedir(cliente, "/calendario.csv", **rango).text)
        _escribir(api / "csv" / f"detecciones_huila_{anio}.csv", _pedir(cliente, "/detecciones.csv", **rango).text)
        archivos += 2
    for dias in DIAS_GLOBAL:
        for res in RES_GLOBAL:
            _escribir(api / "global" / f"{dias}_{res}.json", _pedir(cliente, "/global", dias=dias, res=res).json())
            archivos += 1

    todo = _pedir(cliente, "/detecciones", bbox="-180,-90,180,90", limite=LIMITE_DETECCIONES).json()
    if todo["truncado"]:
        raise RuntimeError(f"más de {LIMITE_DETECCIONES} detecciones: la demo estática no las cubre todas")
    columnas = {
        "base": {k: todo[k] for k in ("rules_version", "config_fingerprint", "cita", "aviso")},
        "origen_datos": todo["origen_datos"],
        "desde": todo["desde"], "hasta": todo["hasta"],
        "grilla_deg": todo["incertidumbre"].get("grilla_deg"),
        "campos": CAMPOS_DETECCION,
        "filas": [[d.get(c) for c in CAMPOS_DETECCION] for d in todo["detecciones"]],
    }
    _escribir(api / "detecciones.json", columnas)
    indice = {"anios": anios, "areas": [slug(a) for a in areas], "dias_global": DIAS_GLOBAL, "res_global": RES_GLOBAL,
              "csv": [f"{t}_huila_{a}" for a in anios for t in ("calendario", "detecciones")],
              "detecciones": len(columnas["filas"])}
    _escribir(api / "indice.json", indice)

    # La interfaz carga estatico.js antes que cualquier otro script (incluido MapLibre).
    html = (salida / "index.html").read_text(encoding="utf-8")
    marca = '  <script src="vendor/maplibre/maplibre-gl.js"></script>'
    assert html.count(marca) == 1, "index.html cambió: no se encontró dónde insertar estatico.js"
    html = html.replace(marca, '  <script src="estatico.js"></script>\n' + marca)
    (salida / "index.html").write_text(html, encoding="utf-8")
    (salida / ".nojekyll").write_text("", encoding="utf-8")  # sin Jekyll: se publican los archivos tal cual
    indice["archivos"] = archivos + 2
    return indice


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--datos", type=Path, default=RAIZ / "data" / "processed" / "demo_historica")
    p.add_argument("--salida", type=Path, default=RAIZ / "_site")
    p.add_argument("--anios-minimos", type=int, default=None)
    a = p.parse_args(argv)
    indice = exportar(a.datos, a.salida, a.anios_minimos)
    print(f"Demo estática en {a.salida}: {indice['archivos']} respuestas, {indice['detecciones']} detecciones, "
          f"años {indice['anios'][0]}–{indice['anios'][-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
