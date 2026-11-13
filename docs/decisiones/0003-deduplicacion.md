# ADR 0003: Deduplicación en la misma celda con ventana de 3 horas

## Estado

PROVISIONAL (H0). La regla se implementará en H2 (R3). La limitación voraz está documentada en `docs/limitaciones.md`.

## Contexto

Un mismo incendio puede aparecer varias veces: en pasadas de distintos satélites, en productos NRT y estándar, o en píxeles VIIRS de 375 m de una misma pasada. Contarlos por separado infla los focos. Hace falta un criterio común para agrupar detecciones que probablemente describen el mismo evento (R3).

## Decisión

- Dos detecciones son candidatas si están en la **misma celda** (R1) y **|Δt| ≤ 3 h**.
- Agrupamiento **voraz con ancla**: se ordenan los registros por hora UTC; el primero abre un grupo y se añaden los que estén a ≤ 3 h **de ese primero**.
- Representante del grupo, por prioridad: VIIRS antes que MODIS; estándar antes que NRT; confianza mayor; hora UTC más temprana; `record_id`.
- Los duplicados se guardan en una **tabla aparte**, con referencia a su representante. No se borran (D-04).
- Se deduplica también dentro del mismo sensor, a propósito.

Algoritmo exacto implementado (`harmonize.rules.dedup`, `armonizacion-0.3.1`):

1. Ordenar todo por `(cell_id, fecha_hora_utc, record_id)`.
2. En cada celda, el primer registro sin asignar abre un grupo anclado en su hora `t0`; el grupo incluye todos los registros con `t ≤ t0 + ventana` (inclusivo). **No** se exige el mismo día UTC: un par 23:30–00:30 se deduplica.
3. Representante = mínimo de `(sensor != "VIIRS", calidad != "estandar", -rango_confianza, fecha_hora_utc, record_id)`, con rango alta=2, nominal=1, baja=0.
4. Los demás van a `deduplicados` con `dedup_de` (record_id del representante), `delta_t_min` (|Δt| respecto al representante, en minutos) y motivo `duplicado: misma celda y |Δt| <= 3 h`.
5. El representante lleva `n_fusionados` = número de registros que absorbió (0 si está solo).

El resultado es idéntico ante cualquier permutación de la entrada. La ventana de 3 h es PROVISIONAL.

## Alternativas

1. **Agrupamiento transitivo (componentes conexas).** Una cadena de registros cada uno a ≤ 3 h del anterior se agruparía entera, aunque el primero y el último estén muy alejados. Puede unir eventos distintos. Descartada por ahora; mayor riesgo de sobre-agrupar.
2. **Ventana fija por intervalos de tiempo** (por ejemplo, bloques de 3 h desde medianoche UTC). Simple, pero parte eventos que caen cerca de un límite. Descartada.
3. **Deduplicar solo entre sensores.** Evitaría el problema de los píxeles de una misma pasada, pero no lo resuelve. Descartada para H2; se puede revisar.

## Consecuencias

- El resultado depende del ancla (el primer registro por hora en la celda), no del orden de llegada. La regla no es transitiva: en el ejemplo de `docs/limitaciones.md`, C queda fuera aunque esté a 1,5 h de B.
- Los conteos deduplicados son **menores** que los registros brutos. Esto debe reportarse junto con el número de duplicados.
- La salida es determinista, porque el desempate final es `record_id` (necesario para D-06).

## Por confirmar

- Si una ventana de 3 h es adecuada para este tipo de focos (sin referencia publicada en esta sesión).
- Si conviene una versión transitiva o por ventana fija como comparación en una fase posterior.
