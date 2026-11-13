# ADR 0005: Mínimo de años de historia para la línea base (D-08)

## Estado

IMPLEMENTADA en H3 como control (2026-11-13). El **valor por defecto es PROVISIONAL**: 5 años.

## Contexto

Un percentil por día del año (ADR 0004) necesita varios años para no depender de unos pocos valores. MODIS tiene una serie más larga que VIIRS. La API responde por el área de interés, así que el control se aplica a los años con dato del área.

## Decisión

- La API cuenta los años distintos con al menos una celda-día en el área (`incertidumbre.anios_con_dato`).
- Si son menos que `anios_minimos`, `linea_base.estado = "base insuficiente"` y no se calculan días inusuales.
- `anios_minimos` es configurable: `create_app(anios_minimos=…)` o `python -m api --anios-minimos N`.
- Valor por defecto: **5 (PROVISIONAL)**. La respuesta lo indica en `linea_base.nota`. Es un supuesto de trabajo, no un valor validado.

## Alternativas

1. **Mínimo distinto por sensor.** Más justo con VIIRS, pero la línea base es armonizada (MODIS + VIIRS) y separar por sensor rompe la comparabilidad.
2. **Contar solo años completos.** Más estricto. Hoy cuenta cualquier año con dato; queda por confirmar.
3. **Sin mínimo.** Descartada: produciría líneas base inestables.

## Consecuencias

- Con la muestra local (un solo año) y con la descarga de un año del Huila, la respuesta será «base insuficiente». Para H4 hace falta descargar más historia.
- Cambiar el valor por defecto obliga a subir `RULES_VERSION`.

## Por confirmar

- El valor definitivo del mínimo (riesgo R-27).
- Si un año cuenta solo cuando está completo.
- Las fechas exactas de inicio de cada serie (MODIS, VIIRS SNPP, NOAA-20 y NOAA-21).
