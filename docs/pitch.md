# Pitch de 2 minutos: Harmonized Heat Neiva

Versión de reglas: `armonizacion-0.3.1`. Las cifras de este guion están sincronizadas con el código mediante `tests/test_documentos.py`. Cada cifra indica su fuente, su fecha y su calidad.

## Guion (≈ 270 palabras, 2:00)

**0:00 a 0:20. El problema.**
En el Huila, la temporada seca trae quemas que llegan a Neiva como humo y emergencias. NASA registra cada foco de calor desde el espacio, pero con dos sensores distintos: MODIS ve píxeles de 1 km y VIIRS de 375 m, y pasan a horas diferentes. Comparar un año con otro, o un sensor con otro, lleva a errores.

**0:20 a 0:55. Qué hicimos.**
Harmonized Heat Neiva lleva MODIS y VIIRS a una grilla común de 1 km. Elimina los focos que dos satélites ven repetidos con menos de 3 horas de diferencia, conserva el satélite, la hora UTC y la calidad de cada registro, y lo publica como un calendario de actividad. Las reglas están versionadas y cada resultado es reproducible: el mismo archivo crudo da el mismo hash.

**0:55 a 1:30. La demo.**
Elegimos un área (el Huila, Neiva o un rectángulo) y vemos el calendario del año. Los días inusuales superan el percentil 95 histórico de esa época del año. En la muestra *sintética* 2020–2026 aparece el periodo crítico inyectado: del **2026-08-10 al 2026-08-15**, 6 días con un máximo de 62 focos. Cada punto del mapa se dibuja con el tamaño de su píxel, porque el fuego no está en el centro exacto.

**1:30 a 1:50. Por qué confiar.**
Validamos el esquema con los archivos oficiales de FIRMS (NRT, 2026-11-13). En el área de estudio, el conteo independiente coincide foco por foco con el pipeline. Esa validación encontró y corrigió un error de medianoche. Con menos de 5 años de historia, la app responde «base insuficiente» en lugar de inventar.

**1:50 a 2:00. Cierre.**
Detecciones térmicas, no incendios confirmados, con su incertidumbre a la vista. Datos de NASA FIRMS (LANCE / ESDIS).

## Cifras y su fuente

| cifra | fuente | fecha | calidad |
|---|---|---|---|
| 1 km (MODIS) y 375 m (VIIRS) | Tabla oficial de atributos de FIRMS | consultada el 2026-11-13 | — |
| Periodo crítico 2026-08-10 a 2026-08-15 (6 días, máximo 62) | API sobre `data/processed/demo_historica` (muestra **sintética**, anomalía inyectada) | generada el 2026-11-13 | sintético; 2026 simula NRT |
| Conteo del Huila: 3 crudas = 3 `n_brutas` (2026-11-12) | `tools/validacion_cruzada.py` sobre los CSV de 24 h de FIRMS | descarga del 2026-11-13 22:54 UTC | NRT |
| Mínimo de 5 años y P95 | ADR 0005 y ADR 0004 | acordados el 2026-11-13 | — |

## Plan B si falla la demo en vivo

Capturas en `docs/capturas/` (ver `docs/checklist_entrega.md`) y la exportación CSV de ejemplo, que se genera con `make api` y el botón «Exportar CSV».
