"""Índice ligero de países y territorios, incluidos microestados, para pedir límites.

Las geometrías mostradas se obtienen de geoBoundaries. Natural Earth 1:10m se
usa únicamente para localizar los países visibles y como metadato de cobertura.
"""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

RAIZ = Path(__file__).resolve().parents[1]
URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_countries.geojson"


def preparar():
    crudo = RAIZ / "data/raw/natural_earth/indice_10m_v5.1.2.geojson"
    if not crudo.exists():
        with urlopen(URL, timeout=60) as r:
            contenido = r.read()
        json.loads(contenido)
        crudo.parent.mkdir(parents=True, exist_ok=True)
        with crudo.open("xb") as f:
            f.write(contenido)
    contenido = crudo.read_bytes()
    paises = {}
    def puntos(c):
        if isinstance(c[0], (int, float)):
            yield c
        else:
            for parte in c:
                yield from puntos(parte)
    for f in json.loads(contenido)["features"]:
        p = f["properties"]
        iso = next((p.get(k) for k in ("ISO_A3", "ISO_A3_EH", "ADM0_A3") if p.get(k) not in (None, "-99")), None)
        if not iso or len(iso) != 3:
            continue
        coords = list(puntos(f["geometry"]["coordinates"]))
        xs, ys = [c[0] for c in coords], [c[1] for c in coords]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
        paises[iso] = {"iso": iso, "nombre": p.get("NAME_ES") or p["NAME"], "bbox": bbox}
    salida = {"fuente": "Natural Earth v5.1.2 Admin 0 1:10m (dominio público); índice, no límites mostrados",
              "url": URL, "sha256": hashlib.sha256(contenido).hexdigest(), "paises": sorted(paises.values(), key=lambda p: p["iso"])}
    destino = RAIZ / "src/ui/static/datos/indice_limites.json"
    destino.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"Índice: {len(paises)} países y territorios; {destino.stat().st_size} bytes")


if __name__ == "__main__":
    preparar()
