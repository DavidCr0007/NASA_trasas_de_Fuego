# ADR 0002: Umbrales de confianza en tres clases

## Estado

PROVISIONAL (H0). Los umbrales son configurables y no están validados contra la documentación oficial de FIRMS.

## Contexto

La confianza de cada detección se expresa de forma distinta según el sensor (R2):

- **MODIS:** valor numérico de 0 a 100 (dominio **por confirmar**).
- **VIIRS:** escala categórica `l`, `n`, `h` (prototipo y recuerdo; **por confirmar** con la FAQ de FIRMS).

Para comparar sensores hacen falta tres clases comunes: baja, nominal y alta. El prototipo fijó `MODIS_CONF_THRESHOLDS = {"nominal": 30, "alta": 80}` con el comentario «deben validarse con documentación del producto».

## Decisión

Asignar tres clases con estas reglas, todas PROVISIONALES:

- **MODIS:** < 30 → baja; 30 a 79 → nominal; ≥ 80 → alta.
- **VIIRS:** mapeo de las clases oficiales (`l` → baja, `n` → nominal, `h` → alta). Este mapeo es **por confirmar**.
- Umbrales configurables. Cualquier cambio cambia `RULES_VERSION`.
- Implementación (`harmonize.config.RulesConfig`): `modis_umbrales = {"nominal": 30, "alta": 80}` (PROVISIONAL); `viirs_mapa` se **deriva** de `ingest.firms_schema.CONFIANZA_VIIRS_VALORES` (estado «por confirmar»), por lo que sigue siendo PROVISIONAL. El dominio MODIS es el rango cerrado 0–100; NaN o texto no numérico → fuera de dominio. El valor VIIRS se compara sin espacios y en minúsculas.
- Si un registro aceptado por H1 no se puede clasificar, `harmonize_ingest` lo envía a cuarentena con `confianza fuera de dominio`.
- Valores fuera de dominio van a cuarentena con motivo (D-03 y D-04), no se clasifican.

## Alternativas

1. **Usar el valor oficial de cada sensor sin armonizar.** Descartada: impide comparar MODIS y VIIRS.
2. **Mapear MODIS con los cortes oficiales de clase (low, nominal, high) de FIRMS.** Más fiel a la fuente, pero los cortes **no están confirmados**. Pendiente.
3. **Cuantiles de la propia muestra.** Depende de la muestra y cambiaría con cada descarga. Descartada para H2.

## Consecuencias

- La clasificación es simple y transparente, y se puede revisar sin cambiar el código.
- Los resultados de confianza no deben presentarse como validados hasta confirmar los dominios y los cortes.
- Cada cambio de umbral obliga a registrar una nueva `RULES_VERSION`.

## Por confirmar

- Dominio de `confidence` de MODIS (0–100) y de VIIRS (`l`, `n`, `h`).
- Clases oficiales de FIRMS para MODIS y sus cortes.
- Mapeo oficial de `l`, `n`, `h` a las clases comunes.
- Si los cortes 30 y 80 son razonables para el área de estudio.
