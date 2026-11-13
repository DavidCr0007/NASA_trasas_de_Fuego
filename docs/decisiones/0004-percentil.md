# ADR 0004: Percentil de la línea base para días inusuales (R5)

## Estado

ACEPTADA como parámetro (2026-11-13). El cálculo de días inusuales se implementa en H4. En H3 la API ya expone el percentil (`linea_base.percentil`).

## Contexto

R5 define la línea base como una **climatología por día del año**, con percentil configurable y 95 por defecto. Un día es inusual si su conteo en el área supera el percentil histórico de ese día del año. La versión anterior de este ADR proponía P90 sobre celda-mes; no coincidía con el requisito del reto y se corrigió.

## Decisión

- La climatología se calcula por día del año para el área de interés consultada.
- El percentil por defecto es **95** (`api.app.PERCENTIL_DEFECTO`), configurable con `create_app(percentil=…)`.
- Como métrica se usa `n_brutas`, el conteo original, para no depender de la deduplicación (R-25). Se confirmará al implementar H4.
- Solo se calcula si se cumple el mínimo de años (ADR 0005). Si no, la respuesta dice «base insuficiente».

## Alternativas

1. **P90.** Más sensible; marca más días.
2. **Media más k desviaciones estándar.** Supone una distribución que los conteos de focos, sesgados y con muchos ceros, no cumplen.
3. **Ventana móvil de ±k días alrededor del día del año.** Da más muestra por día. Queda como opción para H4 (por confirmar).

## Consecuencias

- Con pocos años, el P95 de cada día del año se apoya en muy pocos valores. De ahí el mínimo del ADR 0005.
- Cambiar el percentil por defecto obliga a subir `RULES_VERSION`.

## Por confirmar

- Si se usa ventana móvil y su ancho (H4).
- Si la métrica final es `n_brutas` o `n_detecciones`.
