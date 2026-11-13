# Limitaciones

Este documento recoge lo que el método no resuelve, lo que depende de supuestos provisionales y lo que todavía no está verificado. Debe leerse junto con `docs/metodologia.md` y `tasks/RIESGOS.md`.

## 1. Deduplicación voraz y no transitiva (R3)

La deduplicación agrupa cada detección con el **primer registro del grupo** (ancla), no con el último añadido. Por eso la relación «estar a ≤ 3 h» no es transitiva.

Ejemplo, en la misma celda:

- A a las 10:00 UTC;
- B a las 12:30 UTC;
- C a las 14:00 UTC.

A y B están a 2,5 h (dentro de la ventana), así que B entra en el grupo de A. C está a 1,5 h de B, pero a 4 h de A (ancla), así que **C queda fuera** del grupo aunque |C − B| = 1,5 h. C se trata como una detección independiente. El resultado depende del ancla (el registro más temprano de la celda sin asignar) y el método no lo corrige. Desde `armonizacion-0.2.0` la implementación ordena por `(cell_id, fecha_hora_utc, record_id)` antes de agrupar, de modo que la salida **no** depende del orden de llegada (probado con permutaciones); este ejemplo es una prueba (`test_contraejemplo_voraz_documentado`). La ventana no exige el mismo día UTC y se aplica también entre registros del mismo sensor. Desde `armonizacion-0.3.1`, `n_brutas` cuenta cada detección original en su propio día UTC, aunque su representante caiga en el día vecino. Para eso se emiten celdas-día con `n_detecciones = 0` y `n_brutas > 0`, de modo que la suma de `n_brutas` es igual a aceptados + deduplicados. Hasta 0.3.0 esas detecciones se perdían; lo descubrió la validación cruzada de H5 (ver `docs/metodologia.md` §10).

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

## 10. Naturaleza del dato (declaración obligatoria)

- **Los focos son detecciones térmicas, no incendios confirmados.** Un foco indica que un píxel tuvo una anomalía térmica cuando pasó el satélite. Puede ser una quema agrícola, un incendio forestal, una fuente industrial o un volcán; MODIS estándar trae el campo `type` (tabla oficial de atributos), pero NRT no. No se valida en campo.
- **Error de centro de píxel.** `latitude` y `longitude` son el centro del píxel (1 km nominal en MODIS y 375 m en VIIRS), no la posición del fuego. El fuego puede estar en cualquier punto del píxel, y el píxel crece hacia el borde del barrido (`scan` y `track`). La API publica un semilado **nominal** de 500 m (MODIS) y 187,5 m (VIIRS) por punto; no usa todavía `scan` ni `track` (riesgo R-26).
- **Saturación en VIIRS de 375 m.** La tabla oficial de atributos asigna confianza `high` a los píxeles saturados de la banda I-4. En esos píxeles la temperatura de brillo no es fiable, y FIRMS indica que el FRP de 375 m solo es fiable para fuegos pequeños o de baja intensidad. La armonización no corrige la saturación; `frp_max` y `frp_sum` deben leerse como indicativos.
- **Sesgo horario por la pasada de Terra.** Cada satélite observa a horas fijas: `horario_pasada_utc` las muestra para el área consultada. Si Terra deja de entregar datos, se pierde su pasada y la serie MODIS queda con menos horas muestreadas. Los conteos de antes y después no son comparables sin corrección, así que un descenso puede deberse al muestreo y no a menos fuego. Los CSV de 24 h del 2026-11-13 aún traen datos de Terra; la fecha de fin no está confirmada (R-08).
- **Datos NRT.** Los datos en tiempo casi real son preliminares y pueden cambiar cuando se publica la versión estándar. La API marca `preliminar=true` en cada día y en cada punto con datos NRT, y la exportación CSV lo declara en su encabezado (D-02).
- **Conteos tras deduplicar.** `n_detecciones` cuenta representantes de R3 y `n_brutas`, las detecciones originales. Con datos reales, el 40,5 % de las detecciones se agrupa, sobre todo dentro de VIIRS (R-25). Para comparar con el visor de FIRMS hay que usar `n_brutas`.

## 11. Línea base y días inusuales

- La API exige un mínimo de 5 años con dato en el área (D-08, ADR 0005). Por debajo responde «base insuficiente» y no marca días.
- **Falsos positivos esperados.** Con un P95, cerca del 5 % de los días de un año normal supera el umbral. «Inusual» significa por encima del P95 histórico, no anómalo con significación estadística.
- **Ventana de ±7 días PROVISIONAL** (ADR 0004). Sin ventana, con pocos años y focos dispersos, el umbral sería 0 y cualquier día con un foco saldría inusual.
- **Cobertura deducida de los datos.** Se toma del primer al último día con focos del conjunto procesado, no de las fechas de descarga del manifiesto. Si el último día descargado no tuvo focos, queda fuera de la cobertura (R-29).
- **Años con dato.** Un año cuenta para el mínimo si tiene al menos un foco en el área; no se exige que esté completo (ADR 0005).
- **Métrica.** Se usa `n_brutas` y no `n_detecciones`, para no depender de la deduplicación (R-25).
- **Sensores en el tiempo.** La línea base mezcla años con distinta combinación de sensores (Suomi NPP hasta su fin, NOAA-21 desde su lanzamiento). Un cambio de sensores puede desplazar la serie sin que cambie el fuego.

## 12. Lo que sigue por confirmar

El esquema se verificó el 2026-11-13 (`docs/esquema_firms.md`). Queda pendiente:

- La cabecera exacta y el formato de `confidence` que devuelve la API area: ¿`l`/`n`/`h` o `low`/`nominal`/`high`? (R-23).
- Los cortes oficiales de confianza MODIS; 30 y 80 siguen PROVISIONALES (ADR 0002).
- La colección de los productos VIIRS estándar y el DOI de cada producto (R-24).
- El bbox del Huila con fuente autoritativa (R-06).
- Si un año con dato cuenta aunque esté incompleto (ADR 0005).
- Las fechas de inicio de cada serie y el fin de misión de Terra y Aqua (R-08, R-15).
