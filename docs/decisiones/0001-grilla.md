# ADR 0001: Grilla común de 0,009° (≈ 1 km)

## Estado

PROVISIONAL (H0). Pendiente de validar con el equipo y de confirmar la equivalencia en km sobre el terreno.

## Contexto

Los focos de MODIS y VIIRS deben agruparse por celda (R1). El prototipo `Harmonize.py` calculaba la columna de la celda como `floor(lon · KM_POR_GRADO_EN_ECUADOR · cos(lat))`, con la latitud de **cada punto**. Como el factor de coseno cambia con la latitud, dos puntos de la misma columna podían caer en columnas distintas según su latitud. Así, la grilla quedaba **desalineada**: celdas vecinas no compartían fronteras comunes y la agregación por celda no era estable.

## Decisión

- Grilla fija en grados, sin factor de coseno por punto.
- `CELL_DEG = 0.009` (≈ 1 km en el Huila).
- Origen `(-90, -180)`, configurable.
- Índice: `fila = floor((lat + 90) / CELL_DEG)`, `columna = floor((lon + 180) / CELL_DEG)`.
- Todos los valores son configurables; cambiar un valor **por defecto** obliga a subir `RULES_VERSION` (lo vigila `test_config_defaults_y_congelada`); una configuración distinta pasada en ejecución no cambia `RULES_VERSION`, pero sí `config_fingerprint`, que queda en los metadatos Parquet y en `resumen.json`.
- Implementación (`harmonize.rules.cell_index`, `RULES_VERSION = armonizacion-0.3.1`): se usa `math.floor` sobre `(coordenada - origen) / cell_deg`. Un punto exactamente en un límite pertenece a la celda de índice **mayor**. Con `cell_deg = 0.009` (no representable en binario), un punto a ~1e-12° de un límite puede caer en la celda vecina por redondeo de coma flotante; es irrelevante a la precisión de FIRMS.
- `cell_id = "f{fila}_c{col}"`; el centroide es `(lat0 + (fila + 0.5)·cell_deg, lon0 + (col + 0.5)·cell_deg)`.
- La envoltura `cell_1km(lat, lon)` sigue existiendo y devuelve `(fila, col)`.

## Alternativas

1. **Mantener cos(lat) por punto (prototipo).** Descartada: produce columnas desalineadas.
2. **Cos(lat) de una latitud de referencia fija** (por ejemplo, la de Neiva). Más cercana a km reales, pero la celda deja de ser un rectángulo uniforme en grados para toda el área. Pendiente si se amplía el área.
3. **Proyección plana (UTM o equivalente de áreas).** Más precisa, con celdas de área constante. Mayor complejidad y dependencia de la zona UTM. Candidata para una versión posterior.
4. **Índices hexagonales (H3, S2).** Buenas propiedades geométricas, pero añaden dependencias y complican la trazabilidad a la grilla de FIRMS. Descartadas por ahora.

## Consecuencias

- Las celdas son reproducibles: el mismo punto siempre cae en la misma celda, sin depender de la latitud del vecino.
- El ancho real de la celda varía levemente con la latitud. En el Huila (≈1–4° N) la variación es despreciable para este uso (véase `docs/limitaciones.md`).
- Si se extiende el estudio a latitudes altas, esta decisión debe revisarse (alternativa 2 o 3).

## Por confirmar

- Medición exacta del ancho y alto de la celda en km en el bbox del Huila.
- Si el equipo acepta la aproximación de ~1 km para el reto o requiere celdas de área constante.
