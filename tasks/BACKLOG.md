# Backlog: Harmonized Heat Neiva (hitos H0 a H6)

Estados posibles: `pendiente`, `en curso`, `hecho`, `bloqueado`.
Roles posibles: `infra`, `datos-ingesta`, `reglas`, `docs`, `QA`.

| ID | Descripción | Criterio de aceptación | Estado | Rol | Dependencias |
|---|---|---|---|---|---|
| H0-01 | Estructura de carpetas y paquetes `src/{ingest,harmonize,api,ui}`, `tests`, `docs`, `tasks`, `data/{raw,processed,sample}`. | Existen las carpetas y un `__init__.py` por paquete. `data/raw/` está excluida de git. `Harmonize.py` se mueve a `src/harmonize/` y `Test_harmonize.py` importa `harmonize` sin errores. | hecho | infra | ninguna |
| H0-02 | `pyproject.toml` con uv, Python 3.13 y pytest. | `uv sync` crea el entorno con Python 3.13 y `uv run pytest` ejecuta la suite (aunque la suite inicial esté vacía). `uv.lock` versionado. | hecho | infra | H0-01, R-18 |
| H0-03 | `Makefile` con `sync`, `test`, `demo`, `download` y `secrets`. | `make demo` corre sin red y sin `.env`, usando solo `data/sample/`. `make test` pasa. | hecho | infra | H0-02, R-18 |
| H0-04 | `.env.example` con `FIRMS_MAP_KEY` y registro del bloqueo de la clave. | `.env.example` existe y `.env` está en `.gitignore`. Sin `.env` real, `make download` informa el bloqueo B-01 y no falla en silencio. | hecho | infra | H0-01 |
| H0-05 | Manifiesto SHA-256 de `data/raw/` en `data/raw/manifest.jsonl`. | Cada archivo descargado tiene una línea con ruta, SHA-256, fecha de descarga y fuente. Una prueba recalcula el hash y detecta cualquier cambio. | hecho | datos-ingesta | H0-01, H0-06 |
| H0-06 | Script de descarga por API área de FIRMS para el bbox del Huila, último año, con fuentes `MODIS_NRT`, `MODIS_SP`, `VIIRS_SNPP` (solo histórico), `VIIRS_NOAA20` y `VIIRS_NOAA21`. | Con `FIRMS_MAP_KEY` válida, el script guarda cada CSV en `data/raw/` y registra SHA-256 y fecha de descarga (H0-05). Respeta el límite de `DAY_RANGE` y de transacciones (valores **por confirmar**). Sin clave, falla con mensaje claro. | hecho (código y pruebas); descarga real bloqueada por B-01 | datos-ingesta | H0-04, B-01 |
| H0-07 | Validación del esquema oficial de FIRMS (columnas, códigos de satélite, dominio de confianza, formato de fechas y horas). | `docs/esquema_firms.md` y `src/ingest/firms_schema.py` sin valores «por confirmar» en lo verificado. Cabeceras y 25 filas de cada CSV real en `tests/fixtures/firms_real/`. Sin acceso a red, queda bloqueado. | hecho | datos-ingesta | H0-06 |
| H0-08 | Cita y aviso «as is» de FIRMS, LANCE y ESDIS en `docs/cita.md` y en el README. | `docs/cita.md` contiene el texto oficial copiado literalmente con su URL, sin «por confirmar» en cita, reconocimiento ni aviso. El README reproduce esos textos. Sin fuente accesible, queda bloqueado. | hecho (DOI por confirmar, R-24) | docs | ninguna |
| H0-09 | ADR de supuestos en `docs/decisiones/` (grilla, umbrales, deduplicación, percentil, mínimo de años, stack, precedencia NRT/estándar). | Siete archivos, cada uno con Estado, Contexto, Decisión, Alternativas, Consecuencias y Por confirmar. | hecho | docs | ninguna |
| H0-10 | Escaneo de secretos antes de entregar (`make secrets`). | El escaneo no encuentra claves ni credenciales en el repositorio ni en el historial del commit a entregar. | hecho | QA | H0-03 |
| D-01 | Lector que valida el esquema real de FIRMS. | Un archivo con columnas distintas al esquema oficial se rechaza con motivo. Pruebas con datos sintéticos y con fixtures reales (cuando existan). | hecho | datos-ingesta | H0-07, R-01 |
| D-02 | Procedencia por registro: sensor, satélite, colección, hora UTC, fecha de descarga, hash del archivo fuente y calidad NRT/estándar. | Cada registro aceptado tiene los siete campos no vacíos. Una prueba comprueba la presencia de cada uno. | hecho | datos-ingesta | D-01 |
| D-03 | Validación de latitud, longitud, fecha, confianza y satélite. | Valores fuera de dominio se marcan como inválidos con motivo específico. Pruebas por cada campo. | hecho | datos-ingesta | D-01, R-01 |
| D-04 | Cuarentena con motivo, sin borrar registros. Invariante: entrada = aceptados + cuarentena + deduplicados. | Ningún registro desaparece. Una prueba verifica el invariante en cada ejecución de `make demo` y de `make test`. | hecho | datos-ingesta | D-03, R3 |
| R1 | Grilla común de ~1 km (`CELL_DEG = 0.009`, origen `(-90, -180)`) y agregación celda-día. | Dos puntos próximos en la misma fila de grilla caen en la misma columna, con independencia de su latitud. Pruebas de borde de celda. Parámetros configurables. | hecho | reglas | D-01 |
| R2 | Confianza en 3 clases (baja, nominal, alta) con umbrales configurables, marcados PROVISIONALES. | MODIS: <30 baja, 30–79 nominal, ≥80 alta. VIIRS: mapeo configurable. Pruebas de cada clase y de los bordes. Cambiar un umbral por defecto obliga a subir `RULES_VERSION`; la configuración en ejecución queda en `config_fingerprint`. | hecho | reglas | D-03 |
| R3 | Deduplicación en la misma celda con |Δt| ≤ 3 h, ventana voraz anclada al primer registro, prioridad VIIRS > MODIS, luego estándar > NRT, luego confianza, hora más temprana y `record_id`. | Pruebas: caso de no transitividad (A 10:00, B 12:30, C 14:00 → C fuera), prioridad de cada criterio y conservación de duplicados en tabla aparte. | hecho | reglas | R1, R2 |
| R4 | Conservación de satélite, hora UTC y calidad en el representante. | Una prueba comprueba que estos tres campos llegan intactos a la salida agregada. | hecho | reglas | R3 |
| D-05 | `RULES_VERSION` en cada fila de salida. | Cada fila del Parquet contiene `RULES_VERSION` no vacío. Cambiar una regla cambia el valor. | hecho | reglas | R1, R2, R3, R4, R-18, R-22 |
| D-06 | Reproducibilidad: el mismo crudo produce el mismo Parquet y el mismo hash. | Dos ejecuciones con el mismo `data/raw/` y el mismo `uv.lock` producen el mismo SHA-256 del Parquet. Prueba automatizada en `make test`. | hecho | QA | D-05, H0-05, R-18 |

## H3: API con incertidumbre, mínimo de base y citación

| ID | Descripción | Criterio de aceptación | Estado | Rol | Dependencias |
|---|---|---|---|---|---|
| H3-01 | API FastAPI de solo lectura sobre los Parquet de `data/processed/` con DuckDB. | `create_app(dir)` sirve `/salud`, `/cita`, `/calendario`, `/calendario.csv` y `/detecciones`; si falta un Parquet, `/salud` responde 503 con motivo. Pruebas con `TestClient`, sin red. | hecho | api | D-06 |
| H3-02 (D-07) | Metadatos de incertidumbre en cada respuesta de `/calendario` y `/detecciones`. | El bloque `incertidumbre` trae: resolución (MODIS 1000 m, VIIRS 375 m, grilla 0,009°), horario de pasada observado por satélite (hora UTC mínima y máxima, n), conteo por clase de confianza, años con dato y porcentaje de días con dato en el rango. Cada punto de `/detecciones` trae su semilado nominal en metros. Pruebas con valores esperados de la muestra. | hecho | api | H3-01 |
| H3-03 (D-02) | Calidad NRT o estándar visible. | Cada día y la respuesta global traen `calidad` (`NRT`, `estandar` o `mixta`) y `preliminar=true` si interviene algún dato NRT. Prueba con la muestra (mixta) y con un subconjunto solo estándar. | hecho | api | H3-01 |
| H3-04 (D-05) | Versión de reglas en cada respuesta. | Toda respuesta JSON y CSV lleva `rules_version` y `config_fingerprint` leídos de los metadatos Parquet. | hecho | api | H3-01 |
| H3-05 (D-08) | Mínimo de años para la línea base. | `linea_base.estado` es `"base insuficiente"` cuando los años con dato del área son menos que `anios_minimos` (configurable; valor por defecto PROVISIONAL, ADR 0005). Con años suficientes, `"suficiente"` y el cálculo de días inusuales queda para H4. Pruebas de ambos casos. | hecho | api | H3-01 |
| H3-06 (D-10) | Cita de FIRMS en la API y en la exportación. | Toda respuesta JSON trae `cita` y `aviso` con el texto literal de `docs/cita.md`; `/calendario.csv` empieza con esas líneas comentadas con `#`. Prueba que compara con `docs/cita.md`. | hecho | api | H3-01 |
| H3-07 | Validación de parámetros. | `bbox` mal formado, fuera de rango o con W ≥ E o S ≥ N, y `desde > hasta`, responden 422 con mensaje en español. | hecho | api | H3-01 |
| H3-08 | Arranque local de la API. | `make api` levanta uvicorn sobre `data/processed/demo` sin red; `make demo` sigue siendo el comando único de la demo. | hecho | infra | H3-01 |
| D-09 | Sin datos personales en el MVP. | La API no recibe ni guarda datos de personas; no hay endpoints de registro ni alertas. | hecho | api | ninguna |

## H4: mapa, calendario de actividad y días inusuales

| ID | Descripción | Criterio de aceptación | Estado | Rol | Dependencias |
|---|---|---|---|---|---|
| H4-01 (R5) | Línea base por día del año y días inusuales. | `harmonize.linea_base.calcular(serie, …)`. Para cada día, el umbral es el percentil `p` (95 por defecto, interpolación lineal) de `n_brutas` en los **otros** años, el mismo día del año ± `ventana_dias` (7, PROVISIONAL). El 29 de febrero cuenta como 28. Los días sin focos valen 0 dentro de la cobertura. Un día es inusual si `n_brutas > umbral`. Si un día tiene menos de `anios_minimos` años de referencia, su umbral es nulo («base insuficiente»). Pruebas con series construidas a mano: bisiesto, ventana circular en fin de año, exclusión del propio año, mínimo de años. | hecho | reglas | H3-05 |
| H4-02 | Periodos críticos y climatología mensual. | Los días inusuales consecutivos forman `periodos_inusuales` (inicio, fin, días, máximo). `climatologia_mensual` da la media de `n_brutas` por mes en los meses completos de la cobertura; `meses_pico` son los 3 meses de media más alta. Pruebas con valores esperados. | hecho | reglas | H4-01 |
| H4-03 | API con días inusuales. | Con base suficiente, `/calendario` añade a cada día `umbral`, `inusual` y `n_anios_base`, y a la respuesta `periodos_inusuales`, `climatologia_mensual` y `meses_pico`. Con base insuficiente, esos campos son nulos y `linea_base.estado` sigue siendo «base insuficiente». El CSV exporta `umbral` e `inusual`. | hecho | api | H4-01, H4-02 |
| H4-04 | Muestra histórica sintética de varios años. | `tools/generar_historico.py` genera de forma determinista 2020–2026 para el Huila (MODIS y VIIRS, estándar hasta 2025 y NRT en 2026), con un patrón estacional **sintético** y una anomalía inyectada en agosto de 2026. Pasa por el pipeline sin cuarentena inesperada; la API detecta la anomalía. `make demo` la genera y la procesa sin red. | hecho | datos-ingesta | H4-01 |
| H4-05 | Interfaz: mapa y calendario. | `/` sirve una página sin paso de compilación que funciona sin internet (Leaflet incluido en el repositorio; las teselas base son opcionales). Muestra: mapa con cada foco como círculo del tamaño de su semilado nominal; selector de área (Huila, Neiva y rectángulo dibujado); calendario anual con días inusuales resaltados y días NRT marcados como preliminares; climatología mensual; periodos críticos; estado de la línea base; versión de reglas; enlace de exportación CSV; y la cita de FIRMS en el mapa. Verificada en navegador. | hecho | ui | H4-03 |
| H4-06 | Decisión de stack del frontend. | ADR 0008 explica por qué se usa JavaScript sin compilación con Leaflet incluido en lugar de React. | hecho | docs | H4-05 |

## H5: validación cruzada, documentación, demo y pitch

| ID | Descripción | Criterio de aceptación | Estado | Rol | Dependencias |
|---|---|---|---|---|---|
| H5-01 | Validación cruzada del pipeline contra el archivo oficial. | `tools/validacion_cruzada.py` cuenta por su cuenta, con el módulo `csv`, las filas del CSV oficial por sensor, día UTC y bbox, y las compara con la salida del pipeline. Se cumple `crudas = n_brutas + cuarentena` en el área y el día; la diferencia y su explicación quedan en `docs/metodologia.md`, con fuente, fecha y calidad. Prueba con la muestra. | hecho | QA | H2 |
| H5-02 | Comparación con el visor de FIRMS (§8). | Procedimiento escrito en la metodología. Los conteos del visor para el mismo día y área quedan registrados con su diferencia y explicación. Requiere una persona frente al visor y queda marcado en la lista de entrega. | pendiente | QA | H5-01 |
| H5-03 | Capturas de respaldo. | `docs/capturas/` contiene capturas de la interfaz (vista general, día seleccionado y base insuficiente) tomadas de `make api`, con fecha y versión de reglas. | hecho | ui | H4-05 |
| H5-04 | Pitch de 2 minutos. | `docs/pitch.md`: guion de ~260 palabras con tiempos. Cada cifra lleva fuente, fecha y calidad; una prueba comprueba que la versión de reglas y las cifras de la demo coinciden con el código. | hecho | docs | H4 |
| H5-05 | Lista de verificación de entrega. | `docs/checklist_entrega.md` marca cada entregable y requisito (D-01 a D-11, R1 a R5, §8, §9) como hecho, pendiente o bloqueado, con evidencia. | hecho | QA | H5-01..04 |
| H5-06 | README completo. | El README cubre instalación, uso, datos, citación y limitaciones, y refleja el estado H0 a H5. | hecho | docs | H4 |
| H5-07 | Bibliografía de validación en la metodología. | `docs/metodologia.md` incluye los estudios de validación que cita FIRMS (copiados de `docs/cita.md`). | hecho | docs | H0-08 |

## Mitigación de B-01 y cierre de pendientes de H5

| ID | Descripción | Criterio de aceptación | Estado | Rol | Dependencias |
|---|---|---|---|---|---|
| H5-08 | Ruta pública temporal sin MAP_KEY (ADR 0009). | `ingest.firms_publico` descarga el archivo anual por país, crudo inmutable con SHA-256 y URL; reutiliza lo ya descargado; informa los 404; rechaza cabeceras inválidas; escribe recortes por bbox con hash de origen. `make real` procesa el Huila 2016–2025 sin cuarentena y con línea base suficiente. Pruebas con descarga simulada. | hecho | datos-ingesta | H1, H4 |
| H5-09 | Variante de esquema «archivo por país». | `firms_schema` reconoce `Terra`/`Aqua`, `l`/`n`/`h` e `instrument` y `type`, con fuente [K]; los recortes reales de Colombia 2023 validan sin cuarentena. | hecho | datos-ingesta | H0-07 |
| H5-10 | Validación cruzada con historia real y diagnóstico de borde. | La herramienta separa la diferencia por efecto de borde y la diferencia sin explicar debe ser 0; resultados en la metodología §10.1. | hecho | QA | H5-01, H5-08 |
| H5-11 | DOI oficiales. | Los DOI NRT de MCD14DL, VNP14, VJ114 y VJ214 se copian de la página de cada producto y se comprueba que resuelven en doi.org. | hecho | docs | H0-08 |

## H6: interfaz entendible, tema claro/oscuro y origen de los datos

Objetivo: presentar los datos a un público no técnico (respondedores de emergencia, gestores de tierras, jurado).

| ID | Descripción | Criterio de aceptación | Estado | Rol | Dependencias |
|---|---|---|---|---|---|
| H6-01 | Origen de los datos en la API: `/calendario` y `/detecciones` exponen `origen_datos`. | `origen_datos` vale `"sintetico"`, `"real"`, `"mixto"` o `null` si no hay detecciones, calculado de la columna `sintetico` de `detecciones.parquet` sobre todo el conjunto. Pruebas en `tests/test_api.py` con conjuntos sintético, real y mixto. | hecho | api | H3 |
| H6-02 | Insignia de origen en la interfaz. | Muestra «DATOS SINTÉTICOS (demostración)», «Datos reales NASA FIRMS» o «Datos mixtos: reales y sintéticos», junto a la de calidad (PRELIMINAR/estándar, D-02). | hecho | ui | H6-01 |
| H6-03 | Tema claro y oscuro. | Tokens en `:root` redefinidos con `@media (prefers-color-scheme: dark)` y selector manual claro/oscuro/sistema guardado en `localStorage` con try/catch. Contraste WCAG AA (texto ≥ 4,5:1; gráficos y foco ≥ 3:1) en ambos temas para escala e0..e4, días inusuales, puntos MODIS/VIIRS, insignias, cajas de aviso, popups y controles de Leaflet. Teselas oscurecidas con filtro CSS. El mapa funciona sin internet. | hecho | ui | H4-05 |
| H6-04 | Resumen en lenguaje sencillo y explicaciones «¿qué significa?». | El resumen se genera solo con la respuesta de `/calendario`. Explica foco de calor, día inusual, NRT/preliminar, huella del píxel, base insuficiente y efecto de borde. Incluye el aviso de FIRMS «Do not use for the preservation of life or property» traducido y citado. Fechas legibles («12 ago 2026») además de ISO, números es-CO y unidades. | hecho | ui | H4-03 |
| H6-05 | Calendario accesible. | Celdas navegables con teclado (flechas, Inicio/Fin, Enter/Espacio); roles ARIA `grid`/`row`/`gridcell`; `aria-selected`; tooltip propio; foco visible; día seleccionado resaltado. Comparación «este año frente al promedio histórico mensual» en SVG propio, aclarando que el promedio incluye el año mostrado en sus meses completos. | hecho | ui | H6-03 |
| H6-06 | Robustez de la interfaz. | `pedir()` lee el cuerpo una sola vez; calendario vacío (`dias=[]`) sin errores; sin carreras entre cargas concurrentes (solo pinta la última); estados de carga, vacío y error comprensibles con botón de reintento; responsive desde 375 px sin scroll horizontal de la página (cita larga con `overflow-wrap`). | hecho | ui | H4-05 |
| H6-07 | Pruebas de interfaz. | `tests/test_interfaz.py` comprueba que no hay recursos remotos obligatorios, que hay tokens en ambos temas con contraste AA calculado, el selector de tema, la cita D-10 y la insignia de origen. `uv run pytest -q && make demo` pasa. | hecho (2026-11-14: `uv run pytest -q` con 389 pruebas, `make demo` y `make secrets` pasan) | QA | H6-01..06 |
| H6-08 | Documentación de H6. | Se actualizan `docs/metodologia.md` §9, `docs/capturas/LEEME.md` (capturas a retomar en claro y oscuro) y el ADR 0008 (tema), sin reescribir otras secciones. Capturas con datos reales en claro, oscuro y 375 px hechas (`05`–`08`). Las de la demo sintética en ambos temas siguen pendientes (`docs/capturas/LEEME.md`). | hecho | docs | H6-01..07 |

