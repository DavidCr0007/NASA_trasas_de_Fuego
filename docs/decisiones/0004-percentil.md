# ADR 0004: Percentil de la línea base para días inusuales (R5)

## Estado

ACEPTADA (2026-11-13). El percentil se fijó en H3 y el cálculo se implementó en H4 (`harmonize.linea_base`). La ventana de ±7 días es PROVISIONAL.

## Contexto

R5 define la línea base como una **climatología por día del año**, con percentil configurable y 95 por defecto. Un día es inusual si su conteo en el área supera el percentil histórico de ese día del año. La versión anterior de este ADR proponía P90 sobre celda-mes; no coincidía con el requisito del reto y se corrigió.

## Decisión

- La climatología se calcula por día del año para el área de interés consultada.
- El percentil por defecto es **95** (`api.app.PERCENTIL_DEFECTO`), configurable con `create_app(percentil=…)`.
- Como métrica se usa `n_brutas`, el conteo original, para no depender de la deduplicación (R-25).
- La referencia de cada día se toma de los **otros** años (se excluye el año evaluado), el mismo día del año ± `ventana_dias`. Por defecto son **7 días (PROVISIONAL)**, configurables con `create_app(ventana_dias=…)`. Sin ventana, con pocos años y focos dispersos, el P95 de un solo día suele valer 0 y cualquier foco saldría inusual.
- Solo se calcula si se cumple el mínimo de años (ADR 0005). Si no, la respuesta dice «base insuficiente».

## Alternativas

1. **P90.** Más sensible; marca más días.
2. **Media más k desviaciones estándar.** Supone una distribución que los conteos de focos, sesgados y con muchos ceros, no cumplen.
3. **Sin ventana (±0 días).** Es la lectura literal de R5, pero con 5 a 7 años da umbrales de 0 en la mayor parte del año.
4. **Incluir el año evaluado en su propia referencia.** Se descarta porque amortigua justamente los días extremos que se quieren detectar.

## Consecuencias

- Con pocos años, el P95 de cada día del año se apoya en muy pocos valores. De ahí el mínimo del ADR 0005 y la ventana.
- En un año normal se espera que ~5 % de los días supere el umbral (R-31).
- Cambiar el percentil por defecto obliga a subir `RULES_VERSION`.

## Por confirmar

- El ancho definitivo de la ventana (±7 días es provisional), que debe validarse con datos reales del Huila.
