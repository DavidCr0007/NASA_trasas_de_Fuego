# Harmonized Heat Neiva

Proyecto del reto **«Harmonization of MODIS and VIIRS Hot Spots»** (NASA Space Apps 2026).

## Objetivo

Armonizar los focos de calor (hot spots) de MODIS y VIIRS publicados por NASA FIRMS en un **calendario de actividad de quema** que respondedores de emergencia, científicos y gestores de tierras pueden consultar para un área de interés. Muestra patrones históricos, días inusuales y periodos críticos. El caso de uso es el Huila y Neiva (Colombia).

La serie histórica está repartida entre sensores con distinta resolución y hora de paso (MODIS en Terra y Aqua; VIIRS en Suomi NPP, NOAA-20 y NOAA-21). Para hacerla comparable, el proyecto aplica estas reglas versionadas (`RULES_VERSION = armonizacion-0.3.1`):

- **R1:** grilla común de ~1 km y agregación por celda y día.
- **R2:** confianza en tres clases.
- **R3:** deduplicación entre pasadas cercanas, conservando VIIRS.
- **R4:** cada registro conserva su satélite, su hora UTC y su calidad.
- **R5:** línea base por día del año, para detectar días inusuales.

**Estado (2026-11-14):** hitos H0 a H8 terminados (ver `docs/auditoria_cumplimiento.md` y `docs/checklist_entrega.md`). `make real` descarga la historia **2001–2025** del archivo público por país de FIRMS (calidad estándar, ADR 0009). El calendario usa una **métrica armonizada** (celdas activas equivalentes, ADR 0011) que no cambia al sumar satélites. Pendientes: la MAP_KEY (B-01) para incluir 2026 y la comparación manual con el visor de FIRMS (H5-02). La demo sin red (`make demo`) usa datos **sintéticos**.

## Estructura de carpetas

```
data/
  raw/                Datos crudos de FIRMS. INMUTABLE y fuera de git; manifiesto SHA-256.
  processed/          Salidas Parquet (demo y demo_historica). Se regeneran.
  sample/             Muestra SINTÉTICA pequeña (3 días) para pruebas y casos borde.
  sample_historica/   Muestra SINTÉTICA 2020–2026, generada por make demo (fuera de git).
src/
  ingest/             Esquema FIRMS, descarga (API area y archivo público por país), manifiesto, lector y validación.
  harmonize/          Reglas R1 a R5, configuración versionada y pipeline Parquet.
  api/                API FastAPI de solo lectura (DuckDB sobre Parquet).
  ui/static/          Interfaz: planeta continuo MapLibre y calendarios; bibliotecas incluidas, sin compilación.
tools/                Generadores de muestra, validación cruzada y escaneo de secretos.
tests/                Pruebas con pytest (sintéticas y con recortes reales de FIRMS).
docs/                 Metodología, limitaciones, cita, esquema, decisiones (ADR), pitch y entrega.
tasks/                Backlog (BACKLOG.md) y riesgos (RIESGOS.md).
```

## Datos

- **Origen:** NASA FIRMS. MODIS C6.1 (Terra y Aqua) y VIIRS 375 m (NOAA-20 y NOAA-21; Suomi NPP solo como histórico, porque ya no entrega datos nuevos). Columnas y códigos en `docs/esquema_firms.md`.
- **Calidad:** NRT (preliminar) o estándar. Cada registro, día y exportación lo indica, y cualquier resultado con NRT se marca como **preliminar**.
- **Crudo inmutable:** `data/raw/` nunca se modifica. Cada archivo queda en `data/raw/manifest.jsonl` con su SHA-256, la fecha de descarga y la URL sin la clave.
- **Muestras sintéticas:** `data/sample/` y `data/sample_historica/` **no son observaciones reales**. Sus archivos empiezan por `SINTETICO_` y su manifiesto lleva `sintetico=true`.
- **Sin datos personales** (D-09).

## Puesta en marcha

Ejecute los comandos desde la raíz del proyecto, donde están `pyproject.toml` y `uv.lock`. En Windows use **PowerShell**: los pasos siguientes no requieren `make`, Node.js ni activar manualmente el entorno virtual. Node.js y Chrome solo se necesitan para las pruebas de navegador.

### 1. Preparar el entorno

Instale [Git](https://git-scm.com/downloads) si va a clonar el repositorio y [uv](https://docs.astral.sh/uv/getting-started/installation/). Abra una terminal nueva después de instalar estas herramientas.

Si todavía no tiene el proyecto:

```powershell
git clone https://github.com/DavidCr0007/NASA_trasas_de_Fuego.git
cd NASA_trasas_de_Fuego
```

Si ya lo tiene abierto, abra la terminal en esa carpeta. Prepare Python y las dependencias:

```powershell
uv --version
uv python install 3.13
uv sync --locked
```

La instalación inicial requiere internet. `uv sync --locked` crea `.venv` e instala las versiones de `uv.lock`; `uv run` utiliza ese entorno automáticamente. Continúe con una de las dos opciones siguientes cuando la preparación termine correctamente.

### 2. Iniciar la demo sin clave FIRMS

Esta opción permite comprobar la aplicación con datos **sintéticos**, sin descargar observaciones de NASA. Prepare los archivos y arranque el servidor, en este orden:

```powershell
uv run python -m harmonize.pipeline --input data/sample --output data/processed/demo
uv run python tools/generar_historico.py data/sample_historica
uv run python -m harmonize.pipeline --input data/sample_historica --output data/processed/demo_historica
uv run python -m api --datos data/processed/demo_historica --puerto 8000
```

Cuando aparezca `Uvicorn running on http://127.0.0.1:8000`, abra **http://127.0.0.1:8000/ui/**. La demo se concentra en Huila: que el globo no muestre focos mundiales es esperado con esta muestra.

### 3. Iniciar el globo con datos globales reales

Si ya existen las salidas procesadas en `data/processed/global_nrt`, basta con iniciar:

```powershell
uv run python -m api --datos data/processed/global_nrt --puerto 8000
```

Abra **http://127.0.0.1:8000/ui/**. El mismo conjunto alimenta el globo y el detalle regional, de modo que el acercamiento conserva las detecciones del periodo consultado. Arrancar el servidor reutiliza el archivo local; no descarga ni actualiza datos.

Si aún no tiene esos archivos, primero configure una clave personal desde [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/map_key/). Cree `.env` **solo si no existe**, conservando su configuración si ya lo tiene:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad .env
```

Complete `FIRMS_MAP_KEY=su_clave` en el editor y guarde el archivo. La clave se necesita para descargar mediante la API de FIRMS; la demo y el uso de datos ya procesados no la requieren. `.env` no se incluye en Git.

Descargue los últimos siete días de fechas UTC, procese y arranque. Ejecute cada paso después de que el anterior termine correctamente:

```powershell
$fechaFinUtc = (Get-Date).ToUniversalTime().Date
$fechaInicioUtc = $fechaFinUtc.AddDays(-6)
$desdeFirms = $fechaInicioUtc.ToString('yyyy-MM-dd')
$hastaFirms = $fechaFinUtc.ToString('yyyy-MM-dd')

uv run python -m ingest.firms_download --sources MODIS_NRT VIIRS_NOAA20_NRT VIIRS_NOAA21_NRT --start $desdeFirms --end $hastaFirms --bbox -180 -90 180 90 --out data/raw/global/firms_api --manifest data/raw/global/manifest.jsonl
uv run python -m harmonize.pipeline --input data/raw/global --output data/processed/global_nrt
uv run python -m api --datos data/processed/global_nrt --puerto 8000
```

La descarga global requiere internet, una clave válida y cuota disponible de FIRMS. Los archivos crudos se conservan: si añade descargas a `data/raw/global`, el procesamiento incluye también los archivos anteriores. Los selectores del globo permiten explorar 1, 2 o 7 días hasta el último dato disponible.

### 4. Comprobar el arranque y detener el servidor

Mantenga abierta la terminal del servidor. En el navegador puede consultar:

- **Interfaz con globo:** http://127.0.0.1:8000/ui/
- **Entrada al mapa regional:** http://127.0.0.1:8000/ui/#regional
- **Estado de la API:** http://127.0.0.1:8000/salud
- **Documentación interactiva:** http://127.0.0.1:8000/docs

Para detenerlo, pulse **Ctrl+C** en su terminal. Para volver a iniciarlo, repita únicamente el comando `uv run python -m api --datos ...` de la opción elegida; no hace falta regenerar la demo o descargar datos cada vez.

Si el puerto 8000 está ocupado, use `--puerto 8001` y abra http://127.0.0.1:8001/ui/. Si faltan los Parquet, complete primero la generación o el procesamiento de datos correspondiente. Si `uv` no se reconoce, compruebe su instalación y abra una terminal nueva. El explorador cartográfico necesita un navegador con WebGL habilitado.

### Alternativa con Make

En Linux, macOS o un entorno con `make` instalado, los mismos pasos están resumidos en el `Makefile`:

```bash
make sync
make api          # genera e inicia la demo sintética
```

Con datos globales ya procesados, use `make api-global`. El objetivo `make global` tiene fechas reproducibles fijadas en el `Makefile`; para otra consulta indique `make global DESDE=AAAA-MM-DD HASTA=AAAA-MM-DD` y después `make api-global`.

## Comandos

| Comando | Qué hace |
|---|---|
| `make sync` | Instala las dependencias fijadas en `uv.lock` (requiere red la primera vez). |
| `make test` | Ejecuta las pruebas con pytest. |
| `make demo` | Comando único de la demo **sin red**: procesa `data/sample/`, genera `data/sample_historica/` y la procesa. Todo sintético. |
| `make api` | Corre la demo y levanta la interfaz (mapa y calendario) y la API en http://127.0.0.1:8000 (API en `/docs`). |
| `make real` | Ruta pública temporal sin clave: descarga el archivo anual por país (Colombia 2001–2025), lo recorta al recuadro del Huila y lo procesa (requiere red la primera vez). |
| `make api-real` | Sirve la interfaz con esos datos reales. |
| `make download` | Descarga desde la API área de FIRMS para el bbox del Huila. Requiere `FIRMS_MAP_KEY` en `.env`. |
| `make global` | Descarga los focos NRT de **todo el mundo** (MODIS, NOAA-20, NOAA-21; 7 días) con su propio manifiesto y los procesa (ADR 0012). Requiere `FIRMS_MAP_KEY`. |
| `make api-global` | Sirve la interfaz con el NRT global: globo 3D y focos de cualquier zona. |
| `make e2e` | Prueba de uso en Chrome sin interfaz gráfica (con la API en marcha): mapa → globo → país → zona → día → tema → móvil. |
| `make secrets` | Escanea el repositorio en busca de credenciales antes de entregar. |
| `make verify-raw` | Verifica los SHA-256 de `data/raw/` contra su manifiesto. |

Procedimiento de descarga y verificación: [docs/descarga.md](docs/descarga.md).

## Demo offline

`make demo` corre dos pipelines sin red, ambos con datos **sintéticos**:

1. `data/sample/` → `data/processed/demo/`: 132 filas con casos borde (cuarentena, cruce de medianoche, NRT frente a estándar).
2. `tools/generar_historico.py` genera `data/sample_historica/` (2020–2026, con una anomalía inyectada en agosto de 2026) → `data/processed/demo_historica/`, que es la que usa la interfaz.

Cada salida tiene `detecciones.parquet`, `deduplicados.parquet`, `cuarentena.parquet`, `celda_dia.parquet` y `resumen.json`. Dos ejecuciones producen los mismos hashes, con las versiones de `uv.lock`. Salida esperada de la primera (formato; los valores exactos están en `resumen.json`):

```
Pipeline armonizacion-0.3.1 (config xxxxxxxxxxxx)
  entrada:      132
  aceptados:    N
  deduplicados: N
  cuarentena:   N
  celda-día:    N
  invariante:   OK
```

Detalle de tablas y consultas DuckDB: [docs/metodologia.md](docs/metodologia.md#pipeline-y-salidas).

## Interfaz y API local

`make api` sirve la interfaz en http://127.0.0.1:8000/ con la muestra histórica **sintética** 2020–2026. El globo es la vista inicial; su cobertura corresponde al conjunto servido. Para explorar detecciones reales de todo el mundo, prepare los datos con `make global` y ejecute `make api-global`.

El mapa tiene prioridad visual. En escritorio, una columna lateral permanente reúne el resumen mundial, su leyenda y el resumen regional desplegable; en móvil aparece debajo. Al acercarse o alejarse se conservan su ubicación y los desplegables abiertos. Los países y las celdas se exploran mediante botones operables con teclado. La rotación se activa con «Girar el globo».

«Análisis de la zona» reúne los calendarios, días inusuales, temporada mensual, periodos críticos, clima e incertidumbre. Permanece disponible en ambas escalas. La barra prioriza búsqueda, encuadre y Tema. «Opciones y descargas» reúne Área del análisis, Año del análisis, exportaciones, dibujo y filtros avanzados; abre un menú sin desplazar el mapa y se cierra con Escape o clic exterior.

Accesos directos:

- **Globo:** http://127.0.0.1:8000/ui/
- **Mapa regional:** http://127.0.0.1:8000/ui/#regional
- **Documentación de la API:** http://127.0.0.1:8000/docs

Los datos de la demo, los calendarios y el respaldo continental funcionan sin internet. El relieve natural, la imagen del día, el clima y la primera descarga de límites globales necesitan conexión. Los límites descargados se guardan en una caché local. El explorador necesita WebGL e identifica el origen sintético o real y la calidad de los datos.

Ejemplo de la API para el Huila:

```bash
curl "http://127.0.0.1:8000/calendario?bbox=-76.7,1.4,-74.3,3.9"
curl "http://127.0.0.1:8000/calendario.csv?bbox=-76.7,1.4,-74.3,3.9" -o calendario.csv
curl "http://127.0.0.1:8000/detecciones?bbox=-76.7,1.4,-74.3,3.9"
```

Cada respuesta trae la cita de FIRMS, el aviso «as is», la versión de reglas, la calidad (NRT/estándar, `preliminar`), los metadatos de incertidumbre y el estado de la línea base («base insuficiente» si no hay años suficientes). Rutas y campos: [docs/metodologia.md](docs/metodologia.md#7-api-de-consulta-h3).

## Buscar ciudades, barrios y direcciones

1. Escriba el lugar en la barra superior; añada ciudad o país si el nombre es ambiguo. Ejemplo: **Chapinero, Bogotá, Colombia**.
2. Pulse **Buscar** o Enter. Los resultados indican nombre, tipo y contexto geográfico. Flechas arriba/abajo permiten recorrerlos y Escape cierra la lista.
3. Elija un resultado: el mismo mapa se desplaza hasta él y muestra un marcador azul. La búsqueda conserva el área de los calendarios.
4. Para actualizar también el análisis, pulse **Analizar esta zona** en la ficha del marcador. Se usa el **recuadro aproximado** del lugar. Puede ajustar el año desde Opciones.

La búsqueda usa **Nominatim / OpenStreetMap**, necesita internet y no requiere una clave FIRMS. No añade un mapa de calles. Solo envía consultas al pulsar Buscar o Enter; escribir no genera solicitudes. El proceso API limita las consultas nuevas a una cada 1,1 segundos y conserva hasta 128 consultas en memoria durante 24 horas. La cobertura de barrios y direcciones depende del proveedor.

Endpoint: `/buscar-lugares?q=Chapinero%2C%20Bogota%2C%20Colombia`. Para un servicio propio compatible con Nominatim, configure `NOMINATIM_URL` en el entorno **antes de iniciar la API**. Si el servidor ya estaba abierto antes de incorporar esta función, reinícielo para registrar la nueva ruta.

El panel mundial también se compactó: no muestra una gráfica de un solo día, los cinco rangos FRP permanecen juntos y los detalles técnicos se agrupan en «Origen y actualización». La naturaleza real o sintética y la calidad siguen visibles; la tarjeta de un país actualiza sus cifras al cambiar el periodo. [Auditoría de la interfaz y capturas](docs/auditoria_busqueda_interfaz_2026-11-14.md).

## Globo 3D y vista global (ADR 0012)

La navegación sigue el recorrido **planeta → país → región → detección sobre un único mapa MapLibre**. Al alejarse, el mismo relieve adopta la forma esférica del planeta; al acercarse aumenta el detalle. El lienzo y los paneles permanecen montados. Cuando el conjunto principal cubre las detecciones mundiales, el detalle conserva las fechas del periodo explorado; con conjuntos separados se identifica el límite de cobertura y se ofrece el visor FIRMS.

La agregación mundial pasa de 0,5° a 0,25°. Desde zoom 6 se consulta el detalle del área visible y se agrupan detecciones cercanas en pantalla; por encima del zoom 10 aparecen círculos individuales. El calendario permite seleccionar un día. **MODIS y VIIRS usan círculos en todas las escalas**:

| Representación | Color | Tamaño |
|---|---|---|
| Grupo de detecciones | FRP máximo del grupo | Cantidad de focos |
| Detección individual | FRP del foco | FRP del foco |

En detecciones individuales, la transparencia indica confianza. La ficha identifica NRT y muestra sensor, fecha UTC, calidad, posición, resolución nominal y temperatura de brillo disponible. El círculo representa potencia; no delimita el incendio ni el tamaño real del píxel.

El único fondo es **NASA GIBS Blue Marble en sus colores naturales**, con opacidad completa y sin desaturación. Cambiar el tema modifica los controles, sin alterar el color del planeta ni recargar su estilo. Se retiraron OpenStreetMap y Black Marble. Los créditos del mapa permanecen fijos: GIBS, FIRMS y geoBoundaries. Las solicitudes reemplazadas se cancelan y se reutilizan los resultados disponibles.

Al recargar se presenta la estructura de la página y un esqueleto dentro del mapa. Al cambiar de ciudad se mantienen el lienzo y los paneles mientras llegan los datos; el indicador de carga se limita al mapa y evita destellos en solicitudes rápidas.

### Límites geográficos globales

El índice local contiene 252 países y territorios, incluidos microestados. La interfaz solicita límites simplificados de **geoBoundaries** para los países visibles:

- **Zoom menor que 3:** relieve continental, sin divisiones administrativas.
- **Desde zoom 3:** países (ADM0).
- **Desde zoom 5:** departamentos, estados o equivalentes (ADM1).
- **Desde zoom 8:** municipios, distritos, condados o equivalentes (ADM2).

Los niveles y su cobertura varían por país; ADM2 no equivale siempre a municipio. «Límites geográficos» muestra fuente, año, licencia y capas no disponibles. El crédito DANE/CC BY 4.0 corresponde a Colombia ADM2.

La primera consulta requiere internet. El servicio `/limites/{ISO3}/{nivel}` guarda los archivos y metadatos en `data/processed/limites_globales/` y reutiliza la caché. El índice puede regenerarse mediante `uv run python tools/preparar_indice_limites.py`. Detalles y capturas: [planeta continuo](docs/planeta_continuo_2026-11-14.md).

## Guía de colores, temperatura y sensores

Ambas leyendas enlazan a la guía integrada. El color representa **potencia radiativa del fuego (FRP), en MW**, con los mismos cortes en cualquier zona, nivel de zoom y tema:

| Color | FRP |
|---|---|
| Amarillo claro | Menos de 5 MW |
| Amarillo ámbar | Desde 5 hasta menos de 20 MW |
| Naranja | Desde 20 hasta menos de 100 MW |
| Rojo | Desde 100 hasta menos de 500 MW |
| Rosa | 500 MW o más |

FRP no tiene una conversión directa a temperatura. `/detecciones` y `/detecciones.csv` incluyen `brillo` en **kelvin**, conservado del archivo procesado; la ficha lo presenta también en °C mediante `°C = K − 273,15`. Es temperatura de brillo del píxel, que combina fuego y entorno, y no equivale a la temperatura de la llama o del aire. Si falta el dato, la ficha indica «No disponible».

La guía explica la resolución nominal de MODIS (1.000 m) y VIIRS (375 m), el crecimiento del píxel hacia el borde del barrido y la saturación de VIIRS I4. El archivo no proporciona un margen térmico individual de **± °C**. La confianza de detección y la armonización de conteos del calendario no representan ese margen ni calibran temperaturas. Fuentes y detalles: [informe de reestructuración visual](docs/reestructuracion_visual_2026-11-14.md#temperatura-y-calibración).

## Validación del rediseño

Verificación del **14 de noviembre de 2026** sobre `data/processed/global_nrt`:

- **469 pruebas** correctas con pytest, incluidas la búsqueda, su caché y límite de consultas, el brillo del sensor y los límites globales.
- **18/18 comprobaciones** en Chrome del planeta continuo, colores fijos entre temas, límites reales de Colombia y España, carga localizada, calendario, ficha térmica, dibujo y navegación global; sin errores de consola ni desborde móvil.
- **17/17 comprobaciones de búsqueda y UX** en Chrome: consulta real, ratón y teclado, origen de los datos visible, resultados ambiguos, análisis explícito del lugar, estados vacíos y de error, descarte de respuestas obsoletas y móvil.

Para reproducir el recorrido, ejecute `make api-global` y, en otra terminal, `make e2e`. Se necesitan Node.js 22 o posterior, Chrome e internet para límites que aún no estén en caché. El script admite URL, carpeta de capturas, ruta de Chrome y modo. Use `busqueda` para el buscador y el panel auditado; `planeta` o `normal` para el mapa continuo. `diseno` y `continuidad` se conservan como alias; `panel` añade una captura del análisis y `separado` verifica conjuntos regional y global distintos.

Ejemplo del modo de validación visual en Windows, con la API en marcha:

```powershell
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/local "C:/Program Files/Google/Chrome/Application/chrome.exe" planeta
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/busqueda_local "C:/Program Files/Google/Chrome/Application/chrome.exe" busqueda
```

[Informe y capturas del rediseño](docs/reestructuracion_visual_2026-11-14.md) · [Auditoría comparativa de ramas](docs/auditoria_diseno_ramas_2026-11-14.md). La validación no incluye un estudio con usuarios ni una evaluación formal con lectores de pantalla.

Estado actual: [planeta continuo y carga localizada](docs/planeta_continuo_2026-11-14.md). La [auditoría UX del zoom](docs/auditoria_ux_zoom_2026-11-14.md) conserva la evidencia de la iteración anterior.

## Capas de contexto (H7)

En el mapa y el panel hay tres capas de contexto (ADR 0010):

- **Límites globales ADM0, ADM1 y ADM2** (geoBoundaries). Primera descarga con red y reutilización local. Los 37 municipios del Huila siguen incluidos para el selector y los filtros de la demo.
- **Imagen satelital de color real del día elegido** (NASA GIBS). Requiere internet.
- **Clima del día o del periodo crítico** (Open-Meteo; es un reanálisis, no una observación). Requiere internet.

Sin red se conservan los datos locales, los calendarios, el respaldo continental y los límites ya descargados.

## Limitaciones

Lo esencial; el detalle está en [docs/limitaciones.md](docs/limitaciones.md):

- Los focos son **detecciones térmicas, no incendios confirmados**.
- Cada punto es el **centro de un píxel**: 1 km en MODIS y 375 m en VIIRS, y el píxel crece hacia el borde del barrido.
- VIIRS de 375 m **se satura** en fuegos intensos, así que el FRP es indicativo.
- Cuando Terra deje de pasar, cambiarán las horas de observación y la serie MODIS quedará **sesgada en el horario**.
- Los datos **NRT** son preliminares.
- «Inusual» significa por encima del P95 histórico de ese día del año (±7 días, sin contar el propio año). En un año normal, ~5 % de los días lo supera.
- Se necesitan 5 años de historia; con menos, la respuesta es «base insuficiente».

## Documentación

- [Metodología](docs/metodologia.md): flujo, validación y reglas R1 a R4.
- [Limitaciones](docs/limitaciones.md): lo que el método no resuelve y lo que está por confirmar.
- [Decisiones (ADR)](docs/decisiones/): supuestos registrados uno por archivo.
- [Reestructuración visual y validación](docs/reestructuracion_visual_2026-11-14.md): navegación, simbología, guía térmica y capturas.
- [Auditoría UX del zoom](docs/auditoria_ux_zoom_2026-11-14.md): continuidad entre escalas, paneles estables y barra compacta.
- [Planeta continuo y carga localizada](docs/planeta_continuo_2026-11-14.md): estado actual del mapa único, límites globales y validación.
- [Búsqueda y auditoría de interfaz](docs/auditoria_busqueda_interfaz_2026-11-14.md): ciudades, barrios, direcciones, panel compacto y comprobaciones de UX.
- [Auditoría del diseño entre ramas](docs/auditoria_diseno_ramas_2026-11-14.md): comparación entre `main` y `feat/globo-global` y hallazgos atendidos.
- [Cita y aviso](docs/cita.md): cómo citar FIRMS, LANCE y ESDIS.
- [Esquema FIRMS verificado](docs/esquema_firms.md) y [descarga](docs/descarga.md).
- [Pitch de 2 minutos](docs/pitch.md) y [lista de entrega](docs/checklist_entrega.md).
- [Backlog](tasks/BACKLOG.md) y [riesgos](tasks/RIESGOS.md).

## Cita y aviso

Texto oficial copiado de la página de FIRMS en Earthdata (2026-11-13). Detalle, DOI y estudios de validación en [docs/cita.md](docs/cita.md).

> We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://www.earthdata.nasa.gov/data/tools/firms), part of NASA's Land, Atmosphere Near real-time Capability for Earth observations (LANCE) and NASA's Earth Science Data and Information System (ESDIS).

> The information presented through LANCE, GIBS, Worldview, and FIRMS are provided "as is" and users bear all responsibility and liability for their use of data.

Los focos son detecciones térmicas, no incendios confirmados. Los datos NRT son preliminares. Ver [docs/limitaciones.md](docs/limitaciones.md).
