# Auditoría técnica de segunda fase

Harmonized Heat Neiva · NASA Space Apps Challenge 2026 · 15 de noviembre de 2026.

## Dictamen

**Conformidad técnica condicionada para demostración.** Se verificaron interacciones reales, endpoints, exportaciones y artefactos locales. La demo pública funciona y declara datos sintéticos; ese aviso debe conservarse. Las cifras heurísticas de la auditoría preliminar no se reinterpretan como métricas de calidad certificadas.

La trazabilidad operativa mejoró: ahora se publican el linaje de los conjuntos, la procedencia de cada detección y el método. **La exactitud científica, la cobertura efectiva de observaciones y la accesibilidad completa siguen sin certificarse.** Tener hashes correctos y pruebas automatizadas no resuelve esas tres cuestiones.

## Versiones y evidencia

El repositorio comenzó en `c1d237116baf5851873d17d5cf16f205f1cf46f4`, rama `feat/globo-global`. Durante la revisión se incorporó la revisión `fefb67fa4727cf8d62fc54ac754213be921cfcf9` y el despliegue pasó a exponer los nuevos endpoints. Se separan las mediciones para no atribuir los resultados de una versión a otra.

| Ámbito | Resultado | Evidencia |
|---|---|---|
| Despliegue inicial | 11 de 15 criterios conformes; faltaban linaje público y documentos metodológicos accesibles desde endpoints. | [JSON inicial](evidencias/auditoria_tecnica_20261115/despliegue_antes.json) |
| Despliegue tras la actualización observada | 16 de 16 criterios conformes, incluido el vínculo de los registros al manifiesto. No incluye verificar crudos remotos. | [JSON posterior](evidencias/auditoria_tecnica_20261115/despliegue_despues.json) |
| Conjunto real local | 19 de 19 criterios conformes, con verificación de hashes de entradas y salidas. | [JSON real](evidencias/auditoria_tecnica_20261115/local_real_despues.json) |
| Demo histórica local | 19 de 19 criterios conformes, incluidos hashes. | [JSON demo](evidencias/auditoria_tecnica_20261115/local_demo_despues.json) |
| Navegador público | 13 de 13 comprobaciones; los alcances parciales de F04 y F10 se explican abajo. | [Origen resuelto](capturas/auditoria_tecnica_publica_20261115/01_origen_resuelto.png), [ficha](capturas/auditoria_tecnica_publica_20261115/02_ficha_foco.png), [móvil](capturas/auditoria_tecnica_publica_20261115/03_movil.png) |
| Navegador local corregido | 15 de 15, añadiendo una prueba con demora de 1,5 s para la carga de focos y el encuadre de la ficha expandida. | [Ficha con linaje](capturas/auditoria_tecnica_local_20261115/02_ficha_foco.png), [móvil](capturas/auditoria_tecnica_local_20261115/03_movil.png) |
| Suite del repositorio | 539 pruebas correctas. Una advertencia de deprecación de Starlette TestClient. | `uv run pytest -q --tb=line` |

Los criterios adicionales locales corresponden a verificaciones de artefactos que no se pueden ejecutar contra un endpoint sin acceso a sus archivos. Estas proporciones no son puntuaciones de exactitud ni de conformidad WCAG.

Endpoints públicos comprobados: [salud](https://nasa-trasas-de-fuego.vercel.app/salud), [procedencia](https://nasa-trasas-de-fuego.vercel.app/procedencia), [metodología](https://nasa-trasas-de-fuego.vercel.app/metodologia), [limitaciones](https://nasa-trasas-de-fuego.vercel.app/limitaciones). Los JSON de evidencia conservan la hora UTC de cada medición.

## Hallazgos y correcciones

| Prioridad | Hallazgo comprobado | Acción y estado |
|---|---|---|
| P0 | `HHN_DATOS` configurado con una ruta inexistente terminaba sustituyéndose por la muestra sintética. | Se rechaza la configuración explícita inválida. La demo automática se conserva solo para el arranque sin una ruta explícita. Prueba de regresión en `tests/test_vercel.py`. |
| P0 | El origen del conjunto se deducía solo de los representantes. Un registro sintético absorbido por deduplicación podía quedar fuera de esa clasificación, aunque participe en la métrica armonizada. | Se consideran representantes y deduplicados; se verifica un caso con representantes reales y duplicados sintéticos. API, calendario y globo informan `mixto`. |
| P1 | El pipeline conservaba archivo, fila y checksum, pero el JSON y el CSV públicos de detecciones no los exponían. | Se añadieron producto, colección, archivo, registro, checksum, descarga UTC, naturaleza sintética, reglas y `dataset_id`. La ficha los agrupa en «Procedencia del registro». |
| P1 | No existía un linaje público separado para el análisis y el globo. | `/procedencia` expone ambos conjuntos y si coinciden; `/salud` añade naturaleza y estado de procedencia. El endpoint distingue expresamente linaje declarado de verificación de crudos. |
| P1 | El método existía en el repositorio, pero no había enlaces directos desde el aplicativo. | «Validar datos y método» enlaza `/procedencia`, `/metodologia` y `/limitaciones`. La configuración de Vercel incluye los documentos y sigue excluyendo las capturas voluminosas. |
| P1 | Parte de `docs/limitaciones.md` y una nota de la API afirmaban que la línea base usaba siempre `n_brutas`; el código usa la métrica armonizada por defecto. | Se sincronizaron las notas con la métrica activa y se documentó el caso «sin calibrar». |
| P1 | El panel retiraba `aria-busy` antes de terminar de recibir sus detecciones. | Se mantiene ocupado hasta completar o fallar la petición de focos. Verificado localmente con demora deliberada; este ajuste final de interfaz no se da por publicado por el solo hecho de que los endpoints ya estén actualizados. |
| P2 | Expandir el linaje podía dejar la cabecera de la ficha fuera del mapa. | Se limita la altura con un único desplazamiento y se recalcula el anclaje al desplegar. Se comprobó que la ficha expandida queda dentro del lienzo. |
| P1 | Al dibujar o cambiar explícitamente el área podía conservarse una tarjeta de zona anterior; una búsqueda remota sin polígono también podía conservar un contorno previo. | Se limpia la selección anterior en esos cambios de contexto. La búsqueda de una nueva zona mantiene su propio resaltado cuando hay geometría. |
| Aclaración | La página HTML inicial decía «Origen desconocido», «Actualizando» y «Cargando». | En un navegador con JavaScript terminaron resolviéndose; no se confirmó una carga perpetua. Los estados iniciales recuperados como texto no demuestran un fallo de ejecución. |
| Aclaración | La página advierte que usa datos inventados. | Se confirmó que el despliegue usa la demo sintética deliberadamente. No se eliminó la advertencia ni se etiquetó esa muestra como observaciones reales. |

## Matriz F01–F10

| Prueba de la auditoría preliminar | Resultado de esta fase |
|---|---|
| F01 Buscar Neiva y centrar el municipio | Conforme. Búsqueda local, zona municipal y centro comprobados en Chrome. |
| F02 Cambiar de año | Conforme para un año distinto de la demo: el año del calendario y sus indicadores se actualizan. Un rango explícito del mapa mantiene su propia semántica temporal. |
| F03 Aplicar un rango de fechas | Conforme. Se eligió un día con detecciones y se verificó que ninguna detección del mapa saliera de ese día UTC. |
| F04 Dibujar un polígono | **Parcial.** El aplicativo dibuja un recuadro de dos esquinas y usa exactamente esas cuatro coordenadas. No ofrece polígonos arbitrarios de múltiples vértices. |
| F05 Seleccionar un foco | Conforme. Clic sobre un círculo renderizado, ficha con sensor, fecha, FRP y confianza; en la versión actual también se verificó el linaje. |
| F06 CSV frente al mapa | Conforme para los filtros ensayados y sin truncamiento. Los identificadores, posiciones, fechas y FRP del CSV coinciden con el JSON de detecciones que alimenta el mapa. Se verificó el endpoint de exportación, no el gestor de descargas del sistema operativo. |
| F07 Calendario frente a agregados | Conforme para fechas, `valor`, `n_detecciones` y `n_brutas` del JSON y CSV; los representantes por día coinciden en el área ensayada. La métrica armonizada no se compara como si fuese número de puntos. |
| F08 Ausencia de red | Conforme para la búsqueda: desconexión simulada en Chrome, mensaje comprensible y mapa conservado. No equivale a certificar funcionamiento completo sin red de capas y servicios externos. |
| F09 Cambiar de región | Conforme para Garzón → Neiva: una sola selección y nombre actualizado. Además se corrigió la limpieza de contexto al dibujar, introducir coordenadas o elegir otra área. |
| F10 Móvil, teclado y lector de pantalla | **Parcial.** Escape, devolución del foco, nombre del buscador en el árbol accesible y ausencia de desborde en 390 × 844. Falta una evaluación manual con lector de pantalla y un recorrido WCAG 2.2 AA completo. |

No se convierten los dos resultados parciales en aprobaciones completas. La integración meteorológica requiere una comprobación específica del servicio y sus valores; esta fase no valida Open-Meteo ni ERA5 contra estaciones.

## Datos e integridad

El conjunto real local cubre del **8 al 14 de noviembre de 2026**, con datos NRT. Se verificaron seis archivos crudos y cuatro Parquet contra sus SHA-256 declarados. Su conservación de registros es:

`776.835 entradas = 455.827 representantes + 321.008 deduplicados + 0 en cuarentena`.

La tabla agregada tiene **429.608 celdas-día**. Los **776.835 registros aceptados y deduplicados** tienen vínculo al archivo y checksum declarado por el manifiesto; no se encontraron registros sin linaje según los campos comprobados. Esto verifica procedencia estructural e integridad de los archivos disponibles, no la exactitud de la medición satelital ni cada supuesto de la armonización.

La demo histórica local conserva `6.039 = 3.257 + 2.782 + 0`, con 3.005 celdas-día. Sus archivos también pasaron los hashes. El despliegue público sigue siendo **sintético**. Que exista un conjunto FIRMS real local no significa que esté publicado en Vercel.

`dataset_id` es un identificador determinista de la ejecución declarada —entradas, hashes de salidas, reglas y configuración—, no una firma de un tercero ni un certificado. En ausencia de `resumen.json` no se inventa ese identificador. El campo `fila` designa el registro CSV desde 1, sin contar cabecera, no necesariamente una línea física si hubiera campos multilínea.

El servidor publica hashes declarados; la herramienta de auditoría los compara con los archivos locales. Los crudos reales no se distribuyen desde estos endpoints: para reproducibilidad externa completa todavía hace falta facilitar los archivos versionados o un mecanismo estable de recuperación, además del código y `uv.lock`.

## Algoritmo y anomalías

Se inspeccionaron `harmonize/rules.py`, `armonizada.py`, `linea_base.py`, `pipeline.py` y los filtros de `api/app.py`, junto con sus pruebas:

- R1: grilla de 0,009° en coordenadas geográficas; varía su anchura física con la latitud y no es una proyección de igual área.
- R2: normalización de confianza; los cortes MODIS conservan su condición provisional.
- R3: grupos en la misma celda dentro de una ventana anclada de tres horas, con orden determinista. Los absorbidos se conservan en otra tabla; no se borran.
- R4: producto, sensor, plataforma, fecha, archivo, checksum y registro originales se conservan en Parquet y ahora se exponen en la ficha y exportación.
- Métrica por defecto: **celdas activas equivalentes**, versión `celdas-eq-1.1.0`. Se reconstruye usando representantes y deduplicados; no es la suma directa de MODIS y VIIRS. `metrica=n_brutas` es una alternativa explícita.
- La constelación de referencia es MODIS ∪ Suomi NPP; las otras eras usan factores estimados en solapamiento. El conjunto NRT local no contiene esa referencia y devuelve **«sin calibrar»**. Contar celdas de todas las constelaciones en ese caso no garantiza comparabilidad histórica.
- R5: P95, ventana ±7 días, año evaluado excluido y mínimo de cinco años de referencia por día. Los días sin referencia suficiente conservan umbral e indicador nulos. «Inusual» no se presenta como una alerta de emergencia.

La cobertura se deduce de extremos temporales del conjunto. Los huecos interiores se rellenan con cero; no existe una máscara independiente de pasadas válidas, nubes o indisponibilidad del sensor. Por tanto, **un cero no demuestra ausencia de fuego**. Esta limitación sigue abierta y afecta al uso científico de la línea base.

### Sensibilidad del P95

Se ejecutó un [experimento sintético reproducible](evidencias/auditoria_tecnica_20261115/sensibilidad_r5.json), sin tratarlo como observaciones FIRMS:

| Referencia y configuración | Umbral | Valor objetivo | Inusual |
|---|---:|---:|---|
| Seis años, pico de 10 al día siguiente; ventana 0 | 0 | 1 | Sí |
| La misma serie; ventana ±7 | 10 | 1 | No |
| Seis años rellenados con ceros; ventana ±7 | 0 | 1 | Sí |
| Solo tres años de referencia | Sin umbral | 1 | Sin clasificar |

La ventana cambia materialmente el resultado y los ceros pueden dominar el P95. El experimento no estima sensibilidad diagnóstica, tasa de falsas alarmas ni exactitud frente a incendios confirmados. Esos indicadores necesitan una referencia independiente y un diseño de validación.

## Pendientes para aprobación científica y de accesibilidad

1. Incorporar o justificar la cobertura efectiva de observaciones, diferenciando cero detecciones de falta de observación válida.
2. Validar los factores de armonización por región y era con datos independientes, intervalos de incertidumbre y años de evaluación separados de los usados para calibrar.
3. Facilitar los crudos reales y parámetros necesarios para que un tercero reproduzca la serie; los hashes publicados por sí solos no distribuyen esos archivos.
4. Realizar pruebas manuales con lector de pantalla y WCAG 2.2 AA; la inspección del árbol accesible no sustituye esa evaluación.
5. Decidir si F04 requiere polígonos arbitrarios. La funcionalidad comprobada sigue siendo un recuadro.

## Repetir la auditoría

Desde la raíz del repositorio, con el entorno preparado según el README:

```powershell
uv run pytest -q --tb=line
uv run python tools/auditar_plataforma.py --url https://nasa-trasas-de-fuego.vercel.app --salida docs/evidencias/repeticion_publica.json
uv run python tools/auditar_plataforma.py --datos data/processed/global_nrt --crudos data/raw/global --salida docs/evidencias/repeticion_real.json
uv run python tools/analizar_sensibilidad_r5.py --salida docs/evidencias/repeticion_r5.json
node tools/prueba_navegador.mjs https://nasa-trasas-de-fuego.vercel.app/ui/ docs/capturas/repeticion_publica "C:/Program Files/Google/Chrome/Application/chrome.exe" auditoria
```

Para comprobar el ajuste final de carga local, iniciar `uv run python -m api --datos data/processed/demo_historica --puerto 8000` y usar el modo `auditoria-local` contra `http://127.0.0.1:8000/ui/`. El código de salida 1 de la herramienta de endpoints significa que hay al menos un criterio no conforme; el JSON mantiene su detalle.
