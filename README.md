# Harmonized Heat Neiva

Proyecto del reto **«Harmonization of MODIS and VIIRS Hot Spots»** (NASA Space Apps 2026).

## Objetivo

Armonizar los focos de calor (hot spots) de MODIS y VIIRS publicados por NASA FIRMS en un **calendario de actividad de quema** que respondedores de emergencia, científicos y gestores de tierras pueden consultar para un área de interés. Muestra patrones históricos, días inusuales y periodos críticos. El caso de uso es el Huila y Neiva (Colombia).

La serie histórica está repartida entre sensores con distinta resolución y hora de paso (MODIS en Terra y Aqua; VIIRS en Suomi NPP, NOAA-20 y NOAA-21). Para hacerla comparable, el proyecto aplica estas reglas versionadas (`RULES_VERSION = armonizacion-0.3.1`):

- **R1:** grilla común de ~1 km y agregación por celda y día.
- **R2:** confianza en tres clases.
- **R3:** deduplicación entre pasadas cercanas, conservando VIIRS.
- **R4:** cada registro conserva su satélite, su hora UTC y su calidad.
- **R5:** línea base por día del año, para detectar días inusuales.

**Estado (2026-11-14):** hitos H0 a H4 y H6 (interfaz clara/oscura y origen de los datos) terminados; H5 en entrega, con la comparación con el visor pendiente (H5-02) (ver `docs/checklist_entrega.md`). La `FIRMS_MAP_KEY` de la API area sigue pendiente (B-01). Mientras tanto, `make real` obtiene **historia real de 2016 a 2025** del archivo público por país de FIRMS (ADR 0009, calidad estándar): 84 833 detecciones en el recuadro de trabajo, de las cuales **14 280 caen dentro del Huila** (filtro por forma real, `area=huila`). La demo sin red (`make demo`) usa datos **sintéticos**.

## Estructura de carpetas

```
data/
  raw/                Datos crudos de FIRMS. INMUTABLE y fuera de git; manifiesto SHA-256.
  processed/          Salidas Parquet (demo y demo_historica). Se regeneran.
  sample/             Muestra SINTÉTICA pequeña (3 días) para pruebas y casos borde.
  sample_historica/   Muestra SINTÉTICA 2020–2026, generada por make demo (fuera de git).
src/
  ingest/             Esquema FIRMS, descarga (API area y archivo público por país), manifiesto, lector y validación.
  harmonize/          Reglas R1 a R5, configuración versionada y pipeline Parquet.
  api/                API FastAPI de solo lectura (DuckDB sobre Parquet).
  ui/static/          Interfaz: mapa Leaflet (incluido) y calendario, sin compilación.
tools/                Generadores de muestra, validación cruzada y escaneo de secretos.
tests/                Pruebas con pytest (sintéticas y con recortes reales de FIRMS).
docs/                 Metodología, limitaciones, cita, esquema, decisiones (ADR), pitch y entrega.
tasks/                Backlog (BACKLOG.md) y riesgos (RIESGOS.md).
```

## Datos

- **Origen:** NASA FIRMS. MODIS C6.1 (Terra y Aqua) y VIIRS 375 m (NOAA-20 y NOAA-21; Suomi NPP solo como histórico, porque ya no entrega datos nuevos). Columnas y códigos en `docs/esquema_firms.md`.
- **Calidad:** NRT (preliminar) o estándar. Cada registro, día y exportación lo indica, y cualquier resultado con NRT se marca como **preliminar**.
- **Crudo inmutable:** `data/raw/` nunca se modifica. Cada archivo queda en `data/raw/manifest.jsonl` con su SHA-256, la fecha de descarga y la URL sin la clave.
- **Muestras sintéticas:** `data/sample/` y `data/sample_historica/` **no son observaciones reales**. Sus archivos empiezan por `SINTETICO_` y su manifiesto lleva `sintetico=true`.
- **Sin datos personales** (D-09).

## Instalación

Requisitos: [uv](https://docs.astral.sh/uv/) y Python 3.13 (uv puede instalarlo con `uv python install 3.13`).

```bash
git clone https://github.com/DavidCr0007/NASA_trasas_de_Fuego.git
cd NASA_trasas_de_Fuego
make sync     # instala las dependencias fijadas en uv.lock (requiere red la primera vez)
make test     # pruebas
make api      # demo completa sin red: http://127.0.0.1:8000
```

## Configuración

```bash
cp .env.example .env
# Edite .env y reemplace el valor de FIRMS_MAP_KEY por su clave.
```

`FIRMS_MAP_KEY` es una clave personal de FIRMS. **No se incluye en el repositorio.** Si no existe `.env`, `make download` no se ejecuta y el proyecto sigue trabajando con datos sintéticos (registrado como bloqueo B-01 en `tasks/RIESGOS.md`).

## Comandos

| Comando | Qué hace |
|---|---|
| `make sync` | Instala las dependencias fijadas en `uv.lock` (requiere red la primera vez). |
| `make test` | Ejecuta las pruebas con pytest. |
| `make demo` | Comando único de la demo **sin red**: procesa `data/sample/`, genera `data/sample_historica/` y la procesa. Todo sintético. |
| `make api` | Corre la demo y levanta la interfaz (mapa y calendario) y la API en http://127.0.0.1:8000 (API en `/docs`). |
| `make real` | Ruta pública temporal sin clave: descarga el archivo anual por país (Colombia 2016–2025), lo recorta al Huila y lo procesa (requiere red la primera vez). |
| `make api-real` | Sirve la interfaz con esos datos reales. |
| `make download` | Descarga desde la API área de FIRMS para el bbox del Huila. Requiere `FIRMS_MAP_KEY` en `.env`. |
| `make secrets` | Escanea el repositorio en busca de credenciales antes de entregar. |
| `make verify-raw` | Verifica los SHA-256 de `data/raw/` contra su manifiesto. |

Procedimiento de descarga y verificación: [docs/descarga.md](docs/descarga.md).

## Demo offline

`make demo` corre dos pipelines sin red, ambos con datos **sintéticos**:

1. `data/sample/` → `data/processed/demo/`: 132 filas con casos borde (cuarentena, cruce de medianoche, NRT frente a estándar).
2. `tools/generar_historico.py` genera `data/sample_historica/` (2020–2026, con una anomalía inyectada en agosto de 2026) → `data/processed/demo_historica/`, que es la que usa la interfaz.

Cada salida tiene `detecciones.parquet`, `deduplicados.parquet`, `cuarentena.parquet`, `celda_dia.parquet` y `resumen.json`. Dos ejecuciones producen los mismos hashes, con las versiones de `uv.lock`. Salida esperada de la primera (formato; los valores exactos están en `resumen.json`):

```
Pipeline armonizacion-0.3.1 (config xxxxxxxxxxxx)
  entrada:      132
  aceptados:    N
  deduplicados: N
  cuarentena:   N
  celda-día:    N
  invariante:   OK
```

Detalle de tablas y consultas DuckDB: [docs/metodologia.md](docs/metodologia.md#pipeline-y-salidas).

## Interfaz y API local

`make api` abre la interfaz en http://127.0.0.1:8000/: mapa de focos con su huella nominal, calendario de actividad con días inusuales, temporada mensual y periodos críticos. Sirve la muestra histórica **sintética** 2020–2026, funciona sin internet y las teselas del mapa son opcionales. Tiene tema claro u oscuro (selector «Tema») y una insignia que indica si los datos son sintéticos o reales.

Ejemplo de la API para el Huila:

```bash
curl "http://127.0.0.1:8000/calendario?bbox=-76.7,1.4,-74.3,3.9"
curl "http://127.0.0.1:8000/calendario.csv?bbox=-76.7,1.4,-74.3,3.9" -o calendario.csv
```

Cada respuesta trae la cita de FIRMS, el aviso «as is», la versión de reglas, la calidad (NRT/estándar, `preliminar`), los metadatos de incertidumbre y el estado de la línea base («base insuficiente» si no hay años suficientes). Rutas y campos: [docs/metodologia.md](docs/metodologia.md#7-api-de-consulta-h3).

## Capas de contexto (H7)

En el mapa y el panel hay tres capas de contexto (ADR 0010):

- **Límites de los 37 municipios del Huila** (geoBoundaries / DANE). Funcionan sin red.
- **Imagen satelital de color real del día elegido** (NASA GIBS). Requiere internet.
- **Clima del día o del periodo crítico** (Open-Meteo; es un reanálisis, no una observación). Requiere internet.

Si no hay red, la herramienta funciona sin las dos últimas.

## Limitaciones

Lo esencial; el detalle está en [docs/limitaciones.md](docs/limitaciones.md):

- Los focos son **detecciones térmicas, no incendios confirmados**.
- Cada punto es el **centro de un píxel**: 1 km en MODIS y 375 m en VIIRS, y el píxel crece hacia el borde del barrido.
- VIIRS de 375 m **se satura** en fuegos intensos, así que el FRP es indicativo.
- Cuando Terra deje de pasar, cambiarán las horas de observación y la serie MODIS quedará **sesgada en el horario**.
- Los datos **NRT** son preliminares.
- «Inusual» significa por encima del P95 histórico de ese día del año (±7 días, sin contar el propio año). En un año normal, ~5 % de los días lo supera.
- Se necesitan 5 años de historia; con menos, la respuesta es «base insuficiente».

## Documentación

- [Metodología](docs/metodologia.md): flujo, validación y reglas R1 a R4.
- [Limitaciones](docs/limitaciones.md): lo que el método no resuelve y lo que está por confirmar.
- [Decisiones (ADR)](docs/decisiones/): supuestos registrados uno por archivo.
- [Cita y aviso](docs/cita.md): cómo citar FIRMS, LANCE y ESDIS.
- [Esquema FIRMS verificado](docs/esquema_firms.md) y [descarga](docs/descarga.md).
- [Pitch de 2 minutos](docs/pitch.md) y [lista de entrega](docs/checklist_entrega.md).
- [Backlog](tasks/BACKLOG.md) y [riesgos](tasks/RIESGOS.md).

## Cita y aviso

Texto oficial copiado de la página de FIRMS en Earthdata (2026-11-13). Detalle, DOI y estudios de validación en [docs/cita.md](docs/cita.md).

> We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://www.earthdata.nasa.gov/data/tools/firms), part of NASA's Land, Atmosphere Near real-time Capability for Earth observations (LANCE) and NASA's Earth Science Data and Information System (ESDIS).

> The information presented through LANCE, GIBS, Worldview, and FIRMS are provided "as is" and users bear all responsibility and liability for their use of data.

Los focos son detecciones térmicas, no incendios confirmados. Los datos NRT son preliminares. Ver [docs/limitaciones.md](docs/limitaciones.md).
