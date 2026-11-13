# Limitaciones

Este documento recoge lo que el método no resuelve, lo que depende de supuestos provisionales y lo que todavía no está verificado. Debe leerse junto con `docs/metodologia.md` y `tasks/RIESGOS.md`.

## 1. Deduplicación voraz y no transitiva (R3)

La deduplicación agrupa cada detección con el **primer registro del grupo** (ancla), no con el último añadido. Por eso la relación «estar a ≤ 3 h» no es transitiva.

Ejemplo, en la misma celda:

- A a las 10:00 UTC;
- B a las 12:30 UTC;
- C a las 14:00 UTC.

A y B están a 2,5 h (dentro de la ventana), así que B entra en el grupo de A. C está a 1,5 h de B, pero a 4 h de A (ancla), así que **C queda fuera** del grupo aunque |C − B| = 1,5 h. C se trata como una detección independiente. El resultado depende del ancla (el registro más temprano de la celda sin asignar) y el método no lo corrige. Desde `armonizacion-0.2.0` la implementación ordena por `(cell_id, fecha_hora_utc, record_id)` antes de agrupar, de modo que la salida **no** depende del orden de llegada (probado con permutaciones); este ejemplo es una prueba (`test_contraejemplo_voraz_documentado`). La ventana no exige el mismo día UTC y se aplica también entre registros del mismo sensor. Además, el `n_brutas` de celda-día cuenta cada registro en su propio día UTC, mientras que `n_detecciones` cuenta representantes en el día del representante; un duplicado que cruza la medianoche puede hacer que ambas cifras no coincidan entre días vecinos.

## 2. Deduplicación dentro del mismo sensor

R3 no distingue sensores: también deduplica dentro de un mismo sensor. Esto es intencional, pero tiene efectos:

- Los píxeles VIIRS de 375 m de una misma pasada, dentro de la misma celda de ~1 km, pueden contarse como una sola detección. Esto reduce el número de focos frente al número de píxeles.
- Terra y Aqua (MODIS) pasan por la zona con diferencias de pocas horas; si ambas detectan el mismo foco dentro de 3 h, se consolidan en una sola.

Las consecuencias sobre conteos y sobre la comparación MODIS/VIIRS deben evaluarse antes de sacar conclusiones cuantitativas.

## 3. Grilla en grados

La grilla está fijada en grados (`CELL_DEG = 0.009`) sin factor de coseno. Las celdas tienen un ancho en km que varía algo con la latitud. En el Huila (aproximadamente 1–4° N) la distorsión es despreciable para este uso, pero no es nula. Si se amplía el área de estudio a latitudes mayores, debe revisarse la decisión (`docs/decisiones/0001-grilla.md`).

## 4. Fecha UTC y no hora local

La fecha de celda-día es **UTC**. Colombia usa UTC−5 sin horario de verano. Una detección nocturna local (por ejemplo, a las 21:00 hora local) cae en el día UTC siguiente. Los conteos diarios no corresponden al día calendario local. La hora UTC se conserva en cada registro para permitir otra agregación.

## 5. Umbrales de confianza provisionales (R2)

Los umbrales 30 y 80 para MODIS, y el mapeo de las clases VIIRS, son **PROVISIONALES**. No se han validado contra la documentación oficial de FIRMS ni contra una clasificación de referencia. Son configurables: cambiar un valor **por defecto** obliga a subir `RULES_VERSION` (lo vigila `test_config_defaults_y_congelada`); una configuración distinta pasada en ejecución no cambia `RULES_VERSION`, pero sí `config_fingerprint`, que queda en los metadatos Parquet y en `resumen.json` (`docs/decisiones/0002-umbrales-confianza.md`). Desde `armonizacion-0.3.0` el mapeo VIIRS usa los valores oficiales `low`/`nominal`/`high` (tabla de atributos FIRMS).

## 6. Bbox del Huila por confirmar

El bbox de descarga `(W, S, E, N) = (-76.7, 1.4, -74.3, 3.9)` es aproximado. **No está confirmado** contra una fuente autoritativa (IGAC, DANE o geoBoundaries ADM1) y el margen no está definido. Un bbox distinto cambia el conjunto de focos descargados.

## 7. Solo el último año descargado

La descarga cubre únicamente el último año. No hay historia suficiente para una línea base robusta. Esto afecta a la propuesta de percentil y de mínimo de años (`docs/decisiones/0004-percentil.md` y `docs/decisiones/0005-minimo-anios.md`). VIIRS además tiene menos historia que MODIS.

## 8. Reproducibilidad del hash

El hash del Parquet (D-06) depende de las versiones de las librerías fijadas en `uv.lock`, en particular de `pyarrow`. Si se actualiza `uv.lock`, el mismo crudo puede producir otro hash aunque las reglas no cambien. Por eso el hash debe reportarse junto con `RULES_VERSION` y con el `uv.lock` usado.

## 9. Datos de muestra sintéticos

`data/sample/` contiene datos **sintéticos** que imitan el esquema oficial. Sirven para `make demo` y para las pruebas. Ningún resultado de la muestra debe interpretarse como dato real de incendios. La descarga real requiere `FIRMS_MAP_KEY` en `.env`; si no existe, el proyecto registra el bloqueo B-01 (`tasks/RIESGOS.md`).

## 10. Cita y aviso no verificados

La cita oficial de FIRMS, el reconocimiento de LANCE y ESDIS, el aviso «as is» y los DOI de cada producto **por confirmar** (véase `docs/cita.md`). Hasta verificarlos, el proyecto no puede presentarse con una cita oficial completa.

## 11. Lista completa de «por confirmar»

Lista de lo que `docs/esquema_firms.md` deja sin verificar. Ninguno de estos valores debe usarse como cierto.

### 11.1 Columnas y tipos

- Orden y nombres de columnas de VIIRS 375 m (`VNP14IMGTDL_NRT`, `VJ114IMGTDL_NRT`, `VJ214IMGTDL_NRT`): recuerdo de 14 columnas, sin verificar.
- Orden y nombres de columnas de MODIS C6.1 (`MCD14DL`): recuerdo, sin verificar. Diferencias supuestas: `brightness` en lugar de `bright_ti4`, y `bright_t31` en lugar de `bright_ti5`.
- Tipo y dominio de `latitude` y `longitude`.
- Significado y unidades de `bright_ti4`, `bright_ti5`, `brightness`, `bright_t31` (K) y de `frp` (MW).
- Tamaño de píxel `scan` y `track`: unidades y dominio.
- Formato de `acq_date` (recuerdo: YYYY-MM-DD).
- Formato de `acq_time` (recuerdo: HHMM UTC; no se sabe si tiene ceros a la izquierda).
- Presencia de la columna `instrument` en todas las variantes.
- Valores de `daynight` (recuerdo: D y N).

### 11.2 Satélites

- Códigos de satélite de VIIRS: el prototipo usa `N`, `1` y `2`; el recuerdo sugiere `N`, `N20` y `N21`. **Ninguno confirmado.**
- Códigos de satélite de MODIS: el prototipo usa `T` y `A`; el recuerdo sugiere `Terra` y `Aqua`. **Ninguno confirmado.**

### 11.3 Confianza

- Dominio de `confidence` VIIRS: `l`, `n`, `h` (prototipo y recuerdo). **Por confirmar** con la FAQ de FIRMS.
- Dominio de `confidence` MODIS: 0–100. **Por confirmar.**
- Clases oficiales de FIRMS para MODIS (low, nominal, high) y sus cortes. **Por confirmar.** Los umbrales 30 y 80 son provisionales.

### 11.4 Calidad NRT y estándar

- Patrones de `version` para distinguir NRT de estándar (hipótesis: sufijo `NRT`). **Por confirmar.**
- Colección de cada producto VIIRS. **Por confirmar.**

### 11.5 API área

- Plantilla de URL: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/<FUENTE>/<W,S,E,N>/<DAY_RANGE>[/<fecha>]` (recuerdo). **Por confirmar.**
- Orden de coordenadas `W,S,E,N`. **Por confirmar.**
- Valor máximo de `DAY_RANGE` (recuerdo: 5). **Por confirmar.**
- Límite de transacciones (recuerdo: 5000 por 10 minutos). **Por confirmar.**
- Nombres de fuente: `MODIS_NRT`, `MODIS_SP`, `VIIRS_SNPP_NRT`, `VIIRS_SNPP_SP`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT` (recuerdo). **Por confirmar** con `data_availability`.
- Existencia de `VIIRS_NOAA21_SP`. **Por confirmar.**
- Formato de `FIRMS_MAP_KEY`. **Por confirmar.**

### 11.6 Bbox

- Coordenadas del bbox del Huila, margen y fuente autoritativa. **Por confirmar.**

### 11.7 Cita y licencia

- Cita oficial de FIRMS, reconocimiento de LANCE y ESDIS, aviso «as is» y DOI de cada producto. **Por confirmar** (véase `docs/cita.md`).

### 11.8 Verificación pendiente

- Los CSV de 24 horas de South America (MODIS C6.1, SNPP, NOAA-20, NOAA-21) no se han descargado. Sin ellos no hay cabeceras ni valores distintos verificados.
- Las tablas de atributos oficiales de MODIS C6.1 y de los productos VIIRS 375 m no se han consultado.
