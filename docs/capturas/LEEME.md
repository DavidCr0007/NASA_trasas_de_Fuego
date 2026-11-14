# Capturas de respaldo

Tomadas el 2026-11-13 con `make api`, reglas `armonizacion-0.3.1`, en una ventana de 1280×900 (exportadas a 800 px de ancho).
Los datos son **sintéticos**: muestra histórica 2020–2026 con una anomalía inyectada en agosto de 2026. No son observaciones reales del Huila.

| archivo | qué muestra |
|---|---|
| `01_vista_general.jpg` | Área Huila, año 2026: mapa de focos, 28 días inusuales, temporada con meses pico (agosto, julio, septiembre), periodos críticos (el principal va del 2026-08-10 al 2026-08-15) e insignia PRELIMINAR (NRT). |
| `02_calendario.jpg` | Calendario de actividad 2026 con días inusuales (borde violeta), días NRT (punto blanco), incertidumbre y cita de FIRMS en el pie. |
| `03_dia_seleccionado_huella.jpg` | Día 2026-08-12 seleccionado (24 focos). Con zoom se ve la huella nominal de MODIS (1 km) frente a la de VIIRS (375 m), y la ventana de un foco Terra marcado como preliminar. |
| `04_base_insuficiente.jpg` | Muestra de 3 días (`data/processed/demo`): la línea base responde «Base insuficiente» (1 año frente a los 5 requeridos) y no marca días inusuales. |

Para regenerarlas: `make api` y abrir http://127.0.0.1:8000. Para la cuarta: `uv run python -m api --datos data/processed/demo --puerto 8001`.

## Capturas a retomar (H6)

Las cuatro capturas anteriores muestran la interfaz H4: solo tema claro y sin insignia de origen de los datos. **Deben retomarse** con la interfaz H6 (tema claro y oscuro, insignia de origen, resumen en lenguaje sencillo y calendario accesible).

Las capturas con datos reales de la sección final (`05_real_*` a `08_real_*`) ya muestran la interfaz H6. De los nombres previstos en esta tabla, `06_datos_reales_*` ya está cubierto por `05_real_claro.jpg` y `06_real_oscuro.jpg`; `05_movil_375_*` es para la demo sintética: al tomarlas, usa otro prefijo numérico (p. ej. `10_`) para no confundirlas con las existentes. Las capturas `05`–`09` se retomaron el 2026-11-14 con la rejilla de densidad del mapa (auditoría UI/UX).

| archivo | qué muestra | estado |
|---|---|---|
| `01_vista_general_claro.jpg` | Vista general en tema claro: mapa, resumen, insignias de calidad y de origen. | pendiente |
| `01_vista_general_oscuro.jpg` | Vista general en tema oscuro. | pendiente |
| `02_calendario_claro.jpg` | Calendario con tooltip y día enfocado por teclado. | pendiente |
| `02_calendario_oscuro.jpg` | Calendario en tema oscuro, con tooltip y día enfocado por teclado. | pendiente |
| `03_dia_seleccionado_huella_claro.jpg` | Día seleccionado y huella del píxel (MODIS y VIIRS), tema claro. | pendiente |
| `03_dia_seleccionado_huella_oscuro.jpg` | Día seleccionado y huella del píxel, tema oscuro. | pendiente |
| `04_base_insuficiente_claro.jpg` | Línea base insuficiente, tema claro. | pendiente |
| `04_base_insuficiente_oscuro.jpg` | Línea base insuficiente, tema oscuro. | pendiente |
| `05_movil_375_claro.jpg` | Ventana de 375 px de ancho, tema claro. Sin scroll horizontal. | pendiente |
| `05_movil_375_oscuro.jpg` | Ventana de 375 px de ancho, tema oscuro. | cubierta con datos reales por `08_real_movil_oscuro.jpg`; falta con la demo sintética |
| `06_datos_reales_claro.jpg` | Con `make api-real`: insignia «Datos reales NASA FIRMS». Solo si existe `data/processed/huila_real`. | hecha: ver `05_real_claro.jpg` |
| `06_datos_reales_oscuro.jpg` | Con `make api-real`, tema oscuro. Solo si existe `data/processed/huila_real`. | hecha: ver `06_real_oscuro.jpg` |

**Cómo tomar cada captura**

- **Forzar el tema.** Usar el selector «Tema» de la cabecera: «Claro» u «Oscuro» fijan el tema. Para «Sistema», cambiar la preferencia de color del sistema operativo o del navegador (en el navegador, la emulación de `prefers-color-scheme` de las herramientas de desarrollo también sirve).
- **Ventana de 375 px.** Reducir el ancho de la ventana del navegador a 375 px (o usar el modo de dispositivo móvil de las herramientas de desarrollo con ese ancho).
- **Datos.** `05` y `01`–`04` con `make api` (datos sintéticos, insignia «DATOS SINTÉTICOS (demostración)»). Para `06`, `make api-real` en otra terminal, con `data/processed/huila_real` ya generado.
- **Registro en cada archivo.** Anotar la fecha de la captura, la versión de reglas que muestra la insignia (`armonizacion-0.3.1` o la que aparezca) y el origen de los datos (sintético o real NASA FIRMS). Añadir estos datos en la tabla de arriba al completar cada captura.

## Capturas con datos reales (ruta pública, ADR 0009), retomadas el 2026-11-14

Datos **reales** de NASA FIRMS, calidad estándar, Huila 2025 (`make real` y `make api-real`). Interfaz H6 con las correcciones de la auditoría UI/UX: mapa en Canvas con rejilla de densidad y leyenda numérica.

| archivo | qué muestra |
|---|---|
| `05_real_claro.jpg` | Tema claro: resumen en lenguaje sencillo, insignias «Calidad estándar» y «Datos reales NASA FIRMS», aviso de FIRMS y mapa con densidad en cuadros de ~11 km. |
| `06_real_oscuro.jpg` | El mismo contenido en tema oscuro, con teselas oscurecidas (en oscuro, más claro = más focos). |
| `07_real_comparacion.jpg` | Oscuro: temporada, comparación de 2025 con el promedio histórico mensual y periodos críticos con fecha ISO. |
| `08_real_movil_oscuro.jpg` | 375 px en oscuro: mapa de densidad y su explicación, sin desplazamiento horizontal. |
| `09_real_calendario_oscuro.jpg` | Oscuro: calendario 2025 con leyenda numérica («0 · 1–3 · 4–7 · 8–20 · 21+ focos por día»), días inusuales e incertidumbre bajo el mapa. |

Pendiente: la vista de un día con la huella de cada foco sobre la rejilla nueva. No se pudo capturar en esta sesión porque el panel del navegador estaba en segundo plano y el lienzo del mapa no se repintaba al hacer zoom. Para tomarla: `make api-real`, elegir un día en el calendario (p. ej. el 15 sep 2024) y acercar el mapa. La captura `03_dia_seleccionado_huella.jpg` (demo sintética) muestra la misma idea con la versión anterior del mapa.
