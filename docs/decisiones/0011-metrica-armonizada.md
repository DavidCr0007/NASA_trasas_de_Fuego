# ADR 0011: Métrica armonizada «celdas activas equivalentes» e intercalibración MODIS–VIIRS

## Estado

ACEPTADA (2026-11-14), H8-02. Versión de la métrica: `celdas-eq-1.1.0` (1.1.0, ADR 0012: sin era Suomi NPP se cuentan todas las constelaciones «sin calibrar»). La línea base R5 la usa por defecto (`r5-1.1.0`).

## Contexto

El reto pide que, tras la armonización, «el sensor de origen ya no importe». Con datos reales del Huila (archivo por país de FIRMS, calidad estándar, filtro por forma real), el conteo de detecciones no cumplía esa condición:

| cambio de constelación | conteo bruto (`n_brutas`) |
|---|---|
| 2012, entra Suomi NPP (2008–2011 → 2012–2015) | 110 → 810 por año (× 7,4) |
| 2018, entra NOAA-20 (2014–2017 → 2018–2021) | 805 → 1 388 por año (× 1,7) |

Hay dos causas:
- **Resolución:** un fuego que MODIS ve como 1 píxel de 1 km, VIIRS lo ve como varios píxeles de 375 m.
- **Constelación:** cuantos más satélites, más pasadas y más detecciones del mismo fuego.

## Decisión

1. **Contar celdas, no detecciones.** La métrica diaria es el número de celdas de ~1 km (R1) con al menos una detección. Así se elimina el efecto de resolución.
2. **Constelación de referencia fija:** R = MODIS (Terra y Aqua) ∪ Suomi NPP, disponible en todo 2012–2025. Las detecciones de NOAA-20 y NOAA-21 no cambian la métrica mientras Suomi NPP está disponible.
3. **Intercalibración en la superposición**, con factores calculados sobre todo el conjunto procesado:
   - **Era solo MODIS** (antes de Suomi NPP): MODIS × k_M[mes], con k_M[mes] = Σ R / Σ MODIS en los días de la era de Suomi NPP de ese mes del año. Si el mes tiene menos de 30 celdas MODIS, se usa el factor global.
   - **Después de Suomi NPP** (deja de entregar datos nuevos en noviembre de 2026): (MODIS ∪ NOAA-20) / k_N20, con k_N20 = Σ (MODIS ∪ NOAA-20) / Σ R en los días en que coinciden.
4. La API informa en cada respuesta la métrica, la versión, los factores, sus años y las eras. `metrica=n_brutas` sigue disponible para comparar con el visor de FIRMS.

## Resultado (Huila por forma real, 2001–2025, calidad estándar)

- **Factores:** k_M global = 4,34 (entre 3,95 y 5,18 según el mes); k_N20 = 1,00.
- **Salto de 2012:** la métrica armonizada pasa de 488 a 655 celdas activas por año (× 1,3), frente al × 7,4 del conteo bruto.
- **Salto de 2018:** pasa de 650 a 651 (× 1,00), frente al × 1,7 del conteo bruto.
- **Años con más actividad:** 2024, 2023 y 2020.
- **Detección de anomalías:** en la muestra sintética, la anomalía inyectada en agosto de 2026 se sigue detectando con la métrica armonizada.

## Alternativas descartadas

- **Usar solo MODIS en toda la serie:** es consistente, pero desperdicia el detalle de VIIRS (el reto pide combinarlos) y MODIS está terminando su vida útil.
- **Usar todas las fuentes sin calibrar:** mantiene los saltos de constelación.
- **Calibrar por regresión día a día:** demasiado ruidosa con conteos pequeños por área.

## Consecuencias y límites

- **Precisión:** la era solo MODIS (2001–2011) tiene más incertidumbre, porque k_M escala detecciones que MODIS no vio y supone que la relación de 2012–2025 se mantiene.
- **Origen de los factores:** se estiman en el conjunto procesado, el recuadro del Huila. Para otras regiones conviene recalcularlos con sus propios datos.
- **Unidades:** la métrica cuenta celdas, no fuegos. Un fuego grande que cubre varias celdas cuenta varias veces.
- **Versionado:** cualquier cambio en la referencia, los factores o el mínimo de 30 celdas obliga a subir `VERSION_METRICA`.
