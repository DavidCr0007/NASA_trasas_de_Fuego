# ADR 0017 — Hidrografía mundial con detalle por teselas

Fecha: 2026-11-15. Estado: aplicado.

## Problema y decisión

La preparación anterior conservaba únicamente geometrías que tocaban Colombia. Por ello, las bases «Agua» e «Hidrografía» y la superposición «Ríos y lagos» parecían vacías en otros países.

Se sustituye ese recorte por `hidrografia_mundial.geojson`: todos los **1.455 elementos de ríos y ejes de lagos y 1.355 lagos** de Natural Earth 1:10m v5.1.2. Se conservan nombres, rango y zoom recomendado, coordenadas a cuatro decimales y los SHA-256 de ambos archivos originales. El archivo generalizado funciona sin red; las versiones estáticas lo copian junto a la interfaz.

Desde zoom 6 se solicitan las teselas vectoriales de la zona visible a **OpenFreeMap**, con datos **OpenStreetMap** y esquema **OpenMapTiles**. Se dibujan únicamente `waterway` (ríos, arroyos, canales, drenajes y acequias) y `water` (cuerpos de agua, excluido el océano). Se mantienen los colores azules, la posición bajo los límites y los focos, la opacidad del panel y el mismo lienzo del planeta.

El detalle aparece progresivamente entre zoom 6 y 7. Natural Earth se desvanece cuando hay geometrías detalladas disponibles para evitar trazados duplicados a distinta precisión. Un error del proveedor restaura la capa generalizada. No se descarga el planeta completo de OpenStreetMap: MapLibre solicita las teselas visibles y reutiliza su caché. No se añaden claves ni dependencias de Python.

## Fuentes y alcance

- Ríos: [https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-rivers-lake-centerlines/](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-rivers-lake-centerlines/).
- Lagos: [https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-lakes/](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-lakes/).
- Natural Earth: [dominio público](https://www.naturalearthdata.com/about/terms-of-use/).
- Proveedor de detalle: [https://openfreemap.org/](https://openfreemap.org/).
- Datos: [OpenStreetMap, ODbL](https://www.openstreetmap.org/copyright); [OpenMapTiles](https://www.openmaptiles.org/).

La cobertura pasa a ser mundial. **No equivale a un inventario exhaustivo de cada afluente del planeta**: los cursos pequeños dependen de su registro en OpenStreetMap y de la generalización de las teselas. Natural Earth representa cursos y lagos principales, no una red hidrológica de precisión. Las teselas usan Web Mercator y no cubren las latitudes polares extremas; el respaldo mundial sí conserva las geometrías disponibles de Natural Earth. No proporciona caudales, calidad del agua ni seguimiento en tiempo real.

## Reproducir

Con los dos GeoJSON originales en `data/raw/natural_earth/20261115/`:

```powershell
uv run python tools/preparar_hidrografia.py
uv run pytest -q
uv run python -m api --datos data/processed/demo_historica --puerto 8000
```

En otra terminal:

```powershell
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/hidrografia_mundial "C:/Program Files/Google/Chrome/Application/chrome.exe" hidrografia
```

El recorrido exige geometrías dibujadas en Amazonas, Nilo, Sena, Mississippi, Bangladesh, Australia y Suiza; en Suiza comprueba expresamente arroyos (`stream`) a zoom 13. Conserva el mismo mapa, comprueba el control de visibilidad, bloquea el proveedor para validar el respaldo y revisa el ancho móvil. Evidencia: [cobertura](../capturas/hidrografia_mundial_20261115/cobertura.json), [Sena](../capturas/hidrografia_mundial_20261115/sena.png), [Nilo](../capturas/hidrografia_mundial_20261115/nilo.png).

La suite de Python pasó **564 pruebas** y el recorrido de Chrome **13/13 comprobaciones**, incluida la recuperación al fallar la consulta del proveedor con datos previos en caché. Se conserva una advertencia de deprecación de Starlette/HTTPX, ajena a esta capa. El escaneo de credenciales no encontró secretos.
