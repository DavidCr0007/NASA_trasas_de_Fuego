"""Genera datos de muestra SINTÉTICOS (no son observaciones reales).

Determinista: sin aleatoriedad. Imita la cabecera confirmada de ``firms_schema``
(CSV reales 2026-11-13). Uso: ``uv run python tools/generar_muestra.py [destino]``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from ingest import firms_schema as fs  # noqa: E402
from ingest.manifest import append_entry, build_entry  # noqa: E402

FECHA_DESCARGA = "2026-11-13T00:00:00Z"
FECHA_INICIO, FECHA_FIN = "2026-11-10", "2026-11-12"
LAT0, LON0 = 2.93, -75.28  # Neiva

# fuente -> (índice de banda latitudinal, códigos de satélite, version, filas base)
FUENTES = {
    "MODIS_NRT": (0, ("T", "A"), "6.1NRT", 24),
    "MODIS_SP": (1, ("T", "A"), "6.1", 22),
    "VIIRS_SNPP_SP": (2, ("N",), "2.0", 24),
    "VIIRS_NOAA20_NRT": (3, ("N20",), "2.0NRT", 24),
    "VIIRS_NOAA21_NRT": (4, ("N21",), "2.0NRT", 24),
}
# Versiones de muestra: patrones confirmados con la tabla oficial y CSV reales (2026-11-13).

LON_CASOS = -75.285  # centro de una celda de 0.01° (~1 km)


def _cabecera(sensor: str) -> list[str]:
    return list(fs.COLUMNAS_REQUERIDAS[(sensor, "api_nrt")])


def _fila(fuente: str, *, lat, lon, fecha, hora, sat, conf, brillo="330.5",
          frp="10.0", daynight=None, scan="1.0", track="1.0", brillo2="295.0") -> list[str]:
    sensor = fs.FUENTES_API[fuente]["sensor"]
    version = FUENTES[fuente][2]
    if daynight is None:
        h = int(str(hora).zfill(4)[:2]) if str(hora).isdigit() else 0
        daynight = "D" if 11 <= h < 23 else "N"
    valores = {
        "latitude": lat if isinstance(lat, str) else f"{lat:.5f}",
        "longitude": lon if isinstance(lon, str) else f"{lon:.5f}",
        "scan": scan, "track": track, "acq_date": fecha, "acq_time": str(hora),
        "satellite": sat, "confidence": str(conf),
        "version": version, "frp": frp, "daynight": daynight,
    }
    if sensor == "MODIS":
        valores.update(brightness=brillo, bright_t31=brillo2)
    else:
        valores.update(bright_ti4=brillo, bright_ti5=brillo2)
    return [valores[c] for c in _cabecera(sensor)]


def _base(fuente: str) -> list[list[str]]:
    k, sats, _, n = FUENTES[fuente]
    sensor = fs.FUENTES_API[fuente]["sensor"]
    lat0 = LAT0 + (k - 2) * 0.12
    filas = []
    for i in range(n):
        minutos = (i * 137) % 1440
        hhmm = (minutos // 60) * 100 + minutos % 60
        hora = str(hhmm) if i in (3, 11) else f"{hhmm:04d}"  # sin ceros a la izquierda
        conf = 30 + (i * 7) % 70 if sensor == "MODIS" else ("low", "nominal", "high")[i % 3]
        filas.append(_fila(
            fuente,
            lat=lat0 + (i // 6) * 0.02 + 0.004,
            lon=LON0 - 0.06 + (i % 6) * 0.02 + 0.004,
            fecha=f"2026-11-{10 + i % 3}", hora=hora, sat=sats[i % len(sats)],
            conf=conf, brillo=f"{300.0 + (i * 3) % 60:.1f}",
            frp=f"{1 + (i * 13) % 400 / 10:.1f}", scan=f"{1.0 + (i % 4) * 0.1:.1f}",
            track=f"{1.0 + (i % 3) * 0.1:.1f}", brillo2=f"{285.0 + (i * 5) % 30:.1f}",
        ))
    return filas


def _casos() -> dict[str, list[list[str]]]:
    """Casos límite. Las celdas son de 0.01° y las latitudes caen en su centro."""
    c = LON_CASOS
    modis_c3 = dict(lat=2.565, lon=c, fecha="2026-11-11", hora="1840", sat="A",
                    conf=72, brillo="341.2", frp="25.4", scan="1.2", track="1.1",
                    brillo2="301.7")
    return {
        "MODIS_NRT": [
            # C1: MODIS+VIIRS misma celda, delta 85 min (dedup, se conserva VIIRS)
            _fila("MODIS_NRT", lat=2.505, lon=c, fecha="2026-11-10", hora="1705",
                  sat="T", conf=85),
            # C2: misma celda, delta 6 h 50 min (no dedup)
            _fila("MODIS_NRT", lat=2.535, lon=c, fecha="2026-11-10", hora="635",
                  sat="T", conf=60),
            # C3: misma detección en NRT y SP
            _fila("MODIS_NRT", **modis_c3),
            # C5: cruce de medianoche UTC con VIIRS_NOAA20_NRT, delta 30 min (dedup)
            _fila("MODIS_NRT", lat=2.625, lon=c, fecha="2026-11-10", hora="2350",
                  sat="A", conf=90),
            # C6: latitud fuera de rango
            _fila("MODIS_NRT", lat="95.00000", lon=c, fecha="2026-11-11", hora="1000",
                  sat="T", conf=80),
            # C9: código de satélite inexistente
            _fila("MODIS_NRT", lat=2.445, lon=c, fecha="2026-11-11", hora="1010",
                  sat="ZZ", conf=80),
        ],
        "MODIS_SP": [
            _fila("MODIS_SP", **modis_c3),  # C3 (misma detección que en MODIS_NRT)
            # C8a: confianza MODIS fuera de dominio
            _fila("MODIS_SP", lat=2.475, lon=c, fecha="2026-11-11", hora="1200",
                  sat="T", conf=150),
        ],
        "VIIRS_SNPP_SP": [
            # C7: fecha malformada
            _fila("VIIRS_SNPP_SP", lat=2.415, lon=c, fecha="2026-13-45", hora="1300",
                  sat="N", conf="nominal"),
        ],
        "VIIRS_NOAA20_NRT": [
            # C1: VIIRS de la pareja con MODIS_NRT
            _fila("VIIRS_NOAA20_NRT", lat=2.505, lon=c, fecha="2026-11-10", hora="1830",
                  sat="N20", conf="nominal"),
            # C5: acq_time sin ceros ("20" = 00:20 UTC del día siguiente)
            _fila("VIIRS_NOAA20_NRT", lat=2.625, lon=c, fecha="2026-11-11", hora="20",
                  sat="N20", conf="high"),
            # C10: satélite de otra fuente (Suomi NPP dentro de NOAA-20)
            _fila("VIIRS_NOAA20_NRT", lat=2.385, lon=c, fecha="2026-11-11", hora="1500",
                  sat="N", conf="nominal"),
        ],
        "VIIRS_NOAA21_NRT": [
            # C2: VIIRS de la pareja a más de 3 h
            _fila("VIIRS_NOAA21_NRT", lat=2.535, lon=c, fecha="2026-11-10", hora="1325",
                  sat="N21", conf="high"),
            # C8b: confianza VIIRS fuera de dominio
            _fila("VIIRS_NOAA21_NRT", lat=2.355, lon=c, fecha="2026-11-11", hora="1600",
                  sat="N21", conf="x"),
        ],
    }


def generar(destino: str | Path) -> list[Path]:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    manifiesto = destino / "manifest.jsonl"
    manifiesto.unlink(missing_ok=True)
    casos = _casos()
    escritos = []
    for fuente in FUENTES:
        meta = fs.FUENTES_API[fuente]
        ruta = destino / f"SINTETICO_{fuente}_huila.csv"
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(_cabecera(meta["sensor"]))
            w.writerows(_base(fuente) + casos.get(fuente, []))
        append_entry(manifiesto, build_entry(
            ruta, destino, fuente=fuente, sensor=meta["sensor"], calidad=meta["calidad"],
            coleccion=meta["coleccion"], fecha_descarga=FECHA_DESCARGA,
            url_sin_clave=None, bbox=list(fs.HUILA_BBOX), fecha_inicio=FECHA_INICIO,
            fecha_fin=FECHA_FIN, sintetico=True,
        ))
        escritos.append(ruta)
    return escritos


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    generar(Path(args[0]) if args else RAIZ / "data" / "sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
