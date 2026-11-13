# Esquema FIRMS (MODIS C6.1 y VIIRS 375 m)

## BLOQUEO: sin acceso a CSV reales ni a la web
El trabajador que redactó este documento (fecha 2026-11-13) solo tuvo herramientas
de lectura/edición de archivos: **sin shell, sin curl y sin búsqueda web**. Por tanto:
- No se descargaron los CSV 24h de South America (no hay `data/raw/firms_24h_south_america/`).
- No se consultaron las tablas de atributos, FAQ, API ni página de cita.
- **Ningún dato de este documento está confirmado.** Todo es `por confirmar`.
  Los valores marcados *(recuerdo)* vienen de memoria del redactor, no de una fuente.
- No se hicieron commits (sin shell). Los archivos quedan sin versionar en el worktree.

Siguiente paso: un trabajador con red debe ejecutar la sección «Procedimiento de verificación».

## Tablas por variante y sensor
Aplica igual a las tres variantes (API NRT, API estándar/SP, archivo 24h) hasta verificar
diferencias. Estado de todas las filas: **por confirmar**. Fuente faltante: tabla de
atributos oficial en earthdata.nasa.gov (FIRMS) y cabecera de CSV real.

### VIIRS 375 m (VNP14IMGTDL_NRT, VJ114IMGTDL_NRT, VJ214IMGTDL_NRT) — orden (recuerdo)
| # | columna | tipo | dominio | descripción | estado | fuente |
|---|---|---|---|---|---|---|
| 1 | latitude | float | -90..90 | centro del píxel | por confirmar | tabla de atributos FIRMS |
| 2 | longitude | float | -180..180 | centro del píxel | por confirmar | ídem |
| 3 | bright_ti4 | float | K | temperatura de brillo I-4 | por confirmar | ídem |
| 4 | scan | float | por confirmar | tamaño de píxel along-scan | por confirmar | ídem |
| 5 | track | float | por confirmar | tamaño de píxel along-track | por confirmar | ídem |
| 6 | acq_date | fecha | formato por confirmar (recuerdo: YYYY-MM-DD) | fecha UTC | por confirmar | CSV real |
| 7 | acq_time | entero | formato por confirmar (recuerdo: HHMM UTC, ¿sin ceros a la izquierda?) | hora UTC | por confirmar | CSV real |
| 8 | satellite | texto | por confirmar (prototipo: N,1,2; recuerdo: N,N20,N21) | satélite | por confirmar | CSV real |
| 9 | instrument | texto | por confirmar (recuerdo: VIIRS) | instrumento | por confirmar | CSV real |
| 10 | confidence | texto | por confirmar (prototipo y recuerdo: l,n,h) | clase de confianza | por confirmar | FAQ FIRMS |
| 11 | version | texto | por confirmar (recuerdo: sufijo NRT en tiempo casi real) | colección/versión | por confirmar | CSV real |
| 12 | bright_ti5 | float | K | temperatura de brillo I-5 | por confirmar | tabla de atributos |
| 13 | frp | float | MW | potencia radiativa | por confirmar | tabla de atributos |
| 14 | daynight | texto | por confirmar (recuerdo: D,N) | día/noche | por confirmar | CSV real |

### MODIS C6.1 (MCD14DL) — orden (recuerdo)
Igual que VIIRS salvo: `brightness` (col. 3, en vez de bright_ti4), `bright_t31` (col. 12, en vez de bright_ti5) y `confidence` numérico 0–100 (por confirmar). `satellite` (prototipo T,A; recuerdo: Terra, Aqua) por confirmar. Todo: **por confirmar**.

## Diferencias entre variantes
Por confirmar. Hipótesis a contrastar: la columna `instrument` podría no aparecer en todas las variantes; el sufijo de `version` distingue NRT y estándar.

## API area (por confirmar; fuente: https://firms.modaps.eosdis.nasa.gov/api/area/, no consultada)
- Plantilla (recuerdo): `.../api/area/csv/<MAP_KEY>/<FUENTE>/<W,S,E,N>/<DAY_RANGE>[/<fecha>]`.
- Orden de coordenadas: W,S,E,N (recuerdo, por confirmar).
- DAY_RANGE máximo: por confirmar (recuerdo: 5).
- Límite de transacciones: por confirmar (recuerdo: 5000 por 10 min).
- Nombres de fuente (recuerdo): MODIS_NRT, MODIS_SP, VIIRS_SNPP_NRT, VIIRS_SNPP_SP, VIIRS_NOAA20_NRT, VIIRS_NOAA20_SP, VIIRS_NOAA21_NRT. Por confirmar con `data_availability`.
- Formato de MAP_KEY: por confirmar.

## Bbox del Huila (W,S,E,N)
Aproximado `-76.7,1.4,-74.3,3.9`, **por confirmar**. Falta fuente autoritativa (IGAC, DANE o geoBoundaries ADM1) y definir el margen.

## Decisiones abiertas
1. Códigos de satélite reales de VIIRS y MODIS (el prototipo `N,1,2` / `T,A` es sospechoso).
2. Dominio de `confidence` VIIRS y MODIS y clases oficiales FIRMS para los umbrales 30/80.
3. Formato de `acq_time` (ceros a la izquierda) y de `acq_date`.
4. Patrones de `version` NRT vs estándar.
5. DAY_RANGE máximo, límite de transacciones, existencia de VIIRS_NOAA21_SP.
6. Bbox y margen del Huila.
7. Colección de cada producto VIIRS y DOI.

## Procedimiento de verificación
Descargar con `curl` desde https://firms.modaps.eosdis.nasa.gov/active_fire/ los CSV 24h de South America (MODIS C6.1, SNPP, NOAA-20, NOAA-21) a `data/raw/firms_24h_south_america/<YYYYMMDD>/`; calcular `sha256sum`; leer con `python -I` pasando rutas como argumento; extraer cabecera y valores distintos; copiar cabecera + 25 filas a `tests/fixtures/firms_real/<nombre>_head.csv`; actualizar este documento y `src/ingest/firms_schema.py`.
