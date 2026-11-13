# Esquema FIRMS (MODIS C6.1 y VIIRS 375 m)

Verificado el 2026-11-13. Las constantes viven en `src/ingest/firms_schema.py`.

## Fuentes

| clave | fuente | fecha |
|---|---|---|
| [A] | Tabla oficial de atributos MODIS/VIIRS: <https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs> | 2026-11-13 |
| [F] | FAQ de FIRMS: <https://www.earthdata.nasa.gov/data/tools/firms/faq> | 2026-11-13 |
| [P] | Documentación de la API area: <https://firms.modaps.eosdis.nasa.gov/api/area/> | 2026-11-13 |
| [C] | CSV públicos de 24 h para South America (NRT), descargados el 2026-11-13 22:54 UTC; recortes en `tests/fixtures/firms_real/` | 2026-11-13 |

Los conteos de [C] son de calidad **NRT** (preliminar), fueron descargados el 2026-11-13 y cubren South America entre el 2026-11-12 y el 2026-11-13 UTC:

| archivo | filas | `satellite` | `confidence` | `version` |
|---|---|---|---|---|
| `MODIS_C6_1_South_America_24h.csv` | 3 787 | T 1 224 · A 2 563 | 0 a 99 (entero) | 6.1NRT |
| `J1_VIIRS_C2_South_America_24h.csv` | 15 977 | N20 | low 801 · nominal 14 332 · high 844 | 2.0NRT |
| `J2_VIIRS_C2_South_America_24h.csv` | 14 102 | N21 | low 1 256 · nominal 12 236 · high 610 | 2.0NRT |
| `SUOMI_VIIRS_C2_South_America_24h.csv` | 0 (solo cabecera) | — | — | — |

El archivo de Suomi NPP llega vacío, lo que coincide con el aviso de [A]: «Suomi NPP is no longer delivering new data».

## Columnas (confirmadas en [C], descritas en [A])

**VIIRS 375 m** (VNP14IMGTDL_NRT, VJ114IMGTDL_NRT, VJ214IMGTDL_NRT), en este orden:
`latitude, longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, confidence, version, bright_ti5, frp, daynight`

**MODIS C6.1** (MCD14DL NRT), en este orden:
`latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, version, bright_t31, frp, daynight`

- Ninguno de los dos trae la columna `instrument`. La hipótesis del prototipo queda refutada.
- MODIS estándar (MCD14ML) añade `type` (0 vegetación presunta, 1 volcán, 2 otra fuente terrestre estática, 3 costa afuera) [A]. El lector la tolera como columna extra.
- `latitude` y `longitude` son el centro del píxel: 1 km nominal en MODIS y 375 m en VIIRS [A].
- `acq_date` usa el formato `YYYY-MM-DD` [C].
- `acq_time` va en HHMM UTC con 4 dígitos y ceros a la izquierda, por ejemplo `0017` [C]. El lector también acepta 1 a 3 dígitos por robustez.
- `daynight` toma los valores `D` y `N` [A][C].

## Códigos de satélite

| código | satélite | fuente |
|---|---|---|
| `N` | Suomi NPP (solo histórico) | [A] |
| `N20` | NOAA-20 | [A][C] |
| `N21` | NOAA-21 | [A][C] |
| `T` | Terra | [A][C] |
| `A` | Aqua | [A][C] |

Quedan **refutados** los códigos del prototipo `1` y `2` para VIIRS y los nombres `Terra` y `Aqua` en MODIS: no aparecen en [A] ni en [C].

## Confianza

- **VIIRS:** `low`, `nominal` y `high` [A][F][C]. Los criterios son estos [A]:
  - `low`: de día, con reflejo solar y anomalía I-4 menor de 15 K.
  - `nominal`: sin reflejo solar y con anomalía mayor de 15 K.
  - `high`: píxeles saturados, de día o de noche.
  - FIRMS NRT elimina los `low` nocturnos de la Anomalía Magnética del Atlántico Sur.
- La variante `l`/`n`/`h` del prototipo no aparece en ninguna fuente. Se acepta solo como posible formato de la API area, **por confirmar** (R-23).
- **MODIS:** de 0 a 100 % [A][F]. Las fuentes dicen que el porcentaje se agrupa en baja, nominal y alta, pero **no publican los cortes** en las páginas consultadas. Los umbrales 30/80 siguen PROVISIONALES (ADR 0002).

## `version` y calidad

[A] da `6.1URT`, `6.1RT` y `6.1NRT` para MODIS en tiempo casi real y `6.1` para el estándar. [C] muestra `6.1NRT` y `2.0NRT`.

- Patrón NRT: `^\d+(\.\d+)*(NRT|URT|RT)$`. URT y RT, aún más preliminares, se tratan como NRT.
- Patrón estándar: `^\d+(\.\d+)*$`.
- La colección de VIIRS es la **2** (`2.0NRT` y el nombre `VIIRS_C2` en [C]), aunque [A] aún menciona `1.0`. La colección de los productos VIIRS estándar sigue **por confirmar**.

## API area [P]

- Plantilla: `/api/area/csv/<MAP_KEY>/<FUENTE>/<W,S,E,N>/<DAY_RANGE>[/<YYYY-MM-DD>]`. La fecha es opcional; con ella devuelve el intervalo de `fecha` a `fecha + DAY_RANGE − 1`.
- `DAY_RANGE`: de 1 a 5.
- Límite: 5 000 transacciones por intervalo de 10 minutos. Las peticiones grandes pueden contar como varias transacciones.
- Fuentes: `MODIS_NRT`, `MODIS_SP`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT`, `VIIRS_NOAA21_SP`, `VIIRS_SNPP_NRT`, `VIIRS_SNPP_SP` (y `LANDSAT_NRT`, solo para EE. UU. y Canadá).
- Disponibilidad por fecha: `/api/data_availability/`.
- **Por confirmar:** la cabecera exacta que devuelve la API. Se asume igual a [C] y se verificará con la primera descarga con `MAP_KEY` (bloqueo B-01).

## Pendiente

1. Cabecera y formato de `confidence` en la API area (R-23).
2. Cortes oficiales de confianza MODIS, si existen en la documentación del algoritmo C6.1.
3. Colección de los productos VIIRS estándar (SP) y DOI de cada producto (R-24).
4. Bbox del Huila con fuente autoritativa: IGAC, DANE o geoBoundaries (R-14).
