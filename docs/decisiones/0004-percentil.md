# ADR 0004: Percentil de la línea base celda-mes

## Estado

PROPUESTA para un hito posterior. **No implementada en H0–H2.** Valor por definir.

## Contexto

Para decir si un mes de una celda tiene más focos de lo normal hace falta una línea base de referencia por celda y mes. Un umbral basado en un percentil alto de la historia de la celda permite marcar meses anómalos. El valor del percentil es una decisión de definición, no de código, y debe documentarse antes de implementarse.

## Decisión

- Proponer como candidato el **percentil 90 (P90)** de la línea base celda-mes.
- No implementar en H0–H2. El valor definitivo queda por definir.
- Depende de contar con historia suficiente (ADR 0005).

## Alternativas

1. **P75.** Más sensible, con más falsos positivos.
2. **P95.** Más conservador, con menos meses marcados y menos muestra por celda.
3. **Media más desviación estándar.** Supone una distribución que los conteos de focos probablemente no cumplen.
4. **Mediana.** Demasiado permisiva para marcar anomalías.

## Consecuencias

- Con solo un año de descarga (véase `docs/limitaciones.md`), una línea base celda-mes tiene muy pocos valores por celda. Un P90 sobre tan pocos datos es inestable.
- La decisión depende de ampliar la historia y de fijar el mínimo de años (ADR 0005).

## Por confirmar

- Valor final del percentil (candidato: 90).
- Si el percentil se aplica por celda o por bloque espacial.
- Comparación con alternativas sobre datos reales, cuando haya historia suficiente.
