"""Cobertura mundial real y ausencia de recortes por país en la preparación."""
import importlib.util
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_respaldo_contiene_rios_en_todos_los_continentes_habitados():
    geo = json.loads((RAIZ / "src/ui/static/datos/hidrografia_mundial.geojson").read_text(encoding="utf-8"))
    rios = {f["properties"]["nombre"] for f in geo["features"] if f["properties"]["tipo"] == "rio"}
    assert {"Amazonas", "Magdalena", "Mississippi", "Nile", "Danube", "Yangtze", "Murray"} <= rios
    assert geo["metadatos"]["licencia"] == "Dominio público"
    assert "recorte" not in geo["metadatos"]
    assert len(geo["metadatos"]["sha256_origen"]) == 2
    assert len(geo["features"]) == 2810


def test_preparacion_conserva_geometrias_fuera_de_colombia_y_su_zoom(tmp_path):
    spec = importlib.util.spec_from_file_location("hidrografia", RAIZ / "tools/preparar_hidrografia.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    rio = {"type": "Feature", "properties": {"name": "Prueba Asia", "min_zoom": 3.5, "scalerank": 4},
           "geometry": {"type": "LineString", "coordinates": [[90.123456, 24.345678], [91, 25]]}}
    lago = {"type": "Feature", "properties": {"name": "Prueba Australia"},
            "geometry": {"type": "Polygon", "coordinates": [[[140, -30], [141, -30], [140, -31], [140, -30]]]}}
    for tipo, nombre in modulo.ARCHIVOS.items():
        (tmp_path / nombre).write_text(json.dumps({"features": [rio if tipo == "rio" else lago]}))
    salida = tmp_path / "mundial.geojson"
    geo = modulo.preparar(tmp_path, salida)
    assert len(geo["features"]) == 2
    linea = next(f for f in geo["features"] if f["properties"]["tipo"] == "rio")
    assert linea["properties"]["min_zoom"] == 3.5
    assert linea["geometry"]["coordinates"][0] == [90.1235, 24.3457]
    assert json.loads(salida.read_text(encoding="utf-8")) == geo
