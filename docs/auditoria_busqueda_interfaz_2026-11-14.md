# Búsqueda de lugares y auditoría de interfaz

14 de noviembre de 2026.

## Alcance

Se revisaron la captura aportada, la barra de controles, el resumen mundial y los flujos de búsqueda y análisis sobre el mapa continuo. La revisión combina inspección de código, verificación visual y recorridos de Chrome en escritorio y móvil. No es una certificación WCAG ni una prueba con usuarios.

## Hallazgos y acciones

| Prioridad | Hallazgo | Acción aplicada |
|---|---|---|
| Alta | Faltaba una vía directa para encontrar ciudades, barrios y direcciones. La exploración dependía del zoom y de los filtros regionales. | Buscador global en la barra principal, con resultados identificados por nombre, tipo y contexto geográfico. La consulta se ejecuta con Buscar o Enter. |
| Alta | Elegir un país y después cambiar el periodo podía dejar sus cifras anteriores en la tarjeta seleccionada. | La selección conserva su identidad y actualiza sus cifras con cada respuesta del resumen mundial; permite quitarla explícitamente. Al elegir un lugar, se retira la selección de país anterior para evitar contextos contradictorios. |
| Media | Una única barra para un día ocupaba espacio sin mostrar evolución temporal. | Se omite la gráfica cuando hay menos de dos fechas. La fecha única se presenta una sola vez. |
| Media | Los cinco intervalos FRP se repartían en líneas, dejando el mayor valor aislado y dificultando la comparación. | Escala compacta de cinco columnas con cortes explícitos y los mismos colores que el mapa. La explicación extensa queda en «Cómo leer los círculos». |
| Media | Versión de reglas, procedencia, actualización e instrucciones repetidas competían con periodo y cifras. | Versión y fecha detallada se agrupan en «Origen y actualización». La naturaleza real, sintética o mixta y la calidad NRT permanecen visibles. La alerta de archivo desactualizado también se conserva. |
| Media | Al recorrer un panel largo se perdía el contexto de los totales. | El encabezado «Resumen mundial» permanece visible durante el desplazamiento en escritorio. La tarjeta de país usa un formato corto y la leyenda reduce saltos de línea. |
| Media | Los filtros anuales ocupaban el mismo nivel visual que la exploración mundial. | La barra prioriza búsqueda, encuadre y tema. Área y año siguen disponibles, rotulados como filtros del análisis, dentro de Opciones. Su ubicación no cambia al hacer zoom. |

## Flujo de búsqueda

1. Escribir un lugar; para nombres repetidos, añadir ciudad, departamento o país. Ejemplo comprobado: `Chapinero, Bogota, Colombia`.
2. Pulsar Buscar o Enter. Escribir no dispara consultas. Los resultados presentan su contexto para distinguir ubicaciones con el mismo nombre.
3. Elegir un resultado con ratón o teclado. El mismo mapa se desplaza suavemente y muestra un marcador azul, distinto de los círculos térmicos. Los calendarios conservan el área anterior.
4. Si se quiere cambiar también el análisis, pulsar **Analizar esta zona** en la ficha del marcador. Se aplica el **recuadro aproximado** devuelto por el buscador, no una supuesta delimitación oficial del barrio.

Flechas arriba/abajo recorren resultados; Enter selecciona; Escape cierra y devuelve el foco al campo. Cambiar el texto cancela la petición anterior y una respuesta obsoleta no puede reabrir el desplegable. Los resultados flotan sobre el mapa sin cambiar su tamaño. Las situaciones de búsqueda vacía, falta de resultados, indisponibilidad y límite de consultas se comunican dentro del buscador.

## Proveedor y uso

El endpoint `/buscar-lugares?q=...` usa [Nominatim](https://nominatim.org/release-docs/latest/api/Search/) con datos de OpenStreetMap. La atribución está visible junto al campo. Este servicio localiza lugares; **no incorpora un fondo de calles** y no modifica el relieve natural de NASA GIBS.

Se siguen las condiciones pertinentes del [servicio público de Nominatim](https://operations.osmfoundation.org/policies/nominatim/): búsquedas explícitas, sin autocompletado remoto, identificación de la aplicación y consultas acotadas. El proceso API limita las peticiones nuevas a una cada 1,1 segundos y reutiliza hasta 128 consultas durante 24 horas. Las pruebas automáticas usan una consulta real cacheada y simulan los estados de error; no envían búsquedas por cada tecla ni consultas masivas al proveedor.

`NOMINATIM_URL` permite configurar otro endpoint compatible antes de iniciar la API. El servicio público no requiere clave, pero sí conexión y disponibilidad. La cobertura de barrios y direcciones depende de OpenStreetMap; la búsqueda no garantiza todas las denominaciones locales.

## Verificación

- **469 pruebas correctas** con pytest, incluidas normalización de coordenadas y recuadros, ambigüedad, caché, caducidad, parámetros inválidos, límite de frecuencia, proveedor configurable e indisponibilidad. Se conserva una advertencia de deprecación de Starlette TestClient.
- **17/17 comprobaciones de búsqueda y UX en Chrome:** consulta real de Chapinero, envío con ratón, elección por teclado, origen de los datos visible, marcador sin reconstruir el mapa, análisis explícito del lugar, estados vacíos y de error, descarte de respuestas antiguas, Escape y móvil sin desborde.
- **18/18 comprobaciones de regresión del mapa:** planeta, colores independientes del tema, límites reales, carga localizada, calendario, ficha térmica, dibujo y navegación global.
- Revisión visual en 1440 × 1000 y 390 × 844. Continúan pendientes una evaluación con lectores de pantalla y un estudio de comprensión con usuarios.

Capturas: [panel de un día](capturas/busqueda_ux_20261114/05_panel_un_dia.png), [panel con país seleccionado](capturas/busqueda_ux_20261114/06_panel_auditado.png), [búsqueda de barrios](capturas/busqueda_ux_20261114/07_busqueda_lugares.png), [ubicación seleccionada](capturas/busqueda_ux_20261114/08_lugar_seleccionado.png), [búsqueda móvil](capturas/busqueda_ux_20261114/09_busqueda_movil.png).

Con la API global iniciada, se puede repetir la verificación:

```powershell
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/busqueda_local "C:/Program Files/Google/Chrome/Application/chrome.exe" busqueda
```

Si la API ya estaba iniciada antes de este cambio, reiniciarla para registrar `/buscar-lugares`. El modo `planeta` conserva la verificación del mapa continuo.
