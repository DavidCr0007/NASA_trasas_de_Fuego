# Reestructuración visual y validación

14 de noviembre de 2026 · Rama de trabajo: `feat/globo-global`.

Esta iteración tiene un ajuste posterior de continuidad: [auditoría UX del zoom](auditoria_ux_zoom_2026-11-14.md). El panel y el análisis ahora permanecen disponibles en ambas escalas y la barra conserva su estructura.

## Experiencia aplicada

- El globo abre por defecto. La dirección `/ui/#regional` permite entrar directamente al mapa regional.
- El mapa ocupa el ancho de la vista; el resumen mundial tiene una columna lateral independiente en escritorio y aparece debajo en móvil.
- Los países y la lista de celdas se consultan mediante desplegables. El análisis regional, sus calendarios y la incertidumbre se agrupan en «Análisis de la zona», oculto en el contexto mundial.
- La paleta de la interfaz usa tonos azul pizarra; el fondo geográfico se atenúa para destacar los focos amarillos, naranjas, rojos y rosas. Los cinco colores de FRP son idénticos en los temas claro y oscuro.
- Se conserva el recorrido globo → país → región y el periodo de fechas al pasar al detalle. La agrupación global pasa de 0,5° a 0,25°; la regional se refina de 0,5° a 0,009° según el zoom. A partir del zoom 12, o al seleccionar un día, aparecen detecciones individuales. Todos usan círculos.
- El color siempre representa FRP con cortes fijos en 5, 20, 100 y 500 MW. En agrupaciones se usa el máximo y el tamaño indica cantidad; en detecciones individuales, el tamaño indica FRP. La leyenda explica el significado vigente.
- Se cancelan solicitudes globales reemplazadas por otra consulta y se reutilizan resultados por periodo y resolución. La rotación automática se inicia mediante un botón.

## Temperatura y calibración

La API y el CSV exponen ahora `brillo`, conservado en kelvin desde el archivo procesado. La ficha individual presenta kelvin y su conversión a °C; muestra «No disponible» cuando falta. No se calcula temperatura a partir de FRP.

La guía accesible desde ambas leyendas explica la diferencia entre potencia radiativa y temperatura de brillo del píxel, las resoluciones nominales MODIS (1 km) y VIIRS (375 m), la saturación de VIIRS I4 y los límites de la huella dibujada. El archivo no aporta incertidumbre térmica individual: no se inventa un margen ± °C ni se confunde confianza de detección con precisión térmica.

Fuentes oficiales consultadas: [campos del producto VIIRS, NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/content/descriptions/FIRMS_VIIRS_Firehotspots.html), [guía VIIRS Collection 2](https://www.earthdata.nasa.gov/s3fs-public/2025-06/VIIRS_C2_AF-375m_User_Guide_1.2.pdf) y [simbología y resolución, NASA FIRMS](https://wiki.earthdata.nasa.gov/spaces/FIRMS/blog/2022/07/24/259818054/How%2Bto%2Bcustomize%2Bthe%2Bfires%2Bdisplayed%2Bin%2BFIRMS).

## Verificación

- Suite completa: **450 pruebas correctas**. Incluye conservación de la temperatura de brillo original del archivo procesado. Advertencia existente: deprecación de `httpx` en Starlette TestClient.
- Recorrido Chrome: **18/18** comprobaciones para mapa, globo, país, zoom al detalle con conservación de fechas, selección de día, tema claro y móvil.
- Rediseño Chrome: **7/7** para entrada mundial, separación entre mapa y panel, apertura de guía, círculos agregados e individuales, ficha térmica y ausencia de desborde móvil y errores de consola.
- Datos utilizados: conjunto local `data/processed/global_nrt`. Verificaciones en escritorio y móvil de 390 × 844. No se realizó una evaluación con usuarios o lectores de pantalla.

Capturas: [entrada mundial](capturas/redisenio_mapa_20261114/11_inicio_globo.png), [guía](capturas/redisenio_mapa_20261114/12_guia.png), [móvil](capturas/redisenio_mapa_20261114/13_globo_movil.png) y [detalle regional](capturas/redisenio_recorrido_20261114/04_zona_explorada.png).

La transición al detalle sigue condicionada a que ambos mapas utilicen el mismo conjunto. Con archivos separados se conserva el aviso y el enlace al visor FIRMS.
