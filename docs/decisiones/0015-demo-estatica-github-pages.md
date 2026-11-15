# ADR 0015: Demo estática en GitHub Pages

## Estado

ACEPTADA (2026-11-15). No cambia la app con API (ADR 0008, 0012–0014): añade una forma de publicarla sin servidor.

## Contexto

Se pidió publicar la última versión en GitHub Pages. Pages solo sirve archivos estáticos, y el visor depende de la API FastAPI (`/calendario`, `/detecciones`, `/resumen`, `/global`, `/limites`, `/buscar-lugares`). Publicar solo la carpeta de la interfaz dejaría el mapa sin focos, sin calendario y sin zonas.

La muestra sintética histórica (`make demo`, 2020–2026) tiene 3 257 detecciones: cabe completa en el navegador.

## Decisión

1. **Precalcular con la misma API, no reimplementarla.** `tools/exportar_estatico.py` crea la app en proceso (`TestClient`) y guarda sus respuestas exactas:
   - `/calendario` de cada año con datos para el Huila y sus 37 municipios, más el inicial del Huila;
   - `/resumen` de las 38 áreas;
   - `/global` para 1, 2 y 7 días a 0,25°, 0,5° y 1°;
   - los CSV del Huila por año;
   - todas las detecciones en un archivo por columnas (`api/detecciones.json`, unos 520 kB).

   El sitio pesa unos 28 MB. La armonización, la línea base y el calendario siguen calculándose en Python; el navegador no duplica esa lógica.
2. **`estatico.js` intercepta `fetch`.** El exportador lo inserta antes que cualquier otro script; el `index.html` del repositorio no lo carga.
   - **`/ui/…`** pasa a la carpeta del sitio.
   - **Rutas de la API:** se responden con los archivos precalculados.
   - **Lo que deriva el navegador** de esos archivos, con el mismo `zonas.js`:
     - los periodos parciales del calendario (un día o el rango del globo): días del año y clases de confianza del periodo;
     - las consultas de focos por área (forma real), recuadro y fechas.
   - **MapLibre** carga los GeoJSON del estilo por su cuenta, así que esas dos rutas pasan por `recurso()` en `globo.js`.
3. **Lo que necesita servidor no se inventa.** Las áreas dibujadas o por coordenadas, la búsqueda en internet (Nominatim) y los límites fuera del Huila (`/limites`) responden 404 o 503 con «ejecute la API local (make api)». La tarjeta de zona y la cabecera lo dicen. Los CSV de otras áreas o fechas avisan con un mensaje.
4. **Publicación con GitHub Actions** (`.github/workflows/pages.yml`), en cada push a `main` o a mano:
   1. `uv sync --frozen` y `pytest`;
   2. regenera la muestra (igual que `make demo`);
   3. exporta `_site`;
   4. `actions/upload-pages-artifact` y `actions/deploy-pages`.

   No usa secretos. `_site/` está en `.gitignore`.

## Consecuencias

- **La página publicada muestra datos SINTÉTICOS.** Lo dicen la cabecera, el pie y la tarjeta de origen.
- **Lo que funciona en Pages:**
  - globo, capas, preajustes y vías;
  - resaltado de departamento, municipio y ciudad del Huila;
  - búsqueda local, calendario, matriz año × mes y línea de tiempo;
  - descargas del Huila por año.
- **Lo que no funciona en Pages:** límites fuera del Huila, Nominatim, áreas dibujadas o por coordenadas, y datos reales.
- **Teselas externas:** NASA GIBS, OpenStreetMap y Open-Meteo se piden desde el navegador. En un sitio público, la política de uso de teselas de OSM pide tráfico moderado; si la demo recibe mucho tráfico, hace falta un proveedor propio (R-30).
- **Activación:** Pages debe activarse una vez en *Settings → Pages → Source: GitHub Actions* (permiso de administrador del repositorio).
- **Pruebas:**
  - `tests/test_estatico.py`: respuestas iguales a la API, detecciones completas, `estatico.js` antes que todo y cobertura de las rutas de la interfaz.
  - El recorrido `capas` en Chrome sobre el sitio servido en una subcarpeta da 15/15, con el aviso de la demo fuera del Huila.

## Pendiente

- Publicar una demo con datos reales del Huila (`make real`) cuando se decida publicar ese recorte (el archivo crece a unas 14 000 detecciones; sigue cabiendo).
