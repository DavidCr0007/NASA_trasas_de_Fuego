# Validación de búsqueda global y municipio del foco

15 de noviembre de 2026. Conjunto de verificación: `data/processed/global_nrt`.

## Resultado

El explorador inicia en el planeta, sin seleccionar Huila ni dibujar su recuadro. Países, ciudades y barrios conservan el mismo mapa al buscarse. Una detección individual selecciona su municipio, lo delimita y encuadra automáticamente; el municipio permanece seleccionado al cambiar el zoom. El clic conserva el periodo y el conjunto de datos del foco elegido.

## Problemas corregidos

| Hallazgo | Ajuste |
|---|---|
| El análisis inicial y el recuadro estaban fijados en Huila; sus líneas tenían más peso que las globales. | Análisis inicial mundial, centro del globo neutral y selección vacía. Límites locales con la misma escala, grosor y opacidad que ADM1/ADM2 globales. Huila sigue disponible como muestra opcional. |
| Una sola coincidencia local, incluso parcial, se abría automáticamente. | Siempre se elige en la lista, con contexto y posibilidad de buscar homónimos en internet. Un nombre con otro país no se recorta para forzarlo a coincidir en Huila. |
| Países y barrios con polígono podían rotularse como departamentos; sin polígono quedaba el resaltado anterior. | Categorías diferenciadas y limpieza del contexto anterior en cada selección. |
| El nivel seleccionado cambiaba entre departamento, municipio y área urbana con el zoom; faltaba encuadre automático. | La detección individual busca el municipio que contiene su posición, resalta el polígono y ajusta la cámara a su extensión. Cambiar el zoom conserva la selección. |
| Las coordenadas del GeoJSON renderizado pueden estar cuantizadas. | La pertenencia usa las coordenadas originales `lon` y `lat` de FIRMS, evitando desplazamientos cerca de un límite. |
| Un centro de celda mundial podía tratarse como un punto municipal. | Las celdas y los grupos se exploran hasta encontrar detecciones individuales; no se atribuye el centro agregado a un municipio. |
| La petición inicial de detecciones mundiales podía truncarse a 50.000 puntos y sustituir la vista explorada. | La vista mundial usa `/global`; el detalle se consulta para la zona visible. |
| El servidor local de Windows dejó de aceptar conexiones tras desconexiones del navegador (`WinError 64`, Proactor). | El arranque CLI de Windows usa un bucle Selector. Linux y el despliegue ASGI conservan su configuración. Se verificó HTTP 200 después de cerrar Chrome. |
| Una resolución municipal lenta podía llegar después de buscar otro lugar. | La selección posterior invalida esa respuesta y limpia el indicador localizado de carga. |

## Comprobaciones

- **544 pruebas correctas con pytest**, incluida la normalización de país, ciudad y barrio, la búsqueda con contexto extranjero, la pertenencia municipal sin inventar un municipio cuando solo hay departamento y el arranque local por plataforma. Permanece una advertencia de deprecación de Starlette TestClient.
- **23/23 comprobaciones en Chrome** en el recorrido `lugares-focos`: país, ciudad y barrio; escala del encuadre; análisis anterior preservado; homónimos; búsqueda local; municipio estable; clic real sobre una detección FIRMS; límite completo dentro del encuadre; municipios reales en Tolima y Venezuela; respuestas obsoletas; ausencia de ADM2; móvil sin desbordes y sin errores de consola.
- **17/17 comprobaciones de regresión del buscador** (teclado, ratón, errores, caché y móvil), **18/18 del mapa** (tema, carga localizada, calendario, dibujo y antimeridiano) y **15/15 del visor de capas** (bases, preajustes, municipios estables y capturas en ambos temas y tamaños).
- Tres solicitudes reales a Nominatim, separadas al menos 1,3 segundos: **España**, un resultado de país; **Medellín, Colombia**, dos resultados, el primero ciudad; **Chapinero, Bogotá, Colombia**, tres resultados de barrio. Los primeros resultados de las tres consultas incluyeron polígonos. También se verificó una tesela NASA GIBS con HTTP 200.
- El recorrido automatizado usa respuestas geocodificadas controladas para repetir casos sin consultar masivamente el servicio público. El clic, las detecciones FIRMS y los límites de Colombia y Venezuela usan los archivos reales del proyecto. Las capturas esperan a que terminen el movimiento y la carga de teselas.

Capturas: [inicio mundial](capturas/lugares_focos_20261115/01_inicio_global.png), [país](capturas/lugares_focos_20261115/02_busqueda_pais.png), [ciudad](capturas/lugares_focos_20261115/02_busqueda_ciudad.png), [barrio](capturas/lugares_focos_20261115/02_busqueda_barrio.png), [clic real y municipio](capturas/lugares_focos_20261115/03_clic_foco_real.png), [Tolima](capturas/lugares_focos_20261115/04_foco_tolima.png), [Venezuela](capturas/lugares_focos_20261115/04_foco_venezuela.png), [móvil](capturas/lugares_focos_20261115/05_barrio_movil.png).

## Alcance y límites

La búsqueda conserva el área de los calendarios hasta pulsar **Analizar esta zona**. Los resultados remotos se analizan como recuadro aproximado; el polígono visual no convierte ese conteo en un agregado oficial por barrio. La tarjeta avisa cuando cuenta solo las detecciones cargadas y puede estar incompleta.

Los límites locales funcionan sin internet. El resto depende de geoBoundaries y su cobertura: ADM2 puede representar un municipio o una división equivalente según el país; se rotula así. Si falta la geometría, el mapa centra la detección y muestra el motivo, sin fabricar un límite ni sustituirlo silenciosamente por un departamento. La cobertura de barrios depende de OpenStreetMap/Nominatim. Las teselas NASA también necesitan conexión: una repetición concurrente registró un fallo transitorio de descarga del sombreado adicional; los controles y la selección municipal continuaron funcionando.

Se comprobó escritorio y móvil. No se realizó un estudio con usuarios ni una certificación de accesibilidad. El error de sockets de Windows detectado durante las repeticiones se corrigió en el arranque local; los recorridos posteriores finalizaron con el servidor disponible.

## Reproducción

Con Python y dependencias instaladas según el README:

```powershell
uv run python -m api --datos data/processed/global_nrt --puerto 8000
```

En otra terminal, con Node.js y Chrome:

```powershell
uv run pytest -q
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/lugares_focos_local "C:/Program Files/Google/Chrome/Application/chrome.exe" lugares-focos
```

Reiniciar la API para aplicar el ajuste del arranque de Windows y recargar la pestaña. Se conserva el indicador de carga dentro del mapa y la estructura de la página durante la navegación.
