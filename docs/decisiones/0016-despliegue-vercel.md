# ADR 0016: Despliegue de la app completa con API en Vercel

## Estado

ACEPTADA (2026-11-15). Convive con la demo estática de GitHub Pages (ADR 0015), que se mantiene como respaldo.

## Contexto

Se decidió publicar mediante Vercel **la app completa con API**, conectando el proyecto desde la web de Vercel («Add New → Project → Import» del repositorio). A diferencia de Pages, Vercel ejecuta Python como funciones (documentación consultada el 2026-11-15: <https://vercel.com/docs/functions/runtimes/python>, <https://vercel.com/docs/frameworks/backend/fastapi>):

- Detecta las dependencias en `pyproject.toml` + `uv.lock` y la versión en `.python-version` (3.13; admite 3.12–3.14).
- Carga el `app` ASGI que indica `[tool.vercel] entrypoint`.
- Ejecuta `[tool.vercel.scripts] build` después de instalar las dependencias y antes de publicar.
- El paquete de la función puede ocupar hasta 500 MB sin comprimir. `pyarrow` (unos 90 MB) y `duckdb` caben.
- El disco de la función es de solo lectura, salvo `/tmp`.

## Decisión

1. **Punto de entrada `vercel_app.py`** (raíz del repositorio): crea la misma app que `make api`, con `create_app`.
   - **Datos:** `data/processed/demo_historica`, la muestra **sintética** 2020–2026. `HHN_DATOS` permite apuntar a otro conjunto procesado.
   - **Respaldo:** si la compilación no dejó los datos, los genera una vez en `/tmp/hhn` al arrancar la instancia. Tarda menos de un segundo en local.
   - **Caché de límites de geoBoundaries:** va a `/tmp/hhn/limites_globales`, mediante la variable nueva `HHN_CACHE_LIMITES` de `src/api/limites.py`. Por defecto sigue siendo `data/processed/limites_globales`.
2. **Compilación** `tools/construir_vercel.py`: genera la muestra y ejecuta el pipeline, igual que `make demo` para ese conjunto. Los datos procesados no se versionan (siguen en `.gitignore`); se crean en cada despliegue y son deterministas: mismo `config_fingerprint`.
3. **`vercel.json`:**
   - `maxDuration: 60` para el primer arranque.
   - `excludeFiles` para pruebas, documentación, crudos, conjuntos grandes no usados y Leaflet (ya no se usa).
4. **Nada de secretos:** no se configura `FIRMS_MAP_KEY`. La app publicada no descarga datos de FIRMS; solo sirve la muestra procesada.

## Consecuencias

- **La URL de Vercel ofrece la app completa:**
  - globo, capas y vías;
  - departamento, municipio y ciudad, también fuera del Huila (límites de geoBoundaries bajo demanda);
  - búsqueda con Nominatim, áreas dibujadas y por coordenadas;
  - descargas de cualquier área.

  Los datos siguen siendo **sintéticos** y la interfaz lo indica.
- **Nominatim:** el límite de una consulta por segundo vive en memoria de cada instancia. Con varias instancias simultáneas (Fluid compute) no es global. Para tráfico alto habría que guardar la hora de la última consulta en un almacén compartido. Las búsquedas siguen sin guardarse.
- **Caché de `/tmp`:** dura lo que la instancia. Tras un arranque en frío, los límites se vuelven a pedir a geoBoundaries.
- **Tráfico público:** las teselas de OpenStreetMap y Nominatim tienen políticas de uso moderado. Antes de un uso intensivo hace falta un proveedor propio (R-30).
- **GitHub Pages sigue publicando la demo estática** en cada push a `main` (ADR 0015).
- **Pruebas** (`tests/test_vercel.py`):
  - configuración coherente: punto de entrada, compilación, versión y exclusiones que no tocan lo necesario;
  - la compilación genera los datos;
  - el punto de entrada sirve la API y la interfaz, y genera los datos en `/tmp` si faltan;
  - la caché de límites es configurable.

  Recorrido en Chrome contra `uvicorn vercel_app:app` sin datos previos: 15/15, incluido el Tolima con límites de geoBoundaries.

## Pasos en Vercel

1. *Add New → Project → Import* del repositorio `NASA_trasas_de_Fuego`.
2. *Framework Preset*: **FastAPI** (o «Other»; la configuración vive en `pyproject.toml` y `vercel.json`). Sin variables de entorno. No hay que escribir el *Build Command*: si se escribe uno en el panel, reemplaza al de `pyproject.toml`.
3. *Deploy*. Después, cada push a `main` publica una versión nueva y cada rama tiene su vista previa.
4. Comprobar `/salud` (debe responder `"estado": "ok"`) y `/ui/`.

## Pendiente

- Probar el primer despliegue real. Las pruebas locales no reproducen el sistema de archivos ni el empaquetado de Vercel.
- Publicar datos reales del Huila (`HHN_DATOS` con un conjunto procesado en la compilación) cuando se decida.
