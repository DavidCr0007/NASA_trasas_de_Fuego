# ADR 0007: Precedencia entre NRT y estándar

## Estado

PROVISIONAL (H0). Se aplica como parte de la prioridad del representante en R3.

## Contexto

Para una misma detección pueden existir dos registros: uno NRT (casi tiempo real, con correcciones posteriores pendientes) y otro estándar (procesado con más calma). FIRMS publica ambos. Si se conservan los dos, se cuentan dos veces; si se elige uno, hay que decidir cuál. La distinción entre NRT y estándar se hace a partir de la fuente y del campo `version`, cuyos patrones son **por confirmar**.

## Decisión

- Cuando NRT y estándar se solapan (misma celda y ventana de R3), se **prefiere el estándar** como representante.
- El NRT no se borra: pasa a la tabla de duplicados, con referencia al representante.
- Esta regla va después de la preferencia VIIRS > MODIS y antes de la confianza (R3).
- Implementación: es el segundo elemento de la clave del representante, `calidad != "estandar"`. Se compara solo el valor de `calidad` (`NRT` | `estandar`) que asignó H1; no se interpreta `version`.

## Alternativas

1. **Preferir siempre NRT** (más reciente). Descartada: el NRT puede tener correcciones pendientes.
2. **Conservar ambos en la salida.** Descartada: duplica conteos.
3. **Preferir el de confianza mayor, sin mirar la calidad.** Mezcla dos criterios y puede elegir un NRT sin revisar.

## Consecuencias

- Los resultados del periodo más reciente pueden cambiar cuando FIRMS publique la versión estándar. Esto debe quedar reflejado en la trazabilidad (hash del archivo fuente y fecha de descarga).
- Si no hay estándar para un evento, el NRT se conserva como representante.

## Por confirmar

- Patrones de `version` que distinguen NRT de estándar (hipótesis: sufijo `NRT`). **Por confirmar.**
- Disponibilidad y retraso de la versión estándar por sensor. **Por confirmar.**
- Si la fuente `*_SP` de la API corresponde a la versión estándar. **Por confirmar.**
