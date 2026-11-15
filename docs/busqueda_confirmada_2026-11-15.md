# Búsqueda por lugar con confirmación

Fecha: 2026-11-15.

## Problema corregido

La lista local solo contenía el departamento del Huila y sus municipios. Uno de ellos se llama **Colombia**. Al buscar ese nombre, la única coincidencia local se seleccionaba automáticamente y bloqueaba la búsqueda del país. Además, los polígonos de países obtenidos por búsqueda remota se etiquetaban como departamentos.

## Comportamiento actual

- Se consultan también los países y territorios del índice mundial local. Las coincidencias exactas de país se presentan antes que los municipios homónimos, conservando ambas opciones.
- **Colombia** muestra **País · COL** y **Municipio · Colombia, Huila, Colombia** como resultados distintos.
- **país Colombia** acota al país; **municipio de Colombia**, **Colombia, Huila** y **Colombia, Huila, Colombia** acotan al municipio. Un contexto distinto, como **Colombia, Antioquia**, no se sustituye por el municipio del Huila.
- Ningún resultado, local o remoto, se abre automáticamente, aunque sea único. Seleccionarlo muestra una revisión con nombre, categoría y ubicación completa. Solo **Confirmar lugar** cambia el mapa.
- **Volver a resultados**, Escape, cerrar, editar la consulta o cambiar de idioma invalidan la selección pendiente. La navegación por teclado y el foco se conservan dentro del buscador.
- Los países se etiquetan como países. Los barrios y localidades remotos conservan su categoría. La búsqueda mantiene el mismo lienzo y el área del calendario hasta que se solicita el análisis.
- La confirmación está disponible en español, inglés y francés. No utiliza ventanas nativas de confirmación ni recarga la página.

El índice local permite buscar países y territorios sin internet; para su resaltado se reutiliza la geometría simplificada de Natural Earth cuando existe. Los resultados sin polígono usan su marcador y encuadre. Este contexto no certifica límites oficiales ni modifica la procedencia de los datos FIRMS.

## Validación

**571 pruebas de Python correctas**, incluidas las consultas homónimas, el nivel solicitado y el contexto geográfico. **16/16 comprobaciones en Chrome**: país frente a municipio, confirmación explícita, ausencia de movimiento previo, cancelación, consulta editada, categoría remota, idiomas, mismo mapa y móvil sin desbordamiento. El resultado remoto de barrio del recorrido se controla en el navegador para comprobar el flujo sin depender del orden de un proveedor externo.

También pasaron **17/17 comprobaciones del recorrido de idiomas**. Una consulta real de `Colombia` a `/buscar-lugares` devolvió `nombre: Colombia`, `tipo: País`, contrastando la categoría del proveedor sin seleccionar ningún resultado automáticamente.

Evidencia: [opciones de Colombia](capturas/confirmacion_lugares_20261115/01_colombia_opciones.png), [confirmación del país](capturas/confirmacion_lugares_20261115/02_confirmar_pais.png), [móvil en francés](capturas/confirmacion_lugares_20261115/03_confirmacion_movil_fr.png).

Con una API local en marcha:

```powershell
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/confirmacion_lugares "C:/Program Files/Google/Chrome/Application/chrome.exe" confirmacion
```
