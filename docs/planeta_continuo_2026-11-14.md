# Planeta continuo, límites globales y carga localizada

14 de noviembre de 2026 · `feat/globo-global`.

La iteración posterior incorpora [búsqueda de lugares y auditoría del panel](auditoria_busqueda_interfaz_2026-11-14.md), conservando este mismo mapa.

## Resultado

Se retiró el intercambio de MapLibre y Leaflet de la interfaz. Ahora existe **un único mapa y un único lienzo WebGL**. Al alejarse aparece la esfera; al acercarse aumenta el detalle sobre ese mismo mapa. Cambiar de ciudad, consultar un día, dibujar un área y cambiar de tema conservan la estructura de la página.

El relieve es **NASA GIBS Blue Marble en sus colores naturales**, con opacidad completa y sin desaturación. El modo oscuro modifica los controles y paneles, sin cambiar la imagen del planeta ni volver a cargar su estilo. Se retiraron OpenStreetMap y Black Marble de la interfaz. La [proyección de globo de MapLibre](https://github.com/maplibre/maplibre-gl-js/blob/main/developer-guides/globe.md) permite mantener la exploración en el mismo motor.

Los créditos del mapa permanecen visibles en cualquier escala: NASA GIBS, NASA FIRMS (LANCE / ESDIS) y geoBoundaries. DANE y CC BY 4.0 se identifican para Colombia ADM2; las fuentes y licencias de otros países se muestran en «Límites geográficos».

## Marco geográfico progresivo

| Escala | Presentación |
|---|---|
| Zoom menor que 3 | Relieve continental y esfera, sin divisiones administrativas. |
| Desde zoom 3 | Países, geoBoundaries ADM0. |
| Desde zoom 5 | Departamentos, estados o equivalentes, ADM1. |
| Desde zoom 8 | Municipios, distritos, condados o equivalentes, ADM2. |

Los trazos aparecen gradualmente con el zoom. Pulsar un límite muestra su nombre y nivel. La [API oficial de geoBoundaries](https://www.geoboundaries.org/api.html) define ADM0, ADM1 y ADM2 como niveles administrativos; **ADM2 no equivale a municipio en todos los países y no todos los niveles están publicados para todos los territorios**. La interfaz identifica las capas no disponibles, sin inventar divisiones ni atribuir todos los datos mundiales al DANE.

El índice local permite localizar **252 países y territorios**, incluidos microestados, con un archivo de aproximadamente 22 KB. Se genera con `tools/preparar_indice_limites.py` a partir de [Natural Earth 1:10m](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/). Ese índice solo decide qué países consultar; las líneas administrativas mostradas se descargan de geoBoundaries. El archivo local anterior de Natural Earth se conserva como respaldo continental cuando no hay teselas.

El navegador solicita las geometrías simplificadas de los países visibles, con un máximo de tres descargas simultáneas. El servicio `/limites/{ISO3}/{nivel}` acepta niveles 0, 1 y 2 y guarda resultados y metadatos en `data/processed/limites_globales/`. Las escrituras son atómicas y las solicitudes concurrentes del mismo país y nivel comparten un bloqueo. Las cachés en memoria están acotadas; desplazarse a otra región cancela las solicitudes del navegador que quedaron obsoletas.

## Carga sin parpadeo de la página

- El HTML presenta primero la estructura: barra, contenedor del mapa y panel lateral. El mapa dispone de un esqueleto inicial propio.
- Las consultas posteriores mantienen el lienzo y los resultados anteriores mientras llegan los nuevos datos. No se reemplaza el cuerpo de la página ni se vacía el panel de análisis al comenzar cada carga.
- El indicador se limita al rectángulo del mapa y aparece con una demora de 180 ms para evitar destellos en solicitudes rápidas. También sigue la carga de las teselas del relieve.
- Las respuestas obsoletas se descartan. Arrastrar el mapa durante una consulta evita que la llegada de datos vuelva a centrarlo en una selección anterior.
- Las consultas cercanas al meridiano 180° se dividen en dos recuadros válidos y se deduplican por `record_id`.

El detalle de focos usa círculos y agrupaciones en el mismo motor. La ficha conserva sensor, confianza, calidad, resolución nominal y temperatura de brillo. El calendario y el dibujo de áreas siguen operativos; el dibujo se realiza seleccionando dos esquinas y puede cancelarse con Escape.

## Verificación

- **459 pruebas correctas** con pytest; incluye validación de parámetros, fuentes permitidas, caché en disco, ausencia de cobertura y desconexión del proveedor. Permanece una advertencia de deprecación de Starlette TestClient.
- **18/18 comprobaciones correctas en Chrome**, en escritorio de 1440 × 1000 y móvil de 390 × 844, sin errores de consola ni desborde horizontal.
- **19/19 comprobaciones adicionales** con conjuntos regional y mundial separados: el detalle del análisis se conserva identificado y no reemplaza las agrupaciones mundiales al explorar otra zona.
- Se verificaron límites reales ADM0, ADM1 y ADM2 de Colombia y ADM1 de España. Se comprobó la identidad del mapa y del lienzo antes y después del zoom, y que cambiar de tema no altera ninguna capa ni fuente del estilo.
- Con latencia simulada se verificó que cambiar de ciudad conserva el contenido de los paneles y muestra el esqueleto únicamente dentro del mapa.
- Se probaron la selección de un día, la apertura de una ficha térmica mediante un clic real, el dibujo de un área y el cruce del antimeridiano.

Capturas: [planeta natural](capturas/planeta_unico_20261114/01_planeta_natural.png), [detalle con límites](capturas/planeta_unico_20261114/02_detalle_limites.png), [carga localizada](capturas/planeta_unico_20261114/03_carga_local.png), [ficha térmica](capturas/planeta_unico_20261114/04_ficha_termica.png), [móvil](capturas/planeta_unico_20261114/05_planeta_movil.png).

Reproducción, con `make api-global` o el comando equivalente de PowerShell en marcha:

```powershell
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/planeta_local "C:/Program Files/Google/Chrome/Application/chrome.exe" planeta
```

La primera descarga de límites y el relieve natural necesitan internet. Los límites ya descargados se reutilizan desde la caché. Blue Marble tiene resolución de contexto (nivel nativo 8), no detalle urbano de calles; se mantiene como único fondo según el alcance solicitado. El navegador necesita WebGL. La validación no sustituye un estudio con usuarios o lectores de pantalla.
