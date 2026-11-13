# Harmonized Heat Neiva

Proyecto del reto **«Harmonization of MODIS and VIIRS Hot Spots»** (NASA Space Apps 2026).

## Objetivo

Armonizar los focos de calor (hot spots) de MODIS y VIIRS publicados por NASA FIRMS para el departamento del Huila y Neiva (Colombia), de modo que sean comparables entre sensores y satélites. El resultado es una tabla reproducible por celda y día, con reglas versionadas (`RULES_VERSION`), en la que se conservan el satélite, la hora UTC y la calidad de cada detección.

Estado: en etapa inicial. Los hitos H0 (estructura y documentación), H1 (lector y validación) y H2 (grilla, confianza, deduplicación y Parquet reproducible) están en el alcance de este plan.

> **Aviso importante:** el esquema de datos de FIRMS, los códigos de satélite, las escalas de confianza y el bbox del Huila están **por confirmar** contra la documentación oficial. Hasta que se verifiquen, el proyecto trabaja con datos sintéticos que imitan el esquema oficial. Véanse `docs/esquema_firms.md` y `tasks/RIESGOS.md`.

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
Pipeline armonizacion-0.2.0 (config xxxxxxxxxxxx)
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

Texto de cita y aviso copiado de `docs/cita.md`. Todavía no hay texto oficial verificado: los fragmentos se reproducen tal como constan en ese archivo, y la cita definitiva se completará cuando se consulte la fuente oficial.

**Cita obligatoria de FIRMS**

> por confirmar. Fuente faltante: página de reconocimiento/cita de FIRMS (Earthdata, sección FIRMS).

**Reconocimiento de LANCE y ESDIS**

> por confirmar. Fuente faltante: página de reconocimiento de LANCE (Earthdata).

**Aviso «as is» de LANCE**

> por confirmar (texto oficial literal). Fuente faltante: aviso de datos de LANCE.

**Cómo citar este proyecto**

> Harmonized Heat Neiva (NASA Space Apps 2026, reto «Harmonization of MODIS and VIIRS Hot Spots»). Repositorio: por confirmar. Los datos de incendios provienen de NASA FIRMS; incluya la cita oficial de arriba cuando esté confirmada.

**Aviso**

> Este proyecto es una herramienta de armonización con fines de concurso; los datos se entregan «as is» según el aviso oficial de LANCE (texto por confirmar) y no deben usarse para decisiones críticas.
