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

## 7. API de consulta (H3)

`src/api/app.py` es una API de solo lectura (FastAPI + DuckDB) sobre los Parquet de `data/processed/`. Arranque local, sin red: `make api` (puerto 8000; documentación interactiva en `/docs`).

| ruta | qué devuelve |
|---|---|
| `GET /salud` | Estado; 503 si falta algún Parquet. |
| `GET /cita` | Cita y aviso oficiales, versión de reglas. |
| `GET /calendario?bbox=W,S,E,N[&desde&hasta]` | Serie diaria del área (calendario de actividad), calidad, incertidumbre y línea base. |
| `GET /calendario.csv?…` | La misma serie en CSV, con la cita, el aviso, la versión y la calidad como líneas `#`. |
| `GET /detecciones?bbox=…[&desde&hasta&limite]` | Representantes, cada uno con su semilado nominal. |

Toda respuesta trae `rules_version`, `config_fingerprint`, `cita` y `aviso` (D-05 y D-10).

- **Filtro del área.** Las celdas-día se filtran por su centroide y las detecciones, por su posición. Los días sin focos se rellenan con 0.
- **Calidad (D-02).** Cada día y la respuesta global tienen `calidad` (`NRT`, `estandar` o `mixta`) y `preliminar=true` si interviene algún dato NRT.
- **Incertidumbre (D-07).** Incluye:
  - `resolucion_m` y `semilado_nominal_m` por sensor, y `grilla_deg`;
  - `horario_pasada_utc`, con la hora UTC mínima y máxima observada y el número de detecciones por satélite en el área y el rango;
  - `clases_confianza`, con el conteo por clase;
  - `anios_con_dato`, los años con alguna celda-día en el área, sobre toda la historia;
  - `porcentaje_dias_con_dato`, la proporción de días del rango con al menos un foco.
- **Línea base (D-08).** `linea_base.estado` vale `"base insuficiente"` si `len(anios_con_dato) < anios_minimos` y `"suficiente"` en caso contrario. Se configura con `--anios-minimos`; el valor por defecto es 5 años, acordado con el equipo el 2026-11-13 (ADR 0005). El percentil por defecto es 95 (ADR 0004). Con base suficiente se calculan los días inusuales (sección 8).

## 8. Línea base, días inusuales y periodos críticos (R5, H4)

Implementación: `src/harmonize/linea_base.py`. Parámetros: ADR 0004 y ADR 0005.

1. **Serie del área.** Se suma `n_brutas` por día UTC en las celdas-día cuyo centroide cae en el área consultada, sobre **toda** la historia.
2. **Cobertura.** Va del primer al último día con datos del conjunto procesado. Dentro de ella, un día sin focos vale 0. Fuera de ella no hay observaciones: la API recorta el rango pedido a la cobertura e informa `desde_solicitado` y `hasta_solicitado`.
3. **Referencia de un día `t`.** Son los valores de los **otros** años (se excluye el año de `t`) en el mismo día del año ± `ventana_dias` (7 por defecto, PROVISIONAL), de forma circular sobre 365 días. El 29 de febrero se evalúa como 28 de febrero y no entra en la referencia.
4. **Umbral.** Percentil `p` (95 por defecto) de la referencia, con interpolación lineal.
5. **Inusual.** `n_brutas(t) > umbral`. Si la referencia tiene menos de `anios_minimos` años (5), el día queda sin umbral.
6. **Periodos críticos.** Rachas de días inusuales consecutivos (`periodos_inusuales`: inicio, fin, número de días y máximo).
7. **Temporada.** `climatologia_mensual` es la media de la suma mensual en los meses completos de la cobertura; `meses_pico` son los 3 meses de media más alta.

Interpretación: con un P95 sobre una serie estable se espera que ~5 % de los días supere el umbral aunque no pase nada raro. En la muestra histórica sintética, los años sin anomalía (2021–2025) dan entre 2,7 % y 7,9 %, con media de 4,6 %. La anomalía inyectada en agosto de 2026 se detecta como el periodo crítico más largo.

## 9. Interfaz (H4, H6)

`make api` sirve la interfaz en http://127.0.0.1:8000/ (ADR 0008). Funciona sin internet; las teselas base son opcionales.

- **Mapa.** Cada foco es un punto y un círculo del tamaño de su huella nominal (MODIS 1 km y VIIRS 375 m), con ventana de detalle: satélite, hora UTC, confianza, FRP, calidad y duplicados agrupados. El área se elige entre Huila, Neiva o un rectángulo dibujado.
- **Calendario de actividad.** Un año por vista, con color por `n_brutas`. Los días inusuales llevan borde violeta y los días con datos NRT, un punto blanco («preliminar»). Al hacer clic en un día, el mapa muestra solo ese día.
- **Panel.** Estado de la línea base (incluido «base insuficiente»), temporada mensual con meses pico, periodos críticos, metadatos de incertidumbre y versión de reglas.
- **Calidad y cita.** La insignia de calidad cambia a PRELIMINAR si hay NRT. El enlace «Exportar CSV» incluye cita, aviso, versión y calidad. El mapa lleva la atribución «NASA FIRMS (LANCE / ESDIS)» y el pie, la cita y el aviso completos (D-10).

La demo usa `data/sample_historica/`: datos **sintéticos** de 2020 a 2026 generados por `tools/generar_historico.py`, con un patrón estacional inventado y una anomalía inyectada del 10 al 16 de agosto de 2026.

**Origen de los datos (H6-01 y H6-02)**

- `origen_datos` aparece en `/calendario` y en `/detecciones` (y en la cabecera `# origen_datos:` de `/calendario.csv`). Vale `"sintetico"`, `"real"` o `"mixto"`, y `null` si no hay detecciones. Se calcula sobre la columna `sintetico` de `detecciones.parquet` de **todo** el conjunto, no solo del año o área consultados.
- La insignia junto a la de calidad muestra «DATOS SINTÉTICOS (demostración)», «Datos reales NASA FIRMS» o «Datos mixtos: reales y sintéticos». Si el origen es sintético, el resumen añade un aviso de demostración.
- `make api` sirve `data/processed/demo_historica/` (sintético, generado desde `data/sample_historica/`). `make api-real` sirve `data/processed/huila_real/`: historia real estándar del Huila 2016–2025, obtenida del archivo público de FIRMS por país (ADR 0009).

**Resumen y explicaciones (H6-04)**

- **En pocas palabras.** Resumen en lenguaje sencillo generado solo con la respuesta de `/calendario`: número de focos del año, días fuera de lo normal, periodo más crítico (con fechas) y temporada alta.
- **¿Qué significa?** Explicaciones breves junto a cada concepto:
  - *Foco de calor*: detección térmica de un píxel de satélite. **No es un incendio confirmado.**
  - *Día inusual*: día cuyo número de focos supera el P95 histórico del mismo día del año, con una ventana de ±7 días y sin contar el propio año. Como el umbral es un P95, ~5 % de los días normales también lo superan.
  - *NRT / preliminar*: datos casi en tiempo real que pueden corregirse después (D-02).
  - *Huella del píxel*: MODIS ~1 km y VIIRS ~375 m; el fuego está en algún punto del círculo.
  - *Base insuficiente*: el área tiene menos de 5 años de referencia, así que no se marcan días inusuales.
  - *Efecto de borde*: hacia los extremos del barrido el píxel crece.
- **Aviso de FIRMS.** La interfaz muestra la traducción «No usar para proteger vidas ni bienes» y cita el original en inglés, «Do not use for the preservation of life or property» (aviso de NASA FIRMS). El aviso va en un recuadro debajo del resumen, antes del mapa; la cita y el aviso completos siguen en el pie (D-10).
- **Formato.** Fechas legibles («12 ago 2026») con la fecha ISO al lado; números con formato es-CO (coma decimal, punto de miles) y unidades explícitas (focos, MW, metros, %).

**Tema claro y oscuro (H6-03)**

- Los colores son tokens CSS en `:root`. Siguen la preferencia de color del sistema (`prefers-color-scheme`) y el selector «Tema» permite forzar «Sistema», «Claro» u «Oscuro». La elección se guarda en `localStorage` con la clave `hhn-tema`, con `try/catch` por si el almacenamiento no está disponible. Un script en el `<head>` aplica el tema guardado antes de pintar, para evitar un destello.
- El contraste WCAG AA (texto ≥ 4,5:1; gráficos y foco ≥ 3:1) se calcula en `tests/test_interfaz.py` para ambos temas: escala del calendario e0..e4, días inusuales, puntos MODIS/VIIRS, insignias, cajas de aviso, popups y controles de Leaflet.
- Las teselas de OpenStreetMap se oscurecen con un `filter` CSS en el tema oscuro. El filtro no se aplica a los focos ni a la interfaz. Sin internet el mapa conserva su fondo neutro.

**Calendario accesible (H6-05)**

- Las celdas del calendario son navegables con teclado: flechas para moverse, Inicio y Fin para ir al primer y último día, y Enter para seleccionar. Tienen roles ARIA (`grid`, `row`, `gridcell`) y `aria-selected`. El día seleccionado queda resaltado y el tooltip propio muestra el detalle del día, fuera del `<title>` del navegador.
- La comparación «este año frente al promedio histórico mensual» es un SVG propio, sin librerías. El promedio incluye el año mostrado en sus meses completos, y así se indica en la propia vista.

**Robustez (H6-06)**

- `pedir()` lee el cuerpo de la respuesta una sola vez. Un `AbortController` y un contador por tipo de carga garantizan que solo se pinta la última respuesta, aunque el usuario cambie de área o de año mientras carga.
- Estados de carga, vacío y error con mensaje comprensible y botón «Reintentar». Un calendario sin días (`dias=[]`) se muestra como vacío, sin errores.
- Diseño responsive desde 375 px. La cita y el aviso rompen las palabras largas (`overflow-wrap`) y el calendario tiene desplazamiento propio, de modo que la página no tiene scroll horizontal.

## Prueba con datos reales (H0-07)

Fuente: CSV públicos de FIRMS de 24 h para South America. Calidad **NRT**; descargados el 2026-11-13 22:54 UTC; cubren detecciones del 2026-11-12 y el 2026-11-13 UTC. Los hashes están en `tests/fixtures/firms_real/ORIGEN.md`. Reglas `armonizacion-0.3.1` (las cifras no cambiaron respecto a 0.3.0).

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

## 10. Validación cruzada (H5)

### 10.1 Pipeline frente al archivo oficial

`tools/validacion_cruzada.py` cuenta por su cuenta, con el módulo `csv` y sin usar el lector del proyecto, las filas de cada CSV del manifiesto que caen en el área y el día UTC pedidos. Las compara con la salida del pipeline: `crudas = n_brutas + cuarentena`. Las pruebas (`tests/test_validacion_cruzada.py`) lo exigen para cada día de la muestra.

**Hallazgo.** En la primera ejecución sobre la muestra sintética, el 2026-11-10 dio **45 filas crudas frente a 44** (`n_brutas`) y 0 en cuarentena. Faltaba el duplicado MODIS de las 23:50 cuyo representante VIIRS cayó a las 00:20 del día siguiente: su celda-día no se emitía. Se corrigió en `armonizacion-0.3.1` (`harmonize.rules.celda_dia`), con una prueba del cruce de medianoche, y la diferencia quedó en 0.

**Resultado con datos reales.** Fuente: CSV de FIRMS de 24 h para South America. Calidad **NRT**; descargados el 2026-11-13 22:54 UTC. Reglas `armonizacion-0.3.1`.

| área | día UTC | crudas (MODIS / NOAA-20 / NOAA-21) | `n_brutas` | cuarentena | `n_detecciones` | diferencia |
|---|---|---|---|---|---|---|
| Huila (bbox aproximado `-76.7,1.4,-74.3,3.9`) | 2026-11-12 | 3 (2 / 1 / 0) | 3 | 0 | 3 | 0 |
| Huila | 2026-11-13 | 3 (0 / 1 / 2) | 3 | 0 | 3 | 0 |
| Colombia (bbox aproximado `-79.1,-4.3,-66.8,12.6`) | 2026-11-12 | 400 (17 / 122 / 261) | 400 | 0 | 305 | 0 |

El 2026-11-13 está **incompleto**: el archivo se descargó a las 22:54 UTC de ese día. Suomi NPP no aporta filas porque ya no entrega datos.

Para reproducirlo:

```bash
uv run python -I tools/validacion_cruzada.py data/raw/firms_24h_south_america/20261113 <salida> -76.7,1.4,-74.3,3.9 2026-11-12
```

**Resultado con historia real (ruta pública, ADR 0009).** Fuente: archivo anual por país de FIRMS, Colombia 2016–2025, recortado al Huila. Calidad **estándar**; descargado el 2026-11-13. Reglas `armonizacion-0.3.1`. Entrada: 84 833 detecciones, 0 en cuarentena; se cumple el balance de conteos.

| día UTC | crudas (MODIS / Suomi NPP / NOAA-20) | `n_brutas` | borde | sin explicar |
|---|---|---|---|---|
| 2024-09-15 (día de mayor actividad de 2024) | 426 (22 / 174 / 230) | 425 | 1 | 0 |
| 2025-03-25 | 205 (7 / 138 / 60) | 199 | 6 | 0 |
| 2024-02-10 | 2 | 2 | 0 | 0 |

«Borde» son los puntos dentro del bbox cuya celda de ~1 km tiene el centroide fuera: el pipeline asigna cada celda-día por su centroide. No hay pérdidas; la herramienta lo calcula e informa por separado (R-37).

### 10.2 Comparación con el visor de FIRMS (pendiente, H5-02)

Intento del 2026-11-13: el visor abre con un aviso que hay que aceptar, y aceptarlo requiere la decisión de una persona. Además, el conteo por área se hace dibujando a mano. Queda como paso manual. Para un día con historia estándar conviene usar el **2024-09-15** (`n_brutas` = 425 y 426 puntos en el bbox).

Requiere una persona frente al visor <https://firms.modaps.eosdis.nasa.gov/map/>:

1. Elegir el día UTC 2026-11-12 y las capas MODIS (C6.1), VIIRS NOAA-20 y VIIRS NOAA-21, sin Suomi NPP.
2. Dibujar el área del Huila (`-76.7,1.4,-74.3,3.9`) y contar los focos de cada capa; la herramienta de área del visor da el conteo.
3. Anotar los conteos en la tabla de abajo y explicar la diferencia con la fila de la tabla 10.1.

| fuente | MODIS | NOAA-20 | NOAA-21 | total | diferencia con `n_brutas` | explicación |
|---|---|---|---|---|---|---|
| visor de FIRMS, 2026-11-12, Huila (NRT) | por registrar | por registrar | por registrar | por registrar | por registrar | por registrar |
| visor de FIRMS, 2024-09-15, Huila (estándar) | por registrar | por registrar | por registrar | por registrar | por registrar | por registrar |

Causas esperables de diferencia:

- El visor puede mostrar «últimas 24 h» en lugar del día UTC.
- El visor y los archivos de 24 h se actualizan a horas distintas, y el NRT puede reprocesarse.
- Los focos en el borde del área: el visor filtra por punto y `n_brutas`, por centroide de celda.
- El visor puede tener activados filtros de capa o de confianza distintos a los de los archivos.

## 11. Bibliografía

Estudios de validación de los productos de fuego que cita la FAQ de FIRMS (detalle en `docs/cita.md`):

- Justice, C. O., et al. (2002). The MODIS fire products. *Remote Sensing of Environment*, 83, 244–262.
- Morisette, J. T., Giglio, L., Csiszar, I., & Justice, C. O. (2005). Validation of the MODIS active fire product over Southern Africa with ASTER data. *International Journal of Remote Sensing*, 26(19), 4239–4264.
- Morisette, J. T., et al. (2005). Validation of MODIS active fire detection products derived from two algorithms. *Earth Interactions*, 9(9), 1–25.
- Csiszar, I., Morisette, J. T., & Giglio, L. (2006). Validation of active fire detection from moderate-resolution satellite sensors: the MODIS example in Northern Eurasia. *IEEE Transactions on Geoscience and Remote Sensing*, 44(7), 1757–1764.
- Csiszar, I., et al. (2014). Active fires from the Suomi NPP Visible Infrared Imaging Radiometer Suite: product status and first evaluation results. *Journal of Geophysical Research: Atmospheres*, 119, 803–816.
- Schroeder, W., Oliva, P., Giglio, L., & Csiszar, I. (2014). The New VIIRS 375 m active fire detection data product: Algorithm description and initial assessment. *Remote Sensing of Environment*, 143, 85–96. Es la referencia del algoritmo VIIRS de 375 m.

Fuentes de datos y documentación: tabla de atributos MODIS/VIIRS, FAQ y API de FIRMS (consultadas el 2026-11-13; URL en `docs/esquema_firms.md`).

