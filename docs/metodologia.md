# Metodología

Este documento describe cómo se transforman los focos de calor crudos de NASA FIRMS (MODIS C6.1 y VIIRS 375 m) en una tabla armonizada por celda y día. Los valores marcados **PROVISIONAL** o **por confirmar** no están validados y deben revisarse antes de usar los resultados.

## 1. Flujo general

```
crudo (data/raw, inmutable)
   -> manifiesto SHA-256 (data/raw/manifest.jsonl)
   -> lector y validación (D-01 a D-04)
        -> aceptados
        -> cuarentena (con motivo)
   -> reglas R1 a R4 sobre los aceptados
        -> grilla (R1), confianza (R2), deduplicación (R3), conservación (R4)
        -> duplicados a tabla aparte
   -> agregación celda-día
   -> Parquet reproducible (D-05, D-06)
```

Invariante de conteo (D-04): **entrada = aceptados + cuarentena + deduplicados**. Ningún registro se borra; cada uno termina en una de las tres salidas.

## 2. Crudo, manifiesto y procedencia

- Los archivos de `data/raw/` se escriben una vez y no se modifican.
- Cada archivo se registra en `data/raw/manifest.jsonl` con su ruta, su SHA-256 y la fecha de descarga.
- La descarga usa la API área de FIRMS con `FIRMS_MAP_KEY` (desde `.env`) para el bbox del Huila, el último año y las fuentes `MODIS_NRT`, `MODIS_SP`, `VIIRS_SNPP` (solo histórico), `VIIRS_NOAA20` y `VIIRS_NOAA21`. El bbox y los nombres de fuente están **por confirmar** (véase `docs/esquema_firms.md`).

## 3. Lector y validación (D-01 a D-04)

**D-01. Lector con validación de esquema.** El lector comprueba que las columnas del archivo coinciden con el esquema esperado para su sensor y variante. Las columnas, verificadas contra la tabla oficial de atributos y CSV reales de FIRMS (2026-11-13), están en `src/ingest/firms_schema.py` (detalle en `docs/esquema_firms.md`). Si a un archivo le falta una columna requerida, **todas sus filas van a cuarentena** con el motivo «esquema inválido: faltan columnas […]»; nunca se interpreta a medias. Las columnas extra se toleran y se registran.

**D-02. Procedencia por registro.** Cada registro conserva:

- sensor (MODIS o VIIRS);
- satélite (código tal como aparece en el archivo; los códigos están **por confirmar**);
- colección o producto;
- hora UTC de la detección (`acq_date` + `acq_time`; formato **por confirmar**);
- fecha de descarga;
- hash SHA-256 del archivo fuente;
- calidad: NRT o estándar (a partir de la fuente y del campo `version`; patrones **por confirmar**).

**D-03. Validación de campos.** Cada registro se valida en:

- latitud en [−90, 90] y longitud en [−180, 180] (el recorte al bbox de trabajo lo hace la descarga, no la validación);
- fecha y hora válidas en UTC;
- confianza dentro del dominio del sensor (VIIRS: `l`, `n`, `h`, **por confirmar**; MODIS: número 0–100, **por confirmar**);
- satélite presente en el catálogo de códigos (**por confirmar**).

**D-04. Cuarentena.** Un registro que no supera la validación va a cuarentena con un motivo explícito (por ejemplo, «confianza fuera de dominio»). Nunca se borra. La cuarentena se conserva en una tabla propia para auditoría.

## 4. Reglas de armonización

### R1. Grilla común de ~1 km

- Grilla fija en grados, sin factor de coseno por punto.
- Tamaño de celda: `CELL_DEG = 0.009` (≈ 1 km en el Huila). **PROVISIONAL**, configurable.
- Origen de la grilla: `(-90, -180)`, configurable.
- Índice de celda: `fila = floor((lat - (-90)) / CELL_DEG)`, `columna = floor((lon - (-180)) / CELL_DEG)`.
- Justificación y alternativas: `docs/decisiones/0001-grilla.md`.

### R2. Confianza en tres clases

Cada detección se asigna a una de tres clases: **baja**, **nominal** o **alta**.

- MODIS (valor numérico 0–100, dominio **por confirmar**):
  - < 30 → baja;
  - 30 a 79 → nominal;
  - ≥ 80 → alta.
- VIIRS: mapeo de las clases oficiales de FIRMS (`l`, `n`, `h`, **por confirmar**) a baja, nominal y alta.

Todos los umbrales son **PROVISIONALES** y configurables. Véase `docs/decisiones/0002-umbrales-confianza.md`.

### R3. Deduplicación

- Dos detecciones son candidatas a duplicado si están en la **misma celda** y su diferencia de tiempo cumple **|Δt| ≤ 3 h**.
- El agrupamiento es **voraz** y se ancla al primer registro del grupo: se ordenan los registros por tiempo, se abre un grupo con el primero y se añaden los siguientes que estén a ≤ 3 h de ese primero. Un registro posterior que solo esté cerca del último añadido no entra (la regla no es transitiva; véase `docs/limitaciones.md`).
- Prioridad para elegir el representante de cada grupo:
  1. VIIRS antes que MODIS;
  2. estándar antes que NRT;
  3. confianza mayor;
  4. hora UTC más temprana;
  5. `record_id` (desempate final, determinista).
- Los duplicados no se borran: se guardan en una **tabla aparte** de duplicados, con referencia a su representante.
- Decisión y limitación: `docs/decisiones/0003-deduplicacion.md`, `docs/decisiones/0007-precedencia-nrt-estandar.md`.

### R4. Conservación de atributos

En la salida se conservan, por registro representante: satélite, hora UTC y calidad (NRT o estándar). La agregación no pierde estos atributos.

## 5. Agregación celda-día

Los registros aceptados y deduplicados se agregan por celda (R1) y fecha UTC. La fecha de celda-día es **UTC**, no la hora local de Colombia (UTC−5); véase `docs/limitaciones.md`.

## 6. Salida reproducible (D-05, D-06)

- **D-05. Versión de reglas.** Cada fila de salida incluye `RULES_VERSION`, identificador de la versión de reglas (grilla, umbrales, deduplicación) con que se generó.
- **D-06. Reproducibilidad.** El mismo crudo, con las mismas versiones fijadas en `uv.lock` y la misma `RULES_VERSION`, produce un Parquet con el **mismo hash SHA-256**. Para ello el orden de filas, los tipos de columna y los metadatos son deterministas. La reproducibilidad depende de las versiones fijadas en `uv.lock` (véase `docs/limitaciones.md`).

## Pipeline y salidas

`python -m harmonize.pipeline --input DIR --output DIR [--manifest RUTA]` (o `make demo` con `data/sample`) lee el manifiesto (por defecto `DIR/manifest.jsonl`), verifica el SHA-256 de cada CSV, aplica `harmonize_ingest` y escribe en `--output`. Se rechaza cualquier salida dentro de `data/raw`. No usa red.

| Archivo | Contenido | Orden de filas |
|---|---|---|
| `detecciones.parquet` | Registros conservados (representantes). | `record_id` |
| `deduplicados.parquet` | Registros absorbidos por un representante. | `record_id` |
| `cuarentena.parquet` | Registros rechazados con su motivo (nunca se borran). | `(archivo_origen, fila, motivo, datos_crudos)` |
| `celda_dia.parquet` | Agregación por celda y fecha UTC. | `(cell_id, fecha_utc)` |
| `resumen.json` | Conteos, invariante, `rules_version`, `config_fingerprint`, SHA-256 de entradas y de cada Parquet, cuarentena por motivo. | claves ordenadas |

Columnas principales:

- **detecciones**: `record_id`, `fuente`, `sensor`, `satelite_codigo`, `satelite`, `satelite_confirmado`, `coleccion`, `version`, `calidad` (`NRT`/`estandar`), `lat`, `lon`, `fecha_hora_utc` (timestamp µs UTC), `daynight`, `confianza_raw`, `frp`, `brillo`, `archivo_origen`, `sha256_origen`, `fecha_descarga`, `fila`, `sintetico`, `confianza_clase`, `cell_id`, `cell_fila`, `cell_col`, `rules_version`, `n_fusionados`.
- **deduplicados**: las mismas, sin `n_fusionados`, más `dedup_de`, `delta_t_min`, `motivo`.
- **cuarentena**: `archivo_origen`, `sha256_origen`, `fila`, `motivo`, `datos_crudos` (JSON), `fecha_descarga`, `rules_version`.
- **celda_dia**: `cell_id`, `fecha_utc`, `cell_fila`, `cell_col`, `n_detecciones`, `n_brutas`, `n_modis`, `n_viirs`, `confianza_max`, `frp_max`, `frp_sum`, `primera_hora_utc`, `ultima_hora_utc`, `satelites`, `calidades`, `centroide_lat`, `centroide_lon`, `rules_version`.

Todos los archivos llevan en los metadatos Parquet `rules_version` y `config_fingerprint`. Los umbrales, la ventana y la grilla son **provisionales** (ADR 0001 a 0003).

Consulta con DuckDB:

```sql
SELECT cell_id, fecha_utc, n_detecciones, confianza_max
FROM read_parquet('data/processed/demo/celda_dia.parquet')
ORDER BY n_detecciones DESC LIMIT 10;
```

**Garantía de reproducibilidad.** El mismo crudo (mismos SHA-256 en el manifiesto), la misma configuración y `RULES_VERSION` producen archivos Parquet con el mismo SHA-256, sin importar el orden de las líneas del manifiesto. Lo logran: esquema pyarrow explícito (sin pandas), filas ordenadas por clave estable, parámetros de escritura fijos (zstd nivel 3, grupos de 65 536 filas, estadísticas activas, formato Parquet 2.6), ninguna marca de reloj ni ruta absoluta, y reemplazo atómico del archivo. La garantía está **condicionada a `uv.lock`**: otra versión de pyarrow/Arrow puede cambiar bytes del Parquet (p. ej. `created_by` o la codificación) sin que cambien los datos.

## 7. Propuestas para hitos posteriores (no implementadas en H0–H2)

- Línea base celda-mes con percentil candidato P90 (`docs/decisiones/0004-percentil.md`).
- Mínimo de años de historia para la línea base (`docs/decisiones/0005-minimo-anios.md`).

## Prueba con datos reales (H0-07)

Fuente: CSV públicos de FIRMS de 24 h para South America. Calidad **NRT**; descargados el 2026-11-13 22:54 UTC; cubren detecciones del 2026-11-12 y el 2026-11-13 UTC. Los hashes están en `tests/fixtures/firms_real/ORIGEN.md`. Reglas `armonizacion-0.3.0`.

| magnitud | valor |
|---|---|
| entrada (MODIS 3 787 + NOAA-20 15 977 + NOAA-21 14 102; Suomi NPP vacío) | 33 866 |
| cuarentena | 0 |
| aceptados (representantes) | 20 147 |
| deduplicados | 13 719 |
| — VIIRS agrupado con VIIRS | 12 972 |
| — MODIS agrupado con VIIRS (cruce de sensores) | 692 |
| — MODIS agrupado con MODIS | 55 |
| celdas-día | 18 115 |
| invariante entrada = aceptados + cuarentena + deduplicados | se cumple |

La mayor parte de la deduplicación ocurre **dentro de VIIRS**: varios píxeles de 375 m caen en la misma celda de ~1 km en la misma pasada. Por eso `n_detecciones` (representantes) no es comparable con los conteos brutos del visor de FIRMS. En la validación cruzada (H5) hay que usar `n_brutas`, que `celda_dia` conserva. Riesgo R-25.

