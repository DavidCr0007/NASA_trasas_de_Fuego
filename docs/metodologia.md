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

**D-01. Lector con validación de esquema.** El lector comprueba que las columnas del archivo coinciden con el esquema esperado para su sensor y variante. Las columnas hipotéticas (orden y nombres) están en `src/ingest/firms_schema.py` y **no están confirmadas**. Un archivo con esquema distinto se rechaza en lugar de interpretarse.

**D-02. Procedencia por registro.** Cada registro conserva:

- sensor (MODIS o VIIRS);
- satélite (código tal como aparece en el archivo; los códigos están **por confirmar**);
- colección o producto;
- hora UTC de la detección (`acq_date` + `acq_time`; formato **por confirmar**);
- fecha de descarga;
- hash SHA-256 del archivo fuente;
- calidad: NRT o estándar (a partir de la fuente y del campo `version`; patrones **por confirmar**).

**D-03. Validación de campos.** Cada registro se valida en:

- latitud y longitud dentro de rango y del bbox de trabajo;
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

## 7. Propuestas para hitos posteriores (no implementadas en H0–H2)

- Línea base celda-mes con percentil candidato P90 (`docs/decisiones/0004-percentil.md`).
- Mínimo de años de historia para la línea base (`docs/decisiones/0005-minimo-anios.md`).
