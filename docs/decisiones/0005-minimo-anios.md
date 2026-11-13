# ADR 0005: Mínimo de años de historia para la línea base

## Estado

PROPUESTA para un hito posterior. **No implementada en H0–H2.** Valor por definir.

## Contexto

Una línea base celda-mes necesita historia suficiente para ser estable. Con pocos años, un percentil (ADR 0004) depende de muy pocos valores. Además, VIIRS tiene menos historia que MODIS (así lo indica el planteamiento del reto; la cifra exacta no está verificada). La hipótesis es que las series VIIRS (SNPP, NOAA-20 y NOAA-21) son más cortas que la de MODIS, pero las fechas exactas de inicio de cada serie **no están confirmadas**.

Actualmente solo se descarga el último año (véase `docs/limitaciones.md`), así que la línea base no puede calcularse de forma robusta todavía.

## Decisión

- Fijar un **mínimo de años de historia** por celda o por sensor antes de calcular una línea base.
- Valor por definir. No se implementa en H0–H2.
- Si una celda o sensor no cumple el mínimo, la línea base no se calcula y se marca como insuficiente, sin inventar valores.

## Alternativas

1. **Mínimo único para todos los sensores.** Simple, pero penaliza a VIIRS por su historia más corta.
2. **Mínimo distinto por sensor.** Más justo con VIIRS, pero complica la comparación entre sensores.
3. **Sin mínimo.** Descartada: produciría líneas base inestables.

## Consecuencias

- Puede que la línea base no esté disponible para VIIRS en una parte de las celdas durante varios años.
- Los resultados con línea base deben declarar el número de años usados.

## Por confirmar

- Valor del mínimo de años (por definir).
- Fechas exactas de inicio de la serie de cada producto (MODIS, VIIRS SNPP, NOAA-20, NOAA-21). **Por confirmar** con la documentación oficial de FIRMS.
- Si el mínimo debe ser distinto por sensor.
