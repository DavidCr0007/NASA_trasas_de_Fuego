# Harmonized Heat Neiva

Proyecto del reto **«Harmonization of MODIS and VIIRS Hot Spots»** (NASA Space Apps 2026).

## Objetivo

Armonizar los focos de calor (hot spots) de MODIS y VIIRS publicados por NASA FIRMS para el departamento del Huila y Neiva (Colombia), de modo que sean comparables entre sensores y satélites. El resultado es una tabla reproducible por celda y día, con reglas versionadas (`RULES_VERSION`), en la que se conservan el satélite, la hora UTC y la calidad de cada detección.

Estado: en etapa inicial. Los hitos H0 (estructura y documentación), H1 (lector y validación) y H2 (grilla, confianza, deduplicación y Parquet reproducible) están en el alcance de este plan.

> **Estado del esquema (2026-11-13):** las columnas, los códigos de satélite (`N`, `N20`, `N21`, `T`, `A`), la confianza (`low`/`nominal`/`high` en VIIRS, 0–100 en MODIS) y los patrones de `version` están verificados contra la tabla oficial de atributos y contra CSV reales de FIRMS (24 h, NRT). Siguen **por confirmar** la cabecera exacta de la API area, los cortes oficiales de confianza MODIS, los DOI y el bbox del Huila. La demo usa datos sintéticos con ese esquema confirmado. Véanse `docs/esquema_firms.md` y `tasks/RIESGOS.md`.

## Estructura de carpetas

```
data/
  raw/          Datos crudos de FIRMS. INMUTABLE y fuera de git.
                Incluye el manifiesto SHA-256 en data/raw/manifest.jsonl.
  processed/    Salidas derivadas (Parquet). Se regeneran desde data/raw.
  sample/       Datos de muestra SINTÉTICOS para `make demo` (offline).
src/
  ingest/       Descarga y lectura de FIRMS, validación del esquema.
  harmonize/    Reglas R1 a R4 (grilla, confianza, deduplicación) y salida.
  api/          API FastAPI (fase posterior).
  ui/           Interfaz de usuario (fase posterior).
tests/          Pruebas con pytest (datos sintéticos y fixtures).
docs/           Metodología, limitaciones, cita y decisiones (ADR).
tasks/          Backlog (BACKLOG.md) y riesgos (RIESGOS.md).
```

Notas:

- `data/raw/` nunca se modifica después de escribirse. Cada archivo se registra con su SHA-256 y la fecha de descarga en `data/raw/manifest.jsonl`.
- `data/raw/` y `.env` están excluidos de git.
- Los datos de `data/sample/` son **sintéticos**; no son observaciones reales.

## Requisitos

- [uv](https://docs.astral.sh/uv/)
- Python 3.13 (uv puede instalarlo: `uv python install 3.13`)

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
| `make demo` | Ejecuta el flujo completo **offline** con `data/sample/` (datos sintéticos). |
| `make download` | Descarga desde la API área de FIRMS para el bbox del Huila. Requiere `FIRMS_MAP_KEY` en `.env`. |
| `make secrets` | Escanea el repositorio en busca de credenciales antes de entregar. |

Procedimiento de descarga y verificación: [docs/descarga.md](docs/descarga.md).

## Demo offline

`make demo` procesa `data/sample/` (datos **sintéticos**, sin red) y escribe en `data/processed/demo/`: `detecciones.parquet`, `deduplicados.parquet`, `cuarentena.parquet`, `celda_dia.parquet` y `resumen.json`. Dos ejecuciones producen los mismos hashes (con las versiones de `uv.lock`). Salida esperada (formato; los valores exactos están en `resumen.json`):

```
Pipeline armonizacion-0.3.0 (config xxxxxxxxxxxx)
  entrada:      132
  aceptados:    N
  deduplicados: N
  cuarentena:   N
  celda-día:    N
  invariante:   OK
```

Detalle de tablas y consultas DuckDB: [docs/metodologia.md](docs/metodologia.md#pipeline-y-salidas).

## Documentación

- [Metodología](docs/metodologia.md): flujo, validación y reglas R1 a R4.
- [Limitaciones](docs/limitaciones.md): lo que el método no resuelve y lo que está por confirmar.
- [Decisiones (ADR)](docs/decisiones/): supuestos registrados uno por archivo.
- [Cita y aviso](docs/cita.md): cómo citar FIRMS, LANCE y ESDIS.
- [Backlog](tasks/BACKLOG.md) y [riesgos](tasks/RIESGOS.md).

## Cita y aviso

Texto oficial copiado de la página de FIRMS en Earthdata (2026-11-13). Detalle, DOI y estudios de validación en [docs/cita.md](docs/cita.md).

> We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://www.earthdata.nasa.gov/data/tools/firms), part of NASA's Land, Atmosphere Near real-time Capability for Earth observations (LANCE) and NASA's Earth Science Data and Information System (ESDIS).

> The information presented through LANCE, GIBS, Worldview, and FIRMS are provided "as is" and users bear all responsibility and liability for their use of data.

Los focos son detecciones térmicas, no incendios confirmados. Los datos NRT son preliminares. Ver [docs/limitaciones.md](docs/limitaciones.md).
