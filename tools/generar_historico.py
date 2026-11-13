"""Genera una muestra histórica SINTÉTICA (2020-2026) para el Huila.

NO son observaciones reales. El patrón estacional y la anomalía son inventados
para probar la línea base (R5) y la interfaz sin red. Determinista: usa un
generador pseudoaleatorio con semilla fija por fecha.

Uso: ``uv run python tools/generar_historico.py [destino]``
(por defecto ``data/sample_historica``, excluida de git).
"""

from __future__ import annotations

import csv
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from ingest import firms_schema as fs  # noqa: E402
from ingest.manifest import append_entry, build_entry  # noqa: E402

INICIO, FIN = date(2020, 1, 1), date(2026, 11, 12)
FECHA_DESCARGA = "2026-11-13T00:00:00Z"
ANOMALIA = (date(2026, 8, 10), date(2026, 8, 16))  # tasa x5 (inventada)
MES_PICO_PRINCIPAL = 8
SEMILLA = 20261113

# fuente -> (satélites, version, primer día, último día). Estándar hasta 2025, NRT en 2026.
FUENTES = {
    "MODIS_SP": (("T", "A"), "6.1", INICIO, date(2025, 12, 31)),
    "MODIS_NRT": (("T", "A"), "6.1NRT", date(2026, 1, 1), FIN),
    "VIIRS_SNPP_SP": (("N",), "2.0", INICIO, date(2025, 12, 31)),
    "VIIRS_NOAA20_SP": (("N20",), "2.0", INICIO, date(2025, 12, 31)),
    "VIIRS_NOAA20_NRT": (("N20",), "2.0NRT", date(2026, 1, 1), FIN),
    "VIIRS_NOAA21_NRT": (("N21",), "2.0NRT", date(2026, 1, 1), FIN),
}
# Hora UTC aproximada de pasada (minutos) por satélite: inventada, solo para la muestra.
PASADA_UTC = {"T": 15 * 60 + 30, "A": 18 * 60 + 30, "N": 18 * 60 + 40, "N20": 17 * 60 + 50, "N21": 18 * 60 + 15}
PROB_DETECCION = {"MODIS": 0.45, "VIIRS": 0.75}

_rnd_sitios = random.Random(SEMILLA)
W, S, E, N = -76.3, 1.7, -74.6, 3.6  # dentro del bbox aproximado del Huila
SITIOS = [(round(_rnd_sitios.uniform(S, N), 4), round(_rnd_sitios.uniform(W, E), 4)) for _ in range(40)]


def _tasa(d: date) -> float:
    """Focos esperados por día: dos temporadas inventadas (agosto y febrero)."""
    doy = d.timetuple().tm_yday

    def bump(centro: int, ancho: float) -> float:
        dist = min(abs(doy - centro), 365 - abs(doy - centro))
        return math.exp(-0.5 * (dist / ancho) ** 2)

    tasa = 0.15 + 2.2 * bump(225, 22) + 0.9 * bump(45, 18)
    if ANOMALIA[0] <= d <= ANOMALIA[1]:
        tasa *= 5
    return tasa


def _poisson(rnd: random.Random, lam: float) -> int:
    limite, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= limite:
            return k
        k += 1


def _cabecera(sensor: str) -> list[str]:
    return list(fs.COLUMNAS_REQUERIDAS[(sensor, "24h")])


def _filas_por_fuente() -> dict[str, list[list[str]]]:
    filas: dict[str, list[list[str]]] = {f: [] for f in FUENTES}
    d = INICIO
    while d <= FIN:
        rnd = random.Random(f"{SEMILLA}-{d.isoformat()}")
        for _ in range(_poisson(rnd, _tasa(d))):
            lat0, lon0 = SITIOS[rnd.randrange(len(SITIOS))]
            for fuente, (sats, version, f_ini, f_fin) in FUENTES.items():
                if not f_ini <= d <= f_fin:
                    continue
                sensor = fs.FUENTES_API[fuente]["sensor"]
                for sat in sats:
                    if rnd.random() > PROB_DETECCION[sensor]:
                        continue
                    pixeles = 1 if sensor == "MODIS" else 1 + rnd.randrange(3)
                    minutos = PASADA_UTC[sat] + rnd.randint(-40, 40)
                    hhmm = f"{minutos // 60:02d}{minutos % 60:02d}"
                    for _p in range(pixeles):
                        lat = lat0 + rnd.uniform(-0.004, 0.004)
                        lon = lon0 + rnd.uniform(-0.004, 0.004)
                        frp = f"{rnd.uniform(1, 60):.2f}"
                        if sensor == "MODIS":
                            conf = str(rnd.randint(20, 100))
                            brillo = f"{rnd.uniform(305, 345):.2f}"
                            brillo2 = f"{rnd.uniform(288, 300):.2f}"
                            extra = {"brightness": brillo, "bright_t31": brillo2,
                                     "scan": "1.1", "track": "1.0"}
                        else:
                            conf = rnd.choices(["low", "nominal", "high"], weights=[1, 8, 1])[0]
                            extra = {"bright_ti4": f"{rnd.uniform(310, 367):.2f}",
                                     "bright_ti5": f"{rnd.uniform(288, 300):.2f}",
                                     "scan": "0.45", "track": "0.40"}
                        valores = {
                            "latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}",
                            "acq_date": d.isoformat(), "acq_time": hhmm, "satellite": sat,
                            "confidence": conf, "version": version, "frp": frp,
                            "daynight": "D", **extra,
                        }
                        filas[fuente].append([valores[c] for c in _cabecera(sensor)])
        d += timedelta(days=1)
    return filas


def generar(destino: str | Path) -> list[Path]:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    manifiesto = destino / "manifest.jsonl"
    manifiesto.unlink(missing_ok=True)
    escritos = []
    for fuente, filas in _filas_por_fuente().items():
        meta = fs.FUENTES_API[fuente]
        _, _, f_ini, f_fin = FUENTES[fuente]
        ruta = destino / f"SINTETICO_HIST_{fuente}_huila.csv"
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(_cabecera(meta["sensor"]))
            w.writerows(filas)
        append_entry(manifiesto, build_entry(
            ruta, destino, fuente=fuente, sensor=meta["sensor"], calidad=meta["calidad"],
            coleccion=meta["coleccion"], fecha_descarga=FECHA_DESCARGA, url_sin_clave=None,
            bbox=list(fs.HUILA_BBOX), fecha_inicio=f_ini.isoformat(), fecha_fin=f_fin.isoformat(),
            sintetico=True,
        ))
        escritos.append(ruta)
    return escritos


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    destino = Path(args[0]) if args else RAIZ / "data" / "sample_historica"
    rutas = generar(destino)
    print(f"Muestra histórica SINTÉTICA en {destino}: {len(rutas)} archivos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
