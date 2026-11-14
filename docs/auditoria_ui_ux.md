# Auditoría UI/UX de la interfaz (2026-11-14)

**Alcance:** `src/ui/static` sobre `main` `0a0d3c7`, con datos reales (`make api-real`, Huila 2024 y 2025, calidad estándar).

**Método:**
- Reglas de la skill *ui-ux-pro-max*, dominios `ux` y `chart`.
- Mediciones automáticas en el navegador: contraste de cada texto visible frente a su fondo efectivo, tamaño de los objetivos interactivos, nombres accesibles, regiones `aria-live`, número de elementos del mapa y tiempo de cambio de año.
- Inspección visual en tema claro, tema oscuro y 375 px.

## Lo que cumple

| regla (prioridad de la skill) | resultado medido |
|---|---|
| Contraste de texto 4,5:1 (1, crítica) | **0 fallos** en claro y en oscuro (texto normal ≥ 4,5:1; texto grande ≥ 3:1) |
| Foco visible (1) | Regla `:focus-visible` presente; el calendario usa tabindex itinerante |
| Nombre accesible (1) | 0 controles sin nombre entre 381 interactivos |
| Mensajes anunciados (8) | `#estado-carga` (status) y `#resumen` con `aria-live` |
| Movimiento reducido (7) | `prefers-reduced-motion` respetado |
| Sin desplazamiento horizontal (5) | 0 px de desborde a 375 px |
| No depender solo del color (1) | Día inusual con borde y texto en el tooltip; NRT con punto y etiqueta «preliminar»; tabla alternativa en la comparación mensual |

## Hallazgos, por prioridad

| # | severidad | hallazgo | evidencia | recomendación |
|---|---|---|---|---|
| 1 | Alta (accesibilidad) | En tema oscuro, el botón de zoom enfocado se vuelve invisible. | `leaflet.css` `.leaflet-bar a:focus { background-color:#f4f4f4 }` gana a `styles.css` y deja el texto #f4f4f5 sobre #f4f4f4. Lo detectó también Orquesta (plan `20261114-050443-793b`). | Añadir `:focus` al selector tematizado y al botón de cierre del popup (subtarea `corregir-leaflet-oscuro`). |
| 2 | Alta (rendimiento y legibilidad) | El mapa dibuja cada foco como dos elementos SVG. | 2025: 7 923 elementos; 2024: **15 931** elementos y **1,56 s** para cambiar de año. La guía de la skill fija el paso a Canvas a partir de 1 000 elementos. A escala de departamento los puntos se tapan entre sí y no transmiten densidad. | Usar `L.map(…, { preferCanvas: true })`. Para la vista anual, mostrar la densidad por celda (círculo por celda-día con tamaño o color según `n_brutas`) y reservar los focos individuales para el día seleccionado o para un zoom ≥ 11. |
| 3 | Media (gráficos) | La leyenda del calendario dice «menos ■■■■ más», sin cifras. | La guía `chart` de mapas de calor pide una leyenda numérica de la escala. | Mostrar los cortes reales, por ejemplo «1–3 · 4–9 · 10–25 · 26+ focos», calculados con los mismos cuantiles que pintan las celdas. |
| 4 | Media (táctil) | Las celdas del calendario miden 13×13 px con 2 px de separación. | WCAG 2.2 2.5.8 pide 24×24 px o separación equivalente. Hay alternativa por teclado, pero no táctil. | Por debajo de 600 px, celdas de al menos 24 px con desplazamiento horizontal dentro de la tarjeta, o un selector de día y mes como alternativa. |
| 5 | Baja (tipografía) | Hay textos de menos de 12 px. | Atribución del mapa: 10 px. Etiquetas de mes de la temporada: 11 px. | Subir las etiquetas de mes a 12 px. La atribución puede quedarse en 10–11 px (convención de mapas), pero con el contraste ya verificado. |
| 6 | Baja (maquetación) | Hay un hueco vacío bajo el mapa en escritorio. | Con datos reales el panel derecho es mucho más alto que el mapa (altura fija). | Mover «Incertidumbre» bajo el mapa o hacer el panel desplegable. No usar `position: sticky`: se probó y tapaba el calendario. |
| 7 | Baja (enlaces en línea) | Los enlaces de «Periodos críticos» miden 17 px de alto. | Son enlaces dentro del texto, así que aplica la excepción *inline* de WCAG 2.5.8. | Opcional: `padding-block: 4px` para facilitar el toque. |

## Fuera de la base de la skill

La consulta «map data density clustering» no devolvió coincidencias en la base de la skill. La recomendación de densidad por celda del hallazgo 2 se apoya en la guía `chart` para datos geográficos (Canvas a partir de 1 000 elementos; leyenda con cortes claros) y en el criterio propio del proyecto. No es una regla literal de la base.
