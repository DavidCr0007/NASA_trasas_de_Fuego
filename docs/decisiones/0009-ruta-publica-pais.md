# ADR 0009: Ruta pública temporal sin MAP_KEY (archivo anual por país)

## Estado

ACEPTADA como medida **temporal** (2026-11-13), mientras se valida la `FIRMS_MAP_KEY` de la API area (B-01).

## Contexto

La API area de FIRMS necesita una `MAP_KEY`. Sin ella no había historia real del Huila y la línea base (R5) solo funcionaba con datos sintéticos. FIRMS publica, sin clave, estos archivos:

| ruta | contenido | calidad | ¿sirve para la línea base? |
|---|---|---|---|
| `/data/active_fire/<producto>/csv/<…>_South_America_24h.csv` (y `_7d.csv`) | últimas 24 h o 7 días | NRT | no: muy poca historia |
| `/data/country/<sensor>/<año>/<sensor>_<año>_<País>.csv` | un año completo por país | estándar | **sí** |

Disponibilidad comprobada el 2026-11-13 para Colombia:

| sensor | años |
|---|---|
| `modis` | 2000–2025 |
| `viirs-snpp` | 2012–2025 |
| `viirs-jpss1` (NOAA-20) | 2018–2025 |
| `viirs-jpss2` (NOAA-21) | 404 en 2023–2025 |
| cualquiera, año 2026 | 404 (todavía no publicado) |

## Decisión

- `src/ingest/firms_publico.py` descarga los archivos por país a `data/raw/firms_pais/<País>/`. Son inmutables, de solo lectura y llevan su SHA-256 y su URL en `data/raw/manifest.jsonl`.
- Después escribe un **recorte por bbox** (Huila) en `data/processed/recortes_pais/huila/`, con su propio manifiesto, que incluye `origen_archivo` y `origen_sha256`. Ese manifiesto es la entrada del pipeline.
- `make real` hace la descarga, el recorte y el pipeline. `make api-real` sirve el resultado.
- La demo sin red (`make demo`) sigue usando datos sintéticos.
- Esta variante del esquema (`variante = "pais"`) tiene sus propios códigos: `Terra`/`Aqua` y confianza `l`/`n`/`h` (`docs/esquema_firms.md`).

## Consecuencias

- Hay **historia real de 10 años** (2016–2025), con 84 833 detecciones de calidad estándar en el **recuadro** de trabajo. **Corrección (2026-11-14):** solo 14 280 caen dentro del Huila; el recuadro ocupa cuatro veces la superficie del departamento (ver `docs/metodologia.md` §10.3).
- **No cubre 2026**, que solo existe en NRT. Para el año en curso hacen falta la API area (MAP_KEY) o los archivos de 24 h y 7 días.
- **No incluye NOAA-21** en el archivo por país. Las series mezclan Suomi NPP, NOAA-20 y MODIS (R-36).
- Ocupa unos 165 MB en disco para Colombia 2016–2025. Por eso se recorta antes de procesar.
- Cuando la MAP_KEY esté validada, la API area (`make download`) pasa a ser la ruta principal. Esta ruta queda como respaldo y para reconstruir la historia.

## Alternativas descartadas

- **Usar una clave de terceros:** no es aceptable.
- **Earthdata/LANCE directo:** también requiere iniciar sesión.
- **Google Earth Engine:** exige cuenta y otra cadena de herramientas.
