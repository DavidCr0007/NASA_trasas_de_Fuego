# Datos de muestra SINTÉTICOS

Los archivos `SINTETICO_<FUENTE>_huila.csv` **son sintéticos**: imitan el
esquema de FIRMS tal como está en `src/ingest/firms_schema.py` (aún
**por confirmar** contra los CSV oficiales) y **no son observaciones reales**.
Sirven solo para la demo offline (`make demo`) y las pruebas.

- Los genera `tools/generar_muestra.py`, de forma determinista (`uv run python tools/generar_muestra.py`).
- `manifest.jsonl` registra SHA-256, `sintetico=true`, `fecha_descarga=2026-11-13T00:00:00Z` y `url_sin_clave=null`.
- Códigos de satélite y `version` usados (`Terra`, `Aqua`, `N`, `N20`, `N21`, `6.1NRT`, `2.0NRT`, …) son hipótesis por confirmar.
- Cita y aviso «as is» de los datos reales de FIRMS: ver `docs/cita.md`.

## Casos incluidos (132 filas: 126 aceptadas, 6 en cuarentena)

| Caso | Fuente(s) | Resultado esperado |
|---|---|---|
| C1 MODIS + VIIRS misma celda, Δt = 85 min (2.505, −75.285; 2026-11-10 17:05 y 18:30) | MODIS_NRT, VIIRS_NOAA20_NRT | Ambas aceptadas; H2 deduplica y conserva VIIRS |
| C2 misma celda, Δt = 6 h 50 min (2.535; 06:35 y 13:25) | MODIS_NRT, VIIRS_NOAA21_NRT | Ambas aceptadas; no se deduplican |
| C3 misma detección en NRT y SP (2.565; 2026-11-11 18:40) | MODIS_NRT, MODIS_SP | Ambas aceptadas; tratamiento por decidir en H2 (misma fuente de sensor) |
| C5 cruce de medianoche UTC (2.625; 2026-11-10 23:50 y 2026-11-11 00:20, `acq_time` = `20`) | MODIS_NRT, VIIRS_NOAA20_NRT | Ambas aceptadas; H2 deduplica y conserva VIIRS |
| `acq_time` sin ceros (filas base 4 y 12 de cada archivo) | todas | Aceptadas |
| C6 latitud 95 | MODIS_NRT | Cuarentena: `latitud fuera de rango` |
| C7 fecha `2026-13-45` | VIIRS_SNPP_SP | Cuarentena: `fecha/hora inválida` |
| C8 confianza 150 (MODIS) y `x` (VIIRS) | MODIS_SP, VIIRS_NOAA21_NRT | Cuarentena: `confianza fuera de dominio` (×2) |
| C9 satélite `ZZ` | MODIS_NRT | Cuarentena: `satélite no reconocido` |
| C10 código `N` en la fuente NOAA-20 | VIIRS_NOAA20_NRT | Cuarentena: `satélite inconsistente con la fuente` |
