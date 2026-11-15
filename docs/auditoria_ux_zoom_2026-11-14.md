# Auditoría UX: continuidad al explorar el mapa

14 de noviembre de 2026 · `feat/globo-global`.

**Iteración posterior:** el intercambio de motores descrito aquí fue retirado. El estado actual está documentado en [planeta continuo, límites globales y carga localizada](planeta_continuo_2026-11-14.md).

## Alcance

Se revisaron las tres capturas aportadas, los estilos, la navegación entre MapLibre y Leaflet y el comportamiento en Chrome. La intervención se centra en continuidad visual, estabilidad de paneles y uso del espacio de la barra. Es una revisión técnica y heurística; no incluye entrevistas ni pruebas con usuarios.

## Hallazgos y ajustes

| Prioridad | Hallazgo | Ajuste aplicado |
|---|---|---|
| Alta | El zoom sustituía un globo oscuro por un mapa de calles claro y multicolor. El cambio parecía abrir otra aplicación. | Ambos niveles usan el mismo relieve NASA GIBS, con la misma atenuación y colores de territorio. OpenStreetMap se activa únicamente mediante «Fondo del detalle regional → Calles». |
| Alta | La columna mundial desaparecía y el resumen y la leyenda regionales aparecían flotando sobre el mapa. Cambiaban el ancho útil y la ubicación de la información. | Columna de información permanente: conserva resumen mundial, leyenda y controles. El resumen del análisis regional se consulta en un desplegable dentro de esa columna. En móvil, el mismo conjunto aparece debajo del mapa. |
| Alta | Área y año se ocultaban en el globo; al aparecer en la región cambiaban la altura de la barra. Abrir opciones ampliaba toda la fila. | Barra con los mismos elementos en ambas escalas. Área y año están rotulados como filtros del análisis; el contexto se reduce a «Mundo» o «Región». Tema queda visible. Opciones abre un menú superpuesto, con cierre mediante Escape o clic exterior. |
| Media | El bloque «Análisis de la zona» se retiraba al alejarse; el listado de países perdía su estado al actualizar la resolución. | El bloque permanece disponible y conserva su apertura. La actualización de las agrupaciones conserva también el listado de países abierto. |
| Media | Volver a una zona dentro del recuadro anterior podía conservar resultados del filtro previo. Al volver al globo podía quedar el mensaje «consultando la cobertura». | La exploración consulta el nuevo encuadre y periodo aunque el centro esté dentro del área anterior. El globo recupera el mensaje de cobertura desde sus datos almacenados. |
| Media | El detalle podía extenderse detrás de la columna y ocultar los botones de zoom. | Ambos lienzos reservan exactamente el mismo ancho para el panel; los controles permanecen dentro de la superficie visible. |

El título «Explorador de focos» permanece fijo. Los cambios de contexto se comunican con el indicador de escala y el resultado de la consulta, conservando la altura de la cabecera. La transición entre lienzos usa un fundido breve, desactivado cuando se solicita movimiento reducido. Los lienzos inactivos quedan fuera de la interacción por teclado mediante `inert`.

## Simbología y alcance de los datos

Los círculos conservan la escala FRP existente: amarillo, ámbar, naranja, rojo y rosa, con cortes en 5, 20, 100 y 500 MW. No se cambia la paleta térmica al cruzar el umbral de zoom.

El panel rotula explícitamente «Resumen mundial» y «Periodo mundial». El desplegable regional identifica el año del análisis. Las fechas del mapa se conservan al pasar del globo al detalle. Así se distinguen los totales mundiales, el resultado de la búsqueda espacial y el análisis anual.

## Verificación

- Suite completa: **450 pruebas correctas**; permanece la advertencia de deprecación de Starlette TestClient.
- Chrome, recorrido funcional: **18/18** comprobaciones correctas.
- Chrome, modo `continuidad`: **11/11** comprobaciones correctas. Incluye acercar, alejar, conservar desplegables, comparar geometría, abrir y cerrar opciones, seleccionar calles explícitamente y comprobar móvil sin desborde ni errores de consola.
- Con ventana de 1440 × 1000, el mapa mantuvo **1065 × 790 px**, la columna **310 × 790 px** y la barra **64 px** de altura antes y después de acercarse. Abrir opciones mantuvo esas medidas.
- Datos locales: `data/processed/global_nrt`. Revisión móvil: 390 × 844.

Capturas: [antes del zoom](capturas/ux_continuidad_20261114/14_antes_zoom.png), [después del zoom](capturas/ux_continuidad_20261114/15_despues_zoom.png), [barra con opciones abiertas](capturas/ux_continuidad_20261114/16_barra_opciones.png), [móvil](capturas/ux_continuidad_20261114/17_continuidad_movil.png).

Para reproducir, con la API global iniciada:

```powershell
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/ux_local "C:/Program Files/Google/Chrome/Application/chrome.exe" continuidad
```

## Límites

Se conservan dos motores cartográficos y sus proyecciones; el ajuste estabiliza su presentación y disposición. La carga de teselas depende de la red. El relieve tiene resolución de contexto (nivel nativo máximo 8); para orientación urbana detallada puede elegirse el fondo de calles. Sin red, ambos niveles conservan los países locales. El paso a detecciones regionales sigue condicionado a que ambos mapas usen el mismo conjunto.
